#!/usr/bin/env python3
"""
the Sales Advisory Board — corpus search engine.

Greps every adviser's curated corpus and returns VERBATIM passages with an
exact-second YouTube deep link, so the board can quote real words, not AI guesses.

Deep-link rule (the trust feature): ?t = (marker seconds - 7), floored at 0,
so playback starts ~7s BEFORE the quoted line (captions drift; landing early
keeps trust). See BUILD-SPEC rule #1.

Book-link rule (text-only advisers, e.g. Carnegie): there is no timestamp to
land on, so the citation opens the Internet Archive reader for that book with a
search query built from the most distinctive 6-8 consecutive words of the
matched window. The reader jumps to the page carrying that phrase, which is the
text equivalent of the -7s video landing. Archive IDs live in TEXT_SOURCES, one
entry per text adviser; an adviser missing from that dict falls back to no link.
Those results are labelled [BOOK] where a video result shows its timestamp.

Usage:
  python3 search.py "price objection" --adviser chris-voss --max 5
  python3 search.py "value equation" --adviser alex-hormozi --context 4
  python3 search.py "ask for referrals"            # all advisers
  python3 search.py --list                          # list advisers + file counts

Output is plain text blocks:
  ADVISER | TITLE
  [m:ss]  <deep link>
  "...verbatim window..."
"""
import argparse
import os
import re
import sys
import urllib.parse

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "advisers")
BASE = os.path.normpath(BASE)

MARKER = re.compile(r"\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]")   # [m:ss] or [h:mm:ss]
YT = re.compile(r"https?://youtu\.be/([\w-]+)")     # line-1 video id
OFFSET = 7                                          # seconds to land before the quote

# Text-only advisers -> the Internet Archive reader for their public-domain book.
# Never hardcode an archive ID at the call site; add the adviser here instead.
# An adviser absent from this dict simply gets no link (graceful, not an error).
TEXT_SOURCES = {
    "dale-carnegie": "https://archive.org/details/dli.bengal.10689.22160",
}

PHRASE_WORDS = 7        # words in the archive search phrase (spec allows 6-8)

SENTENCE_SEG_WORDS = 45     # ~words per segment when splitting a book body
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

# --- OCR / front-matter gates for scanned book corpora ----------------------
# The book scans carry real scan damage ("Justify himsdf", "h ealt| ^", stray ■)
# and long stretches of contents pages and publisher boilerplate. Neither is
# quotable: a damaged receipt reads as OUR typo and burns the whole trust
# mechanism, and a contents page is not a thing anyone said. These gates REJECT
# such spans so the ranker falls through to a clean one. They never repair,
# re-spell or tidy a word — verbatim means untouched; clean means choose better.
SCAN_JUNK = re.compile(r"[■□^~¬†‡|<>{}\\]")
INWORD_DIGIT = re.compile(r"[A-Za-z]\d[A-Za-z]|[A-Za-z]{2}\d")
INWORD_CAPS = re.compile(r"[a-z][A-Z]{2}|[a-z]{2}[A-Z][a-z]")
NO_VOWEL = re.compile(r"\b(?![A-Z]{2,}\b)[bcdfghjklmnpqrstvwxz]{4,}\b", re.I)
DOT_LEADER = re.compile(r"\.\s?\.\s?\.\s?\.")
FRONT_MATTER = re.compile(
    r"\bcontents\b|printed in|trade ?mark|pocket book|see other formats|archive\.org|"
    r"copyright|all rights reserved|\bpart (?:one|two|three|four|i{1,3}v?|iv)\b[;:.]|"
    r"dedicated to|introduction by|by lowell thomas|\bedition\b|publisher|\bpreface\b|"
    r"in a nutshell \d", re.I)


def is_scan_damaged(text):
    """True if the span carries OCR damage. Applied to BOOK corpora only —
    caption text legitimately contains none of these patterns, and running the
    gate over video would reject clean transcripts for stylised punctuation."""
    if SCAN_JUNK.search(text):
        return True
    if INWORD_DIGIT.search(text):
        return True
    if INWORD_CAPS.search(text):
        return True
    if NO_VOWEL.search(text):
        return True
    if DOT_LEADER.search(text):
        return True
    if "*" in text:
        return True
    return False


