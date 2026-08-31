#!/usr/bin/env python3
"""
score_bant.py — deterministic BANT scorer for the company-research skill.

WHY THIS EXISTS
The model's ONLY job is to read a company's public facts and assign each of the four
signals a 0-5 level using the evidence anchors in references/bant-rubric.md. This script
then does the arithmetic the SAME way every time, so the same levels always produce the
same /100, tier, decision and grade. No maths in the model, no run-to-run drift.

DESIGN (grounded in the research brief, references/bant-rubric.md):
  - Fit signals (Budget, Authority, Need) vs intent signal (Timing).
  - Cold-outbound weighting: Need + Timing carry more than Budget + Authority,
    because pre-contact you can observe the problem and the trigger, but budget and
    authority are only proxies.
  - AND-gates + negative scoring so a big company can't buy a GO on size alone.

USAGE
  python3 score_bant.py --levels '{"budget":3,"authority":3,"need":4,"timing":3}' \
      [--disqualifier false]
  # or
  python3 score_bant.py --file /tmp/levels.json
Prints a JSON object: { "bant": {...}, "scoring": {...} } ready to drop into the DATA.
"""
import argparse, json, math, sys

# Cold-outbound weights (sum = 100). Need/Timing heavier by design; Budget capped lowest.
WEIGHTS = {"need": 30, "timing": 30, "authority": 22, "budget": 18}

TIER_LABEL = {"strong": "Strong", "fair": "Fair", "weak": "Longshot"}  # one vocabulary: the
# ranked row, the card fit box and the PDF all say Strong / Fair / Longshot. "Weak" appeared only
# on the card and read as a second, disagreeing verdict for the same company.


def clamp(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(f):   # NaN / +inf / -inf clamp to 0 instead of crashing
        return 0
    return max(0, min(5, int(round(f))))


def score(levels, disqualifier=False):
    if not isinstance(levels, dict):   # malformed input (list / scalar) → all zeros, never crash
        levels = {}
    b = clamp(levels.get("budget"))
    a = clamp(levels.get("authority"))
    n = clamp(levels.get("need"))
    t = clamp(levels.get("timing"))

    total = round(
        n / 5 * WEIGHTS["need"]
        + t / 5 * WEIGHTS["timing"]
        + a / 5 * WEIGHTS["authority"]
        + b / 5 * WEIGHTS["budget"]
    )

    # --- decision: gates first, then the positive gate, else maybe ---
    # Auto-gate the three signals the rubric calls "Disqualifying" at level 0:
    # Need (<=1), Authority (==0), and Budget (==0). Budget=0 means "clearly can't
    # fund your offer / outside your serviceable segment" — a hard knock-out, so it
    # can never buy a GO/maybe on Need+Timing alone (mirrors authority==0 / need<=1).
    disq = bool(disqualifier) or total < 45 or n <= 1 or a == 0 or b == 0
    if disq:
        decision = "NO-GO"
    elif total >= 65 and n >= 3 and a >= 2 and t >= 2:
        decision = "GO"
    else:
        decision = "maybe"

    # tier + grade TRACK THE DECISION, not raw score bands, so the ranked-list verdict,
    # the drill-in card's tier pill and the grade letter can never disagree (a "maybe"
    # is Fair everywhere, never Fair-in-the-list-but-Weak-on-the-card). The /100 `score`
    # stays as the granular detail. Uniform across both skills (shared scorer).
    if decision == "GO":
        tier, grade = "strong", "A"
    elif decision == "maybe":
        tier, grade = "fair", "C"
    else:  # NO-GO (disqualified, or gated out) — always the honest bottom label
        tier, grade = "weak", "D"

    reach = a >= 2                 # is a decision-maker plausibly reachable
    buyer_found = a >= 3           # a clear relevant decision-maker identified

    bant = {"budget": b, "authority": a, "need": n, "timing": t, "tier": TIER_LABEL[tier]}
    scoring = {
        "score": total,
        "decision": decision,
        "grade": grade,
        "tier": TIER_LABEL[tier],
        "reach": reach,
        "buyer_found": buyer_found,
    }
    return {"bant": bant, "scoring": scoring}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--levels", help="inline JSON of the 4 levels")
    p.add_argument("--file", help="path to JSON file with levels (+ optional disqualifier)")
    p.add_argument("--disqualifier", default="false")
    args = p.parse_args()

    data = {}
    try:
        if args.file:
            with open(args.file) as f:
                data = json.load(f)
        elif args.levels:
            data = json.loads(args.levels)
        else:
            print("provide --levels or --file", file=sys.stderr)
            sys.exit(1)
    except (json.JSONDecodeError, OSError) as e:
        print(f"bad --levels/--file: {e}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, dict):   # e.g. --levels '[1,2,3,4]' or '5'
        data = {"levels": data}

    disq = data.get("disqualifier")
    if disq is None:
        disq = str(args.disqualifier).lower() in ("1", "true", "yes")
    levels = data.get("levels", data)
    print(json.dumps(score(levels, disq), ensure_ascii=False))


if __name__ == "__main__":
    main()
