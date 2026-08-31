---
name: company-researcher
version: 1.0.0
description: |-
  Understand companies, one or four thousand, in the same skill. Researches what they do, why now plus the angle to use, how they make money, size and competitors, and renders every run as one ranked list where each row opens that company's full cheat sheet. Use for "research [company]", "cheat sheet on [company]", "tell me about [company]", "prep me on [company]", "I've a call with [company]", "what do [company] do", AND for whole lists: "grade my prospects", "score / qualify this list", "scan these companies", "go through these 200 companies", or a dropped Excel/CSV or pasted list of names/domains. Deep research per company, so a long list runs long: it estimates the time and confirms first, and never refuses a list for being long. Default is neutral research on free web data; with a business profile loaded it also ranks every company Strong / Fair / Longshot. NEVER calls Apollo, spends credits, enriches contacts or writes the email — list-building and email-writing are separate skills.
---

# Company Researcher

If a `LOCAL.md` file sits beside this SKILL.md, read it and let it win over anything here — with one carve-out: the rating strip and licence/attribution notices always stay, whatever a LOCAL.md says.

**Engine dependency:** this skill's deterministic engines run via the bash tool with `python3`. If the session has neither, say so plainly in one line and do only what works without them — never improvise an engine's numbers or renders by hand.

One job: **understand companies.** One company or four thousand, same skill, same depth, same
research, same card. The only thing that changes with size is how long it takes.

## ⛔ ONE VIEW. NO MODES. NO COUNT GATE.

Every run renders the **same ranked list**: one row per company, click a row to open that
company's full cheat sheet. One company, eight, or four thousand. There is no tabbed view, no
size limit, no "that's too many, go and get the other skill", and nothing for the user to choose.

**This rule exists because the opposite was tried.** An earlier build stopped at 9 companies and
sent the user elsewhere, because a tabbed layout ran out of horizontal room. That was a layout
constraint dressed up as a research constraint, and it produced the worst possible outcome: faced
with a big list, the skill did no work at all. If you ever find yourself about to tell a user
their list is too long, you have misread this file.

- **Never refuse a list for being long.** Long lists get a time estimate and a confirm (below),
  never a refusal.
- **Never render tabs as the entry view.** The list is the entry view, always. The template still
  contains the old tab code for the drill-in; that is internal plumbing, not a mode.
- **N=1 opens straight into the card.** A one-row list is a pointless click, so when there is
  exactly one company the render opens its card immediately and hides the back button. Same
  template, same data, same code path. Not a mode.

## Scope (in / out)

- **Default: neutral research, free web data, zero credits.** Facts, sourced, no judgement.
- **Optional, only with a business profile: fit ranking (Strong / Fair / Longshot) plus the single
  best outreach angle.** No profile means facts only and an unranked list. Never show hollow scores.
- **Always out: Apollo, any paid enrichment, verified-contact lookup, and copywriting (the
  email/DM).** Those live in list-builder-apollo and the Outbound Room. This skill never spends a credit.

## Preflight — ONE ordered sequence, run it in this order

Do these in order, once per run, before any research. Nothing else claims to be first.

1. **Ingest the list.** Take it however it comes: one name, a pasted list of names/domains, or a
   dropped Excel/CSV (auto-detect the company-name / domain column, ignore the rest). Don't force
   a format. This is how it eats list-builder-apollo's Excel output directly. If nothing is given,
   ask in plain words: *"Paste your list of accounts (company names or domains), or drop an
   Excel/CSV and I'll scan it."* **Never call it "the book" to the user**; that's internal
   shorthand. To them it is their list.
2. **Read the brain** — `python3 scripts/brain_bridge.py get --skill company-research --base
   "<wf>/Claude HQ"`. Branch on the `profile` block (see Data access below). If the `get` fails
   for ANY reason, proceed as profile-empty; never stall the run on the brain.
