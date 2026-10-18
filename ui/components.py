"""共用 UI 元件：RWD 樣式、頁首、公式區塊、說明框、圖表版面。"""
from __future__ import annotations

import html

import plotly.graph_objects as go
import streamlit as st

import config

# 參考調色盤（類別色固定順序，不循環）
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
NEUTRAL = "#8a8985"
GOOD, CRITICAL = "#0ca30c", "#d03b3b"
STRATEGY_COLORS = {"momentum": SERIES[0], "moving_average": SERIES[1], "multi_factor": SERIES[2],
                   "benchmark": NEUTRAL}
MAX_OVERLAY = 4

CSS = """
<style>
:root { --card-bg:#ffffff; --card-border:#e4e3df; --muted:#52514e; --accent:#1c5cab; --soft:#f4f7fb; }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px; }
h1 { font-size: 1.9rem !important; }
.qbox { border-left: 4px solid var(--accent); background: var(--soft); padding: .8rem 1rem;
        border-radius: 6px; margin: .4rem 0 1rem 0; }
.qbox b { color: var(--accent); }
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .75rem;
             margin: .4rem 0 1rem 0; }
.card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 10px;
        padding: .8rem 1rem; }
.card .t { font-size: .82rem; color: var(--muted); }
.card .v { font-size: 1.35rem; font-weight: 600; margin-top: .15rem; word-break: break-word; }
.card .d { font-size: .8rem; color: var(--muted); margin-top: .2rem; }
.step { display:flex; gap:.6rem; align-items:flex-start; }
.step .n { flex:0 0 auto; width:1.8rem; height:1.8rem; border-radius:50%; background:var(--accent);
           color:#fff; display:flex; align-items:center; justify-content:center; font-weight:600; font-size:.9rem; }
.disclaimer { font-size: .8rem; color: #7a4a00; background: #fff6e0; border: 1px solid #f3dca4;
              border-radius: 6px; padding: .35rem .7rem; margin-bottom: .6rem; }
.plain { background:#f3faf4; border:1px solid #cfe9d3; border-radius:8px; padding:.7rem 1rem;
          margin:.3rem 0 1rem 0; line-height:1.7; }
.plain b:first-child { color:#0a6b0a; }
.fund-grid { grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); }
.card.fund .fh { display:flex; justify-content:space-between; align-items:center; gap:.4rem; }
.card.fund .fv { font-size:1.05rem; margin:.45rem 0 .35rem 0; }
.card.fund .fl { display:flex; justify-content:space-between; font-size:.85rem; color:var(--muted);
                 border-top:1px dashed var(--card-border); padding-top:.25rem; margin-top:.25rem; }
.card.fund .fl b { color:#0b0b0b; font-weight:600; }
.risk { font-size:.75rem; font-weight:600; padding:.05rem .5rem; border-radius:999px; white-space:nowrap; }
.risk-低 { background:#e3f6e3; color:#0a6b0a; } .risk-中 { background:#fff3d6; color:#7a4a00; }
.risk-高 { background:#fbe4e4; color:#9c2626; }
.up { color:#0a6b0a; font-weight:700; } .down { color:#9c2626; font-weight:700; }
.chart-title { font-weight: 600; font-size: 1rem; margin: .6rem 0 -.2rem 0; }
.chart-note { font-size: .8rem; color: var(--muted); margin-top: -.4rem; margin-bottom: 1rem; }
.tag { display:inline-block; padding:.05rem .5rem; border-radius:999px; font-size:.78rem; font-weight:600; }
.tag-bull { background:#e3f6e3; color:#0a6b0a; } .tag-bear { background:#fbe4e4; color:#9c2626; }
.tag-mixed { background:#eeeeec; color:#52514e; }
.katex-display { overflow-x: auto; overflow-y: hidden; padding: .2rem 0; }
@media (max-width: 640px) {
  .block-container { padding-left: 1rem; padding-right: 1rem; padding-top: 1.2rem; }
  h1 { font-size: 1.45rem !important; } h2 { font-size: 1.2rem !important; } h3 { font-size: 1.05rem !important; }
  .card .v { font-size: 1.1rem; }
  .card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .5rem; }
  .card-grid.fund-grid { grid-template-columns: 1fr; }
  .katex { font-size: .95em; }
}
</style>
"""


def setup_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def disclaimer() -> None:
    st.markdown(f'<div class="disclaimer">⚠️ {html.escape(config.DISCLAIMER)}</div>', unsafe_allow_html=True)


def page_header(title: str, question: str, data_needed: str | None = None) -> None:
    disclaimer()
    st.title(title)
    st.markdown(f'<div class="qbox"><b>要回答的問題：</b>{question}</div>', unsafe_allow_html=True)
    if data_needed:
        st.markdown(f"**需要的資料：** {data_needed}")


def cards(items: list[tuple[str, str, str | None]]) -> None:
    """items: (標題, 數值, 說明)。以 CSS grid 自動換行，手機兩欄。"""
    body = "".join(
        f'<div class="card"><div class="t">{html.escape(t)}</div><div class="v">{html.escape(v)}</div>'
        + (f'<div class="d">{html.escape(d)}</div>' if d else "") + "</div>"
        for t, v, d in items
    )
    st.markdown(f'<div class="card-grid">{body}</div>', unsafe_allow_html=True)


