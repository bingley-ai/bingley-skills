---
name: sales-control-panel
description: Build the user's Sales Control Panel from their deals file. Reads any sales export (arbitrary headers, xlsx or csv), confronts whatever is wrong with it, and renders the Desk (what to do in the next hour) plus their book of business (how they are tracking, and whether they can trust it). Use when the user asks to set up, install, build or refresh their Sales Control Panel, drops a deals file and asks what is in it, or — with a deals file around — asks things like "is my pipeline ok", "what should I work on next" or "what's my forecast". Also use when someone has no deals data yet and wants to see it run on demo, sample or example data.
version: 1.1.1
---

If a `LOCAL.md` file sits beside this SKILL.md, read it and let it win over anything here — with one carve-out: the rating strip and licence/attribution notices always stay, whatever a LOCAL.md says.

**Engine dependency:** this skill's deterministic engines run via the bash tool with `python3`. If the session has neither, say so plainly in one line and do only what works without them — never improvise an engine's numbers or renders by hand.

# Sales Control Panel

A daily operating system, not a dashboard. Every surface answers "what do I do next?" or "can I trust this?" — never just reports state.

**The engine does the work, you do the conversation.** `scripts/build_panel.py` ingests the file, computes every figure, decides what is unsafe to show, and renders the HTML. You never hand-write the panel, never compute a figure yourself, and never write numbers into the HTML. Your job is: find the file, run the engine, read what it flagged, ask the user those questions in plain English, write their answers to the sidecar, rebuild.

## The one rule everything else serves

**Never a confident silent number.** On first contact this engine got three real salespeople catastrophically wrong — a pipeline 28x too small, "all caught up" over 26 unread tenders, £0 published as fact — and every single failure was a confidently rendered figure that happened to be wrong. So:

- A figure an unanswered blocker affects renders **"unconfirmed"**. Never a number, never £0, never a guess.
- Money with no date is disclosed as its own figure, never placed in a month.
- A rate, an assumption, a skipped row, a fuzzy stage guess: all disclosed, all in Data health.
- If the data cannot prove it, the panel does not say it.

This is the product. If you find yourself tempted to fill a gap to make the panel look better, stop: the honest blocked state IS the feature.

## Run it

```bash
python3 scripts/build_panel.py --deals <file> --name <FirstName> --today <YYYY-MM-DD> \
  --out panel.html --report ingest-report.md --summary-json summary.json --issues-json issues.json \
  [--sheet <name>] [--overrides overrides.json] [--horizon month|quarter|Ndays] \
  [--meetings <file>] [--commitments <file>] [--prep <file>]
```

The engine needs `python3` with `pandas` + `openpyxl` — present in Cowork's sandbox; on any other install, install them first.

- `--deals` is required and takes **any** xlsx/csv with **arbitrary headers**. Do not clean, reshape or re-header the user's file first. The engine maps casual headers ("Where it's at", "Last spoke", "Ref"), strips summary/total/junk rows, detects date order from evidence, handles mixed currency, line items, fiscal quarters and multi-sheet workbooks. Reshaping it yourself destroys the evidence it uses.
- `--today` must come from `env`, never hardcoded.
- `--overrides` is the user's answers (below). `--no-state` disables the run-to-run diff (tests only).
- Outputs: the panel HTML, an ingest report (every decision, in prose), `summary.json` (every figure), `issues.json` (everything that needs a human).
- The engine also keeps `<deals-file>.scp-state.json` beside the user's deals file — its own run-to-run state. Never present it, delete it, or "clean it up".
- **⛔ Of those four, the user gets ONE: `panel.html`.** (Added 21 Aug 2026.) `ingest-report.md`, `summary.json`, `issues.json` and the hidden run-state file are the engine explaining itself to YOU — never `present_files` them, never show the user their JSON, never link them. Presenting the engine's working notes alongside the panel is how a finished run comes to look like a debug dump.

**Read `ingest-report.md` after every run.** It is the engine explaining itself. If you are about to tell the user something about their data, it came from there or from `summary.json`, not from your own reading of the file.

## Demo mode (they have no data yet)

If the user has no deals file, or asks to see it run on demo, sample or example data, do not
hunt for a file and do not seed anything by hand. Run the generator that ships with this skill:

```bash
python3 scripts/make_demo_data.py --out <the user's folder>
```

It writes `SAMPLE-deals.xlsx`, `SAMPLE-meetings.xlsx` and `SAMPLE-commitments.xlsx`, every date
computed from today, so the demo reads as live whenever it is run and never needs re-cutting.
Then build from all three exactly as you would from real files, passing `--meetings` and
`--commitments` as well as `--deals`. Loop step 3 onwards is unchanged; the demo data raises no
blockers, so the panel builds in one pass.

