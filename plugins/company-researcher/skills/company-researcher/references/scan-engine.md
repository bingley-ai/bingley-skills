# The scan engine — parallel fan-out + checkpoint/resume

**Load this file only when the list is ~20 companies or more.** Below that, research serially
and ignore everything here. The engine is orchestration ONLY: it does not touch the rendered
output, the DATA schema, or what the user sees. Same dashboard either way.

Script: `scripts/scan_runner.py`. Free web data only, so there is no Apollo, credits or budget step.

---

## Scale and runtime — be honest up front

This runs the FULL deep research pass on every company, so it is slow by design.

- No hard cap. Built for **~1,000–4,000 companies**. At the MEASURED rate (~15–25 companies/hr
  per agent × 5 agents) that is **~8–13 hrs for 1,000 and ~32–53 hrs for 4,000**. One night
  covers roughly 1,000–1,500; anything past that needs several scheduled nights. Say so up front.
  The dashboard ships partial after night one.
- **Always print the pre-run TIME ESTIMATE first** (compute it, never guess):
  ```bash
  python3 scripts/scan_runner.py estimate --count N --agents 5
  ```
  Surface the hours **range** it returns. Formula: `accounts ÷ (~15–25 accounts/hr per agent) ÷
  agents = hours`. That rate is **measured, not assumed**: one full per-company pass is ~3–4
  minutes (~10–17 searches + fetches). Never talk a run up as faster than the script says.
- At **~100+**, get an explicit confirm BEFORE running, using that estimate; at **~1,000+**, warn
  as well (multi-night, partial-first shape). Exact wording is in `references/run-comms-spec.md`.
- Below ~20, just run serially. No sharding, no estimate, no confirm.

## Parallel fan-out — HARD CAP 5 agents

`plan` dedupes the book by domain, then splits it into **at most 5 shards** (one shard log each).
The driving agent spawns **one Task sub-agent per shard**, so there are never more than 5
concurrent workers. The cap is structural: ≤5 shard files ⇒ ≤5 workers. Each worker loops its
shard: research one company → `mark` its new state → next. Exactly the single-company Procedure,
over its slice.

## Checkpoint / resume — append-only state machine

Each shard owns `run/<run_id>/shard-NN.log.jsonl`. Every company moves `queued → researched →
done`, or `nogo_done` (instant Step-0 knockout, no full pass) / `failed`. `mark` appends each
transition (fsynced) and carries the company's rendered card DATA on `done`.

If the run dies, **on restart call `next` per shard**: it replays that shard's log, takes each
company's LAST state, and returns only the non-terminal companies. Work resumes from the next
unprocessed company, never from the top. At most the one in-flight company is redone.

**Dedupe is by normalised domain** (scheme/www/path stripped), so the same company is never
researched twice, even across overlapping input rows.

**Re-planning is additive.** Re-running `plan` on the same run-dir adds only genuinely new
companies and keeps each existing company on its shard, so "add more companies" and "resume"
both just work.

---

## Orchestration steps

**O1. Estimate + confirm.** Build the input list (parsed names/domains). Run `estimate`, surface
the hours range. Above ~100, get the user's confirm before running.

**O2. Plan/shard.** Write the list as `[{name, domain}, …]` to a JSON file, then:
```bash
python3 scripts/scan_runner.py plan --in <book.json> --run-dir "<run dir>" --agents 5
```
Dedupes by domain and seeds ≤5 shard logs. Pick a stable run-dir per list, e.g.
`Claude HQ/Company Research/<slug>-<date>/run`, so a later night resumes the same run.

**O3. Fan out — one sub-agent per shard, MAX 5.** Spawn one Task sub-agent for each shard
`0..n_shards-1` (`n_shards ≤ 5`, never spawn more). Each sub-agent loops: `next --shard S` → for
each pending company, run Step 0 then steps 1–3 of the Procedure for that ONE company → build its
card DATA object → `mark --shard S --key <the exact key next returned> --state done --data
<card.json>`. Use `nogo_done` for a Step-0 knockout (no full pass) and `failed` for an
unrecoverable company.

**Always pass `--key` with the exact `key` field `next` handed you.** For a domain-less company
that key is `name:<slug>`. `--domain` still works for domain-keyed companies but `--key` is
unambiguous. A blank or mismatched key is a hard error, never a silent no-op, so a mis-marked
company can't be stranded `queued` forever. Marking after each company IS the checkpoint.

**Five things the orchestrator MUST put in each shard sub-agent's prompt** — a worker cannot get
them itself:

1. the `company_profile` block **verbatim**, because `next` returns only `{key, name, domain,
   state}` and workers NEVER read the brain;
2. that its `--data` file is **ONE element of `companies[]`** (a single company card), not the
   whole DATA object;
3. that it stays **SILENT in chat** — five parallel agents narrating is noise;
4. that `angle` should be a terse factual stub, because O5 rewrites it anyway;
5. the trouble-brief: expected signal if it worked, likeliest failure and the countermove,
   stop-when conditions, and to flag anything it could not verify back up to the orchestrator.

**Worker model tier (routing).** Spawn each shard sub-agent at the CHEAPEST CAPABLE model tier
for spec-driven research: the per-company pass fills a fixed schema, so it does not need the top
model. Use the MID tier, not the floor (per-company synthesis needs some judgement, so don't drop
workers to the grunt/search-only tier). The orchestrator keeps the sharding, the merge and the
angle sharpen in O5. Bind "cheapest capable" to whatever models are available this session; never
hardcode a model name here, so this stays correct as models change. **Worst case: if you can't
confidently resolve a cheaper tier, spawn the workers on the session model.** Routing is an
optimisation, never a gate; never block or slow a run to chase it. The rendered DATA is
byte-identical either way.

**O4. Resume after a crash.** Just re-run O3 (and O2 first if adding companies). `next` returns
only the not-yet-terminal companies per shard, so workers continue from where they died.

**O5. Merge + render once all shards drain** (poll with `status --run-dir`):
```bash
python3 scripts/scan_runner.py merge --run-dir "<run dir>" --out /tmp/companies.json
```
Collects every done company's card (with its `scan` object) into the `companies` list, **already
sorted into ranked order** (Strong → Fair → Longshot, score desc within band). Merge enforces
this, so a gate-aware SKIP with a high /100 can never float above a real GO, and the list is never
in completion order. Drop it into the DATA object's `companies` field and render exactly as
**Render the artefact** in SKILL.md. The engine changes nothing the user sees.

**Angle sharpen at merge.** After merge, the orchestrator rewrites each company's `angle` line
from the facts the worker already gathered, no re-searching. This keeps the one taste-bearing,
human-read field on the top model while the bulk research stays on the cheaper tier. It touches
ONLY `angle`; every other field and the schema are untouched, so the render stays byte-identical.

**Ledger on checkpoint.** A long run archives as it goes, on the same checkpoint as the resumable
state, never one write at the end (which would lose everything if the run is interrupted). See
the ledger section in SKILL.md.
