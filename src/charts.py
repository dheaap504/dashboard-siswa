"""Grafik Plotly. Setiap titik/batang membawa `customdata` sebagai kunci
sehingga klik pada grafik bisa dipetakan ke kelompok / siswa / faktor."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .analysis import BINS, group_stats
from .data_loader import LABEL_ID, nf

# Palet (satu hue biru untuk data, abu untuk referensi)
# Palet bergaya Soft UI: navy untuk data utama, fuchsia untuk sorotan
BLUE = "#3a416f"          # seri utama (navy)
BLUE_LIGHT = "#a8b8d8"    # kelompok sekunder
BLUE_DARK = "#141727"
ACCENT = "#cb0c9f"        # sorotan (mis. mencapai target)
GRAY = "#cbd3da"
TEXT = "#67748e"
MUTED = "#8392ab"
GRID = "#eef0f4"
SEQ_SCALE = [[0, "#fbe6f6"], [0.35, "#ec8fd6"], [0.7, "#cb0c9f"], [1, "#5e0a4c"]]
FONT = "Open Sans, -apple-system, Segoe UI, sans-serif"

CONFIG = {"displayModeBar": False, "scrollZoom": False}


def _base(fig: go.Figure, height: int = 320, **kw) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=4, r=12, t=8, b=4),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=TEXT),
        hoverlabel=dict(bgcolor="white", bordercolor="#e9ecef",
                        font=dict(family=FONT, size=12, color="#344767")),
        separators=",.", showlegend=False, bargap=0.18, clickmode="event+select", dragmode=False,
    )
    if kw:
        fig.update_layout(**kw)
    fig.update_xaxes(showgrid=False, linecolor="#e9ecef", ticks="", tickfont=dict(color=MUTED),
                     title_font=dict(size=12, color=MUTED), fixedrange=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED),
                     title_font=dict(size=12, color=MUTED), fixedrange=True)
    return fig


def _ci(s: pd.Series) -> float:
    return 1.96 * s.std(ddof=1) / np.sqrt(len(s)) if len(s) > 1 else 0.0


# ---------------------------------------------------------------- distribusi
def distribution(df: pd.DataFrame, pass_mark: int, dark: bool = True) -> go.Figure:
    counts = df["Exam_Score"].round().astype(int).value_counts().sort_index()
    total = counts.sum()
    hi, lo = ("#ffffff", "rgba(255,255,255,0.38)") if dark else (ACCENT, BLUE_LIGHT)
    colors = [hi if s >= pass_mark else lo for s in counts.index]
    fig = go.Figure(go.Bar(
        x=counts.index, y=counts.values, marker=dict(color=colors, cornerradius=3),
        customdata=np.stack([counts.index, counts.values / total * 100], axis=1),
        hovertemplate="<b>Nilai %{x}</b><br>%{y} siswa · %{customdata[1]:.1f}%"
                      "<extra>klik untuk detail</extra>",
        unselected=dict(marker=dict(opacity=0.35)),
    ))
    ink = "rgba(255,255,255,0.75)" if dark else TEXT
    fig.add_vline(x=pass_mark - 0.5, line=dict(color=ink, width=1, dash="dot"))
    fig.add_annotation(x=pass_mark - 0.5, y=counts.max(), text=f" target ≥{pass_mark}",
                       showarrow=False, xanchor="left", font=dict(size=11, color=ink))
    fig.update_xaxes(title=None, range=[counts.index.min() - 1, min(counts.index.max(), 100) + 1])
    fig.update_yaxes(title=None)
    fig = _base(fig, 420)
    fig.update_layout(margin=dict(l=4, r=22, t=22, b=30))
    if dark:
        fig.update_xaxes(tickfont=dict(color="rgba(255,255,255,0.7)"), linecolor="rgba(255,255,255,0.2)")
        fig.update_yaxes(tickfont=dict(color="rgba(255,255,255,0.7)"), gridcolor="rgba(255,255,255,0.12)")
    return fig


# ---------------------------------------------------------------- peringkat faktor
def factor_ranking(effects: pd.DataFrame) -> go.Figure:
    e = effects.sort_values("abs_effect")
    colors = [ACCENT if a >= 1 else ("#ec8fd6" if a >= 0.5 else GRAY) for a in e["abs_effect"]]
    fig = go.Figure(go.Bar(
        x=e["effect"], y=e["label"], orientation="h",
        marker=dict(color=colors, cornerradius=3),
        customdata=np.stack([e["col"], e["low"], e["high"], e["kind"]], axis=1),
        text=[f"{nf(v, 1, True)}" for v in e["effect"]], textposition="outside",
        textfont=dict(size=11, color=TEXT), cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>%{customdata[1]} → %{customdata[2]}"
                      "<br>Selisih nilai: <b>%{x:+.2f} poin</b><extra>klik untuk detail</extra>",
        unselected=dict(marker=dict(opacity=0.35)),
    ))
    lo = min(0, e["effect"].min())
    fig.update_xaxes(title="Selisih poin",
                     range=[lo - 0.8, e["effect"].max() + 1.2], showgrid=True, gridcolor=GRID,
                     zeroline=True, zerolinecolor="#d2d6da")
    fig.update_yaxes(showgrid=False)
    return _base(fig, 23 * len(e) + 50, bargap=0.32)


# ---------------------------------------------------------------- satu faktor
def factor_chart(df: pd.DataFrame, col: str, overall: float) -> go.Figure:
    g = group_stats(df, col)
    numeric = col in BINS
    fig = go.Figure()
    fig.add_hline(y=overall, line=dict(color=GRAY, width=1, dash="dot"))
    fig.add_annotation(xref="paper", x=1, y=overall, text=f"rata-rata {nf(overall, 1)}",
                       showarrow=False, xanchor="right", yanchor="bottom",
                       font=dict(size=11, color=MUTED))
    fig.add_trace(go.Scatter(
        x=g["group"], y=g["mean"],
        mode="lines+markers+text" if numeric else "markers+text",
        line=dict(color=ACCENT, width=3, shape="spline", smoothing=0.6),
        marker=dict(size=14, color=ACCENT, line=dict(width=3, color="white")),
        error_y=dict(type="data", array=g["ci"], color="#ec8fd6", thickness=1.5, width=6),
        text=[f"{nf(m, 1)}" for m in g["mean"]],
        textposition="top center" if numeric else "middle right",
        textfont=dict(size=12, color="#344767"), cliponaxis=False,
        customdata=np.stack([g["group"], g["n"], g["pass_rate"] * 100], axis=1),
        hovertemplate="<b>%{x}</b><br>Rata-rata %{y:.2f}<br>%{customdata[1]} siswa"
                      " · %{customdata[2]:.0f}% ≥70<extra>klik untuk detail</extra>",
        unselected=dict(marker=dict(opacity=0.35)),
    ))
    span = (g["mean"] + g["ci"]).max() - (g["mean"] - g["ci"]).min()
    pad = max(0.6, span * 0.25)
    fig.update_yaxes(title="Rata-rata nilai ujian",
                     range=[min((g["mean"] - g["ci"]).min(), overall) - pad,
                            max((g["mean"] + g["ci"]).max(), overall) + pad])
    fig.update_xaxes(title=LABEL_ID[col], type="category")
    return _base(fig, 340)


# ---------------------------------------------------------------- kombinasi
def combo_heatmap(df: pd.DataFrame, row: str, col: str) -> go.Figure:
    rb, rl = BINS[row]
    cb, cl = BINS[col]
    t = df.assign(r=pd.cut(df[row], rb, labels=rl, include_lowest=True),
                  c=pd.cut(df[col], cb, labels=cl, include_lowest=True))
    agg = t.groupby(["r", "c"], observed=True)["Exam_Score"].agg(["mean", "count"]).reset_index()
    agg = agg[agg["count"] >= 5]
    zmin, zmax = agg["mean"].min(), agg["mean"].max()
    text_col = ["white" if (m - zmin) / max(zmax - zmin, 1e-9) > 0.55 else "#1b1b1a" for m in agg["mean"]]
    xs, ys = agg["c"].astype(str), agg["r"].astype(str)
    fig = go.Figure(go.Heatmap(
        x=xs, y=ys, z=agg["mean"], colorscale=SEQ_SCALE, zmin=zmin, zmax=zmax, xgap=3, ygap=3,
        text=[nf(m, 1) for m in agg["mean"]], texttemplate="%{text}", hoverinfo="skip",
        textfont=dict(size=13),
        colorbar=dict(title=dict(text="Nilai", font=dict(size=11)), thickness=10,
                      outlinewidth=0, tickfont=dict(size=11, color=MUTED))))
    # lapisan transparen di atas tiap sel agar sel bisa diklik (heatmap tidak mendukung seleksi)
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers", marker=dict(symbol="square", size=64, color="rgba(0,0,0,0.002)"),
        customdata=np.stack([agg["r"].astype(str), agg["c"].astype(str), agg["count"], agg["mean"]], axis=1),
        hovertemplate=f"<b>{LABEL_ID[row]} %{{customdata[0]}} · {LABEL_ID[col]} %{{customdata[1]}}</b>"
                      "<br>Rata-rata %{customdata[3]:.2f} · %{customdata[2]} siswa"
                      "<extra>klik untuk detail</extra>",
        selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)),
    ))
    fig.update_xaxes(title=LABEL_ID[col], type="category", categoryorder="array",
                     categoryarray=[str(x) for x in cl], showline=False)
    fig.update_yaxes(title=LABEL_ID[row], type="category", categoryorder="array",
                     categoryarray=[str(x) for x in rl], showgrid=False)
    return _base(fig, 70 * len(rl) + 90)


# ---------------------------------------------------------------- siswa individual
def student_scatter(df: pd.DataFrame, x: str, color: str, highlight: int | None = None) -> go.Figure:
    rng = np.random.default_rng(7)
    jx = df[x] + rng.uniform(-0.35, 0.35, len(df))
    jy = df["Exam_Score"] + rng.uniform(-0.3, 0.3, len(df))
    fig = go.Figure(go.Scattergl(
        x=jx, y=jy, mode="markers",
        marker=dict(size=6, color=df[color], colorscale=SEQ_SCALE, opacity=0.8,
                    line=dict(width=0),
                    colorbar=dict(title=dict(text=LABEL_ID[color], font=dict(size=11)),
                                  thickness=10, outlinewidth=0, tickfont=dict(size=11, color=MUTED))),
        customdata=np.stack([df["ID"], df[x], df["Exam_Score"], df[color]], axis=1),
        hovertemplate=f"<b>Siswa #%{{customdata[0]}}</b><br>Nilai %{{customdata[2]}}"
                      f"<br>{LABEL_ID[x]}: %{{customdata[1]}}<br>{LABEL_ID[color]}: %{{customdata[3]}}"
                      "<extra>klik untuk profil</extra>",
        unselected=dict(marker=dict(opacity=0.25)),
    ))
    if highlight is not None and highlight in set(df["ID"]):
        r = df[df["ID"] == highlight].iloc[0]
        fig.add_trace(go.Scatter(x=[r[x]], y=[r["Exam_Score"]], mode="markers", hoverinfo="skip",
                                 marker=dict(size=16, color="rgba(0,0,0,0)",
                                             line=dict(width=2.5, color="#0b0b0b"))))
    fig.update_xaxes(title=LABEL_ID[x], showgrid=True, gridcolor=GRID)
    fig.update_yaxes(title="Nilai ujian")
    return _base(fig, 440)


# ---------------------------------------------------------------- mini histogram (di dalam dialog)
def mini_hist(sub: pd.DataFrame, all_df: pd.DataFrame) -> go.Figure:
    bins = np.arange(54.5, 101.5, 1)
    a, _ = np.histogram(all_df["Exam_Score"], bins)
    s, _ = np.histogram(sub["Exam_Score"], bins)
    x = (bins[:-1] + 0.5).astype(int)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=a / a.sum() * 100, mode="lines", name="Semua siswa",
                             line=dict(color=BLUE, width=2, shape="hvh"),
                             hovertemplate="Semua: %{y:.1f}%<extra></extra>"))
    fig.add_trace(go.Bar(x=x, y=s / max(s.sum(), 1) * 100, name="Kelompok ini",
                         marker=dict(color=ACCENT, cornerradius=2),
                         hovertemplate="Nilai %{x}: %{y:.1f}%<extra></extra>"))
    lo, hi = all_df["Exam_Score"].quantile([0.001, 0.999])
    fig.update_xaxes(title="Nilai ujian", range=[lo - 1, hi + 1])
    fig.update_yaxes(title="% siswa")
    fig = _base(fig, 210)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.15, x=0, font=dict(size=11)),
                      clickmode="none", hovermode="x unified")
    return fig
