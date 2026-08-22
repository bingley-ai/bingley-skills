# Artefact flow — one live scorecard, create-then-update

The GRADE result is shown to the user as **one** persistent artefact named `cold-email-scorecard`. The skill is the engine; the artefact is only the view. Never score inside the artefact, never make a second artefact per email.

## 1. Lens / preference file
- Path: `cold-email-scorecard.prefs.json` in the user's working (Cowork) folder.
- Shape: `{"profile":"A|B|C","audience":"B2B|B2C","mode":"cold|follow-up|reactivation","price":"yes|no"}` (any subset).
- On each run: read it (via the brain bridge `get` — brain-first, this file as legacy fallback). Present → grade on that lens. Absent → default (profile A · B2B · cold · no price).
- When the user states a different lens, persist it with `python3 scripts/brain_bridge.py save --skill cold-email --base "<wf>/Claude HQ" lens=…` (the brain is the write path; this legacy file stays read-only), then re-grade. Confirm in one line. The card's `lens` string reflects whatever was used.

## 2. Create vs update — decide, never ask
One scorecard artefact, updated in place. Publish the built HTML with the host's artifact tool, using the **same file path every run**: the first run creates the artefact, every later run republishes it to the same URL. Never a second artefact, never one per email, and the user never chooses. If the host has no artifact tool, save the HTML and present that one file instead.

