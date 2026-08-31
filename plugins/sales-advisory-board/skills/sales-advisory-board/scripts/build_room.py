#!/usr/bin/env python3
"""
build_room.py — the render layer for Sales Advisory Board.

    python3 scripts/build_room.py --sitting <sitting.json> --out <room.html>

Renders ONE of four room states from a sitting JSON:
    empty      first load: how-it-works card + 5 example cases (illustrative only)
    convening  early: stage ticker + preliminary read, dimmed bench
    reading    progressive: readable round one, reading/ready tab strip, progress strip
    verdict    the full signed minute: 5 tabs (pv / p1 / p2 / p3 / pn),
               chair on the bench, follow-up chips on pn

The room is an OUTPUT SURFACE ONLY. There is no composer and no relay: the case
arrives through the host's chat-side elicitation form, the sitting runs in the
live session, and every state is pushed here with update_artifact. Nothing in
this file may call an MCP tool or a scheduled task (measured 21 Aug 2026: the
artifact bridge can only reach REMOTE connectors, and askClaude is model-locked
to the host model — so in-room input costs a connector AND costs Opus).

Everything is poured into assets/templates/room-template.html, which is
boardroom-shell-v6-q3.html with ONLY the content regions tokenised. The base64
bench avatars live in the template and are harvested from it at render time —
nothing outside the template is ever emitted.

Python 3 stdlib only. No third-party imports, ever.
"""

import argparse
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEMPLATE = os.path.join(ROOT, "assets", "templates", "room-template.html")

# bench order is fixed by the approved shell — do not reorder
BENCH_ORDER = ["blount", "carnegie", "keenan", "rackham",
               "sandler", "hormozi", "voss", "belfort"]

# hard word budgets for the verdict state. Over budget = never rendered.
# Calibrated 18 Aug 2026 against the real panel height (528px of content at
# the shipped aspect). At these caps the verdict fits with the bottom row
# whole and NOTHING scrolls. The old caps (60/40/85/16) needed 569px and
# crushed the bottom row to zero. Do not raise them without re-measuring.
# Calibrated 18 Aug 2026 by rendering EVERY field at cap and measuring in a
# real browser: at these caps the verdict fits with zero scroll and the
# split-card byline fully visible. Do not raise without re-measuring.
BUDGETS = {"read": 36, "quote": 26, "call": 44, "action": 12, "action_how": 14,
           "action_detail": 130, "dissent": 30, "dissent_full": 130,
           "dissent_who": 6, "quote_meta": 9}

# fixed chrome strings lifted from the approved mockups
CONVFOOT = ("Sittings usually take <b>2&ndash;3 minutes</b>. The room refreshes "
            "itself when the verdict lands &mdash; you can leave and come back.")
PRELIM_FOOT = ("Early read &mdash; can shift in round two. The full transcript "
               "opens with the verdict.")
# 21 Aug 2026: this used to promise "a two-minute setup" that makes verdicts
# personal. There is no setup — installing the skill IS the setup — and nothing
# in the room is clickable, so it was an instruction pointing nowhere. Replaced
# with a line that is true and tells them the one thing they need to know.
BRAINLINE = ("Every quote is real and deep-linked to the moment it was said "
             "&mdash; <b>check any of them</b>.")
ASKLEAD = ("Tell the board what you&#39;re stuck on <b>in the chat</b> &mdash; "
           "tap one of the examples there, or write your own.")
ASKSUB = ("The bench convenes here. Two to three minutes, then the verdict "
          "lands in this room.")
COMPOSER_LINE = ("More questions? Open <b>What next</b> and copy a line into "
                 "the chat &mdash; the board picks up from here.")
NEXT_BTN_STYLE = ("border:0;background:#1c8a3c;color:#fff;font-family:inherit;"
                  "font-size:1.1cqw;font-weight:800;border-radius:.9cqw;"
                  "padding:.85cqw 2.4cqw;cursor:pointer;"
                  "box-shadow:0 .3cqw .9cqw rgba(28,138,60,.35)")

PILLS = {"yt": ("ytpill", "YouTube link"), "book": ("ytpill", "Book link")}

# 21 Aug 2026 — only these schemes may reach an href. A receipt link is always a
# deep link to a video or a book page; anything else is either a mistake or a
# payload. `javascript:` used to render as a live href (found by the 208-case
# bench), which is one hand-written sitting away from a real hole.
SAFE_SCHEMES = ("https://", "http://")

# Fields ending _html are passed through unescaped on purpose (the approved copy
# carries <b>). Nothing user-supplied may ever be routed into one.
#
# 21 Aug 2026, second pass: the first version of this guard listed four field
# names and blocklisted dangerous markup. Both halves were wrong. It missed
# convening.foot_html and prelim.foot_html — which rendered a live <script> —
# and it missed entity-encoded schemes, <base href>, and position:fixed overlays,
# because a blocklist only ever catches the attacks you thought of.
# So: EVERY key ending _html, at any depth, and an ALLOWLIST of the five inline
# tags the approved copy actually uses. Anything else is refused.
_TAG_OK = re.compile(r"</?(?:b|i|em|strong|br)\s*/?>", re.I)
_LEFTOVER = re.compile(r"<|\{\{|&#|&[a-z]+;?\s*:", re.I)


# --------------------------------------------------------------------------
# escaping
# --------------------------------------------------------------------------
_ENT = [("—", "&mdash;"), ("–", "&ndash;"), ("…", "&hellip;"),
        ("×", "&times;"), ("·", "&middot;"), ("→", "&rarr;"),
        ("“", "&ldquo;"), ("”", "&rdquo;"),
        ("‘", "&lsquo;"), ("’", "&#39;"), ("'", "&#39;"),
        ("●", "&#9679;"), ("▶", "&#9654;"), ("✓", "&#10003;")]


def esc(s):
    """Escape a user-supplied TEXT node the way the approved mockups are written.
    Braces are entity-encoded so user text can never collide with {{TOKENS}} —
    the global token pass runs on the whole document after content insertion."""
    s = html.escape("" if s is None else str(s), quote=False)
    s = s.replace("{", "&#123;").replace("}", "&#125;")
    for a, b in _ENT:
        s = s.replace(a, b)
    return s


def safe_link(url):
    """A receipt link is a deep link, nothing else. Anything that is not plain
    http(s) is refused loudly rather than rendered as a live href."""
    u = ("" if url is None else str(url)).strip()
    if not u:
        return ""
    if not u.lower().startswith(SAFE_SCHEMES):
        sys.stderr.write(
            "LINK REJECTED: %r is not an http(s) link. A receipt link is always "
            "a deep link to the moment on video — the room was NOT rendered.\n" % u)
        sys.exit(2)
    return att(u)


