"""Sumber data dashboard.

Pilih sumber lewat secrets / environment variable DATA_SOURCE:
  - "csv"     : file lokal data/StudentPerformanceFactors.csv (default, statis)
  - "gsheet"  : Google Sheets yang di-"Publish to web" sebagai CSV (gratis, near real-time)
  - "supabase": tabel Postgres di Supabase via REST API (gratis, real-time)
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
LOCAL_CSV = ROOT / "data" / "StudentPerformanceFactors.csv"

ORDER = {
    "Parental_Involvement": ["Low", "Medium", "High"],
    "Access_to_Resources": ["Low", "Medium", "High"],
    "Motivation_Level": ["Low", "Medium", "High"],
    "Family_Income": ["Low", "Medium", "High"],
    "Teacher_Quality": ["Low", "Medium", "High"],
    "Peer_Influence": ["Negative", "Neutral", "Positive"],
    "Parental_Education_Level": ["High School", "College", "Postgraduate"],
    "Distance_from_Home": ["Far", "Moderate", "Near"],
    "Extracurricular_Activities": ["No", "Yes"],
    "Internet_Access": ["No", "Yes"],
    "Learning_Disabilities": ["Yes", "No"],
    "School_Type": ["Public", "Private"],
    "Gender": ["Male", "Female"],
}

LABEL_ID = {
    "Hours_Studied": "Jam belajar / minggu",
    "Attendance": "Kehadiran (%)",
    "Parental_Involvement": "Keterlibatan orang tua",
    "Access_to_Resources": "Akses sumber belajar",
    "Extracurricular_Activities": "Ekstrakurikuler",
    "Sleep_Hours": "Jam tidur / hari",
    "Previous_Scores": "Nilai sebelumnya",
    "Motivation_Level": "Motivasi",
    "Internet_Access": "Akses internet",
    "Tutoring_Sessions": "Sesi les / bulan",
    "Family_Income": "Pendapatan keluarga",
    "Teacher_Quality": "Kualitas guru",
    "School_Type": "Jenis sekolah",
    "Peer_Influence": "Pengaruh teman",
    "Physical_Activity": "Aktivitas fisik (jam/minggu)",
    "Learning_Disabilities": "Kesulitan belajar",
    "Parental_Education_Level": "Pendidikan orang tua",
    "Distance_from_Home": "Jarak rumah",
    "Gender": "Gender",
    "Exam_Score": "Nilai ujian",
}

NUMERIC = ["Hours_Studied", "Attendance", "Sleep_Hours", "Previous_Scores",
           "Tutoring_Sessions", "Physical_Activity", "Exam_Score"]


def nf(v: float, d: int = 1, sign: bool = False) -> str:
    """Format angka gaya Indonesia: 1.234,5"""
    s = f"{v:+,.{d}f}" if sign else f"{v:,.{d}f}"
    s = s.replace(",", "_").replace(".", ",").replace("_", ".")
    return s.replace("-0,0", "0,0").replace("+0,0", "0,0") if abs(v) < 0.05 and d == 1 else s


def _setting(key: str, default: str | None = None) -> str | None:
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:  # secrets.toml tidak ada
        pass
    return os.environ.get(key, default)


def _from_supabase() -> pd.DataFrame:
    url = _setting("SUPABASE_URL").rstrip("/")
    key = _setting("SUPABASE_ANON_KEY")
    table = _setting("SUPABASE_TABLE", "student_performance")
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    rows, step, start = [], 1000, 0
    while True:  # PostgREST membatasi 1000 baris per request -> paging
        r = requests.get(f"{url}/rest/v1/{table}?select=*",
                         headers={**headers, "Range": f"{start}-{start + step - 1}"},
                         timeout=30)
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < step:
            break
        start += step
    df = pd.DataFrame(rows)
    # kolom di Postgres huruf kecil -> kembalikan ke nama asli
    mapping = {c.lower(): c for c in LABEL_ID}
    return df.rename(columns=mapping)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    ids = df["id"] if "id" in df.columns else pd.Series(range(1, len(df) + 1), index=df.index)
    df = df[[c for c in LABEL_ID if c in df.columns]].copy()
    df.insert(0, "ID", ids.astype(int).values)
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Exam_Score"])
    df["Exam_Score"] = df["Exam_Score"].clip(upper=100)  # 1 baris bernilai 101
    for c, cats in ORDER.items():
        if c in df.columns:
            df[c] = pd.Categorical(df[c].fillna("Tidak diketahui"),
                                   categories=cats + ["Tidak diketahui"], ordered=True)
    return df


@st.cache_data(ttl=int(_setting("CACHE_TTL_SECONDS", "60")), show_spinner="Memuat data…")
def load_data() -> tuple[pd.DataFrame, str]:
    source = (_setting("DATA_SOURCE", "csv") or "csv").lower()
    if source == "supabase":
        raw = _from_supabase()
    elif source == "gsheet":
        raw = pd.read_csv(_setting("GSHEET_CSV_URL"))
    else:
        raw = pd.read_csv(LOCAL_CSV)
    stamp = pd.Timestamp.now(tz="Asia/Jakarta").strftime("%d %b %Y %H:%M:%S WIB")
    return clean(raw), f"{source} · dimuat {stamp}"
