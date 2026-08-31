# LAYOUT CONTRACT — the geometry the panel must obey

Read this before touching `panel-shell.html`, `render.js.html` or `modal.css.html`.

Every rule below was written after the panel broke that exact way, and each was found by
**measuring a real browser** or by **looking at a screenshot** — never by reading the CSS.

---

## 1. The stage is fixed. Nothing scrolls. So nothing may overflow.

The Desk is a **1448 x 1086** surface (`.stage`), scaled to the browser by `--fit`. `.center` is a
fixed **1049 x 904** box at **(199, 94)**. The cards inside are absolutely positioned at fixed
sizes. **There is no scrollbar.** Content that doesn't fit is not "below the fold" — it is silently
cut, or it paints on top of the furniture.

The Book (tab 2) is the one surface allowed to scroll. The Desk never is.

## 2. The cards sit ON a desk that the SVG shell draws. Respect its edges.

The shell draws the desk surface at **200,91 -> 1248,985** (a `<rect fill="#faf8f7">`). This is
*smaller than `.center`*, whose bottom is 998. So a card pinned to the bottom of `.center` hangs
**13px over the desk's front lip**, onto the frame. That shipped: `.pipeline` ended at 996 and
`.stale` at 994, and you could see both overhanging.

- **Every card's box must end at y <= 982** — a 3px inset, matching the hero's inset at the top
  (desk top 91, hero top 94). `.pipeline` and `.stale` are therefore `top:735; height:153`.
- Left edge: cards start at **x >= 200**. `.hero` and `.pipeline` used `left:-1px` (= 198 absolute)
  and poked 2px off the desk's left edge. They are `left:1px`.
- Cards that sit side by side must have the **same height**, or their bottom edges stagger.
  `.pipeline` (167) and `.stale` (165) were 2px out of step with each other.

## 3. Card height budgets (measured, demo data)

| card | box | padding | inner budget | spends |
|---|---|---|---|---|
| `.plan` | 275 | 11/12 | 252 | 248 |
| `.meetings` | 273 | 7/8 | 258 | 250 |
| `.commitments` | 187 | 5/8 | 174 | 167 |
| `.pipeline` | 153 | 1/8 | 144 | 132 |
| `.stale` | 153 | 1/8 | 144 | 139 |

**These boxes were traced from a pre-v5 mock.** Every v5 addition — the target line, the issue chip,
the overflow disclosures — spent height the boxes never had. The first casualty was always the
`+N more` link at the bottom: the very affordance promising *"a card that says 6 open must account
for 6"* was itself being cut off. **If you add a line, take one away.**

## 4. A transform is applied AFTER layout. It cannot fix an overflow — it causes one.

`scaleX` on a full-width block stretches the painted result past its box, over whatever is next.
Removed from `.task > span` (1.08 — painted the task text over the "Commit" tag) and `.commit-head`
(1.02 — pushed the "DUE" label 21px off the card). `.pipeline-money` keeps its 1.10 because its ink
is ~120px at the left of a 509px card, so the stretch never reaches the edge — box vs ink.

**Measure INK (text rects via `Range.getClientRects()`), not element boxes.** A full-width block
"overflowing" is usually harmless; its text is at the left. Boxes lie in both directions.

## 5. Fixed-height rows hold ONE line. Enforce it.

`.task` (32px) and `.pipeline-sub` are `white-space:nowrap; overflow:hidden; text-overflow:ellipsis`
with `minmax(0,1fr)` grid columns. A wrap doesn't just look wrong — it grows the card and pushes it
off the desk. The full text is always one click away in the drill-in, so truncating the tail costs
nothing.

`.pipeline-sub` carries the target inline (`weighted · 20 deals · £100k closing by 31 Jul · £10k
over target · 111% covered (£90k)`). It used to be two stacked lines; that 16px was the difference
between sitting on the desk and hanging off it. **"Set your target →" is inline too** — as its own
line it tipped the card over on any panel with no target set.

## 6. The drill-in modal mounts INSIDE `.stage`.

Not on `<body>`. The stage is scaled by `--fit`; a body-mounted modal renders at browser scale over
a scaled panel — visibly not part of the product it came from. Consequences:

- Geometry is in **stage px**, never `vh`/`vw`. The modal is `560px`, `max-height:760px`.
- **Every class must be `scp-` prefixed.** Inside `.stage` a bare modifier collides with the Desk's
  own section classes. `.scp-drow.plan` hit `.plan{position:absolute; left:1px}` and dragged the row
  **444px out of the modal**. Also why `.due`'s pill is scoped to `.scp-modal` — unscoped it landed
  on the Desk's 41px DUE column and sliced "2d late" in half.