def check_html_fields(node, path="sitting"):
    """Walk the WHOLE sitting and allowlist every *_html field at any depth."""
    if isinstance(node, dict):
        for k, v in node.items():
            here = "%s.%s" % (path, k)
            if isinstance(v, str) and k.endswith("_html"):
                stripped = _TAG_OK.sub("", v)
                if _LEFTOVER.search(stripped):
                    sys.stderr.write(
                        "HTML FIELD REJECTED: %s. A passthrough field takes plain "
                        "copy and <b> <i> <em> <strong> <br> — nothing else, and "
                        "nothing user-supplied. The room was NOT rendered.\n" % here)
                    sys.exit(2)
            else:
                check_html_fields(v, here)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            check_html_fields(v, "%s[%d]" % (path, i))


def att(s):
    """Escape a user-supplied ATTRIBUTE value. Quotes are entity-encoded the way
    the approved mockups encode them (&#39; / &quot;), not Python's &#x27;."""
    s = html.escape("" if s is None else str(s), quote=False).replace('"', "&quot;")
    for a, b in _ENT:
        s = s.replace(a, b)
    s = s.replace("{", "&#123;").replace("}", "&#125;")
    return s


# --------------------------------------------------------------------------
# budget guard
# --------------------------------------------------------------------------
_PUNCT_ONLY = re.compile(r"^[\W_]+$", re.UNICODE)


def words(s):
    """Word count. Standalone punctuation (em dashes, middots) does not count."""
    return len([t for t in str(s or "").split() if not _PUNCT_ONLY.match(t)])


def die_budget(field, count, cap):
    sys.stderr.write(
        "BUDGET EXCEEDED: %s is %d words, the hard cap is %d. "
        "The verdict was NOT rendered — cut %d word(s) and rerun.\n"
        % (field, count, cap, count - cap))
    sys.exit(2)


def die_sitting(msg):
    sys.stderr.write("SITTING ERROR: %s The room was NOT rendered.\n" % msg)
    sys.exit(2)


# Panel ids land in an id= and a data-p= attribute unescaped, because they are
# structural identifiers rather than prose. That made them the last raw sink in
# the file: `"id": 'p1"><script>…'` rendered live in the verdict state. They are
# now spelled out, and anything that is not one of them is refused.
PANEL_IDS = ("pv", "p1", "p2", "p3", "pn")


def panel_id(val, where):
    v = ("" if val is None else str(val)).strip()
    if v not in PANEL_IDS:
        die_sitting("%s is %r, and a panel id is one of %s."
                    % (where, v, ", ".join(PANEL_IDS)))
    return v


def as_int(val, where, lo=0, hi=8):
    """A count that arrives as "six" used to be a traceback, not a message."""
    try:
        n = int(val)
    except (TypeError, ValueError):
        die_sitting("%s is %r, which is not a number." % (where, val))
    if not lo <= n <= hi:
        die_sitting("%s is %d, outside %d-%d." % (where, n, lo, hi))
    return n


def bench_surname(slug):
    """The chair's surname, lowercased — what a ballot row votes for."""
    return ("" if slug is None else str(slug)).strip().lower()


def check_structure(sitting):
    """Everything SKILL.md says is a hard rule, enforced where it can't be
    forgotten. Written 21 Aug 2026 after a bench got all of the following past
    the renderer with exit 0: Carnegie seated as chair with a YouTube quote card
    under his name, a nine-voter ballot, an 8-0 split that still named a
    dissenter, and an anonymous receipt with no speaker on it. A rule with no
    code behind it is a suggestion."""
    # --- Carnegie: named, never quoted, never chairs ------------------------
    if (sitting.get("chair") or "").lower() == "carnegie":
        die_sitting("Carnegie cannot chair — his corpus is too damaged to quote "
                    "and the chair is the seat that speaks with receipts.")
    v = sitting.get("verdict") or {}
    speeches = [s for rd in (sitting.get("rounds") or [])
                for s in (rd.get("speeches") or [])]
    for s in speeches:
        if (s.get("who") or "").lower() == "carnegie" and s.get("quote"):
            die_sitting("Carnegie carries a quote card. He is never quoted — "
                        "name his Field-Manual principle instead.")
    # --- every receipt names a real speaker ---------------------------------
    for i, q in enumerate(list(v.get("quotes") or []) +
                          [s["quote"] for s in speeches if s.get("quote")]):
        if not (q.get("who") or "").strip():
            die_sitting("a receipt has no speaker on it. Copy the engine's "
                        "ATTRIBUTE AS line into quote.who — an anonymous quote "
                        "is worthless to someone deciding what to watch.")
        if "carnegie" in (q.get("who") or "").lower():
            die_sitting("a receipt is attributed to Carnegie, who is never quoted.")
        if not (q.get("link") or "").strip():
            die_sitting("a receipt has no link. The link is the proof.")
    # --- the ballot is eight seats, once each -------------------------------
    ballot = sitting.get("ballot") or []
    if ballot:
        whos = [(b.get("who") or "").lower() for b in ballot]
        if len(ballot) != 8 or sorted(whos) != sorted(BENCH_ORDER):
            die_sitting("the ballot is not the eight seats voting once each "
                        "(got %d: %s). It is copied from chair.py, never written."
                        % (len(ballot), ", ".join(sorted(whos))))
    # --- the split adds up, AND agrees with the ballot it summarises ---------
    # Every number here used to be taken on trust, so a verdict could render
    # "6 of 8 backed Sandler" over a ballot where all eight voted Belfort. The
    # ballot is the record; the split is a summary of it, and a summary that
    # disagrees with its own record is the one thing a signed minute may never do.
    sp = v.get("split") or {}
    chair_last = bench_surname(sitting.get("chair"))
    if sp:
        votes = as_int(sp.get("votes"), "verdict.split.votes")
        of = as_int(sp.get("of") or 8, "verdict.split.of")
        if of != 8:
            die_sitting("the split is out of %d, and the bench is eight." % of)
        el = sitting.get("elected") or {}
        if el and (as_int(el.get("for"), "elected.for")
                   + as_int(el.get("against"), "elected.against") != 8):
            die_sitting("elected.for + elected.against must be 8.")
        if el and as_int(el.get("for"), "elected.for") != votes:
            die_sitting("elected.for is %s but the split says %d backed the chair."
                        % (el.get("for"), votes))
        if ballot:
            counted = sum(1 for b in ballot
                          if (b.get("vote") or "").strip().lower() == chair_last)
            if counted != votes:
                die_sitting("the split claims %d of 8 backed %s, but the ballot "
                            "shows %d. The ballot is the record."
                            % (votes, chair_last.title(), counted))
        if votes == 8 and (v.get("dissent") or {}).get("who"):
            die_sitting("the vote is unanimous but a dissenter is named.")
        if sp.get("lead_label") and chair_last not in \
                str(sp["lead_label"]).lower():
            die_sitting("split.lead_label says %r but %s chairs."
                        % (sp["lead_label"], chair_last.title()))
    # --- the dissenter is a seat that actually dissented ---------------------
    dw = (v.get("dissent") or {}).get("who") or ""
    if dw and ballot:
        named = [w for w in BENCH_ORDER if w in dw.lower()]
        if not named:
            die_sitting("the dissent names %r, who is not on the bench." % dw)
        for w in named:
            row = next((b for b in ballot if (b.get("who") or "").lower() == w), None)
            if row and (row.get("vote") or "").strip().lower() == chair_last:
                die_sitting("%s is named as a dissenter but voted for the chair."
                            % w.title())


