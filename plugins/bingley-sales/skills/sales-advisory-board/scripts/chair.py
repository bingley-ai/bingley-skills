#!/usr/bin/env python3
"""
the Sales Advisory Board — deterministic chair / vote engine.

Decides WHICH adviser chairs a given question, who the runner-up is, and how the
bench votes. There is no model in this path: same question in, byte-identical
output out, every time. That is the whole point — the boardroom's seating order
has to be defensible and reproducible, not a fresh opinion each run.

Usage:
  python3 chair.py "<question text>"
  python3 chair.py "<question text>" --json

THE ALGORITHM (fixed; change it here or nowhere)
-----------------------------------------------
1. TOKENISE the question: lowercase, strip punctuation, drop a fixed stopword
   list. Terms = the surviving single words PLUS every consecutive 2-word pair
   of those surviving words ("champion gone dark" -> "champion gone", "gone dark").

2. RETRIEVAL score, per bench adviser. Every corpus file is read once (via
   search.parse_file, so chair.py and search.py agree on what a corpus is) and
   each term is counted with word-boundary matching.
     - flood cap: a term counts at most FLOOD_CAP (6) times inside any ONE file,
       so a single ranty transcript cannot elect an adviser on its own;
     - weights: 2-word phrase hit = 3, single word hit = 1.
   Those raw counts are then made COMPARABLE, because the corpora are wildly
   uneven (Hormozi 612k words, Rackham 26k) and raw counts otherwise just elect
   whoever has the most tape. Three fixed corrections, applied per term:
     - density: counts are divided by the adviser's own corpus size, so the
       question is "how concentrated is this adviser on the term", not "how big
       is his corpus";
     - lift: an adviser scores only the density share he holds ABOVE an even
       1/8 split. Words every adviser uses at the same rate ("days", "went")
       therefore contribute nothing to anyone, which is correct — they carry no
       information about who should chair;
     - support: a term seen fewer than MIN_SUPPORT times across the whole bench
       is damped pro rata, so a freak one-off phrase ("nine days") cannot hand
       someone the chair.
   The result is divided by RETRIEVAL_SCALE so retrieval sits in roughly the
   0-30 band: it is the nuance layer, the standing brief below is the driver.

3. DOMAIN layer. DOMAIN_MAP is a fixed keyword -> (adviser, weight) table: the
   board's standing brief, i.e. who owns which problem regardless of who happens
   to say a word most often. Matching is substring-on-token ("negotiat" fires on
   "negotiating"); hyphenated keys match across a word gap ("cold-call" fires on
   "cold call"). Each keyword scores once, however many tokens it hits. This is
   the primary signal: a question about a prospect going silent belongs to Voss
   whether or not his transcripts happen to over-use the word "quiet".

4. CHAIR = highest combined (retrieval + domain) score. Ties break by BENCH
   order, left to right. RUNNER-UP = second on the same rule.

5. BALLOT, derived rather than invented. Every adviser votes for the chair
   UNLESS their own combined score is >= DISSENT_RATIO (60%) of the chair's AND
   >= DISSENT_FLOOR (8) absolute — a genuinely strong claim on the question —
   in which case they self-vote and are flagged as dissent. The chair never
   self-votes: the chair votes for the runner-up.

Exit code is always 0 unless the question is empty.
"""
import argparse
import json
import os
import re
import sys

# chair.py sits next to search.py and reuses its corpus parsing, so there is
# exactly one definition of "what a corpus file is" in this skill.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search  # noqa: E402

# --- the bench, left to right. This order is also the tie-break order. --------
BENCH = [
    "jeb-blount",
    "dale-carnegie",
    "keenan-gap-selling",
    "neil-rackham",
    "david-sandler",
    "alex-hormozi",
    "chris-voss",
    "jordan-belfort",
]

FLOOD_CAP = 6            # max times one term may count inside one file
W_PHRASE = 3             # weight of a 2-word phrase hit
W_WORD = 1               # weight of a single-word hit
MIN_SUPPORT = 15         # bench-wide hits below which a term is damped pro rata
RETRIEVAL_SCALE = 4      # divisor keeping retrieval a nuance layer, not the driver
RETRIEVAL_CEILING = 30   # after scaling, the TOP retrieval score is normalised down
                         # to this if it exceeds it (proportions preserved). Long
                         # questions produce hundreds of terms and otherwise let the
                         # biggest corpora out-shout the standing brief.
FUZZY_MIN_KEY = 6        # domain keys this long or longer also match at edit
                         # distance 1, so dictation typos (discont, diskount,
                         # gosted) still reach the standing brief. Deterministic.
