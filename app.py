"""Dashboard Faktor Performa Siswa — Streamlit (gaya visual terinspirasi Soft UI).

Jalankan lokal:  streamlit run app.py
Klik titik / batang / sel pada grafik untuk membuka detail.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from src import charts
from src.analysis import (ALL_FACTORS, BINS, GROUPS, PASS_MARK, PROFILE_NUM, factor_effects,
                          group_stats, insights, percentile, profile_compare, subset)
from src.data_loader import LABEL_ID, ORDER, _setting, load_data, nf

st.set_page_config(page_title="Dashboard Performa Siswa", page_icon="◐", layout="wide")

REFRESH = int(_setting("AUTO_REFRESH_SECONDS", "0"))
ss = st.session_state
ss.setdefault("nonce", 0)

# ======================================================================= gaya (Soft UI)
_css = (Path(__file__).parent / "assets" / "style.css").read_text()
# baris kosong dibuang agar parser markdown tidak memotong blok <style>
st.markdown("<style>" + "\n".join(l for l in _css.splitlines() if l.strip()) + "</style>",
            unsafe_allow_html=True)


# ======================================================================= helper UI
def ms(name: str) -> str:
    return f'<span class="ms">{name}</span>'


def card_title(title: str, sub: str = "", hint: bool = True):
    h = f'<p class="card-t">{title}</p>'
    s = sub + (' · <span class="hint">klik titik/batang untuk detail</span>' if hint else "")
    st.markdown(h + (f'<p class="card-s">{s}</p>' if s else ""), unsafe_allow_html=True)


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


def reset_selection():
    ss.nonce += 1


# ======================================================================= data
df_all, source_info = load_data()
stamp = source_info.split(" · ")[1] if " · " in source_info else source_info
src_name = source_info.split(" · ")[0]

PAGES = {
    "Ringkasan": ":material/space_dashboard: Ringkasan",
    "Eksplorasi faktor": ":material/insights: Eksplorasi faktor",
    "Kombinasi faktor": ":material/grid_view: Kombinasi faktor",
    "Profil siswa": ":material/person_search: Profil siswa",
    "Data": ":material/table_chart: Data",
}

with st.sidebar:
    st.markdown(f"""<div class="brand"><div class="ic">{ms('school')}</div>
      <div><b>Performa Siswa</b><small>Dashboard analitik</small></div></div>
      <p class="nav-h">Menu</p>""", unsafe_allow_html=True)
    page = st.radio("Menu", list(PAGES), format_func=PAGES.get, key="page",
                    label_visibility="collapsed")
    st.markdown(f"""<div class="side-card"><div class="ic">{ms('database')}</div>
      <b>Sumber data: {html.escape(src_name)}</b><p>{len(df_all):,} baris · {html.escape(stamp)}</p>
      </div>""".replace(",", "."), unsafe_allow_html=True)
    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    if st.button("Muat ulang data", icon=":material/refresh:", width="stretch"):
        load_data.clear()
        st.rerun()

# ======================================================================= header + filter
FILTERS = {  # key -> (kolom, label)
    "f_school": ("School_Type", "Jenis sekolah"),
    "f_gender": ("Gender", "Gender"),
    "f_income": ("Family_Income", "Pendapatan keluarga"),
    "f_motiv": ("Motivation_Level", "Motivasi"),
}
hmax = int(df_all.Hours_Studied.max())
active = [f"{lab}: {', '.join(ss[k])}" for k, (c, lab) in FILTERS.items()
          if ss.get(k) and len(ss[k]) < len(ORDER[c])]
if ss.get("f_hours", (0, hmax)) != (0, hmax):
    active.append(f"Jam belajar {ss.f_hours[0]}–{ss.f_hours[1]}")
if ss.get("f_att", (60, 100)) != (60, 100):
    active.append(f"Kehadiran {ss.f_att[0]}–{ss.f_att[1]}%")

h1, h2, h3 = st.columns([3, 1.1, 1.1], vertical_alignment="center")
h1.markdown(f'<p class="crumb"><span>Dashboard</span> / {page}</p><p class="page-t">{page}</p>',
            unsafe_allow_html=True)
with h2.popover(f"Filter{f' · {len(active)}' if active else ''}", icon=":material/tune:", width="stretch"):
    for k, (c, lab) in FILTERS.items():
        st.pills(lab, ORDER[c], selection_mode="multi", default=ORDER[c], key=k)
    st.slider("Jam belajar / minggu", 0, hmax, (0, hmax), key="f_hours")
    st.slider("Kehadiran (%)", 60, 100, (60, 100), key="f_att")

    def _reset():
        for k, (c, _) in FILTERS.items():
            ss[k] = ORDER[c]
        ss.f_hours, ss.f_att = (0, hmax), (60, 100)
    st.button("Reset filter", on_click=_reset, width="stretch")
h3.markdown(f'<div style="text-align:right"><span class="chip-live"><i></i>{html.escape(stamp)}</span></div>',
            unsafe_allow_html=True)
if active:
    st.markdown('<div class="fchips">' + "".join(f'<span class="fchip">{html.escape(a)}</span>' for a in active)
                + "</div>", unsafe_allow_html=True)


def _sel(col, chosen):
    return df_all[col].isin(chosen) if chosen else pd.Series(True, index=df_all.index)


df = df_all[_sel("School_Type", ss.get("f_school")) & _sel("Gender", ss.get("f_gender"))
            & _sel("Family_Income", ss.get("f_income")) & _sel("Motivation_Level", ss.get("f_motiv"))
            & df_all.Hours_Studied.between(*ss.get("f_hours", (0, hmax)))
            & df_all.Attendance.between(*ss.get("f_att", (60, 100)))]

if df.empty:
    st.warning("Tidak ada siswa yang cocok dengan kombinasi filter ini.")
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
    kpi("Rata-rata nilai", nf(avg, 1), delta(avg - avg_all) if filtered else "",
        f"median {nf(df.Exam_Score.median(), 0)} · IQR {df.Exam_Score.quantile(.25):.0f}–{df.Exam_Score.quantile(.75):.0f}",
        "grading"),
    kpi(f"Mencapai ≥{PASS_MARK}", f"{pr:.0%}", delta((pr - pr_all) * 100, 0, " pp") if filtered else "",
        f"{nf((df.Exam_Score >= PASS_MARK).sum(), 0)} siswa", "workspace_premium"),
    kpi("Kehadiran rata-rata", f"{nf(df.Attendance.mean(), 0)}%", "",
        f"faktor terkuat · {nf(eff.iloc[0].effect, 1, True)} poin" if eff.iloc[0].col == "Attendance"
        else "rata-rata kehadiran", "event_available"),
]) + "</div>", unsafe_allow_html=True)


# ======================================================================= Ringkasan
if page == "Ringkasan":
    c1, c2 = st.columns([1, 1.25], gap="large")
    with c1, st.container(key="dark_dist"):
        clickable(charts.distribution(df, PASS_MARK, dark=True), "dist", "score")
        st.markdown(f"""<p class="card-t" style="margin-top:1rem !important">Sebaran nilai ujian</p>
