# Cold Email Scoring Model — v2.7.4 (skill-canonical)

**Status:** the live rubric the skill grades and writes against. v2.7.4 = v2.7.3 + a **no-subject-pasted** case: a body pasted without a `Subject:` line leaves the subject NEUTRAL (not failed, not docked, excluded from the cap) and offers a suggested one — only a subject the user actually wrote can be marked down (§2). v2.7.3 = v2.7.2 + the intake is no longer asked: score instantly on a harsh **cold-B2B / profile-A / no-price** default, remembered per user via a preference file, and re-graded only if the user states a different lens (§0). v2.7.2 = v2.7.1 + the fixed **Archetype library (§8)**: every graded email is labelled with exactly one repeatable archetype naming its lead move, which feeds the GRADE verdict headline (label only, never changes the score). v2.7.1 = v2.7 + three fixes from the 17 Jun 2026 split-agent practice run: a merge-field-vs-claimed-specific worked example (§2b), curiosity-bait/surveillance subjects now fail the Subject gate (§2), and a calibration note against under-awarding clean copy (§7). v2.7 = v2.6 + locked 4-question intake (adds the price-in-email call), personalisation demoted from a hard C/72 ceiling to a weighted lever (forced/creepy personalisation now penalised), and the two strategic calls surfaced in output. v2.6 = v2.5 + one micro-fix (no-subject handling). Dev history and the reasoning behind every rule live in the maintainer's calibration runs 01–10 (kept outside this skill package).

## 0. Lens — never asked, harsh default, remembered (v2.7.3)
The four old intake questions are **not asked**. Grade immediately on a fixed default lens, overridable by a remembered preference.
- **Default lens:** **profile A · B2B · cold first-touch · no price** — the harshest reasonable reading. This is what an email is graded as unless a preference says otherwise.
- **Preference file:** `cold-email-scorecard.prefs.json` in the user's working folder may set `profile` (A/B/C), `audience` (B2B/B2C), `mode` (cold/follow-up/reactivation), `price` (yes/no). Present → use it. Absent → default.
- **Lens parameters drive the rubric exactly as before:** profile → §1; audience/list → §2a/§4; mode → §4a (reactivation/follow-up); price → surfaced in output, never scored as copy.
- **Changing it:** the user stating "it's B2C / a follow-up / consumer" re-grades on that lens and persists it via the brain bridge (`scripts/brain_bridge.py save … lens=…`); the preference file is a read-only legacy fallback, never written. The card always prints the current lens.

## 1. Profiles
| | **A — SMB/founder B2B** (default) | **B — B2C / local** | **C — high-ticket / enterprise** |
|---|---|---|---|
| Deal size | low–mid ($20–5k/mo) | low-ticket / consumer | $50k+ |
| CTA gate accepts | interest, offer, soft Q | direct offer ok | interest/offer only; cold calendar link punished |
| Proof counts as | peer + number | reviews, guarantee, local cred | named peer + hard metric |
| Personalisation bar | moderate | segment-level ok | deep/research-level |
| Compliance | CAN-SPAM / PECR B2B | consumer PECR+GDPR | CAN-SPAM / PECR B2B |

## 2. The gated funnel
Each gate 1–5; **<3 = fail**. Order: Deliverability → Subject → Relevance → CTA.
**Caps:** 1 fail → 45–54; 2 → 30–44; 3+ → <30; deliverability spam-bomb → <25. **A gate failure caps below 60.**

**(v2.7.4) No subject pasted → Subject is NEUTRAL, not failed.** When the user pastes a body with no `Subject:` line, the subject is *not provided*: **do NOT fail the Subject gate, do NOT dock the score, exclude it from any cap.** In the artefact mark the Subject gate as pass with the note "no subject pasted — not penalised", and offer to suggest one (a suggested subject is a bonus, never graded against them). Only a subject the user actually wrote that is blank, bait, or weak is marked down (see curiosity-bait rule below). A genuinely empty subject in a real send (user confirms "there is no subject") still fails.

**(v2.7.1) Curiosity-bait / surveillance subject → Subject gate FAILS.** A subject that is vague clickbait, sets up a creepy or misleading reveal, or fakes a relationship ("saw your activity", "re:" with no prior thread) doesn't look like a real 1:1 note and isn't honestly paid off by the body. Score it <3. This targets bait and deception only; a plain-but-dull honest subject is not penalised here.