def is_front_matter(text):
    """True if the span is contents / dedication / publisher boilerplate."""
    return bool(FRONT_MATTER.search(text))


# --- show boilerplate gate for VIDEO corpora -------------------------------
# The book gates above have no video equivalent, and video needs one. Podcast
# transcripts open and close with promo: "go to salesgravy.com/ask, one of our
# producers will reach out", "this week we're facing the challenge of X", "in
# this episode we're going to dive into". Those windows contain the search term,
# so they score STRONG and win — measured 21 Aug 2026, three separate concept
# searches on Blount returned show plugs as the top hit. A receipt that is an
# advert, or an announcement that content is coming, is not something the
# adviser said about selling. This gate REJECTS such spans so the ranker falls
# through to a real one. Like the book gates it never repairs or tidies words.
SHOW_BOILERPLATE = re.compile(
    r"\b(?:go to|visit|head (?:over )?to|check out)\s+\S*\.(?:com|co|io|net|tv)\b|"
    r"\blink in the (?:description|bio|show ?notes)\b|\bshow ?notes\b|"
    r"\b(?:like and |hit (?:the )?)?subscribe (?:to|on|wherever|button)\b|"
    r"\bleave (?:us )?a (?:\d[- ]star )?review\b|\brate (?:and review )?(?:the|this) (?:show|podcast)\b|"
    r"\bone of our producers\b|\bsubmit the form\b|\bsign up (?:at|below)\b|"
    r"\bbrought to you by\b|\bsponsored by\b|\bour sponsors?\b|"
    r"\bwelcome (?:back )?to (?:the|my|another|this)\b|\bthanks for (?:watching|listening|tuning)\b|"
    r"\b(?:in |on )?(?:today'?s|this) (?:episode|video|show)\b|\bwe'?re going to dive into\b|"
    r"\bstay tuned\b|\bcoming up (?:on|in) (?:the|this)\b|\bthis week we'?re\b",
    re.I)


def is_show_boilerplate(text):
    """True if the span is podcast promo, sponsor read, or an announcement of
    content rather than the content. Applied to VIDEO corpora only — the book
    corpora have their own front-matter gate above."""
    return bool(SHOW_BOILERPLATE.search(text))


# --- advisers who may NEVER be quoted verbatim -----------------------------
# Measured 21 Aug 2026. Carnegie's surviving corpus is two OCR scans of the same
# book, and BOTH are partial: 27 of his 29 named principles are simply not in
# the files. What is there carries token-level scan damage ("prime inter«t",
# "w'ounds", "ainything") that no span gate can guarantee to exclude, because
# the corruption sits inside otherwise-ordinary words. A damaged receipt reads
# as OUR typo and burns the trust the whole product runs on.
# So he is FIELD-MANUAL ONLY: named principle, attributed, no verbatim quote and
# no [BOOK] receipt pill. SKILL.md rule 10 already covers this — a named
# Field-Manual principle with no link beats a fabricated link every time.
# To re-enable him, replace the corpus with a complete clean text and drop him
# from this set; nothing else needs to change.
FIELD_MANUAL_ONLY = {"dale-carnegie"}

FIELD_MANUAL_NOTE = (
    "FIELD-MANUAL ONLY — no verbatim receipt available.\n"
    "The surviving corpus is a partial, OCR-damaged scan, so this adviser is\n"
    "never quoted. Cite the named principle from their Field Manual instead,\n"
    "attributed, with no quote card and no [BOOK] pill."
)

