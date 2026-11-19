"""Grafik Plotly.

Aturan yang dijaga di semua grafik:
- setiap sumbu punya judul + satuan (tidak ada sumbu tanpa keterangan)
- label nilai diletakkan di posisi yang tidak menabrak garis/penanda lain
- garis referensi (rata-rata / target) diberi label di luar area data
- `customdata` membawa kunci untuk klik -> pop-up detail
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .analysis import BINS, group_stats
from .data_loader import LABEL_ID, nf

# ------------------------------------------------------------------ palet (gaya Soft UI)
NAVY = "#3a416f"          # seri pembanding / kelompok A
ACCENT = "#cb0c9f"        # seri utama / kelompok B / sorotan
ACCENT_MID = "#ec8fd6"
GRAY = "#cbd3da"
HEAD = "#344767"
TEXT = "#67748e"
MUTED = "#8392ab"
GRID = "#eef0f4"
POS, NEG = "#cb0c9f", "#3a416f"   # divergen: menaikkan vs menurunkan nilai
SEQ_SCALE = [[0, "#fbe6f6"], [0.35, "#ec8fd6"], [0.7, "#cb0c9f"], [1, "#5e0a4c"]]
FONT = "Open Sans, -apple-system, Segoe UI, sans-serif"

# Label pendek untuk colorbar / ruang sempit
SHORT = {"Attendance": "Kehadiran (%)", "Hours_Studied": "Jam belajar<br>/minggu",
         "Previous_Scores": "Nilai<br>sebelumnya", "Tutoring_Sessions": "Sesi les<br>/bulan",
         "Sleep_Hours": "Jam tidur<br>/hari", "Physical_Activity": "Aktivitas fisik<br>(jam/minggu)"}
# satuan tambahan hanya untuk faktor yang labelnya belum memuat satuan
UNIT = {"Previous_Scores": "poin"}

# Toolbar hanya tombol unduh PNG (muncul saat kursor di atas grafik)
CONFIG = {"displayModeBar": "hover", "displaylogo": False, "responsive": True,
          "modeBarButtons": [["toImage"]], "scrollZoom": False,
          "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "grafik-performa-siswa"}}


def _base(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        height=height, autosize=True, margin=dict(l=8, r=16, t=16, b=8),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=TEXT), separators=",.",
        hoverlabel=dict(bgcolor="white", bordercolor="#e9ecef",
                        font=dict(family=FONT, size=12, color=HEAD)),
        showlegend=False, bargap=0.18, clickmode="event+select", dragmode=False,
        uniformtext=dict(minsize=9, mode="hide"),
    )
    fig.update_xaxes(showgrid=False, linecolor="#e9ecef", ticks="", automargin=True,
                     tickfont=dict(color=MUTED, size=11), fixedrange=True,
                     title_font=dict(size=12, color=TEXT), title_standoff=14)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, automargin=True,
                     tickfont=dict(color=MUTED, size=11), fixedrange=True,
                     title_font=dict(size=12, color=TEXT), title_standoff=8)
    return fig


def _ref_line(fig: go.Figure, y: float, text: str):
    """Garis referensi horizontal + label di LUAR area plot (kanan) agar tidak menimpa data."""
    fig.add_hline(y=y, line=dict(color=MUTED, width=1, dash="dot"))
    fig.add_annotation(xref="paper", x=1.0, y=y, text=text, showarrow=False, xanchor="left",
                       xshift=4, font=dict(size=10, color=MUTED), align="left")


# ================================================================== distribusi nilai
def distribution(df: pd.DataFrame, pass_mark: int, dark: bool = True) -> go.Figure:
    counts = df["Exam_Score"].round().astype(int).value_counts().sort_index()
    total = counts.sum()
    hi, lo = ("#ffffff", "rgba(255,255,255,0.38)") if dark else (ACCENT, ACCENT_MID)
    fig = go.Figure(go.Bar(
        x=counts.index, y=counts.values,
        marker=dict(color=[hi if s >= pass_mark else lo for s in counts.index], cornerradius=2),
        customdata=np.stack([counts.index, counts.values / total * 100], axis=1),
        hovertemplate="<b>Nilai ujian %{x}</b><br>%{y} siswa (%{customdata[1]:.1f}% dari tampilan)"
                      "<extra>klik untuk detail</extra>",
        unselected=dict(marker=dict(opacity=0.35)),
    ))
    ink = "rgba(255,255,255,0.8)" if dark else TEXT
    fig.add_vline(x=pass_mark - 0.5, line=dict(color=ink, width=1, dash="dot"))
    fig.add_annotation(x=pass_mark - 0.5, y=1.0, yref="paper", text=f"target ≥{pass_mark}",
                       showarrow=False, xanchor="left", yanchor="bottom", xshift=4,
                       font=dict(size=10, color=ink))
    x_hi = int(min(counts.index.max(), 100))
    fig.update_xaxes(title="Nilai ujian (poin)", range=[counts.index.min() - 1, x_hi + 1], dtick=10)
    fig.update_yaxes(title="Jumlah siswa")
    fig = _base(fig, 395)
    fig.update_layout(margin=dict(l=8, r=16, t=26, b=8))
    if dark:
        w = "rgba(255,255,255,0.75)"
        fig.update_xaxes(tickfont=dict(color=w), title_font=dict(color=w), linecolor="rgba(255,255,255,0.25)")
        fig.update_yaxes(tickfont=dict(color=w), title_font=dict(color=w), gridcolor="rgba(255,255,255,0.12)")
    return fig


# ================================================================== peringkat faktor
def factor_ranking(effects: pd.DataFrame) -> go.Figure:
    e = effects.sort_values("abs_effect")
    colors = [ACCENT if a >= 1 else (ACCENT_MID if a >= 0.5 else GRAY) for a in e["abs_effect"]]
    fig = go.Figure(go.Bar(
        x=e["effect"], y=e["label"], orientation="h",
        marker=dict(color=colors, cornerradius=3),
        customdata=np.stack([e["col"], e["low"], e["high"], e["kind"]], axis=1),
        text=[nf(v, 1, True) for v in e["effect"]], textposition="outside",
        textfont=dict(size=11, color=HEAD), cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Kelompok %{customdata[1]} → %{customdata[2]}"
                      "<br>Selisih rata-rata nilai: <b>%{x:+.2f} poin</b><extra>klik untuk detail</extra>",
        unselected=dict(marker=dict(opacity=0.35)),
    ))
    lo = min(0, e["effect"].min())
    span = e["effect"].max() - lo
    fig.update_xaxes(title="Pengaruh terhadap nilai ujian (selisih poin)",
                     range=[lo - span * 0.12, e["effect"].max() + span * 0.14],
                     showgrid=True, gridcolor=GRID, zeroline=True, zerolinecolor="#d2d6da")
    fig.update_yaxes(title="Faktor", showgrid=False)
    fig = _base(fig, 22 * len(e) + 80)
    fig.update_layout(bargap=0.32)
    return fig


# ================================================================== satu faktor
def factor_chart(df: pd.DataFrame, col: str, overall: float) -> go.Figure:
    g = group_stats(df, col)
    numeric = col in BINS
    fig = go.Figure()
    _ref_line(fig, overall, f"rata-rata<br>semua {nf(overall, 1)}")
    fig.add_trace(go.Scatter(
        x=g["group"], y=g["mean"], mode="lines+markers" if numeric else "markers",
        line=dict(color=ACCENT, width=3, shape="spline", smoothing=0.6),
        marker=dict(size=14, color=ACCENT, line=dict(width=3, color="white")),
        error_y=dict(type="data", array=g["ci"], color=ACCENT_MID, thickness=1.5, width=6),
        customdata=np.stack([g["group"], g["n"], g["pass_rate"] * 100, g["ci"]], axis=1),
        hovertemplate="<b>%{x}</b><br>Rata-rata nilai %{y:.2f} (±%{customdata[3]:.2f})"
                      "<br>%{customdata[1]} siswa · %{customdata[2]:.0f}% mencapai ≥70"
                      "<extra>klik untuk detail</extra>",
        unselected=dict(marker=dict(opacity=0.35)),
    ))
    # label nilai di ATAS ujung interval kepercayaan -> tidak menimpa titik/garis/whisker
    for _, r in g.iterrows():
        fig.add_annotation(x=r["group"], y=r["mean"] + r["ci"], text=f"<b>{nf(r['mean'], 1)}</b>",
                           showarrow=False, yanchor="bottom", yshift=4, font=dict(size=11, color=HEAD))
    top = (g["mean"] + g["ci"]).max()
    bot = (g["mean"] - g["ci"]).min()
    pad = max(0.5, (top - bot) * 0.18)
    fig.update_yaxes(title="Rata-rata nilai ujian (poin)",
                     range=[min(bot, overall) - pad, max(top, overall) + pad * 1.8])
    unit = f" ({UNIT[col]})" if col in UNIT and UNIT[col] not in LABEL_ID[col] else ""
    fig.update_xaxes(title=f"{LABEL_ID[col]}{unit} — kelompok", type="category")
    fig = _base(fig, 360)
    fig.update_layout(margin=dict(l=8, r=78, t=16, b=8))   # ruang untuk label garis rata-rata
    return fig


# ================================================================== kombinasi dua faktor
def combo_heatmap(df: pd.DataFrame, row: str, col: str) -> go.Figure:
    rb, rl = BINS[row]
    cb, cl = BINS[col]
    t = df.assign(r=pd.cut(df[row], rb, labels=rl, include_lowest=True),
                  c=pd.cut(df[col], cb, labels=cl, include_lowest=True))
    agg = t.groupby(["r", "c"], observed=True)["Exam_Score"].agg(["mean", "count"]).reset_index()
    agg = agg[agg["count"] >= 5]
    zmin, zmax = agg["mean"].min(), agg["mean"].max()
    xs, ys = agg["c"].astype(str), agg["r"].astype(str)
    txt_col = ["white" if (m - zmin) / max(zmax - zmin, 1e-9) > 0.5 else HEAD for m in agg["mean"]]
    fig = go.Figure(go.Heatmap(
        x=xs, y=ys, z=agg["mean"], colorscale=SEQ_SCALE, zmin=zmin, zmax=zmax, xgap=3, ygap=3,
        hoverinfo="skip",
        colorbar=dict(title=dict(text="Rata-rata<br>nilai", side="top", font=dict(size=11)),
                      thickness=10, len=0.9, outlinewidth=0, tickfont=dict(size=10, color=MUTED))))
    # angka di tengah sel (warna menyesuaikan kontras)
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="text", text=[nf(m, 1) for m in agg["mean"]],
                             textfont=dict(size=12, color=txt_col), hoverinfo="skip"))
    # lapisan transparan untuk klik + hover
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers", marker=dict(symbol="square", size=44, color="rgba(0,0,0,0.002)"),
        customdata=np.stack([agg["r"].astype(str), agg["c"].astype(str), agg["count"], agg["mean"]], axis=1),
        hovertemplate=f"<b>{LABEL_ID[row]}: %{{customdata[0]}}</b><br><b>{LABEL_ID[col]}: %{{customdata[1]}}</b>"
                      "<br>Rata-rata nilai %{customdata[3]:.2f} · %{customdata[2]} siswa"
                      "<extra>klik untuk detail</extra>",
        selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)),
    ))
    fig.update_xaxes(title=f"{LABEL_ID[col]} — kelompok", type="category", categoryorder="array",
                     categoryarray=[str(x) for x in cl], showline=False)
    fig = _base(fig, 62 * len(rl) + 120)
    fig.update_xaxes(title_standoff=22)
    fig.update_yaxes(title_standoff=18)
    fig.update_yaxes(title=f"{LABEL_ID[row]} — kelompok", type="category", categoryorder="array",
                     categoryarray=[str(x) for x in rl], showgrid=False)
    return fig


# ================================================================== siswa individual
def student_scatter(df: pd.DataFrame, x: str, color: str, highlight: int | None = None) -> go.Figure:
    rng = np.random.default_rng(7)
    jx = df[x] + rng.uniform(-0.35, 0.35, len(df))
    jy = df["Exam_Score"] + rng.uniform(-0.3, 0.3, len(df))
    fig = go.Figure(go.Scattergl(
        x=jx, y=jy, mode="markers",
        marker=dict(size=6, color=df[color], colorscale=SEQ_SCALE, opacity=0.8, line=dict(width=0),
                    colorbar=dict(title=dict(text=SHORT.get(color, LABEL_ID[color]), side="top",
                                             font=dict(size=11)),
                                  thickness=10, len=0.9, outlinewidth=0, tickfont=dict(size=10, color=MUTED))),
        customdata=np.stack([df["ID"], df[x], df["Exam_Score"], df[color]], axis=1),
        hovertemplate=f"<b>Siswa #%{{customdata[0]}}</b><br>Nilai ujian: %{{customdata[2]}}"
                      f"<br>{LABEL_ID[x]}: %{{customdata[1]}}<br>{LABEL_ID[color]}: %{{customdata[3]}}"
                      "<extra>klik untuk profil</extra>",
        unselected=dict(marker=dict(opacity=0.25)),
    ))
    if highlight is not None and highlight in set(df["ID"]):
        r = df[df["ID"] == highlight].iloc[0]
        fig.add_trace(go.Scatter(x=[r[x]], y=[r["Exam_Score"]], mode="markers", hoverinfo="skip",
                                 marker=dict(size=18, color="rgba(0,0,0,0)", line=dict(width=2.5, color=HEAD))))
    unit = f" ({UNIT[x]})" if UNIT.get(x) and UNIT[x] not in LABEL_ID[x] else ""
    fig.update_xaxes(title=f"{LABEL_ID[x]}{unit}", showgrid=True, gridcolor=GRID)
    fig.update_yaxes(title="Nilai ujian (poin)")
    return _base(fig, 460)


# ================================================================== mini histogram (dialog)
def mini_hist(sub: pd.DataFrame, all_df: pd.DataFrame, name: str = "Kelompok ini") -> go.Figure:
    bins = np.arange(54.5, 101.5, 1)
    a, _ = np.histogram(all_df["Exam_Score"], bins)
    s, _ = np.histogram(sub["Exam_Score"], bins)
    x = (bins[:-1] + 0.5).astype(int)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=s / max(s.sum(), 1) * 100, name=name,
                         marker=dict(color=ACCENT, cornerradius=2),
                         hovertemplate="Nilai %{x}: %{y:.1f}% dari " + name.lower() + "<extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=a / a.sum() * 100, mode="lines", name="Semua siswa (tampilan)",
                             line=dict(color=NAVY, width=2, shape="hvh"),
                             hovertemplate="Nilai %{x}: %{y:.1f}% dari semua<extra></extra>"))
    lo, hi = all_df["Exam_Score"].quantile([0.002, 0.995])
    fig.update_xaxes(title="Nilai ujian (poin)", range=[lo - 1, hi + 2])
    fig.update_yaxes(title="% siswa", ticksuffix="%")
    fig = _base(fig, 240)
    fig.update_layout(showlegend=True, clickmode="none", hovermode="x unified",
                      legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=11)),
                      margin=dict(l=8, r=16, t=30, b=8))
    return fig


# ================================================================== perbandingan dua kelompok
def compare_dist(a: pd.DataFrame, b: pd.DataFrame, name_a: str, name_b: str, pass_mark: int) -> go.Figure:
    bins = np.arange(54.5, 101.5, 1)
    x = (bins[:-1] + 0.5).astype(int)
    fig = go.Figure()
    for d, nm, c in [(a, name_a, NAVY), (b, name_b, ACCENT)]:
        h, _ = np.histogram(d["Exam_Score"], bins)
        fig.add_trace(go.Scatter(
            x=x, y=h / max(h.sum(), 1) * 100, name=nm, mode="lines", line=dict(color=c, width=2.5, shape="spline"),
            hovertemplate=f"{nm}: " + "%{y:.1f}%<extra></extra>"))
        fig.add_vline(x=d["Exam_Score"].mean(), line=dict(color=c, width=1.5, dash="dash"))
    fig.data[0].update(fill="tozeroy", fillcolor="rgba(58,65,111,0.12)")
    fig.data[1].update(fill="tozeroy", fillcolor="rgba(203,12,159,0.12)")
    fig.add_vline(x=pass_mark - 0.5, line=dict(color=MUTED, width=1, dash="dot"))
    fig.add_annotation(x=pass_mark - 0.5, y=0.98, yref="paper", text=f"target ≥{pass_mark}", showarrow=False,
                       xanchor="left", yanchor="top", xshift=4, font=dict(size=10, color=MUTED),
                       bgcolor="rgba(255,255,255,0.85)")
    lo = min(a["Exam_Score"].quantile(.002), b["Exam_Score"].quantile(.002))
    hi = max(a["Exam_Score"].quantile(.995), b["Exam_Score"].quantile(.995))
    fig.update_xaxes(title="Nilai ujian (poin)", range=[lo - 1, hi + 2])
    fig.update_yaxes(title="% siswa dalam kelompok", ticksuffix="%")
    fig = _base(fig, 330)
    fig.update_layout(showlegend=True, clickmode="none", hovermode="x unified",
                      legend=dict(orientation="h", y=1.04, yanchor="bottom", x=0, font=dict(size=11)),
                      margin=dict(l=8, r=16, t=40, b=8))
    return fig


def compare_profile(rows: pd.DataFrame, name_a: str, name_b: str) -> go.Figure:
    """Dumbbell: rata-rata faktor numerik A vs B, dinormalisasi ke persentil semua siswa."""
    fig = go.Figure()
    for _, r in rows.iterrows():
        fig.add_trace(go.Scatter(x=[r["pa"], r["pb"]], y=[r["label"]] * 2, mode="lines",
                                 line=dict(color=GRAY, width=3), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=rows["pa"], y=rows["label"], mode="markers", name=name_a,
                             marker=dict(size=13, color=NAVY, line=dict(width=2, color="white")),
                             customdata=rows["va"], hovertemplate="%{y}<br>" + name_a +
                             ": rata-rata %{customdata:.1f} (persentil %{x:.0f})<extra></extra>"))
    fig.add_trace(go.Scatter(x=rows["pb"], y=rows["label"], mode="markers", name=name_b,
                             marker=dict(size=13, color=ACCENT, line=dict(width=2, color="white")),
                             customdata=rows["vb"], hovertemplate="%{y}<br>" + name_b +
                             ": rata-rata %{customdata:.1f} (persentil %{x:.0f})<extra></extra>"))
    fig.update_xaxes(title="Persentil di antara semua siswa (0–100)",
                     range=[0, 100], showgrid=True, gridcolor=GRID, dtick=25)
    fig.update_yaxes(title="Faktor", showgrid=False, autorange="reversed")
    fig = _base(fig, 46 * len(rows) + 90)
    fig.update_layout(showlegend=True, clickmode="none",
                      legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=11)),
                      margin=dict(l=8, r=16, t=36, b=8))
    return fig


# ================================================================== simulasi: kontribusi faktor
def contributions(contrib: pd.Series) -> go.Figure:
    c = contrib[contrib.abs() >= 0.01].sort_values()
    c.index = [LABEL_ID[i] for i in c.index]
    fig = go.Figure(go.Bar(
        x=c.values, y=c.index, orientation="h",
        marker=dict(color=[POS if v > 0 else NEG for v in c.values], cornerradius=3),
        text=[nf(v, 2, True) for v in c.values], textposition="outside", cliponaxis=False,
        textfont=dict(size=11, color=HEAD),
        hovertemplate="<b>%{y}</b><br>%{x:+.2f} poin dibanding siswa rata-rata<extra></extra>"))
    span = max(c.abs().max(), 0.5)
    fig.update_xaxes(title="Kontribusi terhadap prediksi (poin, dibanding siswa rata-rata)",
                     range=[-span * 1.3, span * 1.3], showgrid=True, gridcolor=GRID,
                     zeroline=True, zerolinecolor="#adb5bd", zerolinewidth=1.5)
    fig.update_yaxes(title="Faktor", showgrid=False)
    fig = _base(fig, 24 * max(len(c), 3) + 90)
    fig.update_layout(clickmode="none", bargap=0.3)
    return fig


def gauge(pred: float, lo: float, hi: float, pass_mark: int) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=pred, number=dict(valueformat=".1f", font=dict(size=40, color=HEAD)),
        gauge=dict(axis=dict(range=[lo, hi], tickfont=dict(size=10, color=MUTED), dtick=5),
                   bar=dict(color=ACCENT, thickness=0.28), bgcolor="#f1f3f7", borderwidth=0,
                   threshold=dict(line=dict(color=HEAD, width=2), thickness=0.8, value=pass_mark),
                   steps=[dict(range=[lo, pass_mark], color="#f1f3f7"),
                          dict(range=[pass_mark, hi], color="#fbe6f6")])))
    fig = _base(fig, 210)
    fig.update_layout(margin=dict(l=20, r=20, t=10, b=0), separators=",.")
    return fig