_CORPUS_CACHE = []


def _corpus_text():
    """Whitespace-normalised text of every adviser corpus, read exactly the way
    search.py reads it (corpus_units + parse_raw, which strips the [m:ss]
    markers). Built once per process."""
    if not _CORPUS_CACHE:
        sys.path.insert(0, HERE)
        import search as _search
        chunks = []
        for _slug, d in _search.adviser_dirs():
            for path, raw in _search.corpus_units(d):
                parsed = _search.parse_raw(path, raw)
                if parsed:
                    chunks.append(" ".join(t for _sec, t in parsed[4]))
        _CORPUS_CACHE.append(re.sub(r"\s+", " ", " ".join(chunks)))
    return _CORPUS_CACHE[0]


def check_receipts_verbatim(sitting):
    """Every receipt's words must exist verbatim in the corpus search.py reads.
    Whitespace is normalised, nothing else — a quote that is not in the corpus
    is a fabrication, however plausible the link under it."""
    v = sitting.get("verdict") or {}
    speeches = [s for rd in (sitting.get("rounds") or [])
                for s in (rd.get("speeches") or [])]
    quotes = list(v.get("quotes") or []) + \
        [s["quote"] for s in speeches if s.get("quote")]
    if not quotes:
        return
    try:
        hay = _corpus_text()
    except Exception as e:                                    # noqa: BLE001
        die_sitting("the advisers/ corpus cannot be read (%s) — likely an "
                    "incomplete install; reinstall the skill. Quotes come from "
                    "the corpus or not at all." % e)
    for q in quotes:
        needle = re.sub(r"\s+", " ", str(q.get("text") or "")).strip()
        if needle and needle not in hay:
            die_sitting("the quote %r is not verbatim in any adviser corpus. "
                        "A receipt is search.py output copied untouched, or it "
                        "does not exist." % needle)


def check_budgets(sitting):
    """Hard guard. Only a verdict-state sitting is budgeted."""
    v = sitting.get("verdict") or {}
    n = words(v.get("read"))
    if n > BUDGETS["read"]:
        die_budget("verdict.read", n, BUDGETS["read"])
    for i, q in enumerate(v.get("quotes") or [], 1):
        n = words(q.get("text"))
        if n > BUDGETS["quote"]:
            die_budget("verdict.quotes[%d].text" % i, n, BUDGETS["quote"])
    n = words((v.get("call") or {}).get("text"))
    if n > BUDGETS["call"]:
        die_budget("verdict.call.text", n, BUDGETS["call"])
    actions = v.get("actions") or []
    if len(actions) != 2:
        sys.stderr.write(
            "BUDGET EXCEEDED: verdict.actions has %d entries, exactly 2 are "
            "required. The verdict was NOT rendered.\n" % len(actions))
        sys.exit(2)
    for i, a in enumerate(actions, 1):
        do = a.get("do") if isinstance(a, dict) else a
        how = a.get("how") if isinstance(a, dict) else None
        n = words(do)
        if n > BUDGETS["action"]:
            die_budget("verdict.actions[%d]" % i, n, BUDGETS["action"])
        if how:
            n = words(how)
            if n > BUDGETS["action_how"]:
                die_budget("verdict.actions[%d].how" % i, n, BUDGETS["action_how"])
        detail = a.get("detail") if isinstance(a, dict) else None
        if detail:
            n = words(detail)
            if n > BUDGETS["action_detail"]:
                die_budget("verdict.actions[%d].detail" % i, n,
                           BUDGETS["action_detail"])
    n = words((v.get("dissent") or {}).get("text"))
    if n > BUDGETS["dissent"]:
        die_budget("verdict.dissent.text", n, BUDGETS["dissent"])
    n = words((v.get("dissent") or {}).get("full"))
    if n > BUDGETS["dissent_full"]:
        die_budget("verdict.dissent.full", n, BUDGETS["dissent_full"])

    # the attribution line and the citation line are rendered text too — they
    # wrap and push the card taller, so they are budgeted like everything else
    n = words((v.get("dissent") or {}).get("who"))
    if n > BUDGETS["dissent_who"]:
        die_budget("verdict.dissent.who", n, BUDGETS["dissent_who"])
    for i, q in enumerate(v.get("quotes") or []):
        n = words(q.get("meta"))
        if n > BUDGETS["quote_meta"]:
            die_budget("verdict.quotes[%d].meta" % i, n, BUDGETS["quote_meta"])

    # ---- HUNG BENCH -------------------------------------------------------
    # chair.py can return a tie. A 4-4 used to render as a signed verdict with a
    # 50/50 bar and the word "elected" over it, which is a lie the user cannot
    # see. A tie is a legitimate outcome and it has to be SAID, not smoothed.
    sp = v.get("split") or {}
    votes, of = int(sp.get("votes") or 0), int(sp.get("of") or 8)
    if of and votes * 2 <= of and not sp.get("hung"):
        sys.stderr.write(
            "HUNG BENCH: %d of %d is not a majority. A tie is a real outcome, "
            "but it must be declared: set verdict.split.hung true, say in "
            "verdict.read that the bench split, and make the call the chair's. "
            "The verdict was NOT rendered.\n" % (votes, of))
        sys.exit(2)

    # ---- SENSE GATE -------------------------------------------------------
    # Truncated words pass a word count and still read as garbage ("…your
    # answer about this"). Every prose field must end like a finished thought.
    # Quotes are exempt: they are verbatim captions and are never touched.
    # Words that cannot legally END an English clause. Stranded prepositions
    # ("something to react to") are legitimate and are NOT in this set.
    DANGLING = {"the", "a", "an", "and", "or", "but", "of", "your", "his",
                "her", "their", "its", "if", "because", "while", "whereas",
                "although", "unless", "is", "are", "was", "were", "very"}
    def die_sense(field, tail):
        sys.stderr.write(
            "SENSE CHECK FAILED: %s ends mid-thought (\u2026%s). The verdict was "
            "NOT rendered \u2014 rewrite the sentence to fit the budget, never "
            "chop words off the end.\n" % (field, tail))
        sys.exit(2)
    def sense(field, text, terminal):
        t = (text or "").strip()
        if not t:
            return
        if terminal and t[-1] not in ".!?\u2026\"'\u2019\u201d)":
            die_sense(field, "'" + " ".join(t.split()[-4:]) + "'")
        lastword = t.split()[-1].strip(".!?,;:\u2026\"'\u2019\u201d()").lower()
        if lastword in DANGLING:
            die_sense(field, "'" + " ".join(t.split()[-4:]) + "'")
    sense("verdict.read", v.get("read"), True)
    sense("verdict.call.text", (v.get("call") or {}).get("text"), True)
    sense("verdict.dissent.text", (v.get("dissent") or {}).get("text"), True)
    sense("verdict.dissent.full", (v.get("dissent") or {}).get("full"), True)
    for i, a in enumerate(actions, 1):
        do = a.get("do") if isinstance(a, dict) else a
        how = a.get("how") if isinstance(a, dict) else None
        sense("verdict.actions[%d].do" % i, do, False)
        sense("verdict.actions[%d].how" % i, how, False)
        if isinstance(a, dict):
            sense("verdict.actions[%d].detail" % i, a.get("detail"), True)