3. **Offer the fit capture if the brain is empty** (see Fit). Once per run, never per company.
4. **Estimate and confirm, but only if the list is big.** Under ~20 companies, skip this entirely
   and just work. At ~20+, load `references/scan-engine.md` and follow it. At ~100+, print the
   computed time estimate and get an explicit confirm before starting.

Then research.

## Data access — the brain bridge (shared Sales OS profile)

This skill reads and writes the user's business profile through the shared **AI sales brain**, the
SAME brain the cold-email builder uses, via `scripts/brain_bridge.py` (deps `brainstore.py` /
`schema.py` / `brain_maps.py` bundled beside it). The business profile is the shared spine
(`business.*` in `sales-os-profile.json`): whatever the user tells ANY Sales OS skill about what
they sell lands there, so a user who filled it in cold-email gets fit ranking on their FIRST run
here, and vice versa. One profile, every skill, one brain.

⛔ **The `--skill` value is `company-research`, NOT `company-researcher`.** That is the shared
brain KEY defined in `brain_maps.py`, and every profile already written to the brain is stored
under it. It looks like a typo. It is not — "fixing" it silently orphans the user's saved profile
and makes the skill act like it has never met them. Leave it exactly as it is.

**Two verbs**, always pass `--skill company-research --base "<the user's working folder>/Claude HQ"`
(the `Claude HQ` subfolder, where the brain lives, NEVER the working-folder root). Each prints JSON.

- **`get`** → `{"profile":{…},"lens":{…}}`, brain-first then schema default, creates nothing.
- **`save key=value …`** → writes to the brain (provenance-stamped). Capture flags
  (`seen`/`deepDone`/`deepSkips`) always apply; `deepSkips=+1` increments.

Install order is irrelevant: any Sales OS skill extends the one brain; the libs are identical and
writes are field-level + file-locked, so they never clobber each other.

## Fit — offered up front when the brain is empty

Fit is scored against the USER's business (`business.product / audience / problem`), never the
target company alone. Deep research is expensive to repeat, so when the brain is empty this skill
offers the one-minute capture **UP FRONT, before researching**, kept skippable in ONE word. Asking
afterwards and re-running to add scores pays for the research twice.

"Profile present" = `product` (ideally also `audience`) holds a real value.

- **Profile present (filled here OR in cold-email).** Rank every company via the rubric, not by
  gut (see Scoring). Set the render DATA `company_profile`, and each company's `bant`, `scoring`
  and `scan`. Print ONE guard line: *"Scoring fit as **[name]**. Different business? Say 'redo'
  and I'll re-tailor."* No questions. **Stale check:** the same `get` returns `"stale": [...]`; if
  it lists `product` or `audience`, extend the guard line once per session with *"…(you confirmed
  this a while back, still right?)"*. A "redo" save needs `--confirmed`.
- **Profile empty — offer the capture UP FRONT.** Ask once, and make skipping one word:
  > Before I dig in: want these ranked by how well they fit YOUR business? Drop your website or one line on what you sell and every company gets a Strong / Fair / Longshot fit, about a minute. Or say **skip** and I'll research unscored.

  - **They give a website/sentence** → run the deep round below, save the profile, THEN research
    and render once, ranked. One pass, no re-run.
  - **They skip / decline / "just research it"** → research unscored (see Unscored rendering
    below; say nothing more about it in chat), then `save seen=true deepSkips=+1`. **Never block
    the research behind the profile.** One gentle re-offer on a LATER run is fine; when
    `deepSkips >= 2` or `deepDone` is true, never offer again.

**Once per run, never per company, never per shard.** Shard workers NEVER read the brain or
re-offer; they only score against the already-loaded `company_profile` handed to them.

**The deep round (the SHARED capture).** Same business-profile capture the cold-email builder
runs, so doing it here fills the one brain for both. (1) **Infer hard first** from the
website/sentence: short `name`, `product`, `audience`, likely `problem`, any `proof`. Never ask
for what you can see. (2) **Read it back and confirm** in one line. (3) If gaps remain, ask them
as ONE multiple-choice elicitation form (reuse the cold-email builder's locked problem/proof/ask
form, options re-clothed from the scrape, never open prose). (4) **Save:**
```bash
python3 scripts/brain_bridge.py save --skill company-research --confirmed --base "<wf>/Claude HQ" \
  name="…" product="…" audience="…" problem="…" proof="…" deepDone=true
```
then render with fit ranked. On skip: save nothing but `save seen=true deepSkips=+1`. The profile
is complete the moment the round is done even if a field was skipped. Never re-ask.