<p class="card-s"><b>{pr:.0%}</b> siswa mencapai target ≥{PASS_MARK} · <span class="hint">klik batang untuk detail</span></p>""",
                    unsafe_allow_html=True)

        def mstat(icon, grad, label, val, unit, frac):
            return (f'<div class="mstat"><div class="h"><span class="t" style="background:var(--g-{grad})">{ms(icon)}</span>'
                    f'{label}</div><div class="v">{val} <small>{unit}</small></div>'
                    f'<div class="pbar"><i style="width:{max(min(frac, 1), 0) * 100:.0f}%"></i></div></div>')
        st.markdown('<div class="mstats">' + "".join([
            mstat("event_available", "primary", "Kehadiran", nf(df.Attendance.mean(), 0), "%", df.Attendance.mean() / 100),
            mstat("menu_book", "info", "Belajar", nf(df.Hours_Studied.mean(), 1), "j/mgg", df.Hours_Studied.mean() / 44),
            mstat("co_present", "success", "Les", nf(df.Tutoring_Sessions.mean(), 1), "/bln", df.Tutoring_Sessions.mean() / 8),
            mstat("bedtime", "danger", "Tidur", nf(df.Sleep_Hours.mean(), 1), "j/hari", df.Sleep_Hours.mean() / 10),
        ]) + "</div>", unsafe_allow_html=True)

    with c2, st.container(key="card_rank"):
        card_title("Peringkat pengaruh faktor",
                   f"<b>{eff.iloc[0].label}</b> paling berpengaruh · selisih rata-rata nilai kelompok terendah → tertinggi")
        clickable(charts.factor_ranking(eff), "rank", "factor")

    c1, c2 = st.columns([1.75, 1], gap="large")
    with c1, st.container(key="card_top"):
        top = eff.head(6)
        card_title("Kelompok dengan capaian tertinggi",
                   f"<b>{len(top)} faktor teratas</b> · kelompok terbaik di tiap faktor", hint=False)
        icons = {"Attendance": "event_available", "Hours_Studied": "menu_book", "Previous_Scores": "history_edu",
                 "Tutoring_Sessions": "co_present", "Access_to_Resources": "library_books",
                 "Parental_Involvement": "family_restroom", "Learning_Disabilities": "psychology",
                 "Parental_Education_Level": "school", "Peer_Influence": "diversity_3",
                 "Distance_from_Home": "home_pin", "Family_Income": "payments", "Motivation_Level": "bolt",
                 "Teacher_Quality": "person_book", "Internet_Access": "wifi", "Extracurricular_Activities": "sports_soccer",
                 "Physical_Activity": "directions_run", "Sleep_Hours": "bedtime", "School_Type": "apartment",
                 "Gender": "wc"}
        rows = []
        for r in top.itertuples():
            gs = group_stats(df, r.col)
            b = gs.loc[gs["mean"].idxmax()]
            rows.append(
                f"<tr><td><span class='ico'>{ms(icons.get(r.col, 'insights'))}</span><b>{r.label}</b></td>"
                f"<td>{html.escape(str(b.group))}</td><td>{nf(b.n, 0)}</td><td><b>{nf(b['mean'], 1)}</b></td>"
                f"<td><b>{nf(r.effect, 1, True)}</b></td>"
                f"<td><div class='prog'><span>{b.pass_rate:.0%}</span><div class='pbar'>"
                f"<i class='{'hi' if b.pass_rate >= .5 else ''}' style='width:{b.pass_rate * 100:.0f}%'></i></div></div></td></tr>")
        st.markdown("<table class='tbl'><tr><th>Faktor</th><th>Kelompok terbaik</th><th>Siswa</th>"
                    "<th>Rata-rata</th><th>Pengaruh</th><th style='width:22%'>% ≥70</th></tr>"
                    + "".join(rows) + "</table>", unsafe_allow_html=True)
    with c2, st.container(key="card_ins"):
        card_title("Temuan utama", "dihitung ulang otomatis dari data & filter", hint=False)
        tl_icons = [("trending_up", "#cb0c9f"), ("schedule", "#2152ff"), ("join_inner", "#17ad37"),
                    ("block", "#8392ab"), ("bar_chart", "#fb8c00")]
        st.markdown('<ul class="tl">' + "".join(
            f'<li><span class="d" style="color:{c}">{ms(i)}</span>{bold(t)}</li>'
            for t, (i, c) in zip(insights(df, eff), tl_icons)) + "</ul>", unsafe_allow_html=True)

# ======================================================================= Eksplorasi faktor
elif page == "Eksplorasi faktor":
    with st.container(key="card_pick"):
        g = st.segmented_control("Kelompok faktor", list(GROUPS), default="Akademik",
                                key="grp", label_visibility="collapsed") or "Akademik"
        col = st.pills("Faktor", GROUPS[g], default=GROUPS[g][0], format_func=LABEL_ID.get,
                      key=f"fac_{g}", label_visibility="collapsed") or GROUPS[g][0]
    st.markdown("<div style='height:.55rem'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns([2.3, 1], gap="large")
    with c1, st.container(key="card_fac"):
        card_title(f"Rata-rata nilai menurut {LABEL_ID[col].lower()}",
                   "garis tipis = interval kepercayaan 95%")
        clickable(charts.factor_chart(df, col, avg), f"fac_{col}", "group", {"col": col})
    with c2, st.container(key="card_facsum"):
        r = eff[eff.col == col].iloc[0]
        gs = group_stats(df, col)
        best, worst = gs.loc[gs["mean"].idxmax()], gs.loc[gs["mean"].idxmin()]
        st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-start">
<div><p class="card-t">Ringkasan faktor</p><p class="card-s">{LABEL_ID[col]}</p></div>
<div class="ictile" style="width:40px;height:40px;font-size:20px">{ms('insights')}</div></div>
<div style="margin:.4rem 0 1rem"><div class="l" style="font-size:.78rem;color:#8392ab;font-weight:600">PENGARUH</div>
<div style="font-size:1.9rem;font-weight:700;color:#344767">{nf(r.effect, 1, True)}
<span style="font-size:.9rem;color:#8392ab;font-weight:600">poin</span></div>
<div style="font-size:.8rem;color:#67748e">peringkat <b>#{r['rank']}</b> dari {len(eff)} faktor</div></div>
<table class="rows">
<tr><td>Kelompok terbaik</td><td class="v">{best.group}</td><td class="d">{nf(best['mean'], 1)}</td></tr>
<tr><td>Kelompok terendah</td><td class="v">{worst.group}</td><td class="d">{nf(worst['mean'], 1)}</td></tr>
<tr><td>Jumlah kelompok</td><td class="v">{len(gs)}</td><td class="d"></td></tr>
<tr><td>Kelompok terbesar</td><td class="v">{gs.loc[gs.n.idxmax(), 'group']}</td>
<td class="d">{gs.n.max() / gs.n.sum():.0%}</td></tr>
</table>""", unsafe_allow_html=True)