## 7. Content follows the data; the data never bends to fit the layout.

The facts grid takes 2, 3 or 4 columns (`.scp-f2/.scp-f3/.scp-f4`) because a fixed 3-up rule
silently ate the diff's 4th counter — *gone*, a deal vanishing from the export, the most
consequential change on the panel. **A geometry rule must never outrank the truth rule.** If the
data needs a cell, the grid gives it one.

Corollary: never `||0` a missing count and never let `fmt(null)` render an empty £ cell in a column
of real numbers. See `amt()` / `factMoney()` / `moneyBlocked()` in `render.js.html`.

## 8. THE BOOK has its own laws. Sections 1-3 do NOT apply to it.

The Book scrolls on purpose, so "fits the desk" is meaningless here — and because none of the rules
above applied, it shipped with no layout coverage at all and collected its own defect set, every one
found by eye. What replaces the fixed-card law:

- **The Book sets its own base font-size (13px), same as the modal body.** It set none, inherited the
  browser's 16px, and rendered the `.scp-drow` rows it borrows from the drill-ins at 45px each: 20
  demo deals spent 924px, and a real 400-deal book would have been a ~14,000px scroll. *Allowed to
  scroll is not a licence to be twice the size of the product it belongs to.*
- **A table's column template lives on the TABLE (`.t-st` / `.t-cm` / `.t-sk`), never on the rows.**
  Stated per-row, the header has to remember to claim the same modifier. It didn't: a 4-cell head
  fell back to the 3-column default and "Value" stacked under "Days". Then claiming `.st` on the head
  to fix it made the head a stale *row* — the gate counting `.scp-drow.st` read 4 deals from a file
  with 3. **A header is not a row.**
- **The header lives INSIDE the scroller** (`bookTable()`), not as a sibling above it. `.book-table`
  carries 12px padding + 1px border, so an outside head sat 13px left of every column it named. Two
  boxes can't be kept in register by hand; one box keeps itself. Sticky is the payoff: on deal 300 of
  400, an unlabelled column of numbers is not a ledger.
- **Every capped list accounts for its own count, and the scroll cue must be TRUE.** A 340px table of
  35px rows showed 7 of 8 promises under a head reading "8 open", with this platform's overlay
  scrollbar invisible until you already knew to scroll. That is the panel's founding defect (P7: 103
  of 108 stale rows hidden) wearing a nicer coat. So: a permanent scrollbar, a fade, a line stating
  the full count — and the fade and the words "scroll it, nothing is held back" are painted ONLY
  when `markOverflow()` has measured real overflow. A fade over a list that fits dims a real row to
  advertise rows that don't exist.
- **Measure after you show it.** `markOverflow()` ran from `renderBookInner()`, which is called while
  the view is still `hidden` — every table measured 0x0 and read "fits", so the cue never appeared on
  the one section that overflows. It is called from `showView()` after the view is shown. *Measure
  the thing on screen, or don't call it a measurement.*
- **A door must be worth opening.** Stale and commitment rows open the Desk's own `staleBody()` /
  `commitBody()` — the same record, no Book-only invention. Pipeline rows deliberately have NO door:
  the stage payload carries nothing the row doesn't already show, and a door that opens onto what you
  just read is a lie about depth.
- **Say it once.** The row accounting was published three times on one screen (trust strip, section
  meta, four KV rows). The trust strip owns it. A count of 0 is not a finding, and a count whose rows
  are itemised below is the same fact twice — the itemised one is the useful one.

## 8b. THE MEETING DRILL-IN: two tiers, one screen.

v1's meeting-prep mock (`sales-control-panel-v2-DEMO-wired.html`) is the design target. Note what it
actually was: `m.prep.points/emails/call` were **hand-written demo strings**. The "AI talking points"
were never a capability — they were a picture of one. So this is built, not restored.

- **The evidence IS the feature; synthesis is not required to make it valuable.** What made v1's
  screen good was never the AI — it was the buyer's own sentence. Everything on the connected bands
  is **verbatim or a timestamp**: the ask is the buyer's words, the call summary is the transcript
  tool's words carried with its own name and link. We display someone else's synthesis; we never
  write our own, and we never re-summarise theirs (a synthesis of a synthesis is two steps from
  anything anyone said, and unfalsifiable by the time it reaches the rep).
- **Rank the thread by UNANSWERED ASK, never by recency.** Sorting by timestamp reliably surfaces
  "Great, see you Tuesday" and buries the sentence that decides the hour. "Open" = nothing sent since
  it — arithmetic on two dates, never a judgement about whether the rep answered it well.
- **Facts about the thread, never verdicts.** "They sent the last email" — not "you owe them a
  reply". The file cannot know they didn't phone.
