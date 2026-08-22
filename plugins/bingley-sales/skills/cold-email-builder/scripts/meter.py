#!/usr/bin/env python3
"""Cold-email meter — deterministic pre-pass for the cold-email-builder skill.
Counts the objective signals, returns metrics + flags + the dimension floors/docks
they imply. The grader runs this FIRST, then applies judgement only to what's left
(relevance quality, proof believability, problem concreteness). Same email -> same numbers.

Thresholds are evidence-anchored (see scoring-model.md §9). The self-reference ratio
and self-block are heuristics, not sourced numbers: they flag/dock softly, never hard-fail.

Usage: python3 meter.py emails.json   # [{"id","subject","body"}, ...]
       or import meter(subject, body) -> dict
"""
import re, json, sys
W=r"[A-Za-z0-9']+"; YOU=r"\b(you|your|yours)\b"; IWE=r"\b(i|we|my|me|our|us)\b"
BIO=re.compile(r"(about me|my name is|i'?m the|co-?founder|years in|director|i lead|i run|i head)", re.I)

def _syl(word):
    word=word.lower(); 
    if not word: return 1
    v="aeiouy"; n=0; prev=False
    for c in word:
        is_v=c in v
        if is_v and not prev: n+=1
        prev=is_v
    if word.endswith("e") and n>1: n-=1
    return max(n,1)

def meter(subject, body):
    body=(body or "").strip()
    words=re.findall(W, body); wc=len(words) or 1
    sents=[s for s in re.split(r'(?<=[.!?])\s+', body) if s.strip()] or [body]
    sc=len(sents); wps=wc/sc
    longest=max((len(re.findall(W,s)) for s in sents), default=0)
    syl=sum(_syl(w) for w in words); fk=round(0.39*wps + 11.8*(syl/wc) - 15.59, 1)
    q=body.count('?'); links=len(set(re.findall(r'https?://\S+|www\.[^\s<]+|<a\s', body)))
    you=len(re.findall(YOU, body, re.I)); iwe=len(re.findall(IWE, body, re.I))
    ratio=iwe/you if you else (iwe if iwe else 0)
    subj_wc=0 if not subject else len(subject.split())
    paras=[p.strip() for p in re.split(r'\n\s*\n|\n', body) if p.strip()]
    # self-block: biggest net-self paragraph, OR a trailing bio block
    block_pct=0; block_kind=""
    for p in paras:
        pw=len(re.findall(W,p))
        if pw<12: continue
        pi=len(re.findall(IWE,p,re.I)); py=len(re.findall(YOU,p,re.I))
        share=100*pw/wc
        is_bio = BIO.search(p) is not None
        if pi>py and share>=15 and (share>=45 or is_bio) and share>block_pct:
            block_pct=round(share); block_kind="bio/credentials block" if is_bio else "self-block"
    signoff=bool(re.search(r'(thanks|cheers|regards|best|sincerely|talk soon|warmly)\b', body, re.I)) or (len(re.findall(W,paras[-1]))<=4 if paras else False)
    flags=[]; docks={}
    def dock(dim,n,why): docks[dim]=docks.get(dim,0)-n; flags.append(f"{dim} -{n}: {why}")
    # T1 hard-ish floors
    if wc>225: dock("Brevity",3,f"{wc} words")
    elif wc>175: dock("Brevity",2,f"{wc} words")
    elif wc>125: dock("Brevity",1,f"{wc} words (trim toward <125)")
    if ratio>=1.8: dock("Relevance",1,f"self-focused, I/we {iwe} vs you/your {you} ({ratio:.1f}:1)")
    elif iwe>you: flags.append(f"flag: leans self ({iwe} I/we vs {you} you) — nudge toward them")
    if block_pct: flags.append(f"FLAG {block_kind} ~{block_pct}% of email — trim")
    if links>=1: dock("Deliverability",1,f"{links} link(s) in first email")
    # T2 soft flags (subject + questions never hard-dock)
    if subj_wc==0: flags.append("subject: none pasted — neutral, suggest one")
    elif subj_wc>=10: flags.append(f"flag: subject {subj_wc} words — long, trim to ~1-6")
    elif subj_wc>=7: flags.append(f"flag: subject {subj_wc} words — slightly long")
    if q==0: flags.append("flag: no question — a soft 1-question ask tends to lift replies")
    elif q>=4: flags.append(f"flag: {q} questions — Boomerang sweet spot is 1-3")
    # T3 lenient readability (one-sided: only ever costs points when dense/long)
    if fk>13: dock("Brevity",1,f"reading grade {fk} (dense)")
    elif fk>=11: flags.append(f"flag: reading grade {fk} — a touch dense")
    if wps>=20: dock("Brevity",1,f"avg {wps:.0f} words/sentence")
    if longest>35: flags.append(f"flag: longest sentence {longest} words — split it")
    if not signoff: flags.append("no sign-off — sure you want to send without one?")
    return dict(subj_words=subj_wc, words=wc, sentences=sc, wps=round(wps,1), longest=longest,
        questions=q, links=links, you=you, iwe=iwe, self_ratio=round(ratio,1),
        self_block_pct=block_pct, fk_grade=fk, signoff=signoff, flags=flags, docks=docks)

if __name__=="__main__":
    for e in json.load(open(sys.argv[1])):
        r=meter(e.get('subject'), e['body'])
        print("="*68); print(f"{e['id']} | words {r['words']} | I/we:you {r['iwe']}:{r['you']} ({r['self_ratio']}:1) | grade {r['fk_grade']} | subjW {r['subj_words']} | Q {r['questions']}")
        print(f"  DOCKS: {r['docks'] or 'none'}")
        for f in r['flags']: print(f"    - {f}")