## 3. Build the artefact HTML
- Take `references/scorecard-template.html` **verbatim**.
- Compute the `DATA` object from the grade (schema below).
- Minify it, then **make it script-safe — mandatory, every run**: `payload = json.dumps(DATA, separators=(",", ":")).replace("<", "\\u003c")` (the `replace` rewrites every `<` as its JavaScript unicode escape, so no real `<` survives in the data block). The pasted email is embedded verbatim, so if it contains `</script>` — common in HTML signatures, forwarded web copy and email previews — an unescaped `<` closes the inline `<script>` early: the card renders blank and any markup after the tag is injected into the page. The escape is the standard safe-JSON-in-HTML fix and is invisible on the card (the browser turns it back into `<`, then the template's own `esc()` escapes it for display). `json.dumps` already escapes quotes, newlines and U+2028/9; `<` is the one it leaves, so this single replace closes the hole.
- Inject by replacing the line `window.__SCORE_DATA__ = window.__SCORE_DATA__ || null;` (inside `<script id="cold-scorecard-data">`) with `window.__SCORE_DATA__ = <payload>;`.
- Write the result to a file (same path every run) and publish that file as the artefact. **Change nothing else** — not the shell, not the content, not the render script.

## 4. DATA schema (what the template renders)
The card is a **dual view**: the user's pasted email scored (`before`) and, once rebuilt, the improved version scored (`after`). A Before/After toggle flips the score side; **both emails are always shown** (yours, then the rebuild). On a grade-only run with no rebuild yet, **omit `after`** — the toggle hides itself and only the user's email shows.

```json
{
  "lens": "cold B2B first-touch",          // printed on the card; reflects the profile used
  "before": { /* view object */ },
  "after":  { /* view object — optional; omit on a grade-only run */ }
}
```

Each **view object** (`before` and `after` share the same shape):
```json
{
  "score": 76,                              // 0-100 int (headline)
  "band": "C",                              // A|B|C|D|Gated|F
  "tier_label": "Decent, a few fixes",
  "archetype": "The Problem-Led Opener",    // one name from scoring-model.md §8
  "verdict": "one plain sentence about replies",
  "emailHeading": "The email — your copy, with the evidence marked",  // heading above THIS view's email
  "dims": {"Relevance":3,"Problem-led":4,"CTA quality":4,"Proof":4,"Brevity":3,"Subject":null},
  "gates": [
    {"name":"Deliverability","score":4,"pass":true,"note":"..."},
    {"name":"Subject","score":null,"pass":true,"skipped":true,"note":"no subject pasted — left out of the score"},
    {"name":"Relevance","score":3,"pass":true,"note":"..."},
    {"name":"CTA","score":4,"pass":true,"note":"..."}
  ],
  "costing": [{"ref":1,"score":3,"title":"short","body":"one plain line"}],   // red, up to 3 (weakest)
  "working": [{"ref":4,"score":4,"title":"short","body":"one plain line"}],   // blue, up to 3 (strongest)
  "subject": "the subject line, or (none pasted)",
  "email_text": "the full email as plain text for the Copy button — greeting, blank line, body paragraphs (blank line between), sign-off + name on adjacent lines; before = the user's pasted email verbatim, after = the rebuilt email",
  "email_lines": [
    {"text":"Hi Name,","mark":"none","ref":null},
    {"text":"I saw you're growing the team...","mark":"good","ref":4},
    {"text":"We help B2B companies...","mark":"bad","ref":1}
  ]
}
```

Rules:
- dims and gate scores are ints 0-5, or `null` when skipped. No subject pasted → set the `Subject` dim and the Subject gate to `null` with `"skipped":true`; **never penalise a missing subject** (the gate shows a grey minus, not a fail).
- a gate fails when its score < 3; any fail caps `score` < 60. Bands: A>=90, B80-89, C70-79, D60-69, Gated30-59, F<30. The card colours the headline by band: **blue 80+, gold 60-79, red below 60**.
- **Gate progress line — each segment takes the colour of the checkpoint it leaves.** The four gate dots are joined by line segments; segment *i* (from gate *i* to gate *i+1*) is coloured by gate *i*'s own status: **pass → green, skipped → grey, fail → red, not-yet-reached → grey**. So a passed gate's outgoing line is green; a skipped or failed gate's outgoing line carries its own colour onward. Concretely, **with no subject** (`Subject` skipped): Deliverability→Subject is **green** (Deliverability passed), the Subject dot is a **grey minus**, and Subject→Relevance is **grey** (the line leaves a skipped gate). This rule is general, not subject-specific: any missing/red checkpoint greys/reddens only the one line leaving it. There is no "60+ unlocked" chip — it was removed.
- give each costing/working a `ref` and mark the matching `email_lines` entry with the SAME ref (`good` = blue/working, `bad` = red/costing); use `ref:null` for unlinked lines. A costing card may carry `"neutral":true` to render grey (not red) for a not-scored note, e.g. a missing subject.
- keep every title/body one short plain sentence about what the READER does.
- the `after` view's `email_lines` are the rebuilt email: apply the **sign-off rule** (greeting by name; sign-off + sender name with nothing after it; any bio goes in the body before the sign-off). The flip from Before to After should visibly lift the score (e.g. C→B) and recolour the headline.
- **Rebuilt-email formatting rule (so display AND copy keep their shape).** The card renders each `email_lines` entry as a paragraph block (`white-space:pre-line`, blocks joined by a blank line) and the Copy button writes the same blocks out. So encode the rebuilt email as **whole paragraph blocks, never one-line-per-sentence** (one sentence per entry double-spaces the whole email on paste). Required shape: **greeting** is its own block (`"Hi Name,"`); **each body paragraph** is one block (keep its sentences together in that one entry); the **close** is a single block with the sign-off and name on their own lines, separated by a single newline inside the text, e.g. `"text":"Thanks,\nSam"` — nothing after the name. This yields, both on the card and on the clipboard:

  ```
  Hi Name,

  First paragraph.

  Second paragraph.

  Thanks,
  Sam
  ```

  Evidence marks (`good`/`bad`/`ref`) still attach per block. Apply this to the `after` (rebuild) view. The `before` view MAY stay sentence-level for finer highlighting, BUT the Copy button copies the shown view (it copies `before` on a grade-only run), so **every view MUST set `email_text`** — the clean, correctly-spaced full email. Copy prefers `email_text` and only falls back to joining `email_lines` when it is absent (which double-spaces a sentence-level `before`), so always set `email_text`.
- the **"what next" options grid** is built into the template and needs no data. The **Copy button** copies `email_text` from the shown view (falling back to `email_lines`), so always provide `email_text`.

## 5. Shell / content separation (for future shell swaps)
`scorecard-template.html` is built in labelled layers: the **v3 shell** (base `<style>` + SVG desk-shell markup + fit script), the **scorecard content + styles**, and the **render script** (`<script id="cold-scorecard-js">`) fed by `<script id="cold-scorecard-data">`. When a new pixel-final shell lands, replace only the shell layer; the content and the data binding are untouched. Keep these layers separate in any future edit. The data binding carries one hard rule (§3): every `<` in the injected JSON is escaped (the `.replace` in §3) so a pasted `</script>` can't break out of the data script — never drop that step.

## 6. The "Rate this skill" strip (added 14 Aug 2026, moved 14 Aug 2026) — DO NOT STRIP

The card's footer strip — the bar that used to read **HEAD OFFICE** — is now a 1-to-10 rating
strip. It lives in the **shell block** (`#officeStrip` markup + `.office-*` CSS + a small IIFE),
NOT in the scorecard content. Inject `DATA` as normal and it renders itself. Nothing in this
flow changes because of it.

Four things a future edit must not "tidy away":

- **The pips are `<a href>` links, not `fetch()`.** Cowork artefacts sandbox outbound requests,
  so a real link opening the user's browser is the only channel out of the card. Anyone
  converting these to buttons with a `fetch` will silently kill the feedback loop — it will
  look fine and send nothing.
- **They point at `https://bingley.ai/r?s=<data-skill>&n=<1-10>`**, handled by `_worker.js` on
  the `bingley-home` Pages project, which writes to the `ratings` table in the `bingley-downloads`
  D1 database and returns a thank-you page. One rating per person per skill (most recent click
  wins), read back via `GET /skill-stats` as `rating_n`, `rating_avg`, `rated_pct`.
- **It asks every run until they answer, then never again.** Flag is
  `localStorage["bingley.rated.coldemail"]`, set on click. Every republish redraws this card
  from scratch, so an in-page flag would reset each time — localStorage is what
  survives the redraw. It **fails open**: if storage is unavailable the strip still shows, so a
  broken environment means "keep asking", never "silently stop asking".
- **⛔ It is in the SHELL, which is swapped wholesale.** A shell swap would delete all three
  pieces and nothing would error — the ratings would just stop arriving. Re-apply them and set
  `data-skill`; a missing `data-skill` hides the strip on purpose, so a half-applied patch shows
  nothing rather than filing ratings under the wrong skill.

**Maintainer-only note** (paths outside this skill package; ignore if you don't have them):
the identical three pieces live in the maintainer's `sales-control-panel` shell — keep them
byte-identical apart from `data-skill` — and the endpoint's source of truth is the maintainer's
skill-download-tracker deploy doc.
