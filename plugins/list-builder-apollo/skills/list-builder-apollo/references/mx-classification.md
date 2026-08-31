# MX classification — provider table and rationale

Read alongside Stage 4.6 of SKILL.md, which holds the implementation and output rules.

**Why this is free and worth doing.** `dig MX <domain>` resolves in under 100ms with no external API and no credit cost. Secure-email-gateway providers reject or bin a large share of cold mail before it reaches the inbox. Identifying gateway-protected domains pre-send lets the user route the list differently — slower warm-up cadence for the gateway slice, faster send for M365/Google, or exclude gateway entirely if deliverability is poor.

## Provider patterns

Substring match on the MX hostname, case-insensitive:

| MX hostname contains | Bucket | Provider string |
|---|---|---|
| `mimecast` | GATEWAY | `mimecast` |
| `barracuda`, `barracudanetworks` | GATEWAY | `barracuda` |
| `pphosted`, `proofpoint` | GATEWAY | `proofpoint` |
| `sophos`, `messagelabs` | GATEWAY | `sophos` |
| `titan.email`, `titanhq`, `spamtitan` | GATEWAY | `titanhq` |
| `mailcontrol`, `forcepoint` | GATEWAY | `forcepoint` |
| `iphmx`, `cisco` | GATEWAY | `cisco` |
| `trendmicro`, `trustwave` | GATEWAY | `trustwave` |
| `outlook.com`, `mail.protection.outlook.com` | M365 | `microsoft` |
| `google.com`, `googlemail.com`, `aspmx.l.google.com` | GOOGLE | `google` |
| anything else with valid MX | OTHER | raw MX hostname |
| no MX records returned | NO_MX | empty string |

If a recognisable secure-gateway hostname not yet in the table above appears in the OTHER pile during a run, surface it in the Stage 8 summary so it can be promoted to GATEWAY for the next run.