# ---------------------------------------------------------------------------
# ATTRIBUTION — who the words on a receipt actually belong to
# ---------------------------------------------------------------------------
# Added 21 Aug 2026 after a 208-case bench found the product's own central claim
# breaking on its chair seat. A corpus folder is named for the SCHOOL, and a span
# from it is not automatically that person speaking:
#   * Sandler's corpus is his organisation teaching his system. David Sandler
#     died in 1995. Every word in it is somebody else's — usually Dave Mattson's.
#   * Rackham's corpus includes films ABOUT him with a narrator.
#   * Every other corpus is a channel, so hosts, guests and interviewers are in
#     it too, and their turns score exactly like the adviser's own.
# "Attribution is sacred" has to mean the name on the card, not just the link.
# So the engine states the mandated attribution with every hit, and the card
# copies it verbatim. A seat is a school of thought; a receipt is a person.
ATTRIBUTION = {
    "david-sandler": {
        "who": "Sandler Training",
        "note": ("David Sandler died in 1995 — this corpus is his organisation "
                 "teaching his system (largely Dave Mattson). NEVER put "
                 "\"David Sandler\" on a quote card."),
    },
    "neil-rackham": {
        "who": "Neil Rackham",
        "note": ("Some files are ABOUT Rackham, narrated by someone else. If the "
                 "window is a narrator describing him, choose another window."),
    },
    "jeb-blount": {"who": "Jeb Blount"},
    "keenan-gap-selling": {"who": "Jim Keenan"},
    "alex-hormozi": {"who": "Alex Hormozi"},
    "chris-voss": {"who": "Chris Voss"},
    "jordan-belfort": {"who": "Jordan Belfort"},
}

SPEAKER_CHECK = (
    "SPEAKER CHECK: this corpus is a channel, so hosts, guests and interviewers "
    "are in it and their turns score the same as the adviser's own. Read the "
    "window and confirm whose words these are before you quote them."
)


def attribution(slug):
    return ATTRIBUTION.get(slug, {"who": slug})


BUNDLE_NAME = "_BUNDLE.txt"
BUNDLE_MARK = re.compile(r"^===FILE=== (.+)$", re.M)


def parse_file(path):
    """Back-compat wrapper: parse one on-disk corpus file."""
    with open(path, encoding="utf-8", errors="ignore") as f:
        raw = f.read()
    return parse_raw(path, raw)


def corpus_units(d):
    """Yield (pseudo_path, raw) for every corpus unit in an adviser dir.
    A packaged corpus may ship each transcripts/ folder as ONE _BUNDLE.txt
    (installer caps a .skill at 200 files); its sections expand here into
    exactly the per-file units the loose layout would produce, in the same
    sorted order, so retrieval, flood caps and chair maths are byte-identical
    either way."""
    for path in iter_corpus_files(d):
        if os.path.basename(path) == BUNDLE_NAME:
            raw = open(path, encoding="utf-8", errors="ignore").read()
            parts = BUNDLE_MARK.split(raw)
            # parts = [preamble, name1, body1, name2, body2, …]
            for i in range(1, len(parts) - 1, 2):
                yield (os.path.join(os.path.dirname(path), parts[i].strip()),
                       parts[i + 1].lstrip("\n"))
        else:
            with open(path, encoding="utf-8", errors="ignore") as f:
                yield (path, f.read())


def sentence_segments(body, target_words=SENTENCE_SEG_WORDS):
    """Split a book-length body into sentence-aligned segments of ~target_words.

    Why this exists (21 Aug 2026): the text branch used to return the WHOLE book
    as one segment. With one segment there is nothing for windows() to slide over
    and nothing for the ranker to choose between, so centre_snippet() always
    landed on the FIRST occurrence of the term — which in a scanned book is the
    contents page. Every Carnegie query came back with front matter. Segmenting
    gives the ranker real candidates, so the damage gates below have something
    clean to fall through to."""
    parts = SENT_SPLIT.split(body)
    segments, buf, count = [], [], 0
    for p in parts:
        p = p.strip()
        if not p:
            continue
        buf.append(p)
        count += len(p.split())
        if count >= target_words:
            segments.append((None, " ".join(buf)))
            buf, count = [], 0
    if buf:
        segments.append((None, " ".join(buf)))
    return segments or [(None, body)]


