---
name: list-builder-apollo
description: End-to-end prospecting on a connected Apollo account — no API key needed. The free steps scrape directories, match companies to your target profile, enforce the job titles you asked for, and check which email addresses are likely to actually land; the paid steps (Apollo company search and contact enrichment) each sit behind their own explicit confirm — nothing is spent without a yes. Builds a ranked shortlist and a review Excel before any enrichment. If filters thin the list it relaxes titles one step, then stops and asks rather than pad. Delivers a ready-to-send Excel formatted for cold email tools and maintains a per-niche master file for dedupe and pipeline tracking. Use when the user types /list-builder-apollo, or asks to find prospects, build a target list, or run prospecting.
version: 1.0.1
---

# list-builder-apollo

If a `LOCAL.md` file sits beside this SKILL.md, read it and let it win over anything here — with one carve-out: the rating strip and licence/attribution notices always stay, whatever a LOCAL.md says.

**List Builder**: finds named decision-makers and verified emails on a connected Apollo account.


End-to-end prospecting for cold email outreach. The Excel file is the deliverable. Every formatting and structural decision optimises for: clean, scannable, ready to drop into any cold-email tool (Instantly, Smartlead, lemlist, etc.) via plain First Name / Last Name / Email / Company columns.

---

## AI sales brain (READ-ONLY — read this before Stage 1)

This skill can read the user's shared **AI sales brain** to pre-fill part of the Stage 1 pre-flight. It never writes to it, never creates it, and never runs the setup itself.

**Lib resolution.** Before Stage 0.5, try `<working folder>/Claude HQ/_lib/brain/brain_bridge.py`. If that file is not present, this skill has no bundled brain libs — treat it as no brain and run Stage 1 exactly as written below, standalone.

**Read (only if the lib is present).** Call:
```
python3 "<working folder>/Claude HQ/_lib/brain/brain_bridge.py" get --skill sales-setup --base "<working folder>/Claude HQ"
```
This is a read. It creates nothing — a user with no brain yet gets back an empty/default `profile` and the run proceeds exactly as if the brain didn't exist. Never call the `save` verb from this skill.

**If the brain has usable targeting data** (a non-empty `profile.audience`, and/or `profile.product`), use it to pre-fill Round 1/Round 2 of Stage 1 — see "Brain-aware pre-fill" under Stage 1 below — instead of asking those questions cold. Anything the brain doesn't cover is still asked normally.

**If there is no brain, or the lib is missing, or the profile is empty:** run Stage 1 unchanged, exactly as documented below. At most once per run — after the pre-flight questions complete, never before, never twice, never blocking — you may add this single optional line:

> If you have the sales-brain-setup skill, run it once and I'll already know your targeting next time.

**User override always wins for this run.** If the user changes any pre-filled answer, use their version for the whole run and do not write it back to the brain — that's the setup skill's job, not this one.

---

## The ledger — archive every list built, silently

**When the final Excel is written, archive the run.** One call, then carry on:

```
python3 "<SKILL_DIR>/scripts/ledger.py" append --base "<wf>" --skill list-builder \
  --kind list.built --subject "<the niche, in the user's words>" --ref "<absolute path to the Excel>" \
  --meta rows=N --meta titles="<the two-tier titles enforced>" --meta filters="<geo, size, industry>" \
  --meta softened="<what was relaxed, or none>" --meta credits=N
```