# --------------------------------------------------------------------------
# bench harvest — seat blocks in the template are regex-parseable
# --------------------------------------------------------------------------
SEAT_RE = re.compile(
    r'<div class="seat \{\{SEAT_CLASS_(?P<i>\d)\}\}">'
    r'<img class="face " src="(?P<src>[^"]*)" data-real="(?P<real>[^"]*)" '
    r'data-av="(?P<av>[^"]*)" alt="" />'
    r'\{\{SEAT_BADGE_\d\}\}'
    r'<div class="fn">(?P<fn>[^<]*)</div>'
    r'<div class="ln">(?P<ln>[^<]*)</div>'
    r'<div class="rl">(?P<rl>[^<]*)</div>')


def harvest_bench(tpl):
    """surname(lower) -> {i, src, real, av, first, last, role}."""
    bench = {}
    for m in SEAT_RE.finditer(tpl):
        bench[m.group("ln").lower()] = {
            "i": int(m.group("i")), "src": m.group("src"),
            "real": m.group("real"), "av": m.group("av"),
            "first": m.group("fn"), "last": m.group("ln"), "role": m.group("rl"),
        }
    if sorted(bench) != sorted(BENCH_ORDER):
        sys.stderr.write("TEMPLATE ERROR: bench harvest found %s, expected %s\n"
                         % (sorted(bench), sorted(BENCH_ORDER)))
        sys.exit(3)
    return bench


def who(bench, slug, field="av"):
    """in-body faces use data-av; the chairchip uses the seat src."""
    key = (slug or "").strip().lower().split()[-1] if slug else ""
    if key not in bench:
        sys.stderr.write("SITTING ERROR: unknown adviser %r (bench: %s)\n"
                         % (slug, ", ".join(BENCH_ORDER)))
        sys.exit(3)
    return bench[key][field]


def full_name(bench, slug):
    k = (slug or "").strip().lower().split()[-1]
    b = bench[k]
    return "%s %s" % (b["first"], b["last"])


def pct(part, whole):
    v = 100.0 * float(part) / float(whole or 1)
    return ("%.4f" % v).rstrip("0").rstrip(".")


# --------------------------------------------------------------------------
# tally bar
# --------------------------------------------------------------------------
# A 7-1 vote gives the minority segment 12.5% of the bar. In the verdict's
# split card that bar is only ~28cqw wide, so "1 other" was rendering as a
# sliced half-word inside a coloured block — it read as a rendering fault, not
# as a vote. The label now goes in ONLY when the segment can hold it whole;
# otherwise the segment is a plain colour block and the count is carried by the
# byline underneath ("7 of 8 backed Keenan"), which says it in words anyway.
#
# Widths are in cqw (the room is a container-query box, everything scales with
# it), so this stays correct at every render size. 0.55 is the average glyph
# width of the bar's bold face as a fraction of its font-size.
GLYPH_W = 0.55


def tallybar(lead, other, lead_label, other_label, container_cqw, font_cqw,
             compact=False):
    """Two-segment tally bar. Labels are dropped, never clipped."""
    def label(pct_s, text, pad_cqw):
        text = (text or "").strip()
        if not text:
            return ""
        need = len(text) * GLYPH_W * font_cqw + pad_cqw
        return esc(text) if (container_cqw * float(pct_s) / 100.0) >= need else ""
    return ('<div class="tallybar%s">'
            '<div class="tv" style="width:%s%%">%s</div>'
            '<div class="tv2" style="width:%s%%">%s</div></div>'
            % (" compact" if compact else "",
               lead, label(lead, lead_label, 1.8),
               other, label(other, other_label, 1.4)))


# --------------------------------------------------------------------------
# fragment builders
# --------------------------------------------------------------------------
def paras(t):
    """Overlay body: blank-line-separated paragraphs, never a blob."""
    return "".join("<p>%s</p>" % esc(x.strip())
                   for x in (t or "").split("\n\n") if x.strip())


def f_quote(q):
    pill = PILLS.get((q.get("pill") or "yt").lower(), PILLS["yt"])
    # Verbatim captions start and stop mid-sentence. The words are sacred, the
    # framing is ours: a fragment is shown AS a fragment, with ellipses, so a
    # lowercase start or a hanging end reads as a clip, not a typo.
    t = (q.get("text") or "").strip()
    frag_open = "\u2026" if (t and (t[0].islower() or t[0] in ",;")) else ""
    frag_close = "\u2026" if (t and t[-1] not in ".!?\u2026") else ""
    who_html = ('<span class="qwho">%s</span> ' % esc(q["who"])) if q.get("who") else ""
    return ('<div class="quote"><span class="qtext">%s%s%s</span><span class="src">'
            '%s<a href="%s" class="%s" target="_blank" rel="noopener">%s</a>'
            ' &middot; %s</span></div>'
            % (frag_open, esc(t), frag_close, who_html,
               safe_link(q.get("link")), pill[0], pill[1], esc(q.get("meta"))))


def f_mrow(bench, sp):
    av = who(bench, sp.get("who"))
    name = esc(sp.get("name") or full_name(bench, sp.get("who")))
    text = esc(sp.get("text"))
    if sp.get("lead"):
        quote = f_quote(sp["quote"]) if sp.get("quote") else ""
        return ('<div class="mrow leadrow"><img class="face avface" src="%s" alt=""/>'
                '<div class="mtxt"><span class="mname">%s</span>'
                '<span class="leadtag">%s</span><p>%s</p>%s</div></div>'
                % (av, name, esc(sp.get("seat_label") or "Lead seat"), text, quote))
    if sp.get("replying_to") or sp.get("replying_note"):
        if sp.get("replying_to"):
            lab = "&rarr; replying to <b>%s</b>" % esc(sp["replying_to"])
        else:
            lab = esc(sp["replying_note"])
        cls = " reply" if sp.get("reply") else ""
        return ('<div class="mrow%s"><img class="face avface" src="%s" alt=""/>'
                '<div class="mtxt"><span class="mname">%s</span>'
                '<span class="replyto">%s</span><p>%s</p></div></div>'
                % (cls, av, name, lab, text))
    return ('<div class="mrow"><img class="face avface" src="%s" alt=""/>'
            '<div class="mtxt"><span class="mname">%s</span>'
            '<span class="mseat">%s</span><p>%s</p></div></div>'
            % (av, name, esc(sp.get("seat_label")), text))


