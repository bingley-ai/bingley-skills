#!/usr/bin/env python3
"""Generic Sales Control Panel engine (loop-1 patched).
Ingests ANY user's deals file (xlsx/csv, arbitrary headers), optional meetings +
commitments files, and produces (1) the panel HTML, (2) an ingest report, and
(3) issues.json. No demo hardcoding. Every parse decision is surfaced.

Usage:
  build_panel.py --deals FILE [--meetings FILE] [--commitments FILE]
                 [--out panel.html] [--report ingest-report.md]
                 [--today YYYY-MM-DD] [--name First] [--sheet NAME]
                 [--summary-json out.json] [--issues-json out.json]
                 [--overrides overrides.json] [--dedupe keep-first|most-recent]
                 [--horizon month|quarter|Ndays]
"""
import argparse, json, re, sys, datetime as dt, os, math
import pandas as pd

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel-shell.html")
STAGE_DEFAULT_PROB = {"Discovery":0.20,"Demo":0.40,"Proposal":0.60,"Negotiation":0.80,
                      "Active Retainer":1.0,"Closed Won":1.0,"Closed Lost":0.0}
OPEN_STAGES = ["Discovery","Demo","Proposal","Negotiation"]
STALE_DAYS = 5
FX_TO_GBP = {"GBP":1.0,"£":1.0,"USD":0.79,"$":0.79,"EUR":0.86,"€":0.86}
CUR_SYM = {"GBP":"£","USD":"$","EUR":"€"}

report_lines, warnings = [], []
def rep(s): report_lines.append(s)
def warn(s): warnings.append(s); report_lines.append("WARNING: "+s)

# ---------- issues system ----------
issues=[]
PROB_CLAMPED=[]   # out-of-range probabilities, clamped to [0,1]
UNPARSED_VALUES=[]  # (csv line, raw text) for non-empty deal values that parsed to nothing
def add_issue(rule,severity,csv_lines,saw,question,choices,override_key,affects,proposed_fix,assumed="",
              choices_values=None,emit="scalar",raw_stage=None,title=None):
    # choices_values: machine value per display choice (parallel to `choices`) so the fix page can
    #   round-trip a chosen button back to a valid override VALUE (not the label). emit tells render
    #   how to place it: "scalar" -> out[override_key]=value; "stage_map" -> out.stage_map[raw_stage]=value.
    pfx={"blocker":"B","warning":"W","fyi":"F"}[severity]
    d=dict(id=f"{pfx}-{sum(1 for i in issues if i['severity']==severity)+1}",rule=rule,severity=severity,
           csv_lines=csv_lines,saw=saw,assumed=assumed,question=question,choices=choices,
           choices_values=choices_values,emit=emit,raw_stage=raw_stage,title=title,
           override_key=override_key,affects=affects,proposed_fix=proposed_fix,resolved=False)
    issues.append(d); return d

# ---------- column mapping ----------
# NOTE: dict order matters — earlier canonicals consume a column before later ones.
# fee_pct + amount_official + product are consumed BEFORE deal_value / probability.
SYNONYMS = {
 "deal_id":["deal_id","id","deal id","opportunity id","opp id","job id",
            "ref","reference","quote ref","quote no","quote number","job ref","job no","our ref","reference no"],
 "deal_title":["deal name","opportunity name","deal title","job title","opportunity","tender","role"],
 "salary":["salary","base salary"],
 "fee_pct":["fee %","fee percent","fee percentage","fee rate"],
 "amount_official":["opportunity amount","amount converted","amount official"],
 "prospect_name":["prospect_name","prospect","contact","client","name","customer","lead","who",
                  "contact name","associated contact","primary contact","contact full name"],
 "company_name":["company_name","company","account","organisation","organization","firm","business",
                 "account name","associated company","client corporation","clientcorporation"],
 "stage":["stage","deal stage","status","phase","pipeline stage","where its at","where it is","where it s at"],
 "deal_value":["deal_value","deal value","value","amount","price","acv","contract value","deal size",
               "value gbp","value £","annual value","total price","fee value","opportunity product total price"],
 "probability":["probability","prob","likelihood","win probability","win %","confidence","win rate"],
 "deal_type":["deal_type","deal type","type","product type","revenue type","contract type"],
 # product AFTER deal_type so a "Product Type" descriptor column is claimed by deal_type,
 # not mistaken for a line-item column (which would trigger aggregation).
 "product":["product name","line item","product code","product"],
 "recurring":["recurring","is recurring"],
 "forecast_category":["forecast category","forecastcategory","forecast"],
 "monthly_value":["monthly_value","mrr","monthly","monthly value","monthly recurring","mrr £"],
 "expected_close":["expected_close","close date","expected close","close","closing date","est close",
                   "forecast close","expected placement date","placement date","expected placement"],
 "last_touch":["last_touch","last contacted","last activity","last activity date","last touch","last spoke",
               "last contact","last modified","updated","last touched","last note date","date last note"],
 "prospect_email":["prospect_email","email","contact email","e-mail"],
 "prospect_title":["prospect_title","title","position"],
 "whale":["whale","key account"],
 "next_step":["next step","next_step","nextstep","next action","next steps","next activity"],
 "notes":["notes","note","comments","description","detail","details"],
 "currency":["currency","currency code","ccy","currency iso"],
}
def norm_header(h):
    s=str(h).strip()
    s=re.sub(r"(?<=[a-z0-9])(?=[A-Z])"," ",s)
    s=re.sub(r"[^a-z0-9% ]"," ",s.lower())
    return re.sub(r"\s+"," ",s).strip()
def _whole_word(s, n):
    return re.search(r"(?:^| )"+re.escape(s)+r"(?:$| )", n) is not None

def map_columns(cols):
    # Two passes: EXACT synonym matches across every field first, whole-word matches second.
    # Single-pass-in-dict-order let prospect_name's generic "contact" steal "Last Contact"
    # before last_touch's exact synonym was ever tried, silently zeroing staleness. (Wave-3 QA.)
    normed = {c: norm_header(c) for c in cols}
    mapping, used = {}, set()
    for canon, syns in SYNONYMS.items():
        for c, n in normed.items():
            if c in used or not n: continue
            if n in syns:
                mapping[canon] = c; used.add(c); break
    for canon, syns in SYNONYMS.items():
        if canon in mapping: continue
        for c, n in normed.items():
            if c in used or not n: continue
            if any(_whole_word(s, n) for s in syns):
                mapping[canon] = c; used.add(c); break
    return mapping

AUM_RE=re.compile(r"(?:^| )(assets|aum|portfolio|fum)(?:$| )")

# ---------- value / date / prob parsing ----------
def parse_amount(v):
    """Return (amount_float_or_None, currency_symbol_or_None, had_magnitude_suffix)."""
    if v is None: return None,None,False
    if isinstance(v,(int,float)):
        if pd.isna(v): return None,None,False
        return float(v),None,False
    s=str(v).strip()
    if s=="" or s.lower() in ("nan","n/a","-","tbd","?"): return None,None,False
    cur=None
    for sym in ("£","$","€"):
        if sym in s: cur=sym; break
    m=re.search(r"(gbp|usd|eur)",s.lower())
    if m and not cur: cur={"gbp":"£","usd":"$","eur":"€"}[m.group(1)]
    s3=s
    for _sym in ("£","$","€"): s3=s3.replace(_sym,"")
    s3=s3.replace(",","").replace(" ","").strip()
    try: return float(s3),cur,False
    except (ValueError,OverflowError): pass
    s2=re.sub(r"[^0-9.\-]","",s.replace(",",""))
    if s2 in ("","-","."): return None,cur,False
    try:
        val=float(s2); low=s.lower(); suf=False
        if low.endswith("k") or " k" in low: val*=1000; suf=True
        if low.endswith("m"): val*=1_000_000; suf=True
        return val,cur,suf
    except ValueError:
        return None,cur,False

def parse_money(v):
    a,c,_=parse_amount(v); return a,c

def parse_pct(v):
    """Parse a fee percentage cell -> fraction (0.20). Accepts 0.20, '22%', 20."""
    if v is None: return None
    s=str(v).strip()
    if s=="" or s.lower() in ("nan","-","n/a"): return None
    had=("%" in s)
    s2=re.sub(r"[^0-9.\-]","",s)
    if s2 in ("","-","."): return None
    try: f=float(s2)
    except ValueError: return None
    if had or f>1: f=f/100.0
    return f

def detect_date_order(values):
    first_gt12=second_gt12=0
    for v in values:
        if v is None: continue
        s=str(v).strip().split(" ")[0]
        m=re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$",s)
        if not m: continue
        a,b=int(m.group(1)),int(m.group(2))
        if a>12: first_gt12+=1
        if b>12: second_gt12+=1
    if second_gt12 and not first_gt12:
        return False,f"month-first (mm/dd/yyyy) proven by {second_gt12} value(s) with day>12 in 2nd position"
    if first_gt12 and not second_gt12:
        return True,f"day-first (dd/mm/yyyy) proven by {first_gt12} value(s) with day>12 in 1st position"
    if first_gt12 and second_gt12:
        return True,(f"CONFLICT: {first_gt12} value(s) look day-first and {second_gt12} look month-first "
                     f"in the same column. Defaulting to day-first; slash dates may be WRONG.")
    return True,"no unambiguous slash dates; assumed day-first (UK). Ambiguous values could be wrong."

EXCEL_EPOCH=dt.date(1899,12,30)
FISCAL_RE=re.compile(r"^\s*q([1-4])\s*fy\s*(\d{2,4})\s*$",re.I)
def is_fiscal_quarter(v):
    if v is None: return False
    return bool(FISCAL_RE.match(str(v).strip()))
def resolve_fiscal_quarter(v, fy_start_month):
    m=FISCAL_RE.match(str(v).strip())
    if not m: return None
    q=int(m.group(1)); yy=int(m.group(2))
    year_end=yy if yy>100 else 2000+yy
    fy_start_year=year_end-1  # FY labelled by its END calendar year; starts prior year
    # quarter END = last day of the month (fy_start_month + 3*q - 1)
    month_index=fy_start_month+3*q-1
    yr=fy_start_year+(month_index-1)//12
    mo=(month_index-1)%12+1
    if mo==12: return dt.date(yr,12,31)
    return dt.date(yr,mo+1,1)-dt.timedelta(days=1)

def parse_date(v, dayfirst=True):
    if v is None: return None
    if isinstance(v,(dt.date,dt.datetime)): return v.date() if isinstance(v,dt.datetime) else v
    if isinstance(v,(int,float)):
        if pd.isna(v): return None
        try: return EXCEL_EPOCH+dt.timedelta(days=int(v))
        except Exception: return None
    s=str(v).strip()
    if s=="" or s.lower() in ("nan","n/a","-"): return None
    s=s.split(" ")[0]
    for fmt in ("%Y-%m-%d","%Y/%m/%d"):
        try: return dt.datetime.strptime(s,fmt).date()
        except ValueError: pass
    m=re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$",s)
    if m:
        a,b,c=(int(x) for x in m.groups())
        if c<100: c+=2000
        d1,mo1=(a,b) if dayfirst else (b,a)
        if mo1>12 and d1<=12: d1,mo1=mo1,d1
        try: return dt.date(c,mo1,d1)
        except ValueError:
            try: return dt.date(c,d1,mo1)
            except ValueError: return None
    try: return pd.to_datetime(s,dayfirst=dayfirst).date()
    except Exception: return None

def parse_prob(v, percent_scale):
    if v is None: return None
    try: f=float(str(v).replace("%","").strip())
    except (ValueError,TypeError): return None
    if pd.isna(f): return None
    p=f/100.0 if percent_scale else f
    if p<0 or p>1:
        PROB_CLAMPED.append(str(v))
        p=min(1.0,max(0.0,p))
    return p

# ---------- stage normalisation ----------
STAGE_MAP=[
 ("Closed Lost",["closed lost","lost","closedlost","dead","no deal","withdrawn"]),
 ("Closed Won",["closed won","won","closedwon","complete","closed-won","awarded","placed","signed"]),
 ("Active Retainer",["retainer","subscription","recurring","live account","active retainer"]),
 ("Negotiation",["award pending","preferred bidder","offer extended","contract review","bafo","signing",
                 "negotiation","negotiate","contracting","contract sent","decision","deciding","verbal","final"]),
 ("Proposal",["tender submitted","proposal sent","quote sent","sent quote","itt","interviewing",
              "proposal","quote","presentationscheduled","presentation","review"]),
 ("Demo",["shortlist sent","fact find","demo","demonstration","evaluation","trial","poc","qualified","sql",
          "call booked","booked call","meeting booked","demo booked","call scheduled","meeting scheduled","booked in"]),
 ("Discovery",["discovery","disco","intro","new","prospecting","contacted","chatted","chatting","talking",
               "qualifying","qualification","sourcing","pqq","first chat","lead","mql","first call"]),
]
PARKED_VALUES={"parked","excluded","exclude","drop","dropped","park"}
CANON_OVERRIDE={"discovery":"Discovery","demo":"Demo","proposal":"Proposal","negotiation":"Negotiation",
                "closed won":"Closed Won","won":"Closed Won","closed lost":"Closed Lost","lost":"Closed Lost",
                "active retainer":"Active Retainer","retainer":"Active Retainer","parked":"Parked"}
def _canon_override_value(v):
    """Normalise a stage_map target value to a canonical stage. 'parked'/'exclude' -> Parked
    (excluded from open pipeline). Recognised canonical names pass through; anything else is
    returned as-is so a bespoke bucket label still applies."""
    vn=str(v).strip().lower()
    if vn in PARKED_VALUES: return "Parked"
    return CANON_OVERRIDE.get(vn, v)