# ======================================================================= Kombinasi
elif page == "Kombinasi faktor":
    with st.container(key="card_combo"):
        num_cols = list(BINS)
        a, b, _ = st.columns([1, 1, 2])
        rowf = a.selectbox("Baris", num_cols, index=num_cols.index("Hours_Studied"), format_func=LABEL_ID.get)
        opts = [c for c in num_cols if c != rowf]
        colf = b.selectbox("Kolom", opts, index=opts.index("Attendance") if "Attendance" in opts else 0,
                           format_func=LABEL_ID.get)
        card_title(f"Rata-rata nilai: {LABEL_ID[rowf].lower()} × {LABEL_ID[colf].lower()}",
                   "makin pekat = makin tinggi · sel dengan <5 siswa disembunyikan · klik sel untuk detail",
                   hint=False)
        clickable(charts.combo_heatmap(df, rowf, colf), f"combo_{rowf}_{colf}", "combo",
                  {"row": rowf, "col": colf})

# ======================================================================= Profil siswa
elif page == "Profil siswa":
    with st.container(key="card_stu"):
        a, b, c, _ = st.columns([1, 1, 1, 1.2])
        num_all = ["Attendance", "Hours_Studied", "Previous_Scores", "Tutoring_Sessions",
                   "Sleep_Hours", "Physical_Activity"]
        xf = a.selectbox("Sumbu X", num_all, format_func=LABEL_ID.get)
        cf = b.selectbox("Warna", [x for x in num_all if x != xf], format_func=LABEL_ID.get,
                         index=0 if xf != "Hours_Studied" else 1)
        sid = c.number_input("Cari siswa (ID)", min_value=int(df_all.ID.min()),
                             max_value=int(df_all.ID.max()), value=None, step=1, placeholder="mis. 125")
        card_title("Setiap titik = satu siswa", f"{nf(len(df), 0)} siswa · posisi diberi sedikit acakan agar tidak menumpuk"
                   + " · <span class='hint'>klik titik untuk profil</span>", hint=False)
        clickable(charts.student_scatter(df, xf, cf, sid), f"stu_{xf}_{cf}", "student")
    if sid is not None and ss.get("_last_sid") != sid:
        ss._last_sid = sid
        clicks.append(("student", {"customdata": [sid]}, {}))

