"""Perhitungan statistik yang dipakai grafik, dialog detail, dan insight otomatis."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data_loader import LABEL_ID, ORDER, nf

PASS_MARK = 70

# Pengelompokan faktor numerik: (batas bin, label)
BINS: dict[str, tuple[list[float], list[str]]] = {
    "Attendance": ([59, 70, 80, 90, 100], ["60–70", "71–80", "81–90", "91–100"]),
    "Hours_Studied": ([0, 10, 15, 20, 25, 30, 45], ["≤10", "11–15", "16–20", "21–25", "26–30", ">30"]),
    "Previous_Scores": ([49, 60, 70, 80, 90, 100], ["50–60", "61–70", "71–80", "81–90", "91–100"]),
    "Tutoring_Sessions": ([-1, 0, 1, 2, 3, 8], ["0", "1", "2", "3", "4+"]),
    "Sleep_Hours": ([3, 5, 6, 7, 8, 10], ["4–5", "6", "7", "8", "9–10"]),
    "Physical_Activity": ([-1, 1, 2, 3, 4, 6], ["0–1", "2", "3", "4", "5–6"]),
}

GROUPS = {
    "Akademik": ["Attendance", "Hours_Studied", "Previous_Scores", "Tutoring_Sessions",
                 "Teacher_Quality", "Access_to_Resources"],
    "Keluarga & Lingkungan": ["Parental_Involvement", "Family_Income", "Parental_Education_Level",
                              "Distance_from_Home", "Internet_Access", "School_Type", "Peer_Influence"],
    "Personal": ["Motivation_Level", "Learning_Disabilities", "Extracurricular_Activities",
                 "Sleep_Hours", "Physical_Activity", "Gender"],
}
ALL_FACTORS = [c for g in GROUPS.values() for c in g]

# Kolom yang ditampilkan di profil kelompok
PROFILE_NUM = ["Attendance", "Hours_Studied", "Previous_Scores", "Tutoring_Sessions",
               "Sleep_Hours", "Physical_Activity"]
PROFILE_CAT = {  # kolom -> kategori "positif" yang dihitung persentasenya
    "Motivation_Level": "High", "Parental_Involvement": "High", "Access_to_Resources": "High",
    "Family_Income": "High", "Teacher_Quality": "High", "Peer_Influence": "Positive",
    "Parental_Education_Level": "Postgraduate", "Learning_Disabilities": "Yes",
    "Internet_Access": "Yes", "Extracurricular_Activities": "Yes", "School_Type": "Private",
    "Distance_from_Home": "Near", "Gender": "Female",
}


def group_key(df: pd.DataFrame, col: str) -> pd.Series:
    """Label kelompok tiap baris untuk faktor `col` (bin untuk numerik)."""
    if col in BINS:
        b, l = BINS[col]
        return pd.cut(df[col], b, labels=l, include_lowest=True).astype(str)
    return df[col].astype(str)


def subset(df: pd.DataFrame, col: str, group: str) -> pd.DataFrame:
    return df[group_key(df, col) == str(group)]


def group_stats(df: pd.DataFrame, col: str) -> pd.DataFrame:
    key = group_key(df, col)
    order = BINS[col][1] if col in BINS else ORDER[col]
    rows = []
    for g in order:
        s = df.loc[key == str(g), "Exam_Score"]
        if len(s) == 0:
            continue
        rows.append(dict(group=str(g), n=len(s), mean=s.mean(), median=s.median(),
                         pass_rate=(s >= PASS_MARK).mean(),
                         ci=1.96 * s.std(ddof=1) / np.sqrt(len(s)) if len(s) > 1 else 0.0))
    return pd.DataFrame(rows)


def factor_effects(df: pd.DataFrame) -> pd.DataFrame:
    """Selisih rata-rata nilai antara kelompok terendah -> tertinggi tiap faktor.
    Numerik: kuartil bawah (≤Q1) vs kuartil atas (≥Q3). Kategori: kategori pertama vs terakhir."""
    rows = []
    for col in ALL_FACTORS:
        if col in BINS:
            q1, q3 = df[col].quantile([0.25, 0.75])
            lo = df.loc[df[col] <= q1, "Exam_Score"].mean()
            hi = df.loc[df[col] >= q3, "Exam_Score"].mean()
            low_lbl, high_lbl, kind = f"≤{q1:g}", f"≥{q3:g}", "numerik"
        else:
            cats = [c for c in ORDER[col] if (df[col] == c).any()]
            if len(cats) < 2:
                continue
            lo = df.loc[df[col] == cats[0], "Exam_Score"].mean()
            hi = df.loc[df[col] == cats[-1], "Exam_Score"].mean()
            low_lbl, high_lbl, kind = cats[0], cats[-1], "kategori"
        if np.isnan(lo) or np.isnan(hi):
            continue
        rows.append(dict(col=col, label=LABEL_ID[col], effect=hi - lo, abs_effect=abs(hi - lo),
                         low=low_lbl, high=high_lbl, kind=kind))
    out = pd.DataFrame(rows).sort_values("abs_effect", ascending=False).reset_index(drop=True)
    out["rank"] = out.index + 1
    return out


def profile_compare(sub: pd.DataFrame, ref: pd.DataFrame):
    num = [(LABEL_ID[c], sub[c].mean(), ref[c].mean()) for c in PROFILE_NUM]
    cat = []
    for c, val in PROFILE_CAT.items():
        a, b = (sub[c] == val).mean() * 100, (ref[c] == val).mean() * 100
        cat.append((f"{LABEL_ID[c]}: {val}", a, b, a - b))
    cat.sort(key=lambda r: abs(r[3]), reverse=True)
    return num, cat


def insights(df: pd.DataFrame, eff: pd.DataFrame) -> list[str]:
    top, second = eff.iloc[0], eff.iloc[1]
    weak = eff[eff["abs_effect"] < 0.5]["label"].tolist()
    out = [
        f"**{top.label}** adalah faktor terkuat — kelompok {top.high} unggul "
        f"**{nf(top.effect, 1, True)} poin** dibanding {top.low}.",
        f"Disusul **{second.label}** ({nf(second.effect, 1, True)} poin antara {second.low} dan {second.high}).",
    ]
    if {"Attendance", "Hours_Studied"} <= set(df.columns):
        best = df[(df.Attendance > 90) & (df.Hours_Studied > 25)]["Exam_Score"]
        worst = df[(df.Attendance <= 70) & (df.Hours_Studied <= 15)]["Exam_Score"]
        if len(best) and len(worst):
            out.append(f"Kombinasi kehadiran >90% **dan** belajar >25 jam/minggu: rata-rata "
                       f"**{nf(best.mean(), 1)}**, vs **{nf(worst.mean(), 1)}** untuk kehadiran ≤70% & ≤15 jam.")
    if weak:
        out.append(f"Hampir tak berpengaruh (<0,5 poin): {', '.join(weak)}.")
    out.append(f"Nilai sangat terpusat (IQR {nf(df.Exam_Score.quantile(.25), 0)}–"
               f"{nf(df.Exam_Score.quantile(.75), 0)}); hanya **{(df.Exam_Score >= PASS_MARK).mean():.0%}** "
               f"siswa mencapai ≥{PASS_MARK}.")
    return out


def percentile(series: pd.Series, value: float) -> float:
    return (series < value).mean() * 100