def f_vchip(bench, b):
    return ('<div class="vchip"><img class="face avface" src="%s" alt=""/>'
            '%s <span class="varrow">&rarr;</span> <b>%s</b>'
            '<span class="why">%s</span></div>'
            % (who(bench, b.get("who")),
               esc(b.get("voter") or bench[b["who"].lower()]["last"]),
               esc(b.get("vote")), esc(b.get("why"))))


def f_excase(t):
    # Illustrative only — the tappable copies of these live in the chat-side
    # elicit form. Nothing in the room is clickable, so nothing here may look
    # clickable: no "Ask this →" affordance, no pointer cursor (see .excase
    # override in room-optiona-css).
    return '<div class="excase"><p>%s</p></div>' % esc(t)


def f_stagerow(s):
    # `state` lands in a class attribute and `icon` used to land raw in the
    # markup — both were breakout points until 21 Aug 2026. Neither is prose, so
    # neither is free text: the state is an enum and the icon comes from the map.
    icons = {"done": "&#10003;", "now": "&#9654;", "todo": "&middot;"}
    st = (s.get("state") or "todo").lower()
    if st not in icons:
        die_sitting("stage state %r is not done, now or todo." % st)
    return ('<div class="stagerow %s"><span class="st">%s</span>%s</div>'
            % (st, icons[st], esc(s.get("text"))))


def next_chips(sitting, bench):
    """The follow-up strip, GENERATED FROM THE SITTING — never templated.

    The room cannot send anything to chat (measured 21 Aug 2026), so a chip's
    whole job is to write the right sentence to the clipboard. That makes the
    wording load-bearing, and it is why these are generated: a hard-coded strip
    reads as nonsense the moment the verdict says something other than what it
    was written against. "If the call doesn't get me a date" is meaningless
    under a verdict that says hold the price, so the shipped lines below name
    NO channel, NO outcome and NO gender. The only thing interpolated is the
    chair's surname, which every sitting has.

    A sitting may override any chip via verdict.next[]; the defaults are
    complete and correct on their own, so a sitting that says nothing is right.
    """
    chair_last = bench[(sitting.get("chair") or "").lower()]["last"]
    # The set below is what survived a cold read by someone playing the rep who
    # gets handed this on a Monday. Two earlier chips died there: one asked the
    # chair for his exact words (the receipts card already has them) and one
    # asked "if it doesn't work" (the same question as "if they say no"). Both
    # slots went to the two things a rep actually does next — get the words, and
    # come back with the reply they got.
    default = [
        {"label": "Push back on this",
         "hint": "then say what they got wrong",
         "copy": "The board got this wrong because: "},
        {"label": "Write it out for me",
         "copy": "Write it out for me: the exact words to use."},
        # "what if they say no?" sat here until a cold read pointed out that
        # "no" is undefined under half the verdicts this board hands down, and
        # that it was the one chip whose answer a rep could guess. Rehearsal
        # replaced it: it is the best thing the board does and nobody types it
        # unprompted.
        {"label": "Rehearse it with me",
         "copy": "Rehearse it with me: you play them, I'll go first."},
        {"label": "They've come back to me",
         "hint": "then paste what they said",
         "copy": "They've come back to me. What they said: "},
        {"label": "Something they didn't know",
         "hint": "then add the fact",
         "copy": "Something the board didn't know: "},
        {"label": "New decision for the board",
         "hint": "then say what you're deciding",
         "copy": "New decision for the board: "},
    ]
    _ = chair_last  # available to an override; no default chip needs it
    override = (sitting.get("verdict") or {}).get("next") or []
    for i, o in enumerate(override):
        if i < len(default) and isinstance(o, dict):
            # a partial override that keeps the old hint is worse than no
            # override: the label and the hint stop describing the same thing.
            default[i] = {**{k: v for k, v in default[i].items() if k == "copy"},
                          **o} if "label" in o else {**default[i], **o}
    for c in default:
        raw = c.get("copy")
        if not isinstance(raw, str):
            die_sitting("a What-next line is %r, and a chip is a sentence." % raw)
        # \n is not the only line break that reaches a clipboard: U+2028/2029,
        # NEL and the vertical tabs all split a pasted line in two.
        line = re.sub(r"[\r\n\u2028\u2029\u0085\x0b\x0c\x00]+", " ", raw)
        if len(line) > 160:
            sys.stderr.write(
                "CHIP REJECTED: a What-next line is %d characters. A chip is one "
                "sentence a user pastes into chat, not a payload. The room was "
                "NOT rendered.\n" % len(line))
            sys.exit(2)
        c["copy"] = line
    return default


def f_chip(n, c):
    hint = ('<div class="nchint">%s</div>' % esc(c.get("hint"))) if c.get("hint") else ""
    return ('<div class="nchip"><div class="nctxt"><div class="nclab">%s</div>%s'
            '</div><button class="nccopy" type="button" data-copy="%s">Copy</button>'
            '</div>' % (esc(c.get("label")), hint, att(c.get("copy"))))


def body_next(sitting, bench):
    """Panel #pn — the only surface in the room that does anything, and all it
    does is write text to the clipboard. No input, no network, no host bridge."""
    nx = (sitting.get("verdict") or {}).get("next_panel") or {}
    chips = "".join("        " + f_chip(i, c) + "\n"
                    for i, c in enumerate(next_chips(sitting, bench), 1))
    # This copy led with the constraint until a cold read called it out: it
    # explained a limitation the reader would rather not have learned, in the
    # sentence meant to sell them the feature. Lead with what they get.
    lead = esc(nx.get("lead") or
               "Copy a line, paste it into the chat, and the board picks up "
               "exactly where this verdict left off.")
    foot = esc(nx.get("foot") or
               "If what you add changes the call, this room updates in place. "
               "If it doesn't, the board says so and the verdict stands.")
    return ('    <div class="panel" id="pn">\n'
            '      <div class="nextwrap">\n'
            '        <div class="nclead">%s</div>\n'
            '        <div class="ncgrid">\n%s        </div>\n'
            '        <div class="ncfoot">%s</div>\n'
            '      </div>\n'
            '    </div>' % (lead, chips, foot))


def f_roundconc(label, text):
    return ('      <div class="roundconc"><div class="lab">%s</div>\n'
            '      <p>%s</p></div>' % (esc(label), esc(text)))


# --------------------------------------------------------------------------
# tab strips
# --------------------------------------------------------------------------
def tabs_verdict(sitting):
    labs = sitting.get("tabs") or {}
    def L(k, d, s):
        t = labs.get(k) or {}
        return esc(t.get("label") or d), esc(t.get("sub") or s)
    a = L("pv", "The verdict", "the board's answer")
    b = L("p1", "Round one", "every adviser speaks")
    c = L("p2", "Round two", "the disagreements")
    d = L("p3", "The vote", "who they chose")
    e = L("pn", "What next", "ask the board more")
    return (
        '<div class="tabs">\n'
        '      <button class="tab on" data-p="pv" type="button">%s<small>%s</small></button>\n'
        '      <button class="tab" data-p="p1" type="button">%s<small>%s</small></button>\n'
        '      <button class="tab" data-p="p2" type="button">%s<small>%s</small></button>'
        '<button class="tab" data-p="p3" type="button">%s<small>%s</small></button>'
        '<button class="tab" data-p="pn" type="button">%s<small>%s</small></button>\n'
        '    </div>' % (a[0], a[1], b[0], b[1], c[0], c[1], d[0], d[1], e[0], e[1]))