EXPLAIN_MODES = ["白話版", "專業版"]


def is_plain() -> bool:
    """側邊欄「說明方式」：白話版（預設，給一般投資人）或專業版（公式全展開）。"""
    return st.session_state.get("explain_mode", EXPLAIN_MODES[0]) == EXPLAIN_MODES[0]


def formula(latex: str, explain: str | None = None) -> None:
    """白話版把公式收進「看公式」折疊區；專業版直接顯示。"""
    target = st.expander("🔍 看公式（給想深入了解的人）") if is_plain() else st.container()
    with target:
        st.latex(latex)
        if explain:
            st.caption(explain)


def plain(text: str, title: str = "白話說") -> None:
    """💡 白話說明框：用生活化語言解釋上一段內容。"""
    st.markdown(f'<div class="plain"><b>💡 {html.escape(title)}：</b>{text}</div>', unsafe_allow_html=True)


def fund_cards(items: list[dict]) -> None:
    """基金小卡：name、tag、headline、lines（[(label, value), ...]）、level（低／中／高）。"""
    body = []
    for it in items:
        lv = it.get("level", "")
        lines = "".join(f'<div class="fl"><span>{html.escape(a)}</span><b>{html.escape(b)}</b></div>'
                        for a, b in it["lines"])
        body.append(
            f'<div class="card fund"><div class="fh"><b>{html.escape(it["name"])}</b>'
            f'<span class="risk risk-{html.escape(lv)}">風險{html.escape(lv)}</span></div>'
            f'<div class="d">{html.escape(it["tag"])}</div>'
            f'<div class="fv">{it["headline"]}</div>{lines}</div>')
    st.markdown(f'<div class="card-grid fund-grid">{"".join(body)}</div>', unsafe_allow_html=True)


def meaning(can: list[str], cannot: list[str]) -> None:
    st.subheader("結果代表什麼、不代表什麼")
    c1, c2 = st.columns(2)
    with c1:
        st.success("**可以說明**\n\n" + "\n".join(f"- {x}" for x in can))
    with c2:
        st.warning("**不能推論**\n\n" + "\n".join(f"- {x}" for x in cannot))


def chart_note(period: str, unit: str, note: str) -> None:
    st.markdown(f'<div class="chart-note">期間：{html.escape(period)}｜單位：{html.escape(unit)}｜'
                f'{html.escape(note)}｜資料來源：SYNTHETIC 模擬資料，僅供展示</div>', unsafe_allow_html=True)


def style_fig(fig: go.Figure, title: str, y_title: str, x_title: str = "", height: int = 420,
              legend: bool = True) -> go.Figure:
    fig.update_layout(
        meta={"title": title},
        height=height,
        margin=dict(l=10, r=10, t=10 if not legend else 40, b=10),
        hovermode="x unified",
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title_text=""),
        font=dict(family="Noto Sans TC, Microsoft JhengHei, sans-serif", size=12),
        plot_bgcolor="#fcfcfb", paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(title_text=x_title, showgrid=False, linecolor="#c3c2b7")
    fig.update_yaxes(title_text=y_title, gridcolor="#ecebe7", zerolinecolor="#c3c2b7")
    return fig


def show_fig(fig: go.Figure, key: str | None = None) -> None:
    """圖表標題以 HTML 呈現在圖外，避免窄螢幕時與圖例重疊。"""
    meta = fig.layout.meta
    title = meta.get("title") if isinstance(meta, dict) else None
    if title:
        st.markdown(f'<div class="chart-title">{html.escape(title)}</div>', unsafe_allow_html=True)
    st.plotly_chart(fig, width="stretch", key=key,
                    config={"displaylogo": False, "responsive": True,
                            "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


def state_tag(state: str) -> str:
    cls = {"多頭排列": "tag-bull", "空頭排列": "tag-bear"}.get(state, "tag-mixed")
    icon = {"多頭排列": "▲", "空頭排列": "▼"}.get(state, "◆")
    return f'<span class="tag {cls}">{icon} {html.escape(state)}</span>'


def pct(x: float, digits: int = 2) -> str:
    return "—" if x is None or x != x else f"{x * 100:.{digits}f}%"


def weight_sliders(store_key: str, defaults: dict[str, float], labels: dict[str, str], cols: int = 3) -> dict:
    """權重滑桿（0~100，步距 5）。值存在 session_state，跨頁保留；回傳原始百分比 dict。"""
    ss = st.session_state
    if store_key not in ss:
        ss[store_key] = {k: round(v * 100) for k, v in defaults.items()}
    widget_keys = {k: f"{store_key}__{k}" for k in defaults}
    for k, wk in widget_keys.items():
        if wk not in ss:
            ss[wk] = ss[store_key][k]

    def reset():
        for k, wk in widget_keys.items():
            ss[wk] = round(defaults[k] * 100)

    columns = st.columns(min(cols, len(defaults)))
    for i, (k, wk) in enumerate(widget_keys.items()):
        with columns[i % len(columns)]:
            st.slider(labels[k], 0, 100, step=5, key=wk, format="%d%%")
    st.button("還原預設權重", on_click=reset, key=f"{store_key}__reset")
    ss[store_key] = {k: ss[wk] for k, wk in widget_keys.items()}
    return dict(ss[store_key])
