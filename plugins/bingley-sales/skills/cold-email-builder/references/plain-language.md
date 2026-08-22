# Plain-Language Layer — what the user actually reads

**Purpose:** `scoring-model.md` and `evidence-base.md` are the engine. This file is the interface. Everything the user sees by default is translated through here and framed around the one outcome they care about: **replies.** Internal terms (gate, Block A, band, pin, ceiling, evidence tier) never reach the user unless they ask "show me the scoring / the data".

**Rule: plain by default, data on demand.** Never lead with the machinery.

---

## 1. Band → plain label
The user sees the number out of 100 and a plain label, never the internal band letter.

| Internal band | /100 | Plain label the user sees |
|---|---|---|
| A | 90+ | Ready to send |
| B | 80–89 | Strong, small tweaks |
| C | 70–79 | Decent, a few fixes |
| D | 60–69 | Needs work |
| Gated | 30–59 | Held back by one or two big things |
| F | <30 | Start fresh |

If a cap applies, say it in plain words, not code:
- template / blanks → "Capped until you fill the blanks. Drop in a real result and it jumps."
- reactivation / warm → "Judged as a re-opener, not a cold email, so the bar is different."

## 2. Term translation — never say the left, say the right
| Internal (engine) | Plain (user) |
|---|---|
| Relevance gate fail / sender-led / pitch-slap | "It opens with you, not them. Cold readers decide on line one, and if it's about your company they're gone." |
| Them-led opener | "Opens with something true about them." |
| CTA too high friction / cold calendar link | "The ask is too heavy. Cold readers refuse meetings but say yes to easy." |
| Interest CTA | "An easy ask, just gauging interest." |
| Proof weak / believability flag | "The proof is vague. No name or number, so it reads as probably-not-true." |
| Brevity dimension | "Length. Can they read it in ten seconds on a phone?" |
| Subject line dimension | "The subject. Does it look like a real person sent it, and does the email pay it off?" |
| Feature dump | "It lists what your product does instead of what changes for them." |
| Deliverability / placement | "Whether it lands in the inbox or the promotions tab." |
| Block A / weighted score | "the detailed scoring" |
| Evidence tag / tier | "the study behind it" |

## 3. The 7 things that get replies (the benchmark / North Star)
The spine every email is pushed toward, every run. Both modes use these: in GRADE they become "what's working / what's costing you replies"; in BUILD they become "why this works." The dimension and study in brackets are internal, surfaced only if the user asks.

1. **Lead with them, not you.** First line about their world, not your name or company. *(Relevance & targeting · Collier "enter the conversation"; Hunter 11M: relevance is the #1 reply driver.)*
2. **One concept only.** One problem, one fix, one idea. Two competing ideas and it dies. *(Problem-led / Brevity · Hormozi, $100M Leads: "one concept, just keep it on one thing".)*
3. **Name a real problem they have right now.** A concrete moment, not a generic benefit or a feature. *(Problem-led · Gong 28M: pitching cuts replies up to 57%.)*
4. **One easy ask.** Interest, not a meeting. One ask, not three. *(CTA · Gong 304k: an interest ask wins on a cold first touch.)*
5. **One concrete proof point.** A name or a number beats "we help companies grow." *(Proof · Goldstein 2008: specific, similar social proof.)*
6. **Short.** Ten-second read, well under 200 words. *(Brevity · Gong / 30MPC; Hormozi: under ~200 words, plain reading level.)*
7. **A human subject line.** Looks like a real person sent it, and the email answers it. *(Subject · Sahni 2018: +20% opens, peer-reviewed.)*

**Two locked calls layered on top (house rules):**
- **No price in the email.** Its only job is the call; price sells live. (Default: no, unless the user says otherwise.)
- **Why-me last, never opening.** Credibility is a closing beat, woven in just before the CTA.

## 4. Tone rules for the plain layer
- Frame every "why" as what the **reader** does, not what the rubric does. "They're gone by line two", not "fails Relevance".
- Lead with what's working before what's broken. It softens the teardown and tells them what to keep.
- Keep the number (motivating, shareable). Drop the band letter.
- Offer depth once at the end. Never force it.
- No evidence tags, no "[large-N vendor]", no "pin / ceiling / gate" in the default view, ever.
