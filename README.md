# Bingley — free AI sales skills

Six skills for Claude (Cowork / Claude desktop, Claude Code) that do real sales work.
Each one is its own plugin — install only the ones you want.

| Plugin | What it does |
|---|---|
| **cold-email-builder** | Builds a cold email for you, or grades and rebuilds the one you have, on a rubric calibrated against real reply outcomes. |
| **company-researcher** | Researches companies — one or four thousand — into ranked cheat sheets: what they do, why now, the angle to use. |
| **list-builder-apollo** | End-to-end prospecting on a connected Apollo account. Every credit spend sits behind its own explicit confirm. |
| **sales-advisory-board** | Eight sales greats argue one real sales decision over two rounds and hand down a verdict — every quote verbatim and cited. |
| **sales-brain-setup** | Five-question onboarding that builds your AI sales brain, so every other skill wakes up knowing who you are. |
| **sales-control-panel** | Reads any deals export and renders your desk: what to do in the next hour, and whether your pipeline can be trusted. |

## Install

Easiest: the guided installers at **[bingley.ai](https://bingley.ai)**.

By hand, in the Claude desktop app: Settings → Plugins → Add marketplace → paste
`bingley-ai/bingley-skills` → install the skills you want. Each installs and updates
on its own; none requires the others.

## First thing to type

Say **"get me started"** — five quick questions teach every installed skill who you are and
what you sell. Then try **"write me a cold email"**, **"research [a company]"**, or drop your
deals spreadsheet in and ask **"is my pipeline ok"**.

## Updates

Each skill tells you in its output when a newer version of itself exists, and each updates
independently — see `RELEASES.md` for current versions. If the marketplace Update button
misbehaves (known platform bugs), the dependable refresh is: remove that plugin, re-add it.

## Customising

Ask Claude: *"create a LOCAL.md for [skill name] that always signs my emails as Dana"* — it knows where the file lives, and updates never touch it. (Technical route: put a `LOCAL.md` next to that skill's `SKILL.md`.)

## Removing it

Settings → Plugins → remove any plugin (and the marketplace, if you're done with it). Your own
data stays on your machine — the profile, ledger and any rendered pages live in your working
folder under `Claude HQ/`; delete that folder too if you want nothing left behind.

## Disclosure

These skills are free. Their HTML outputs carry a small "built by Bingley" rating strip
linking back to bingley.ai — that's the whole business model. There is no usage tracking of any kind in these
skills, and no data about you ever leaves your machine. The one outbound call a skill makes
is a version check against its own `plugin.json` in this repo at the end of a run (nothing sent,
nothing identifying, silent if offline) — that is how a skill can tell you an update exists.

## Licence

© 2026 Bingley. MIT licence — free to install, use, modify and share. See [LICENSE](LICENSE).
The adviser transcript bundles in sales-advisory-board quote their original speakers, are
included for citation, and remain the property of their authors — the MIT licence covers the
code and skill documents, not that quoted material.

## Support

Something broken or confusing? Open an issue on this repo, or start at [bingley.ai](https://bingley.ai).