READING_TAB_DEFAULTS = [
    {"state": "locked",   "label": "The verdict", "sub": "being written…"},
    {"state": "reading",  "label": "Round one",   "sub": "you're reading this", "panel": "p1"},
    {"state": "ready",    "label": "Round two",   "sub": "● ready — up next"},
    {"state": "progress", "label": "The vote",    "sub": "▶ in progress"},
]


def tabs_reading(sitting):
    spec = (sitting.get("reading") or {}).get("tab_states") or READING_TAB_DEFAULTS
    out = ['<div class="tabs">']
    for t in spec:
        st = (t.get("state") or "plain").lower()
        lab, sub = esc(t.get("label")), esc(t.get("sub"))
        if st == "locked":
            b = ('<button class="tab locked" type="button" '
                 'style="opacity:.45;cursor:default">%s<small>%s</small></button>')
        elif st == "reading":
            b = ('<button class="tab on reading" data-p="%s" type="button">'
                 '%%s<small>%%s</small></button>'
                 % panel_id(t.get("panel") or "p1", "reading.tab_states[].panel"))
        elif st == "ready":
            b = '<button class="tab ready" type="button">%s<small>%s</small></button>'
        elif st == "progress":
            b = ('<button class="tab" type="button" style="opacity:.6;cursor:default">'
                 '%s<small>%s</small></button>')
        else:
            b = ('<button class="tab" data-p="%s" type="button">%%s<small>%%s</small></button>'
                 % panel_id(t.get("panel") or "p1", "reading.tab_states[].panel"))
        out.append("      " + b % (lab, sub))
    out.append("    </div>")
    return "\n".join(out)


# --------------------------------------------------------------------------
# bodies
# --------------------------------------------------------------------------
def body_empty(sitting):
    e = sitting.get("empty") or {}
    cases = e.get("cases") or []
    rows = "\n".join("      " + f_excase(c) for c in cases)
    return (
        '    <div class="bigask askoff">\n'
        '      <p class="asklead">%s</p>\n'
        '      <p class="asksub">%s</p>\n'
        '    </div>\n'
        '    <div class="excases">\n'
        '      <div class="exlab">%s</div>\n'
        '%s\n'
        '      <div class="brainline">%s</div>\n'
        '    </div>'
        % (e.get("lead_html") or ASKLEAD,
           e.get("sub_html") or ASKSUB,
           esc(e.get("cases_label") or "The kind of decision the board rules on"),
           rows, e.get("brainline_html") or BRAINLINE))


def body_convening(sitting):
    c = sitting.get("convening") or {}
    stages = "\n".join("      " + f_stagerow(s) for s in (c.get("stages") or []))
    p = c.get("prelim") or {}
    return (
        '    <div class="convwrap"><div class="convcard">\n'
        '      <div class="convhead"><span class="pulse"></span>%s</div>\n'
        '%s\n'
        '    </div>\n'
        '    <div class="convfoot">%s</div>\n'
        '    <div class="prelim"><div class="lab">%s</div>\n'
        '      <p>%s</p>\n'
        '      <div class="foot">%s</div>\n'
        '    </div>\n'
        '</div>'
        % (esc(c.get("heading") or "Sitting in progress"), stages,
           c.get("foot_html") or CONVFOOT,
           esc(p.get("label") or "Preliminary — where round one landed"),
           esc(p.get("text")),
           p.get("foot_html") or PRELIM_FOOT))


def body_reading(sitting, bench):
    r = sitting.get("reading") or {}
    pr = r.get("progress") or {}
    ptxt = esc(pr.get("text"))
    if pr.get("bold"):
        ptxt = (ptxt + " " if ptxt else "") + "<b>%s</b>" % esc(pr["bold"])
    rounds = sitting.get("rounds") or []
    rd = next((x for x in rounds if x.get("id") == (r.get("panel") or "p1")),
              rounds[0] if rounds else {})
    rows = "\n".join("      " + f_mrow(bench, s) for s in (rd.get("speeches") or []))
    conc = rd.get("conclusion") or {}
    return (
        '    <div class="progstrip"><span class="pulse"></span>\n'
        '      <span class="ptxt">%s</span>\n'
        '      <span class="peta">%s</span></div>\n'
        '    <div class="panel on" id="%s">\n'
        '%s\n'
        '%s<div style="display:flex;justify-content:center;margin-top:1.4cqw;margin-bottom:7cqw">\n'
        '        <button type="button" style="%s">%s</button>\n'
        '      </div>\n'
        '    </div>\n'
        '    '
        % (ptxt, esc(pr.get("eta")), panel_id(rd.get("id") or "p1", "rounds[].id"), rows,
           f_roundconc(conc.get("label") or "Where round one landed", conc.get("text")),
           NEXT_BTN_STYLE,
           esc(r.get("next_button") or "Finished? Read round two →")))


def panel_round(bench, rd, on=False):
    rows = "\n".join("      " + f_mrow(bench, s) for s in (rd.get("speeches") or []))
    conc = rd.get("conclusion") or {}
    return ('    <div class="panel%s" id="%s">\n%s\n%s\n    </div>'
            % (" on" if on else "", panel_id(rd.get("id"), "rounds[].id"), rows,
               f_roundconc(conc.get("label"), conc.get("text"))))


def panel_vote(sitting, bench):
    v = sitting.get("verdict") or {}
    sp = v.get("split") or {}
    votes, of = int(sp.get("votes") or 0), int(sp.get("of") or 8)
    lead, other = pct(votes, of), pct(of - votes, of)
    chips = "\n".join("          " + f_vchip(bench, b)
                      for b in (sitting.get("ballot") or []))
    note = ('<b>%s</b> chairs this sitting, elected '
            '<b style="color:#1c8a3c">%d</b>&ndash;<b style="color:#c0392b">%d</b>. %s'
            % (esc(full_name(bench, sitting.get("chair"))), votes, of - votes,
               esc(sitting.get("ballot_note"))))
    # the vote panel's bar runs the full band: body 100cqw less 3cqw padding
    # each side and 2.4cqw of band padding each side.
    bar = tallybar(lead, other, sp.get("lead_label"), sp.get("other_label"),
                   container_cqw=89.0, font_cqw=1.0)
    return (
        '    <div class="panel" id="p3">\n'
        '      <div class="voteband"><div class="vlab">%s</div>\n'
        '        %s\n'
        '        <div class="voterow">\n'
        '%s\n'
        '        </div>\n'
        '        <div class="dissent">%s</div>\n'
        '      </div>\n'
        '    </div>'
        % (esc(v.get("vote_label")
               or "The vote — each adviser names who should make the call"),
           bar, chips, note))


