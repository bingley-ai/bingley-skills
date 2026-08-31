# Releases

Each skill is now its own plugin and versions independently. Current versions:
cold-email-builder 1.0.0 · company-researcher 1.0.0 · list-builder-apollo 1.0.0 ·
sales-advisory-board 1.0.0 · sales-brain-setup 1.0.0 · **sales-control-panel 1.1.1**.

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