DOMAIN_WEIGHT = 20       # default weight of a DOMAIN_MAP keyword hit
WEAK_DOMAIN_WEIGHT = 7   # weight for AMBIGUOUS keywords (see SHARED entries)

# Seats that may speak and vote but never chair, because they have no quotable
# corpus (search.FIELD_MANUAL_ONLY). Kept as a literal rather than an import so
# chair.py stays runnable on its own; the two lists must agree.
CHAIR_INELIGIBLE = {"dale-carnegie"}
DISSENT_RATIO = 0.60     # self-vote threshold, relative to the chair
DISSENT_FLOOR = 8        # self-vote threshold, absolute

# --- fixed stopword list (~120 words). Frozen deliberately: editing it changes
# every historic result, so treat it as part of the algorithm, not a setting. ---
STOPWORDS = set("""
a about after again all also am an and another any are as at back be because been
before being below between both but by came can cant could did didnt do does doesnt
doing dont down during each even ever every few for from further get gets go goes
going got had has have having he her here hers him his how however i if im in into
is isnt it its ive just keep let like ll made make many may me might mine more most
much must my never no nor not now of off on once one only or other others ought our
ours out over own re really said same say says she should since so some still such
than that the their theirs them then there these they this those though through to
too under until up us used using very want was way we well were what when where
which while who whom why will with within without wont would yet you your yours
""".split())

# --- the standing brief: who owns which problem. -----------------------------
# Keys are matched as SUBSTRINGS against question tokens, so use stems
# ("negotiat" catches negotiate / negotiating / negotiation). Hyphenated keys
# match across a word gap. Every entry carries DOMAIN_WEIGHT unless a specific
# weight is given, so the table can be re-tuned from one constant.
_D = DOMAIN_WEIGHT
_W = WEAK_DOMAIN_WEIGHT
DOMAIN_MAP = {
    # Hormozi — money, offers, what the thing costs and why it is worth it
    "discount": ("alex-hormozi", _D),
    "pricing": ("alex-hormozi", _D),
    "price": ("alex-hormozi", _D),
    "offer": ("alex-hormozi", _D),
    "guarantee": ("alex-hormozi", _D),
    "margin": ("alex-hormozi", _D),

    # Voss — silence, leverage, the negotiation itself. "walk" sits here because
    # walking away IS the leverage question, not a pipeline question.
    "ghost": ("chris-voss", _D),
    "ghosted": ("chris-voss", _D),
    "silence": ("chris-voss", _D),
    "quiet": ("chris-voss", _D),
    "dark": ("chris-voss", _D),
    "negotiat": ("chris-voss", _D),
    "counter": ("chris-voss", _D),
    "follow-up": ("chris-voss", _D),
    "unrespons": ("chris-voss", _D),
    "no-reply": ("chris-voss", _D),
    "walk": ("chris-voss", _D),

    # Blount — the number, the funnel, the activity that feeds it
    "pipeline": ("jeb-blount", _D),
    "prospect": ("jeb-blount", _D),
    "stalled": ("jeb-blount", _D),
    "quota": ("jeb-blount", _D),
    "forecast": ("jeb-blount", _D),
    "cold-call": ("jeb-blount", _D),
    "cadence": ("jeb-blount", _D),

    # Keenan — the problem underneath, and whether it was ever found
    "discovery": ("keenan-gap-selling", _D),
    "gap": ("keenan-gap-selling", _D),
    "problem": ("keenan-gap-selling", _D),
    "stuck": ("keenan-gap-selling", _D),
    "root-cause": ("keenan-gap-selling", _D),

    # Sandler — qualification and the contract for the meeting
    "qualify": ("david-sandler", _D),
    "qualif": ("david-sandler", _D),
    "upfront": ("david-sandler", _D),
    "up-front": ("david-sandler", _D),
    "proposal": ("david-sandler", _D),
    "budget": ("david-sandler", _D),
    "no-decision": ("david-sandler", _D),
    # Authority and the buying decision. Added 21 Aug 2026: the table had no
    # word at all for the single most common qualification question there is —
    # "can this person actually say yes" — so those cases were decided by
    # whatever incidental word happened to carry a domain hit.
    "authorit": ("david-sandler", _D),
    "decision-maker": ("david-sandler", _D),
    "decision-making": ("david-sandler", _D),
    "decid": ("david-sandler", _D),
    "sign-off": ("david-sandler", _D),
    "signoff": ("david-sandler", _D),
    "approv": ("david-sandler", _D),
    "who-signs": ("david-sandler", _D),
    "sign": ("david-sandler", _W),
    "signature": ("david-sandler", _W),

    # Rackham — big, multi-stakeholder, enterprise sales
    "spin": ("neil-rackham", _D),
    "implication": ("neil-rackham", _D),
    "large-sale": ("neil-rackham", _D),
    "enterprise": ("neil-rackham", _D),
    "committee": ("neil-rackham", _D),
    "stakeholder": ("neil-rackham", _D),

    # Belfort — the state of the seller in the room
    "conviction": ("jordan-belfort", _D),
    "certainty": ("jordan-belfort", _D),
    "tonality": ("jordan-belfort", _D),
    "tone": ("jordan-belfort", _D),
    "nerve": ("jordan-belfort", _D),
    "objection": ("jordan-belfort", _D),
    "script": ("jordan-belfort", _D),

    # Carnegie — the human relationship carrying the deal
    "rapport": ("dale-carnegie", _D),
    "relationship": ("dale-carnegie", _D),
    "likeable": ("dale-carnegie", _D),
    "likable": ("dale-carnegie", _D),

    # --- AMBIGUOUS terms: shared, at WEAK weight. --------------------------
    # A word that several seats can legitimately claim must never hand one of
    # them a 20-point win on its own. "champion" used to sit on Carnegie at full
    # weight, which meant any question containing the word elected him — even a
    # pure authority question, where he is the wrong chair and (being
    # field-manual-only) the one adviser who cannot produce a receipt.
    "champion": [("david-sandler", _W), ("neil-rackham", _W)],
    "trust": [("dale-carnegie", _W), ("chris-voss", _W)],
    "sponsor": [("neil-rackham", _W), ("david-sandler", _W)],
    "single-thread": [("jeb-blount", _W), ("neil-rackham", _W)],
}

