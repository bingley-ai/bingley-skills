# File format specification (the blueprint)

Every Excel file the skill produces must match this spec exactly — Stage 6's sanity check enforces it.

## Workbook structure

Filename: `Prospects_[Niche]_MASTER.xlsx`. One file per niche.

**Filename rules:** replace spaces with underscores, strip punctuation, preserve case. "Wealth Management" → `Prospects_Wealth_Management_MASTER.xlsx`. "M&A Advisory" → `Prospects_MA_Advisory_MASTER.xlsx`. "SaaS / B2B" → `Prospects_SaaS_B2B_MASTER.xlsx`.

**Cross-geography collision rule:** if the same niche is being run for multiple geographies, use `Prospects_[Niche]_[Geo]_MASTER.xlsx`. Detect collision at Stage 0 master scan: if a master with the same niche already exists from a different geography, prompt the user once.

Four tabs in this order:
1. `[Niche] — Merged` (Prospects master tab)
2. `Latest Run` (regenerated each run, just this run's contacts)
3. `Filtered Out` (every dropped row with reason)
4. `Legend` (plain-English column explanations)

**Workbook-level metadata (xlsxwriter `set_custom_property`):**
- `run_niche` — niche string from Q1
- `run_geography` — from Q2
- `run_constraint` — verbatim user answer to Q7 (the screen/exclude constraint), or empty string if none. Travels with the file so the active constraint is always recoverable from the workbook.
- `run_date` — YYYY-MM-DD

## Column structure (19 columns; Tab 3 adds col T "Drop Reason")

| Col | Letter | Header | Width | Alignment | Notes |
|---|---|---|---|---|---|
| 1 | A | # | 5 | center | Sequential row number |
| 2 | B | Company | 32 | left | **Hyperlinked to firm website** |
| 3 | C | Employees | 11 | center | Actual integer post-enrichment, band placeholder pre |
| 4 | D | Rev Band | 12 | center | Verified band, or `~` prefix + ` (est)` suffix for estimate, or "Unknown" |
| 5 | E | Headcount Trend | 18 | center | "↑ Growing" / "→ Stable" / "↓ Shrinking" / "Unknown" |
| 6 | F | Contact Name | 28 | left | Full name combined |
| 7 | G | Title | 32 | left | |
| 8 | H | LinkedIn | 12 | center | **Visible "LinkedIn", URL as hidden hyperlink** |
| 9 | I | Company Phone | 18 | left | International format with country code (+44, +1, etc.) |
| 10 | J | Notes | 13 | left | SKILL-managed flags only (e.g. `catchall`). Never user outreach actions. |
| 11 | K | Email | 36 | left | Verified email from Apollo. No email = drop the row. |
| 12 | L | Background | 60 | left | 2-3 sentences industry-relevant. **wrap_text = FALSE**. |
| 13 | M | Source | 22 | center | "Niche Data" / "Apollo" / "Both" |
| 14 | N | Outreach Status | 16 | center | Cold / Sent / Replied / Booked / Dead |
| 15 | O | Run Date | 14 | center | YYYY-MM-DD |
| 16 | P | Run Niche | 16 | center | Niche string from Q1 |
| 17 | Q | User Notes | 30 | left | USER ONLY — outreach actions, personal annotations |
| 18 | R | First Name | 14 | left | For Instantly `{{firstName}}` merge tag |
| 19 | S | Last Name | 16 | left | For Instantly `{{lastName}}` merge tag |
| 20 | T | Drop Reason | 50 | left | **Filtered Out tab only** |

## Font rules

- **Default everywhere**: Calibri 11, black (#000000)
- **Header row**: Calibri 11 bold, white (#FFFFFF), background dark navy (#07131C), centered, frozen
- **Hyperlinks (Company B + LinkedIn H)**: Calibri 11, blue (#0563C1), single underline. Use xlsxwriter `font_color="#0563C1"` and `underline=True`.

## Row formatting

- **Row height**: locked 15pt for ALL rows. Never auto-grow.
- **Vertical alignment**: center on every cell.
- **Horizontal alignment**: per the column table above.

## Row colour rules

- Alternating by firm group: light grey `#F4F4F4` and white `#FFFFFF`. Each firm gets one colour, next firm switches.
- Flagged rows override with light orange `#FFE4CC`. Triggers: title score below 6, wrong-firm match, conflicting data, post-paid re-rank flags (retired headline, <12mo tenure, headcount outside band).
- Skill never applies bright yellow.