def parse_raw(path, raw):
    """Return (kind, url_or_None, vid_or_None, title, segments).
    segments = list of (seconds:int|None, text:str). Text-only advisers (no
    youtu.be header) are split into sentence-aligned segments; chair.py rejoins
    them per file, so its maths is unaffected by the segmentation."""
    lines = raw.splitlines()
    if not lines:
        return None
    m = YT.search(lines[0])
    if not m:
        # text-only (e.g. Carnegie): cite by file, no link
        title = os.path.splitext(os.path.basename(path))[0]
        body = " ".join(l.strip() for l in lines if l.strip())
        return ("text", None, None, title, sentence_segments(body))
    vid = m.group(1)
    url = f"https://youtu.be/{vid}"
    title = lines[1].strip() if len(lines) > 1 else vid
    body = "\n".join(lines[2:])
    # split body on [m:ss] markers, keeping the time of the chunk that FOLLOWS each marker
    segments = []
    pos = 0
    last_sec = 0
    for mk in MARKER.finditer(body):
        pre = body[pos:mk.start()].strip()
        if pre:
            segments.append((last_sec, pre))
        h = int(mk.group(1)) if mk.group(1) else 0
        last_sec = h * 3600 + int(mk.group(2)) * 60 + int(mk.group(3))
        pos = mk.end()
    tail = body[pos:].strip()
    if tail:
        segments.append((last_sec, tail))
    return ("video", url, vid, title, segments)


def adviser_dirs(only=None):
    out = []
    for slug in sorted(os.listdir(BASE)):
        d = os.path.join(BASE, slug)
        if not os.path.isdir(d):
            continue
        if only and slug not in only:
            continue
        out.append((slug, d))
    return out


def iter_corpus_files(d):
    for sub in ("transcripts", "text"):
        p = os.path.join(d, sub)
        if os.path.isdir(p):
            for fn in sorted(os.listdir(p)):
                if fn.endswith(".txt"):
                    yield os.path.join(p, fn)


def deep_link(url, seconds):
    if url is None or seconds is None:
        return None
    t = max(0, seconds - OFFSET)
    return f"{url}?t={t}"


def distinctive_phrase(text, words=PHRASE_WORDS):
    """Pick the most distinctive run of consecutive words from a matched window.

    Deterministic: strip quotes/punctuation, then slide a fixed-width window over
    the words and keep the highest-scoring run, earliest position wins a tie.
    A word scores 1 if it is not a stopword and is 5+ characters (the same
    "distinctive" test the search scorer uses), so the phrase we hand Archive is
    the rarest wording in the passage rather than a run of filler."""
    # Scanned books carry OCR line-break hyphens ("criti¬ cizes"). Rejoin them
    # first or the search phrase we send Archive contains half-words.
    text = re.sub(r"[¬­]\s*", "", text)
    toks = re.findall(r"[A-Za-z']+", text)
    toks = [t.strip("'") for t in toks if t.strip("'")]
    if not toks:
        return ""
    if len(toks) <= words:
        return " ".join(toks)

    def weight(w):
        lw = w.lower()
        return 1 if (lw not in STOPWORDS and lw not in FILLER and len(lw) >= 5) else 0

    best_i, best_score = 0, -1
    for i in range(len(toks) - words + 1):
        score = sum(weight(w) for w in toks[i:i + words])
        if score > best_score:       # strict > keeps the earliest run on a tie
            best_i, best_score = i, score
    return " ".join(toks[best_i:best_i + words])


def book_link(slug, text):
    """Archive reader deep link for a text-only adviser, or None if unknown."""
    base = TEXT_SOURCES.get(slug)
    if not base:
        return None                  # unmapped text adviser -> "no link", as before
    phrase = distinctive_phrase(text)
    if not phrase:
        return base
    return f"{base}?q={urllib.parse.quote_plus(phrase)}"