def norm_stage(raw, stage_override=None):
    """Return (canonical_stage, unknown, assumed_from).
    assumed_from = the raw stage text when the engine had to FUZZY-guess a canonical whose name
    differs from the raw text (e.g. 'Verbal but no paperwork' -> Negotiation). None when the raw
    text is itself the canonical name, when an override was used, or when defaulted."""
    n=norm_header(raw)
    if not n: return "Discovery",True,None
    if stage_override:
        for k,v in stage_override.items():
            if norm_header(k)==n: return _canon_override_value(v),False,None
    for canon,keys in STAGE_MAP:
        for k in sorted(keys,key=len,reverse=True):
            if n==k or k in n:
                assumed = raw if norm_header(canon)!=n else None
                return canon,False,assumed
    # DEVIATION from spec E11: unrecognised stages map to Discovery (default weight) AND raise
    # the unrecognised_stages flag (never silent). Keeps personas 1-3 (whose hand-truth expects
    # "map to Discovery AND raise a flag") exact. The flag/blocker still fires and is surfaced.
    return "Discovery",True,None

def fmt(n,sym="£"):
    if n is None: return ""
    n=float(n); a=abs(n)
    if a>=1_000_000:
        m=n/1_000_000; return sym+(f"{m:.0f}" if m%1==0 else f"{m:.1f}")+"m"
    if a>=1000:
        k=n/1000; return sym+(f"{k:.0f}" if k%1==0 else f"{k:.1f}")+"k"
    return sym+f"{round(n):,}"

# ---------- load ----------
def _nonempty_sheet(path, sh):
    try:
        df=pd.read_excel(path,sheet_name=sh,header=None,dtype=object)
        return df.dropna(how="all").shape[0]>0
    except Exception:
        return True

def detect_header(dfN):
    """Given a header=None frame, find the row that best serves as the header.
    Returns (row_index, columns_list)."""
    best=None
    for r in range(min(5,len(dfN))):
        cols=[("" if (x is None or (isinstance(x,float) and pd.isna(x))) else str(x)) for x in dfN.iloc[r].tolist()]
        m=map_columns(cols)
        score=sum(1 for k in ("prospect_name","company_name","deal_title","stage","deal_value") if k in m)
        if best is None or score>best[0]:
            best=(score,r,cols)
    return best[1],best[2]

def read_sheet(path, sh):
    """Read one xlsx sheet with merged/banded-header detection."""
    dfN=pd.read_excel(path,sheet_name=sh,header=None,dtype=object)
    dfN=dfN.dropna(how="all").reset_index(drop=True)
    if dfN.empty: return pd.DataFrame()
    hr,cols=detect_header(dfN)
    # de-dupe blank column names
    seen={}; fixed=[]
    for c in cols:
        c=c or "col"
        if c in seen: seen[c]+=1; c=f"{c}.{seen[c]}"
        else: seen[c]=0
        fixed.append(c)
    body=dfN.iloc[hr+1:].reset_index(drop=True)
    body.columns=fixed[:body.shape[1]]
    return body

