"""Upload CSV awal ke Supabase (sekali jalan).

Pakai SERVICE ROLE key (rahasia, jangan taruh di dashboard):
  SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python scripts/upload_to_supabase.py data/StudentPerformanceFactors.csv
"""
import json
import math
import os
import sys

import pandas as pd
import requests

url = os.environ["SUPABASE_URL"].rstrip("/")
key = os.environ["SUPABASE_SERVICE_KEY"]
table = os.environ.get("SUPABASE_TABLE", "student_performance")

df = pd.read_csv(sys.argv[1])
df.columns = [c.lower() for c in df.columns]
df["exam_score"] = df["exam_score"].clip(upper=100)
records = [{k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()}
           for r in df.to_dict("records")]

headers = {"apikey": key, "Authorization": f"Bearer {key}",
           "Content-Type": "application/json", "Prefer": "return=minimal"}
for i in range(0, len(records), 500):
    r = requests.post(f"{url}/rest/v1/{table}", headers=headers,
                      data=json.dumps(records[i:i + 500], default=int), timeout=60)
    r.raise_for_status()
    print(f"uploaded {min(i + 500, len(records))}/{len(records)}")