def mmss(seconds):
    if seconds is None:
        return "[book/text]"
    if seconds >= 3600:
        return f"[{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}]"
    return f"[{seconds // 60}:{seconds % 60:02d}]"


def windows(segments, size):
    """Yield (start_seconds, joined_text) over a sliding window of `size` segments."""
    for i in range(len(segments)):
        chunk = segments[i:i + size]
        if not chunk:
            continue
        start_sec = chunk[0][0]
        text = " ".join(c[1] for c in chunk)
        yield start_sec, text


STOPWORDS = set((
    "the a an to of for and or is it in on at by with as do how i my me you your we our "
    "what should can if be are was that this they them their how's i'm don't get got "
    "more most some any not no than then so just like about into out up down").split())

# words too generic to confer a STRONG match on their own
GENERIC = set((
    "think about sales sell selling deal deals people person business customer customers "
    "thing things way ways good better best make made want need going time work").split())

# caption backchannel / filler — windows dominated by these are noise, not quotable
FILLER = set((
    "okay ok yeah yep yup um uh huh hmm right so well like gonna wanna gotta kinda sorta "
    "you know i mean word cool nice sure absolutely totally basically literally actually "
    "stuff things guys guy man dude oh ah eh mhm uhhuh").split())


def is_filler_heavy(text):
    """True if the window is mostly backchannel/filler (low quotable substance)."""
    words = re.findall(r"[a-z']+", text.lower())
    if len(words) < 6:
        return True
    sub = [w for w in words if w not in STOPWORDS and w not in FILLER and len(w) > 2]
    return (len(sub) / len(words)) < 0.45


