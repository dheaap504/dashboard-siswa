"""Dashboard Faktor Performa Siswa — Streamlit (gaya visual terinspirasi Soft UI).

Jalankan lokal:  streamlit run app.py
Klik titik / batang / sel pada grafik untuk membuka detail.
"""
from __future__ import annotations

import html
import re
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src import charts
from src.analysis import (BINS, GROUPS, PASS_MARK, PROFILE_CAT, PROFILE_NUM, factor_effects,
                          group_stats, insights, percentile, profile_compare, subset)
from src.data_loader import LABEL_ID, ORDER, _setting, load_data, nf
from src.model import CAT, NUM, NUM_RANGE, fit, recommendations

st.set_page_config(page_title="Dashboard Performa Siswa", page_icon="◐", layout="wide",
                   initial_sidebar_state="auto")

REFRESH = int(_setting("AUTO_REFRESH_SECONDS", "0"))
ss = st.session_state
ss.setdefault("nonce", 0)

_css = (Path(__file__).parent / "assets" / "style.css").read_text()
# baris kosong dibuang agar parser markdown tidak memotong blok <style>
st.markdown("<style>" + "\n".join(l for l in _css.splitlines() if l.strip()) + "</style>",
            unsafe_allow_html=True)


# ======================================================================= helper UI
def ms(name: str) -> str:
    return f'<span class="ms">{name}</span>'


def card_title(title: str, sub: str = ""):
    st.markdown(f'<p class="card-t">{title}</p>' + (f'<p class="card-s">{sub}</p>' if sub else ""),
                unsafe_allow_html=True)


def howto(text: str, icon: str = "touch_app"):
    st.markdown(f'<div class="howto">{ms(icon)}<div>{text}</div></div>', unsafe_allow_html=True)


def delta(v: float, d: int = 1, unit: str = "", invert: bool = False) -> str:
    if abs(v) < (0.05 if d else 0.5):
        return f'<span class="flat">0{unit}</span>'
    good = (v > 0) ^ invert
    arrow = "▲" if v > 0 else "▼"
    return f'<span class="{"up" if good else "down"}">{arrow} {nf(abs(v), d)}{unit}</span>'


