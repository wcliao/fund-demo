"""動能策略頁（規格書 5.A）。"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from database import repository as repo
from services.analysis_service import save_strategy_snapshot, strategy_params
from ui import components as ui
from ui.data import eval_date, fund_label, get_data, hist, momentum_at, to_weights

master, _ = get_data()
nav = hist()
d = eval_date()
ds = f"{d:%Y-%m-%d}"
PERIODS = list(config.MOMENTUM_WINDOWS)

ui.page_header("動能策略 Momentum", "過去一段時間表現較強的基金，是否值得列入觀察？",
               f"評估日 {ds} 以前的每日 NAV。12M 報酬需至少 253 筆資料（索引 t ≥ 252）。")

# ---- 方法與公式 ----
st.subheader("方法與公式")
c1, c2 = st.columns(2)
with c1:
    ui.formula(r"R_n(t)=\frac{NAV_t}{NAV_{t-n}}-1",
               "n = 63、126、252 個交易日，分別近似 3M、6M、12M。")
with c2:
    ui.formula(r"Score=w_{3M}R_{3M}+w_{6M}R_{6M}+w_{12M}R_{12M}",
               "預設權重 20%／30%／50%；權重自動正規化為總和 100%。分數由高至低排名，同分依代碼排序。")

# ---- 參數 ----
st.subheader("可調整參數：期間權重")
raw_w = ui.weight_sliders("mom_w", config.DEFAULT_MOMENTUM_WEIGHTS, {p: f"{p} 權重" for p in PERIODS})
try:
    w = to_weights(raw_w)
except ValueError as e:
    st.error(f"權重設定錯誤：{e}。請至少一個期間權重大於 0。")
    st.stop()
st.markdown("正規化後權重：" + "、".join(f"**{p} {w[p]:.0%}**" for p in PERIODS)
            + ("（原始輸入總和不是 100%，已自動正規化）" if sum(raw_w.values()) != 100 else ""))
wt = tuple(sorted(w.items()))
df = momentum_at(ds, wt)

# ---- 排行榜 ----
st.subheader("動能排行榜")
board = df[["rank", "score", "R_3M", "R_6M", "R_12M", "top_driver", "status"]].copy()
board.insert(1, "基金", [fund_label(master, f) for f in board.index])
for c in ["score", "R_3M", "R_6M", "R_12M"]:
    board[c] = board[c] * 100
st.dataframe(board, hide_index=True, column_config={
    "rank": st.column_config.NumberColumn("排名", format="%d"),
    "score": st.column_config.ProgressColumn("加權報酬分數", format="%.2f%%",
                                             min_value=float(min(board["score"].min(), 0)),
                                             max_value=float(max(board["score"].max(), 1))),
    "R_3M": st.column_config.NumberColumn("3M 報酬", format="%.2f%%"),
    "R_6M": st.column_config.NumberColumn("6M 報酬", format="%.2f%%"),
    "R_12M": st.column_config.NumberColumn("12M 報酬", format="%.2f%%"),
    "top_driver": "主要貢獻期間", "status": "狀態",
})

# ---- 貢獻拆解圖 ----
order = df.dropna(subset=["score"]).index[::-1]
fig = go.Figure()
for i, p in enumerate(PERIODS):
    fig.add_trace(go.Bar(y=[fund_label(master, f) for f in order], x=df.loc[order, f"c_{p}"] * 100,
                         name=f"{p} 貢獻（{w[p]:.0%} × R_{p}）", orientation="h",
                         marker=dict(color=ui.SERIES[i], line=dict(color="#fcfcfb", width=2)),
                         hovertemplate="%{x:.2f} 個百分點"))
fig.add_trace(go.Scatter(y=[fund_label(master, f) for f in order], x=df.loc[order, "score"] * 100, mode="markers",
                         name="總分", marker=dict(symbol="diamond", size=10, color="#0b0b0b",
                                                 line=dict(color="#fcfcfb", width=2)),
                         hovertemplate="總分 %{x:.2f}%"))
fig.update_layout(barmode="relative")
ui.style_fig(fig, "各基金動能分數拆解：各期間加權貢獻", "", "百分點（%）", height=480)
fig.update_layout(hovermode="y unified")
ui.show_fig(fig, "mom_contrib")
ui.chart_note(f"評估日 {ds}", "百分點", "正負堆疊；菱形為加權總分＝三段貢獻相加")

# ---- 計算範例 ----
st.subheader("具體計算範例（實際數值代入）")
fid = st.selectbox("選擇基金", list(master.index), index=list(master.index).index("F002"),
                   format_func=lambda f: fund_label(master, f), key="mom_example")
row = df.loc[fid]
s = nav[fid]
if row["status"] == "OK":
    lines = []
    for p, n in config.MOMENTUM_WINDOWS.items():
        lines.append(rf"R_{{{p}}}=\frac{{{s.iloc[-1]:.2f}}}{{{s.iloc[-1 - n]:.2f}}}-1={row[f'R_{p}'] * 100:.2f}\%"
                     rf"\quad(NAV_{{t-{n}}}\text{{ 於 {s.index[-1 - n]:%Y-%m-%d}}})")
    for ln in lines:
        st.latex(ln)
    st.latex(r"Score=" + "+".join(rf"{w[p]:.2f}\times{row[f'R_{p}'] * 100:.2f}\%" for p in PERIODS)
             + rf"={row['score'] * 100:.2f}\%")
    st.markdown(f"**得分原因：** {fund_label(master, fid)} 排名第 **{int(row['rank'])}**，"
                f"貢獻最大的是 **{row['top_driver']}** 期間（{row[f'c_{row.top_driver}'] * 100:+.2f} 個百分點）。")
else:
    st.info("此評估日資料不足，無法計算 12M 報酬。")

# ---- F002 vs F006 ----
st.subheader("展示案例：F002 長期強勢 vs F006 近期反轉")
cmp = df.loc[["F002", "F006"], [f"R_{p}" for p in PERIODS]] * 100
fig2 = go.Figure()
for i, f in enumerate(cmp.index):
    fig2.add_trace(go.Bar(x=PERIODS, y=cmp.loc[f], name=fund_label(master, f), marker_color=ui.SERIES[i],
                          marker_line=dict(color="#fcfcfb", width=2),
                          text=[f"{v:.1f}%" for v in cmp.loc[f]], textposition="outside",
                          hovertemplate="%{y:.2f}%"))
ui.style_fig(fig2, "不同期間報酬比較", "期間報酬（%）", "回顧期間", height=380)
ui.show_fig(fig2, "mom_cmp")
ui.chart_note(f"評估日 {ds}", "%", "短期與長期報酬不一致時，權重設定決定誰排前面")

st.markdown("**權重如何影響排名？** 以三組權重重新排名（其餘條件相同）：")
presets = {"重短期 60/30/10": {"3M": .6, "6M": .3, "12M": .1}, "預設 20/30/50": config.DEFAULT_MOMENTUM_WEIGHTS,
           "只看 12M 0/0/100": {"3M": 0, "6M": 0, "12M": 1}, "目前設定": w}
sens = pd.DataFrame({k: momentum_at(ds, tuple(sorted(to_weights(v).items())))["rank"] for k, v in presets.items()})
sens.index = [fund_label(master, f) for f in sens.index]
st.dataframe(sens.sort_values("目前設定").astype("Int64"), column_config={
    k: st.column_config.NumberColumn(k, format="%d") for k in presets})
st.caption("數字為排名（1 = 最強）。F006 這類「近期回升」基金在重短期權重下排名明顯上升。")

# ---- 儲存 ----
with st.expander("💾 儲存本次計算結果至資料庫"):
    st.caption("拖拉權重只在記憶體計算；按下儲存才寫入 strategy_config／strategy_result。相同參數會重用同一個 config_id。")
    if st.button("儲存結果", key="mom_save", type="primary"):
        conn = repo.connect()
        try:
            cid, n = save_strategy_snapshot(conn, "momentum", strategy_params("momentum", w), d,
                                            df)
        finally:
            conn.close()
        st.success(f"已儲存 {n} 筆結果，config_id = {cid}，評估日 {ds}。")

ui.meaning(
    ["在評估日以前，哪些基金的歷史期間報酬較強", "不同期間權重如何改變排序"],
    ["動能強的基金未來一定持續上漲（動能可能反轉）", "高動能代表低風險——本策略完全不考慮波動與回撤",
     "跨資產類別（股票 vs 債券）的動能比較具投資合理性"],
)