**`--confirmed` is required when the user has explicitly confirmed or corrected a business fact.**
Without it the brain refuses to replace confirmed identity and lists the refused fields in the
save result's `"rejected": [...]`. If that is non-empty after a user-requested change, re-run
with `--confirmed`.

## Procedure — per company

This is what happens for ONE company, whether it is the only company or one of four thousand.
For ~20+, `references/scan-engine.md` wraps these steps in the sharded runner.

**0. Knockout check — ~10 seconds, no searching.** From the name/domain alone, is this an OBVIOUS
hard disqualifier: a direct competitor, a consumer/B2C business with no commercial sales function,
or an entirely wrong buyer category? If yes, skip the full pass: build a minimal card (`name`,
`domain`, a one-line `summary`, and a `scan` object with `verdict:"SKIP"` and a plain-words `why`)
and mark it **`nogo_done`**. If it is not obvious inside ten seconds, do NOT guess: run the full
pass. **`nogo_done` is ONLY for Step-0 knockouts**; a NO-GO reached *after* a full pass is marked
`done` like anything else, so the two stay countable. Skip this step entirely when there is no
profile: with nothing to disqualify against, everything gets the full pass.

⛔ **SIZE IS NEVER A KNOCKOUT.** A company being far bigger than the usual customer is not a
disqualifier here and never has been: `references/bant-rubric.md` handles above-band size with a
Budget cap, so a 96,000-person multinational scores Budget 2, `disqualifier: false`, and still
lands NO-GO through the ordinary gates *after being researched*. Step-0 skipping it on size alone
contradicts the rubric and produces two different answers from the same evidence.