- **Reference the Excel, never copy it.** The rows already live in the per-niche master file; duplicating them would bloat the archive and desynchronise two copies of the same truth.
- **Archive the filters and what got softened.** The rows are recoverable from the file; *why this list looked like this* is not, and that is the part worth having in six months.
- **A run that ends without a list still gets a line** (`--kind list.abandoned` with the reason). A niche that could not be filled is a finding, and silence looks identical to never having tried.
- **Silent and non-blocking, always.** Never mention it, never show the command, never wait on it. `ledger.py` exits 0 on every path by design; if it reports `written:false` (folder not mounted, user turned it off), ignore it and carry on. The archive is never a reason a user doesn't get their work.
- **It changes nothing about how this skill behaves.** The ledger is written here and never read here. It projects into no profile, feeds no scoring, and alters no output.
- **The user's controls, if they ask:** the archive lives in a `ledger/` folder at the top of their working folder and goes nowhere else; `ledger/.disabled` turns it off; deleting `ledger/` deletes it.
- **⛔ NEVER `present_files` the ledger or the scrape side-cars.** `ledger/*.jsonl`, `.people_search.jsonl`, `.enrichment_output.jsonl` and the brain store files are internal state. The host's default is "files were written, show them", so silence here ends the run with download cards full of internals. **The ONLY file this skill ever hands over is `Prospects_[Niche]_MASTER.xlsx`**, via the `computer://` link at Stage 8 / Final, or the dashboard's Download Excel button. (Sole exception: the dashboard HTML itself, in Stage 13's no-tool fallback.)

## STRATEGIC PRINCIPLE (read this first)

**The skill's job is to return good matches, not to hit the number.** Quality of fit beats volume every time. If filters take the list below 60% of target, stop and ask rather than padding with low-confidence firms. See Stage 4 volume-honesty rule.

**Free pass = judgment work no API does well.** Operator filter (vendor vs. real operator), semantic description match against the niche, Background context (recent deals, integration risk), MX/deliverability classification, revenue estimate, sense-checks. This is the differentiator. (Headcount, growth-trend and most revenue are filled later from Apollo enrichment, not from a registry.)

**Paid pass = data harvest, through the connected Apollo app — NO API key.** Claude calls the `apollo_people_bulk_match` connector tool in batches of up to 10 contacts, matched by Apollo person ID (~95% hit rate). The response is large (~5,000 lines per contact), so the platform auto-saves it to a file and returns only a path; Claude reads that file with `jq` and never lets it into context. That trimmed output is the source of truth — see Stage 10 for the call pattern and Stage 11 for how downstream consumes it. **No `APOLLO_API_KEY`, no `.env`, no credentials step: the same connected Apollo account that powers search also powers enrichment.**

**Token-cost discipline.** A 10-contact `apollo_people_bulk_match` response is ~5,000 lines of JSON per contact (full employment_history, ~150-item keywords array); a 10-contact batch runs ~130k characters / ~3,900 lines. Because it exceeds the inline limit, the connector auto-saves the response to a file and returns only the path — confirmed in testing. Claude MUST read that file with `jq`, extract only the trimmed fields (Stage 10 schema), and never let the full payload into context. If a tiny batch ever returns inline, persist it to a temp file first and `jq` it the same way. Never summarise the full payload from context.

**Interface goal: minimum user clicks, maximum data per credit spent.** Target: two batched question rounds plus one confirmation per paid step (company search at Stage 2, enrichment at Stage 9). Anything more is friction; anything less risks acting on bad assumptions.

---

## FOUNDATIONAL PRINCIPLES

These override everything else. Read first, every time.

### 0. LOCALE IS NOT HARDCODED — DETECT IT FROM GEOGRAPHY

This skill ships to users in any country. Do not assume UK/£. At Stage 1 Q2 (geography), set the run's currency and corporate registry from the answer:
- **Currency** — drive all money UI (revenue-band options, dollar/credit estimate, per-head benchmarks) from the geography's currency: £ for UK, $ for US, € for eurozone, etc. Never present £ bands to a non-UK user.
- **Headcount, growth-trend and most revenue come from Apollo enrichment (Stage 10) — global, no registry, no key.** Do NOT ask the user their country beyond Q2, and do NOT make any registry a requirement. A corporate registry is only an OPTIONAL silent top-up for *verified revenue* on firms Apollo left blank, and only fires per-firm when a key for that registry already exists in the environment: Companies House (UK), SEC EDGAR (US public, no key needed). If no registry key is present, skip it silently and fall back to Apollo revenue → web-search estimate → "Unknown". Never block, never prompt for a registry key, never return a wall of "Unknown" without trying Apollo + web estimate first.
- **Destination tool** — the Excel is formatted for cold-email import generically (separate First Name / Last Name / Email / Company columns). Instantly is one consumer, not the only one; don't hardcode Instantly-specific assumptions beyond those plain columns.

### 1. NEVER SPEND USER MONEY WITHOUT EXPLICIT PERMISSION

**FREE Apollo calls — run automatically, no permission needed:**
- `apollo_users_api_profile`
- `apollo_mixed_people_api_search` (returns names, titles, **and Apollo person IDs — capture them**)
- Any endpoint where `credits_consumed` returns 0

**LOW-COST Apollo calls — 1 credit per request, NOT free:**
- `apollo_mixed_companies_search` (1 credit per request that returns results; 0 if no matches). Returns revenue, domain, LinkedIn. Because it costs a credit it gets its OWN explicit one-tap confirm immediately before Stage 2 runs the search (see Stage 2), never carried, never bundled into another question. Treat it like any other paid call per the rule below. Never describe this call as free.

**PAID Apollo calls — explicit user "yes" required, no exceptions:**
- `apollo_people_bulk_match` (the connector enrichment / email-reveal call — 1 credit per matched person, 0 on a miss, up to 10 per call). This is the only routine paid call, and it runs through the connected Apollo app — no API key.
- `apollo_organizations_bulk_enrich` (1 credit per matched org — and DON'T use this for revenue, the free search returns the same revenue field)
- Any endpoint where `credits_consumed` > 0

The principle is consent, not amount. £0.05 spent without permission is the same trust violation as £50. No "small amount" exceptions, no "let me just add this for you" exceptions, no backfill exceptions.

Before any paid call, the skill MUST: state credits + dollar estimate, present yes/no question with cancel option, wait for explicit yes.

### 2. THE FILE FORMAT IS THE DELIVERABLE

Every Excel file produced MUST match the format specification in `references/format-spec.md` exactly. Sanity check enforces it. The user has spent significant time on the format — never deviate.

### 3. USE XLSXWRITER FOR FILE OUTPUT, NEVER OPENPYXL'S SAVE

openpyxl has destructive bugs with hyperlinks: `cell.style = "Hyperlink"` after setting `cell.hyperlink` silently drops the hyperlink from the saved file. The `cell.hyperlink.target` attribute reads correctly post-save (Python cache) but the file shows plain text in Excel.

**Pattern: read with openpyxl, write with xlsxwriter.** Use `worksheet.write_url(row, col, url, format, display_text)` for every hyperlink cell. Verify the saved file by unzipping it and counting `<hyperlink ` entries in `xl/worksheets/sheet1.xml`. Must equal expected.

Never trust openpyxl's `cell.hyperlink.target` post-save as proof of correctness.

### 4. THE SKILL NEVER DELETES — APPEND-ONLY ON WORKBOOK TOTAL

Across any run of this skill, the combined row count of the master tab (`[Niche] — Merged`, where `[Niche]` is the run's niche) + `Filtered Out` must never decrease between the start and end of execution. Resolve the master tab name at runtime from the workbook's first tab / `run_niche` metadata — never assume a fixed niche. The skill can move rows between those tabs (e.g. drop a constraint-violating contact from Merged to Filtered Out post-enrichment) — that's net-zero. The skill must never remove a row from the workbook entirely.

**Why:** Deletes by the skill are silent destructive operations. Any bug in the dedupe logic — wrong key, broken filter, off-by-one — becomes a data-loss event if the script is allowed to shrink the master. Lost contacts are usually unrecoverable (Apollo's `people_match` doesn't auto-save to Saved Contacts, so prior enrichments aren't retrievable without re-spending credits).

**Enforcement:** Before any write to the master file, capture `pre_total = rows(Merged) + rows(Filtered Out)` from the existing file. After building the new in-memory state, assert `new_total >= pre_total`. If the assertion fails, abort without writing — the live file stays untouched. Write to a `.tmp` path first and only `os.replace` to the live path if the assertion passes.

**Out of scope:** deletions the user requests directly (hand-edits in Excel, explicit instructions to remove specific firms) happen outside the skill's automated run and are not constrained by this rule.

### 5. STAY IN LANE — AND CATCH THE CONSUMER TRAP (added 31 Aug 2026 after cold-run testing)

This skill builds B2B prospect lists. Nothing else. Two rules that must never depend on the model's mood:

- **Sibling jobs get a decline and a name, never a fake.** Asked mid-run (or instead of the run) to write the cold email, or to research one company in depth — strategy, revenue, "the works" — do NOT produce it. One line: that's a different tool's job — cold-email-builder for the email, company-researcher for the deep dive (both free at bingley.ai if not installed) — then return to the open question in THIS run. Never answer a deep-dive from memory dressed up as research, never draft outreach copy with no offer context. Plausible-sounding revenue figures from parametric memory are invented data.
- **Apollo has no consumers in it.** The moment the target could be individual people rather than businesses — weddings, homeowners, private clients, "anyone who'd pay" — say so BEFORE the intake continues: *"Apollo is a business database — it can't target consumers like wedding clients. Businesses that buy [their thing] — agencies, venues, corporates — I can do. Which is it?"* Never run a consumer-shaped brief through company search and let it return junk.
- **A vague brief never gets silently precised.** If Q2–Q4 (geography / headcount / revenue) go unanswered, re-ask or state the assumption in the recap line the user confirms — a band the user never picked is flagged as "my assumption", not passed off as their answer.

### 6. THE MID-RUN COST QUESTION HAS ONE ANSWER (added 31 Aug 2026 after cold-run testing)

"What is this doing? Is this costing me money?" mid-run is the single most likely interruption this skill gets. Answer it from state, not vibes, in this shape, then resume where the run left off (an interruption never restarts intake):

> "Spent so far: [N credits / nothing — say which, from the actual calls made]. The steps running now ([name them]) are free. The next paid step is [Stage 2 company search ~1 credit per request / Stage 9 enrichment ~1 credit per matched contact, ~$0.03 each] — it will show you the exact cost and wait for your yes. Nothing is ever spent without that yes, and you can stop at any point and keep everything built so far."

---

## FILE FORMAT SPECIFICATION (THE BLUEPRINT)

The full spec — filename rules, tabs, workbook metadata, the 19-column table, fonts, row formatting and colour rules — lives in `references/format-spec.md`. Read it in full before building or checking any Excel output (Stages 6, 7 and 11); every rule in it is binding.

---

## STAGE FLOW

### Stage 0 — Silent pre-flight

**Hard requirement — bash workspace.** This skill needs the bash tool (`mcp__workspace__bash` or equivalent): the jq extraction, MX lookups, side-car files and Excel build all run through it. If no bash tool is present, stop before Stage 1 and say so plainly — this skill cannot run without the bash workspace. Do not improvise a workaround.

1. **Apollo connector ping** via `apollo_users_api_profile` with `include_credit_usage=true`. Capture: connection ok and current credit balance. Do NOT hardcode plan sizes — read the live balance; Free, Basic, Professional and Organization all work and differ only in monthly credit allowance. Cache for session.
   - On fail / not connected: do NOT silently proceed, and do NOT ask for a key. Show this exact message before the entry/niche questions, then act on the reply:
     > **Quick one before we start, you've got two options:**
     >
     > **1. Say "Shortlist"** and I'll build a vetted company list right away. No names, no emails, you can enrich later.
     >
     > **2. Connect Apollo for the full run.** Apollo's a free database with verified emails and named decision-makers. Go to **apollo.io** and create a free account, then come back and connect it here:
     >    1. Click **Customise** on the left.
     >    2. Open **Connectors** and search **Apollo**.
     >    3. Sign in and approve, then say **ready**.
     - **If "Shortlist":** run research-only mode (every free stage), deliver the vetted company shortlist with Contact Name and Email set to "Connect Apollo to reveal", and close with: "This is your vetted company shortlist. Connect Apollo (a free account works) and re-run to turn these into named decision-makers with verified emails."
     - **If "ready":** re-ping `apollo_users_api_profile`. If now connected, run the full flow with verified emails. If still not connected, point back to the three connect steps above and offer the Shortlist option. Never hard-stop with nothing.
2. **No API key needed — enrichment runs through the connected Apollo app.** Do not check for, prompt for, or require `APOLLO_API_KEY`. The same Apollo connector that powers search (Stage 2/4) also powers enrichment (Stage 10) via `apollo_people_bulk_match`. The only Apollo requirement is that the Apollo app is connected (Step 1); if it is, every stage works end to end with nothing to paste.
3. **Master file scan** for `Prospects_*_MASTER.xlsx` — RECURSIVE across the whole working folder, any depth (users keep masters in subfolders). If two masters share the same niche at different paths, the most recently modified wins for the Continue path; surface the duplicate in one line of the run summary so the user can tidy it. Record `master_count` for Stage 0.5.
4. **Legacy file migration** (only on first ingest of pre-V2 file): scan Notes column for outreach signals. Move "email sent / replied / called" to User Notes col. Infer Status. One-time per file.
5. **Exclusion list** load if `exclusion_list.txt` present.
6. **Saved ICPs** load if `apolloclaude_icps.json` present.
7. **Dashboard capability (silent).** If the environment has any artifact publish/update tool (one that publishes an HTML file to a page and can republish the same file so the page updates in place), set `dashboard_enabled = true`; otherwise `false`. No user-facing message. When false, Stage 13 falls back to presenting the dashboard HTML as a single file.

### Stage 0.5 — Entry question (single AskUserQuestion call — SKIPPED on first run)

**If `master_count` is 0 (first run), do NOT ask this question — it has only one possible answer.** Go straight to Stage 1, and immediately before Round 1 say this one framing line (first run only, never again once a master exists):

> "Seven quick questions, then I build you a vetted list for free — you review it, and nothing is spent until you approve it."

Otherwise ask: "Are you starting a new search, or continuing an existing one?"
- **New** → Stage 1 (Round 1 + Round 2 = 2 user touches).
- **Continue [niche]** → Continue Round (3 questions in ONE call): volume / per-firm / parameter override (Yes-keep / Yes-tweak / No-cancel). Skip Stage 1. On Yes-keep, the prior run's `run_constraint` (read from workbook metadata) is reused. On Yes-tweak, Round 2 fires and the user can edit Q7.
- **Continue but change params** → Continue Round, then if "Yes-tweak", fall through to Stage 1 Round 2 only (Q5/Q6/Q7) preserving Q1-Q4.

In Cowork mode, master file scan happens silently in Stage 0; user sees one option per detected master file in the entry question (e.g. "Continue Wealth Management"), rather than a separate file-upload step.

### Stage 1 — Pre-flight (TWO BATCHED ROUNDS, not eight clicks)

AskUserQuestion supports up to 4 questions per call. Use that to batch.

**⛔ SINGLE-SELECT ONLY, EVERY QUESTION.** Single-select options auto-advance on tap; multi-select forces an extra "Next" click per question (tested and rejected). No question in this skill is ever multiSelect. Multi-valued answers are expressed as curated single-tap options (combined bands, title SETS), and anyone wanting a custom combination types it via the automatic "Other". **⛔ NO UI META-EXPLANATIONS in question text** — never write "one tap", "each option is a ready-made set", or similar; just ask the question.

**Brain-aware pre-fill (do this before building the Round 1 / Round 2 question arrays).** If Stage 0's brain read (see "AI sales brain" above) returned a non-empty `profile.audience` and/or `profile.product`, use it to pre-fill whichever of Q1/Q5/Q7 the free-text data actually supports, then drop those questions from the AskUserQuestion arrays and show one confirm line instead:

> "Using your AI sales brain: targeting **[niche/operator description]** at **[company-size band]** **[geography]** — right, or override?"

Only claim what the brain actually gave you — the brain's `profile.audience` is one free-text sentence (e.g. "mid-market and small enterprises in Spain"), not separate structured fields, so:
- **Q1 (niche)** — pre-fill from `profile.product` + `profile.audience` combined into the niche description; still shown in the confirm line, not silently assumed.
- **Q2 (geography)** — pre-fill only if a country/region is parseable out of `profile.audience` (e.g. "in Spain", "UK-based"). If geography is not stated, still ask Q2 normally.
- **Q3 (headcount) / Q4 (revenue)** — pre-fill only if a size descriptor is parseable out of `profile.audience` ("mid-market", "SMEs", "enterprise", "small business", etc. — map loosely to the existing band options). If nothing size-related is stated, still ask normally.
- **Q5 (decision-maker titles)** — the brain has no dedicated titles field today; only pre-fill if `profile.ask` or `profile.audience` names a role explicitly (e.g. "CFOs", "Head of Finance"). When Q5 IS pre-filled, include it in the confirm line as a "reaching **[titles]**" clause — never pre-fill it silently.
- **Q7 (constraint/disqualifier)** — check the brain's `profile.wcNotes` FIRST: any line starting `disqualifier:` is exactly this constraint (setup saves the user's "who's NOT a fit" there) — pre-fill Q7 with it verbatim and show it in the confirm line as "excluding **[disqualifier]**". Also pre-fill if the audience free text names an explicit exclusion. Otherwise still ask Q7 normally; never invent a constraint the brain didn't state.

Show the confirm line once, covering only the fields actually pre-filled (omit any bracket the brain didn't supply — e.g. if only niche and geography are known, drop the size clause from the sentence; append the "reaching" and "excluding" clauses only when Q5/Q7 were pre-filled). One tap to accept; typing an override replaces the pre-filled value for this run only, and is never written back to the brain. Any question the brain can't answer is still asked via the normal Round 1 / Round 2 flow below.

**Round 1 — Brief (4 questions in ONE AskUserQuestion call):**
- **Q1 Niche** — free text. Question wording (fixed): **"What industry or niche are you after? The more specific, the better."** 4 example options + "Something else" (auto-added by UI). **Cold-start examples (fixed — never improvise these):** Marketing agencies · Recruitment agencies · Accountancy firms · B2B SaaS. These four are deliberately the most widely recognised cold-email niches; never substitute specialist niches (e.g. boutique M&A) on a fresh install. Smart cycling: if user has saved ICPs, show 2 most recent + 2 adjacent instead of the cold-start four. If user clicks an example, fire double-check on submit: "You picked '[example]'. Is that your actual niche, or did you mean to type your own?"
- **Q2 Geography** — 4 common options + Something else.
- **Q3 Headcount** — single-select. Main: Early stage (1-10), Small (11-50), Mid-market (51-200), Larger (201+). If Larger picked, fire follow-up drill-down (201-1k, 1k-5k, 5k-25k, 25k+) as one extra question. Spans (e.g. 11-200) come via "Other".
- **Q4 Revenue** — single-select. Main: Under 5M, 5M-25M, 25M-100M, 100M+ — **labels are currency-neutral numerals** because Q4 renders in the same batch as Q2 (geography), so the currency is not yet known; add one description line: "in your local currency". Drill-down on either extreme. From Round 1's submit onward the geography answer sets the run currency, and every later money string (Rev Band column, credit estimates, run summary) uses the proper symbol.

**Round 2 — Targeting (4 questions in ONE AskUserQuestion call, fired AFTER Round 1):**
- **Q5 Decision-maker** — single-select, **niche-aware** based on Q1. Each option is a curated title SET, not one title — e.g. for agencies: "Founders + MDs (Recommended)" (Founder, Owner, MD, CEO) / "Founders / Owners only" / "MDs / CEOs only" / "Commercial leads" (Sales Director, Growth Director, Head of New Business). The chosen set becomes the strict tier. Construct the 4 sets from realistic senior titles for the niche. Examples: boutique M&A → Managing Partner / Senior Partner / MD / Founder; SaaS → CEO / CRO / Head of Growth / CTO; wealth management → Founder / MD / Head of Wealth / Compliance Director. **The titles selected here become the strict tier at Stage 4 — see Stage 4 two-tier title enforcement.** For niches outside financial services and SaaS (manufacturing, healthcare, construction, hospitality, retail, legal, creative), the four suggested titles are guesswork — sense-check before submitting. **Thin-tier warning (fires on Round 2 submit, one line, never blocks):** derive the softer tier (Stage 4 rules) from the selected titles at selection time; if it comes back EMPTY and no executive title (CEO/MD/Founder/Owner/Partner-level) is in the set — e.g. the user picked only "Practice Manager" — warn once: "[Titles] have no fallback tier, so if few firms list them on Apollo, coverage may run thin and I'll stop and ask rather than pad. Add a senior title, or continue as is?" Continue is a valid answer; the warning exists so the Stage 4 stop rule never ambushes anyone.
- **Q6a Total leads** — 10 / 50 (Recommended) / 100 / 250 / custom.
- **Q6b Contacts per firm** — 1 / 2 / 3. **Recommended-marker shifts based on Q3 headcount.** If Q3 = "Early stage (1-10)" only, mark "1 (Recommended)" and add description on 2/3 options: "Boutiques at 1-10 staff typically have 1 senior on Apollo — you'll likely get closer to 1 per firm regardless." If Q3 includes 11+, mark "2 (Recommended)".
- **Q7 Constraint** — free text, open question. Prompt: "Anything specific I should screen for or exclude? (Examples: pure-play only, no PE-backed firms, exclude franchises, must be founder-led, no manufacturers)". Default placeholder text in the UI gives those examples. Empty answer is valid and means "no extra constraint". Capture the answer **verbatim** and persist it as `run_constraint` for the run. It is passed to:
  - Stage 3 operator filter as a hard constraint (firms violating it are dropped to Filtered Out with reason "User constraint: [verbatim]"),
  - Stage 8 run summary banner ("Active constraint: [verbatim]"),
  - workbook custom property `run_constraint` so it travels with the master file and is recoverable on Continue runs.

**Pre-emptive credit check on Round 2 submit**: if `requested_leads > balance`, fire ONE follow-up question: "You picked [N] but have [balance] credits. Reduce / proceed anyway / top up first?". Do NOT bundle any credit spend into this step. The company-search spend is confirmed by its own one-tap prompt at Stage 2, and the verified-email spend is confirmed at Stage 9. Round 2 is targeting only.

**Volume threshold (≥250)**: bake into Q6a description ("Larger batch — recommended only if niche is validated"). No separate confirmation round.

### PROGRESS DISCIPLINE (Stages 2–7 and 10 — the silent stretch)

The free build takes 5–15 minutes and the user must never wonder whether it died. Two mechanisms, both mandatory when the environment supports them:
1. **Task list** — at run start create one task per major stage (Sources → Operator filter → People pull → Pre-enrichment → MX check → Build review file; plus Enrichment and Final update after the credit gate). Mark each in_progress/complete as the run moves. The widget is the ambient progress bar; no extra renders.
2. **One status line per stage boundary** — a single compact line, numbers not prose, e.g. "212 candidates → operator filter → 61 survive → pulling people". Never more than one line per stage, never a paragraph, never silent across a stage boundary.

### Stage 2 — Source discovery (free directory scrape + one paid search, explicitly confirmed)

Two channels, merged. Channel A (directory scrape) is genuinely free and runs automatically. Channel B (Apollo company search) costs 1 credit per request, so it gets its OWN explicit one-tap confirm BEFORE it runs:
> "To find your firms I'll run Apollo company search, about 1 credit per search request (roughly [X] credits for this run). Proceed?"
>
> Compute [X] = `ceil(1.3 × requested_firms / 25)`, floored at 2 and capped at 10 requests — state it as a rough figure, never a promise.
> - **Yes, run the search** — spend the company-search credits and continue.
> - **No, free directory only** — skip the paid search; build from the free directory scrape alone (smaller, lower coverage).
> - **Cancel** — stop here, spend nothing.

Only on **Yes** is any company-search credit spent.

**FREE-PLAN FALLBACK.** Apollo's Free plan returns `API_INACCESSIBLE` on BOTH search APIs (`mixed_companies_search` AND `mixed_people_api_search`) through the connector — errored calls cost 0 credits. On that error do NOT stop and do NOT re-ask: say one line — "Your Apollo plan doesn't include search, so I'll discover companies from the web instead; nothing was spent" — then run WEB DISCOVERY as a full Channel-B replacement: extend the directory scrape, and per candidate firm run verification web searches for headcount, revenue signal, and the decision-maker's name (team pages, press, league tables). Stage 4's people pull is replaced by those researched names, and Stage 10 matches by `first_name + last_name + organization_name + domain` instead of person ID (enrichment endpoints DO work on Free). Everything else — filters, MX, review file, dashboard, credit gates — runs unchanged. This satisfies Principle 1 (explicit yes before any paid call) and the Apollo tool's own mandatory 1-credit confirm. The skill still picks the directories itself (most users don't know which matter); the confirm is purely about the credit spend, not the source choice.

**Channel A: Niche Data (Top 4 highest-confidence directories)** — web search for niche-specific directories (ICAEW CFF, BVCA, AMAA for M&A; AIA / NCARB for architects; PIMFA, VouchedFor, Citywire, FT Adviser for UK wealth; etc.). Default: scrape top 4 sources. **MANDATORY on continue path with same parameters.**

**Channel B: Apollo company search** — `apollo_mixed_companies_search` with niche keywords + geography + headcount + revenue. Returns canonical org records WITH revenue field. Costs 1 credit per request (not free); runs ONLY after the explicit one-tap confirm above.

**Merge** by domain. Tag source per row: Niche Data / Apollo / Both.

**Surface in Stage 8 run summary** which sources were actually scraped, so the user can override on next run if they want different coverage.

**Exhaustion fallback** triggered at end of Stage 4, not here.

### Stage 3 — Operator filter (FREE, RULE-BASED + SEMANTIC)

Drop vendors-to-the-niche. This stage runs three checks in order: rule-based industry/description patterns, then semantic description match against the niche + user constraint, then user-constraint enforcement. A firm only survives if it passes all three.

**Check 1 — Rule-based drops (sight-unseen):**

Apollo industry tags to drop on sight: Management Consulting, Computer Software, Information Technology & Services, Staffing & Recruiting, Marketing & Advertising, Professional Training & Coaching, Accounting (unless niche IS accountancy), Legal Services (unless niche IS legal).

Description patterns to drop: "we help [niche]", "platform for [niche]", "software for [niche]", "advisor to [niche]", "consultancy serving [niche]".

**Check 2 — Semantic description match (THE OPERATOR FILTER UPGRADE):**

For each candidate firm, read the actual company description and compare it semantically to: `niche + run_constraint`. If the description does not match the niche on substance, drop the firm.

Sources to read, in priority order:
1. Apollo `short_description` (primary)
2. Website blurb from the firm's homepage (WebFetch — only if Apollo description is thin or generic)
3. LinkedIn company tagline / `about` section (only if 1 and 2 are inconclusive)

What "match on substance" means: the firm's primary activity, as described in its own words, is the niche the user asked for. A firm that **serves** the niche, **sells into** the niche, or **was once in** the niche but has pivoted, is not a match.

**Do not rely on Apollo industry tags or SIC codes alone — they mislabel.** Tags are coarse, frequently inherited from years-old self-classification, and miss the substance of what a firm actually does. A firm's tag can match the niche while its own description shows the wrong sub-niche and the wrong buyer — the description wins.

When in doubt, drop. Quality > volume (see Stage 4 volume-honesty rule).

Log every semantic-match drop to Filtered Out with reason "Semantic mismatch: [one-line summary of what the firm actually does]".

**Check 3 — User constraint enforcement:**

If `run_constraint` (from Q7) is non-empty, apply it as a hard filter. The constraint is free-text from the user; interpret it literally and conservatively. If the constraint is "no PE-backed firms" and Apollo's `owned_by_organization` indicates PE ownership, drop. If the constraint is "founder-led only" and no current-founder evidence appears in description or team page, drop. If the constraint is ambiguous as it applies to a specific firm, prefer dropping over keeping (consistent with quality > volume).

Log every user-constraint drop to Filtered Out with reason "User constraint: [verbatim Q7 text]".

**Always-on drops (independent of the three checks above):**

- **Firm-level dedupe against master**: drop any firm whose domain matches any row already in the master.
- **Sub-3yr firms with under 10 staff**: drop. Source: `founded_year` from Apollo.
- **Firms acquired in last 12 months**: best-effort. Source: Apollo `owned_by_organization`. If parent is unfamiliar, orange-flag rather than auto-drop. Don't pull Companies House for this.
- **Exclusion list**: drop anything matching `exclusion_list.txt` if present.

Log every drop to Filtered Out tab with a specific reason.

### Stage 4 — People pull (FREE)

`apollo_mixed_people_api_search` with `organization_ids` filter. Up to N senior contacts per firm.

**Token discipline — `per_page: 100` + jq extraction.** Apollo people-search responses run ~500 bytes per person. At `per_page: 50` the payload sits inline in Claude's context (~10–30k tokens per page). At `per_page: 100` the payload usually crosses the MCP inline threshold and auto-writes to disk, returning only a file path. Always pass `per_page: 100` for this reason.

Immediately after each people-search call — whether the response is a file path or inline JSON — extract only the seven fields downstream stages actually need into a side-car JSONL via bash+jq, and reference ONLY the trimmed file in subsequent reasoning. Never re-cite the full response:

- `id` (Apollo person ID — primary key for Stage 10 enrichment)
- `first_name`
- `last_name_obfuscated`
- `title`
- `has_email`
- `has_direct_phone`
- `organization.name`

Recipe — for an auto-dumped response at `${TOOL_OUTPUT}`:
```
jq -c '.people[] | {id, first_name, last_name_obfuscated, title, has_email, has_direct_phone, organization_name: .organization.name}' "$TOOL_OUTPUT" >> "${MASTER_DIR}/.people_search.jsonl"
```
For an inline response, persist it to a temp file first then jq the same way. Downstream stages (title enforcement, ranking, build, enrichment) read from `.people_search.jsonl`, never from the full payload.

**Direct-REST is NOT available for people-search.** Apollo's Basic plan returns `403 API_INACCESSIBLE` on `/v1/people/search` and `/v1/mixed_people/search` when called with an API key. The MCP wrapper bypasses this via OAuth. People-search has to go through the MCP tool; the per_page=100 + jq pattern is the token-control mechanism.

**PAGINATION LOOP**: Apollo returns 50 per page (or 100 with the discipline above). Skill keeps fetching pages 2, 3, 4... and dedups each against master. Stop when ANY of:
- (a) net-new firms post-dedup ≥ `1.3 × requested_firms`,
- (b) Apollo returns no more results,
- (c) 10 pages cap reached.

**Apollo obfuscates last names on Free/Basic plans** (returns "Morgan At***n"). The Stage 10 bulk_match call needs a surname for any contact lacking a person ID (the name+org+domain fallback path); surnames typically surface incidentally during Stage 4.5D Background research (team pages, LinkedIn snippets) — capture and pass them to Stage 10. Mark Contact Name in the review file with `[Apollo: Xx***x]` until enrichment resolves it. Do NOT do dedicated surname-hunting passes. Contacts WITH a captured Apollo person ID don't need a surname at all — ID-based bulk_match bypasses the name heuristic.

**CAPTURE THE APOLLO PERSON ID for every contact.** `apollo_mixed_people_api_search` returns `id` on each person record. Persist it (e.g. as a column in the intermediate state and as a column in the review Excel's hidden metadata, OR as a side-car JSONL). Stage 10's `bulk_match` call uses `id` as the primary lookup key — ~95% hit rate via ID vs. ~5% via name-only on Basic plan. Without person IDs, Stage 10 falls back to the name + org path with much lower fidelity. The bulk endpoint accepts the same `id` field per-record in its `details[]` array as the singular endpoint does at top level.

**TWO-TIER TITLE ENFORCEMENT (size-conditional):**

Q5 selections form the **strict tier**. At Stage 4, the skill derives a **softer tier** algorithmically from each strict-tier title — niche-agnostic, never hardcoded:
- For any strict title of form "[X] Director" or "Director of [X]" → add "Head of [X]" and "[X] Manager" to softer tier. Example: Sales Director → Head of Sales, Sales Manager.
- For executive titles ("CEO", "MD", "Managing Director", "Managing Partner", "Senior Partner", "Founder", "Co-Founder", "Owner", "Chairman") → no softer adjacents.
- For titles already in "Head of [X]" form → no further adjacents.

Aliases: "MD" = "Managing Director", "CEO" = "Chief Executive Officer", "Co-Founder" = "Founder". Treat as equivalent on both tiers.

**Per-contact rule:**
- Firms with `estimated_num_employees ≥ 50` → strict tier only.
- Firms with `estimated_num_employees < 50` → strict tier OR softer tier.
- Firms with no headcount data yet → treat as <50 until enrichment resolves. Re-check at Stage 11; downgrade tier-promoted contacts if enriched headcount is ≥50 (drop to Filtered Out).

**Hybrid titles:** count if any token matches the applicable allow-list. "Founder & CEO" matches as strict. At a 30-staff firm, "Sales Manager & IFA" matches as softer (assuming Sales Director is on Q5). "Director & IFA" does NOT match if Q5 was "Managing Partner / Senior Partner / MD / Founder" — Director alone is not on either tier.

**Drop on no match.** Log to Filtered Out with reason "Title not on Q5 allow-list (firm size [N], tier checked: [strict/softer]): [actual title]".

Rationale: small firms title senior commercial leaders unevenly — at a 30-staff wholesaler, "Sales Manager" is often the de facto Sales Director. Large firms have proper hierarchies; soft titles there usually mean junior. The user made a decision in Q5 — honour it, but acknowledge that title norms vary by firm size.

**Exhaustion check — volume honesty (THE STOP RULE):**

After operator filter (Stage 3) + people pull + two-tier title enforcement (strict tier only at this point), compute:
- `valid_firms` = firms with ≥1 valid (has-email, allow-listed-title) senior contact
- `valid_contacts` = total contacts that survived
- `firms_short` = `requested_firms - valid_firms`
- `contacts_short` = `requested_contacts - valid_contacts`
- `firm_coverage = valid_firms / requested_firms`

**Bounded auto-softening (one step, pre-approved):**

If `firm_coverage < 0.60` using strict tier only, the skill may auto-promote the softer tier for **all** firms (not just <50) — one bounded step. Re-count. If coverage now ≥0.60, proceed and **surface in Stage 8 summary**: "Softened automatically to include softer-tier titles at all firm sizes because strict-tier coverage was [pct]%. [N] contacts came in through the softened tier."

Anything beyond one step (widen revenue, broaden Apollo keywords, expand geography) is NOT auto-applied. Requires explicit user approval via case 1 below. No silent padding.

**Decision tree (volume honesty rule applies first):**

1. **If `firm_coverage < 0.60` even after one-step softening → STOP. Do not pad.** Diagnose which filter dropped the most candidates by inspecting Filtered Out drop reasons; that's the lever to name. Fire ONE AskUserQuestion box:
   > "TAM thinner than expected after one-step softening. Returning [valid_firms] of [requested_firms] firms. That's [pct]% of target.
   >
   > Looking at the drops, the lever most likely to recover volume is: **[diagnosed lever, e.g. 'revenue band — 60% of drops were firms outside £5M–£25M']**.
   >
   > - **Widen [specific lever]** — [concrete change, e.g. 'extend revenue band to £5M–£40M']. Free, ~2–5 min.
   > - **Run as is** — proceed with [valid_firms] firms this run, top up later.
   > - **Pick a related niche** — cancel and restart with a different Q1."

2. **If `firm_coverage ≥ 0.60` AND `valid_contacts ≥ requested_contacts` → proceed silently.**

3. **If `firm_coverage ≥ 0.60` AND `valid_contacts < requested_contacts` → DO NOT fire user question.** Small-firm phenomenon: user asked for 2-3 per firm, but boutiques only have 1 senior on Apollo. Proceed silently. Note in Stage 8 run summary.

4. **If `firm_coverage ≥ 0.60` BUT below 1.0 → fire ONE softer AskUserQuestion box** (real but not catastrophic coverage gap):
   > "Found [X] firms with valid senior contacts vs. your target of [N]. To get the rest, I can:
   > - **Widen directory scrape** — pull from niche-specific sources beyond top 4 (~5 min, free)
   > - **Broaden Apollo params** — relax revenue band by ±£5M or headcount band by one tier (~2 min, free)
   > - **Proceed with [X] firms** — accept smaller batch this run, top up later"

The rule: case 3 doesn't ask because the answer is "the data is what it is at this size" — the user picked headcount band and per-firm count without knowing they interact. Cases 1 and 4 do ask because filters carved real volume off the target. Padding is never an option.

### Stage 4.5 — Free pre-enrichment (the differentiator)

Every piece of free data BEFORE any paid call. **Scope rule:** only do work that the paid people/match call will NOT return. Canonical paid-response field list lives in Stage 10 — do not duplicate any of those fields in this stage.

**A. Apollo org search per firm** — already returned canonical domain, company LinkedIn URL, revenue, founded year, switchboard phone. Use directly. For small UK firms, search response often returns null employee count and growth signals — accept this; paid enrichment will fill them.

**B. Revenue band waterfall** — for firms where Apollo returned null/0 revenue. (Apollo enrichment at Stage 10 also backfills revenue for many firms, so this pre-paid pass is best-effort and free; never block on it.)
1. WebSearch snippet: `"[firm] turnover [country]"`. Parse for £X.XM / $X.XM patterns (use the run's currency).
2. Companies House (UK firms) — ONLY if a `COMPANIES_HOUSE_API_KEY` is present in the environment; otherwise skip silently. When present: API search → company_number → filing-history → download iXBRL → parse `<ix:nonFraction name="*Turnover">`. ~80% hit rate for UK Ltd above small-co threshold.
3. SEC EDGAR for US public firms (no key needed; rare for cold-email targets).
4. Estimate from headcount × industry benchmark (per-head figures driven by the run's geography/niche). Mark `~` prefix + ` (est)` suffix.
5. "Unknown" only if no headcount AND no public source. Acceptable and common; not an error.

**C. Headcount trend — primary source is Apollo enrichment (Stage 10), global, no key:**
1. At Stage 11, read `organization.{six_month,one_year,two_year}_growth` from the enrichment output. Treat only non-null AND non-zero as authoritative — Apollo returns 0.0 for "no signal detected" (not "genuinely flat") at small firms, so treat 0.0 as null. Map: ↑ Growing (≥ +15%), → Stable (−15% to +15%), ↓ Shrinking (≤ −15%).
2. Optional UK top-up, ONLY if `COMPANIES_HOUSE_API_KEY` is present: pull last 2-3 accounts via filing-history, parse iXBRL for `EmployeesTotal`/`AverageNumberEmployees`, compute the YoY delta. Skip silently if no key.
3. "Unknown" if no non-zero Apollo signal AND no Companies House delta. Common for very small firms — acceptable, not an error.

**D. Background research per firm (scaled to volume)** — ≤25 firms = deep (recent deal, sector specialism, integration risk, ownership change). >25 firms = light (sector tag + one signal). Surnames captured here as byproduct.

**E. International register fallback (optional top-up, only if that registry's key is present; else skip silently)** — UK: Companies House. US public: SEC EDGAR (no key). US private: skip. Others: skip (OpenCorporates carries no revenue/headcount). Apollo enrichment remains the primary source for headcount/growth; this only adds verified revenue.

**F. Background field write** — 2-3 sentences industry-relevant per firm. Specialism + standout fact + integration risk + recent signal. If no public signal: "[Industry] firm based in [geography]."

**G. Apply Company website hyperlink** to col B using canonical domain. Visible text = company name; click opens website.

**Explicitly NOT done in this stage:**
- Dedicated surname-hunting passes (surnames come from 4.5D as a byproduct)
- Person LinkedIn URL search (paid enrichment returns most; backfill remaining only AFTER paid step in Stage 11.5)
- Any field the paid enrichment returns (see Stage 10 list)

### Stage 4.6 — MX gateway filter (FREE)

DNS MX lookup per firm domain. Classifies which provider actually receives mail for the domain. Lets cold email senders split gateway-protected domains (which aggressively quarantine unwarmed cold outreach) from M365/Google domains (which behave more predictably).

**The provider→bucket table and the rationale live in `references/mx-classification.md`.** Read it before classifying any domain, here or at the Stage 11.5 Step C.5 re-check.

**Classification rules.** For each firm domain (canonical primary domain from Stage 4.5A), resolve MX records and map the lowest-priority MX hostname to a provider bucket per the reference table. Write the result to two columns on every contact row at that firm:

- **MX Status** — one of: `GATEWAY`, `M365`, `GOOGLE`, `OTHER`, `NO_MX`, `UNKNOWN` (lookup failed — re-checkable, never a verdict)
- **MX Provider** — the matched provider string (e.g. `mimecast`, `barracuda`, `proofpoint`, `sophos`, `microsoft`, `google`), or the raw MX hostname for `OTHER`, or empty for `NO_MX` / `UNKNOWN`

**Implementation.** Primary: `dig +short MX <domain>` — preinstalled in the sandbox; parse the lowest-priority exchange. Fallback only if dig is absent: `dnspython` (`pip install dnspython --break-system-packages` — note pip's network is blocked in some sandboxes, which is why dig is primary). Resolve once per firm domain, not once per contact — cache results within the run. Skip lookup if the row already has an `MX Status` other than `UNKNOWN`; on continue-path re-runs, `UNKNOWN` rows are always re-checked. On DNS timeout (3s default), retry once; on second timeout mark `UNKNOWN` (never `NO_MX` — a timeout is not evidence the domain has no MX) and log to the run notes.

**Output.** Append two columns to the master if not already present (`MX Status`, `MX Provider`). Both are skill-managed — never user-edited. They survive across runs and are re-checked at Stage 11.5 against the actual email domain (see Step C.5).

**Gateway exclusion is a hard default, not a recommendation (enforced at Stage 10 Step 1).** Rows classified `GATEWAY` are split out of the paid set before enrichment unless the user explicitly opts to include them at Stage 9. Classifying gateways but still enriching them spends credits on contacts that will not be mailed. The Stage 8 and Stage 9 text remains the user-facing summary; the actual drop happens in code at Stage 10 Step 1.

**Stage 8 surfacing.** Add the MX-mix line to the run summary — and, if any firms are gateway-protected, the gateway recommendation. Both verbatim blocks live at Stage 9, where they sit at the moment of spend; reuse them here word for word.

### Stage 5 — Rank (FREE)

Title score: Managing Partner/Founder/CEO/Owner = 10, Chairman = 9, MD = 8, Partner = 7, Head of/Director = 6, Other = 4.

Note: ranking applies **within the applicable tier (strict, or strict+softer for sub-50 firms)**. Stage 4 two-tier enforcement has already dropped anyone outside it. Ranking is for sorting the survivors, not for second-chancing rejected adjacent titles. Softer-tier titles typically score 6 ("Head of/Director" tier) or below.

**Hybrid titles**: take MAX score across all matching tokens.
- "Founder & CEO" → max(10, 10) = 10
- "Director & IFA" → max(6, 4) = 6 (assumes Director was on Q5 allow-list; otherwise the contact never reached this stage)
- "Managing Partner & Head of Origination" → max(10, 6) = 10

Tenure tiebreaker: 3+ years at firm = +1 (applied in Stage 11 with real `current_tenure_years` from the enrichment output, not pre-paid).

Sort descending. Highlight top N.

### Stage 6 — Sanity check (runs before Stage 7 build AND after Stage 11 final)

Three layers, all hard-fail.

**Layer 1 — Format integrity (every run):**
- Headers match 19-col spec exactly
- Calibri 11 black on every cell, blue underlined Calibri 11 on hyperlinks
- All rows 15pt locked. Background col `wrap_text = FALSE`.
- Per-column alignment per spec
- Headers: white bold on navy, frozen, centered
- Alternating grey/white by firm; orange for flagged rows
- Phones in international format (+xx prefix)
- No bright yellow
- Hyperlink XML verification: unzip the saved .xlsx, count `<hyperlink ` entries in `xl/worksheets/sheet1.xml`. Must equal expected.
- Workbook custom property `run_constraint` is set (empty string is acceptable if Q7 was left blank).

**Layer 2 — Drop rules (every run):**
- No-email rows DROPPED to Filtered Out
- Wrong-firm matches DROPPED with reason "Contact moved to [new firm]"
- Ghost rows DROPPED (Contact Name blank AND Email lacks "@")
- Title-not-on-Q5-allow-list rows DROPPED with reason "Title not on Q5 allow-list (firm size [N], tier checked: [strict/softer]): [actual title]"
- Semantic-mismatch firm rows DROPPED with reason "Semantic mismatch: [one-liner]"
- User-constraint rows DROPPED with reason "User constraint: [verbatim Q7]"

**Layer 3 — Completeness (HARD FAIL — runs ONLY after Stage 11 final):**
For every contact in Latest Run, these MUST be populated:
- **Email** — drop to Filtered Out if paid enrichment found no email
- **LinkedIn URL** — paid enrichment first; if absent, Stage 11.5 web-research backfill via `"<First> <Last>" <Firm> site:linkedin.com`. Treat as equally important as email. **Escape hatch (defined, so this can never deadlock a delivery):** if the backfill search also finds nothing, write "Not found" to the cell, orange-flag the row, and note it as a soft warning in the run summary — LinkedIn absence alone never blocks the file. Email remains the only completeness hard-drop.
- **First Name + Last Name** — required for Instantly merge tags
- **Title** — required to assess fit; must still be on the applicable tier (strict, or softer if `estimated_num_employees < 50` post-enrichment)
- **Company website hyperlink** on col B
- **Employees** — actual integer from paid enrichment, not search-band placeholder

A failed completeness check is a SKILL bug. Backfill quietly, re-run sanity. Never present a file with blank Email or LinkedIn cells (final file only — the Stage 7 review file legitimately has them).

**Soft warnings (flag, don't fail):**
- Company Phone — if paid enrichment returned none, web-search switchboard. Acceptable to deliver without after 2 retries.
- Headcount Trend — "Unknown" acceptable AFTER Apollo growth has been read (and Companies House delta attempted only if a key is present).
- Revenue Band verified vs estimated.

**Notes/User Notes split:**
- Notes column (col J): skill writes data-quality flags only (e.g. `catchall`). Never user actions.
- User Notes column (col Q): never written by skill, ever.
- Status column (col N) carries outreach state, not colour.
- First time `catchall` appears in a run, define it in run summary: "Domain accepts mail to any address; verifier confirms email won't bounce but cannot confirm inbox is monitored. Lower send volume."

### Stage 7 — Build review Excel (BEFORE credit confirmation)

Build the master file with every column populated except Email. Append new rows to existing master. Set workbook custom properties per the metadata spec in `references/format-spec.md`. Use xlsxwriter (Principle 3). Run sanity check Layers 1-2. Wait time: ~1 min.

### Stage 8 — Present file (forced view step)

**Dashboard-first review (best-effort, non-fatal — the brain-setup lesson applied at the decision moment).** Before printing the template below, if `dashboard_enabled` is true, run Stage 13 steps 2–4 against the REVIEW workbook built at Stage 7 (same builder, same read-only + swallow-all-failures rules; Email cells are simply blank at this point and render as empty). Same `artifact_id` as Stage 13, so the post-enrichment run updates this artefact in place rather than creating a second one. If it publishes, open the review with one line — "Review your list in the dashboard above; summary below." — then print the full text template regardless (it is the fallback and the audit trail). A dashboard failure here changes nothing: text template alone, no error shown.

**Template:**
> "Review file ready: [Prospects_[Niche]_MASTER.xlsx](computer://path)
>
> [N] new contacts at [M] firms (Latest Run tab = just this run). Email column blank, fills on enrichment.
>
> **Active constraint:** [verbatim Q7 text, or "None set" if empty]
>
> **Sources used:** [list directories actually scraped] + Apollo company search. If you'd prefer different sources next run, say so.
>
> **Filter casualties:** [X] firms dropped on semantic mismatch, [Y] dropped on user constraint, [Z] contacts dropped on title (not on Q5 allow-list). Full reasons in Filtered Out tab.
>
> **Three things to sense-check before you confirm credits:**
> 1. **Integration flags** — [X] firms have ownership changes flagged in Background.
> 2. **Orange-flagged rows** — [Y] contacts where Apollo title score is below 6 OR firm fit is questionable.
> 3. **Single-contact firms** — [Z] of [M] firms returned only 1 senior contact on the Q5 allow-list."

If any category has zero items, omit that bullet. If Q7 was blank, omit the "Active constraint" line entirely.

### Stage 9 — Credit-spend confirmation (no skip)

Pre-flight credit check. If `num_credits_remaining < N`, modify question to "Enrich top [balance] only / Save without enriching / Cancel".

**No API key step.** Enrichment runs through the connected Apollo app; there is nothing to paste. If the Apollo connector is not connected, do not show this gate at all — instead deliver the research-only company shortlist (Stage 0 Step 1) and tell the user to connect Apollo to reveal verified emails.

Standard question: "Confirm Apollo request: ~[N] credits (roughly $[X], check with Apollo for exact cost)". Per-credit cost (refresh quarterly via Apollo docs): Basic ~$0.026, Professional ~$0.025.

**Echo the Stage 4.6 MX mix inside this prompt**, on its own line right under the credits/dollar estimate, so the deliverability shape of the batch is visible at the literal moment of spend decision:
> **Email-provider mix in this batch:** [GW]% behind strict corporate filters ([N] firms) | [M365]% Microsoft 365 | [G]% Google | [O]% other | [NX]% no mail server found

(Plain English at the spend moment: never show the user the raw terms "MX" or "gateway".)

If any firms are gateway-protected, append:
> **Recommendation: drop the [N] firms behind strict corporate filters before send.** Cold email rarely reaches them — those filters judge content and sender reputation, not sending speed, so a slower cadence does not rescue them. Enriching addresses you will not actually mail wastes credits. Use LinkedIn / referrals / phone for those firms instead.

Combined with the "Skip flagged firms" option below, this gives the user a clean exit before credits go.

**Four options (gateway-aware):**
1. **Enrich sendable only, skip [G] gateway firms (Recommended)** — enriches [N-G] non-gateway contacts, ~[N-G] credits, balance after: [X-(N-G)]. Default: gateway domains are poor cold-email targets and enriching them wastes credits.
2. **Skip gateways and flagged firms, enrich [N-G-Y]** — also drops [Y] contacts at firms with integration or orange-flag triggers from Stage 8. Available only if any flagged contacts exist.
3. **Enrich everything incl. [G] gateways, [N]** — only if the user explicitly wants the gateway slice (e.g. a LinkedIn or phone export, not cold email). ~[N] credits.
4. **Save without enriching** — file kept as-is, no credit spend.

### Stage 10 — Apollo enrichment (CREDITS, ON CONFIRM ONLY)

**Mechanic.** Call the `apollo_people_bulk_match` connector tool directly (no script, no bash, no key), passing a `details` array of up to 10 contacts per call. The response is large and auto-saves to a file; the tool returns a message containing that file path instead of streaming the payload into context. Read ONLY that file with `jq`, extract the trimmed fields (Step 2) into a cumulative `${MASTER_DIR}/.enrichment_output.jsonl`, and never let the raw payload enter the conversation. Loop in batches for larger lists.

**Always match by Apollo person ID.** `apollo_people_bulk_match` matched by the person ID captured at Stage 4 returns ~95% hit rate and works on every plan including Free. Same credit cost (1 per match, 0 on misses). Matching by name+org+domain is the weak fallback only (Free/Basic mask surnames, breaking the name heuristic); person ID is a primary-key lookup that bypasses it.

**Mapping batch results back to inputs.** The response has a `matches` array. Each match carries its `id` (Apollo person ID); map back to your input by that ID (most reliable), else by `(first_name + organization_name)`. Carry the ID through as `input_id` in the trimmed JSONL so Stage 11 is order-independent.

**Credentials: none.** There is no API key and no `.env`. Enrichment authenticates through the connected Apollo app (OAuth) — the same connection used for search. If `apollo_people_bulk_match` returns an auth/connection error, the Apollo app simply is not connected: fall back to the research-only shortlist (Stage 0 Step 1) rather than asking for a key.

**Step 1: build the batch `details` arrays.** Group the approved contacts into batches of ≤10. Each `details` entry: `{"id": "<apollo_person_id>", "first_name": "<x>", "organization_name": "<firm>", "domain": "<domain>"}`. `id` (captured at Stage 4) is the primary key; the name/org/domain fields are the fallback. `domain` is the canonical primary domain from the free org search.

**Hard gateway rule:** do NOT include any contact whose `MX Status` is `GATEWAY` in the `details` arrays, unless the user chose Stage 9 option 3. This enforces the Stage 4.6 split, so no credit is ever spent on a gateway domain. Assert the total queued count equals the non-gateway approved count before the first call.

**Step 2: call the connector per batch, then jq the dumped file.** For each batch call `apollo_people_bulk_match` with that batch's `details` and `reveal_personal_emails: false` (cold B2B wants the work email, returned by default). The tool reports a saved-result file path. Immediately extract the trimmed fields from it and append to `${MASTER_DIR}/.enrichment_output.jsonl`:
```
jq -c '.matches[] | {input_id: .id, matched: (.email != null),
  person: {id, first_name, last_name, name, email, email_status,
           email_domain_catchall, linkedin_url, title, headline,
           city, state, country},
  organization: {id: .organization.id, name: .organization.name,
           domain: .organization.primary_domain,
           estimated_num_employees: .organization.estimated_num_employees,
           six_month_growth: .organization.organization_headcount_six_month_growth,
           one_year_growth: .organization.organization_headcount_twelve_month_growth,
           two_year_growth: .organization.organization_headcount_twenty_four_month_growth,
           primary_phone_sanitized: .organization.sanitized_phone,
           organization_revenue: .organization.organization_revenue,
           owned_by_organization: .organization.owned_by_organization}}' "<saved_file_path>" >> "${MASTER_DIR}/.enrichment_output.jsonl"
```
Append after each batch so partial state survives interruption. Typical: 50 contacts ≈ 5 calls, 250 ≈ 25 calls.

**Step 3: read the output for Stage 11.** Stage 11 reads `${MASTER_DIR}/.enrichment_output.jsonl` as the source of truth. The raw Apollo payload files are never read again and never enter context.

**Output schema (per line, on success) — exactly what the Step 2 jq emits:**
```
{
  "input_id": "<apollo_person_id>",
  "matched": true,
  "person": {
    "id": "...", "first_name": "...", "last_name": "...", "name": "...",
    "email": "...", "email_status": "verified|catch_all|...",
    "email_domain_catchall": true|false|null,
    "linkedin_url": "https://linkedin.com/in/...",
    "title": "...", "headline": "...",
    "city": "...", "state": "...", "country": "..."
  },
  "organization": {
    "id": "...", "name": "...", "domain": "...",
    "estimated_num_employees": 42,
    "six_month_growth": 0.05, "one_year_growth": 0.12, "two_year_growth": 0.25,
    "primary_phone_sanitized": "+44...",
    "organization_revenue": 4290000,
    "owned_by_organization": "ParentCo Ltd" | null
  }
}
```
(`current_tenure_years` is not emitted by default; Stage 11's tenure tiebreaker simply skips when it is absent. Derive it from the match's `employment_history` current entry only if needed.)

On failure:
```
{"input_id": "...", "matched": false, "error": "no match | auth error | http 422: credits exhausted | ..."}
```

**Pipe ALL of the above into the master file at Stage 11.** Paid response is the source of truth — never read org fields from free-search after this point.

**Retry / error behaviour (connector):**
- Nickname expansion (Jonny→Jonathan, Tom→Thomas, Mike→Michael, etc.): only relevant on the name-fallback path (no person ID). If an ID-less contact misses and its first_name is a known nickname, re-call that batch once with the expanded name. Contacts matched by person ID never need this.
- Transient failures / rate limit: if a batch call errors transiently, retry that batch up to 3x with backoff (1s, 3s, 9s).
- Credit exhaustion: if a call reports credits exhausted, stop, keep the `.enrichment_output.jsonl` written so far, and surface: "[N] enriched before Apollo credits ran out — top up and re-run on the remainder."
- Auth / not-connected error: no retry. The Apollo app is not connected — stop the paid step and deliver the research-only shortlist (Stage 0 Step 1).

**Skill-level checks at Stage 11 (against the output JSONL):**
- Wrong-firm: if `organization.name` ≠ input firm name → drop to Filtered Out (contact moved).
- Title-still-valid: if `person.title` no longer on applicable tier → drop to Filtered Out.

### Stage 11 — Final master update + re-rank

**Before doing anything here, run the Principle 4 append-only guard**: capture `pre_total` before any in-memory rebuild, assert `new_total >= pre_total` after, abort without touching the live file on failure. Full rule and rationale under Principle 4.

**Step A — Read the enrichment output JSONL:** open `${MASTER_DIR}/.enrichment_output.jsonl`. For each line:
- If `matched=false`: log to Filtered Out with reason "Enrichment miss: [error]". Do not populate any fields.
- If `matched=true`:
  - populate Email from `person.email`,
  - replace obfuscated Last Name with `person.last_name`,
  - rebuild Contact Name from `person.first_name + person.last_name`, drop the `[Apollo: Xx***x]` placeholder,
  - overwrite Employees from `organization.estimated_num_employees` (actual integer, replaces the search-band placeholder),
  - overwrite Headcount Trend from `organization.{six_month,one_year,two_year}_growth` (use the same priority rule as Stage 4.5C: only non-null AND non-zero are authoritative),
  - overwrite Company Phone from `organization.primary_phone_sanitized`,
  - overwrite person LinkedIn (col H) from `person.linkedin_url`,
  - write `catchall` to Notes (col J) if `person.email_domain_catchall` is true.

**Step B — Re-rank against the brief:**
- If `organization.estimated_num_employees` falls outside user's headcount band → orange-flag with reason "enriched headcount [N] outside [band]" (do not drop).
- If `current_tenure_years >= 3` → +1 to title score.
- If `current_tenure_years < 1` → orange-flag with reason "<1 year at firm — verify decision authority".
- If `person.headline` contains "Retired" or similar → orange-flag.
- If `organization.owned_by_organization` is non-null and not on a known-good parent list → orange-flag for review (parent-ownership often only surfaces in the paid response).
- Re-sort the master tab by new title score.

**Step C — Backfill missing person LinkedIn (Stage 11.5):** for any contact where paid enrichment returned no `linkedin_url`, run web search `"<First> <Last>" <Firm> site:linkedin.com` once. Free.

**Step C.5 — MX recheck on actual email domain (Stage 11.5):** Apollo's verified email may live on a different domain than the firm's website (group domains, brand consolidation, post-acquisition email migration). For every enriched contact, parse the domain from `person.email` and compare to the firm domain used at Stage 4.6. If different, re-run the Stage 4.6 MX classification against the email domain and overwrite `MX Status` + `MX Provider` for that row. The email-domain MX is the operational truth for what happens when you actually press send — the website-domain MX from Stage 4.6 is a useful pre-enrichment heuristic but can drift from reality. Free.

**Step D — Re-run sanity check (Stage 6 all three layers).**

### Stage 12 — Master file rules

**Dedupe key:** `domain` (lowercased, stripped) + `first_name` (lowercased). Domain over Company name (handles rebrands). first_name over full Contact Name (handles pre-paid obfuscation matching post-paid resolved names).

For multi-contact firms where two contacts share a first_name (rare), append last_name when available, else use Apollo person ID.

Never overwrite existing rows. User-added columns preserved. Required columns must be present (abort with clear error if any renamed/deleted by user).

**Re-enrich trigger:** scan master for rows where Status = Cold AND Run Date > 6 months. Flag in run summary, offer paid re-enrich (with confirmation per Principle 1). LinkedIn URLs go stale — worth running quarterly even on Sent/Replied rows.

### Stage 13 — Build + publish the Bingley cold-list dashboard (BEST-EFFORT, NON-FATAL, RUNS BEFORE THE CLOSE)

Runs after Stage 12 and **before the Final presentation close**, so the artefact is on screen as the headline deliverable at the moment the close points at it. It is still best-effort: it MUST NEVER block, delay, alter, or fail the run. The Excel written at Stage 11 and the `computer://` link in the close are the guaranteed deliverable; this stage only ever **reads** the finished file. It sets ONE flag the close reads: `dashboard_published`, true only if step 4 publishes without error, false on any skip or failure.

Treat the entire stage as wrapped in one try/except whose except branch is "set `dashboard_published = false` and carry on, the Excel is already the guaranteed deliverable."

1. **Gate.** If `dashboard_enabled` is false (no artifact publish/update tool in this environment), steps 2–3 still run and step 4 uses its no-tool fallback. Only if the render itself is impossible, set `dashboard_published = false` and SKIP SILENTLY. No message, no error.
2. **Precondition.** Confirm the final `Prospects_[Niche]_MASTER.xlsx` exists and is readable. If not, set `dashboard_published = false` and SKIP.
3. **Render (read-only).** Run the bundled builder, which opens the workbook READ-ONLY (it never writes the xlsx) and emits a self-contained HTML file:
   ```
   python3 "<SKILL_DIR>/scripts/build_coldlist_dashboard.py" "<final master.xlsx path>" "<scratch>/coldlist_dashboard.html" "<final master.xlsx path>"
   ```
   It prints one JSON line, e.g. `{"ok":true,"artifact_id":"cold-list-<niche>-<geo>","rows":N,"dl_mode":"embed",...}`. If `ok` is false or the script errors, set `dashboard_published = false` and SKIP SILENTLY.
4. **Publish (one dashboard, updated in place).** Use whatever artifact publish/update tool this environment offers to publish `<scratch>/coldlist_dashboard.html`. The rule is intent, not tool names: ONE dashboard per niche+geography, republished in place on every later run so the same page updates rather than a second one appearing — key the republish on whatever identity the tool uses (same file path, same URL, or the printed `artifact_id`). If the tool can grant the page a file-handover mechanism for the Download Excel button (e.g. a `present_files` allowlist), grant it; where it can't, the button falls back to a normal browser download when the HTML is opened outside the artifact sandbox (the builder's 3rd arg embeds the master path for this). **No-tool fallback:** if no artifact publish tool exists at all, save the HTML beside the master, present that single file, and leave `dashboard_published = false` so the close leads with the Excel link. On a successful publish, set `dashboard_published = true`.
5. **On ANY failure of 1–4** (artifact API error/unavailable, oversized embed, parse error, anything): set `dashboard_published = false` and SWALLOW IT. Do not retry beyond one attempt. Do not ask the user anything. The close will simply lead with the file link instead.

**Invariants this stage preserves (do not violate):**
- The builder has **no write path** on the xlsx — it opens read-only and reads bytes only. Principle 3 (hyperlinks) and Principle 4 (append-only) are untouched; both completed at Stage 11 *before* this stage runs. The skill's Excel output is byte-for-byte unchanged.
- **One artifact per niche+geography** — `artifact_id` mirrors the master filename rule (`spaces→_`, strip punctuation) plus a `-<geo>` suffix when `run_geography` is set, then **lowercased**. (The builder emits a lowercase id so re-publishes always key on an identical, stable identity; the filename keeps its case — only the artifact id is lowercased.) So re-runs update in place and different niches/geographies never collide or clobber.
- The xlsx behind **Download Excel** is the byte-identical final master, read from disk. Lists too large to embed (raw xlsx > 2.5 MB) fall back to the on-disk file link and the dashboard says so. Tables over 2,500 rows render the first 2,500 with a "filter or download for all" note (search/filter still run over the full list).
- The dashboard reads the **final, post-enrichment** workbook (after Stage 11), so the view and the download always match the delivered Excel, including the real LinkedIn-profile and company-website hyperlinks stored in columns H and B.


---

### Final presentation (the close — runs LAST, after Stage 13 has tried to publish)

Brief stats: total firms surveyed, retained after operator filter, semantic-match drops, user-constraint drops, title-enforcement drops, top N enriched, source breakdown, credits spent this session.

End with **one** of the following, chosen on `dashboard_published` (the ACTUAL outcome of Stage 13, never on `dashboard_enabled`):
- If `dashboard_published` is true: "Ready for outreach. Your list is in the **Bingley cold-list dashboard** above, hit **Download Excel** there for the file. (If the dashboard doesn't load, the file is here: [Prospects_[Niche]_MASTER.xlsx](computer://path).)"
- If `dashboard_published` is false: "Ready for outreach. File is in your Instantly-compatible format with First Name, Last Name, Email, Company as separate columns." plus the [Prospects_[Niche]_MASTER.xlsx](computer://path) link.

The `computer://` file link is the guaranteed handover and is NEVER removed; it is the fallback whenever the dashboard is absent or fails to render. NEVER tell the user the dashboard is "above" unless `dashboard_published` is true.


## Version stamp + update check (house rule)

1. **Stamp.** The close-out of every run states this skill's name and version, read from the `version:` frontmatter at the top of this file (e.g. "list-builder-apollo v1.0.0").
2. **Update check — best-effort, never blocking, at most once per conversation.** After the deliverable is produced, if web access is available in the session, fetch <https://raw.githubusercontent.com/bingley-ai/bingley-skills/main/plugins/list-builder-apollo/.claude-plugin/plugin.json> (give it ~5 seconds, then move on) and compare its `version` field to this file's `version:`. If they differ AND no update line has already appeared earlier in this conversation (from this or any sibling skill), append exactly one line to the close-out: "A newer version of this skill is out — get the update at bingley.ai." On later runs in the same conversation, skip the line even if versions still differ. If the fetch fails, times out, or the session has no web access: append nothing and never mention the check. The deliverable is never delayed or blocked by this step.
