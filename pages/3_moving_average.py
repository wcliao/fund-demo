"""均線策略頁（規格書 5.B）。"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from database import repository as repo
from services.analysis_service import save_strategy_snapshot, strategy_params
from strategies.moving_average import BEAR, BULL, DEATH, GOLDEN, state_runs
from ui import components as ui
from ui.data import eval_date, fund_label, get_data, ma_frame_for, ma_snapshot_at

master, _ = get_data()
d = eval_date()
ds = f"{d:%Y-%m-%d}"

ui.page_header("均線策略 Moving Average", "基金目前走勢與過去長期趨勢有什麼關係？訊號會不會落後？",
               f"評估日 {ds} 以前的每日 NAV。SMA60 自第 60 筆、SMA200 自第 200 筆資料起才有值。")

st.subheader("方法與公式")
ui.formula(r"SMA_n(t)=\frac{1}{n}\sum_{i=0}^{n-1}NAV_{t-i},\qquad n=60\ (短期),\ 200\ (長期)")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**狀態**（每天判斷，可持續很多天）")
    st.markdown("""
| 條件 | 標示 |
| --- | --- |
| NAV > SMA200 且 SMA60 > SMA200 | ▲ 多頭排列 |
| NAV < SMA200 且 SMA60 < SMA200 | ▼ 空頭排列 |
| 其他 | ◆ 混合／轉換中 |
""")
with c2:
    st.markdown("**事件**（只在穿越當天成立）")
    st.latex(r"\text{黃金交叉}: SMA60_{t-1}\le SMA200_{t-1}\ \wedge\ SMA60_t>SMA200_t")
    st.latex(r"\text{死亡交叉}: SMA60_{t-1}\ge SMA200_{t-1}\ \wedge\ SMA60_t<SMA200_t")
    st.caption("第一個 SMA200 有值的日子沒有前一日可比較，不產生事件。")
st.info("**狀態 ≠ 事件**：多頭排列可能持續數百天，但黃金交叉只在穿越的那一天出現。")

st.markdown(f"**參數：** 短期均線 {config.SMA_SHORT} 日、長期均線 {config.SMA_LONG} 日（第一版固定，回測使用相同參數）。")

# ---- 全部基金狀態 ----
snap = ma_snapshot_at(ds)
st.subheader(f"10 檔基金於 {ds} 的趨勢狀態")
counts = snap["state"].value_counts()
ui.cards([("▲ 多頭排列", f"{counts.get(BULL, 0)} 檔", "回測中會被持有"),
          ("▼ 空頭排列", f"{counts.get(BEAR, 0)} 檔", None),
          ("◆ 混合／轉換中", f"{len(snap) - counts.get(BULL, 0) - counts.get(BEAR, 0)} 檔", None)])
tbl = snap[["state", "nav", "sma_short", "sma_long", "gap_pct", "last_event", "last_event_date",
            "n_golden", "n_death"]].copy()
tbl.insert(0, "基金", [fund_label(master, f) for f in tbl.index])
tbl["gap_pct"] = tbl["gap_pct"] * 100
tbl["last_event_date"] = pd.to_datetime(tbl["last_event_date"])
st.dataframe(tbl, hide_index=True, column_config={
    "state": "狀態", "nav": st.column_config.NumberColumn("NAV", format="%.2f"),
    "sma_short": st.column_config.NumberColumn("SMA60", format="%.2f"),
    "sma_long": st.column_config.NumberColumn("SMA200", format="%.2f"),
    "gap_pct": st.column_config.NumberColumn("NAV 相對 SMA200", format="%+.2f%%"),
    "last_event": "最近事件", "last_event_date": st.column_config.DateColumn("事件日期", format="YYYY-MM-DD"),
    "n_golden": st.column_config.NumberColumn("黃金交叉次數", format="%d"),
    "n_death": st.column_config.NumberColumn("死亡交叉次數", format="%d"),
})

# ---- 單一基金走勢圖 ----
st.subheader("走勢圖與交叉事件")
c1, c2 = st.columns([2, 1])
with c1:
    fid = st.selectbox("選擇基金", list(master.index), index=list(master.index).index("F004"),
                       format_func=lambda f: fund_label(master, f), key="ma_fund",
                       help="建議比較 F004（景氣循環）與 F009（趨勢反轉）")
with c2:
    shade = st.toggle("以底色標示狀態", value=True)
f = ma_frame_for(fid).loc[:d]
fig = go.Figure()
if shade:
    colors = {BULL: "rgba(12,163,12,.08)", BEAR: "rgba(208,59,59,.08)"}
    for a, b, stt in state_runs(f["state"]):
        if stt in colors:
            fig.add_vrect(x0=a, x1=b, fillcolor=colors[stt], line_width=0, layer="below")
fig.add_trace(go.Scatter(x=f.index, y=f["nav"], name="NAV", line=dict(width=1.5, color="#9a9994"),
                         hovertemplate="%{y:.2f}"))
fig.add_trace(go.Scatter(x=f.index, y=f["sma_short"], name="SMA60（短期）", line=dict(width=2, color=ui.SERIES[0]),
                         hovertemplate="%{y:.2f}"))
fig.add_trace(go.Scatter(x=f.index, y=f["sma_long"], name="SMA200（長期）", line=dict(width=2, color=ui.SERIES[1]),
                         hovertemplate="%{y:.2f}"))
for ev, sym, col in [(GOLDEN, "triangle-up", ui.GOOD), (DEATH, "triangle-down", ui.CRITICAL)]:
    e = f[f["event"] == ev]
    fig.add_trace(go.Scatter(x=e.index, y=e["sma_short"], mode="markers", name=f"{'▲' if ev == GOLDEN else '▼'} {ev}",
                             marker=dict(symbol=sym, size=13, color=col, line=dict(color="#fcfcfb", width=2)),
                             hovertemplate=f"{ev}<br>%{{x|%Y-%m-%d}}<br>SMA60 %{{y:.2f}}<extra></extra>"))
ui.style_fig(fig, f"{fund_label(master, fid)}：NAV、SMA60、SMA200 與交叉事件", "NAV（TWD／單位）", "日期", height=480)
ui.show_fig(fig, "ma_chart")
ui.chart_note(f"{f.index[0]:%Y-%m-%d} ～ {ds}", "TWD／單位",
              "綠底＝多頭排列、紅底＝空頭排列、無底色＝混合；▲ 黃金交叉、▼ 死亡交叉")

# ---- 事件與落後分析 ----
events = f.dropna(subset=["event"])
st.markdown(f"**{fund_label(master, fid)} 交叉事件明細與訊號落後**")
if events.empty:
    st.info("評估日以前沒有交叉事件。")
else:
    rows, prev = [], f.index[0]
    for dt, r in events.iterrows():
        seg = f.loc[prev:dt, "nav"]
        ext_date = seg.idxmin() if r["event"] == GOLDEN else seg.idxmax()
        rows.append({"事件日期": dt, "事件": r["event"], "當日 NAV": r["nav"], "SMA60": r["sma_short"],
                     "SMA200": r["sma_long"],
                     "前段極值日": ext_date, "落後交易日數": f.index.get_loc(dt) - f.index.get_loc(ext_date),
                     "從極值到訊號已變動": (r["nav"] / f.loc[ext_date, "nav"] - 1) * 100,
                     "原因": ("SMA60 由下往上穿越 SMA200" if r["event"] == GOLDEN else "SMA60 由上往下穿越 SMA200")})
        prev = dt
    ev_tbl = pd.DataFrame(rows)
    st.dataframe(ev_tbl, hide_index=True, column_config={
        "事件日期": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "前段極值日": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "當日 NAV": st.column_config.NumberColumn(format="%.2f"),
        "SMA60": st.column_config.NumberColumn(format="%.2f"), "SMA200": st.column_config.NumberColumn(format="%.2f"),
        "從極值到訊號已變動": st.column_config.NumberColumn(format="%+.2f%%"),
    })
    st.caption("落後交易日數：從上一段的最低點（黃金交叉）或最高點（死亡交叉）到訊號出現所經過的交易日。"
               "「已變動」越大，代表訊號出現時行情已走了一大段——這就是均線的訊號落後。")

# ---- 計算範例 ----
st.subheader("具體計算範例（評估日數值）")
last = f.iloc[-1]
if pd.notna(last["sma_long"]):
    st.latex(rf"SMA60=\frac{{1}}{{60}}\sum_{{i=0}}^{{59}}NAV_{{t-i}}={last['sma_short']:.2f},\quad "
             rf"SMA200=\frac{{1}}{{200}}\sum_{{i=0}}^{{199}}NAV_{{t-i}}={last['sma_long']:.2f}")
    c_nav = ">" if last["nav"] > last["sma_long"] else "<"
    c_sma = ">" if last["sma_short"] > last["sma_long"] else "<"
    st.latex(rf"NAV={last['nav']:.2f}\ {c_nav}\ SMA200={last['sma_long']:.2f},\qquad "
             rf"SMA60={last['sma_short']:.2f}\ {c_sma}\ SMA200={last['sma_long']:.2f}")
    st.markdown(f"→ 判定為 {ui.state_tag(last['state'])}", unsafe_allow_html=True)
else:
    st.info("資料不足 200 筆，SMA200 尚未有值。")

with st.expander("💾 儲存本次狀態至資料庫"):
    st.caption("score 欄位以 NAV 相對 SMA200 的偏離（%）記錄；狀態與事件存於 details_json。")
    if st.button("儲存結果", key="ma_save", type="primary"):
        res = snap.assign(score=snap["gap_pct"], rank=None)
        conn = repo.connect()
        try:
            cid, n = save_strategy_snapshot(conn, "moving_average", strategy_params("moving_average"), d,
                                            res.drop(columns=["last_event_date"]).assign(
                                                last_event_date=snap["last_event_date"].astype(str)))
        finally:
            conn.close()
        st.success(f"已儲存 {n} 筆結果，config_id = {cid}，評估日 {ds}。")

ui.meaning(
    ["評估日的 NAV 是否符合「長期趨勢向上」的條件", "趨勢何時發生轉換（交叉事件日期）"],
    ["訊號一定即時：均線是過去 60／200 日的平均，必然落後於價格", "交叉後一定會延續趨勢：盤整時可能反覆交叉（假訊號）",
     "多頭排列代表未來會上漲"],
)