When you hand a demo panel over, say two things and stop: these are sample figures rather than
theirs, and to run it on their own numbers they point the skill at any CRM export. Leave the
`SAMPLE-` files where they are, they are the user's to keep or bin.

**This is not a hole in "do not mock, seed or demo-fill" below.** That rule forbids the panel
inventing content inside a build from someone's real pipeline. Demo mode writes a real, plainly
labelled sample file and the engine ingests it as honestly as it ingests any export, every figure
computed, nothing fabricated at render time. The two never mix: if a real deals file is present,
never top it up with demo rows.

## The two surfaces

**Desk (default tab) — the next hour.** Hero (greeting, chips, issues chip), Today's plan (ranked, seeded from overdue commitments + top stale + closing-stage deals), Today's meetings, Pipeline headline + stage bars, At-risk + top-5 stale. Fixed stage, never scrolls, capped lists always disclose their tail.

**Your book of business (tab 2) — how am I tracking, can I trust it.** Trust strip, then five sections: Target and gap to target · Data health · Pipeline in full · Deals going cold · Commitments tracker. This is the one surface allowed to scroll. It is a second **view** of one truth, never a second **calculation** of it: every figure is the same object the Desk renders.

**Fix my data (takeover from the issues chip).** One question at a time, ranked by money at stake, with live payoff and a copyable answer block.

Scope note (16 Jul): cash runway, a renewals section, a forecast-category section and a currency section were all built and then **cut**. Ship the minimum, let users pull the rest. Do not re-add them without being asked.

## The loop you actually run

1. **Find the file.** Ask where their deals data is if it is not obvious. One question, one `AskUserQuestion` call. If they have not got one, go to Demo mode above rather than leaving them stuck.
2. **Run the engine.** Cold, no overrides, first pass. If it exits non-zero, read the error and tell the user in plain English what is wrong with their file (missing, unreadable, not a real xlsx/csv, a legacy `.xls` that needs re-saving as `.xlsx`). Do not retry by cleaning or altering their file — rule 4 below forbids it.
3. **Read `issues.json`.** Blockers first, then warnings, then FYIs.
4. **Ask the blockers conversationally.** Each issue carries `question`, `choices`, `saw` and `csv_lines` already written in plain English. Ask them as they are. Never show the user JSON, never ask them to edit a file, never invent a question the engine did not raise.
5. **Write their answers to `overrides.json`** and rebuild. The figures un-grey.
6. **Hand over `panel.html`, then report in one short line.** `present_files` the panel so the user can actually open it — this is the deliverable, and until 21 Aug 2026 this file said nothing about how it reached them, which left it to chance. Presenting it is explicit and required; presenting anything else the engine wrote is forbidden (above). On a host with no `present_files` tool, give the user the path to `panel.html` and tell them to open it in a browser. Then one line: what loaded, what is still unconfirmed.

Blockers are first-run only. Warnings batch. FYIs never interrupt.

### overrides.json — the user's answers, never your assumptions

Only ever write a key the engine asked for. Each issue names its own `override_key` and, where the answer is a fixed choice, carries `choices_values` (the machine value) parallel to `choices` (what the user sees). `emit: "stage_map"` nests under `stage_map` keyed by the raw stage word.

```json
{
  "target": {"amount": 150000, "period": "quarter"},
  "stage_map": {"Tender Submitted": "Proposal", "Parked": "parked"},
  "dedupe_policy": "keep-first",
  "forecast_category": {"column": "ForecastCategory", "mode": "show"},
  "fx": {"EUR": 0.86},
  "horizon": "quarter",
  "sheets": ["Deals"],
  "value_semantics": {...}, "fee_derivation": {...}, "fiscal_year_start": 4
}
```

`target` is never invented — the panel shows "Set your target →" until the user gives a number. Same principle everywhere: the engine asks, it does not assume.

## What you must not do

1. **Do not hand-write the panel HTML.** It is `panel-shell.html` + `render.js.html` + `modal.css.html`, rendered by the engine. Editing the output by hand breaks the next rebuild.
2. **Do not compute a figure.** Every number the user sees comes from the engine. If you need one, read `summary.json`.
3. **Do not mock, seed or demo-fill.** Earlier versions of this skill shipped mock meetings, mock call summaries and mock emails behind a "Demo data" tag. That is gone, and it is not coming back: a panel that invents plausible content is the exact failure this engine exists to prevent. An empty section says it is empty and says what would fill it. (Demo mode above is the one sanctioned route to sample figures, and it works by writing a labelled sample file the engine then reads normally, never by filling gaps at render time.)
4. **Do not clean the user's file first.** See above.
5. **Do not edit `panel-shell.html`.** It is the shared desk shell and is swapped wholesale. Room content and logic live in `render.js.html` / `modal.css.html`. Read `scripts/LAYOUT-CONTRACT.md` before touching any of them.
6. **Do not answer a blocker on the user's behalf**, however obvious it looks.