### 2a. Relevance gate — them-led vs sender-led
- **PASS** if the lead is about the recipient: their situation/signal, a concrete shared problem-moment, or a value offer framed around them.
- **FAIL** if sender-led: product/company intro, pitch-slap, generic "we help [segment] achieve [benefit]".
- On a broad/segment list the gate reads the **BODY's opening**, not the subject. A strong subject does not rescue a sender-led or feature-dump body.

### 2b. Individual signal is a lever, not a cap (token/signal rule) — v2.7
- **Merge tokens** (`[Name]`, `[Company]`, `{{firstName}}`) are filled fields; they NEVER cap the score.
- **No hard ceiling for "no individual signal" (changed v2.7).** A genuinely relevant email to the right person on the right trigger can reach A/B with no per-person line. Individual signal LIFTS Relevance; it no longer caps the score.
- A **genuine individual signal** (literal specifics about this recipient) is a bonus that pushes Relevance toward 5.
- Token standing in for a **claimed specific detail** (`loved your [blog]`, `[GENERIC BENEFIT]`) → fake personalisation → Relevance FAILS.
- **Forced / creepy personalisation** (surveillance-style "I saw you did X, then Y, then Z", or a personal line bolted on with no bearing on the offer) → deduct Relevance; it reads as off-putting. Relevant-to-the-offer beats personal-for-its-own-sake.
- **Merge field vs claimed-specific — worked example (v2.7.1).** A bare merge field renders to a neutral fact and is fine: `covering [City]` → "covering Leeds". A merge field wrapped in an *asserted observation about them* is a claimed specific, not a merge field: `Saw you're one of the few firms covering [City] out of hours` asserts a researched claim whose specific is unrendered, so it reads as fake personalisation. **Test:** strip the bracket; if the sentence still claims you looked them up ("Saw you're one of the few firms covering ___ out of hours"), treat it as a claimed specific → Relevance FAILS unless the claim is literally true and verifiable for every recipient on the list. Do not bolt an unverifiable "I researched you" line onto an email that already passes.

## 3. Block A — weighted score (only if all gates clear)
| Dimension | Weight | "5" |
|---|---|---|
| Relevance & targeting | 25 | right person, right trigger, real why-now; a genuine individual signal is a bonus, not a requirement |
| Problem-led & triggering | 20 | their problem as a concrete moment |
| CTA quality | 20 | one, low-friction, right tier for profile |
| Proof & credibility | 15 | profile-appropriate proof |
| Brevity & readability | 10 | ~50–125 words, one idea |
| Subject line | 10 | short, internal-looking, paid off by body |

### 3a. Caps vs arithmetic — order of operations
Evaluate **PIN flags first, then ceilings, then arithmetic**. Lowest result wins.
- **PIN flags:** competence-insult → place in **Gated**; praise-only → place in **D**. Research does not exempt a pin.
- **CEILING caps:** template/placeholder (unfilled blanks) → max C; reactivation → ≤ C. (v2.7: the "no individual signal → ≤ C/72" ceiling is removed, see §2b.)

## 4. Tight-list rule (v2.7: no ceiling)
Broad → §2a. Tight (narrow, named, category-matched) → category/trigger relevance counts in full, Relevance floor ~3, brevity rewarded, **no C/72 ceiling**. A strong tight-list email can reach A/B on category relevance alone; a genuine individual signal lifts it further but is not required.

### 4a. Reactivation / warm-follow-up mode
Not judged as cold: relevance bar = prior interest; short on-topic reopener passes; **waive Proof + individual-signal**, renormalise; **ceiling C**.

## 5. Special rules, flags, penalties
- **Token split rule** → §2b.
- **Deception (deduct-and-warn):** fake "Re:/Fwd:" threads, false "as discussed" → −1 Subject, −1 realness + warning. (On a cold list, fake-continuity with no real relevance still fails Relevance.)
- **Missing sign-off on a cold email (flag-and-confirm, no dock):** a cold first-touch normally closes with a sign-off — a bare sender name on its own line is enough (no need for "Kind regards"), with nothing after the name. If there's no sign-off, **don't deduct**: raise "no sign-off — sure you want to send without one?" in the teardown so the user confirms it's intentional. Punchy them-led cold emails often drop it deliberately. (Content trailing *after* the name — a bio tacked below it — is still flagged via the self-block/bio rule.) Warm/reply threads skip this.
- **Profile-B compliance = warn, not hard-gate.**