WORD = re.compile(r"[a-z']+")


# --------------------------------------------------------------------------- #
# 1. tokenise
# --------------------------------------------------------------------------- #
def tokenise(question):
    """Return (all_tokens, terms). all_tokens keeps stopwords (the domain layer
    reads the raw question); terms are the content words plus their consecutive
    2-word pairs, which is what the retrieval layer counts."""
    lowered = question.lower().replace("-", " ").replace("/", " ")
    all_tokens = [t.strip("'") for t in WORD.findall(lowered)]
    all_tokens = [t for t in all_tokens if t]
    content = [t for t in all_tokens if t not in STOPWORDS and len(t) > 2]
    pairs = [f"{content[i]} {content[i + 1]}" for i in range(len(content) - 1)]
    # de-duplicate but hold insertion order, so the term list is stable
    terms = []
    for t in content + pairs:
        if t not in terms:
            terms.append(t)
    return all_tokens, terms


# --------------------------------------------------------------------------- #
# 2. retrieval
# --------------------------------------------------------------------------- #
def corpus_texts(slug):
    """All corpus text for one adviser, one lowercased blob per file."""
    d = os.path.join(search.BASE, slug)
    out = []
    if not os.path.isdir(d):
        return out
    for path, raw in search.corpus_units(d):
        parsed = search.parse_raw(path, raw)
        if not parsed:
            continue
        _kind, _url, _vid, _title, segments = parsed
        out.append(" ".join(s[1] for s in segments).lower())
    return out


def load_bench():
    """{slug: (blobs, word_count)} — the bench corpora, read once per run."""
    bench = {}
    for slug in BENCH:
        blobs = corpus_texts(slug)
        bench[slug] = (blobs, sum(len(b.split()) for b in blobs) or 1)
    return bench


