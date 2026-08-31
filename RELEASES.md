# Releases

Each skill is now its own plugin and versions independently. Current versions:
cold-email-builder 1.0.1 · company-researcher 1.0.1 · list-builder-apollo 1.0.1 ·
sales-advisory-board 1.0.0 · sales-brain-setup 1.0.1 · **sales-control-panel 1.2.1**.

## sales-control-panel v1.2.1 — 31 Aug 2026

- **Negative deal values are now flagged, not silently summed.** A deal with a negative amount
  (a typo, or a credit miskeyed as a deal) used to drag your pipeline down with no warning. It's
  now surfaced like any other data-quality issue — counted as-is so the total stays honest to your
  file, but you're told and can fix it.

## cold-email-builder v1.0.1 — 31 Aug 2026

- **Fixes a cross-skill glitch found in testing.** When you set up your sales brain first and then
  built an email, the email could pick up an internal "what to do next" note (like "write/fix your
  cold email") and use it as the email's call-to-action. Now the builder treats that field as a
  hint only and always writes a proper reader-facing CTA. You'd have caught it in the draft anyway
  (nothing is ever sent for you), but now it won't happen.

## sales-control-panel v1.2.0 — 31 Aug 2026

Fixes from a 30-run cold-start test of all six skills (every scenario run as a brand-new user).

- **Duplicate rows are now caught even without a deal-id column.** Before this, a deal exported
  twice was silently counted twice — your pipeline number was quietly wrong. Now exact duplicate
  rows (same deal, company, value, stage and close date) count once, and the panel tells you it
  found them and lets you choose which row wins.
- **Stage guesses are always disclosed.** When your stage names don't match the standard ones
  (say "Proposal Sent"), the engine maps them to the nearest stage to weight your pipeline. It
  now always tells you which guesses it made and how to correct them — before, it only mentioned
  this if something else was also wrong with the file.
- The skill now says plainly when a request belongs to a sibling skill (writing the cold email,
  building a prospect list, deep company research) instead of leaving that to chance.

## company-researcher v1.0.1 — 31 Aug 2026

- **No list? Not a dead end any more.** Say "I don't know who to research" and it offers a real
  starting point instead of waiting for a list you don't have.
- **Messy files handled by rule, not luck.** Phone numbers, test rows, duplicates and broken rows
  in your export are now skipped or repaired *and you're told exactly what was skipped and why* —
  none of it is silently researched or silently dropped.

## list-builder-apollo v1.0.1 — 31 Aug 2026

- **Consumer targets are caught early.** Apollo only holds businesses — if your buyers are
  individuals (wedding clients, homeowners), it now says so up front and helps you reframe,
  instead of running a search that can't work.
- **"Is this costing me money?" now has one fixed, honest answer** — what's been spent, what's
  free, what the next paid step costs — and asking never restarts your run.
- The skill now declines sibling jobs (writing your cold email, deep single-company research) by
  name instead of improvising, and never invents company facts from memory.

## sales-brain-setup v1.0.1 — 31 Aug 2026

- **The "delete it" instruction is now the whole truth.** Deleting the `ledger` folder stops the
  tools keeping copies; erasing everything the brain knows means deleting the whole `Claude HQ`
  folder in your working folder. The finish screen now says both.
- Internal fix: the silently-derived "first move" suggestion is stored as a guess, not as
  something you confirmed.

## sales-control-panel v1.1.1 — 31 Aug 2026

Packaging-only release to verify the new per-skill update path end to end. No functional
changes — if you're on 1.1.0 you're missing nothing except this test.

## sales-control-panel v1.1.0 — 31 Aug 2026

- **Demo mode.** No CRM export yet? Say "build my sales panel with demo data" and it writes a
  clearly labelled sample pipeline (dated today, never stale) and builds the full panel from it —
  meetings, commitments and all. Point it at your own export whenever you're ready.
- No more dead end on first run without a deals file.

## Marketplace restructure — 31 Aug 2026

The single "bingley-sales" bundle is now six standalone plugins in this marketplace. Install
only what you want; each updates on its own. If you had the old bundle installed, remove it
and install the skills you use from the marketplace list — same skills, better updates.

## v1.0.0 — 22 Aug 2026

First public release of the Bingley Sales plugin: the same six skills previously shipped
as `.skill` downloads on bingley.ai, now as one installable, updatable plugin.

What you get, in plain English:

- All six skills in one install: cold-email-builder, company-researcher (now covering full
  list scans of any size — the old Prospect Grader is folded in), list-builder-apollo,
  sales-advisory-board, sales-brain-setup, sales-control-panel.
- Every skill hardened this month: hostile-reviewed, fixed, and re-verified end to end from
  the shipped build — including the bug where a 40-company research list stopped dead at 9.
- Your customisations survive updates: put them in LOCAL.md beside any skill.
- Skills now say in their output which version produced it, and tell you when a newer
  version exists.

Nothing you need to do: if you're installing fresh, this is simply what you get.
If you used the old `.skill` downloads, install the plugin and delete the old skills —
same tools, but these ones can be updated.