# ======================================================================= Data
elif page == "Data":
    with st.container(key="card_data"):
        card_title("Data siswa", f"{nf(len(df), 0)} baris · klik baris untuk membuka profil siswa", hint=False)
        show = df[["ID", "Exam_Score"] + [c for c in df.columns if c not in ("ID", "Exam_Score")]].rename(columns=LABEL_ID)
        ev = st.dataframe(
            show, hide_index=True, height=520, key=f"tbl_{ss.nonce}", on_select="rerun",
            selection_mode="single-row",
            column_config={
                "ID": st.column_config.NumberColumn("ID", width="small"),
                "Nilai ujian": st.column_config.ProgressColumn("Nilai ujian", min_value=50, max_value=100,
                                                               format="%d"),
                "Kehadiran (%)": st.column_config.ProgressColumn("Kehadiran (%)", min_value=0,
                                                                 max_value=100, format="%d%%"),
            })
        if ev and ev.selection.rows:
            clicks.append(("student", {"customdata": [int(df.iloc[ev.selection.rows[0]]["ID"])]}, {}))
        st.download_button("Unduh data terfilter (CSV)", df.to_csv(index=False).encode(),
                           "data_terfilter.csv", "text/csv", icon=":material/download:")

st.markdown(
    '<p class="hint" style="margin-top:1.6rem">Metodologi: pengaruh = selisih rata-rata nilai antara '
    'kelompok terendah dan tertinggi (faktor numerik: kuartil bawah ≤Q1 vs atas ≥Q3). '
    'Hubungan bersifat korelasional, bukan sebab-akibat.</p>', unsafe_allow_html=True)