def body_verdict(sitting, bench):
    v = sitting["verdict"]
    chair_slug = sitting.get("chair")
    if not chair_slug or chair_slug.lower() not in bench:
        sys.stderr.write("SITTING ERROR: unknown chair slug %r — must be one of %s\n"
                         % (chair_slug, ", ".join(sorted(bench))))
        sys.exit(3)
    el = sitting.get("elected") or {}
    sp = v.get("split") or {}
    votes, of = int(sp.get("votes") or 0), int(sp.get("of") or 8)
    lead, other = pct(votes, of), pct(of - votes, of)
    quotes = "".join(f_quote(q) for q in (v.get("quotes") or []))
    call = v.get("call") or {}
    dis = v.get("dissent") or {}
    chair_last = bench[chair_slug.lower()]["last"]
    acts = v.get("actions") or []
    def _act(n, a):
        do = a.get("do") if isinstance(a, dict) else a
        how = a.get("how") if isinstance(a, dict) else None
        detail = a.get("detail") if isinstance(a, dict) else None
        howh = ('<div class="ahow">%s</div>' % esc(how)) if how else ""
        exp = ""
        if detail:
            exp = ('<button class="dexp aexp" type="button" data-ov="aov" '
                   'data-src="src-a%d" data-title="%s">Expand</button>'
                   '<div class="ovsrc" id="src-a%d" style="display:none">%s</div>'
                   % (n, att(do), n, paras(detail)))
        return ('<div class="act"><span class="an">%d</span>'
                '<div class="atxt"><div class="ado">%s</div>%s</div>%s</div>'
                % (n, esc(do), howh, exp))
    donow = _act(1, acts[0]) + _act(2, acts[1])
    h = (call.get("heading") or "").strip()
    ch_html = ("<h3>%s</h3>" % esc(h)) if h and h.lower() != "the call" else ""

    # Order is fixed: the read -> the call -> do this now -> receipts ->
    # split + disagreement. The answer comes before the evidence.
    pv = (
        '    <div class="panel on" id="pv">\n'
        '      <div class="minute">\n'
        '        <div class="vcard vread"><div class="vlabel" style="color:#3d6fd0">'
        'The read &mdash; what&#39;s actually going on</div>\n'
        '          <p class="reason" style="margin:0">%(read)s</p>\n'
        '        </div>\n'
        '        <div class="thecall"><div class="lab">The call</div>%(ch_html)s\n'
        '          <p>%(ct)s</p></div>\n'
        '        <div class="vcard"><div class="vlabel">Do this now</div>'
        '<div class="donow2">%(donow)s</div></div>\n'
        '        <div class="vcard"><div class="vlabel">'
        'The receipts &middot; verbatim, deep-linked</div>\n'
        '          %(quotes)s\n'
        '        </div>\n'
        '        <div class="vrow">\n'
        '          <div class="vcard"><div class="vlabel">How the board split</div>'
        '<div class="vsplitrow"><div class="vsplitchair"><div class="chairchip">'
        '<img class="face" src="%(cface)s" alt=""/><div><div class="cname">%(cname)s</div>'
        '<div class="clab">Chair &middot; %(eword)s %(efor)d&ndash;%(eag)d</div></div>'
        '</div></div><div class="vsplitvotes">'
        '%(splitbar)s'
        '<div class="vhint" style="margin-top:.3cqw">%(votes)d of %(of)d backed <b>%(clast)s</b> &middot; '
        'full ballot in <b>The vote</b></div></div></div></div>\n'
        '          <div class="vcard"><div class="vlabel" style="color:#c0392b">'
        'Where they disagreed <button class="dexp" id="dexpBtn" type="button" '
        'data-ov="dov" data-src="src-dis" data-title="Where they disagreed">Expand</button></div>'
        '<div class="ddash"><p id="ddashTxt">%(dt)s</p></div>'
        '<div class="ovsrc" id="src-dis" style="display:none">%(dfullp)s</div>'
        '<div class="dwho">%(dw)s <span style="color:#8a8f98;font-weight:600">'
        '&middot; %(dn)s</span></div><div class="vhint">The full clash is in '
        '<b>Round two</b></div></div>\n'
        '        </div>\n'
        '      </div>\n'
        '    </div>'
        % {"read": esc(v.get("read")), "ch_html": ch_html,
           "ct": esc(call.get("text")), "donow": donow, "quotes": quotes,
           # the split card's bar is the narrow one: half the body less the
           # chair chip beside it. ~28cqw, which is why labels get dropped here
           # long before they would in the full-width vote panel.
           "splitbar": tallybar(lead, other, sp.get("lead_label"),
                                sp.get("other_label"), container_cqw=28.0,
                                font_cqw=.82, compact=True),
           "votes": votes, "of": of, "clast": esc(chair_last),
           "cface": who(bench, chair_slug, "src"),
           "cname": esc(full_name(bench, chair_slug)),
           "efor": int(el.get("for") or votes), "eag": int(el.get("against") or of - votes),
           "eword": ("elected" if int(el.get("for") or votes) > int(el.get("against") or of - votes)
                     else "chairs a split bench"),
           "dt": esc(dis.get("text")), "dfullp": paras(dis.get("full") or dis.get("text")),
           "dw": esc(dis.get("who")),
           "dn": esc(dis.get("note") or "voted against the call")})

    parts = [pv]
    for rd in sitting.get("rounds") or []:
        parts.append(panel_round(bench, rd))
    parts.append(panel_vote(sitting, bench))
    parts.append(body_next(sitting, bench))
    return "\n".join(parts)