**Auto-flags:**
- **Pitch-slap** (sender-led lead) → Relevance fails.
- **Multiple CTAs** → CTA fails.
- **Cold calendar link** → profile B deduction; profile C part-cap.
- **Feature dump** → Problem + Proof hit; on a broad list also fails Relevance.
- **Fake / stale personalisation** → Relevance fails.
- **Forced / creepy personalisation** → deduct Relevance (not a fail unless fabricated). Surveillance-style or bolted-on personal lines read as off-putting; relevant-to-the-offer beats personal-for-its-own-sake. (v2.7)
- **"Just checking in"** → Problem fails.
- **Competence-insult** → **PIN to Gated** + warning. Fires ONLY when the email tells the recipient they're doing badly at the specific craft/service they SELL. A neutral observation about a tool/process they merely *use* does not fire. Test: would they read it as "you're bad at your own job"?
- **Praise-only opener** → **PIN to D** + "praise is not a reason to reply."
- **Believability flag — teardown only, does NOT change the score.** When the core claim is hypothetical/conditional/vague ("*if* I had a buyer", "we could probably help") rather than concrete/committed ("I *have* a buyer", "you're losing X/month"), flag it: *"state the claim as a concrete fact, not a hypothetical — vagueness reads as untrue and kills replies."* Candidate scored dimension, held out of the weights until live outcome pairs confirm it.

## 6. Bands
A 90+ · B 80–89 · C 70–79 · D 60–69 · **Gated 30–59** · F <30.

## 7. Known limits (state honestly in output)
- Grades **copy, not list quality** (intake carries the list). Short copy to a tight/warm list may out-perform its grade.
- **Templates with blanks cap at C** — they grade template hygiene, not the filled-in send. A real, rendered individual signal scores higher (write-mode confirms A is reachable).
- **Within-band fine ranking** (the believability lever) is still calibrating on live outcomes; trust the band more than a 2–3 point gap.
- **Don't under-award clean copy (v2.7.1).** When all gates clear and the dimensions are genuinely 5s, award the full arithmetic score, **including A (90+)**. "Trust the band" means don't over-read a 2–3 point gap; it does NOT mean reflexively holding rewrites at B. A BUILD/rewrite reaching A is expected when earned; never cap it just to look conservative.

## 8. Archetype library (fixed — assign exactly one, repeatable)
The verdict names the email's dominant **lead move** so the same email always returns the same archetype. This is a LABEL, not a score: it never changes the number, it tells the user what *kind* of email they wrote. Walk the list top-down and assign the **first** that matches (gate-fail tier outranks lead-move tier; within a tier, lowest number wins). ★ = grounded in a real calibration email (`outcomes-log.md`).

**Gate-fail tier (check first — these typically fail a gate in §2):**
1. **The Pitch-Slap** ★ — opener leads with the sender/product ("We help X do Y", "I'm [name] from [co]…"). Relevance gate fail (§2a). *(Massaro we-help — won only on a hot list.)*
2. **The Naked Question** ★ — opens on a generic question with no personalisation or signal ("Honest question…"). *(SDR E97, 4%.)*
3. **The Curiosity Hook** ★ — withholding/vague subject or opener engineered for curiosity ("{domain} quick question"). Often trips the curiosity-bait Subject fail (§2, v2.7.1). *(IH, 0.37–2%.)*

