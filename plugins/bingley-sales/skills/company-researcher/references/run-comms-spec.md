# Full Accounts Scan — Run Comms Spec

Exact copy the driving agent says to the user at each moment of a run. Use these lines verbatim. Substitute the `{…}` tokens at runtime.

## Voice rules (do not drift)
- Short, plain British English. Verdict/point first.
- No em dashes. No hyphens as connectors (use commas and full stops).
- Concrete numbers over vague reassurance. No hype, no fortune-cookie lines, no padding.
- This is product UX microcopy, not sales copy. Functional and tight.

## Estimate phrasing rule
Always give the time as a **range, never a single number** (false precision reads as a promise). Round to whole or half hours. Format: `roughly {X} to {Y} hours`. Build the range from companies ÷ 5 agents × per-company time, then pad to a sensible spread (e.g. 3.5 to 5 hours, not 4.2 hours). If the range crosses a night, see the partial case below.

---

## 1. PRE-RUN CONFIRM (with time estimate)

> That's {N} companies. Across 5 agents, roughly {X} to {Y} hours. Best left to run overnight. Output is the same ranked dashboard you get on a small run, Strong / Fair / Longshot per company with the full cheat-sheet drill-in. Run it?

If no business profile is loaded, append:

> One thing first: without your business profile this comes back as a browsable index, facts only, no Strong / Fair / Longshot ranking. Want to add the profile before I start, or run it unranked?

---

## 2. LARGE-LIST WARNING (above the new soft cap)

The old warn-at-100 / cap-at-500 is lifted. New behaviour:

**Between ~100 and ~1,000** — confirm only (use moment 1, no extra warning needed).

**At ~1,000 or more** — warn, then confirm:

> Heads up: that's {N} companies. A book that size runs across more than one night, the dashboard ships on a partial book first and fills in as agents finish. Numbers stay accurate as it goes. Happy to run it that way, or split the list if you'd rather have it all in one pass. Run it?

**Above ~2,000** — still run it. Say what the shape of the run is, then start:

> That's {N} companies, so this runs across roughly {NIGHTS} nights. I'll take them in order and the dashboard fills in as each batch finishes, so you get a usable ranked list after the first night rather than waiting for the whole thing. Starting now unless you want a different order.

⛔ **There is no cap above which this refuses.** Never tell the user their list is too long, never
ask them to split it and come back, and never hand the job to another skill. A long list is a
scheduling fact, not a reason to do nothing. The run is checkpointed and resumable, which is
exactly what makes an oversized list safe to just start.

---

## 3. PROGRESS / REASSURANCE (running unattended)

Say once, on kick-off, so the user can walk away:

> Running now. 5 agents, {N} companies, checkpointed every {checkpoint_n} so nothing's lost if it stops. Safe to close this and come back. If it's interrupted it picks up where it left off, it never restarts from zero. I'll have the dashboard ready when you're back.

Optional mid-run status line (only if asked "how's it going"):

> {done} of {N} done, {go_count} Strong so far. On track. Roughly {remaining} left.

---

## 4. COMPLETION

> Done. {N} companies scanned. {go_count} Strong, {maybe_count} Fair, {skip_count} Longshot. Dashboard's ready, ranked best fit first. Open it from the card above, click any row for that company's full cheat sheet.

If unranked (no profile):

> Done. {N} companies, browsable index ready, open it from the card above. Add your business profile and I'll rank the whole book Strong / Fair / Longshot in one more pass.

---

## 5. CRASH / RESUME

When a run was interrupted and is being resumed:

> Picking up from account {next_n} of {N}. The {done_n} already done are saved, I'm not re-running them. Carrying on now, same dashboard at the end.

If it stopped mid-account:

> Resuming from account {next_n} of {N}. The {done_n} finished are saved, the one it stopped on reruns clean. Carrying on now.

---

## 6. PARTIAL / OVERNIGHT-SHIFT (book too big for one night)

On kick-off, when the estimate crosses a night:

> This won't finish in one night. Here's how it works: the dashboard ships once the first batch is in, then fills out as the rest land. So you wake up to a working ranked list on a partial book, and it keeps completing through the day. Run it?

When the partial dashboard first ships overnight:

> Partial dashboard's ready, {done} of {N} scanned so far, ranked as they come in. The rest fill in through the day, numbers update live. Safe to start using it now.

When it finally completes:

> All done now. Full book in: {N} scanned, {go_count} Strong, {maybe_count} Fair, {skip_count} Longshot. The dashboard you've been using is now complete and final.

---

## Token reference
- `{N}` total companies on the list
- `{X}` / `{Y}` low / high end of the time range (whole or half hours)
- `{NIGHTS}` how many nights a very large book spans (there is NO cap that refuses a run)
- `{checkpoint_n}` companies per checkpoint write
- `{done}` / `{done_n}` companies finished · `{next_n}` next account to do
- `{go_count}` / `{maybe_count}` / `{skip_count}` verdict breakdown
- `{remaining}` rough time left
