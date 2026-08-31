# Company Research Framework

_Ported from the GitHub "ai-sales-team" `sales-research.md` (the 8-dimension research
engine), kept rich on purpose so the user can see everything and prune. This is NEUTRAL
company understanding — there is **no ICP scoring and no GO/NO-GO gate here**. The job
is "understand this company", whatever the reason for asking._

## Source-priority hierarchy (when sources conflict, trust higher)
1. Company website (self-reported facts)
2. SEC / Companies House / public filings (financials, legal entity)
3. Crunchbase / PitchBook (funding, valuation, investors)
4. LinkedIn (headcount, team, growth, tenure)
5. Press releases (announcements, partnerships)
6. News articles (industry context)
7. Review sites (G2, Capterra, Glassdoor)
8. Social media (real-time signals, culture)

**Distrust scraped profile aggregators.** Craft.co, Owler, ZoomInfo, Latka, Growjo and similar sit
BELOW everything above and are frequently flatly wrong — in testing, one returned 5 employees, 2018
revenue, the wrong HQ and an invented competitor list for a 160-person company whose real accounts are
filed and public. Never take headcount, revenue, founding year or competitors from them when a filing,
the company's own site or LinkedIn exists. If one is genuinely your only source, mark the fact **Low**
and say where it came from.

## Confidence flags (tag every material claim)
| Flag | Meaning |
|---|---|
| **High** | Directly stated / observable fact |
| **Med** | Reasonable inference from real data |
| **Low** | Indirect signal needing interpretation |
| **Inferred** | Educated guess from company profile |

## Freshness
- Headcount within 6 months or flag it. Funding: include latest round, flag if 18+ months old.
- Revenue: always state the estimation method + confidence.
- News/triggers: last 6 months is "current"; older goes in History.

---

## The research dimensions (port — prune to taste)
Default depth captures the first set; the rest are "go deeper" sections. Each fact
carries a source + confidence. Never present an inferred number as known.

### 1. Overview
Legal name + DBA, founded, founders, HQ + other offices, geography, employee count
(+ source), stage (startup / growth / mature / public), structure (private / public /
subsidiary), one-line "what they actually do", mission/vision if stated.
Employee-count methods: LinkedIn page, hiring velocity, team page (understates), press mentions.

### 2. Business model & revenue
Revenue model (subscription / transactional / marketplace / advertising / licensing),
pricing tiers (note any "Contact Sales"/enterprise tier), revenue estimate **with method
+ confidence**, customer count / notable logos, key metrics (DAU/MAU/ARR), monetisation signals.
Revenue estimation methods (state which): employee-based (median SaaS ~$200–300k/employee ×
industry multiplier), funding-based (Series A ≈ $1–3M ARR, B ≈ $5–15M, C ≈ $15–50M),
customer-based (avg price × customers), traffic-based (traffic × conversion × AOV).

### 3. Product & technology
Core products, product category, tech stack (from job posts, tech blog, site source),
differentiators, integrations, API/platform maturity, notable IP / open source.

### 4. Leadership & team — OUT OF SCOPE for this skill
No people/leadership section and no named contacts (locked decision). A leadership change can
still count as a *trigger* under Recent developments, but never a named-person section.

### 5. Funding & financial health
Total funding, latest round (type, amount, date), round history, key investors, valuation,
burn-rate signals (hiring pace vs funding age, layoffs), profitability signals.

### 6. Market position
Market category, top 3–5 competitors, relative position, differentiators vs competitors,
win/loss signals from reviews, analyst coverage, awards.

### 7. Culture & employer brand
Stated values, Glassdoor rating + themes, hiring pace, work model (remote/hybrid/office),
notable benefits, overall employer-brand strength.

### 8. Recent developments (last 6 months)
Product launches, partnerships, funding events, leadership changes, market/geographic
expansion, controversies (negative press, lawsuits, breaches, layoffs), customer wins,
acquisitions. Reverse-chronological. These are the conversation hooks.

---

## Output: what the brief should contain (DECIDED fundamentals, not "everything")
A neutral, sourced understanding per company. Pick the fundamentals that actually help a
seller; don't pad. On-screen this is the company's drill-in card (opened from its list row),
sections in this order:
1. **What they do** — one factual line (hero).
2. **Why now + angle to use** — recent triggers and the resulting play. The payoff. Lead here.
3. **Money & scale** — revenue estimate, funding, headcount/hiring trend. Growth, not "founded".
4. **Competitors** — 3–5 named, a one-liner each + a neutral where-a-seller-wins/loses angle.
5. **How big & growing/shrinking** — employees + a growth trend (▲/▼) in the metric strip.
6. **What they likely run** — tools/stack, especially anything near the user's product.
7. **Location (HQ)** — a thin Founded · HQ line; **no map** (removed).
- **Hero strip** (founded, HQ) — one thin line, not the headline.
- **Deeper detail** + **Sources** — overflow and links.

NO people/leadership section and NO fabricated "who to talk to" contacts (those need
enrichment). **Fit (BANT)** is an OPTIONAL panel scored only against the user's own business
profile — never the company in isolation; with no profile it's the onboarding prompt. The
competitor angle stays neutral (how a generic seller is positioned), not "why you should sell".

No score. No verdict. No "should you sell to them". If the user later asks to qualify it
against a profile, that is a separate step layered on top — not part of this skill.

## Graceful degradation
URL unreachable → web search only. Page missing → "Not publicly available", continue.
Thin footprint → lower confidence across the board, note the gap. Always produce a brief
with whatever exists. Gaps are flagged, never faked.
