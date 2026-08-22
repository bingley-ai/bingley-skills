#!/usr/bin/env python3
"""Draw N example cases from assets/case-bank.md, seeded by date (rotates daily,
stable within a day). Usage: python3 scripts/draw_cases.py [--n 5] [--date YYYY-MM-DD]"""
import argparse, datetime, random, re, os, json

BANK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "case-bank.md")

def load_cases(path=BANK):
    txt = open(path, encoding="utf-8").read()
    cases = re.findall(r"^\d+\.\s+\[[^\]]*\]\s+(.+)$", txt, re.M)
    if len(cases) < 20:
        raise SystemExit("case bank parse failed: only %d cases" % len(cases))
    return cases

def draw(n=5, date=None, path=BANK):
    date = date or datetime.date.today().isoformat()
    cases = load_cases(path)
    rng = random.Random(date)          # deterministic per day
    return rng.sample(cases, n)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--date", default=None)
    a = ap.parse_args()
    print(json.dumps(draw(a.n, a.date), indent=1))
