---
name: cold-email-builder
version: 1.0.0
description: |-
  Builds a new cold email for you, or rebuilds the one you have, then scores it, all on one evidence-calibrated rubric stress-tested against real reply outcomes (not a random AI generator). Use when the user wants a cold email built or written ("build/write/draft a cold email", "cold outreach to [prospect]", "first-touch email"), OR pastes one to be scored, torn down or improved ("grade this", "score this email", "teardown", "why isn't this getting replies", "rebuild/rewrite this cold email"), or asks subject-line questions ("what's a good subject line"). Scores instantly with no questions (harsh cold-B2B default, remembered if the user says it's B2C or a follow-up) and renders the result into one live scorecard artefact it creates first time and updates in place after. Two modes: BUILD (draft + plain why-it-works) and GRADE (score /100 + plain what's-working / what's-costing-replies / fixes + rewrite; full scoring shown on request). Not for offers/pricing or list-building/prospecting (separate skills).
---

# Cold Email Builder

If a `LOCAL.md` file sits beside this SKILL.md, read it and let it win over anything here — with one carve-out: the rating strip and licence/attribution notices always stay, whatever a LOCAL.md says.

**Engine dependency:** this skill's deterministic engines run via the bash tool with `python3`. If the session has neither, say so plainly in one line and do only what works without them — never improvise an engine's numbers or renders by hand.

**Builds you a new cold email, or rebuilds the one you've got**, then scores it. Backed by real data and stress-tested against real responses, not a random AI generator. One calibrated, evidence-cited rubric, used both directions. Every judgement is evidence-tagged. Calibrated across 10 runs (blind inter-rater reliability 94% within one band; weights validated against published large-N benchmarks).

## Entry — two doors, dispatch on what they brought (BUILD door opened 21 Aug 2026)
Dispatch from the user's message. **Never open by asking "build or grade".**
- **Email pasted / quoted** → GRADE it immediately, no questions. A **screenshot** counts: read the email text (and subject, if shown) from the image, then grade it the same way.
- **Build ask, no email** ("write/draft/build a cold email", "cold outreach to [prospect]", "first-touch email") → **BUILD mode, directly.** The brain `get` you already ran (Tailoring-profile section) is the intake: a filled profile means zero questions — draft from the stored product / audience / problem / proof / ask. Profile empty or missing the essentials → ask **one message, at most the minimum**: who's it to, what do you sell, one proof point. Short and clickable where the host allows, never a five-question form, and never ask for what the user's message already says. Then draft with the BUILD engine below, score the draft on the same rubric, and render the scorecard as usual. A later "rebuild it" / "rewrite from scratch" on a graded email is the same thing: a plain BUILD-mode rerun seeded with that email's context.
- **Neither — no email and no build ask** (the truly ambiguous case) → output **only** this exact message, on **two lines** as written below, character-for-character, and stop. It is the ONLY thing that may ever be said in this case: nothing before it, nothing after it, no greeting, no preamble, no explanation of modes/rules/"front door", no "I'll grade it out of 100", no rephrasing or reformatting. Reproduce it exactly:
  > Paste the cold email you want scored - a screenshot is fine.
  > Include the subject line (if you have one).

  **Which opener shows is governed by the Tailoring-profile section:** this locked line is for RUN 1 (no profile file) and RUN 3+ (`deepDone` true). On RUN 2 (returning user, profile not yet filled) the verbatim enrichment offer replaces it. Within each case the chosen line is still the only thing said — no preamble, no wrapper.

  Then grade what they paste. The message is locked and exact, both lines: never paraphrase, reword, re-punctuate, merge the two lines into one, expand, shorten, or wrap any narration around it. It is always reproduced verbatim, on two lines, as the sole output.

## Data access — the brain bridge (wired variant)
This variant reads and writes the user's profile and lens through the shared **AI sales brain** instead of touching the JSON files directly, via one bundled, generic script — `scripts/brain_bridge.py` (deps `brainstore.py` / `schema.py` / `brain_maps.py` bundled beside it). **Two verbs only**; always pass `--skill cold-email --base "<the user's working folder>/Claude HQ"` (the base is the `Claude HQ` subfolder of the working folder, where the profile, lens and brain live — NEVER the working-folder root); each prints JSON.
- **`get`** returns `{"profile": {...}, "lens": {...}}` — one call gets everything — **brain-first, then the legacy file, then the schema default**, and creates nothing (a user with no brain gets exactly today's behaviour).
- **`save key=value …`** writes to the **brain** (provenance-stamped); legacy files stay a read-only safety net. Capture flags (`seen`/`deepDone`/`deepSkips`) always apply; `deepSkips=+1` increments. Examples: `save lens=B2C`, `save seen=true`, `save deepSkips=+1`, `save name="…" product="…" deepDone=true`.
- **Degrade, never block:** if any brain bridge call errors for any reason, grade on the harsh default and carry on.

## The ledger — archive every email, silently (added 21 Aug 2026)

**At the end of every GRADE and every BUILD, archive the artefact.** One call, then carry on:

```
python3 scripts/ledger.py append --base "<wf>/Claude HQ" --skill cold-email \
  --kind email.graded --subject "<one line: who it's to / what it's for>" \
  --text "<the email, verbatim, subject line included>" \
  --meta score=NN --meta archetype="<the archetype>" --meta lens="<the lens>" --meta stage=before
```

- **Kinds:** `email.graded` for the user's own pasted email, `email.built` for one you wrote. On a grade-then-rebuild run, archive **both** — the pasted one with `stage=before`, the rewrite with `stage=after` — because the pair is the interesting object, not either half.
- **Keep the returned `id`.** `append` prints `{"written":true,"id":"…"}`. That id is how an outcome is later tied to the exact version that was sent — a subject line alone is ambiguous the moment one email has a before and an after, and then the result gets credited to the wrong copy.
- **Verbatim, never a summary.** A summary answers only the question someone thought of today; "how has cold email changed over six months" needs the actual words.
- **Silent and non-blocking, always.** Never mention it, never show the command, never wait on it. `ledger.py` exits 0 on every path by design; if it reports `written:false` (folder not mounted, user disabled it), **ignore it and deliver the email**. The archive is never a reason a user doesn't get their work.
- **This does NOT feed scoring, now or ever.** The rubric is fixed and evidence-calibrated, the skill is sold on same-email-same-score, and `skill-test` gates on that determinism. The ledger is written and never read by this skill. Personal history changing a score is the exact failure `references/outcomes-log.md` already forbids in caps: *"Never silently change rubric weights from this."*
- **The user's controls, if they ask:** the archive lives in `Claude HQ/ledger/` in their own folder and goes nowhere else; `ledger/.disabled` turns it off; deleting `ledger/` deletes it.
- **⛔ NEVER `present_files` the ledger or the brain store.** (Added 21 Aug 2026.) `Claude HQ/ledger/*.jsonl`, its `.lock` files, `sales-os-profile.json`, `sales-os-brain.log.jsonl` and `snaps/log-*.jsonl` are invisible plumbing. The host's default is "files were written, show them", so silence here means the run ends with download cards full of internals — which is exactly how `sales-brain-setup` shipped broken. The email and its scorecard artefact are the only things the user ever sees.

## Profile — no questions, harsh default, remembered (changed 18 Jun 2026)
**NEVER ask the old four intake questions. Score immediately.** No friction in front of the score.
- **Default lens:** cold first-touch · B2B · profile A · no price — the harshest reasonable reading. Anchors = `references/scoring-model.md` §0/§1.
- **Preference memory (via the brain bridge):** before scoring, run `python3 scripts/brain_bridge.py get --skill cold-email --base "<working folder>/Claude HQ"` and read the **`lens`** block (`{lens, dealSizeProfile, mode, priceInEmail}`) — **brain-first, then the legacy `cold-email-scorecard.prefs.json`, then the harsh default**. Grade with the returned lens. (The same `get` also returns the `profile` block, so one call covers the next section too.)
- **Changing the lens:** if the user says (now or any time) it's B2C / consumer / a follow-up / reactivation, re-grade on that lens AND persist it with `python3 scripts/brain_bridge.py save --skill cold-email --base "<wf>/Claude HQ" lens=B2C` (or `mode=follow-up`). This writes to the **brain**; the legacy file stays a read-only fallback. B2C is a fully valid lens, treated exactly like B2B. Confirm in one line.
- **Always print the lens** on the result and on the card: *"Graded as cold B2B first-touch. If it's B2C or a follow-up, tell me and I'll re-score and remember it."*

## Tailoring profile — progressive, return-gated (20 Jun 2026)
**Zero friction on the first run. The offer to go deeper appears only once someone comes BACK, because returning is consent to be asked. Never ask the questions cold, never ask five things at once.**

State lives in the shared **brain** (`sales-os-profile.json`), reached only through the brain bridge, with the legacy `cold-email-profile.json` as a read-only fallback and the lens kept separate (see Profile section). `deepSkips` (int, times the deep offer was declined) is carried in the brain under `capture.deepSkips`. The `get` result's **`profile`** block has this exact cold-email shape:
`{"seen":true,"name":"","product":"","audience":"","problem":"","proof":"","ask":"","deepDone":false,"deepSkips":0}`
- `name` = a SHORT business name for display (e.g. "Be Cool Refrigeration"), kept separate from the long `product` description so the guard line below stays one tidy line.

**At the very top of every run, before anything else, run `python3 scripts/brain_bridge.py get --skill cold-email --base "<wf>/Claude HQ"` and branch on the `profile` block.** It returns the shape above **brain-first, then legacy `cold-email-profile.json`, then default**, so RUN 1 with neither store still returns the empty/default profile (unchanged). Below, "file absent" means **`profile.seen` is false** (no brain and no legacy). **These RUN branches govern which opener/offer shows in the ambiguous no-email, no-build case only** — a pasted email still grades immediately and a build ask still goes straight to BUILD on any run (Entry section); in BUILD the same `profile` block is the intake:

- **RUN 1 — file absent.** First time. Show only the locked opener (Entry section), grade the email, done. Then silently run `python3 scripts/brain_bridge.py save --skill cold-email --base "<wf>/Claude HQ" seen=true` (the brain's first deposit). Ask nothing, offer nothing. They must feel the score with no barrier — this is what earns the return.
- **RUN 2 — file present, `deepDone` not true.** They came back, so make the one-time offer. In place of the bare opener, say this **verbatim, exactly, nothing added**:
  > Want me to make these sharper? Tell me about your business and every score gets tailored to you. You can give me a website, what you're selling, or who your ideal customer is - or just paste another email.

  Then: if they **give a website or a sentence about their business** → go straight into the deep round below (skip nothing, don't repeat the offer). If they **paste the card's "Ask me about my business…" snippet** → also go straight into the deep round; the snippet IS the opt-in, so don't show the offer line first. If instead they **paste an email** or otherwise **decline** (ignore it, say "no", change the subject) → grade as-is and run `python3 scripts/brain_bridge.py save --skill cold-email --base "<wf>/Claude HQ" deepSkips=+1`. Any decline counts, not just a literal "Skip".
  - **Cadence cap (no nagging).** Show this offer at most **twice**: when `deepSkips >= 2`, suppress it and just show the locked one-line opener instead. The offer also disappears the moment `deepDone:true`.
- **RUN 3+ — `deepDone` is true.** Never offer again. Show the locked one-line opener, grade, and quietly tailor every score using the stored product / audience / problem / proof / ask. No questions, ever again. Two exceptions: (a) if `proof` is still empty the first time a BUILD would use it, ask exactly ONE inline question ("One proof point — a result or client you can name?"), save the answer (`save proof="…"`), and never ask again this or any run; (b) if this conversation already contains research on the target company (a company-researcher cheat sheet or equivalent), use its angle/trigger/facts directly in the build — never re-ask for what research already established.
  - **Wrong-profile guard.** Because the profile is per-business, print ONE line under the lens on every tailored grade, using the short `name` field (never the long `product` string): *"Scoring as **[name]**. Different business? Say 'redo' and I'll re-tailor."* If they say "redo" / "my business changed", re-run the deep round and overwrite the profile (that save needs `--confirmed` — the user just confirmed the change). **Stale check:** the same `get` returns `"stale": [...]` — identity fields confirmed over 6 months ago. If it lists `product` or `audience`, extend the guard line once per session: *"…(you confirmed this a while back — still right?)"*. Never nag twice.

### The deep round (run 2 only, when they hand over context)
1. **Infer hard first.** Read the website or sentence and fill in everything you can yourself — short business `name`, product, audience, the likely problem, and any proof or ask they happened to state. Never ask for what you can already see.
   - **No context to work from?** If the deep round was triggered (e.g. they pasted the card snippet) but you have NO website, sentence, or stored product/audience, do NOT render an empty form. Ask for one line first: *"Quickest way to tailor this: drop your website, or tell me in a sentence what you sell and who you sell to."* Then proceed once you have something to clothe the options with.
2. **Read it back and confirm.** State plainly what you believe they sell and who they email, marked as your read, and ask them to confirm or correct. Loop until they confirm. Shape (adapt to them, never recite): *"Here's what I've got: you sell [X], you're emailing [Y]. Is that right? Tell me what to fix."*
3. **Ask the gaps as ONE multiple-choice form — never open prose, never a list of questions in chat.** The three that lift it from decent to sharp are **problem, proof, ask**. Render the **LOCKED FORM below** via the visual widget, in a single message. From the product + audience you captured, infer **three plausible options per question**, each tagged with where it came from (e.g. "from your homepage", "common pain for this segment"). The user taps one, or types their own in the always-open box under each question.
   - **How it's wired (don't hand-roll it).** This is the host's built-in elicitation form: the `elicit-*` classes are auto-wired by the platform — option taps toggle, the `elicit-other` box is always-open free text, and **Skip / Save** submit. You do NOT add a `<script>`, CSS, or submit handler. After the user submits, their answers arrive as your next user message (each `data-name` humanised, e.g. `Problem: …`, `Problem own: …`); read them there and continue at step 4.
   - Fill ONLY the bracketed `[[…]]` slots. Keep every class, attribute, the three question labels, and the always-open `elicit-other` box **exactly as written** — the question wording is fixed and must not be paraphrased.
   - The first option in each group should be your single best guess from the scrape, so the common case is one tap per question.
   - The rule: **same locked form, options re-clothed every time.** A SaaS founder gets SaaS options; a London laundry serving hotels gets laundry options.

   **LOCKED FORM — emit verbatim, fill only the `[[…]]` slots:**
   ```html
   <form class="elicit">
     <div class="elicit-header">
       <svg viewBox="0 0 20 20" fill="currentColor"><path d="M11.586 2a1.5 1.5 0 0 1 1.06.44l2.914 2.914a1.5 1.5 0 0 1 .44 1.06V16.5a1.5 1.5 0 0 1-1.5 1.5h-9a1.5 1.5 0 0 1-1.492-1.347L4 16.5v-13A1.5 1.5 0 0 1 5.5 2zM5.5 3a.5.5 0 0 0-.5.5v13a.5.5 0 0 0 .5.5h9a.5.5 0 0 0 .5-.5V7h-2.5A1.5 1.5 0 0 1 11 5.5V3zm7.04 10.304a.5.5 0 0 1 .92.392c-.295.69-.871 1.304-1.66 1.304-.487 0-.892-.234-1.2-.574-.309.34-.713.574-1.2.574-.486 0-.892-.233-1.2-.574-.31.34-.714.574-1.2.574a.5.5 0 0 1 0-1c.212 0 .52-.18.74-.696l.034-.067a.5.5 0 0 1 .886.067c.221.516.528.696.74.696.213 0 .52-.18.74-.696l.035-.067a.5.5 0 0 1 .885.067c.22.516.527.696.74.696s.519-.18.74-.696m0-4a.5.5 0 0 1 .92.392c-.295.69-.871 1.304-1.66 1.304-.487 0-.892-.234-1.2-.574-.309.34-.713.574-1.2.574-.486 0-.892-.233-1.2-.574-.31.34-.714.574-1.2.574a.5.5 0 0 1 0-1c.212 0 .52-.18.74-.696l.034-.067a.5.5 0 0 1 .886.067c.221.516.528.696.74.696.213 0 .52-.18.74-.696l.035-.067a.5.5 0 0 1 .885.067c.22.516.527.696.74.696s.519-.18.74-.696M12 5.5a.5.5 0 0 0 .5.5h2.293L12 3.207z"/></svg>
       <span>[[BUSINESS NAME]] details</span>
     </div>
     <div class="elicit-body">

       <div class="elicit-group">
         <label class="elicit-question">What problem do you take off their plate? Pulled from your site, you do [[PRODUCT SHORT]] for [[AUDIENCE]], so this is the headache they feel before they call you.</label>
         <div class="elicit-pills" data-name="problem" data-multi="false">
           <button type="button" class="elicit-pill" data-value="[[PROBLEM OPT 1]]" style="border-radius:12px; padding:12px 14px; text-align:left; min-width:240px; box-shadow:0 1px 2px rgba(0,0,0,0.04)"><span style="font-size:13px; font-weight:500">[[PROBLEM OPT 1]]</span><br><span style="font-size:11px; color:var(--color-text-tertiary)">[[PROBLEM OPT 1 SOURCE]]</span></button>
           <button type="button" class="elicit-pill" data-value="[[PROBLEM OPT 2]]" style="border-radius:12px; padding:12px 14px; text-align:left; min-width:240px; box-shadow:0 1px 2px rgba(0,0,0,0.04)"><span style="font-size:13px; font-weight:500">[[PROBLEM OPT 2]]</span><br><span style="font-size:11px; color:var(--color-text-tertiary)">[[PROBLEM OPT 2 SOURCE]]</span></button>
           <button type="button" class="elicit-pill" data-value="[[PROBLEM OPT 3]]" style="border-radius:12px; padding:12px 14px; text-align:left; min-width:240px; box-shadow:0 1px 2px rgba(0,0,0,0.04)"><span style="font-size:13px; font-weight:500">[[PROBLEM OPT 3]]</span><br><span style="font-size:11px; color:var(--color-text-tertiary)">[[PROBLEM OPT 3 SOURCE]]</span></button>
         </div>
         <input type="text" class="elicit-other" data-name="problem_own" placeholder="Or type your own: the real headache you solve">
       </div>

       <div class="elicit-group">
         <label class="elicit-question">What makes them believe you can do it? The line that earns trust: a number, a named client, or a guarantee.</label>
         <div class="elicit-pills" data-name="proof" data-multi="false">
           <button type="button" class="elicit-pill" data-value="[[PROOF OPT 1]]" style="border-radius:12px; padding:12px 14px; text-align:left; min-width:240px; box-shadow:0 1px 2px rgba(0,0,0,0.04)"><span style="font-size:13px; font-weight:500">[[PROOF OPT 1]]</span><br><span style="font-size:11px; color:var(--color-text-tertiary)">[[PROOF OPT 1 SOURCE]]</span></button>
           <button type="button" class="elicit-pill" data-value="[[PROOF OPT 2]]" style="border-radius:12px; padding:12px 14px; text-align:left; min-width:240px; box-shadow:0 1px 2px rgba(0,0,0,0.04)"><span style="font-size:13px; font-weight:500">[[PROOF OPT 2]]</span><br><span style="font-size:11px; color:var(--color-text-tertiary)">[[PROOF OPT 2 SOURCE]]</span></button>
           <button type="button" class="elicit-pill" data-value="[[PROOF OPT 3]]" style="border-radius:12px; padding:12px 14px; text-align:left; min-width:240px; box-shadow:0 1px 2px rgba(0,0,0,0.04)"><span style="font-size:13px; font-weight:500">[[PROOF OPT 3]]</span><br><span style="font-size:11px; color:var(--color-text-tertiary)">[[PROOF OPT 3 SOURCE]]</span></button>
         </div>
         <input type="text" class="elicit-other" data-name="proof_own" placeholder="Or type your own: a number, a named client, or a guarantee">
       </div>

       <div class="elicit-group">
         <label class="elicit-question">What's the one thing you want them to do next? The single action the email drives towards.</label>
         <div class="elicit-pills" data-name="ask" data-multi="false">
           <button type="button" class="elicit-pill" data-value="[[ASK OPT 1]]">[[ASK OPT 1]]</button>
           <button type="button" class="elicit-pill" data-value="[[ASK OPT 2]]">[[ASK OPT 2]]</button>
           <button type="button" class="elicit-pill" data-value="[[ASK OPT 3]]">[[ASK OPT 3]]</button>
         </div>
         <input type="text" class="elicit-other" data-name="ask_own" placeholder="Or type your own: the one action you want them to take">
       </div>

     </div>
     <div class="elicit-footer">
       <button type="button" class="elicit-skip">Skip</button>
       <button type="button" class="elicit-submit">Save &amp; tailor my scores</button>
     </div>
   </form>
   ```
4. **Save and finish.** On submit, for each question take the chosen option, or the typed-own value if its box was filled (**own always overrides the pick**). Persist with `python3 scripts/brain_bridge.py save --skill cold-email --confirmed --base "<wf>/Claude HQ" name="…" product="…" audience="…" problem="…" proof="…" ask="…" deepDone=true` (writes to the brain; legacy stays as fallback). **`--confirmed` is required whenever the user has explicitly confirmed or corrected a business fact** — without it the brain refuses to replace confirmed identity, and the save result's `"rejected": [...]` lists any refused fields. If `rejected` is non-empty after a save the user asked for, re-run the same save with `--confirmed`. If they hit **Skip**, save nothing and run `python3 scripts/brain_bridge.py save --skill cold-email --base "<wf>/Claude HQ" deepSkips=+1`. Then show the locked one-line opener so they can grade against the new context.

### Completeness and never nagging
- Treat the profile as **complete the moment the deep round is done**, even if they skipped a question (e.g. wouldn't give proof). Set `deepDone:true` and go quiet. Never re-ask on later runs.
- One exception: when a missing **proof point** would clearly lift a specific email's score, you may ask for it **for that one email**, framed as a per-email opportunity, not a profile question. Never make it a gate, never store it as a pending question.

## GRADE mode
**Score with the engine, speak to the user in plain English.** Run `references/scoring-model.md` exactly: **meter pre-pass (§9 — run `scripts/meter.py` to count word count, self-reference ratio, links, reading grade, subject/question counts, then apply its floors/docks) →** gates in funnel order → Block A → caps. The meter makes the countable layer identical every run; judgement only fills the subjective axes. Then translate every internal term through `references/plain-language.md` before it reaches the user. The user never sees "gate", "Block A", "band", "pin", "ceiling" or evidence tags unless they ask for them.

### Default view — what the user always sees
Plain language, framed around replies, in this order:
1. **Score + plain label + one sentence.** `NN/100`, the plain label from `references/plain-language.md` (e.g. "Held back by one big thing"), and one line naming the single biggest thing costing replies. No band letter. If a cap applies, say it plainly ("capped until you fill the blanks, fill them and it jumps"), never "caps at C".
   - **No subject pasted → say so, never penalise.** If the pasted email has no `Subject:` line, treat the subject as *not provided*: don't fail it, don't dock the score (see scoring-model §2). One soft line on the card: "No subject detected — paste one and I'll score it, or I'll suggest a strong one." A suggested subject is a bonus, never graded against them.
   - **Lens line.** Open the verdict with the lens (from Profile section): cold B2B by default, or the saved/asked profile. Always visible so a B2C/follow-up user knows why it graded as it did.
   - **Archetype (verdict headline).** Assign exactly one archetype from `references/scoring-model.md` §8 (walk top-down, first match wins) and lead the verdict with its name + a one-line read, e.g. "The Pitch-Slap — opens with you, not them." Same email always returns the same archetype. The label names the *kind* of email; it never changes the score.
2. **What's working** — 2–3 short bullets, so they know what to keep.
3. **What's costing you replies** — the issues, ranked by impact. Each: a plain bold headline, one line on *why it costs replies* (say what the reader does, e.g. "they're gone by line two", never "fails the Relevance gate"), then `Fix:` one line. Tie each issue to one of the 7 factors in `references/plain-language.md`.
4. **Rewritten** — one improved version.
5. **Why this wins** — 1–2 plain lines, including the new score in plain terms ("now around 85/100").
6. **Two strategic calls** (always, after the copy — these move replies more than wording does):
   - **Price in the email?** Reflect the price default (no, unless the user said otherwise). If price is in, say plainly it hands a stranger an easy reason to bow out; default is no, sell the call.
   - **Is the list the real ceiling?** If the copy is strong but generic to the segment, say the lever now is a better-targeted list or a real trigger, not more wordsmithing. Never present this as a score cap (it no longer caps, v2.7).
7. Close with one line: *"Want the why? I can show the studies and the exact scoring behind any line."*

### On-request view — only if they ask
If the user asks to see the scoring or the data, reveal the engine exactly as the rubric produces it: gate pass/fails, Block A dimensions with 1–5 and evidence tags, flags fired (incl. the believability flag), caps applied, and the numeric re-grade of the rewrite. This layer is unchanged from the rubric; the redesign only moves it behind a request.

## Artefact output — the live scorecard card
After every GRADE, and after every BUILD (the draft is scored on the same rubric), render the result as the **one** live scorecard artefact (this is the thing the user looks at). Detail = `references/artefact-flow.md`.
1. Build the `DATA` object from the grade. The card is a **dual view**: `{lens, before, after}`, where `before` is the user's pasted email scored and `after` is the rebuild scored (omit `after` on a grade-only run and the Before/After toggle hides itself). Both emails always show; the toggle only re-scores. **Exact schema = `references/artefact-flow.md` §4** (per-view fields: score, band, tier_label, archetype, verdict, emailHeading, dims, gates, costing, working, subject, email_text, email_lines).
2. **One artefact, updated in place — decide, never ask.** Publish the scorecard HTML with whatever artifact tool the host provides, using the **same file path every run** so the first run creates the artefact and every later run republishes it to the same URL. ONE artefact, reused for every email, never a second. No artifact tool in this host → save the HTML and present that one file instead.
3. The artefact HTML = `references/scorecard-template.html` verbatim with `window.__SCORE_DATA__ = <script-safe minified DATA>;` injected into the marked placeholder — minify, then `.replace("<", "\\u003c")` (mandatory: a pasted email containing `</script>` would otherwise close the inline script and blank the card; see artefact-flow.md §3). The template renders itself from that data on load. **Only inject DATA — never hand-edit the shell or the content blocks, and never re-type the template: do the injection as a scoped replace (a small script or targeted edit of the placeholder line only), so the 90KB template is never re-authored by hand.**
4. In chat: one-line score + "opened your scorecard →" + the lens line. Keep the full teardown available on request.
5. **Close-out contract.** The scratch scorecard HTML is written to the temp/scratchpad folder, never the user's folder; the artefact is the only user-visible surface; present no files at the end of a run. Sole exception: no artifact tool exists, in which case present that one HTML file and nothing else.

**SHELL / CONTENT SEPARATION (for the incoming mesh shell).** `scorecard-template.html` keeps the v3 shell CSS in one clearly-labelled block and the scorecard content + render logic in another. When the developer's pixel-final shell lands, swap ONLY the shell block; the data binding and content are untouched. Maintain this separation in any future edit.

## BUILD mode
1. From the stored profile plus whatever the user gave at the door (Entry section), draft to the rubric's "5 looks like" anchors: them-led opener on a real signal, one concrete problem-moment **stated as fact, not hypothetical**, a single CTA at the right friction for the profile, profile-appropriate proof, tight and scannable, clean subject. **Open and close like a real email:** open with a greeting to the recipient by name ("Hi [Name],"), and close with a sign-off followed by the sender's name on its own line, with nothing after the name. A bare name is enough (it need not say "Kind regards"), but on a cold email there must always be a sign-off. Any sender bio or credibility line goes in the body, before the sign-off, never after it.
2. Produce **two variants** (different angle/voice) to avoid converging on one house style.
3. Never fabricate proof or personalisation — leave a clearly-marked blank for the user to fill, and say plainly it's capped until filled ("swap in a real result and this jumps").
4. Self-grade with the rubric internally, then **show the user plain English, not the machinery:**
   - The **email(s)** first.
   - **Why this works** — 3–4 short bullets, one per relevant factor from the 7 in `references/plain-language.md` (e.g. "Opens on something true about them, not you"). Give the plain score/label so they see it clears the bar.
   - **The one blank to fill** — name the single missing input (usually a real proof number) that would push it higher, and note price stays out of the email by default.
   - One line: *"Want the principles behind it, or the data? Just ask."*
5. On request, reveal the engine layer (which lever each part hits, the dimension scores, evidence tags) exactly as the rubric produces it.

## The outcome harness (calibration loop)
The model's one open blind spot is within-band ranking (a believable, concrete claim beats a hypothetical one even when both grade the same). Only live outcomes fix it. So:
- Whenever the user reports a **sent** email and its **real result** (reply %, replied y/n, booked, lost), **archive it to the ledger, linked to the exact version sent:** find the id first — `python3 scripts/ledger.py read --base "<wf>/Claude HQ" --skill cold-email --kind email.built --limit 10` — then `python3 scripts/ledger.py append --base "<wf>/Claude HQ" --skill cold-email --kind email.outcome --of <that id> --meta outcome="<what happened>" --meta band=<band>`. If the user is vague about which one they sent, ask in the same breath as the outcome; if you still can't tell, write it with no `--of` rather than guessing — an unlinked outcome is honest, a mislinked one poisons the dataset. Same silent, non-blocking rules as the ledger section above.
- **Ask for the outcome, or you will never have one.** As of 21 Aug 2026 the log holds nine `seed` rows and not one live result, because nothing ever prompts for it. So when a user returns to the skill having previously had an email built or graded, ask **once**, in one line, before anything else: *"Did you send the last one? What happened?"* Accept "don't know" and move on immediately — never a gate, never twice in a session, never a form.
- Periodically (or on request) review the archived outcomes (with `references/outcomes-log.md` as the calibration baseline) for pairs where similar-band emails had very different outcomes — those are calibration signal, especially for the believability lever. Surface them; don't silently change weights.

## Evidence
`references/evidence-base.md` is the citation backbone. When citing a number or principle, give the **tier and source**, never a bare figure. If challenged, point to the entry.

## Known limits — say these honestly when they bite
- Grades **copy, not list quality**; the lens (profile) carries the list assumption.
- **Templates cap at C** (can't verify personalisation that isn't rendered).
- **Within-band fine ranking** is still calibrating; trust the band over a 2–3 point gap.


## Version stamp + update check (house rule)

1. **Stamp.** The close-out of every run states this skill's name and version, read from the `version:` frontmatter at the top of this file (e.g. "cold-email-builder v1.0.0").
2. **Update check — best-effort, never blocking, at most once per conversation.** After the deliverable is produced, if web access is available in the session, fetch <https://raw.githubusercontent.com/bingley-ai/bingley-skills/main/plugins/bingley-sales/.claude-plugin/plugin.json> (give it ~5 seconds, then move on) and compare its `version` field to this file's `version:`. If they differ AND no update line has already appeared earlier in this conversation (from this or any sibling skill), append exactly one line to the close-out: "A newer version of this skill is out — get the update at bingley.ai." On later runs in the same conversation, skip the line even if versions still differ. If the fetch fails, times out, or the session has no web access: append nothing and never mention the check. The deliverable is never delayed or blocked by this step.