# ======================================================================= dialog detail
def _cd(point: dict) -> list:
    cd = point.get("customdata")
    if isinstance(cd, dict):  # Streamlit mengirim array 2D sebagai {"0": .., "1": ..}
        return [cd[k] for k in sorted(cd, key=int)]
    return cd if isinstance(cd, list) else [cd]


def group_detail(sub: pd.DataFrame, subtitle: str):
    st.caption(subtitle)
    n, m = len(sub), sub.Exam_Score.mean()
    p = (sub.Exam_Score >= PASS_MARK).mean()
    k = st.columns(4)
    k[0].metric("Siswa", f"{n:,}".replace(",", "."), f"{nf(n / len(df) * 100, 1)}% dari tampilan", delta_color="off", delta_arrow="off")
    k[1].metric("Rata-rata nilai", f"{nf(m, 1)}", f"{nf(m - avg, 1, True)} vs rata-rata")
    k[2].metric(f"Mencapai ≥{PASS_MARK}", f"{p:.0%}", f"{nf((p - pr) * 100, 0, True)} pp")
    k[3].metric("Rentang nilai", f"{nf(sub.Exam_Score.min(), 0)}–{nf(sub.Exam_Score.max(), 0)}",
                f"median {nf(sub.Exam_Score.median(), 0)}", delta_color="off", delta_arrow="off")
    st.plotly_chart(charts.mini_hist(sub, df), config=charts.CONFIG, key="dlg_hist")
    num, cat = profile_compare(sub, df)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**Profil kelompok** <span class='hint'>vs rata-rata tampilan</span>", unsafe_allow_html=True)
        st.markdown('<table class="rows">' + "".join(
            f'<tr><td>{lab}</td><td class="v">{nf(a, 1)}</td><td class="r">{nf(b, 1)}</td>'
            f'<td class="d">{delta(a - b)}</td></tr>' for lab, a, b in num) + "</table>",
            unsafe_allow_html=True)
    with c2:
        st.markdown("**Ciri paling menonjol** <span class='hint'>% siswa</span>", unsafe_allow_html=True)
        st.markdown('<table class="rows">' + "".join(
            f'<tr><td>{lab}</td><td class="v">{nf(a, 0)}%</td><td class="r">{nf(b, 0)}%</td>'
            f'<td class="d">{delta(d, 0, invert="Kesulitan" in lab)}</td></tr>'
            for lab, a, b, d in cat[:6]) + "</table>", unsafe_allow_html=True)
    with st.expander(f"Lihat daftar siswa ({n:,})".replace(",", ".")):
        st.dataframe(sub.rename(columns=LABEL_ID), hide_index=True, height=260)