- **The engine reads FILES; the adapter calls the API.** `--emails` / `--calls` take json, exactly
  like `--meetings` / `--commitments`. Fetching lives outside. This keeps the build deterministic —
  the batteries re-run it as a subprocess and pin its output to the pound, and **a gate that depends
  on someone's inbox is not a gate.**
- **The gap strip must know what we already have.** Hardcoded, it went on advertising "connect Gmail"
  directly beneath a verbatim email it had just pulled *from Gmail* — the panel failing to notice its
  own state. `meetingGap()` names only what is genuinely still missing, and renders nothing when
  nothing is. Both directions are pinned: CSV-only must still ask; connected must stop asking.
- **If a talking point is ever built: no citation, no render.** "Lead with pricing — she asked for a
  breakdown by store size" is safe *because* the email sits beside it. Un-cited, it is the one object
  on this screen that can lie fluently, and the gap strip cannot catch it — a missing number looks
  missing, a plausible wrong sentence looks like help. It also needs an LLM in the build path, which
  would end the determinism the batteries rest on. Not built. Deliberate.

## 9. How to verify (do not eyeball this) — MAINTAINER REPO ONLY

`layout_test.js` lives in the development HQ, not in an installed copy of this skill. On an install, the
path below does not exist — skip the script and rely on the screenshot check; do not go hunting
for it.

```bash
node ../../Sales\ Control\ Panel/shippability-test/_engine/layout_test.js <panel.html> [stress.html]
```

Run it over the demo **and** a stress panel — a 400-deal file and a blocked/suppressed file. The
forecast-category table that spent 245px of a 144px budget only appeared on persona 6; the 108
blank £ cells only appeared on persona 7. **A clean demo proves nothing about a real book.**

Then look at a screenshot. `layout_test.js` finds what it was told to look for; the eye finds the
rest. Both the sliced DUE pills and the "See all insights →" escaping onto the side panel were
spotted by eye first, then confirmed by measurement.

**And check the gate can still fail.** A gate that passes on good code proves nothing until you have
watched it catch the defect it was written for. **Every one of the four Book assertions has been
mutation-proven** — mutate the built panel, re-run, confirm the right check goes red:

| mutation | restores the defect | must fail |
|---|---|---|
| head moved outside `.book-table` | the 13px register drift | *head sits over its own column* |
| strip `t-st` off the stale table | "Value" stacked under "Days" | *every table head is a single line* |
| force `.overflows` true | fade over a list that fits | *scroll cue matches the measurement* |
| `fmt(t.gap)` without the sign branch | "£-10k to find" | *no NaN/undefined/negative money* |

This is not ceremony: the head-check **passed** its mutation at first and had to be rewritten to
measure grid rows rather than text lines. It was testing the wrong thing, it was green, and only the
mutation showed it. Assume a new assertion is wrong until a mutation turns it red.

---

## ⛔ THE FOOTER STRIP IS NO LONGER DECORATION — A SHELL SWAP WOULD SILENTLY DELETE IT

`.office` used to read HEAD OFFICE. Since **14 Aug 2026** it is the **rate-this-skill strip**: the
only feedback channel back from a shipped skill, and the only thing that answers "is anyone
actually using this". It is three pieces inside `panel-shell.html` — the `#officeStrip` markup,
the `.office-*` CSS, and the small IIFE above the `fit()` script.

**The shell is swapped wholesale when the mesh shell lands. That swap would take all three with
it, and nothing would break, error or look wrong — the ratings would just stop arriving.** That
is the worst kind of regression: silent, and invisible until you go looking at an empty chart.

So, on any shell swap:
1. Re-apply the three pieces to the incoming shell (they are self-contained, ~40 lines total).
2. Set `data-skill` on `#officeStrip` to this room's key (`salescontrolpanel` here). **If the
   attribute is missing the strip hides itself** — deliberate, so a half-applied patch shows
   nothing rather than posting ratings under the wrong skill.
3. Verify by loading the panel and confirming ten pips render, then `GET /skill-stats` and check
   the skill's `rating_n` still moves.

Maintainer repo only from here: the pointers below name files in the development HQ that an installed
copy of this skill does not carry. On an install, ignore them — the strip itself is already in
`panel-shell.html` and needs nothing from these paths.

The identical three pieces live in `cold-email-builder/references/scorecard-template.html`
(`data-skill="coldemail"`). Five more rooms still show the old HEAD OFFICE text and carry a
byte-identical `.office` rule, so the same patch drops straight into them:
company-researcher, list-builder-apollo, projects-board.

Endpoint + storage detail: `Claude HQ/Projects/Home Site/skill-download-tracker/DEPLOY.md`.
