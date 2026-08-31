#!/usr/bin/env python3
"""Sales Control Panel — demo data generator.

Writes three sample files dated relative to TODAY, so the demo always looks
live no matter when it is run. Sample data, not the user's: every file is
labelled SAMPLE and is meant to be deleted once real data is connected.

    python3 make_demo_data.py [--out DIR] [--today YYYY-MM-DD]
"""
import argparse, datetime as dt, pandas as pd, os

p = argparse.ArgumentParser()
p.add_argument("--out", default=".")
p.add_argument("--today", default=None)
a = p.parse_args()
T = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
d = lambda n: (T + dt.timedelta(days=n)).strftime("%d/%m/%Y")

# close offsets are spread from +4 to +55 days so something always sits inside
# the current month whatever day of the month the demo is run.
rows = [
 ("D-1041","Priya Shah","Eastgate Group","Discovery",18000,27,-1,"Asked for a case study from a similar size firm"),
 ("D-1042","Matt Dowsing","Northbrook Ltd","Discovery",8500,34,-2,"Wants pricing in writing before next call"),
 ("D-1043","Marcus Ainsworth","Hadley Vine","Discovery",16000,41,-9,"Gone quiet after intro call"),
 ("D-1044","Adetola Olusola","Stratton Vale","Discovery",22000,20,-3,"Promised case studies"),
 ("D-1045","Liam Worsley","Aldgate & Co","Discovery",15000,55,-14,"Budget confirmed for next quarter"),
 ("D-1046","Tom Baxter","Holloway Burns","Discovery",35000,48,-1,"Referred in by Meridian"),
 ("D-1047","Helen Dale","Brackenbury","Demo",30000,13,-4,"Bringing her FD to the next one"),
 ("D-1048","Olivia Whitford","Drayton Group","Demo",25000,18,-11,"Asked about integration, no reply since"),
 ("D-1049","Sarah Kettering","Penmere","Demo",22000,9,-7,"Wants the pricing re-cut"),
 ("D-1050","Ben Halloran","Marsden Hill","Demo",28000,25,-2,"Champion is keen, procurement unknown"),
 ("D-1051","Vikram Joshi","Tarvill","Demo",20000,31,-5,""),
 ("D-1052","Claire Foulkes","Westmoor","Demo",19000,16,-1,"Second demo booked"),
 ("D-1053","Patrick Evans","Norfield Partners","Proposal",35000,7,-2,"Decision this week"),
 ("D-1054","Daniel Mensah","Cresswick","Proposal",50000,11,-16,"Sent proposal, chasing"),
 ("D-1055","Mira Kapoor","Pickering Group","Proposal",20000,21,-4,"Two tiers requested"),
 ("D-1056","David Lange","Halewood CA","Proposal",15000,28,-3,""),
 ("D-1057","Rajiv Patel","Belford & Crowe","Negotiation",45000,5,-6,"Wants a 90 day pilot clause"),
 ("D-1058","Anita Brookes","Kemble LLP","Negotiation",45000,4,-2,"Legal reviewing"),
 ("D-1059","Grace Lindqvist","Ashby Rowe","Negotiation",26000,12,-8,"Haggling on year one"),
 ("D-1060","Sam Okonkwo","Trentham Ltd","Discovery",12000,None,-3,"No close date agreed yet"),
 ("D-1061","Rachel Nunn","Colvin Hart","Demo",17000,None,-12,"Interested but no timeline"),
 ("D-1062","James Whitmore","Meridian Advisory","Closed Won",72000,-21,-2,"Signed, 12 month term"),
 ("D-1063","Caroline Bingley","Netherfield","Closed Won",54000,-9,-1,"Renewal due in 10 months"),
 ("D-1064","Neil Frost","Oakbourne","Closed Lost",30000,-30,-30,"Went with incumbent"),
]
deals = pd.DataFrame([{"Ref":r[0],"Contact":r[1],"Company":r[2],"Where it's at":r[3],
    "Value":r[4],"Expected close":(d(r[5]) if r[5] is not None else ""),
    "Last spoke":d(r[6]),"Owner":"You","Notes":r[7]} for r in rows])

meetings = pd.DataFrame([
 {"Time":"09:30","Contact":"Helen Dale","Company":"Brackenbury","Subject":"Demo, second session","Notes":"Bringing her FD","Value":30000},
 {"Time":"11:00","Contact":"Patrick Evans","Company":"Norfield Partners","Subject":"Proposal review","Notes":"Decision this week","Value":35000},
 {"Time":"14:00","Contact":"Rajiv Patel","Company":"Belford & Crowe","Subject":"Contract call","Notes":"Pilot clause","Value":45000},
 {"Time":"16:15","Contact":"Sarah Kettering","Company":"Penmere","Subject":"Pricing follow up","Notes":"Re-cut numbers","Value":22000},
])
commitments = pd.DataFrame([
 {"Promise":"Send the pricing one-pager","Owed to":"Matt Dowsing","due_offset_days":0,"Status":"open"},
 {"Promise":"Send case studies from similar size firms","Owed to":"Adetola Olusola","due_offset_days":0,"Status":"open"},
 {"Promise":"Re-send the pricing breakdown","Owed to":"Sarah Kettering","due_offset_days":-2,"Status":"open"},
 {"Promise":"Introduce to FD","Owed to":"Helen Dale","due_offset_days":3,"Status":"open"},
 {"Promise":"Send the revised SoW","Owed to":"Patrick Evans","due_offset_days":1,"Status":"open"},
 {"Promise":"Share the implementation timeline","Owed to":"Rajiv Patel","due_offset_days":5,"Status":"open"},
 {"Promise":"Send the two-tier proposal","Owed to":"Mira Kapoor","due_offset_days":-4,"Status":"open"},
 {"Promise":"Send the signed order form","Owed to":"James Whitmore","due_offset_days":-6,"Status":"done"},
])

os.makedirs(a.out, exist_ok=True)
paths = []
for name, df, sheet in (("SAMPLE-deals",deals,"Deals"),("SAMPLE-meetings",meetings,"Meetings"),
                        ("SAMPLE-commitments",commitments,"Commitments")):
    fp = os.path.join(a.out, name + ".xlsx")
    with pd.ExcelWriter(fp, engine="openpyxl") as w:
        df.to_excel(w, sheet_name=sheet, index=False)
    paths.append(fp)
print("Demo data written for " + T.strftime("%d %b %Y") + ":")
for fp in paths: print("  " + fp)