**1. Research the company** with `references/research-framework.md`. WebSearch + WebFetch.
**Decide the fundamentals, don't collect everything.** Capture: **what they do** (one line) →
**why now + the angle to use** (triggers + the play, the payoff) → **how big & growing/shrinking**
(employees + a growth trend ▲/▼) → **money & scale** (revenue; funding only if it exists) →
**competitors** (3-5 + neutral win/lose angle) → **what they likely run** (tools, especially
anything near the user's product) → **location**. Source + confidence flag on every material fact.
⛔ **No people/leadership section** (this is about the company, not names) and **no fabricated
contacts**.

**Last 30 days (neutral intel).** Also gather what's moved in the last ~30 days from FREE sources
(Reddit/HN/news/app store/Trustpilot, scored by engagement; WebSearch quality is fine, no API
keys) and write `last30days`: `momentum` = 2-3 STANDING facts (ARR / subs / profitability);
`signals` = 3-5 DATED events, each carrying **source + date**. Keep it **neutral**: what's
happening, not a pitch. If a fact is already in the momentum strip (e.g. ARR), don't repeat it in
a signal.

**Window rule — be honest, never pad.** Prefer events inside ~30 days. Most private mid-market
companies genuinely have none, and the 3-5 target must NOT be met by inventing or stretching:
widen the lookback to at most ~6 months and DATE-STAMP every signal so its age is visible, or emit
fewer than 3. Fewer real signals beats padding; an empty `signals` is fine once the two recency
searches below have earned it.

**Recency guardrail.** The "why now" / last-30-days dig is where a run most often stops one search
short and wrongly concludes nothing is happening. Run at least TWO recency-focused searches per
company (e.g. `<name> news 2026`, `<name> funding OR launch OR acquisition`). NEVER write "no
recent trigger" or leave `triggers`/`signals` empty unless those searches actually returned
nothing: **absence must be earned, not assumed.** Flag material conflicts rather than silently
picking one figure: put them in a `dimensions` entry titled **"Conflicts & low confidence"**. That
is the channel, there is no other, and in a sharded run the orchestrator reads those at merge.

**2. Fit — OPTIONAL, scored against the USER's business, never the company alone.** Governed by
the brain read in Preflight. Profile present → score with the rubric and set `company_profile`,
`bant`, `scoring` and `scan`. Profile empty → `scan` carries `verdict:"NONE"` and the list renders
unranked (below). Plain research with no profile is facts only, no fit.

**Scoring — use the rubric + scorer, never a gut number.** `references/bant-rubric.md` is the
source of truth. Web-only research can't measure real BANT, so the rubric scores *public proxies*
and weights Need + Timing (observable pre-contact) above Budget + Authority (inferences).

Read the anchors → for each of Budget / Authority / Need / Timing pick the ONE 0-5 level the
evidence meets (level 5 = explicit/dated/named, rare; no evidence = 1-2, not 3+) → set a
`disqualifier` flag for hard knock-outs (competitor, wrong industry/geography, wrong buyer
category — **never size**, which the rubric handles with a Budget cap instead) → run:
```bash
python3 scripts/score_bant.py --levels '{"budget":B,"authority":A,"need":N,"timing":T}' --disqualifier <true|false>
```
It prints `{ "bant": {...}, "scoring": {...} }`. Drop both into the company's DATA verbatim.
**Never hand-set score / tier / decision / grade** — the script owns the maths and the
GO/maybe/NO-GO gates (size alone never buys a GO; it needs a real Need and a reachable buyer).
When asked how a score was reached, cite the four levels and the evidence line behind each.

**Build the `scan` row from that ONE scorer output**, so the row and the drill-in card can never
disagree:
- `scan.score` = `scoring.score` (the /100).
- `scan.verdict` = map `scoring.decision`: **GO → `GO`** (Strong) · **maybe → `MAYBE`** (Fair) ·
  **NO-GO → `SKIP`** (Longshot). Always write the TOKEN; the render shows the label. Never emit a
  bare "skip" to the user: it is a recommendation of fit, not an instruction not to prospect.
- `scan.buyer` = `scoring.buyer_found` **verbatim, a boolean, not a string**. The row renders it
  as "Buyer reachable" / "No clear buyer" itself.
- `scan.why` = one plain line tied to a real signal ("fast-growing, hiring for the role, but no
  buyer visible yet"). Never lead with jargon like "fails the Authority gate". **If you set the
  `disqualifier` flag, `scan.why` MUST say why in plain words** ("sells the same thing we do",
  "consumer brand, no B2B sales function"). The flag is stored nowhere else on the card, so
  without this the /100 is unreproducible from the card.
- **Emit `scan` + `bant` + `scoring` together** for every scored company, never one without the others.

**3. Contacts and enrichment are a separate later layer, NOT this skill.** Free web data only.
Never calls Apollo, never spends a credit.

## Unscored rendering — the list still works with no profile

⛔ **Every company ALWAYS carries a `scan` object**, scored or not. That is what keeps one view.

With no profile, emit `scan: { verdict: "NONE", why: "<one plain line: what they do>" }` and omit
`score` and `buyer`. The list renders a neutral row: no fit bar, no verdict chip, no buyer chip,
and the header reads "Company Research · N companies" with no Strong/Fair/Longshot pills, followed
by the one-line offer to add a profile and rank them.

**Never emit `verdict:"SKIP"` or `score:0` to mean "unscored".** A company nobody has scored is
not a Longshot, and rendering it as one is a lie the user will act on.

## The ledger — archive every run, silently

**Archive at two levels: the run, and each company in it.** For a single company, write only the
`company.researched` line and omit `--of`.

```bash
# only when N > 1
python3 scripts/ledger.py append --base "<wf>/Claude HQ" --skill company-research \
  --kind book.graded --subject "<what the list was>" --ref "<path to the source file, if there was one>" \
  --meta companies=N --meta strong=N --meta fair=N --meta longshot=N

# always, once per company
python3 scripts/ledger.py append --base "<wf>/Claude HQ" --skill company-research \
  --kind company.researched --subject "<Company> (<domain>)" [--of <the book.graded id>] \
  --text "<the cheat sheet in plain text: what they do, why now, how they make money, size, competitors>" \
  --meta domain=<domain> --meta fit="<Strong|Fair|Longshot|unscored>" --meta angle="<the one-line angle>"
```

- **Store the research, not a pointer to it.** The value in six months is "what did we already
  know about these people", and that only works if the words are there.
- **`--of` ties each company back to the run it came from**, so "what did that 300-company scan
  actually conclude" is answerable later without guessing from timestamps.
- **`fit=unscored`** when no business profile is loaded. Never invent a score to fill the field.
- **A prospect's facts stay the prospect's.** This is an archive of work done, NOT a brain write.
  Nothing here ever reaches `sales-os-profile.json`, which is the user's own identity and must
  never be contaminated with a company they merely looked at.
- **A long run archives as it goes**, on the same checkpoint as the resumable state, never one
  write at the end (which loses everything if the run is interrupted).
- **Silent and non-blocking, always.** Never mention it, never show the command, never wait on it.
  `ledger.py` exits 0 on every path by design; if it reports `written:false` (folder not mounted,
  user turned it off), ignore it and carry on. The archive is never a reason a user doesn't get
  their work.
- **It changes nothing about how this skill behaves.** Written here, never read here. It projects
  into no profile, feeds no scoring, alters no output.
- **The user's controls, if they ask:** the archive lives in `Claude HQ/ledger/` in their own
  folder and goes nowhere else; `ledger/.disabled` turns it off; deleting `ledger/` deletes it.
- **⛔ NEVER `present_files` the ledger, the scratch files, or the archive.** (Added 21 Aug 2026.)
  `Claude HQ/ledger/*.jsonl`, `/tmp/research-data.json`, `/tmp/research-instance.html`, the
  `Company Research/<slug>-<date>/` archive and its `versions/` folder are all internal. The host's
  default is "files were written, show them", so silence here ends a research run with download
  cards full of scratch files. The rendered cheat-sheet artefact is the only user-facing output.
  **One exception:** the saved `cheatsheet.html` instance itself IS presented, but only via the
  fallback in Render step 3, when no artifact tool exists and the file is the only way to hand
  over the work.

## Render the artefact (real Bingley desk shell, Pattern A)

The artefact renders **inside the genuine Bingley desk shell**. `assets/cheatsheet-template.html`
is the desk chrome (cloned byte-for-byte from the bundled shell) + research room, with an empty
`room-data` block and a `<!--RESEARCH_TEMPLATE_VERSION:N-->` marker. Shell, data and instance stay
separate, so the shell is interchangeable: swap it, rebuild, content untouched.

⛔ **Never hand-write the HTML.** The only way to build the instance is the render script.

1. Build the `DATA` object (schema below), save to e.g. `/tmp/research-data.json`.
2. Run:
   ```bash
   python3 "<skill dir>/scripts/render_instance.py" \
     --template "<skill dir>/assets/cheatsheet-template.html" \
     --data /tmp/research-data.json \
     --out /tmp/research-instance.html
   ```
   It injects your data into the `room-data` block and copies the desk shell verbatim, printing
   `OK ... shell intact`. If it errors, **fix the data**. Never fall back to hand-built HTML.
   (`<skill dir>` is this skill's folder; resolve it from where SKILL.md lives.)
3. **Publish (fresh view).** **Check the tools exist FIRST**, before the run, not after building
   the HTML: if the session exposes NO artifact publish/update tool of any kind, set
   `artifact_enabled = false` and plan to hand over the file instead. Do not discover this by
   calling a tool that isn't there. Tool names change between hosts, so gate on intent, never on
   a hardcoded name.
   - `artifact_enabled` → publish `/tmp/research-instance.html` with whatever artifact
     publish/update tool the session exposes, and publish so a RE-RUN updates the SAME artefact
     rather than creating a new one (same file path, same id, same URL, whatever that tool keys
     on). The on-screen artefact always shows the CURRENT run, not an accumulating list.
   - If the tool wraps the file in its own `<!doctype>/<html>/<head>/<body>`, publish a stripped
     variant: take everything between `<html …>` and `<body>` (minus the charset and viewport
     metas, which it supplies) plus the body's inner HTML, and give it a real `<title>`. Same
     `room-data`, same shell, same code path. Publishing can still be refused if the session
     cannot show the approval card — that is a hard stop, not something to retry; fall through to
     the file below and say so.
   - no artifact tool at all → re-run the render with `--out` pointing inside the connected working folder (or the session's outputs/scratchpad folder if no folder is connected — NEVER leave it in `/tmp`, which the file-presenting tool cannot reach) and `present_files` that one HTML file.

   ⛔ **When you hand over a FILE, say in the same breath that links only work once it is opened
   in a real browser.** (Added 21 Aug 2026 after this bit a live run.) An embedded preview
   pane sandboxes the page without `allow-popups`, so `target="_blank"` is swallowed in silence:
   no tab, no error, nothing. Template v17 catches that and copies the URL with a toast instead, so
   the click is never dead, but a copied link is a consolation prize and he will read it as broken.
   **This is a change of SURFACE, not a regression in the room** — the same file's links open fine
   from Finder, and fine as an artefact. Name the surface, or the next run gets the same bug report.

   ⛔ **The artefact IS the deliverable.** Never substitute a chat write-up, a markdown file or a
   different render path for it, and never put the research detail in chat instead. A missing tool
   changes the delivery mechanism only, never the output.
4. **Save / archive the run.** Create `Claude HQ/Company Research/<slug>-<YYYY-MM-DD>/` in the
   workspace (slug = company name kebab-cased, `-batch-` for multi-company) and write `data.json`
   (the DATA) + `cheatsheet.html` (the instance). Research persists on disk though the on-screen
   view is fresh.
5. **PDF.** The page has a **Save PDF** button (browser print). A print-only `#pbwrap` (built by JS
   from the same `room-data`, scoped under `#pbwrap` so it can't touch the screen card) renders ONE
   A4 brief per company; print hides the desk shell and shows the briefs. **Fixed structure every
   run:** header (monogram, name, domain, summary, Website/LinkedIn pills; a green/amber/grey fit
   card ONLY if the company carries `scoring`) → vitals strip → two-column body (Why now + Angle /
   Business model / Likely running | Last 30 days / Competitors / Fit signals BANT, BANT only if
   `bant` present) → a **Walk in with** band (relabelled **"Things to weigh"** when
   `scoring.decision == "NO-GO"`) → pinned Sources footer. One colour per section (blue
   Why/Competitors/BANT, violet Last 30, amber band, green/grey grade; unscored shows no fit card
   and no BANT). **Robustness guarantee:** every field is hard-capped and each brief is a
   fixed-height `overflow:hidden` box, so ANY input yields exactly one page, never a broken or
   2-page doc (less info over broken). Two buttons: a drill-in **Save PDF** prints that one
   company's brief; the list-view **Save all PDF** prints the single ranked overview (`#pbScan`),
   not N briefs. Logos are monogram-only (no network needed). Brief source:
   `_build/brief_renderer.py`, applied inline by `build_template.py`'s PB_JS at build time. Never
   hand-edit `#pbwrap`.
6. **In chat:** a short plain summary (per company for a small run, the band counts for a big one)
   plus "opened your cheat sheet →". **Keep the long detail in the artefact, never in chat.**
7. Versioning: copy the live instance → `versions/research-vN.html` + a line in `versions/VERSIONS.md`.

Rebuild the template only via `_build/build_template.py` (development HQ only — installs don't
carry `_build/`; it clones the Bingley desk shell and re-injects the research room). Never hand-edit the chrome. After a shell upgrade, just re-run it.

## Files — what the user sees, and what stays invisible

**Presented** (call `present_files` on these, and only these):
- the saved instance `cheatsheet.html` when the artefact tools are unavailable and the HTML file
  is the only way to hand over the work.

**NEVER `present_files`** — internals, every one of them:
`scripts/*.py` (all of them, including `brain_bridge.py`, `score_bant.py`, `scan_runner.py`,
`ledger.py`), `sales-os-profile.json`, `ledger/*.jsonl`, `run/<run_id>/shard-*.log.jsonl`,
`/tmp/research-data.json`, `/tmp/companies.json`, `data.json`, any shard `--data` card file, and
anything under `evals/`. A finished run shows the artefact. It does not show the plumbing that
built it.

**`evals/` is dev-only and never ships.** `evals/qa_render.py` renders every shape the room must
survive (N=1/3/8/40/500, scored, unscored, thin, unicode, mixed verdicts) and `evals/qa_assert.py`
loads each in a real browser and asserts the entry view, the N=1 auto-open, the unscored row, band
ordering, one-page briefs and zero JS errors. Run them after ANY change to the template or
`_build/build_template.py`. The packager excludes `evals/` at the skill root, so it stays out of
the download.

**Declared shared components** (the manifest; nothing else shared ships here):
`brain_bridge.py`, `brainstore.py`, `schema.py`, `brain_maps.py`, `wcontext.py`, `ledger.py`,
`render_instance.py`, `score_bant.py`, `scan_runner.py`.

## DATA schema (injected into the `room-data` block)

```js
// contents of <script type="application/json" id="room-data">
{
  generated: "2026-08-21",
  run: {},                               // reserved; not shown. This skill spends nothing.
  company_profile: null,                 // the USER's business (what you sell / ICP). Present → ranked; null → unranked list + the add-a-profile offer
  companies: [{                          // ANY number, 1 to ~4000. EVERY company carries `scan` → one ranked list row; row click opens its no-scroll drill-in card. N=1 auto-opens the card.
    name, domain,                        // domain drives the logo (Clearbit → favicon → monogram)
    logo,                                // OPTIONAL data: URI; overrides domain fetch so the logo shows in the network-blocked Cowork panel
    summary: "1-2 plain sentences: what they do",                  // → hero (3-line clamp)
    links: { website, linkedin, maps, x, instagram, tiktok },     // → "Links" brand-icon row INSIDE the hero (real SVG glyphs; rendered only where present; Maps = a google-maps search URL)
    highlights: [ { value:"7M", label:"users" }, ... ],           // → signature-numbers row (2-3 distinctive OPS stats; NOT revenue/employees, those live in Vitals). Keep value + label SHORT (label ≤ ~16 chars); the template WRAPS, it never truncates, so reword rather than relying on a cut-off.
    angle: "the play: why-now turned into a reason to reach out",  // → Angle-to-use box (alias: why_it_matters)
    triggers: [ { trigger, date, source, confidence } ],          // WHY NOW feature
    snapshot: { founded, hq, employees, stage, revenue_estimate, total_funding, latest_round },  // → LEFT Vitals; funding cell only if present; stage is labelled "Type". TERSE: a bare number/amount with any qualifier in ONE short bracket — "£19.7m (FY24 filed)", NEVER a sentence.
    growth: { dir:"up|down|flat", label:"e.g. ARR +51%" },         // ▲/▼ coloured caption under Employees
    ratings: { employer:{score,count,source:"Glassdoor"}, customer:{score,count,source:"Trustpilot|G2"}, google:{score,count,source:"Google|Google Play"} },  // → Reviews bars; any subset; ALWAYS look for a Google rating too
    hooks: [ "smart question to ask in the meeting", ... ],        // → "Walk in with" list (3 best)
    last30days: {                                                  // → "Last 30 Days" (right). Collapsed TEASER card; clicking opens a bottom-RIGHT overlay holding the dated signals.
      updated: "Aug 2026",
      headline: "one strong, neutral line — what's most notable right now",
      oneLine:  "the verdict in one sentence (neutral, not a pitch)",
      momentum: [ { value:"$300M+", label:"ARR · >2× YoY" }, ... ],// 2-3 STANDING facts
      signals:  [ { type:"News|Strategy|Product|Community|Risk", date:"2026", text:"…", source:"Sacra" }, ... ],  // 3-5 DATED events
      take:     { quote:"…", by:"App Store review" },              // OPTIONAL pull-quote
      fullBriefUrl: ""                                             // OPTIONAL link
    },
    competitors: [ { name, note } ],                               // → compact non-interactive list; max 3 shown
    scan: { score, verdict:"GO|MAYBE|SKIP|NONE", buyer:true|false, why },  // ⛔ REQUIRED ON EVERY COMPANY. verdict:"NONE" = unscored (omit score + buyer) → neutral row, no fit bar, no pills.
    bant: { budget, authority, need, timing, tier:"Strong|Fair|Longshot" },  // OPTIONAL; omit when unscored
    scoring: { score, decision:"GO|maybe|NO-GO", grade, tier, reach, buyer_found },  // OPTIONAL; drives the fit card + PDF grade. Omit when unscored → no fit card.
    tech_stack: [ "tool / stack item [confidence]", ... ],         // inside the "More detail" overlay
    dimensions: [ { title, confidence, points: ["sourced point", ...] }, ... ],  // inside the "More detail" overlay
    sources:  [ { label, url } ]                                   // inside the "More detail" overlay
    // NO leadership/people. NO Apollo — free web data only.
  }]
}
```

**Never write a confidence tag, source or date INTO a display value.** `[High]` / `[Med]` /
`(source: X)` belong in the `confidence` key, in `dimensions`, or in `sources`, never inside
`snapshot`, `highlights`, `summary`, `momentum` or `angle`. They are not stripped at render: they
print literally on the card AND in the one-page PDF. A live test produced a Revenue cell reading
"£19.72m turnover, FY ending 31 Dec 2024 [High]". Sourced does not mean annotated in-line.

**Never truncate (on screen).** Every label and value WRAPS rather than clipping in the on-screen
artefact, so author short labels. **Exception by design:** the print BRIEF deliberately hard-caps
fields (with ellipsis) to guarantee a one-page brief. Wrap on screen, cap in the brief.

## Graceful degradation

Thin data → lower confidence, never fake. No profile → unranked list, never hollow scores. No
artifact tools → hand over the HTML path, never a chat write-up. No attached working folder →
skip the brain, ledger and archive silently and still render + hand over the artefact. Always
produce the card with whatever exists.


**Very large books (800+ companies):** the single-page artefact gets heavy at this scale — keep the full ranked list in the artefact, cap inline drill-in briefs to the top ~500, and say in one line that the remaining rows carry the ranked summary only (offer to render any of them in full on request). Never promise a file this skill doesn't produce.

**Person, not a company?** If the name given is a person, say this skill researches companies, and ask which company they're at — never silently treat a person's name as a company.

**Hand-off:** after a single-company cheat sheet, the close-out may add one line — "Want a cold email to them? Say the word — I'll use this research." (cold-email-builder then builds from these facts; never auto-run it.)

## Version stamp + update check (house rule)

1. **Stamp.** The close-out of every run states this skill's name and version, read from the `version:` frontmatter at the top of this file (e.g. "company-researcher v1.0.0").
2. **Update check — best-effort, never blocking, at most once per conversation.** After the deliverable is produced, if web access is available in the session, fetch <https://raw.githubusercontent.com/bingley-ai/bingley-skills/main/plugins/company-researcher/.claude-plugin/plugin.json> (give it ~5 seconds, then move on) and compare its `version` field to this file's `version:`. If they differ AND no update line has already appeared earlier in this conversation (from this or any sibling skill), append exactly one line to the close-out: "A newer version of this skill is out — get the update at bingley.ai." On later runs in the same conversation, skip the line even if versions still differ. If the fetch fails, times out, or the session has no web access: append nothing and never mention the check. The deliverable is never delayed or blocked by this step.
