"""Model regresi linear sederhana (numpy) untuk simulasi / prediksi nilai ujian.

Dipakai halaman "Simulasi nilai": memprediksi nilai dari profil siswa, menguraikan
kontribusi tiap faktor terhadap siswa rata-rata, dan memberi rekomendasi perubahan.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt

import numpy as np
import pandas as pd

from .analysis import PASS_MARK
from .data_loader import LABEL_ID, ORDER

NUM = ["Hours_Studied", "Attendance", "Previous_Scores", "Tutoring_Sessions",
       "Sleep_Hours", "Physical_Activity"]
CAT = list(ORDER)

# Rentang input simulasi
NUM_RANGE = {"Hours_Studied": (0, 44, 1), "Attendance": (60, 100, 1), "Previous_Scores": (50, 100, 1),
             "Tutoring_Sessions": (0, 8, 1), "Sleep_Hours": (4, 10, 1), "Physical_Activity": (0, 6, 1)}


@dataclass
class Model:
    names: list[str]          # nama kolom desain
    owner: list[str]          # faktor asal tiap kolom desain
    coef: np.ndarray
    intercept: float
    x_mean: np.ndarray
    r2: float
    mae: float
    resid_sd: float
    n: int
    mode: dict                # nilai modus kategori (untuk default)
    median: dict              # median numerik (untuk default)

    # ------------------------------------------------------------ desain
    def row(self, profile: dict) -> np.ndarray:
        x = []
        for name, own in zip(self.names, self.owner):
            if own in NUM:
                x.append(float(profile[own]))
            else:
                level = name.split("=", 1)[1]
                x.append(1.0 if str(profile[own]) == level else 0.0)
        return np.array(x)

    def predict(self, profile: dict) -> float:
        return float(self.intercept + self.row(profile) @ self.coef)

    def baseline(self) -> float:
        """Prediksi untuk 'siswa rata-rata' (semua fitur = rata-rata data)."""
        return float(self.intercept + self.x_mean @ self.coef)

    def contributions(self, profile: dict) -> pd.Series:
        """Kontribusi tiap faktor (poin) relatif terhadap siswa rata-rata."""
        d = (self.row(profile) - self.x_mean) * self.coef
        return pd.Series(d, index=self.owner).groupby(level=0).sum()

    def p_pass(self, pred: float) -> float:
        z = (PASS_MARK - 0.5 - pred) / self.resid_sd
        return 1 - 0.5 * (1 + erf(z / sqrt(2)))


def _design(df: pd.DataFrame):
    cols, names, owner = [], [], []
    for c in NUM:
        cols.append(df[c].astype(float).values)
        names.append(c)
        owner.append(c)
    for c in CAT:
        vals = df[c].astype(str)
        for level in ORDER[c][1:]:          # level pertama = baseline
            cols.append((vals == level).astype(float).values)
            names.append(f"{c}={level}")
            owner.append(c)
    return np.column_stack(cols), names, owner


def fit(df: pd.DataFrame) -> Model:
    d = df.copy()
    for c in CAT:  # isi nilai kosong dengan modus
        mode = d.loc[d[c].astype(str) != "Tidak diketahui", c].astype(str).mode().iloc[0]
        d[c] = d[c].astype(str).replace("Tidak diketahui", mode)
    X, names, owner = _design(d)
    y = d["Exam_Score"].astype(float).values
    A = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ beta
    resid = y - pred
    r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return Model(
        names=names, owner=owner, coef=beta[1:], intercept=float(beta[0]), x_mean=X.mean(axis=0),
        r2=float(r2), mae=float(np.abs(resid).mean()), resid_sd=float(resid.std(ddof=len(beta))),
        n=len(y),
        mode={c: d[c].astype(str).mode().iloc[0] for c in CAT},
        median={c: float(d[c].median()) for c in NUM},
    )


# Perubahan yang realistis untuk diusulkan (faktor yang bisa diubah siswa/sekolah/orang tua)
ACTIONS = [
    ("Attendance", "num", 10, "Naikkan kehadiran +10 poin persen"),
    ("Hours_Studied", "num", 5, "Tambah jam belajar +5 jam/minggu"),
    ("Tutoring_Sessions", "num", 1, "Tambah 1 sesi les/bulan"),
    ("Parental_Involvement", "cat", 1, "Tingkatkan keterlibatan orang tua satu tingkat"),
    ("Access_to_Resources", "cat", 1, "Tingkatkan akses sumber belajar satu tingkat"),
    ("Motivation_Level", "cat", 1, "Tingkatkan motivasi satu tingkat"),
    ("Peer_Influence", "cat", 1, "Arahkan ke lingkungan teman yang lebih positif"),
    ("Physical_Activity", "num", 1, "Tambah aktivitas fisik +1 jam/minggu"),
    ("Sleep_Hours", "num", 1, "Tambah jam tidur +1 jam/hari"),
]


def recommendations(m: Model, profile: dict) -> list[dict]:
    base = m.predict(profile)
    out = []
    for col, kind, step, text in ACTIONS:
        new = dict(profile)
        if kind == "num":
            lo, hi, _ = NUM_RANGE[col]
            if profile[col] >= hi:
                continue
            new[col] = min(hi, profile[col] + step)
            change = f"{profile[col]:g} → {new[col]:g}"
        else:
            levels = ORDER[col]
            i = levels.index(str(profile[col])) if str(profile[col]) in levels else 0
            if i >= len(levels) - 1:
                continue
            new[col] = levels[i + 1]
            change = f"{profile[col]} → {new[col]}"
        gain = m.predict(new) - base
        if gain > 0.05:
            out.append(dict(col=col, label=LABEL_ID[col], text=text, change=change, gain=gain))
    return sorted(out, key=lambda r: r["gain"], reverse=True)