def retrieval_scores(terms, bench):
    """{slug: score} — density-normalised, lift-only, support-damped term hits.

    Iteration order is fixed (terms list, then BENCH list), so the float
    arithmetic runs in the same order every time and the rounded result is
    reproducible to the byte."""
    scores = {slug: 0.0 for slug in BENCH}
    n_bench = len(BENCH)
    for term in terms:
        pat = re.compile(r"\b" + re.escape(term) + r"\b")
        weight = W_PHRASE if " " in term else W_WORD
        counts = {}
        for slug in BENCH:
            blobs, _wc = bench[slug]
            # flood cap applies per FILE: no single transcript can flood a term
            counts[slug] = sum(min(len(pat.findall(b)), FLOOD_CAP) for b in blobs)
        total_hits = sum(counts.values())
        if total_hits == 0:
            continue
        # rare terms are damped: they are anecdote, not evidence of ownership
        support = min(1.0, total_hits / float(MIN_SUPPORT))
        densities = {s: counts[s] / (bench[s][1] / 100000.0) for s in BENCH}
        total_density = sum(densities.values())
        if total_density <= 0:
            continue
        for slug in BENCH:
            # credit only the share held ABOVE an even split; a word everyone
            # uses equally tells us nothing about who should chair
            lift = densities[slug] / total_density - 1.0 / n_bench
            if lift > 0:
                scores[slug] += weight * 100.0 * lift * support
    out = {s: scores[s] / RETRIEVAL_SCALE for s in BENCH}
    # normalise: retrieval is the nuance layer by design. On long questions the
    # raw scores can reach the hundreds, silencing the domain brief entirely —
    # scale everything down so the leader sits at RETRIEVAL_CEILING, with all
    # proportions (and therefore all orderings) preserved.
    top = max(out.values()) if out else 0.0
    if top > RETRIEVAL_CEILING:
        f = RETRIEVAL_CEILING / top
        out = {s: v * f for s, v in out.items()}
    return {s: int(round(v)) for s, v in out.items()}


# --------------------------------------------------------------------------- #
# 3. domain layer
# --------------------------------------------------------------------------- #
def _ed1(a, b):
    """True if edit distance between a and b is exactly 0 or 1. Deterministic,
    no imports: one substitution, one insertion or one deletion."""
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    if la > lb:
        a, b, la, lb = b, a, lb, la
    # a is shorter by one: try skipping one char of b
    i = 0
    while i < la and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def _fuzzy_token_hit(key, tokens):
    """Typo-tolerant single-word match: exact substring first, then edit
    distance 1 for keys >= FUZZY_MIN_KEY chars ("discont" reaches "discount",
    "gosted" reaches "ghosted"). Short keys stay exact-only — at 5 letters,
    distance-1 neighbours are real words ("price"/"pride")."""
    for t in tokens:
        if key in t:
            return True
    if len(key) < FUZZY_MIN_KEY:
        return False
    for t in tokens:
        if len(t) < len(key) - 1:
            continue
        if _ed1(key, t) or _ed1(key, t[:len(key)]) or _ed1(key, t[:len(key) + 1]):
            return True
    return False


def domain_scores(all_tokens):
    """{slug: score} plus the keywords that fired, for the audit trail."""
    haystack = " ".join(all_tokens)
    scores = {slug: 0 for slug in BENCH}
    fired = {slug: [] for slug in BENCH}
    for keyword, owners in DOMAIN_MAP.items():
        # an entry is either one (slug, weight) or a list of them (ambiguous term)
        if isinstance(owners, tuple):
            owners = [owners]
        key = keyword.replace("-", " ")
        hit = (key in haystack) if " " in key else _fuzzy_token_hit(key, all_tokens)
        if not hit:
            continue
        for slug, weight in owners:
            if slug not in scores:
                continue
            scores[slug] += weight
            fired[slug].append(keyword)
    for slug in fired:
        fired[slug].sort()                          # stable regardless of dict order
    return scores, fired


# --------------------------------------------------------------------------- #
# 4 + 5. chair, runner-up, ballot
# --------------------------------------------------------------------------- #
def rank(combined):
    """Bench slugs, best first. Ties break by bench order (left to right)."""
    return sorted(BENCH, key=lambda s: (-combined[s], BENCH.index(s)))


def ballot(combined, chair, runnerup):
    """Derived ballot: dissent is earned by score, never assigned by hand."""
    threshold = max(DISSENT_FLOOR, combined[chair] * DISSENT_RATIO)
    votes = []
    for slug in BENCH:
        if slug == chair:
            votes.append({"voter": slug, "vote": runnerup, "dissent": False,
                          "reason": "chair never self-votes"})
        elif combined[slug] >= threshold and combined[slug] >= DISSENT_FLOOR:
            votes.append({"voter": slug, "vote": slug, "dissent": True,
                          "reason": "own claim >= 60% of chair and >= 8"})
        else:
            votes.append({"voter": slug, "vote": chair, "dissent": False,
                          "reason": "backs the chair"})
    return votes


def tally(votes, chair):
    for_chair = sum(1 for v in votes if v["vote"] == chair)
    return for_chair, len(votes) - for_chair


