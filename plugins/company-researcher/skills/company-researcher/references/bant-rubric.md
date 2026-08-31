# BANT scoring rubric (evidence-anchored, cold-outbound)

**Purpose.** Turn the fuzzy "score 0-5" instruction into a defensible, repeatable score.
The model reads the company's public facts and assigns each of the four signals a **0-5
level using the anchors below**; `scripts/score_bant.py` then computes the /100, tier,
decision and grade deterministically (same levels → same output, every run).

**The honest frame.** Web-only research cannot *measure* BANT — real budget, authority,
pain-priority and timeline are confirmed in conversation. This rubric scores **public
proxies** for each, and is deliberately more confident about Need and Timing (observable
pre-contact) than Budget and Authority (inferences). Scores are a *prioritisation* of who
to approach, not a verdict on the deal.

**Scored against the seller's ICP**, never the company alone. Read `business.product /
audience / problem` from the brain and judge fit *to that*. "Budget 4" means the company
can fund *your* offer, not that they're rich in the abstract.

---

## How to score (procedure)

1. Research the company (the normal skill flow) so you have: size (revenue / employees),
   growth, funding, `triggers`, `last30days.signals`, `tech_stack`, industry/model,
   competitors.
2. For each dimension pick the **single 0-5 level** whose descriptor the evidence best
   meets. Level 5 is reserved for **explicit, dated, named** evidence and should be rare.
   If you can't find evidence, you are at level 1-2, not 3+. Do not round up out of
   politeness.
3. Set a **`disqualifier` flag** to true if any hard knock-out applies (below).
4. Run the scorer:
   ```bash
   python3 scripts/score_bant.py --levels '{"budget":B,"authority":A,"need":N,"timing":T}' --disqualifier <true|false>
   ```
   It prints `{ "bant": {...}, "scoring": {...} }`. Drop both straight into the company's
   DATA. **Never hand-set the /100, tier, decision or grade** — the script owns those.

---

## The anchors

### BUDGET — can they fund your offer? (fit proxy: size / funding vs your price band)
- **0** — Disqualifying: clearly can't fund your offer (e.g. pre-revenue micro-business vs an enterprise-priced service), or outside your serviceable segment.
- **1** — Size / revenue well below your ICP's paying range.
- **2** — Below range but not impossible; thin or unknown financials.
- **3** — Revenue / headcount sits in your ICP band — generic capacity to pay.
- **4** — Comfortably in band **and** healthy growth or recent funding = clear spend capacity.
- **5** — In band **and** a dated funding raise or budget expansion earmarked for the area you serve.

**Budget is a FIT proxy, not a wealth score. Too-big counts against, not for.** A company *above*
your ICP band (e.g. a multinational / large PLC when you sell to SME–mid-market) is a size-**misfit**:
**cap Budget at 2**, because enterprise procurement, incumbent big-4 vendors and committee buying
make them a poor fit for your offer even though they can obviously pay. Only score 3+ when size sits
**in** band. This stops cash-rich whales floating to the top of a ranked list on capacity alone.

**Size is NEVER a disqualifier — precedence rule.** Above-band size is handled by the Budget cap above
and by nothing else. “Segment”, both in the hard-disqualifier list and in Budget level 0, means
**industry, buyer category or geography — never headcount or revenue**. So a 96,000-person
multinational gets Budget 2 with `disqualifier: false`, and still lands NO-GO through the ordinary
gates. Without this rule two readers produce different `disqualifier` values on identical evidence,
which breaks the same-levels-same-output guarantee.

**Not all capital is spendable — read what the money is FOR.** Lending and securitisation facilities,
debt raised to fund a loan book, restricted grants and ring-fenced project finance say nothing about
opex for your offer, so they are **not** a Budget 4-5 trigger. Only equity raises, profit, or a stated
budget for the area you serve count. (A £210m securitisation facility at an invoice-finance lender is
Budget 3 at most, never 5.)

### AUTHORITY — is a decision-maker identifiable and reachable? (fit proxy: titles / org)
- **0** — No reachable buyer for your offer; decisions sit at an unreachable parent with no local mandate.
- **1** — Buyer persona exists but buried in a very large org; economic buyer hard to reach.
- **2** — Relevant senior titles present, but org complexity implies multi-stakeholder sign-off.
- **3** — A clear, relevant decision-maker title is identifiable at the company.
- **4** — Decision-maker identifiable **and** org size implies they can sign without a committee.
- **5** — A specific, named, in-seat decision-maker for your category (e.g. a just-hired exact-fit exec).

### NEED — do they have the problem you solve? (fit: ICP + observable pain)
- **0** — Structurally can't need it, or already run a mature in-house solution to the exact problem.
- **1** — No observable sign of the problem; weak ICP fit.
- **2** — Industry / model plausibly has the problem, but no specific signal.
- **3** — Clear ICP fit — the problem is generically likely for this kind of company.
- **4** — A **specific public signal** of the pain: a relevant job posting, tech-stack gap, complaints/reviews, or an initiative that implies it.
- **5** — **Explicit, dated** evidence they're actively tackling this exact problem (named project, stated priority, hiring a leader to fix precisely it).

**"They already use AI" is not automatically low Need — read WHICH AI.** Distinguish
*customer/product-facing* AI (a shopping assistant, an AI feature in their app) from the *internal
AI-adoption* you sell (mapping roles to workflows, upskilling leaders). Product AI does **not**
reduce Need for an adoption seller. Only a **mature internal** programme — a named org-wide AI
transformation, a Head/Chief of AI already in seat driving it — pulls Need to 0-1. When unsure,
score Need 2 (plausible, unconfirmed), not 3.

### TIMING — why now? (intent: fresh trigger events; recency matters most)
- **0** — A trigger arguing *against* now (recent layoffs / freeze in the relevant area, just bought a rival solution).
- **1** — No trigger; steady state.
- **2** — An older (>120 days) or weak / indirect trigger.
- **3** — A relevant trigger in the last ~90 days (expansion, product launch, moderate change).
- **4** — A **strong** relevant trigger in the last ~30-60 days (funding round, new exec in the buying function, new-market entry).
- **5** — A strong, dated trigger in the last ~30 days **directly tied to your offer** (e.g. just hired a leader mandated to solve your problem; raise earmarked for it).

Timing signals decay fast (hiring data loses ~half its predictive value in 3 months; new-exec
evaluation windows close ~90-120 days). When triggers are stale, score down, don't credit them.

**Ambiguous events — read the direction, not just the change.** An acquisition or merger is
only a positive trigger if it brings budget/expansion. **Acquisition-driven restructuring with
headcount cuts, or a takeover that moves the buyer to an unreachable parent, scores Timing ≤ 1
(often 0), not 3** — the "change" is real but it argues against a purchase now. Same for
layoffs, cost-cutting programmes, or a distressed sale.

**Distress vs routine restructuring — don't confuse them.** A *profitable, growing* firm booking
small redundancy costs is **not** distressed; judge its real trigger (e.g. a fresh exec hire) on its
own merit, don't slam it to ≤ 1. Apply the ≤ 1 floor only on genuine retrenchment: falling profit,
administration, distressed sale, or mass cuts. (Currys FY26: +18% profit, £16m redundancies, incoming
CEO → Timing 3 for the new exec, **not** 1. BAT: 9,000-role cut → Timing ≤ 1.)

---

## Hard disqualifiers (set `disqualifier: true` → forces NO-GO)
- Outside serviceable geography, industry or buyer category (**not** size — see the Budget cap above).
- Is a competitor.
- Company type entirely outside the ICP (wrong buyer category altogether).

## Scoring maths (owned by the script, documented here)
- Weights (cold-outbound): **Need 30, Timing 30, Authority 22, Budget 18** (sum 100). Score = Σ (level/5 × weight).
- **Decision gates** (checked in order):
  - **NO-GO** if disqualifier, or score < 45, or Need ≤ 1, or Authority = 0, or Budget = 0.
    (Need, Authority and Budget each auto-gate at their level-0 "Disqualifying" anchor.)
  - **GO** if score ≥ 65 **and** Need ≥ 3 **and** Authority ≥ 2 **and** Timing ≥ 2.
  - **maybe** otherwise.
- **Tier pill + grade track the DECISION** (not raw score bands), so the ranked verdict, the card tier
  and the grade never disagree: **GO → Strong / A · maybe → Fair / C · NO-GO → Longshot / D**. The `/100`
  score is the granular detail alongside them.
- `reach` = Authority ≥ 2; `buyer_found` = Authority ≥ 3.

The AND-gates are the anti-inflation mechanism: a big company scores high on Budget but
**cannot reach GO without a real Need and a reachable buyer**, so size alone never buys a pass.

## Calibration status (be honest with the user)
The weights and thresholds are a **starting hypothesis from vendor practice**, not yet
backtested against your closed-won data. They were sanity-checked by scoring a spread of
varied companies to confirm the output discriminates (see `_build/bant-calibration.md`, development HQ only).
Log score + tier at first touch so the model can be recalibrated once real outcomes exist.
Target distribution as a health check: only ~15-25% of a mixed list should land GO; if far
more do, the anchors or thresholds are too loose.