## House style

- British English. No em dashes as connectors in anything the user reads.
- Money compact everywhere: `£131k`, `£1.3m`, never `£131,000`. Retainers `£6k/mo`.
- Plain sales English in every label. No borrowed startup-finance or RevOps vocabulary. "Gap to target", not "coverage ratio". "Deals going cold", not "stale ledger". If a rep would not say it at their desk, do not put it on the panel.
- Preserve casing from the user's data. "Introduce to FD" stays as written.
- Stale threshold is fixed at 5 days, `>=`. Do not ask.
- Stage defaults: Discovery 20%, Demo 40%, Proposal 60%, Negotiation 80%, Active Retainer 100%, Closed Won 100%, Closed Lost 0%.

## Connectors (optional, additive)

Match by tool suffix, not full name — Cowork MCP server ids are session-random. Use ToolSearch to resolve.

- **Calendar** (`__list_events`) → `--meetings`. Absent: the meetings card says so.
- **Gmail** (`__search_threads`) → commitments from sent mail.
- **Call transcripts** (`__get_transcript`, `__list_meetings`, any of Fathom/Granola/Fireflies/Grain/Circleback) → verbal commitments, call summaries.
- **AI sales brain** — read-only, via `Claude HQ/_lib/brain/brain_bridge.py get --skill sales-setup`. Pre-fills the offer sentence. Never written to, never a blocker, never created.

No connector is required. A deals file alone produces a full Desk plus the whole book of business; the connector-fed cards collapse to one "connect your calendar to unlock" strip rather than rendering hollow.

The engine reads files, never an API — you fetch, write the file, pass the flag:

- `--meetings` (xlsx/csv): attendee (a "Steven Mackay · Mackay's Toys" cell splits itself), plus any of time/start/when, subject/title, context/type/notes, value.
- `--commitments` (xlsx/csv): promise/task/commitment per row, owed_to/prospect/client/who, due_date (or due_offset_days), status — done rows are dropped.
- `--prep` (json): keyed by contact name → `{"company_note", "emails": [{"direction": "sent"|"received", "date", "subject", "body", "link"}], "call": {"source", "summary", "date", "link"}, "points": [{"lead", "rest", "cite", "quote"}]}`. Keys starting `_` are ignored; a point with no `cite` never renders.

## Before you change the engine — MAINTAINER REPO ONLY

**This whole section applies only in the development HQ where this skill is maintained.** An installed copy of this skill does not carry `shippability-test/`, the batteries, or `/skill-test` — if those paths are not beside you, you are running an install: skip this section entirely and do not go looking for them.

Three gates live in `Sales Control Panel/shippability-test/_engine/` and run against **this** skill's engine (there is one engine, no copies):

```bash
python3 battery.py           # 60 ingest fixtures, one failure mode each
python3 battery_book.py      # book of business + v1 scope
NODE_PATH=<jsdom> node ui_test.js <panel.html>   # render contract against the real DOM
python3 persona_regress.py   # 6 personas, headline figures frozen to hand-declared truth
```

All four must be green before anything ships. `persona_regress.py` is the important one: it fails if any headline figure moves. If it fails, you changed money. Prove why before you touch the frozen truths — they are the evidence, not a cache.

Then run `/skill-test` as the launch gate.


**`overrides.json` is plumbing too:** agent-written, engine-read — never `present_files` it; the user changes it by answering the panel's questions, not by opening the file.

**Refresh rules (both mandatory):** (1) Before building, look for an `overrides.json` beside the deals file and pass `--overrides` with it automatically — the user's stage mappings and target must survive every rebuild without being re-asked. (2) Change-tracking state is keyed to the deals file's name: if a `*.scp-state.json` side-car from a DIFFERENT filename sits in the folder, say so plainly — "this looks like a re-export under a new name; history doesn't carry over, keep the filename stable to track changes" — and never silently report "first run".

## Version stamp + update check (house rule)

1. **Stamp.** The close-out of every run states this skill's name and version, read from the `version:` frontmatter at the top of this file (e.g. "sales-control-panel v1.0.0").
2. **Update check — best-effort, never blocking, at most once per conversation.** After the deliverable is produced, if web access is available in the session, fetch <https://raw.githubusercontent.com/bingley-ai/bingley-skills/main/plugins/sales-control-panel/.claude-plugin/plugin.json> (give it ~5 seconds, then move on) and compare its `version` field to this file's `version:`. If they differ AND no update line has already appeared earlier in this conversation (from this or any sibling skill), append exactly one line to the close-out: "A newer version of this skill is out — get the update at bingley.ai." On later runs in the same conversation, skip the line even if versions still differ. If the fetch fails, times out, or the session has no web access: append nothing and never mention the check. The deliverable is never delayed or blocked by this step.