def run(question):
    all_tokens, terms = tokenise(question)
    retr = retrieval_scores(terms, load_bench())
    dom, fired = domain_scores(all_tokens)
    combined = {s: retr[s] + dom[s] for s in BENCH}
    order = rank(combined)
    # The chair is the ONLY seat that speaks with retrieved quotes (SKILL.md
    # step 4), so a seat that can never produce a receipt can never chair. It
    # still speaks in round one and still votes — it just never leads.
    # This also removes a real bias: a tiny corpus scores high retrieval density
    # per 100k words, so the smallest corpus on the bench was winning questions
    # where no domain keyword fired at all.
    eligible = [s for s in order if s not in CHAIR_INELIGIBLE] or order
    chair = eligible[0]
    runnerup = next((s for s in order if s != chair), order[-1])
    votes = ballot(combined, chair, runnerup)
    for_chair, against = tally(votes, chair)
    return {
        "question": question,
        "terms": terms,
        "chair": chair,
        "runnerup": runnerup,
        # a question that scored nothing anywhere seats the chair on bench order
        # alone. Say so rather than pass it off as a verdict.
        "no_signal": combined[chair] == 0,
        "tally": f"{for_chair}-{against}",
        "scores": [
            {"adviser": s, "retrieval": retr[s], "domain": dom[s],
             "combined": combined[s], "domain_hits": fired[s]}
            for s in order
        ],
        "ballot": votes,
    }


def render(res):
    lines = []
    lines.append(f"QUESTION  {res['question']}")
    lines.append("")
    lines.append(f"{'ADVISER':<20}{'RETRIEVAL':>10}{'DOMAIN':>8}{'COMBINED':>10}   DOMAIN HITS")
    lines.append("-" * 78)
    for row in res["scores"]:
        hits = ", ".join(row["domain_hits"]) if row["domain_hits"] else "-"
        lines.append(f"{row['adviser']:<20}{row['retrieval']:>10}{row['domain']:>8}"
                     f"{row['combined']:>10}   {hits}")
    lines.append("")
    lines.append(f"CHAIR      {res['chair']}")
    lines.append(f"RUNNER-UP  {res['runnerup']}")
    if res["no_signal"]:
        lines.append("NOTE       no term or domain signal — chair is bench order, not a verdict")
    lines.append("")
    lines.append("BALLOT")
    for v in res["ballot"]:
        flag = "  <- dissent" if v["dissent"] else ""
        lines.append(f"  {v['voter']:<20} -> {v['vote']:<20}{flag}")
    lines.append("")
    lines.append(f"TALLY      {res['tally']}  (for chair - against)")
    return "\n".join(l.rstrip() for l in lines)


def main():
    ap = argparse.ArgumentParser(description="Deterministic chair/vote engine for the Sales Advisory Board.")
    ap.add_argument("question", nargs="?", default="", help="the question put to the board")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--allow-no-signal", action="store_true",
                    help="return a chair even when the question scored nothing "
                         "(diagnostics only — never in a sitting)")
    args = ap.parse_args()

    if not args.question.strip():
        ap.error("provide a question")

    res = run(args.question)

    # SIGNAL BANDS, measured 21 Aug 2026 across 19 inputs.
    #   real decisions:  18-64   ("do I drop my price?" 26, ghosted champion 64)
    #   real but terse:   5-13   ("chase or wait?" 5, "fire this client?" 7)
    #   not a decision:   1-11   ("yes" 1, a bare URL 10, a poem request 10,
    #                             "how do I get better at closing" 4)
    # The two middle bands OVERLAP, so a hard cut-off would refuse real cases —
    # which is why this reports rather than refuses. Only a zero is fatal.
    res["signal"] = ("none" if res["no_signal"]
                     else "thin" if res["scores"][0]["combined"] < 15
                     else "strong")
    if res["signal"] == "thin":
        sys.stderr.write(
            "THIN SIGNAL: barely anything in that scored, so the chair below is "
            "weakly evidenced — lead with it, but don't present it as a decisive "
            "election. If what you sent is a TOPIC rather than a decision, that "
            "is why: ask for the decision instead of convening.\n")

    # A rule saying "check no_signal" is a rule that gets skipped at 2am. An
    # emoji, a full stop or keyboard mash scores zero and still elects a
    # confident 7-1 bench with Carnegie — who cannot chair — as runner-up. So
    # the engine refuses instead of hoping the caller reads the flag.
    if res["no_signal"] and not args.allow_no_signal:
        sys.stderr.write(
            "NO SIGNAL: nothing in that scored against any adviser, so the chair "
            "below would be noise, not an election. Do NOT convene. Ask for the "
            "decision in one line and try again.\n")
        sys.exit(3)
    if args.json:
        print(json.dumps(res, indent=2, sort_keys=True))
    else:
        print(render(res))


if __name__ == "__main__":
    main()