**Lead-move tier (clears the relevance gate — assign by what it leads with):**
4. **The Concrete Offer** ★ — leads with a specific real asset in hand ("I have a buyer ready, talking numbers?"). Believability win (§5 believability flag). *(SalesBread, 18%.)*
5. **The Hypothetical** ★ — the conditional twin of #4 ("If I had a buyer, open to a call?"). Fires the believability flag. *(SalesBread IF, 9.8%.)*
6. **The Them-Led Opener** ★ — opens on a real signal about them (their post, role change, trigger event). *(SDR E93, 42%.)*
7. **The Problem-Led Opener** — leads with a specific pain moment they're living now.
8. **The Proof-Led Opener** — leads with a named peer result ("Got [peer] +35%").
9. **The Referral / Pointer** — asks to be pointed to the right person (Cold Calling 2.0).
10. **The Giver** — leads with genuine free value/gift first (reciprocity).
11. **The Pivot** — reframes mid-email from one angle to another (structural fallback when no cleaner lead move dominates).

**Assignment rule:** every graded email gets exactly one archetype. If two lead-move types are present, the one the **first line/sentence** commits to wins. #11 (The Pivot) is the catch-all only when no single lead move dominates. The name feeds the GRADE verdict headline (§ SKILL.md GRADE default view).

## 9. The meter — deterministic pre-pass (v2.8)
**Why this exists:** the rubric's countable signals were being eyeballed, so the same email scored a few points differently every run. The meter **counts** them once and **sets the floors/docks below before any judgement.** Run `scripts/meter.py emails.json` (or compute the identical counts by hand) FIRST; judgement then scores only what is genuinely subjective — relevance *quality*, proof *believability*, problem concreteness. Same email in → same numbers out. Do not re-litigate a counted value (never "feels short enough" against a 180-word body).

**Tier 1 — floors / docks (objective, applied to Block A before arithmetic):**
- **Body word count → Brevity.** ≤125 fine · 126–175 −1 · 176–225 −2 · >225 −3. *(Boomerang 40M [large-N vendor], evidence-base S; Yesware 262,518 templates [large-N vendor], evidence-base T; Gong/30MPC 85M: 50–125, ideal <100.)*
- **Self-reference ratio** (I/we/my/me/our vs you/your) **→ Relevance.** Dock −1 only at **≥1.8:1**; below that, flag only. **Heuristic, not a sourced number — never hard-fails.** *(Direction only: Gong pitching −57%, "make it about them".)*
- **Self-block / bio bloat → flag to trim.** Any net-self paragraph ≥45% of the email, or a bio/credentials block ("About me", "my name is", a title, "co-founder") that is self-referential and ≥15%. Advisory flag, no dock. *(This is the lever that catches an over-long About-me.)*
- **Link count → Deliverability.** 0 in a cold first-touch; ≥1 → −1 + placement warning. *(Smartlead / Cognism / QuickMail; Hunter HTML-bounce direction, exact % soft.)*

**Tier 2 — flags only (never dock — a helpful builder, not a nitpicky gate):**
- **Subject word count.** None pasted → NEUTRAL (don't penalise, see §2); 1–6 fine; 7–9 "slightly long"; ≥10 "trim to ~1–6". *(Yesware 1–5 words peak [large-N vendor], evidence-base T.)*
- **Question count.** 1 ideal; 0 → "consider a soft ask"; ≥4 → "Boomerang sweet spot is 1–3". *(Boomerang: 1–3 questions, ~50% more replies than none [large-N vendor], evidence-base S.)*

**Tier 3 — readability, deliberately one-sided** (only ever costs points when dense/long, never rewards going simpler — this protects necessary technical terms):
- **Reading grade (Flesch-Kincaid).** ≤10 fine; 11–13 flag "a touch dense"; >13 → −1 Brevity. **No credit for going under grade 5.** *(Boomerang 3rd-grade +36% replies [large-N vendor], evidence-base S — used as a ceiling, not a target.)*
- **Sentence length.** avg ≥20 words → −1 Brevity; longest >35 words → "split it" flag.

**Realness:** no sign-off on a cold first-touch → **advisory flag only, no dock** — surface "no sign-off — sure you want to send without one?" in the teardown so the user confirms it's deliberate (§5). Not a defect; many punchy cold emails skip it on purpose.

**Output & card:** the meter returns metrics + flags + the implied docks. Flags surface in the teardown as concrete fixes; the counts are shown on the card so the user sees *why* a dimension was floored. **Honesty line:** word count, reading grade, links, sentence length, subject and question counts are evidence-anchored; the self-reference ratio and self-block are reasonable heuristics we set ourselves — they flag and softly dock, never hard-fail.