def student_detail(sid: int):
    row = df_all[df_all.ID == sid]
    if row.empty:
        st.info("Siswa tidak ditemukan.")
        return
    r = row.iloc[0]
    pct = percentile(df_all.Exam_Score, r.Exam_Score)
    rank = int((df_all.Exam_Score > r.Exam_Score).sum()) + 1
    ok = r.Exam_Score >= PASS_MARK
    c1, c2 = st.columns([1, 2.2])
    c1.markdown(f"""
<div class="score"><div class="l">Nilai ujian</div>
<div class="v">{nf(r.Exam_Score, 0)}</div>
<div class="s">lebih tinggi dari <b>{nf(pct, 0)}%</b> siswa · peringkat {rank:,} dari {len(df_all):,}</div></div>
<div style="margin-top:10px"><span class="stat {'ok' if ok else 'no'}">
{'✓ Mencapai target' if ok else '✕ Di bawah target'} ≥{PASS_MARK}</span></div>
""".replace(",", "."), unsafe_allow_html=True)
    with c2:
        st.markdown("**Kebiasaan & riwayat** <span class='hint'>bar = posisi persentil di antara semua siswa</span>",
                    unsafe_allow_html=True)
        rows = []
        for cname in PROFILE_NUM:
            v, mu = r[cname], df_all[cname].mean()
            pc = percentile(df_all[cname], v)
            rows.append(f'<tr><td>{LABEL_ID[cname]}</td><td class="v">{v:g}</td>'
                        f'<td class="r">rata-rata {nf(mu, 1)}</td>'
                        f'<td style="width:110px;padding-left:12px"><div class="bar"><i style="width:{nf(pc, 0)}%"></i></div></td></tr>')
        st.markdown('<table class="rows">' + "".join(rows) + "</table>", unsafe_allow_html=True)

    # faktor kategori: bandingkan rata-rata kelompok siswa ini dengan rata-rata umum
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
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
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
        k[2].metric("Korelasi (r)", f"{nf(df[col].corr(df.Exam_Score), 2)}", "dengan nilai ujian",
                    delta_color="off", delta_arrow="off")
    else:
        k[2].metric("Kategori", len(gs), "kelompok", delta_color="off", delta_arrow="off")
    st.plotly_chart(charts.factor_chart(df, col, avg), config=charts.CONFIG, key="dlg_fac")
    head = ("<tr><td class='hint'>Kelompok</td><td class='hint' style='text-align:right'>Siswa</td>"
            "<td class='hint' style='text-align:right'>Rata-rata</td>"
            "<td class='hint' style='text-align:right'>± CI 95%</td>"
            f"<td class='hint' style='padding-left:16px'>% mencapai ≥{PASS_MARK}</td></tr>")
    body = "".join(
        f"<tr><td>{g.group}</td><td class='r'>{nf(g.n, 0)}</td><td class='v'>{nf(g.mean, 2)}</td>"
        f"<td class='r'>{nf(g.ci, 2)}</td><td style='padding-left:16px'><div style='display:flex;"
        f"align-items:center;gap:8px'><div class='bar' style='flex:1'><i style='width:{g.pass_rate * 100:.0f}%'>"
        f"</i></div><span style='width:2.6rem;text-align:right'>{g.pass_rate:.0%}</span></div></td></tr>"
        for g in gs.itertuples())
    st.markdown(f'<table class="rows">{head}{body}</table>', unsafe_allow_html=True)
    st.caption("Buka tab **Eksplorasi faktor** untuk mengklik setiap kelompok.")


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