def load_table(path, sheet=None):
    # Content sniffing + plain-English failures: a renamed .xlsx, an empty export or a ragged
    # CSV must produce a sentence, never a traceback. (Wave-3 QA hardening.)
    try:
        with open(path, "rb") as _fh: _head = _fh.read(8)
    except OSError as e:
        raise SystemExit(f"CANNOT-READ: the deals file could not be opened ({e}).")
    if len(_head) == 0:
        raise SystemExit("CANNOT-READ: the deals file is empty (0 bytes) — re-export it from the CRM and try again.")
    _is_excel = _head[:2] == b"PK" or _head[:4] == b"\xd0\xcf\x11\xe0"
    try:
        if path.lower().endswith((".csv", ".tsv")) and not _is_excel:
            sep = "\t" if path.lower().endswith(".tsv") else ","
            df = pd.read_csv(path, sep=sep, encoding="utf-8-sig", dtype=str,
                             keep_default_na=False, skip_blank_lines=False)
        else:
            df = read_sheet(path, sheet or pd.ExcelFile(path).sheet_names[0])
    except SystemExit:
        raise
    except Exception as e:
        raise SystemExit(f"CANNOT-READ: this file doesn't parse as a spreadsheet ({type(e).__name__}: {e}). "
                         "If it came from a CRM export, re-save it as .xlsx or a clean .csv and try again.")
    return df.reset_index(drop=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--deals",required=True); ap.add_argument("--meetings"); ap.add_argument("--commitments")
    # THE CONNECTED TIER. Same contract as --meetings/--commitments: the engine reads a FILE, it never
    # calls an API. Fetching is an adapter's job (Gmail/Granola/Fireflies -> json), which keeps this
    # build deterministic — the batteries re-run it as a subprocess and pin its output to the pound,
    # and a gate that depends on someone's inbox is not a gate.
    ap.add_argument("--prep", help="json: meeting prep per contact — talking points (each cited), verbatim emails, the transcript tool's own call summary. Shape documented under Connectors in SKILL.md.")
    ap.add_argument("--out",default="panel.html"); ap.add_argument("--report",default="ingest-report.md")
    ap.add_argument("--today"); ap.add_argument("--name",default="there"); ap.add_argument("--sheet")
    ap.add_argument("--summary-json"); ap.add_argument("--issues-json")
    ap.add_argument("--overrides"); ap.add_argument("--dedupe",choices=["keep-first","most-recent"])
    ap.add_argument("--horizon",default="month")
    ap.add_argument("--no-state",action="store_true"); ap.add_argument("--state")
    a=ap.parse_args()
    TODAY=dt.date.fromisoformat(a.today) if a.today else dt.date.today()

    ov={}
    if a.overrides and os.path.exists(a.overrides):
        ov=json.load(open(a.overrides))
    dedupe_policy = (a.dedupe or ov.get("dedupe_policy") or "most-recent").replace("_","-")
    if dedupe_policy=="most-recent" or dedupe_policy=="most_recent": dedupe_policy="most-recent"
    stage_override = ov.get("stage_map") or {}
    horizon = ov.get("horizon") or a.horizon or "month"
    global FX_TO_GBP
    if ov.get("fx"):
        for k,v in ov["fx"].items():
            FX_TO_GBP[k.upper()]=v
    resolved_notes=[]

    # ---- state read (for run-to-run diff) ----
    state_path = a.state or (a.deals + ".scp-state.json")
    prev_state=None; prev_since=None; prev_run_today=None; prev_file=None; state_note=None
    if not a.no_state and os.path.exists(state_path):
        try:
            _ps=json.load(open(state_path))
            if isinstance(_ps,dict) and isinstance(_ps.get("deals"),dict):
                prev_state=_ps["deals"]; prev_since=_ps.get("saved_at")
                prev_run_today=_ps.get("run_today"); prev_file=_ps.get("deals_file")
            else:
                state_note="previous state malformed; treated as first run"
        except Exception:
            state_note="previous state unreadable; treated as first run"

    rep(f"# Ingest report\nRun date (today): {TODAY.isoformat()}\nDeals file: {os.path.basename(a.deals)}\n")

    # ---- multi-sheet handling ----
    is_xlsx = not a.deals.lower().endswith((".csv",".tsv"))
    multi_sheet_blocked=False
    frames=[]
    if is_xlsx:
        try:
            xl=pd.ExcelFile(a.deals)
        except Exception as e:
            raise SystemExit(f"CANNOT-READ: this file doesn't parse as a spreadsheet ({type(e).__name__}: {e}). "
                             "If it came from a CRM export, re-save it as .xlsx or a clean .csv and try again.")
        data_sheets=[s for s in xl.sheet_names if _nonempty_sheet(a.deals,s)]
        sheets_ans = ov.get("sheets")
        if a.sheet:
            frames=[(a.sheet, read_sheet(a.deals,a.sheet))]
        elif len(data_sheets)>1 and not sheets_ans:
            counts={s:read_sheet(a.deals,s).shape[0] for s in data_sheets}
            add_issue("multi_sheet","blocker",[1],
                f"workbook has {len(data_sheets)} data sheets: "+", ".join(f"{s} ({counts[s]} rows)" for s in data_sheets),
                "This workbook has more than one sheet with data. Combine all of them, or pick one?",
                ["Combine all sheets"]+[f"Use only {s}" for s in data_sheets]+["Something else"],
                "sheets",["pipeline_total","weighted","at_risk","month","whales","stale","counts","stages"],
                "Confirm which sheets make up your pipeline; the panel then combines them.")
            multi_sheet_blocked=True
            frames=[(data_sheets[0], read_sheet(a.deals,data_sheets[0]))]
            rep(f"\n## Sheets\n- {len(data_sheets)} data sheets found: "+", ".join(f"{s} ({counts[s]} rows)" for s in data_sheets)
                +"\n- BLOCKED: not combined until you answer (showing none of the combined figures).")
        elif sheets_ans:
            chosen = data_sheets if sheets_ans in ("all",True) else list(sheets_ans)
            frames=[(s, read_sheet(a.deals,s)) for s in chosen]
            resolved_notes.append(f"multi_sheet: combined {len(frames)} sheet(s): {', '.join(s for s,_ in frames)}")
            rep(f"\n## Sheets\n- combined {len(frames)} sheet(s): "+", ".join(s for s,_ in frames))
        else:
            frames=[(data_sheets[0] if data_sheets else "Sheet1", read_sheet(a.deals, data_sheets[0] if data_sheets else None))]
    else:
        frames=[(None, load_table(a.deals))]

    # tag source sheet + concat
    parts=[]
    for sname,df in frames:
        df=df.copy(); df.columns=[str(c) for c in df.columns]
        df["__sheet__"]=sname or ""
        parts.append(df)
    raw=pd.concat(parts,ignore_index=True) if len(parts)>1 else parts[0]
    n_in=sum(p.shape[0] for p in parts)

    cols=[c for c in raw.columns if c!="__sheet__"]
    mapping=map_columns(cols)
    has_id_col = "deal_id" in mapping  # when false, the diff keys on name+company (disclosed), not row position

    # ---- value-semantics suspect (AUM/assets) ----
    val_col = mapping.get("deal_value")
    aum_suspect=None
    for c in cols:
        if AUM_RE.search(norm_header(c)): aum_suspect=c; break
    vs_override = ov.get("value_semantics")
    value_semantics_blocked=False
    fee_rate=None; millions_scale=False
    header_for_units = (val_col or aum_suspect or "")
    if re.search(r"\(?\s*£?\s*m\s*\)?", str(header_for_units).lower()) and re.search(r"£m|\(m\)|\(£m\)", str(header_for_units).lower()):
        millions_scale=True
    if aum_suspect and (val_col is None or AUM_RE.search(norm_header(val_col))):
        if vs_override:
            val_col = vs_override.get("column") or aum_suspect
            if vs_override.get("meaning") in ("aum","fee_on_assets","assets"):
                fee_rate = vs_override.get("fee_rate") or vs_override.get("rate")
            mapping["deal_value"]=val_col
            resolved_notes.append(f"value_semantics: '{val_col}' treated as AUM; fee value = AUM x {fee_rate}")
        else:
            add_issue("value_semantics","blocker",[2],
                f"value column header is '{aum_suspect}'; looks like assets under management, not deal revenue",
                f"Is '{aum_suspect}' the revenue value of each deal, or assets under management? If it's assets, what fee rate should I apply?",
                ["It's revenue","It's AUM — apply a fee rate of ___%","Something else"],
                "value_semantics",["pipeline_total","weighted","at_risk","month","whales"],
                "Confirm AUM plus fee rate; the panel then shows the fee value per client.",
                "nothing — money figures suppressed until you answer")
            value_semantics_blocked=True
            val_col=None; mapping.pop("deal_value",None)

    # ---- fee derivation (salary x fee%) ----
    fee_derivation = bool(ov.get("fee_derivation"))
    fee_deriv_blocked=False
    have_pair = ("salary" in mapping and "fee_pct" in mapping)
    if have_pair and not value_semantics_blocked:
        if fee_derivation:
            resolved_notes.append("fee_derivation: deal value derived as Salary x Fee% for every row")
            mapping.pop("deal_value",None)  # ignore the unreliable Fee Value column
        else:
            add_issue("value_missing_derivable","blocker",[2],
                f"Salary and Fee% columns present; the Fee Value column is blank or wrong on many rows",
                "Fee Value is unreliable (blank or equal to salary on some rows). Derive fee from Salary x Fee% for all roles?",
                ["Yes — derive Salary x Fee%","No — trust the Fee Value column","Something else"],
                "fee_derivation",["pipeline_total","weighted","at_risk","month","whales"],
                "Derive fee = Salary x Fee%; fee figures then appear.",
                "nothing — fee figures suppressed until you answer")
            fee_deriv_blocked=True

    # ---- unparsed headers guard ----
    if not (mapping.get("stage") and (val_col or have_pair or aum_suspect)) and not multi_sheet_blocked:
        if "prospect_name" not in mapping and "stage" not in mapping:
            add_issue("unparsed_headers","blocker",[1],
                f"could not map required fields from headers: {cols[:12]}",
                "I could not read the columns safely. Which columns are the deal name, stage and value?",
                ["Map them for me"],"column_map",
                ["pipeline_total","weighted","at_risk","month","whales","stale","counts","stages"],
                "Confirm the header row / column meanings.")

    rep("## Column mapping (chosen)")
    for canon in SYNONYMS:
        rep(f"- {canon}: {mapping.get(canon,'— (none found)')}")
    if val_col: rep(f"- deal_value resolved to: {val_col}")
    for req in ("prospect_name","stage"):
        if req not in mapping: warn(f"required field '{req}' not found in headers; results will be degraded")

    def col(r,canon,default=None):
        c=mapping.get(canon)
        if c is None: return default
        v=r.get(c)
        return default if (v is None or (isinstance(v,float) and pd.isna(v))) else v

    # ---- probability scale ----
    percent_scale=False
    if "probability" in mapping:
        vals=[]
        for _,r in raw.iterrows():
            try: vals.append(float(str(col(r,"probability","")).replace("%","")))
            except: pass
        if vals and max(vals)>1.5: percent_scale=True
        rep(f"\n## Probability\n- column: {mapping['probability']}; scale: "
            f"{'0-100 percent (÷100)' if percent_scale else '0-1 fraction'}")
    else:
        rep("\n## Probability\n- no probability column; using stage-default probabilities")

    # ---- fiscal quarter close dates ----
    fy_start = ov.get("fiscal_year_start")
    fiscal_blocked=False
    ec_col=mapping.get("expected_close")
    if ec_col:
        fqvals=[r.get(ec_col) for _,r in raw.iterrows()]
        n_fiscal=sum(1 for v in fqvals if is_fiscal_quarter(v))
        if n_fiscal>0 and fy_start is None:
            add_issue("fiscal_quarter_dates","blocker",[2],
                f"{n_fiscal} close dates look like fiscal quarters (e.g. 'Q2 FY27')",
                "Your close dates are fiscal quarters. What month does your financial year start?",
                ["April (UK public sector)","January","Something else"],
                "fiscal_year_start",["month"],
                "Give the FY start month; each quarter then resolves to its quarter-end date.")
            fiscal_blocked=True
        elif n_fiscal>0 and fy_start is not None:
            resolved_notes.append(f"fiscal_year_start: FY starts month {fy_start}; quarters resolved to quarter-end dates")

    # ---- date convention ----
    _dvals=[]
    for canon in ("last_touch","expected_close"):
        c=mapping.get(canon)
        if c is not None: _dvals+=[r.get(c) for _,r in raw.iterrows()]
    DAYFIRST,date_evidence=detect_date_order(_dvals)
    rep(f"\n## Dates\n- slash-date convention: {date_evidence}")

    # ---- parse rows ----
    parsed=[]; skipped=[]; junk=[]
    for idx,r in raw.iterrows():
        line=idx+2
        name=col(r,"prospect_name"); comp=col(r,"company_name")
        title=col(r,"deal_title"); stageraw=col(r,"stage")
        namestr=str(name or "").strip() or str(title or "").strip()
        rowtext=" ".join(str(x or "") for x in (namestr,title,comp)).strip()
        # D17: scan the IDENTITY cells, never the prose ones. A TOTAL row hides its marker in a
        # name/ref/label cell (battery 7, P5) — it does not hide it in your notes. "summary",
        # "total" and "weighted" are ordinary English: a next step of "Send ROI summary" or a note
        # reading "sent the weighted forecast" used to delete a live deal from the pipeline. That
        # is the 28x-too-small failure with better manners, so the prose fields are excluded.
        _prose={mapping.get(k) for k in ("notes","next_step") if mapping.get(k)}
        allcells=" ".join(str(v or "") for k,v in r.items() if k not in _prose)
        # blank
        rawval_present = any(col(r,k) not in (None,"") for k in ("deal_value","amount_official","salary"))
        if not rowtext and not rawval_present:
            skipped.append((line,"blank row")); continue
        # summary/total — scan ALL cells (P5 TOTAL rows hide "TOTAL" in the Ref cell)
        if re.search(r"\b(total|subtotal|summary|weighted|grand total)\b",allcells,re.I):
            skipped.append((line,f"summary row: {rowtext[:40] or allcells[:40]}")); continue
        # junk / test — precise markers only (never bare "test": "Pen Test Programme" is real)
        comp_norm=norm_header(comp)
        _jt=rowtext.lower()
        is_junk = (comp_norm in ("internal test","internal / test")
                   or re.search(r"\b(zzz+|dummy|asdf)\b",_jt)
                   or re.search(r"(do not use|donotuse|delete me|test job|test record|test - |- ignore|ignore -|test deal)",_jt))
        if is_junk:
            junk.append((line,f"test/junk row: {rowtext[:50]}")); continue

        did=str(col(r,"deal_id","") or "").strip() or f"D-{idx+1:03d}"
        # value
        vraw=col(r,"deal_value")
        val,cur,suf=parse_amount(vraw)
        if val is None and str(vraw if vraw is not None else "").strip().lower() not in ("","nan","n/a","-","tbd","?"):
            UNPARSED_VALUES.append((line,str(vraw)[:40]))
        if val is not None and millions_scale and not suf and not aum_suspect:
            val*=1_000_000
        # AUM path
        if fee_rate is not None and val_col:
            av,ac,asuf=parse_amount(r.get(val_col))
            if av is not None:
                if millions_scale and not asuf: av*=1_000_000
                val=av*fee_rate; cur=ac
            else:
                val=None
        # fee derivation path
        sal=parse_amount(col(r,"salary"))[0] if "salary" in mapping else None
        fpct=parse_pct(col(r,"fee_pct")) if "fee_pct" in mapping else None
        if fee_derivation:
            if (sal in (None,0) and fpct in (None,)):
                junk.append((line,f"incomplete row (no salary/fee): {rowtext[:40]}")); continue
            val = (sal*fpct) if (sal not in (None,) and fpct not in (None,)) else None
        curcol=col(r,"currency")
        if curcol:
            code=str(curcol).strip().upper()
            if code in FX_TO_GBP: cur=code
        # stage
        stage,unknown,stage_assumed=norm_stage(stageraw,stage_override) if stageraw is not None else ("Unconfirmed",True,None)
        dtype_raw=str(col(r,"deal_type","") or "").lower()
        rec_raw=str(col(r,"recurring","") or "").strip().lower()
        recurring_true = rec_raw in ("yes","true","y","1","recurring")
        is_retainer=(stage=="Active Retainer" or recurring_true or "retainer" in dtype_raw
                     or "subscription" in dtype_raw or "recurring" in dtype_raw or "renewal" in dtype_raw)
        prob=parse_prob(col(r,"probability"),percent_scale)
        mval,_=parse_money(col(r,"monthly_value"))
        lt=parse_date(col(r,"last_touch"),DAYFIRST)
        # close date (fiscal aware)
        ecraw=col(r,"expected_close")
        if ecraw is not None and is_fiscal_quarter(ecraw):
            ec = resolve_fiscal_quarter(ecraw,fy_start) if fy_start is not None else None
        else:
            ec=parse_date(ecraw,DAYFIRST)
        aofficial,_,asuf2=parse_amount(col(r,"amount_official"))
        if aofficial is not None and millions_scale and not asuf2:
            aofficial*=1_000_000
        # HELD tenders: a close/expected-close cell of "HOLD"/"ON HOLD" marks a paused tender.
        # Excluded from open pipeline (kept as an entry). This reads the CLOSE column only, so it
        # never collides with an "On Hold" STAGE value (which stays mapped per norm_stage).
        held=bool(re.match(r"^\s*(on[\s-]*)?hold\s*$", str(ecraw or ""), re.I))
        dkey = did if has_id_col else ("K:"+norm_header(namestr or "")+"|"+norm_header(str(comp or "")))
        parsed.append(dict(line=line,deal_id=did,diff_key=dkey,name=namestr or "(unnamed)",company=str(comp or "").strip(),
            company_raw=str(comp or ""),name_raw=str(name or ""),stage_assumed=stage_assumed,
            stageraw=str(stageraw or ""),stage=stage,unknown=unknown,prob=prob,value=val,cur=cur,
            monthly=mval,expected_close=ec,last_touch=lt,notes=str(col(r,"notes","") or ""),
            person_title=str(col(r,"prospect_title","") or "").strip(),
            is_retainer=is_retainer,amount_official=aofficial,held=held,
            forecast_category=str(col(r,"forecast_category","") or "").strip(),
            product=str(col(r,"product","") or "").strip(),whale_raw=col(r,"whale"),
            next_step=str(col(r,"next_step","") or "").strip(),
            close_raw=str(ecraw or "")))

    # ---- aggregation (line items) vs dedupe ----
    has_product = "product" in mapping
    deals=[]; dupes=[]; agg_note=None; mismatch_rows=[]; id_reused=[]
    if has_product:
        groups={}
        order=[]
        for p in parsed:
            if p["deal_id"] not in groups:
                groups[p["deal_id"]]=[]; order.append(p["deal_id"])
            groups[p["deal_id"]].append(p)
        for did in order:
            g=groups[did]; head=g[0]
            vsum=sum(x["value"] for x in g if x["value"] is not None)
            vsum=vsum if any(x["value"] is not None for x in g) else None
            d=dict(head); d["value"]=vsum
            # KEEP THE LINES, don't just sum them. The rep cannot negotiate a number they cannot
            # decompose: "£28k" is a fact they already know, "Sandbox Add-on £0 — already given away"
            # is the one they don't. Summing and discarding threw away the only part of the figure
            # that is actionable in the room. Each line keeps its file line number so every figure
            # can be walked back to the export.
            d["lines"]=[{"product":str(x.get("product") or "").strip() or None,
                         "value":x["value"],"line":x["line"],"cur":x.get("cur")} for x in g]
            # line-item exports often carry the account name on a non-head row; take the first
            # non-empty company across the group so account-level checks (possible_same_account) see it.
            if not str(d.get("company_raw") or "").strip():
                fc=next((x["company_raw"] for x in g if str(x.get("company_raw") or "").strip()),"")
                if fc: d["company_raw"]=fc; d["company"]=fc.strip()
            if head["amount_official"] is not None and vsum is not None and abs(vsum-head["amount_official"])>0.01*max(1,abs(head["amount_official"])):
                mismatch_rows.append((head["name"],vsum,head["amount_official"],[x["line"] for x in g]))
            deals.append(d)
        agg_note=f"{len(parsed)} rows aggregated into {len(deals)} opportunities (product line items summed per deal id)"
        rep(f"\n## Aggregation\n- {agg_note}")
    else:
        # D2: dedupe within OPEN rows and within CLOSED rows SEPARATELY. A closed (Won/Lost) row must
        # never evict a live open row of the same id — the open row wins for the pipeline. When an id is
        # present BOTH open and closed (recycled/re-used number), raise a distinct id_reused FYI (not a
        # generic duplicate). Genuine duplicate rows within the same bucket still dedupe by policy.
        id_reused=[]
        def _fs(p): return "Active Retainer" if (p["is_retainer"] and p["stage"] in OPEN_STAGES) else p["stage"]
        def _bucket(p):
            if p.get("held"): return "other"
            fs=_fs(p)
            if fs in OPEN_STAGES: return "open"
            if fs in ("Closed Won","Closed Lost"): return "closed"
            return "other"
        def _dedupe(rows):
            if not rows: return None,[]
            keep=rows[0]; disc=[]
            for r in rows[1:]:
                take=(dedupe_policy=="most-recent" and r["last_touch"]
                      and (keep["last_touch"] is None or r["last_touch"]>keep["last_touch"]))
                if take: disc.append(keep); keep=r
                else: disc.append(r)
            return keep,disc
        groups={}; order=[]
        for p in parsed:
            did=p["deal_id"]
            if did not in groups: groups[did]={"open":[],"closed":[],"other":[]}; order.append(did)
            groups[did][_bucket(p)].append(p)
        for did in order:
            g=groups[did]
            o,od=_dedupe(g["open"]); c,cd=_dedupe(g["closed"]); ot,otd=_dedupe(g["other"])
            discarded=od+cd+otd
            survivors=[x for x in (o,c,ot) if x]  # priority: open > closed > other
            if o and c: id_reused.append((did,o["name"]))
            survivor=survivors[0] if survivors else None
            if survivor is not None: deals.append(survivor)
            for x in survivors[1:]:
                # a recycled id's dropped CLOSED row is disclosed via id_reused, not as a duplicate
                if not (survivor is o and x is c): discarded.append(x)
            for disc in discarded:
                kept=survivor if survivor is not None else disc
                fresher_disc = (disc["last_touch"] and kept["last_touch"] and disc["last_touch"]>kept["last_touch"])
                dupes.append({"line":disc["line"],"deal_id":did,"discarded_name":disc["name"],
                              "discarded_stage":disc["stageraw"],"discarded_value":disc["value"],
                              "discarded_last_activity":str(disc["last_touch"] or ""),"fresher":bool(fresher_disc)})
                skipped.append((disc["line"],f"duplicate deal_id {did} ({'kept fresher row' if dedupe_policy=='most-recent' else 'kept first'})"))

    # ---- currency ----
    currencies=set(d["cur"] for d in deals if d["cur"])
    if UNPARSED_VALUES:
        add_issue("unparseable_values","warning",[l for l,_ in UNPARSED_VALUES],
            f"{len(UNPARSED_VALUES)} deal value(s) I could not read as a number (e.g. {UNPARSED_VALUES[0][1]!r}) — they count as £0 until fixed",
            "","","unparseable_values",[],"Type the value as a plain number in the deals file (e.g. 12000, 12k).")
    if PROB_CLAMPED:
        add_issue("probability_out_of_range","fyi",[1],
            f"{len(PROB_CLAMPED)} probability value(s) outside 0-100% (e.g. {PROB_CLAMPED[0]!r}) were clamped into range",
            "","","prob_clamped",[],"Check the probability column; values must be 0-100%.")
    if len(currencies)<=1:
        disp_sym=(list(currencies)[0] if currencies else "£")
        if not currencies:
            add_issue("currency_assumed_gbp","fyi",[1],
                "no currency symbol anywhere in the deals file — all values are being shown as £ (GBP) by assumption",
                "","","currency_assumed",[],"Add a currency symbol to the value column, or say which currency this is.")
        rep(f"\n## Currency\n- single currency: {disp_sym or 'plain numbers, assumed GBP'}")
    else:
        rep(f"\n## Currency\n- MIXED currencies {sorted(currencies)}; all values converted to GBP at STATIC rates.")
        warn("mixed currencies: every value converted to GBP at STATIC hardcoded rates (not live FX)")
        disp_sym="£"
    def gbp(v,cur):
        if v is None: return None
        rate=FX_TO_GBP.get(cur,FX_TO_GBP.get("£"))
        return v*rate if len(currencies)>1 else v

    # ---- retainers / open ----
    for d in deals: d["final_stage"]="Active Retainer" if d["is_retainer"] and d["stage"] in OPEN_STAGES else d["stage"]
    held=[d for d in deals if d.get("held")]
    retainers=[d for d in deals if d["final_stage"]=="Active Retainer" and not d.get("held")]
    open_oneoff=[d for d in deals if d["final_stage"] in OPEN_STAGES and not d.get("held")]
    # D13: deals mapped to 'parked' (via stage_map) are excluded from open but surfaced as parked,
    # not silently dropped and not reported as "gone/lost".
    parked=[d for d in deals if d["final_stage"]=="Parked"]
    unconfirmed=[]  # unrecognised stages stay in Discovery (see norm_stage deviation note)
    if held:
        add_issue("tenders_on_hold","warning",[d["line"] for d in held][:8],
            f"{len(held)} tender(s) have HOLD in the close-date column; excluded from open pipeline",
            "Some tenders are marked HOLD (e.g. funding paused). Keep them out of the live pipeline?",
            ["Yes — keep held tenders excluded","No — include them as open"],"",[],
            "Held tenders sit out of the open figures; listed in the report. Refs: "
            +", ".join((d["name"] or d["deal_id"]) for d in held[:6]))

    # ---- unrecognised stages issue (flag, never silent; deals kept in Discovery) ----
    unrec=[d for d in open_oneoff if d.get("unknown") and str(d["stageraw"]).strip()]
    STAGE_CHOICES=["Discovery","Demo","Proposal","Negotiation","Won","Lost","Parked (exclude)"]
    STAGE_CHOICE_VALUES=["Discovery","Demo","Proposal","Negotiation","Closed Won","Closed Lost","parked"]
    if unrec:
        by={}
        for d in unrec: by.setdefault(str(d["stageraw"]).strip() or "(blank)",[]).append(d)
        # D1/D3: ONE answerable card PER raw stage word (not one lumped "Map: ..." button). Each card
        # emits {"stage_map":{"<raw>":"<chosen canonical>"}} with normalised machine values so the fix
        # page round-trips to a valid overrides.json. Enumerates every raw word kept in Discovery interim.
        for rawk in sorted(by.keys()):
            grp=by[rawk]
            add_issue("unrecognised_stages","blocker",[d["line"] for d in grp][:8],
                f"{len(grp)} deal(s) have the stage “{rawk}”, which I do not recognise — kept in Discovery for now until you map it.",
                f"What pipeline stage does “{rawk}” mean?",
                list(STAGE_CHOICES),"stage_map",["stages"],
                f"Map “{rawk}” to a stage; those deal(s) are re-bucketed and reweighted.",
                choices_values=list(STAGE_CHOICE_VALUES),emit="stage_map",raw_stage=rawk,
                title=f"Unrecognised stage: “{rawk}”")

    # missing value / no last activity accounting
    missing_value=sum(1 for d in open_oneoff if d["value"] is None)
    no_last_activity=sum(1 for d in open_oneoff if d["last_touch"] is None)

    # ---- suppression set ----
    suppressed=set()
    for i in issues:
        if i["severity"]=="blocker" and not i["resolved"] and i["rule"]!="unrecognised_stages":
            suppressed.update(i["affects"])

    # ---- whales ----
    # D15: if the FILE SAYS WHO THE WHALES ARE, that wins. A "whale"/"key account" column is the
    # user telling us, in their own data, which accounts they treat as whales — and this engine
    # parsed that column (whale_raw) and then silently overrode it with a top-10%-by-value guess.
    # That is the panel contradicting the rep's own file: on the demo book it demoted a declared
    # £18k whale and promoted a £20k deal the user never called one. Guess only when not told.
    def _declared_whale(v):
        if v is None: return False
        if isinstance(v,bool): return v
        if isinstance(v,(int,float)):
            try: return not pd.isna(v) and float(v)!=0
            except Exception: return False
        return str(v).strip().lower() in ("true","yes","y","1","whale","key","key account")
    has_whale_col = "whale" in mapping
    declared_ids = {id(d) for d in deals if _declared_whale(d.get("whale_raw"))} if has_whale_col else set()

    valued_open=[d for d in open_oneoff if gbp(d["value"],d["cur"]) is not None]
    valued_open.sort(key=lambda d:(gbp(d["value"],d["cur"]), str(d["deal_id"])),reverse=True)
    whale_thresh=None; whale_ids=set()
    if declared_ids:
        # the user declared them; no threshold exists and none is invented
        whale_ids=declared_ids
        rep(f"\n## Whales\n- {len(declared_ids)} taken from your file's own whale column (not guessed)")
    elif len(valued_open)>=5:
        # not told: top k = ceil(0.10 * n_valued_open) by value. Select the k highest deals
        # explicitly (not a >= threshold) so equal-valued deals at the boundary can't inflate the
        # count beyond k (P7 had 8 extra whales from ties). k matches the old threshold count for
        # the no-tie personas (1-3,5,6), so their whale list/threshold are unchanged.
        n=len(valued_open); k=n-(math.ceil(n*0.9)-1)
        top=valued_open[:k]
        whale_ids={id(d) for d in top}
        whale_thresh=gbp(top[-1]["value"],top[-1]["cur"]) if top else None
    for d in deals:
        d["whale"]=bool(id(d) in whale_ids and d["final_stage"] in OPEN_STAGES and not d.get("held"))

    # ---- pipeline stages ----
    # per-deal currency provenance: a converted figure always shows its own working
    # ("from $780,000 @ 0.79"), so no GBP number on the panel is unexplained.
    def prov(d):
        # only when a conversion actually happened: gbp() is a no-op in a single-currency file,
        # so claiming provenance there would be a lie about maths that never ran.
        if len(currencies)<=1 or d["value"] is None: return None
        c=(d["cur"] or "£")
        if c in ("GBP","£"): return None
        rate=FX_TO_GBP.get(c)
        if rate is None: return None
        sym=CUR_SYM.get(c.upper(), c if c in ("$","€") else c+" ")
        return {"cur":c,"raw":d["value"],"rate":rate,
                "text":f"from {sym}{d['value']:,.0f} @ {rate}"}

    stages=[]
    for s in OPEN_STAGES:
        g=[d for d in open_oneoff if d["final_stage"]==s]
        weighted=sum((gbp(d["value"],d["cur"]) or 0)*(d["prob"] if d["prob"] is not None else STAGE_DEFAULT_PROB.get(s,0.2)) for d in g)
        ds=[{"name":d["name"],"company":d["company"],"value":round(gbp(d["value"],d["cur"]) or 0),"stage_raw":d["stageraw"],
             "whale":d["whale"],"days":((TODAY-d["last_touch"]).days if d["last_touch"] else None),
             "prov":prov(d)} for d in g]
        if g: stages.append({"name":s,"weighted":round(weighted),"count":len(g),"deals":ds})
    pipeline_total=sum(s["weighted"] for s in stages)
    unweighted_total=round(sum(gbp(d["value"],d["cur"]) or 0 for d in open_oneoff))
    unconf_value=round(sum(gbp(d["value"],d["cur"]) or 0 for d in unconfirmed))

    # horizon
    def horizon_end():
        if horizon=="quarter":
            q=(TODAY.month-1)//3; m=q*3+3
            return dt.date(TODAY.year,m,1)+dt.timedelta(days=31);
        m=re.match(r"(\d+)\s*days?$",str(horizon))
        if m: return TODAY+dt.timedelta(days=int(m.group(1)))
        if TODAY.month==12: return dt.date(TODAY.year,12,31)
        return dt.date(TODAY.year,TODAY.month+1,1)-dt.timedelta(days=1)
    hend=horizon_end()
    if horizon=="quarter":
        q=(TODAY.month-1)//3; m=q*3+3
        hend=dt.date(TODAY.year,m,1)-dt.timedelta(days=1) if m<12 else dt.date(TODAY.year,12,31)
        if m<12: hend=(dt.date(TODAY.year,m+1,1)-dt.timedelta(days=1))
    with_close=[d for d in open_oneoff if d["expected_close"]]
    no_close=len(open_oneoff)-len(with_close)
    month_deals=[d for d in with_close if d["expected_close"]<=hend]
    pipeline_month=round(sum((gbp(d["value"],d["cur"]) or 0)*(d["prob"] if d["prob"] is not None else STAGE_DEFAULT_PROB.get(d["final_stage"],0.2)) for d in month_deals))
    has_close=len(with_close)>0

    # stale (count is date-based and stands even when money is suppressed)
    money_suppressed = bool({"weighted","pipeline_total","at_risk"} & suppressed)
    stale=[]
    for d in open_oneoff:
        if d["last_touch"] and (TODAY-d["last_touch"]).days>=STALE_DAYS:
            gv=round(gbp(d["value"],d["cur"]) or 0)
            stale.append({"name":d["name"],"company":d["company"],"deal_id":d["deal_id"],
                          "value":(None if money_suppressed else gv),"_v":gv,
                          "stage":d["final_stage"],"prov":(None if money_suppressed else prov(d)),
                          "days":(TODAY-d["last_touch"]).days,"whale":d["whale"],
                          # the same record the meeting drill-in shows. One deal must not be worth
                          # more truth through one door than another.
                          "note":str(d.get("notes") or "").strip(),
                          "close":(d["expected_close"].strftime("%-d %b") if d["expected_close"] else None)})
    stale.sort(key=lambda x:x["days"]*x["_v"],reverse=True)
    at_risk=sum(s["_v"] for s in stale)
    for s in stale: del s["_v"]

    # ---- run-to-run diff vs previous state ----
    # D2: keyed on diff_key (real deal id when an id column exists; else name+company — NEVER row
    #     position, so re-sorting the sheet does not churn the diff).
    # D4: `moved` fires on RAW stage-text change (normalised), so Discovery->Qualification is caught
    #     even when both fold to the same canonical bucket, and an override that only changes the
    #     canonical mapping (raw text unchanged across runs) produces NO phantom move.
    diff=None; first_run=(prev_state is None)
    def _acctnorm(s):
        s=str(s or "").strip().lower(); s=re.sub(r"^the\s+","",s); s=re.sub(r"[^a-z0-9 ]"," ",s)
        return re.sub(r"\s+"," ",s).strip()
    reused_keys={did for did,_ in id_reused}  # recycled ids: the open row is a DIFFERENT underlying deal
    if prev_state is not None:
        cur_open={d["diff_key"]:d for d in open_oneoff}
        closed_by_id={d["diff_key"]:d["final_stage"] for d in deals if d["final_stage"] in ("Closed Won","Closed Lost")}
        new_l=[]; moved_l=[]; slipped_l=[]; gone_l=[]
        for did,d in cur_open.items():
            if did not in prev_state:
                gv=round(gbp(d["value"],d["cur"]) or 0) if d["value"] is not None else None
                # D8: value stored as a NUMBER (or null); band AND modal both format via fmt() — never
                # a pre-formatted string that a second fmt() would turn into NaN.
                new_l.append({"name":d["name"],"company":d["company"],
                              "value":(None if (money_suppressed or gv is None) else gv)})
                continue
            pv=prev_state[did]
            prev_raw=pv.get("stage_raw"); cur_raw=d["stageraw"]
            raw_changed=(prev_raw is not None and norm_header(prev_raw)!=norm_header(cur_raw))
            canon_changed=(pv.get("stage") and pv["stage"]!=d["final_stage"])
            if raw_changed or (prev_raw is None and canon_changed):
                pcanon=pv.get("stage"); ccanon=d["final_stage"]
                # display the RAW stage words the user actually sees; canonical carried alongside
                frm = (str(prev_raw).strip() if prev_raw else pcanon)
                to  = (str(cur_raw).strip() if cur_raw else ccanon)
                moved_l.append({"name":d["name"],"from":frm,"to":to,"from_canon":pcanon,"to_canon":ccanon})
            # a recycled id's Monday open row is a DIFFERENT deal, so its close date is not comparable to
            # the prior deal's — do not report a phantom slip (the move is still shown; recycle is flagged).
            pc=pv.get("expected_close"); nc=d["expected_close"]
            if pc and nc and did not in reused_keys:
                try: pcd=dt.date.fromisoformat(str(pc))
                except Exception: pcd=None
                if pcd and nc>pcd:
                    slipped_l.append({"name":d["name"],"from":pcd.strftime("%-d %b"),"to":nc.strftime("%-d %b")})
        for did,pv in prev_state.items():
            if did in cur_open: continue
            outcome=("won" if closed_by_id.get(did)=="Closed Won" else ("lost" if closed_by_id.get(did)=="Closed Lost" else "gone"))
            gone_l.append({"name":(pv.get("name") or did),"company":pv.get("company") or "",
                           "outcome":outcome,"value":pv.get("value")})
        # D5: re-key detection — a new+gone pair with the same normalised name+company (value within 5%)
        # looks re-keyed, not real churn. Flag it and net it out; never silently show £X arriving AND
        # the same £X leaving over one weekend.
        rekey=[]
        for n in new_l:
            for g in gone_l:
                if g.get("_paired"): continue
                if _acctnorm(n["name"])+"|"+_acctnorm(n.get("company")) != _acctnorm(g["name"])+"|"+_acctnorm(g.get("company")): continue
                nv=n.get("value"); gv2=g.get("value")
                vok=(nv is None or gv2 is None) or (max(abs(nv),abs(gv2),1)>0 and abs(nv-gv2)<=0.05*max(abs(nv),abs(gv2),1))
                if not vok: continue
                g["_paired"]=True; n["_paired"]=True
                rekey.append({"name":n["name"],"company":n.get("company"),"value":nv}); break
        for x in new_l+gone_l: x.pop("_paired",None)
        # D9: baseline label = the PRIOR run's export (its --today + file), never this run's clock.
        since="last run"
        if prev_run_today:
            try:
                _pd=dt.date.fromisoformat(str(prev_run_today))
                since=_pd.strftime("%a %-d %b")+"'s file"
            except Exception: since="last run"
        elif prev_since:
            try:
                _sd=dt.datetime.fromisoformat(str(prev_since))
                since=_sd.strftime("%a %-d %b")+"'s file"
            except Exception: since="last run"
        diff={"since":since,"new":new_l,"moved":moved_l,"slipped":slipped_l,"gone":gone_l,
              "rekey":rekey,"real_new":len(new_l)-len(rekey),"real_gone":len(gone_l)-len(rekey)}

    # ---- target (from overrides only; never fabricated) ----
    target=None; target_bad=False
    _tov=ov.get("target")
    if isinstance(_tov,dict) and str(_tov.get("amount") or "").strip()!="":
        try: _amt=float(_tov.get("amount"))
        except (TypeError,ValueError): _amt=None
        if _amt and _amt>0:
            _period=str(_tov.get("period") or "quarter")
            if money_suppressed:
                target={"amount":round(_amt),"period":_period,"coverage_pct":None,"gap":None,"basis":"weighted","surplus":None}
            else:
                _gap=round(_amt-pipeline_total)
                # D6: expose the basis + a surplus figure so render can say "£X over target" (never "gap £-X").
                target={"amount":round(_amt),"period":_period,
                        "coverage_pct":round(pipeline_total/_amt*100),"gap":_gap,
                        "basis":"weighted","surplus":(abs(_gap) if _gap<0 else 0)}
        else:
            target_bad=True
    elif _tov is not None:
        target_bad=True

    # ---- forecast category ----
    fc_view=None
    fc_col=mapping.get("forecast_category")
    if fc_col:
        fc_ov=ov.get("forecast_category")
        if fc_ov and fc_ov.get("mode")=="show":
            cats={}
            for d in open_oneoff:
                c=d["forecast_category"] or "(none)"
                if c.lower()=="omitted": continue
                cats.setdefault(c,{"count":0,"gbp":0})
                cats[c]["count"]+=1; cats[c]["gbp"]+=round(gbp(d["value"],d["cur"]) or 0)
            fc_view=cats
            resolved_notes.append("forecast_category: per-category totals shown (Omitted excluded)")
            rep("\n## Forecast category (driven)\n"+"\n".join(f"- {k}: {v['count']} / {fmt(v['gbp'])}" for k,v in cats.items()))
            # D6: when Forecast Category drives the view, ALSO expose Commit-basis coverage — the number a
            # VP actually forecasts on — alongside the flattering weighted figure. Both bases, both labelled.
            _commit_key=next((k for k in cats if k.lower()=="commit"),None)
            if target and not money_suppressed and _commit_key:
                _ct=cats[_commit_key]["gbp"]; _amt2=target["amount"]
                target["commit"]={"total":_ct,"coverage_pct":round(_ct/_amt2*100),"gap":round(_amt2-_ct)}
            # D11: Commit deals still sitting in an early stage (Discovery) are a hygiene risk — flag them.
            _diss=[d for d in open_oneoff if (d["forecast_category"] or "").lower()=="commit" and d["final_stage"]=="Discovery"]
            if _diss:
                add_issue("category_stage_dissonance","fyi",[d["line"] for d in _diss][:8],
                    f"{len(_diss)} deal(s) marked Commit but still in Discovery: "+", ".join((d["name"] or d["company"]) for d in _diss[:5]),
                    "","","",[],"A Commit-category deal in an early stage is a forecast risk; review.")
        else:
            vals_fc=set((d["forecast_category"] or "").lower() for d in open_oneoff if d["forecast_category"])
            if vals_fc & {"commit","best case","pipeline","omitted","upside"}:
                add_issue("forecast_category_column","warning",[1],
                    f"file has a Forecast Category column ({fc_col}) with values like {sorted(list(vals_fc))[:5]}",
                    "Your file has a Forecast Category column. Should it drive your numbers instead of stage-weighted maths?",
                    ["Yes — show category totals","No — keep stage-weighted"],"forecast_category",[],
                    "Answer to add per-category (Commit/Best Case/Pipeline) totals.",
                    choices_values=[{"column":fc_col,"mode":"show"},{"column":fc_col,"mode":"off"}],emit="scalar")

    # ---- FYI + warnings ----
    if mismatch_rows:
        for nm,vsum,amt,lines in mismatch_rows:
            add_issue("line_item_amount_mismatch","warning",lines,
                f"{nm}: line-item sum {fmt(vsum)} vs Amount column {fmt(amt)}",
                f"{nm}'s product line items add to {fmt(vsum)} but its Amount says {fmt(amt)}. Which is right?",
                ["Use line-item sum","Use Amount column"],"amount_source",[],
                "Confirm which figure to trust; line-item sum is used by default.")
    if dupes:
        fresher=[d for d in dupes if d["fresher"]]
        add_issue("duplicate_rows","warning",[d["line"] for d in dupes],
            f"{len(dupes)} duplicate deal id(s); policy = {dedupe_policy}"+(f"; {len(fresher)} discarded row is FRESHER than the kept one" if fresher else ""),
            "Duplicate deal ids found. Which row should win?",
            ["Keep first","Keep most recently touched"],"dedupe_policy",[],
            "Confirm the dedupe policy.",
            choices_values=["keep-first","most_recent"],emit="scalar")
    # D2: a re-used/recycled id (present both open and closed) — open row wins for the pipeline; disclose.
    if id_reused:
        add_issue("id_reused","fyi",[1],
            f"{len(id_reused)} deal id(s) re-used (a closed row and a new open row share the number): "
            +", ".join(f"{did} ({nm})" for did,nm in id_reused[:5])
            +". The open row is kept in the live pipeline.",
            "","","",[],"A recycled deal id; the live open row wins so no live deal is lost.")
    if len(currencies)>1:
        add_issue("mixed_currency_static_fx","fyi",[1],
            f"mixed currencies {sorted(currencies)} converted to GBP at static rates",
            "","","fx",[],"Static FX rates used; provide live rates to override.")
    prob0=[d for d in open_oneoff if d["prob"]==0]
    if prob0:
        add_issue("prob_zero_live_deal","fyi",[d["line"] for d in prob0][:8],
            f"{len(prob0)} live deal(s) at 0% probability","","","",[],"Review these live-but-zero deals.")
    past_close=[d for d in open_oneoff if d["expected_close"] and d["expected_close"]<TODAY]
    if past_close:
        add_issue("stale_close_dates","warning",[d["line"] for d in past_close][:8],
            f"{len(past_close)} open deal(s) have a close date in the past",
            "Some open deals have close dates in the past. Update them?",["Update dates"],"",[],
            "These still count in the month view; update to refresh.")
    if junk:
        add_issue("junk_rows_detected","warning",[l for l,_ in junk],
            f"{len(junk)} test/junk/incomplete row(s) skipped",
            "I skipped rows that look like test/junk data.",["OK"],"",[],
            "Skipped: "+"; ".join(w for _,w in junk[:5]))
    if whale_thresh is not None:
        biggest=max((gbp(d["value"],d["cur"]) or 0) for d in open_oneoff) if open_oneoff else 0
        if unweighted_total and biggest>0.40*unweighted_total:
            add_issue("whale_concentration","fyi",[1],
                f"one deal is {round(biggest/unweighted_total*100)}% of open pipeline","","","",[],
                "Concentration risk in a single deal.")
    if no_last_activity:
        add_issue("no_last_activity","fyi",[1],f"{no_last_activity} open deal(s) have no last-activity date","","","",[],
            "Cannot assess these for staleness.")
    # D3: stage-assumption disclosure. When the panel is already asking about unreadable stages
    # (unrecognised_stages blocker present), also DISCLOSE every fuzzy stage GUESS the engine made
    # (raw text != the canonical it booked), so nothing is silently booked at Proposal/Negotiation
    # while the interim headline claims "kept in Discovery". Gated on the blocker so confidently-casual
    # pipelines (personas 1-2) are not nagged. Mappable via the same stage_map override key.
    if unrec:
        assum={}
        for d in open_oneoff:
            ra=d.get("stage_assumed")
            if ra: assum.setdefault(str(ra).strip(),{"canon":d["final_stage"],"n":0}); assum[str(ra).strip()]["n"]+=1
        if assum:
            saw="; ".join(f"“{k}” → {v['canon']} ({v['n']} deal(s))" for k,v in assum.items())
            add_issue("stage_assumptions","fyi",[1],
                f"stage guesses I made from non-standard wording: {saw}. Correct any via stage_map.",
                "","","stage_map",[],
                "These are best-effort guesses from free-text stage labels; confirm or remap.")
    # D5: surface the re-key netting as an FYI so the band's raw new/gone count is honestly qualified.
    if diff and diff.get("rekey"):
        rk=diff["rekey"]
        add_issue("possible_rekey","fyi",[1],
            f"{len(rk)} gone/new pair(s) share name + account + value — these look re-keyed, not real churn: "
            +", ".join((r["name"] or "")+(f" · {r['company']}" if r.get('company') else "") for r in rk[:5])
            +f". Net real churn = {diff['real_new']} new / {diff['real_gone']} gone.",
            "","","",[],"Re-keyed deal ids inflate the raw new/gone counts; the net figures are shown.")
    # D2: no id column at all -> the diff keys on name+company (disclosed), never row position.
    if not has_id_col and not first_run:
        add_issue("no_id_column","fyi",[1],
            "no deal-id column found; changes since your last file are tracked by name + company, not a stable id.",
            "","","",[],"Add a deal-id/ref column for the most reliable change tracking.")

    # ---- possible_same_account (FYI) — near-duplicate/variant account names ----
    # Normalise (lowercase, strip leading "the ", collapse whitespace, strip punctuation) and group
    # KEPT deals. A group qualifies only when >=2 DISTINCT raw spellings map to the same normalised
    # name across >=2 distinct deal ids — so genuinely repeated identical accounts do NOT fire, but
    # variants like "Royal Marsden"/"The Royal Marsden" or a trailing-space "Nimbus Bank " do. No
    # dedupe action: this is a question only.
    def _norm_acct(s):
        s=str(s or "").strip().lower()
        s=re.sub(r"^the\s+","",s)
        s=re.sub(r"[^a-z0-9 ]"," ",s)
        return re.sub(r"\s+"," ",s).strip()
    acct_groups={}
    for d in deals:
        # use the UNSTRIPPED account identity so trailing/leading-whitespace variants count as distinct
        # raw spellings (parsed 'company'/'name' are already .strip()ped, which would erase them). Some
        # files map the account into the name column, so fall back through company_raw -> name_raw.
        raw=str(d.get("company_raw") or "")
        if not raw.strip(): raw=str(d.get("name_raw") or "")
        if not raw.strip(): raw=str(d.get("name") or "")
        if not raw.strip(): continue
        key=_norm_acct(raw)
        if not key: continue
        g=acct_groups.setdefault(key,{})
        e=g.setdefault(raw,{"id":d["deal_id"],"lines":[]})
        e["lines"].append(d["line"])
    same_groups=[]; same_lines=[]
    for key,g in acct_groups.items():
        ids={e["id"] for e in g.values()}
        if len(g)>=2 and len(ids)>=2:
            parts=[]
            for raw,e in g.items():
                parts.append(f"'{raw}' ({e['id']})"); same_lines.extend(e["lines"])
            same_groups.append(", ".join(parts))
    if same_groups:
        add_issue("possible_same_account","fyi",sorted(set(same_lines))[:12],
            "These look like the same account: "+"; ".join(same_groups)+" — same account?",
            "","","",[],
            "Near-duplicate account names spotted; confirm whether they are one account. No change made, question only.")

    # ---- value_note_mention (FYI) — a kept row's note hints its value should be adjusted ----
    # Whole-word share / JV / joint venture / our share / 50% / split in the notes field. The engine
    # never mines notes into the maths (DATA-ISSUES §5); it uses the full value and asks. Catches the
    # P5 £24.2m JV whose true share is 50%.
    _note_re=re.compile(r"\bjoint venture\b|\bour share\b|\bshare\b|\bsplit\b|\bjv\b|\b50\s*%",re.I)
    for d in deals:
        note=str(d.get("notes") or "").strip()
        if not note: continue
        m=_note_re.search(note)
        if not m: continue
        if len(note)<=120:
            frag=note
        else:
            st=max(0,m.start()-30); en=min(len(note),m.end()+30)
            frag=("…" if st>0 else "")+note[st:en].strip()+("…" if en<len(note) else "")
        add_issue("value_note_mention","fyi",[d["line"]],
            f"The note on {d['name']} mentions '{frag}' — should its value be adjusted? I have used the full value.",
            "","","",[],
            "A free-text note hints the deal value may not be the full amount; confirm. No change made, question only.")

    # ---- meetings ----
    meetings=[]; internal_ct=0
    if a.meetings and os.path.exists(a.meetings):
        mt=load_table(a.meetings); mm=map_columns([str(c) for c in mt.columns])
        for _,r in mt.iterrows():
            person=str(r.get(mm.get("prospect_name")) or "").strip()
            compy=str(r.get(mm.get("company_name")) or "").strip()
            tcol=next((c for c in mt.columns if norm_header(c) in ("time","start","when","start time","starttime")),None)
            subcol=next((c for c in mt.columns if norm_header(c) in ("subject","title")),None)
            ctxcol=next((c for c in mt.columns if norm_header(c) in ("context","type","notes")),None)
            subj=str(r.get(subcol,"") or "").strip() if subcol else ""
            # D14: a calendar export often carries no company COLUMN — the attendee cell is
            # "Steven Mackay · Mackay's Toys". Split on the separator that is already in the file
            # rather than reading the whole cell as a person and calling the meeting internal for
            # want of a column. Nothing is inferred: no separator, no company.
            if not compy and person:
                _p=re.split(r"\s+[·|]\s+|\s+[-–—]\s+",person,maxsplit=1)
                if len(_p)==2 and _p[0].strip() and _p[1].strip():
                    person,compy=_p[0].strip(),_p[1].strip()
            who=" · ".join([x for x in (person,compy) if x])
            # D12: a meeting with no company (or an explicit "internal" marker) is an internal meeting.
            internal = (not compy) or ("internal" in (person+" "+subj).lower())
            if not who:
                who=subj or "Internal"
            if not str(who).strip(): continue
            if internal: internal_ct+=1
            v,_=parse_money(r.get(mm.get("deal_value"))) if mm.get("deal_value") else (None,None)
            meetings.append({"time":str(r.get(tcol,"") or ""),"who":str(who),
                             "sub":subj if (subj and subj!=who) else str(r.get(ctxcol,"") or ""),
                             "value":round(v) if v else None,"prep":None,"internal":internal,
                             "person":person,"company":compy})
        rep(f"\n## Meetings\n- loaded {len(meetings)} ({len(meetings)-internal_ct} external + {internal_ct} internal)")
    else:
        rep("\n## Meetings\n- no meetings file; empty state")

    # ---- commitments ----
    commitments=[]; ambiguous_commits=[]
    if a.commitments and os.path.exists(a.commitments):
        ct=load_table(a.commitments); cmap={norm_header(c):c for c in ct.columns}
        def cc(r,*names):
            for nm in names:
                key=norm_header(nm)
                if key in cmap:
                    v=r.get(cmap[key])
                    if v not in (None,"") and not (isinstance(v,float) and pd.isna(v)): return v
            return None
        for _,r in ct.iterrows():
            promise=cc(r,"promise","promise_text","what you promised","task","commitment")
            if not promise: continue
            status=str(cc(r,"status") or "").strip().lower()
            if status in ("done","complete","completed","closed","resolved"):
                continue
            owed=cc(r,"owed_to","owed to","related account","prospect","client","contact","who") or ""
            due=parse_date(cc(r,"due_date","due date","due"))
            off=(due-TODAY).days if due else None
            # Some exports carry the due date as an OFFSET from the run date rather than a date
            # (due_offset_days = -2). Read it: without this the row still printed the file's
            # "2d late" display string while the hero counted 0 overdue — the card and the chip
            # contradicting each other, which is the exact failure this engine exists to prevent.
            if off is None:
                _off_raw=cc(r,"due_offset_days","due offset days","due_offset","days_until_due")
                try:
                    if _off_raw is not None and str(_off_raw).strip()!="":
                        off=int(float(_off_raw)); due=TODAY+dt.timedelta(days=off)
                except (TypeError,ValueError): off=None
            dd=cc(r,"due_display")
            disp = dd if (dd and not isinstance(dd,(dt.date,dt.datetime))) else (
                   "Today" if off==0 else (f"{-off}d late" if (off is not None and off<0) else (f"{off}d" if off is not None else "")))
            dcls="bad" if (off is not None and off<0) else ("warn" if off==0 else "ok")
            # A display string we cannot corroborate with a real date is not evidence. Say so
            # rather than styling it as if we knew.
            if off is None and dd:
                add_issue("commitment_due_unreadable","warning",[1],
                    f"commitment '{str(cc(r,'promise_text','promise','') or '')[:40]}' shows a due of \"{dd}\" "
                    "but has no due date or offset I can read, so it is not counted as overdue.",
                    "Some commitments show a due label I cannot turn into a date. Which column holds the real due date?",
                    ["Tell me the column"],"",[],
                    "Add a due_date (or due_offset_days) column so overdue counts are real.")
            src="call" if str(cc(r,"source_type","source") or "").lower().startswith("call") else "email"
            mv,_=parse_money(cc(r,"linked_value","value","deal value"))
            # D10: if the owed-to name matches 2+ OPEN deals, the join is ambiguous — join to NONE and
            # flag, rather than silently pinning the promise to the first (possibly wrong) deal.
            matches=[d for d in deals if d["name"].strip().lower()==str(owed).strip().lower() and d["final_stage"] in OPEN_STAGES]
            dl = matches[0] if len(matches)==1 else None
            if len(matches)>1:
                ambiguous_commits.append((str(owed),[m["deal_id"] for m in matches]))
            cval=gbp(mv,None) if mv is not None else (gbp(dl["value"],dl["cur"]) if (dl and dl["value"] is not None) else None)
            commitments.append({"promise":str(promise),"owed_to":str(owed),
                "deal":(f"{dl['deal_id']} · {dl['final_stage']}" if dl else ""),
                "value":(round(cval) if cval is not None else None),
                "due":disp,"due_class":dcls,"src":src,"quote":str(cc(r,"source_quote","quote","") or ""),"_off":off})
        rep(f"\n## Commitments\n- loaded {len(commitments)} (Done rows excluded)")
    else:
        rep("\n## Commitments\n- no commitments file; empty state")
    if ambiguous_commits:
        add_issue("ambiguous_commitment","fyi",[1],
            "commitment(s) whose contact matches more than one open deal (joined to none): "
            +"; ".join(f"{who} → {', '.join(ids)}" for who,ids in ambiguous_commits[:5]),
            "","","",[],"The promise could belong to any of these deals; confirm which before acting.")
    commit_overdue=sum(1 for c in commitments if c["due_class"]=="bad")
    commit_open=len(commitments)

    # ---- meeting → deal link (SHIP-PLAN §3 #3, ranked add) ----
    # There is no transcript, so a meeting drills into THE DEAL IT IS ABOUT rather than a dead end.
    # Everything here already exists in the file: stage, value, days since last touch, expected close,
    # the open commitments owed to that person, and the last note ON the record. Nothing is inferred:
    # no talking points, no email thread, no summary. Those stay honestly empty behind a connect strip.
    #
    # The join uses the SAME contract as commitments (D10): the link must be UNAMBIGUOUS or there is no
    # link. Exactly one open deal must match, else the meeting says why it can't link and stays inert.
    # A wrong pin here is a confident silent number in the shape of a deal.
    def _norm_who(s):
        return re.sub(r"[^a-z0-9]+"," ",str(s or "").lower()).strip()
    # ---- THE CONNECTED TIER: emails + calls, keyed by contact ----
    # EVERY field here is VERBATIM or a timestamp. Nothing on these bands is written by us: the ask is
    # the buyer's own sentence, the call summary is the transcript tool's own words with its own link.
    # That is the whole safety model — v1's "AI talking points" were hand-written demo strings with no
    # engine behind them, and an un-cited talking point is the one object on this screen that can lie
    # fluently. The evidence IS the feature; synthesis is not required to make it valuable.
    prep_by={}
    if a.prep and os.path.exists(a.prep):
        try:
            prep_by={_norm_who(k):v for k,v in json.load(open(a.prep)).items() if not k.startswith("_")}
        except Exception as ex: rep(f"- prep file unreadable, ignored: {ex}")

    def _ago(d):
        try:
            n=(TODAY-dt.date.fromisoformat(str(d)[:10])).days
            return None if n is None else ("today" if n==0 else ("1d ago" if n==1 else f"{n}d ago"))
        except Exception: return None

    def _prep_for(name):
        """Meeting prep for one contact. Everything here is authored or verbatim — the ONE thing
        this function decides for itself is which question is still open, and that is arithmetic."""
        p=prep_by.get(_norm_who(name))
        if not p: return None
        es=sorted(p.get("emails") or [],key=lambda x:str(x.get("date") or ""),reverse=True)
        # THE OPEN ASK — computed, never declared in the file. A received email is "open" only if
        # nothing has been SENT after it. That is two dates compared; it is not a judgement about
        # whether the rep answered it well, and it is not recency: sorting a thread by timestamp
        # reliably surfaces "Great, see you Tuesday" and buries the sentence that decides the hour.
        last_sent=next((e for e in es if str(e.get("direction"))=="sent"),None)
        lsd=str(last_sent.get("date"))[:10] if last_sent else ""
        open_ask=next((e for e in es if str(e.get("direction"))=="received"
                       and str(e.get("date"))[:10]>lsd), None)
        emails=[{"direction":e.get("direction"),"subject":e.get("subject"),"body":e.get("body"),
                 "ago":_ago(e.get("date")),"link":e.get("link"),
                 "open_ask":(open_ask is not None and e is open_ask)} for e in es]
        # a talking point with no citation does not render. The cite is what makes it reasoning
        # rather than a guess, and the line it cites is on this same screen for the eye to check.
        points=[{"lead":pt.get("lead"),"rest":pt.get("rest"),"cite":pt.get("cite"),"quote":pt.get("quote")}
                for pt in (p.get("points") or []) if pt.get("cite") and (pt.get("lead") or pt.get("rest"))]
        c=p.get("call")
        call=({"source":c.get("source"),"summary":c.get("summary"),"link":c.get("link"),
               "ago":_ago(c.get("date"))} if c and c.get("summary") else None)
        return {"company_note":p.get("company_note"),"points":points,"emails":emails,"call":call,
                "has_ask":bool(open_ask)}

    def _link_meeting(m):
        if m["internal"]: return None,"internal"
        pn=_norm_who(m.get("person")); cp=_norm_who(m.get("company"))
        if not pn and not cp: return None,"no name on the invite"
        cands=[d for d in deals if d["final_stage"] in OPEN_STAGES]
        # 1) contact name, with the company as a tie-break when the invite carries one
        byname=[d for d in cands if pn and _norm_who(d["name"])==pn]
        if len(byname)>1 and cp:
            byname=[d for d in byname if _norm_who(d["company"])==cp] or byname
        if len(byname)==1: return byname[0],None
        if len(byname)>1:
            return None,"matches "+str(len(byname))+" open deals ("+", ".join(d["deal_id"] for d in byname[:4])+")"
        # 2) no contact match: fall back to the company, again only when it is unambiguous
        bycomp=[d for d in cands if cp and _norm_who(d["company"])==cp]
        if len(bycomp)==1: return bycomp[0],None
        if len(bycomp)>1:
            return None,"matches "+str(len(bycomp))+" open deals at "+str(m.get("company") or "")
        return None,"no open deal on file for this contact"
    for m in meetings:
        d,why=_link_meeting(m)
        if d is None:
            m["prep"]=None; m["nolink"]=why
            continue
        gv=gbp(d["value"],d["cur"]) if d["value"] is not None else None
        # money obeys suppression exactly as the rest of the panel does: never a number under a blocker
        mv=(None if (money_suppressed or gv is None) else round(gv))
        oc=[{"promise":c["promise"],"due":c["due"],"due_class":c["due_class"]}
            for c in commitments if _norm_who(c["owed_to"])==_norm_who(d["name"])]
        note=str(d.get("notes") or "").strip()

        # ---- A. THE ACCOUNT LINE — the other open deals on this logo ----
        # The one fact the meeting row cannot carry: you do not grind 12% out of a £28k negotiation
        # sixteen days before a £138k renewal lands with the same buyer. The card says WHALE and says
        # £28k and never notices those two are arguing.
        # EXACT normalised match only, NEVER fuzzy: merging "Belford & Crowe" with "Belford and Crowe
        # Ltd" would publish a confident total for an account that does not exist — inventing a
        # relationship is the same sin as inventing a number. Near-misses are DISCLOSED and NOT
        # counted, so the total is always a floor, never a guess.
        acct=None
        akey=_acctnorm(d.get("company") or "")
        if akey:
            sibs=[x for x in open_oneoff if x is not d and _acctnorm(x.get("company") or "")==akey]
            if sibs:
                def _sv(x):
                    g=gbp(x["value"],x["cur"]) if x["value"] is not None else None
                    return (None if (money_suppressed or g is None) else round(g))
                others=sorted(sibs,key=lambda x:(_sv(x) or 0),reverse=True)
                vals=[_sv(x) for x in others]+[mv]
                acct={
                    "name":d.get("company") or "",
                    "open_count":len(sibs)+1,
                    # never a total that silently drops an unknown: if any value is missing, say so
                    "total":(None if any(v is None for v in vals) else sum(vals)),
                    "others":[{"name":x["name"],"stage":x["final_stage"],"value":_sv(x),
                               "deal_id":x["deal_id"],
                               "close":(x["expected_close"].strftime("%-d %b") if x["expected_close"] else None),
                               "days":((TODAY-x["last_touch"]).days if x["last_touch"] else None)}
                              for x in others],
                    # variants read as the same account to a human but NOT to an exact match: listed,
                    # never added. The rep's eye closes it; the panel does not.
                    "variants":sorted({x.get("company") for x in open_oneoff
                                       if x.get("company") and _acctnorm(x["company"])!=akey
                                       and _acctnorm(x["company"]).replace("the","").strip()==akey.replace("the","").strip()}),
                }

        # ---- B. WHAT'S MOVED — the delta on this deal since the last export ----
        # A deal whose close date has moved twice is not a negotiation, it's a stall, and the rep
        # walks in asking a different question. The engine ALREADY computes this for the Desk's diff
        # band and stores prior state; the drill-in simply wasn't reading it.
        # An export is NOT an event log: every line is dated to the prior FILE, never asserted as a
        # fact about the world, and "no change" is never an all-clear — it is a statement about two
        # files, exactly as "No promise to them found in your file" is.
        moved=None
        if prev_state is not None:
            pv=prev_state.get(d["diff_key"])
            if pv:
                # D8 APPLIES HERE: money is stored as a NUMBER (or null) and formatted ONCE, by the
                # render layer's fmt(). A pre-formatted "£28k" put through fmt() again renders NaN —
                # so each row declares its KIND and the render layer decides how to print it.
                rows=[]
                if pv.get("stage") and pv["stage"]!=d["final_stage"]:
                    rows.append({"what":"Stage","kind":"text","from":pv["stage"],"to":d["final_stage"],"note":None})
                pvv=pv.get("value")
                if pvv is not None and mv is not None and pvv!=mv:
                    rows.append({"what":"Value","kind":"money","from":pvv,"to":mv,"delta":mv-pvv,"note":None})
                pc=pv.get("expected_close")
                if pc and d["expected_close"]:
                    try:
                        pcd=dt.date.fromisoformat(pc)
                        if pcd!=d["expected_close"]:
                            dd=(d["expected_close"]-pcd).days
                            rows.append({"what":"Close date","kind":"text",
                                         "from":pcd.strftime("%-d %b"),
                                         "to":d["expected_close"].strftime("%-d %b"),
                                         "note":("moved out "+str(dd)+" days" if dd>0 else "pulled in "+str(-dd)+" days")})
                    except Exception: pass
                # ONE PLAIN-ENGLISH LINE, not a band. "What's moved · since Sat 11 Jul's file" was
                # engineer-speak on a sales screen — it named our plumbing (an export) instead of the
                # thing that happened. "moved up from Discovery on Friday" is the same fact in the
                # rep's own language, costs no space, and rides on the Stage fact it describes.
                # Silence stays silent: no movement renders nothing, and says nothing.
                when=(dt.date.fromisoformat(prev_run_today).strftime("%A") if prev_run_today else "in your last file")
                # "was X on Saturday" — NOT "moved up from X on Saturday". We do not know WHEN it
                # moved; we know what Saturday's file said and what today's says. The first phrasing
                # is a claim about the world, the second is a claim about two files we actually read,
                # and the difference is the whole product. It is also still plain English, which was
                # the point of killing the old label.
                say=None
                for r in rows:
                    if r["what"]=="Stage": say="was "+r["from"]+" on "+when; break
                if say is None:
                    for r in rows:
                        if r["what"]=="Close date": say="close date was "+str(r["from"])+" on "+when; break
                moved={"since":(dt.date.fromisoformat(prev_run_today).strftime("%a %-d %b") if prev_run_today else None),
                       "file":prev_file,"rows":rows,"say":say}
        m["prep"]={
            "deal_id":d["deal_id"],"name":d["name"],"company":d["company"],
            "title":str(d.get("person_title") or "").strip(),
            "stage":d["final_stage"],"stage_raw":d["stageraw"],
            "value":mv,"prov":(None if money_suppressed else prov(d)),
            "whale":d["whale"],
            "days":((TODAY-d["last_touch"]).days if d["last_touch"] else None),
            "close":(d["expected_close"].strftime("%-d %b") if d["expected_close"] else None),
            "commits":oc,
            "note":note,
            "account":acct,
            "moved":moved,
            "first_run":first_run,
            # ---- D. WHAT'S INSIDE THE NUMBER ----
            # Present only when the file actually carries product rows. When it doesn't, the render
            # layer says so in one honest line rather than leaving a dead band — "no breakdown
            # exported" is a fact about the file, and the panel says those out loud.
            "lines":([{"product":(l["product"] or "unnamed line"),
                       "value":(None if money_suppressed or l["value"] is None
                                else round(gbp(l["value"],l.get("cur") or d["cur"]) or 0)),
                       "line":l["line"]} for l in d.get("lines")]
                     if d.get("lines") and len(d["lines"])>1 else None),
            "lines_source":("product rows in your file" if d.get("lines") and len(d["lines"])>1 else None),
            # ---- meeting prep: points / emails / call (absent unless a prep file was supplied) ----
            "mp":_prep_for(d["name"]),
        }
        m["nolink"]=None
    if meetings:
        _linked=sum(1 for m in meetings if m.get("prep"))
        rep(f"- linked {_linked}/{len(meetings)} to an open deal"
            +("" if _linked==len(meetings) else "; unlinked: "
              +"; ".join(f"{m['who']} ({m.get('nolink')})" for m in meetings if not m.get("prep"))))

    # ---- plan (ranked, deterministic per v5 contract) ----
    # 1 overdue commitments (most late first) + due-today; 2 closing-stage (Negotiation, meeting
    # today first then nearest close); 3 stale by days x value; 4 no-next-step. Honest cap, keep quick-add.
    def _has_mtg(d):
        nm=(d.get("name") or "").strip().lower(); cp=(d.get("company") or "").strip().lower()
        for m in meetings:
            who=str(m.get("who") or "").lower()
            if not who: continue
            if cp and cp in who: return True
            if nm and nm in who: return True
        return False
    def _wv(d):  # weighted value for ranking
        return (gbp(d["value"],d["cur"]) or 0)*(d["prob"] if d["prob"] is not None else STAGE_DEFAULT_PROB.get(d["final_stage"],0.2))
    plan=[]; planned_ids=set()
    overdue_c=sorted([c for c in commitments if c["due_class"]=="bad"],
                     key=lambda c:(c.get("_off") if c.get("_off") is not None else 0))
    for c in overdue_c+[c for c in commitments if c["due_class"]=="warn"]:
        why=(f"promised, {c['due'].lower()}" if c["due_class"]=="bad" else "promised, due today")
        plan.append({"text":f"{c['promise']} · {c['owed_to']}".strip(" ·"),"why":why,"type":"Commit","done":False})
    # Tier 2 closing (Negotiation): meeting-today first, then nearest close. Cap 5.
    closing=[d for d in open_oneoff if d["final_stage"]=="Negotiation"]
    closing.sort(key=lambda d:(0 if _has_mtg(d) else 1, d["expected_close"] or dt.date.max))
    for d in closing[:5]:
        planned_ids.add(d["deal_id"])
        cl=d["expected_close"]; gv=round(gbp(d["value"],d["cur"]) or 0) if d["value"] is not None else None
        vtxt="" if (gv is None or money_suppressed) else f" · {fmt(gv)}"
        why="meeting today" if _has_mtg(d) else (f"closes {cl.strftime('%-d %b')}" if cl else "in negotiation")
        plan.append({"text":f"Push {d['name']} to close"+vtxt,"why":why,"type":"Closing","done":False})
    # Tier 3 stale (days x value). Cap 5. D7: dedupe against ALREADY-SURFACED DEALS (by deal_id), NOT by
    # contact name — a rep with a Negotiation deal must not lose an unrelated stale deal to a name clash.
    stale_ids={s["deal_id"] for s in stale}
    stale_added=0
    for s in stale:
        if s["deal_id"] in planned_ids: continue
        if stale_added>=5: continue
        planned_ids.add(s["deal_id"]); stale_added+=1
        vtxt="" if s["value"] is None else (f" · whale {fmt(s['value'])}" if s["whale"] else f" · {fmt(s['value'])}")
        plan.append({"text":f"Chase {s['name']}","why":f"{s['days']}d silent"+vtxt,"type":"Stale","done":False})
    # Tier 4 no-next-step: open, NOT stale, no meeting, not already surfaced. D7: rank by WEIGHTED value,
    # cap 3. Negotiation deals that OVERFLOWED the Tier-2 closing cap correctly cascade here (they are
    # open, not stale, no meeting) — only the rows already ON the plan (planned_ids) are excluded.
    #
    # D16: if the file HAS a next-step column, believe it. This tier tells the rep "no next step
    # logged" — an assertion — while never looking for a next-step field, so any deal it simply
    # hadn't mentioned got accused of having no next step. Where the column exists, only a deal
    # with an EMPTY one qualifies, and the sentence is then true because we looked. Where it does
    # not exist the old behaviour stands (the rep logs next steps nowhere we can see).
    has_next_col = "next_step" in mapping
    nonext=[d for d in open_oneoff
            if d["deal_id"] not in stale_ids
            and d["deal_id"] not in planned_ids and not _has_mtg(d)
            and (not has_next_col or not str(d.get("next_step") or "").strip())]
    nonext.sort(key=lambda d:(_wv(d),str(d["deal_id"])),reverse=True)
    for d in nonext[:3]:
        planned_ids.add(d["deal_id"])
        plan.append({"text":f"Set a next step for {d['name']}","why":"no next step logged","type":"No next step","done":False})
    # D7: overflow disclosure counts only deals that qualified for a tier but are NOT on the plan at all
    # (a Negotiation deal that overflowed Tier-2 but CASCADED into Tier-4 is shown, so it is not hidden).
    def _hidden(ids): return len([i for i in ids if i not in planned_ids])
    plan_overflow=[]
    for tier,ids in (("Closing",[d["deal_id"] for d in closing]),
                     ("Stale",[s["deal_id"] for s in stale]),
                     ("No next step",[d["deal_id"] for d in nonext])):
        h=_hidden(ids)
        if h>0: plan_overflow.append({"tier":tier,"hidden":h})
    if not plan:
        plan.append({"text":"Send 10 cold emails to new prospects","why":"pipeline looks quiet","type":"Manual","done":False})
    for _i,_row in enumerate(plan,1): _row["rank"]=_i
    for c in commitments: c.pop("_off",None)
    plan_total=len(plan)

    # ---- hero ----
    n_block=sum(1 for i in issues if i["severity"]=="blocker" and not i["resolved"])
    n_issue=sum(1 for i in issues if not i["resolved"])
    whale_note=None
    hot=[d for d in open_oneoff if d["whale"]]
    if hot and "whales" not in suppressed: whale_note=f"{len(hot)} whale{'s' if len(hot)>1 else ''} in play"
    # ---- THE ONE MOVE: the hero states a verdict, not a status ----
    # WHAT WAS HERE, AND WHY IT HAD TO GO. Three branches, all three broken:
    #   1. "N things need your eyes before these numbers are safe. Open the panel to answer."
    #      — Bingley narrating his own UI, captioning a chip 40px to its right.
    #   2. "Here is where things stand: 2 promises overdue, £64k going stale, 4 meetings today."
    #      — a verbatim restatement of the chips beside it.
    #   3. "You are all caught up. Add deals or connect your tools to see more."
    #      — THE FOUNDING SIN, still in the engine. It fired when there were no issues AND no
    #      overdue commitments AND no stale deals AND no meetings — but for a CSV-only user (6 of 8)
    #      commitments and meetings are zero BY ABSENCE, not by fact. Gareth's file — the one with 26
    #      unread tenders — lands exactly there. "All caught up" is the sentence this panel exists to
    #      prevent, and it was one clean-looking export away from rendering.
    # A hero is a VERDICT, not a summary: every card below already holds the facts, and none of them
    # can choose. So Bingley names the one deal to start with, and shows his working inline so the
    # rep can overrule him in a glance. A verdict with its evidence attached is trustworthy; without
    # one it is just another confident number.
    move=None
    _cands=[d for d in open_oneoff if d["last_touch"] and d["value"] is not None]
    if _cands:
        # A MEETING TODAY OUTRANKS EVERYTHING, then days silent x weighted value.
        # On pure days x value this picked Hargreaves (14d x £20k) over Rajiv (5d x £28k) — and
        # plan.mp3 says "First, Rajiv Parmer ... has gone quiet ahead of your three o'clock with him,
        # so open the morning with a nudge." The voice was right and the formula was wrong: a cold
        # deal you are sitting down with at 15:00 is the only one with a clock on it. Hargreaves can
        # be chased at any hour today; Rajiv cannot be nudged at 15:01.
        # This is also the tier-2 rule the plan card already uses (meeting-today first), so the hero
        # and the plan rank on the same law rather than two.
        def _urg(d):
            days=(TODAY-d["last_touch"]).days
            gv=gbp(d["value"],d["cur"]) or 0
            return (1 if _has_mtg(d) else 0, days*gv*(d["prob"] if d.get("prob") else 1))
        top=max(_cands,key=_urg)
        _d=(TODAY-top["last_touch"]).days
        gv=round(gbp(top["value"],top["cur"]) or 0)
        why=[]
        if not money_suppressed and gv: why.append(fmt(gv))
        why.append(top["final_stage"].lower())
        why.append(f"silent {_d} day{'s' if _d!=1 else ''}")
        _m=next((m for m in meetings if not m["internal"] and (m.get("prep") or {}).get("deal_id")==top["deal_id"]),None)
        if _m: why.append(f"and he's in your diary at {_m['time']}")
        # The dot-separated `why` is kept — it is what the drill-ins and the gates read — but the
        # hero no longer PRINTS it. A rep does not think in "£28k · negotiation · silent 5 days";
        # that is a record, read aloud. The parts go out separately so the hero can say the same
        # facts as a sentence, and every one of them is still a field off the file, not a phrase
        # invented to make the sentence flow. If a part is missing, the clause is dropped — the
        # sentence never fills a gap with a guess.
        move={"name":top["name"],"why":" · ".join(why),
              "value":(None if money_suppressed or not gv else fmt(gv)),
              "stage":top["final_stage"].lower(),
              "days":_d,
              "whale":bool(top.get("whale")),
              "mtg":(_m["time"] if _m else None)}
    # the chips absorb the risk CONCENTRATION: "£64k at risk" is a number nobody acts on, while
    # "£64k of your £100k — 4 deals, untouched for a fortnight" is a problem. Same data, a verdict
    # rather than a stat. Suppression still wins: never a concentration built on a blocked figure.
    # NO RATIO. The first cut of this line read "£64k of your £100k is cold — 64%" and that number
    # was FALSE: at_risk is a sum of RAW deal values, pipeline_total is PROBABILITY-WEIGHTED, and
    # dividing one by the other gave 64% when the truth is 31% (raw:raw, £64k of £203.6k) or 47%
    # (weighted:weighted, £47.2k of £100k). Neither. A numerator and a denominator from two
    # different accounting bases, asserted in bold, in the hero — the exact confident silent number
    # this panel exists to prevent, built by the thing built to prevent it.
    # The lesson is not "check the maths", it is that a ratio invites you to divide two numbers that
    # were never the same kind. So the line makes NO ratio: it states a money figure and a COUNT,
    # and both are on screen elsewhere for the rep to check (the stale card says "4 at risk", the
    # pipeline says "20 deals"). Proportion without division, and nothing to get wrong.
    concentration=None
    if stale and "stale" not in suppressed and "at_risk" not in suppressed and not money_suppressed:
        _oldest=max((s["days"] for s in stale if s.get("days") is not None), default=None)
        _w=sum(1 for s in stale if s.get("whale"))
        concentration={"at_risk":fmt(at_risk),"count":len(stale),
                       "of_count":(None if "counts" in suppressed else len(open_oneoff)),
                       "oldest":_oldest,"whales":_w}
    intro=None  # the intro line is gone: it never said anything the chips beside it didn't

    def sup(key,value):
        return "unconfirmed" if key in suppressed else value

    DATA={
     "date":TODAY.strftime("%A, %-d %B %Y"),
     "date_iso":TODAY.isoformat(),
     "name":a.name,
     "hero_intro":intro,
     "move":move,
     "concentration":concentration,
     # THE RECEIPT. The only line alive for a first-run, CSV-only user with no target and no prior
     # export — which is 6 of 8. Every catastrophic failure was the panel speaking about a number it
     # had not earned, in the same confident font as one it had; this says which file it read, how
     # much of it survived, and how old it is, so the 700px below inherit a provenance instead of
     # asking for trust. An export the rep took 6 days ago is a different product from a live one,
     # and until now the panel never said so.
     "receipt":{"file":os.path.basename(a.deals),"rows_in":n_in,"kept":len(deals),
                "exported":(prev_run_today or None)},
     "issue_chip":({"count":n_issue,"level":("blocker" if n_block else "warning")} if n_issue else None),
     "issues":[{k:i[k] for k in ("id","rule","severity","csv_lines","saw","assumed","question","choices","choices_values","emit","raw_stage","title","override_key","affects","proposed_fix","resolved")} for i in issues],
     "suppressed":sorted(suppressed),
     "insights":{"overdue":commit_overdue,"at_risk":sup("at_risk",fmt(at_risk)),"whale_note":whale_note},
     "activity":[],
     "diff":diff,"target":target,
     "plan":plan,"plan_done":0,"plan_total":plan_total,"plan_overflow":plan_overflow,
     "meetings":meetings,"meetings_internal":internal_ct,
     "commitments":commitments,"commit_open":commit_open,"commit_overdue":commit_overdue,
     "pipeline":{"total":sup("weighted",fmt(pipeline_total)),"count":(("unconfirmed" if "counts" in suppressed else len(open_oneoff))),
                 "label":"(OPEN)","suppressed":bool({"weighted","pipeline_total"} & suppressed),
                 "stages":([] if ({"weighted","stages"} & suppressed) else stages),
                 "unconfirmed_bar":({"count":len(unconfirmed),"value":unconf_value} if unconfirmed else None),
                 "month_note":(sup("month",f"{fmt(pipeline_month)} closing by {hend.strftime('%-d %b')}") if has_close else None),
                 "retainer_note":(f"{len(retainers)} renewal{'s' if len(retainers)>1 else ''} excluded" if retainers else None),
                 "parked_note":((f"{len(parked)} parked · {fmt(round(sum(gbp(d['value'],d['cur']) or 0 for d in parked)))} excluded") if parked else None),
                 "category":fc_view},
     "stale":([] if "stale" in suppressed else stale),"stale_count":("unconfirmed" if "stale" in suppressed else len(stale)),
     # the drill-in states the threshold it used; it must never guess or hardcode one
     "stale_days":STALE_DAYS,
     "at_risk":sup("at_risk",fmt(at_risk)),
     "retainers":[{"name":d["name"],"company":d["company"],
                   "monthly":(fmt(d["monthly"],disp_sym) if d["monthly"] else None),
                   "value":round(gbp(d["value"],d["cur"]) or 0)} for d in retainers],
     # ---- Your book of business (tab 2): do I trust it / how am I tracking ----
     # Every figure here is the SAME object the Desk renders (target, stages, stale, commitments,
     # issues) — the Book is a second view of one truth, never a second calculation of it.
     "book":{
       "target_unweighted":(None if money_suppressed else unweighted_total),
       "target_weighted":(None if money_suppressed else pipeline_total),
       "open_count":(("unconfirmed" if "counts" in suppressed else len(open_oneoff))),
       "horizon":{"label":horizon,"end":hend.strftime("%-d %b %Y"),
                  "weighted":(None if money_suppressed else pipeline_month),
                  "count":len(month_deals),"no_close":no_close} if has_close else None,
       "health":{"rows_in":n_in,"kept":len(deals),"skipped":len(skipped),"junk":len(junk),
                 "blockers":n_block,"issues":n_issue,
                 "skipped_detail":[{"line":i,"why":w} for i,w in skipped[:200]],
                 "junk_detail":[{"line":i,"why":w} for i,w in junk[:100]],
                 "resolved":resolved_notes},
       "currency":{"mixed":len(currencies)>1,"currencies":sorted(currencies),
                   # GBP is the base: a "GBP -> GBP @ 1" row is noise, not provenance.
                   "rates":({c:FX_TO_GBP.get(c) for c in sorted(currencies)
                             if str(c).upper() not in ("GBP","£")} if len(currencies)>1 else None),
                   "note":("Static rates, not live FX. Set your own in overrides.fx."
                           if len(currencies)>1 else None)},
     },
    }

    # ---- report tail ----
    rep(f"\n## Rows\n- rows in file: {n_in}\n- deals kept: {len(deals)}\n- skipped: {len(skipped)}\n- junk skipped: {len(junk)}")
    for ix,why in skipped[:80]: rep(f"  - line {ix}: {why}")
    for ix,why in junk[:40]: rep(f"  - JUNK line {ix}: {why}")
    if dupes:
        rep(f"\n## Duplicate deal ids — policy {dedupe_policy}, discarded {len(dupes)} row(s)")
        for d in dupes:
            rep(f"  - line {d['line']} · {d['deal_id']} · {d['discarded_name']} · stage '{d['discarded_stage']}' · "
                f"value {d['discarded_value']} · last activity {d['discarded_last_activity']}"+("  [FRESHER than kept]" if d["fresher"] else ""))
        # headline delta under the OTHER dedupe policy (so the user sees what the alternative costs)
        def _dedupe_totals(policy):
            seen2={}; deals2=[]
            for p in parsed:
                did=p["deal_id"]
                if did in seen2:
                    prev=seen2[did]; keep_new=False
                    if policy=="most-recent":
                        a_lt=p["last_touch"]; b_lt=deals2[prev]["last_touch"]
                        if a_lt and (b_lt is None or a_lt>b_lt): keep_new=True
                    if keep_new: deals2[prev]=p
                    continue
                seen2[did]=len(deals2); deals2.append(p)
            stg={}; ar=0
            for d in deals2:
                fs="Active Retainer" if d["is_retainer"] and d["stage"] in OPEN_STAGES else d["stage"]
                if d.get("held") or fs not in OPEN_STAGES: continue
                v=gbp(d["value"],d["cur"]) or 0
                stg[fs]=stg.get(fs,0.0)+v*(d["prob"] if d["prob"] is not None else STAGE_DEFAULT_PROB.get(fs,0.2))
                if d["last_touch"] and (TODAY-d["last_touch"]).days>=STALE_DAYS: ar+=round(v)
            return sum(round(x) for x in stg.values()), ar
        other = "most-recent" if dedupe_policy!="most-recent" else "keep-first"
        ow,oar=_dedupe_totals(other)
        other_label = "keep-most-recent" if other=="most-recent" else "keep-first"
        rep(f"- under {other_label}: weighted {fmt(ow)}, at-risk {fmt(oar)}")
    rep(f"\n## Headline figures")
    rep(f"- weighted open pipeline: {'unconfirmed' if 'weighted' in suppressed else fmt(pipeline_total)} ({len(open_oneoff)} open one-off deals)")
    rep(f"- unweighted open pipeline: {'unconfirmed' if 'pipeline_total' in suppressed else fmt(unweighted_total)}")
    if unconfirmed: rep(f"- UNCONFIRMED bucket (unrecognised stages): {len(unconfirmed)} deal(s), {fmt(unconf_value)} unweighted")
    rep(f"- stage weighted: "+", ".join(f"{s['name']} {fmt(s['weighted'])}/{s['count']}" for s in stages))
    rep(f"- stale (>= {STALE_DAYS}d): {'unconfirmed' if 'stale' in suppressed else str(len(stale))+' deals, '+fmt(at_risk)+' at risk'}")
    rep(f"- retainers: {len(retainers)}; held (HOLD close): {len(held)}; commitments: {commit_open} open, {commit_overdue} overdue")
    rep("\n## What changed")
    if a.no_state:
        rep("- state disabled (--no-state); no diff computed")
    elif diff is None:
        rep("- "+(state_note+"; baseline saved" if state_note else "first run, baseline saved"))
    else:
        rep(f"- since {diff['since']}: {len(diff['new'])} new, {len(diff['moved'])} moved, {len(diff['slipped'])} slipped, {len(diff['gone'])} gone")
        for x in diff["new"]: rep(f"  - NEW: {x['name']}"+(f" {fmt(x['value'])}" if x['value'] is not None else ""))
        if diff.get("rekey"): rep(f"  - RE-KEY: {len(diff['rekey'])} pair(s) look re-keyed (net {diff['real_new']} new / {diff['real_gone']} gone)")
        for x in diff["moved"]: rep(f"  - MOVED: {x['name']}: {x['from']} -> {x['to']}")
        for x in diff["slipped"]: rep(f"  - SLIPPED: {x['name']}: {x['from']} -> {x['to']}")
        for x in diff["gone"]: rep(f"  - GONE: {x['name']} ({x['outcome']})")
    if target:
        cov=("n/a" if target["coverage_pct"] is None else f"{target['coverage_pct']}% (weighted)")
        g=target["gap"]
        gp=("n/a" if g is None else (f"{fmt(-g)} over target" if g<0 else f"gap {fmt(g)}"))
        rep(f"\n## Target\n- {fmt(target['amount'])} per {target['period']}: coverage {cov}, {gp}")
        if target.get("commit"):
            c=target["commit"]; cg=c["gap"]
            rep(f"- Commit basis: {fmt(c['total'])} · {c['coverage_pct']}% of target · "
                +(f"{fmt(-cg)} over target" if cg<0 else f"gap {fmt(cg)}"))
    elif target_bad:
        rep("\n## Target\n- target override present but unreadable; ignored")
    if resolved_notes:
        rep("\n## Resolved (answers applied)")
        for r_ in resolved_notes: rep(f"- {r_}")
    if issues:
        rep("\n## Issues raised")
        for i in issues:
            rep(f"- [{i['severity'].upper()}] {i['rule']}: {i['saw']}"+(f"  (Q: {i['question']})" if i['question'] else ""))
    if warnings: rep("\n## Warnings\n"+"\n".join("- "+w for w in warnings))

    summary={"today":TODAY.isoformat(),"rows_in":n_in,"deals_kept":len(deals),"skipped":len(skipped),
     "junk_skipped":len(junk),
     "pipeline_weighted":pipeline_total,"pipeline_open_weighted":pipeline_total,
     "pipeline_unweighted":unweighted_total,
     "pipeline_month_weighted":pipeline_month,"month_deal_count":len(month_deals),
     "open_deals":len(open_oneoff),"unconfirmed_deals":len(unconfirmed),"unconfirmed_value":unconf_value,
     "no_close_date":no_close,
     "whales":[d["name"] for d in open_oneoff if d["whale"]],
     "stages":{s["name"]:{"weighted":s["weighted"],"count":s["count"]} for s in stages},
     "stale_count":len(stale),"at_risk":at_risk,"retainers":len(retainers),"held":len(held),
     "commit_open":commit_open,"commit_overdue":commit_overdue,"percent_scale":percent_scale,
     "currencies":sorted(currencies),"whale_threshold":whale_thresh,"warnings":warnings,
     "dayfirst":DAYFIRST,"date_evidence":date_evidence,"no_last_activity":no_last_activity,
     "missing_value":missing_value,
     "meetings_today":len(meetings),"meetings_internal":internal_ct,
     "suppressed":sorted(suppressed),
     "n_blockers":n_block,"n_issues":n_issue,
     "issue_rules":[i["rule"] for i in issues],
     "forecast_category":({k:{"count":v["count"],"gbp":v["gbp"]} for k,v in fc_view.items()} if fc_view else None),
     "resolved":resolved_notes,
     "diff_counts":({k:len(diff[k]) for k in ("new","moved","slipped","gone")} if diff else None),
     "diff_rekey":(len(diff["rekey"]) if diff else None),
     "diff_real_new":(diff.get("real_new") if diff else None),
     "diff_real_gone":(diff.get("real_gone") if diff else None),
     "parked":len(parked),"id_reused":len(id_reused),
     "target":target,
     "skipped_detail":[f"line {i}: {w}" for i,w in skipped]}

    # ---- render ----
    html=open(TEMPLATE).read()
    for cls in ("hero","plan","meetings","commitments","pipeline","stale"):
        html=re.sub(r'(<section class="'+cls+r' card">).*?(</section>)',r'\1\2',html,count=1,flags=re.DOTALL)
    data_script='<script id="scp-data">window.SCP_DATA = '+json.dumps(DATA,ensure_ascii=False,default=str).replace("<","\\u003c")+';</script>'
    html=html.replace("</head>",MODAL_CSS+"\n</head>",1)
    html=html.replace("</body>",data_script+"\n"+RENDER_JS+"\n</body>",1)
    _outdir=os.path.dirname(os.path.abspath(a.out))
    if _outdir and not os.path.isdir(_outdir): os.makedirs(_outdir)
    open(a.out,"w").write(html)
    if not a.no_state:
        try:
            # D9: persist the run's --today + file so the NEXT run's diff label reads "since Fri 11 Jul's
            # file", not a wall-clock save time. D4: persist raw stage text so moved fires on raw change.
            new_state={"saved_at":dt.datetime.now().isoformat(timespec="seconds"),
                       "run_today":TODAY.isoformat(),"deals_file":os.path.basename(a.deals),
                       "deals":{d["diff_key"]:{"name":d["name"],"company":d["company"],"stage":d["final_stage"],
                                "stage_raw":d["stageraw"],
                                "value":(round(gbp(d["value"],d["cur"]) or 0) if d["value"] is not None else None),
                                "expected_close":(d["expected_close"].isoformat() if d["expected_close"] else None),
                                "last_touch":(d["last_touch"].isoformat() if d["last_touch"] else None)}
                                for d in open_oneoff}}
            open(state_path,"w").write(json.dumps(new_state,default=str))
        except Exception as _e:
            report_lines.append(f"\n## State\n- could not write state: {_e}")
    open(a.report,"w").write("\n".join(report_lines)+"\n")
    if a.summary_json: open(a.summary_json,"w").write(json.dumps(summary,indent=2,default=str))
    issues_path=a.issues_json or os.path.join(os.path.dirname(os.path.abspath(a.report)) or ".","issues.json")
    open(issues_path,"w").write(json.dumps({"issues":issues,"suppressed":sorted(suppressed)},indent=2,default=str))
    print("PANEL:",a.out); print("REPORT:",a.report); print("ISSUES:",issues_path)
    print("SUMMARY:",json.dumps({k:summary[k] for k in ("deals_kept","open_deals","pipeline_weighted","stale_count","at_risk","n_blockers","suppressed","issue_rules")},default=str))

_here=os.path.dirname(os.path.abspath(__file__))
RENDER_JS=open(os.path.join(_here,"render.js.html")).read()
MODAL_CSS=open(os.path.join(_here,"modal.css.html")).read()

if __name__=="__main__":
    main()