def centre_snippet(text, terms, limit=320):
    """Return a ~limit-char window centred on the first matched term, so the
    displayed quote actually contains the match (not truncated away)."""
    low = text.lower()
    pos = -1
    for t in sorted(terms, key=len, reverse=True):  # prefer the most distinctive term
        i = low.find(t)
        if i != -1:
            pos = i
            break
    clean = re.sub(r"\s+", " ", text).strip()
    if pos == -1 or len(clean) <= limit:
        return clean if len(clean) <= limit else clean[:limit].rsplit(" ", 1)[0] + "..."
    # map pos into cleaned string approximately by re-finding the term
    low_clean = clean.lower()
    j = low_clean.find(low[pos:pos + 12].strip()[:8]) if pos >= 0 else -1
    if j == -1:
        j = 0
    start = max(0, j - limit // 3)
    end = min(len(clean), start + limit)
    out = clean[start:end]
    if start > 0:
        out = "..." + out.split(" ", 1)[-1]
    if end < len(clean):
        out = out.rsplit(" ", 1)[0] + "..."
    return out


def search(query, only=None, context=3, maxhits=8):
    raw = [t.lower() for t in re.findall(r"[a-z']+", query.lower())]
    content = [t for t in raw if t not in STOPWORDS and len(t) > 2]
    # "distinctive" terms (>=5 chars) are strong signal on their own
    strong = [t for t in content if len(t) >= 5]
    phrase = query.strip().lower()
    results = []
    for slug, d in adviser_dirs(only):
        # Field-manual-only advisers are never quoted, by name or in a blend.
        if slug in FIELD_MANUAL_ONLY:
            continue
        for path, raw in corpus_units(d):
            parsed = parse_raw(path, raw)
            if not parsed:
                continue
            kind, url, vid, title, segments = parsed
            seen_spans = set()
            for start_sec, text in windows(segments, context):
                low = text.lower()
                present = [t for t in content if t in low]
                n_present = len(present)
                # a "meaningful" match = a present content term that isn't generic
                meaningful = [t for t in present if t not in GENERIC]
                n_meaning = len(meaningful)
                # graded relevance (STRONG only when a meaningful term or the phrase hits):
                #   100  exact phrase
                #    50  all content terms present AND >=1 meaningful term
                #    10  partial / generic-only match (weak)
                if phrase in low and len(content) > 1:
                    score = 100 + n_present
                elif content and n_present == len(content) and n_meaning >= 1:
                    score = 50 + n_present
                elif content and (n_meaning >= 1 or n_present * 2 >= len(content)):
                    score = 10 + n_present * 2 + n_meaning
                else:
                    continue
                # quality gates: drop filler-heavy windows, and for weak matches
                # require the centred snippet to actually carry a meaningful term
                if is_filler_heavy(text):
                    continue
                # book corpora: never surface scan damage or front matter
                if kind == "text" and (is_scan_damaged(text) or is_front_matter(text)):
                    continue
                # video corpora: never surface show promo or episode framing
                if kind != "text" and is_show_boilerplate(text):
                    continue
                snippet = centre_snippet(text, meaningful or present or content)
                # the snippet is the span the USER sees, so gate it too — a clean
                # window can still centre on a damaged phrase inside itself
                if kind == "text" and (is_scan_damaged(snippet) or is_front_matter(snippet)):
                    continue
                if kind != "text" and is_show_boilerplate(snippet):
                    continue
                if score < 50:
                    snip_low = snippet.lower()
                    if meaningful and not any(t in snip_low for t in meaningful):
                        continue
                key = (slug, title, start_sec)
                if key in seen_spans:
                    continue
                seen_spans.add(key)
                if kind == "text":
                    # no timestamp exists: label [BOOK] and link into the reader
                    marker = "[BOOK]"
                    link = book_link(slug, snippet)
                else:
                    marker = mmss(start_sec)
                    link = deep_link(url, start_sec)
                results.append({
                    "adviser": slug, "title": title, "seconds": start_sec,
                    "marker": marker, "link": link,
                    "text": snippet, "score": score, "matched": n_present,
                })
    results.sort(key=lambda r: (-r["score"], r["adviser"]))
    return results[:maxhits]


def main():
    ap = argparse.ArgumentParser(description="Search the Sales Board corpora.")
    ap.add_argument("query", nargs="?", default="", help="words or phrase to find")
    ap.add_argument("--adviser", action="append", help="restrict to slug(s); repeatable")
    ap.add_argument("--context", type=int, default=3, help="segments per window (default 3)")
    ap.add_argument("--max", type=int, default=8, help="max hits (default 8)")
    ap.add_argument("--list", action="store_true", help="list advisers + file counts")
    args = ap.parse_args()

    if args.list:
        for slug, d in adviser_dirs():
            n = sum(1 for _ in corpus_units(d))
            print(f"{slug}\t{n} files")
        return

    if not args.query:
        ap.error("provide a query, or use --list")

    # asked for a field-manual-only adviser: say why, don't just say "not found"
    asked = set(args.adviser or [])
    if asked and asked <= FIELD_MANUAL_ONLY:
        print(FIELD_MANUAL_NOTE)
        return

    hits = search(args.query, only=args.adviser, context=args.context, maxhits=args.max)
    if not hits:
        print("NO SUPPORTING QUOTE FOUND")
        return
    for h in hits:
        link = h["link"] or "(no link — text source)"
        rel = "strong" if h["score"] >= 50 else "weak"
        at = attribution(h["adviser"])
        print(f"{h['adviser']} | {h['title']}  (relevance: {rel})")
        print(f"{h['marker']}  {link}")
        print(f"\"{h['text']}\"")
        print(f"ATTRIBUTE AS: {at['who']}   <- copy this into quote.who, verbatim")
        if at.get("note"):
            print(f"  {at['note']}")
        print(f"  {SPEAKER_CHECK}")
        # 'relevance: strong' is a LEXICAL score: it means the words matched, not
        # that the span supports the point being made. Measured misfires include
        # a Vegas hotel anecdote for "lying" and an anti-scam disclaimer for
        # "WhatsApp". A real link under a claim it does not support is worse than
        # no link at all, because it looks checked.
        print("  CLAIM CHECK: 'strong' means the words matched, not that this "
              "span supports your point. Read it and drop it if it doesn't.")
        print()


if __name__ == "__main__":
    main()