def reviewed_line(sitting):
    """The footer under the verdict.

    A follow-up that the board considered and did NOT act on is invisible: the
    room looks identical, so "considered, call unchanged" and "nothing ran" are
    the same picture. Re-rendering an unchanged verdict is the wrong fix — it
    trains the user to distrust the room updating at all. One dated line is the
    right one, and it is chrome, so it costs the measured panel no height.
    """
    lr = sitting.get("last_reviewed") or {}
    when, note = esc(lr.get("when")), esc(lr.get("note"))
    if when:
        # "Reviewed 21 Aug, 16:04 · call unchanged" read as a system log to a
        # first-time reader. Say who did it and what happened, in words.
        stem = "The board looked at this again on %s" % when
        if note:
            stem += " &mdash; <b>%s</b>" % note
        return stem + ". More lines to copy in <b>What next</b>."
    return COMPOSER_LINE


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------
def render(sitting, tpl):
    bench = harvest_bench(tpl)
    state = (sitting.get("state") or "verdict").lower()
    if state not in ("empty", "convening", "reading", "verdict"):
        sys.stderr.write("SITTING ERROR: unknown state %r\n" % state)
        sys.exit(3)

    q = sitting.get("question") or {}
    seat_class = {i: "" for i in range(1, 9)}
    seat_badge = {i: "" for i in range(1, 9)}
    seat_word = {i: "" for i in range(1, 9)}

    check_html_fields(sitting)
    if state == "verdict":
        check_structure(sitting)
        check_receipts_verbatim(sitting)
        check_budgets(sitting)
        _ch = (sitting.get("chair") or "").lower()
        if _ch not in bench:
            sys.stderr.write("SITTING ERROR: unknown chair slug %r — must be one "
                             "of %s\n" % (sitting.get("chair"), ", ".join(sorted(bench))))
            sys.exit(3)
        ci = bench[_ch]["i"]
        seat_class[ci] = "chair"
        seat_badge[ci] = '<span class="chairtick">✓</span>'
        seat_word[ci] = '<div class="chairword">CHAIR</div>'
    elif state in ("convening", "reading"):
        # the empty room has no chair AND no speaking seat — bench sits plain
        spk = (sitting.get(state) or {}).get("speaking")
        if spk:
            seat_class[bench[spk.lower()]["i"]] = "speaking"

    if state == "empty":
        e = sitting.get("empty") or {}
        headline = esc(e.get("headline") or "What's the sales problem?")
        qask_lab = esc(e.get("qask_label") or "The bench")
        qask = esc(e.get("qask") or "Eight advisers · every quote real and "
                                    "deep-linked · one verdict you can act on today")
        tabs, body = "", body_empty(sitting)
        # the empty room already says how to reach the board — no footer line
        footline, hidden = "", ' style="display:none"'
    else:
        qask_lab = esc(q.get("asked_label") or "You asked")
        qask = esc(q.get("asked"))
        if state == "verdict":
            headline = esc(q.get("headline"))
            tabs = tabs_verdict(sitting)
            body = body_verdict(sitting, bench)
            footline = sitting.get("footer_html") or reviewed_line(sitting)
            hidden = ""
        else:
            headline = esc(q.get("convening_headline")
                           or "The board is convening…")
            footline = (sitting.get("footer_html")
                        or "The board is sitting &mdash; this room updates "
                           "itself as each round lands.")
            hidden = ""
            if state == "convening":
                tabs, body = "", body_convening(sitting)
            else:
                tabs, body = tabs_reading(sitting), body_reading(sitting, bench)

    out = tpl
    out = out.replace("{{HEADLINE}}", headline)
    out = out.replace("{{QASK_LAB}}", qask_lab).replace("{{QASK}}", qask)
    out = out.replace("    {{TABS}}\n", ("    %s\n" % tabs) if tabs else "    \n")
    out = out.replace("{{BODY}}", body)
    out = out.replace("{{FOOTER_LINE}}", footline)
    out = out.replace("{{FOOTER_HIDDEN}}", hidden)
    for i in range(1, 9):
        out = out.replace("{{SEAT_CLASS_%d}}" % i, seat_class[i])
        out = out.replace("{{SEAT_BADGE_%d}}" % i, seat_badge[i])
        out = out.replace("{{SEAT_WORD_%d}}" % i, seat_word[i])
    # a plain seat is class="seat" in the approved shell, not class="seat "
    out = out.replace('<div class="seat ">', '<div class="seat">')

    left = re.findall(r"\{\{[A-Z_0-9]+\}\}", out)
    if left:
        sys.stderr.write("RENDER ERROR: unsubstituted tokens %s\n" % sorted(set(left)))
        sys.exit(3)
    return out


# ---------------------------------------------------------------------------
# RETIRED 21 Aug 2026 — the artifact relay.
#
# There used to be an --artifact flag here that injected a <script id="board-wiring">
# doing: composer click -> Google Drive write of sales-board-case.json ->
# runScheduledTask('sales-counsel-sitting'). It worked. It was deleted anyway,
# because it cost a Google Drive connector and a background scheduled task to buy
# one button, and both were measured as unavoidable:
#
#   * window.cowork exposes exactly ["callMcpTool","askClaude","runScheduledTask"] —
#     no sendPrompt, no file access, no host frame. Nothing else carries text out.
#   * callMcpTool reaches REMOTE connectors only; every local server (bash,
#     scheduled-tasks, even a read) returns 400. So the case had to go via Drive.
#   * askClaude(prompt, data[]) has no model parameter and does not inherit the
#     session model, so anything answered in-room would not be Opus.
#
# The case now arrives through the host's chat-side elicit form and the sitting runs
# in the live session. No connector, no task, no relay. DO NOT reintroduce this
# without re-measuring the bridge — the full findings are in the 21 Aug 2026 handover.
# ---------------------------------------------------------------------------

SOLO_TITLE = "Sales Advisory Board"

SOLO_CSS = """
<style id="solo-shell">
/* SOLO SHELL (default). This skill ships on its own, so the room must not
   advertise a product line the installer does not own. Hides the parent
   wordmark and the side-rail list of other rooms; both rails are absolutely
   positioned, so nothing reflows. Render with --desk to put them back. */
.brand-center{display:none !important}
.side, .side.left, .side.right{display:none !important}
</style>
"""


def solo_shell(html):
    """Strip the parent-brand furniture from a rendered room.

    Removed outright, not just hidden: the side rails name six other rooms and
    the wordmark names a product line, and a display:none copy still sits in the
    source for anyone who looks. Both asides are well-formed and non-nested, so
    the cut is a safe string operation on RENDERED output — this is not
    hand-editing the template, which stays the single source of truth."""
    html = re.sub(r"<title>.*?</title>",
                  "<title>%s</title>" % SOLO_TITLE, html, count=1, flags=re.S)
    html = re.sub(r'<aside class="side (?:left|right)">.*?</aside>', "",
                  html, flags=re.S)
    html = re.sub(r'<div class="brand-center">.*?</div>', "",
                  html, count=1, flags=re.S)
    if "</head>" in html:
        return html.replace("</head>", SOLO_CSS + "</head>", 1)
    return html.replace("<body", SOLO_CSS + "<body", 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a Sales Board room from a sitting JSON.")
    ap.add_argument("--sitting", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--template", default=TEMPLATE)
    ap.add_argument("--desk", action="store_true",
                    help="render inside the full Bingley desk shell (parent "
                         "wordmark + the other rooms in the side rail). OFF by "
                         "default: a user who installed this skill alone owns "
                         "none of those rooms and must not be shown them.")
    a = ap.parse_args(argv)

    with open(a.sitting, encoding="utf-8") as fh:
        sitting = json.load(fh)
    if not isinstance(sitting, dict):
        die_sitting("the sitting file is valid JSON but not an object — it must be a JSON object "
                    "with a \"state\" field, per the sitting schema in SKILL.md.")
    with open(a.template, encoding="utf-8") as fh:
        tpl = fh.read()

    out = render(sitting, tpl)
    if not a.desk:
        out = solo_shell(out)
    d = os.path.dirname(os.path.abspath(a.out))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(out)
    sys.stderr.write("rendered %s state -> %s (%d bytes)\n"
                     % (sitting.get("state"), a.out, len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