def bold(t: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


clicks: list[tuple[str, dict, dict]] = []


def clickable(fig, name: str, kind: str, ctx: dict | None = None):
    ev = st.plotly_chart(fig, key=f"{name}_{ss.nonce}", on_select="rerun",
                         selection_mode="points", config=charts.CONFIG)
    pts = (ev or {}).get("selection", {}).get("points", []) if ev else []
    if pts:
        clicks.append((kind, pts[0], ctx or {}))


def static_chart(fig, key: str):
    st.plotly_chart(fig, key=key, config=charts.CONFIG)


def reset_selection():
    ss.nonce += 1


def unit(col: str) -> str:
    u = charts.UNIT.get(col, "")
    return "" if not u or u in LABEL_ID[col] else u


# ======================================================================= data
df_all, source_info = load_data()
stamp = source_info.split(" · ")[1] if " · " in source_info else source_info
src_name = source_info.split(" · ")[0]


@st.cache_data(show_spinner="Melatih model prediksi…")
def get_model(data: pd.DataFrame):
    return fit(data)


PAGES = {
    "Ringkasan": (":material/space_dashboard: Ringkasan",
                  "Gambaran umum nilai ujian dan faktor yang paling berpengaruh."),
    "Eksplorasi faktor": (":material/insights: Eksplorasi faktor",
                          "Lihat rata-rata nilai untuk setiap kelompok dalam satu faktor."),
    "Kombinasi faktor": (":material/grid_view: Kombinasi faktor",
                         "Efek gabungan dua faktor numerik terhadap nilai ujian."),
    "Bandingkan kelompok": (":material/compare_arrows: Bandingkan kelompok",
                            "Bandingkan dua kelompok siswa yang Anda definisikan sendiri."),
    "Simulasi nilai": (":material/calculate: Simulasi nilai",
                       "Perkirakan nilai ujian dari profil siswa dan lihat perubahan yang paling berdampak."),
    "Profil siswa": (":material/person_search: Profil siswa",
                     "Setiap titik adalah satu siswa — klik untuk melihat profil lengkapnya."),
    "Data": (":material/table_chart: Data", "Tabel data lengkap yang bisa diurutkan, dicari, dan diunduh."),
}

with st.sidebar:
    st.markdown(f"""<div class="brand"><div class="ic">{ms('school')}</div>
      <div><b>Performa Siswa</b><small>Dashboard analitik</small></div></div>
      <p class="nav-h">Menu</p>""", unsafe_allow_html=True)
    page = st.radio("Menu", list(PAGES), format_func=lambda p: PAGES[p][0], key="page",
                    label_visibility="collapsed")
    st.markdown(f"""<div class="side-card"><div class="ic">{ms('database')}</div>
      <b>Sumber data: {html.escape(src_name)}</b><p>{nf(len(df_all), 0)} baris · {html.escape(stamp)}</p>
      </div>""", unsafe_allow_html=True)
    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    if st.button("Muat ulang data", icon=":material/refresh:", width="stretch"):
        load_data.clear()
        get_model.clear()
        st.rerun()

# ======================================================================= header + filter global
FILTERS = {
    "f_school": ("School_Type", "Jenis sekolah"),
    "f_gender": ("Gender", "Gender"),
    "f_income": ("Family_Income", "Pendapatan keluarga"),
    "f_motiv": ("Motivation_Level", "Motivasi"),
    "f_parent": ("Parental_Involvement", "Keterlibatan orang tua"),
}
hmax = int(df_all.Hours_Studied.max())
active = [f"{lab}: {', '.join(ss[k])}" for k, (c, lab) in FILTERS.items()
          if ss.get(k) and len(ss[k]) < len(ORDER[c])]
if ss.get("f_hours", (0, hmax)) != (0, hmax):
    active.append(f"Jam belajar {ss.f_hours[0]}–{ss.f_hours[1]}")
if ss.get("f_att", (60, 100)) != (60, 100):
    active.append(f"Kehadiran {ss.f_att[0]}–{ss.f_att[1]}%")


def _reset_filters():
    for k, (c, _) in FILTERS.items():
        ss[k] = ORDER[c]
    ss.f_hours, ss.f_att = (0, hmax), (60, 100)


with st.container(key="hdr"):
    h1, h2, h3 = st.columns([3, 1.1, 1.3], vertical_alignment="center")
    h1.markdown(f'<p class="crumb"><span>Dashboard</span> / {page}</p><p class="page-t">{page}</p>'
                f'<p class="page-d">{PAGES[page][1]}</p>', unsafe_allow_html=True)
    with h2.popover(f"Filter{f' · {len(active)}' if active else ''}", icon=":material/tune:", width="stretch"):
        st.caption("Filter berlaku untuk semua halaman (kecuali model simulasi yang dilatih dari seluruh data).")
        for k, (c, lab) in FILTERS.items():
            st.pills(lab, ORDER[c], selection_mode="multi", default=ORDER[c], key=k)
        st.slider("Jam belajar per minggu", 0, hmax, (0, hmax), key="f_hours")
        st.slider("Kehadiran (%)", 60, 100, (60, 100), key="f_att")
        st.button("Reset filter", on_click=_reset_filters, width="stretch", icon=":material/restart_alt:")
    h3.markdown(f'<div class="livewrap"><span class="chip-live"><i></i>{html.escape(stamp)}</span></div>',
                unsafe_allow_html=True)
if active:
    st.markdown('<div class="fchips">' + "".join(f'<span class="fchip">{html.escape(a)}</span>' for a in active)
                + "</div>", unsafe_allow_html=True)


def _sel(data, col, chosen):
    return data[col].isin(chosen) if chosen else pd.Series(True, index=data.index)


mask = pd.Series(True, index=df_all.index)
for k, (c, _) in FILTERS.items():
    mask &= _sel(df_all, c, ss.get(k))
mask &= df_all.Hours_Studied.between(*ss.get("f_hours", (0, hmax)))
mask &= df_all.Attendance.between(*ss.get("f_att", (60, 100)))
df = df_all[mask]

if df.empty:
    st.warning("Tidak ada siswa yang cocok dengan kombinasi filter ini. Klik **Filter → Reset filter**.")
    st.stop()

avg, avg_all = df.Exam_Score.mean(), df_all.Exam_Score.mean()
pr, pr_all = (df.Exam_Score >= PASS_MARK).mean(), (df_all.Exam_Score >= PASS_MARK).mean()
filtered = len(df) < len(df_all)
eff = factor_effects(df)


def kpi(label, value, extra, sub, icon, grad="primary"):
    return (f'<div class="kpi"><div><div class="l">{label}</div><div class="v">{value}<small>{extra}</small></div>'
            f'<div class="s">{sub}</div></div><div class="ictile" style="background:var(--g-{grad})">{ms(icon)}</div></div>')


st.markdown('<div class="kpis">' + "".join([
    kpi("Jumlah siswa", nf(len(df), 0), "", f"{nf(len(df) / len(df_all) * 100, 0)}% dari total" if filtered
        else "seluruh data", "groups"),
    kpi("Rata-rata nilai ujian", nf(avg, 1), delta(avg - avg_all) if filtered else "",
        f"median {nf(df.Exam_Score.median(), 0)} · IQR {df.Exam_Score.quantile(.25):.0f}–{df.Exam_Score.quantile(.75):.0f}",
        "grading"),
    kpi(f"Mencapai nilai ≥{PASS_MARK}", f"{pr:.0%}", delta((pr - pr_all) * 100, 0, " pp") if filtered else "",
        f"{nf((df.Exam_Score >= PASS_MARK).sum(), 0)} siswa", "workspace_premium"),
    kpi("Kehadiran rata-rata", f"{nf(df.Attendance.mean(), 0)}%", "",
        f"faktor terkuat · {nf(eff.iloc[0].effect, 1, True)} poin" if eff.iloc[0].col == "Attendance"
        else "rata-rata kehadiran", "event_available"),
]) + "</div>", unsafe_allow_html=True)

FAC_ICON = {"Attendance": "event_available", "Hours_Studied": "menu_book", "Previous_Scores": "history_edu",
            "Tutoring_Sessions": "co_present", "Access_to_Resources": "library_books",
            "Parental_Involvement": "family_restroom", "Learning_Disabilities": "psychology",
            "Parental_Education_Level": "school", "Peer_Influence": "diversity_3",
            "Distance_from_Home": "home_pin", "Family_Income": "payments", "Motivation_Level": "bolt",
            "Teacher_Quality": "person_book", "Internet_Access": "wifi", "Extracurricular_Activities": "sports_soccer",
            "Physical_Activity": "directions_run", "Sleep_Hours": "bedtime", "School_Type": "apartment",
            "Gender": "wc"}

# ======================================================================= 1. Ringkasan
if page == "Ringkasan":
    with st.container(key="row_1"):
        c1, c2 = st.columns([1, 1.25], gap="large")
        with c1, st.container(key="dark_dist"):
            clickable(charts.distribution(df, PASS_MARK, dark=True), "dist", "score")
            card_title("Sebaran nilai ujian",
                       f"<b>{pr:.0%}</b> siswa mencapai target ≥{PASS_MARK} · batang putih = mencapai target")
            howto("Klik sebuah batang untuk melihat profil siswa dengan nilai tersebut.")

            def mstat(icon, grad, label, val, u, frac, cap):
                return (f'<div class="mstat"><div class="h"><span class="t" style="background:var(--g-{grad})">{ms(icon)}</span>'
                        f'{label}</div><div class="v">{val} <small>{u}</small></div>'
                        f'<div class="pbar"><i style="width:{max(min(frac, 1), 0) * 100:.0f}%"></i></div>'
                        f'<div class="c">{cap}</div></div>')
            st.markdown('<div class="mstats">' + "".join([
                mstat("event_available", "primary", "Kehadiran", nf(df.Attendance.mean(), 0), "%",
                      df.Attendance.mean() / 100, "skala 0–100"),
                mstat("menu_book", "info", "Belajar", nf(df.Hours_Studied.mean(), 1), "j/mgg",
                      df.Hours_Studied.mean() / 44, "skala 0–44"),
                mstat("co_present", "success", "Les", nf(df.Tutoring_Sessions.mean(), 1), "/bln",
                      df.Tutoring_Sessions.mean() / 8, "skala 0–8"),
                mstat("bedtime", "danger", "Tidur", nf(df.Sleep_Hours.mean(), 1), "j/hari",
                      df.Sleep_Hours.mean() / 10, "skala 0–10"),
            ]) + "</div>", unsafe_allow_html=True)

        with c2, st.container(key="card_rank"):
            card_title("Peringkat pengaruh faktor",
                       f"<b>{eff.iloc[0].label}</b> paling berpengaruh · panjang batang = selisih rata-rata "
                       "nilai antara kelompok terendah dan tertinggi")
            howto("Klik batang sebuah faktor untuk melihat rincian per kelompok.")
            clickable(charts.factor_ranking(eff), "rank", "factor")

    with st.container(key="row_2"):
        c1, c2 = st.columns([1.75, 1], gap="large")
        with c1, st.container(key="card_top"):
            top = eff.head(6)
            card_title("Kelompok dengan capaian tertinggi",
                       f"<b>{len(top)} faktor teratas</b> · kelompok terbaik di tiap faktor · rata-rata & pengaruh dalam poin nilai ujian")
            rows = []
            for r in top.itertuples():
                gs = group_stats(df, r.col)
                b = gs.loc[gs["mean"].idxmax()]
                rows.append(
                    f"<tr><td><span class='ico'>{ms(FAC_ICON.get(r.col, 'insights'))}</span><b>{r.label}</b></td>"
                    f"<td>{html.escape(str(b.group))}</td><td>{nf(b.n, 0)}</td><td><b>{nf(b['mean'], 1)}</b></td>"
                    f"<td><b>{nf(r.effect, 1, True)}</b></td>"
                    f"<td><div class='prog'><span>{b.pass_rate:.0%}</span><div class='pbar'>"
                    f"<i class='{'hi' if b.pass_rate >= .5 else ''}' style='width:{b.pass_rate * 100:.0f}%'></i></div></div></td></tr>")
            st.markdown("<div class='tblwrap'><table class='tbl'><tr><th>Faktor</th><th>Terbaik</th>"
                        "<th>Siswa</th><th>Rata-rata</th><th>Pengaruh</th><th>% ≥70</th></tr>"
                        + "".join(rows) + "</table></div>", unsafe_allow_html=True)
        with c2, st.container(key="card_ins"):
            card_title("Temuan utama", "dihitung ulang otomatis dari data & filter")
            tl_icons = [("trending_up", "#cb0c9f"), ("schedule", "#2152ff"), ("join_inner", "#17ad37"),
                        ("block", "#8392ab"), ("bar_chart", "#fb8c00")]
            st.markdown('<ul class="tl">' + "".join(
                f'<li><span class="d" style="color:{c}">{ms(i)}</span>{bold(t)}</li>'
                for t, (i, c) in zip(insights(df, eff), tl_icons)) + "</ul>", unsafe_allow_html=True)

# ======================================================================= 2. Eksplorasi faktor
elif page == "Eksplorasi faktor":
    with st.container(key="card_pick"):
        g = st.segmented_control("Kelompok faktor", list(GROUPS), default="Akademik", key="grp") or "Akademik"
        col = st.pills("Faktor", GROUPS[g], default=GROUPS[g][0], format_func=LABEL_ID.get,
                       key=f"fac_{g}") or GROUPS[g][0]
    with st.container(key="rowwide_fac"):
        c1, c2 = st.columns([2.2, 1], gap="large")
        gs = group_stats(df, col)
        with c1, st.container(key="card_fac"):
            card_title(f"Rata-rata nilai ujian menurut {LABEL_ID[col].lower()}",
                       "titik = rata-rata kelompok · garis vertikal tipis = interval kepercayaan 95% · "
                       "garis putus-putus = rata-rata semua siswa")
            howto("Klik titik kelompok untuk membuka profil siswa di kelompok tersebut.")
            clickable(charts.factor_chart(df, col, avg), f"fac_{col}", "group", {"col": col})
        with c2, st.container(key="card_facsum"):
            r = eff[eff.col == col].iloc[0]
            best, worst = gs.loc[gs["mean"].idxmax()], gs.loc[gs["mean"].idxmin()]
            st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:.6rem">
<div><p class="card-t">Ringkasan faktor</p><p class="card-s">{LABEL_ID[col]}</p></div>
<div class="ictile" style="width:40px;height:40px;font-size:20px">{ms(FAC_ICON.get(col, 'insights'))}</div></div>
<div style="margin:.3rem 0 .9rem"><div class="lbl">Pengaruh</div>
<div class="big">{nf(r.effect, 1, True)} <small>poin</small></div>
<div style="font-size:.8rem;color:#67748e">peringkat <b>#{r['rank']}</b> dari {len(eff)} faktor</div></div>
<table class="rows">
<tr><th>Kelompok</th><th>Siswa</th><th>Rata-rata</th><th>% ≥70</th></tr>
""" + "".join(f"<tr><td>{x.group}</td><td class='r'>{nf(x.n, 0)}</td><td class='v'>{nf(x.mean, 1)}</td>"
              f"<td class='r'>{x.pass_rate:.0%}</td></tr>" for x in gs.itertuples()) + f"""
</table>
<p class="card-s" style="margin-top:.8rem !important">Siswa di kelompok <b>{best.group}</b> rata-rata
<b>{nf(best['mean'] - worst['mean'], 1)} poin</b> lebih tinggi daripada kelompok <b>{worst.group}</b>
({best.pass_rate:.0%} vs {worst.pass_rate:.0%} mencapai ≥{PASS_MARK}).</p>""", unsafe_allow_html=True)

# ======================================================================= 3. Kombinasi
elif page == "Kombinasi faktor":
    num_cols = list(BINS)
    with st.container(key="rowwide_combo"):
        c1, c2 = st.columns([2.4, 1], gap="large")
        with c1, st.container(key="card_combo"):
            with st.container(key="ctl_combo"):
                a, b = st.columns(2)
                rowf = a.selectbox("Faktor baris (sumbu Y)", num_cols, index=num_cols.index("Hours_Studied"),
                                   format_func=LABEL_ID.get)
                opts = [c for c in num_cols if c != rowf]
                colf = b.selectbox("Faktor kolom (sumbu X)", opts,
                                   index=opts.index("Attendance") if "Attendance" in opts else 0,
                                   format_func=LABEL_ID.get)
            card_title(f"Rata-rata nilai ujian: {LABEL_ID[rowf].lower()} × {LABEL_ID[colf].lower()}",
                       "angka di sel = rata-rata nilai ujian · makin pekat = makin tinggi · sel dengan <5 siswa disembunyikan")
            howto("Klik sebuah sel untuk melihat siswa di irisan dua kelompok itu.")
            clickable(charts.combo_heatmap(df, rowf, colf), f"combo_{rowf}_{colf}", "combo",
                      {"row": rowf, "col": colf})
        with c2, st.container(key="card_combosum"):
            rb, rl = BINS[rowf]
            cb, cl = BINS[colf]
            t = df.assign(r=pd.cut(df[rowf], rb, labels=rl, include_lowest=True).astype(str),
                          c=pd.cut(df[colf], cb, labels=cl, include_lowest=True).astype(str))
            agg = t.groupby(["r", "c"])["Exam_Score"].agg(["mean", "count"]).reset_index()
            agg = agg[agg["count"] >= 5]
            hi_, lo_ = agg.loc[agg["mean"].idxmax()], agg.loc[agg["mean"].idxmin()]
            card_title("Ringkasan kombinasi")
            st.markdown(f"""
<div class="lbl" style="margin-top:.6rem">Kombinasi terbaik</div>
<div class="big">{nf(hi_['mean'], 1)} <small>poin</small></div>
<p class="card-s">{LABEL_ID[rowf]} <b>{hi_.r}</b> & {LABEL_ID[colf].lower()} <b>{hi_.c}</b> · {nf(hi_['count'], 0)} siswa</p>
<div class="lbl" style="margin-top:.8rem">Kombinasi terendah</div>
<div class="big">{nf(lo_['mean'], 1)} <small>poin</small></div>
<p class="card-s">{LABEL_ID[rowf]} <b>{lo_.r}</b> & {LABEL_ID[colf].lower()} <b>{lo_.c}</b> · {nf(lo_['count'], 0)} siswa</p>
<div class="lbl" style="margin-top:.8rem">Rentang efek gabungan</div>
<div class="big">{nf(hi_['mean'] - lo_['mean'], 1)} <small>poin</small></div>
<p class="card-s">Bandingkan dengan efek masing-masing faktor sendirian:
{LABEL_ID[rowf]} {nf(eff.set_index('col').loc[rowf, 'effect'], 1, True)} dan
{LABEL_ID[colf]} {nf(eff.set_index('col').loc[colf, 'effect'], 1, True)} poin.</p>""", unsafe_allow_html=True)

# ======================================================================= 4. Bandingkan kelompok
elif page == "Bandingkan kelompok":
    CMP_CAT = ["Motivation_Level", "Parental_Involvement", "Access_to_Resources", "Family_Income",
               "Peer_Influence", "School_Type", "Gender"]

    def group_builder(tag: str, dot: str, default_att):
        with st.container(key=f"card_cmp{tag}"):
            st.markdown(f'<p class="card-t"><span class="dot{tag}"></span>Kelompok {tag}</p>'
                        '<p class="card-s">atur kriteria — hasil perbandingan di bawah diperbarui otomatis</p>',
                        unsafe_allow_html=True)
            name = st.text_input("Nama kelompok", value=f"Kelompok {tag}", key=f"cmp{tag}_name")
            att = st.slider("Kehadiran (%)", 60, 100, default_att, key=f"cmp{tag}_att")
            hrs = st.slider("Jam belajar per minggu", 0, hmax, (0, hmax), key=f"cmp{tag}_hrs")
            m = df.Attendance.between(*att) & df.Hours_Studied.between(*hrs)
            with st.expander("Kriteria lain (opsional)"):
                for c in CMP_CAT:
                    sel = st.pills(LABEL_ID[c], ORDER[c], selection_mode="multi", default=ORDER[c],
                                   key=f"cmp{tag}_{c}")
                    if sel:
                        m &= df[c].isin(sel)
            sub = df[m]
            st.caption(f"{nf(len(sub), 0)} siswa cocok dengan kriteria ini.")
            return (name or f"Kelompok {tag}"), sub

    with st.container(key="row_cmp"):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            na, A = group_builder("A", "dotA", (60, 79))
        with c2:
            nb, B = group_builder("B", "dotB", (80, 100))

    if len(A) < 2 or len(B) < 2:
        st.warning("Salah satu kelompok terlalu kecil (butuh minimal 2 siswa). Longgarkan kriterianya.")
    else:
        ma, mb = A.Exam_Score.mean(), B.Exam_Score.mean()
        pa, pb = (A.Exam_Score >= PASS_MARK).mean(), (B.Exam_Score >= PASS_MARK).mean()
        va, vb = A.Exam_Score.var(ddof=1), B.Exam_Score.var(ddof=1)
        se = sqrt(va / len(A) + vb / len(B))
        tval = (mb - ma) / se if se else 0.0
        pval = 2 * (1 - 0.5 * (1 + erf(abs(tval) / sqrt(2))))
        d = (mb - ma) / sqrt((va + vb) / 2) if va + vb else 0.0
        size = "sangat kecil" if abs(d) < .2 else "kecil" if abs(d) < .5 else "sedang" if abs(d) < .8 else "besar"
        signif = pval < 0.05
        with st.container(key="card_cmpres"):
            card_title("Hasil perbandingan",
                       f"<b>{html.escape(nb)}</b> dibanding <b>{html.escape(na)}</b>")

            def vsbox(title, a_, b_, fmt, d_unit, dec=1):
                return (f'<div class="vsbox"><div class="t" style="color:#8392ab">{title}</div>'
                        f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:.3rem">'
                        f'<span><span class="dotA"></span><b style="color:#344767">{fmt(a_)}</b></span>'
                        f'<span><span class="dotB"></span><b style="color:#344767">{fmt(b_)}</b></span></div>'
                        f'<div style="font-size:.78rem;margin-top:.3rem">Selisih B − A: {delta(b_ - a_, dec, d_unit)}</div></div>')
            st.markdown('<div class="vs">' + "".join([
                vsbox("Jumlah siswa", len(A), len(B), lambda v: nf(v, 0), " siswa", 0),
                vsbox("Rata-rata nilai", ma, mb, lambda v: nf(v, 1), " poin"),
                vsbox("Median nilai", A.Exam_Score.median(), B.Exam_Score.median(), lambda v: nf(v, 0), " poin"),
                vsbox(f"Mencapai ≥{PASS_MARK}", pa * 100, pb * 100, lambda v: f"{nf(v, 0)}%", " pp", 0),
            ]) + "</div>", unsafe_allow_html=True)
            verdict = ("Perbedaan rata-rata ini <b>signifikan secara statistik</b>" if signif
                       else "Perbedaan rata-rata ini <b>belum signifikan secara statistik</b>")
            st.markdown(f'<div class="howto" style="margin-top:.8rem">{ms("science")}<div>{verdict} '
                        f'(uji Welch, p {"< 0,001" if pval < 0.001 else "= " + nf(pval, 3)}); ukuran efek '
                        f'Cohen\'s d = {nf(d, 2)} (<b>{size}</b>).</div></div>', unsafe_allow_html=True)

        with st.container(key="rowwide_cmp2"):
            c1, c2 = st.columns([1.3, 1], gap="large")
            with c1, st.container(key="card_cmpdist"):
                card_title("Sebaran nilai ujian kedua kelompok",
                           "area = persentase siswa di tiap nilai · garis putus-putus = rata-rata kelompok")
                static_chart(charts.compare_dist(A, B, na, nb, PASS_MARK), "cmp_dist")
            with c2, st.container(key="card_cmpprof"):
                rows = pd.DataFrame([dict(label=LABEL_ID[c], va=A[c].mean(), vb=B[c].mean(),
                                          pa=percentile(df_all[c], A[c].mean()), pb=percentile(df_all[c], B[c].mean()))
                                     for c in PROFILE_NUM])
                card_title("Profil kebiasaan", "posisi rata-rata kelompok dibanding semua siswa")
                static_chart(charts.compare_profile(rows, na, nb), "cmp_prof")

        with st.container(key="card_cmpcat"):
            card_title("Komposisi kelompok", "persentase siswa dengan karakteristik tertentu")
            trs = []
            for c, val in PROFILE_CAT.items():
                a_, b_ = (A[c] == val).mean() * 100, (B[c] == val).mean() * 100
                trs.append((abs(b_ - a_), f"<tr><td>{LABEL_ID[c]}: <b>{val}</b></td><td class='v'>{nf(a_, 0)}%</td>"
                                          f"<td class='v'>{nf(b_, 0)}%</td><td class='d'>{delta(b_ - a_, 0, ' pp', invert=c == 'Learning_Disabilities')}</td></tr>"))
            trs.sort(key=lambda x: x[0], reverse=True)
            st.markdown("<div class='tblwrap'><table class='rows' style='min-width:420px'><tr><th>Karakteristik</th>"
                        f"<th><span class='dotA'></span>{html.escape(na)}</th><th><span class='dotB'></span>{html.escape(nb)}</th>"
                        "<th>Selisih B − A</th></tr>" + "".join(t for _, t in trs) + "</table></div>",
                        unsafe_allow_html=True)

# ======================================================================= 5. Simulasi nilai
elif page == "Simulasi nilai":
    model = get_model(df_all)
    defaults = {**{c: int(round(model.median[c])) for c in NUM}, **model.mode}
    for c, v in defaults.items():
        ss.setdefault(f"sim_{c}", v)

    def _load_student():
        sid = ss.get("sim_sid")
        row = df_all[df_all.ID == sid]
        if sid is None or row.empty:
            return
        r = row.iloc[0]
        for c in NUM:
            ss[f"sim_{c}"] = int(r[c])
        for c in CAT:
            v = str(r[c])
            ss[f"sim_{c}"] = v if v in ORDER[c] else model.mode[c]

    def _reset_sim():
        for c, v in defaults.items():
            ss[f"sim_{c}"] = v

    with st.container(key="rowwide_sim"):
        c1, c2 = st.columns([1.25, 1], gap="large")
        with c1, st.container(key="card_simin"):
            card_title("Profil siswa", "ubah nilai di bawah — prediksi di sebelah kanan langsung diperbarui")
            with st.container(key="ctl_sim"):
                a, b, c = st.columns([1.2, 1, 1], vertical_alignment="bottom")
                a.number_input("Muat profil siswa (ID)", min_value=int(df_all.ID.min()), max_value=int(df_all.ID.max()),
                               value=None, step=1, placeholder="mis. 125", key="sim_sid")
                b.button("Muat profil", on_click=_load_student, width="stretch", icon=":material/download:")
                c.button("Profil tipikal", on_click=_reset_sim, width="stretch", icon=":material/restart_alt:")
            tabs = st.tabs(list(GROUPS))
            for tab, (gname, cols) in zip(tabs, GROUPS.items()):
                with tab:
                    for c in cols:
                        if c in NUM:
                            lo, hi, stp = NUM_RANGE[c]
                            u = unit(c)
                            st.slider(f"{LABEL_ID[c]}{f' ({u})' if u else ''}", lo, hi, step=stp, key=f"sim_{c}")
                        else:
                            st.segmented_control(LABEL_ID[c], ORDER[c], key=f"sim_{c}")
            others = [c for c in CAT if c not in sum(GROUPS.values(), [])]
            for c in others:
                st.segmented_control(LABEL_ID[c], ORDER[c], key=f"sim_{c}")

        profile = {c: (ss.get(f"sim_{c}") if ss.get(f"sim_{c}") is not None else defaults[c]) for c in NUM + CAT}
        pred = model.predict(profile)
        lo_i, hi_i = pred - 1.96 * model.resid_sd, pred + 1.96 * model.resid_sd
        p70 = model.p_pass(pred)
        pct = percentile(df_all.Exam_Score, pred)
        recs = recommendations(model, profile)
        with c2, st.container(key="card_simout"):
            card_title("Prediksi nilai ujian", "garis gelap pada gauge = target ≥70")
            static_chart(charts.gauge(pred, 55, 85, PASS_MARK), "sim_gauge")
            st.markdown(f"""
<div class="vs" style="margin-top:-.4rem;grid-template-columns:repeat(auto-fit,minmax(min(100%,108px),1fr))">
<div class="vsbox"><div class="lbl">Rentang 95%</div><div class="big" style="font-size:1.3rem">{nf(lo_i, 1)}–{nf(hi_i, 1)}</div></div>
<div class="vsbox"><div class="lbl">Peluang ≥{PASS_MARK}</div><div class="big" style="font-size:1.3rem">{nf(p70 * 100, 0)}%</div></div>
<div class="vsbox"><div class="lbl">Posisi</div><div class="big" style="font-size:1.3rem">P{nf(pct, 0)}</div>
<div style="font-size:.72rem;color:#8392ab">di atas {nf(pct, 0)}% siswa</div></div>
</div>
<p class="card-s" style="margin-top:.8rem !important"><b>Rekomendasi paling berdampak</b> (perkiraan model)</p>
""" + ("".join(f'<div class="reco"><div class="n">{i + 1}</div><div><b>{x["text"]}</b><p>{x["change"]} → prediksi '
               f'{nf(pred + x["gain"], 1)}</p></div><div class="g">+{nf(x["gain"], 1)}</div></div>'
               for i, x in enumerate(recs[:4])) or "<p class='card-s'>Profil ini sudah maksimal pada faktor yang bisa diubah.</p>")
                + f"""<p class="hint" style="margin-top:.7rem">Model regresi linear dari {nf(model.n, 0)} siswa ·
R² {nf(model.r2, 2)} · rata-rata meleset ±{nf(model.mae, 1)} poin. Perkiraan berbasis korelasi, bukan jaminan sebab-akibat.</p>""",
                unsafe_allow_html=True)

    with st.container(key="card_simcontrib"):
        card_title("Mengapa prediksinya segini?",
                   f"kontribusi tiap faktor dibanding siswa rata-rata (prediksi dasar {nf(model.baseline(), 1)}) · "
                   "fuchsia = menaikkan, navy = menurunkan")
        static_chart(charts.contributions(model.contributions(profile)), "sim_contrib")

# ======================================================================= 6. Profil siswa
elif page == "Profil siswa":
    with st.container(key="card_stu"):
        num_all = ["Attendance", "Hours_Studied", "Previous_Scores", "Tutoring_Sessions",
                   "Sleep_Hours", "Physical_Activity"]
        with st.container(key="ctl_stu"):
            a, b, c = st.columns(3)
            xf = a.selectbox("Sumbu X", num_all, format_func=LABEL_ID.get)
            cf = b.selectbox("Warna titik", [x for x in num_all if x != xf], format_func=LABEL_ID.get,
                             index=0 if xf != "Hours_Studied" else 1)
            sid = c.number_input("Cari siswa (ID)", min_value=int(df_all.ID.min()),
                                 max_value=int(df_all.ID.max()), value=None, step=1, placeholder="mis. 125")
        card_title(f"Nilai ujian vs {LABEL_ID[xf].lower()}",
                   f"{nf(len(df), 0)} siswa · warna = {LABEL_ID[cf].lower()} · posisi diberi sedikit acakan agar tidak menumpuk")
        howto("Klik sebuah titik untuk membuka profil lengkap siswa tersebut.")
        clickable(charts.student_scatter(df, xf, cf, sid), f"stu_{xf}_{cf}", "student")
    if sid is not None and ss.get("_last_sid") != sid:
        ss._last_sid = sid
        clicks.append(("student", {"customdata": [sid]}, {}))

# ======================================================================= 7. Data
elif page == "Data":
    with st.container(key="card_data"):
        card_title("Data siswa", f"{nf(len(df), 0)} baris · klik judul kolom untuk mengurutkan · ikon kaca pembesar untuk mencari")
        howto("Centang sebuah baris untuk membuka profil siswa.")
        show = df[["ID", "Exam_Score"] + [c for c in df.columns if c not in ("ID", "Exam_Score")]].rename(columns=LABEL_ID)
        ev = st.dataframe(
            show, hide_index=True, height=520, key=f"tbl_{ss.nonce}", on_select="rerun",
            selection_mode="single-row",
            column_config={
                "ID": st.column_config.NumberColumn("ID", width="small"),
                "Nilai ujian": st.column_config.ProgressColumn("Nilai ujian", min_value=50, max_value=100, format="%d"),
                "Kehadiran (%)": st.column_config.ProgressColumn("Kehadiran (%)", min_value=0, max_value=100,
                                                                 format="%d%%"),
            })
        if ev and ev.selection.rows:
            clicks.append(("student", {"customdata": [int(df.iloc[ev.selection.rows[0]]["ID"])]}, {}))
        a, b = st.columns([1, 3])
        a.download_button("Unduh data terfilter (CSV)", df.to_csv(index=False).encode(),
                          "data_terfilter.csv", "text/csv", icon=":material/download:", width="stretch")
    with st.container(key="card_desc"):
        card_title("Statistik deskriptif", "faktor numerik pada data yang sedang ditampilkan")
        dsc = df[["Exam_Score"] + PROFILE_NUM].describe().T
        dsc.index = [LABEL_ID[i] for i in dsc.index]
        st.markdown("<div class='tblwrap'><table class='rows' style='min-width:560px'><tr><th>Faktor</th><th>Rata-rata</th>"
                    "<th>Std</th><th>Min</th><th>Q1</th><th>Median</th><th>Q3</th><th>Maks</th></tr>" + "".join(
                        f"<tr><td>{i}</td><td class='v'>{nf(r['mean'], 1)}</td><td class='r'>{nf(r['std'], 1)}</td>"
                        f"<td class='r'>{nf(r['min'], 0)}</td><td class='r'>{nf(r['25%'], 0)}</td>"
                        f"<td class='r'>{nf(r['50%'], 0)}</td><td class='r'>{nf(r['75%'], 0)}</td>"
                        f"<td class='r'>{nf(r['max'], 0)}</td></tr>" for i, r in dsc.iterrows()) + "</table></div>",
                    unsafe_allow_html=True)

st.markdown(
    '<p class="hint" style="margin-top:1.6rem">Metodologi: pengaruh = selisih rata-rata nilai antara '
    'kelompok terendah dan tertinggi (faktor numerik: kuartil bawah ≤Q1 vs atas ≥Q3). '
    'Hubungan bersifat korelasional, bukan sebab-akibat. Arahkan kursor ke grafik untuk tombol unduh PNG.</p>',
    unsafe_allow_html=True)


# ======================================================================= dialog detail
def _cd(point: dict) -> list:
    cd = point.get("customdata")
    if isinstance(cd, dict):  # Streamlit mengirim array 2D sebagai {"0": .., "1": ..}
        return [cd[k] for k in sorted(cd, key=int)]
    return cd if isinstance(cd, list) else [cd]


def group_detail(sub: pd.DataFrame, subtitle: str):
    st.caption(subtitle)
    if sub.empty:
        st.info("Tidak ada siswa di kelompok ini.")
        return
    n, m = len(sub), sub.Exam_Score.mean()
    p = (sub.Exam_Score >= PASS_MARK).mean()
    k = st.columns(4)
    k[0].metric("Siswa", nf(n, 0), f"{nf(n / len(df) * 100, 1)}% dari tampilan", delta_color="off", delta_arrow="off")
    k[1].metric("Rata-rata nilai", nf(m, 1), f"{nf(m - avg, 1, True)} vs rata-rata")
    k[2].metric(f"Mencapai ≥{PASS_MARK}", f"{p:.0%}", f"{nf((p - pr) * 100, 0, True)} pp")
    k[3].metric("Rentang nilai", f"{nf(sub.Exam_Score.min(), 0)}–{nf(sub.Exam_Score.max(), 0)}",
                f"median {nf(sub.Exam_Score.median(), 0)}", delta_color="off", delta_arrow="off")
    st.plotly_chart(charts.mini_hist(sub, df), config=charts.CONFIG, key="dlg_hist")
    num, cat = profile_compare(sub, df)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**Profil kebiasaan kelompok**", unsafe_allow_html=True)
        st.markdown('<table class="rows"><tr><th>Faktor</th><th>Kelompok</th><th>Semua</th><th>Selisih</th></tr>' + "".join(
            f'<tr><td>{lab}</td><td class="v">{nf(a, 1)}</td><td class="r">{nf(b, 1)}</td>'
            f'<td class="d">{delta(a - b)}</td></tr>' for lab, a, b in num) + "</table>",
            unsafe_allow_html=True)
    with c2:
        st.markdown("**Karakteristik paling menonjol**", unsafe_allow_html=True)
        st.markdown('<table class="rows"><tr><th>Karakteristik</th><th>Kelompok</th><th>Semua</th><th>Selisih</th></tr>' + "".join(
            f'<tr><td>{lab}</td><td class="v">{nf(a, 0)}%</td><td class="r">{nf(b, 0)}%</td>'
            f'<td class="d">{delta(d, 0, " pp", invert="Kesulitan" in lab)}</td></tr>'
            for lab, a, b, d in cat[:6]) + "</table>", unsafe_allow_html=True)
    with st.expander(f"Lihat daftar siswa ({nf(n, 0)})"):
        st.dataframe(sub.rename(columns=LABEL_ID), hide_index=True, height=260)


def _to_sim(sid: int):
    ss.sim_sid = sid
    row = df_all[df_all.ID == sid].iloc[0]
    for c in NUM:
        ss[f"sim_{c}"] = int(row[c])
    for c in CAT:
        v = str(row[c])
        ss[f"sim_{c}"] = v if v in ORDER[c] else None
    ss.page = "Simulasi nilai"
    ss.nonce += 1


def student_detail(sid: int):
    row = df_all[df_all.ID == sid]
    if row.empty:
        st.info("Siswa tidak ditemukan.")
        return
    r = row.iloc[0]
    pct = percentile(df_all.Exam_Score, r.Exam_Score)
    rank = int((df_all.Exam_Score > r.Exam_Score).sum()) + 1
    ok = r.Exam_Score >= PASS_MARK
    model = get_model(df_all)
    prof = {c: (str(r[c]) if c in CAT else r[c]) for c in NUM + CAT}
    for c in CAT:
        if prof[c] not in ORDER[c]:
            prof[c] = model.mode[c]
    pred = model.predict(prof)
    c1, c2 = st.columns([1, 2.1], gap="large")
    c1.markdown(f"""
<div class="score"><div class="l">Nilai ujian</div>
<div class="v">{nf(r.Exam_Score, 0)}</div>
<div class="s">lebih tinggi dari <b>{nf(pct, 0)}%</b> siswa · peringkat {nf(rank, 0)} dari {nf(len(df_all), 0)}</div></div>
<div style="margin:10px 0"><span class="stat {'ok' if ok else 'no'}">
{'✓ Mencapai target' if ok else '✕ Di bawah target'} ≥{PASS_MARK}</span></div>
<div class="s" style="font-size:.8rem;color:#67748e">Prediksi model untuk profil ini: <b>{nf(pred, 1)}</b>
({'di atas' if r.Exam_Score > pred + .5 else 'di bawah' if r.Exam_Score < pred - .5 else 'sesuai'} perkiraan)</div>
""", unsafe_allow_html=True)
    with c1:
        if st.button("Simulasikan perubahan", icon=":material/calculate:", on_click=_to_sim, args=(sid,),
                     width="stretch"):
            st.rerun()
    with c2:
        st.markdown("**Kebiasaan & riwayat** <span class='hint'>bar = posisi persentil di antara semua siswa</span>",
                    unsafe_allow_html=True)
        rows = []
        for cname in PROFILE_NUM:
            v, mu = r[cname], df_all[cname].mean()
            pc = percentile(df_all[cname], v)
            rows.append(f'<tr><td>{LABEL_ID[cname]}</td><td class="v">{v:g}</td>'
                        f'<td class="r">rata-rata {nf(mu, 1)}</td>'
                        f'<td style="width:28%;padding-left:12px !important"><div class="bar"><i style="width:{pc:.0f}%"></i></div></td></tr>')
        st.markdown('<table class="rows">' + "".join(rows) + "</table>", unsafe_allow_html=True)

    contrib = []
    for cname in ORDER:
        val = str(r[cname])
        if val == "Tidak diketahui":
            continue
        gm = df_all.loc[df_all[cname].astype(str) == val, "Exam_Score"].mean()
        contrib.append((LABEL_ID[cname], val, gm - avg_all))
    contrib.sort(key=lambda x: x[2], reverse=True)
    pos = [c for c in contrib if c[2] > 0.3][:4]
    neg = [c for c in contrib if c[2] < -0.3][-4:][::-1]
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**Faktor pendukung** <span class='hint'>kelompoknya rata-rata di atas umum</span>",
                    unsafe_allow_html=True)
        st.markdown('<table class="rows">' + ("".join(
            f'<tr><td>{a}</td><td class="v">{v}</td><td class="d">{delta(d)}</td></tr>' for a, v, d in pos)
            or '<tr><td class="hint">—</td></tr>') + "</table>", unsafe_allow_html=True)
    with c2:
        st.markdown("**Faktor penghambat** <span class='hint'>kelompoknya rata-rata di bawah umum</span>",
                    unsafe_allow_html=True)
        st.markdown('<table class="rows">' + ("".join(
            f'<tr><td>{a}</td><td class="v">{v}</td><td class="d">{delta(d)}</td></tr>' for a, v, d in neg)
            or '<tr><td class="hint">—</td></tr>') + "</table>", unsafe_allow_html=True)
    st.markdown("**Atribut lain**", unsafe_allow_html=True)
    st.markdown('<div class="chips">' + "".join(
        f'<span class="chip">{LABEL_ID[c]}: <b>{html.escape(str(r[c]))}</b></span>' for c in ORDER) +
        "</div>", unsafe_allow_html=True)


def factor_detail(col: str):
    r = eff[eff.col == col].iloc[0]
    gs = group_stats(df, col)
    k = st.columns(3)
    k[0].metric("Pengaruh", f"{nf(r.effect, 2, True)} poin", f"{r.low} → {r.high}", delta_color="off", delta_arrow="off")
    k[1].metric("Peringkat", f"#{r['rank']}", f"dari {len(eff)} faktor", delta_color="off", delta_arrow="off")
    if col in BINS:
        k[2].metric("Korelasi (r)", nf(df[col].corr(df.Exam_Score), 2), "dengan nilai ujian",
                    delta_color="off", delta_arrow="off")
    else:
        k[2].metric("Kategori", len(gs), "kelompok", delta_color="off", delta_arrow="off")
    st.plotly_chart(charts.factor_chart(df, col, avg), config=charts.CONFIG, key="dlg_fac")
    body = "".join(
        f"<tr><td>{g.group}</td><td class='r'>{nf(g.n, 0)}</td><td class='v'>{nf(g.mean, 2)}</td>"
        f"<td class='r'>±{nf(g.ci, 2)}</td><td style='padding-left:24px !important'><div style='display:flex;"
        f"align-items:center;gap:8px'><div class='bar' style='flex:1'><i style='width:{g.pass_rate * 100:.0f}%'>"
        f"</i></div><span style='width:2.6rem;text-align:right'>{g.pass_rate:.0%}</span></div></td></tr>"
        for g in gs.itertuples())
    st.markdown("<div class='tblwrap'><table class='rows' style='min-width:460px'><tr><th>Kelompok</th><th>Siswa</th>"
                f"<th>Rata-rata</th><th>± CI 95%</th><th style='text-align:left;padding-left:24px !important'>"
                f"% mencapai ≥{PASS_MARK}</th></tr>{body}</table></div>", unsafe_allow_html=True)
    st.caption("Buka halaman **Eksplorasi faktor** untuk mengklik setiap kelompok.")


def open_dialog(title: str, body, *args):
    st.dialog(title, width="large", on_dismiss=reset_selection)(body)(*args)


if clicks:
    kind, pt, ctx = clicks[0]
    cd = _cd(pt)
    if kind == "score":
        s = int(float(cd[0]))
        open_dialog(f"Siswa dengan nilai {s}", group_detail,
                    df[df.Exam_Score.round() == s], f"Kelompok siswa yang memperoleh nilai ujian {s}.")
    elif kind == "factor":
        c = cd[0]
        open_dialog(LABEL_ID[c], factor_detail, c)
    elif kind == "group":
        c, gname = ctx["col"], str(cd[0])
        open_dialog(f"{LABEL_ID[c]}: {gname}", group_detail, subset(df, c, gname),
                    f"Semua siswa dengan {LABEL_ID[c].lower()} = {gname}.")
    elif kind == "combo":
        rv, cv = str(cd[0]), str(cd[1])
        sub = subset(subset(df, ctx["row"], rv), ctx["col"], cv)
        open_dialog(f"{LABEL_ID[ctx['row']]} {rv} · {LABEL_ID[ctx['col']]} {cv}", group_detail, sub,
                    "Irisan dua kelompok faktor.")
    elif kind == "student":
        s = int(float(cd[0]))
        open_dialog(f"Profil siswa #{s}", student_detail, s)


# ======================================================================= auto refresh
if REFRESH > 0:
    @st.fragment(run_every=REFRESH)
    def _watch():
        d, _ = load_data()
        sig = (len(d), float(d.Exam_Score.sum()), int(d.ID.max()))
        if ss.get("_sig") is None:
            ss._sig = sig
        elif sig != ss._sig:
            ss._sig = sig
            st.rerun(scope="app")
    _watch()
