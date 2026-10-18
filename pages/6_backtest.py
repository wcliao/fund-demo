"""回測比較頁（規格書第六章）。"""
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from backtest.metrics import METRIC_LABELS
from database import repository as repo
from services.analysis_service import STRATEGY_LABELS, save_backtests
from strategies.common import drawdown_series
from ui import components as ui
from ui.data import backtests, fund_label, get_data, session_weights

master, nav = get_data()
mom_w, fac_w = session_weights()
results = backtests(mom_w, fac_w)
first = next(iter(results.values()))[0]
period = f"{first.daily.index[0]:%Y-%m-%d} ～ {first.daily.index[-1]:%Y-%m-%d}"

ui.page_header("回測比較", "如果當時依照每月訊號持有，後來結果如何？（不是證明策略有效）",
               "全期每日 NAV；每個訊號只使用訊號日（含）以前的資料。")

st.subheader("回測規則")
c1, c2 = st.columns(2)
with c1:
    st.markdown(f"""
| 項目 | 設定 |
| --- | --- |
| 初始資金 | {config.INITIAL_CAPITAL:,.0f} 元 |
| 回測期間 | {period} |
| 訊號日 | 每月最後交易日（索引 ≥ 252，第一年暖機） |
| 執行日 | 訊號日的下一個交易日，以當日 NAV 成交 |
| 交易成本 | 每筆成交金額 × {config.COST_RATE:.1%}（買、賣、建倉都收） |
| 現金報酬 | 0 |
| 管理費 | 已含在 NAV，不另扣 |
""")
with c2:
    st.markdown(f"""
| 策略 | 持有規則 |
| --- | --- |
| 動能 | 動能分數前 {config.TOP_N} 名，等權 |
| 均線 | 多頭排列者等權；無符合者全數現金 |
| 多因子 | 總分前 {config.TOP_N} 名，等權 |
| 基準 | 10 檔等權，每月同時點再平衡 |
""")
    mw, fw = dict(mom_w), dict(fac_w)
    st.caption("每次執行日都再平衡回目標權重（持股不變也會調回等權）。使用策略頁目前設定的權重——動能："
               + "、".join(f"{p} {mw[p]:.0%}" for p in config.MOMENTUM_WINDOWS) + "；多因子："
               + "、".join(f"{config.FACTORS[k][0].split('（')[0]} {fw[k]:.0%}" for k in config.FACTORS) + "。")

with st.expander("📐 時點規則與成本公式（防止未來函數）", expanded=False):
    st.markdown("""
```
t 日（月底）收盤 ──► 用 NAV_0 … NAV_t 計算訊號 ──► t+1 日以 NAV_{t+1} 成交
                     （不讀取 t+1 以後任何資料）       t 與 t+1 之間沿用舊持倉估值
```
""")
    ui.formula(r"\text{成本}_i=c\times|\text{目標金額}_i-\text{現有金額}_i|,\quad c=0.2\%")
    ui.formula(r"\text{目標金額}_i=k\cdot w_i\cdot V,\quad V-\sum_i k w_i V-c\sum_i|k w_i V-h_i|=0",
               "以迭代求出縮放係數 k，使扣除成本後現金恰好不為負（V 為執行前組合總值，h_i 為現有持倉市值）。")
    ui.formula(r"\text{年化報酬}=(1+\text{累積報酬})^{252/N}-1,\quad Sharpe=\frac{\bar r\times252-1\%}{\sigma_r\sqrt{252}}")

# ---- 績效 ----
st.subheader("績效比較")
mt = pd.DataFrame({STRATEGY_LABELS[s]: m for s, (_, m) in results.items()}).T
show = mt.copy()
for c in ["cumulative_return", "annual_return", "annual_volatility", "max_drawdown", "turnover"]:
    show[c] = show[c] * 100
st.dataframe(show[list(METRIC_LABELS)], column_config={
    "cumulative_return": st.column_config.NumberColumn("累積報酬", format="%.2f%%"),
    "annual_return": st.column_config.NumberColumn("年化報酬", format="%.2f%%"),
    "annual_volatility": st.column_config.NumberColumn("年化波動率", format="%.2f%%"),
    "max_drawdown": st.column_config.NumberColumn("最大回撤", format="%.2f%%"),
    "sharpe": st.column_config.NumberColumn("Sharpe", format="%.2f"),
    "total_cost": st.column_config.NumberColumn("總交易成本（元）", format="%,.0f"),
    "turnover": st.column_config.NumberColumn("年化換手率", format="%.0f%%"),
    "final_equity": st.column_config.NumberColumn("期末淨值（元）", format="%,.0f"),
})

fig = go.Figure()
for sid, (res, _) in results.items():
    eq = res.daily["equity"] / config.INITIAL_CAPITAL * 100
    fig.add_trace(go.Scatter(x=eq.index, y=eq, name=STRATEGY_LABELS[sid],
                             line=dict(width=2, color=ui.STRATEGY_COLORS[sid],
                                       dash="dot" if sid == "benchmark" else "solid"),
                             hovertemplate="%{y:.1f}"))
ui.style_fig(fig, "累積淨值（起始 = 100）", "組合淨值指數", "日期", height=440)
ui.show_fig(fig, "bt_equity")
ui.chart_note(period, "指數（起始 100）", "已扣除交易成本；虛線為等權基準")

fig2 = go.Figure()
for sid, (res, _) in results.items():
    dd = -drawdown_series(res.daily["equity"]) * 100
    fig2.add_trace(go.Scatter(x=dd.index, y=dd, name=STRATEGY_LABELS[sid],
                              line=dict(width=2, color=ui.STRATEGY_COLORS[sid],
                                        dash="dot" if sid == "benchmark" else "solid"),
                              hovertemplate="%{y:.2f}%"))
ui.style_fig(fig2, "回撤（距前高跌幅）", "回撤（%）", "日期", height=340)
ui.show_fig(fig2, "bt_dd")
ui.chart_note(period, "%", "0 表示創新高；越低代表從高點跌得越深")

# ---- 持倉與交易 ----
st.subheader("持倉與交易明細")
sid = st.segmented_control("選擇策略", list(STRATEGY_LABELS), format_func=STRATEGY_LABELS.get,
                           default="momentum", required=True)
res, m = results[sid]
pos = pd.DataFrame(list(res.daily["positions"]), index=res.daily.index).fillna(0)
weights = pos.div(res.daily["equity"], axis=0) * 100
monthly = weights.resample("ME").last().reindex(columns=list(master.index), fill_value=0)
fig3 = go.Figure(go.Heatmap(
    z=monthly.T.values, x=monthly.index, y=[fund_label(master, f) for f in monthly.columns],
    colorscale=[[0, "#f4f7fb"], [0.5, "#6da7ec"], [1, "#104281"]], zmin=0, zmax=100,
    colorbar=dict(title="權重 %", thickness=12), xgap=2, ygap=2,
    hovertemplate="%{y}<br>%{x|%Y-%m}<br>月底權重 %{z:.1f}%<extra></extra>"))
ui.style_fig(fig3, f"{STRATEGY_LABELS[sid]}：每月底持倉權重", "", "月份", height=420, legend=False)
fig3.update_layout(hovermode="closest")
fig3.update_yaxes(autorange="reversed")
ui.show_fig(fig3, "bt_heat")
ui.chart_note(period, "% 組合淨值", "顏色越深權重越高；空白欄代表該月全數現金")

ui.cards([("交易筆數", f"{len(res.trades):,}", None),
          ("總交易成本", f"{m['total_cost']:,.0f} 元", f"占初始資金 {m['total_cost'] / config.INITIAL_CAPITAL:.2%}"),
          ("訊號次數", f"{len(res.signals)}", "每月一次"),
          ("期末現金", f"{res.daily['cash'].iloc[-1]:,.0f} 元", None)])

tab1, tab2 = st.tabs(["交易紀錄", "每月訊號"])
with tab1:
    tr = res.trades.copy()
    fsel = st.multiselect("篩選基金", list(master.index), format_func=lambda f: fund_label(master, f), key="bt_tr_f")
    if fsel:
        tr = tr[tr["fund_id"].isin(fsel)]
    st.dataframe(tr, hide_index=True, column_config={
        "signal_date": st.column_config.DateColumn("訊號日", format="YYYY-MM-DD"),
        "exec_date": st.column_config.DateColumn("執行日", format="YYYY-MM-DD"),
        "fund_id": "基金", "side": "買／賣",
        "amount": st.column_config.NumberColumn("成交金額（元）", format="%,.0f"),
        "units": st.column_config.NumberColumn("單位數", format="%.4f"),
        "price": st.column_config.NumberColumn("成交 NAV", format="%.4f"),
        "cost": st.column_config.NumberColumn("成本（元）", format="%,.2f"),
    })
with tab2:
    st.dataframe(res.signals, hide_index=True, column_config={
        "signal_date": st.column_config.DateColumn("訊號日", format="YYYY-MM-DD"),
        "exec_date": st.column_config.DateColumn("執行日", format="YYYY-MM-DD"),
        "targets": "目標持倉", "n_holdings": st.column_config.NumberColumn("檔數", format="%d")})

# ---- 儲存 ----
st.subheader("執行並儲存回測")
st.caption("把四組回測（含參數 config_id、逐日淨值、交易明細）寫入 SQLite。相同參數重用 config_id，回測紀錄每次新增。")
if st.button("執行並儲存回測", type="primary"):
    conn = repo.connect()
    try:
        ids = save_backtests(conn, results)
    finally:
        conn.close()
    st.success("已儲存：" + "、".join(f"{STRATEGY_LABELS[k]} run_id={v}" for k, v in ids.items()))

conn = repo.connect()
try:
    runs = repo.list_backtest_runs(conn)
finally:
    conn.close()
if len(runs):
    runs["策略"] = runs["strategy_id"].map(STRATEGY_LABELS)
    met = runs["metrics_json"].apply(json.loads)
    runs["累積報酬"] = met.apply(lambda x: x["cumulative_return"] * 100)
    runs["最大回撤"] = met.apply(lambda x: x["max_drawdown"] * 100)
    st.dataframe(runs[["run_id", "策略", "config_id", "params_json", "start_date", "end_date", "累積報酬", "最大回撤",
                       "created_at"]], hide_index=True, column_config={
        "params_json": "參數", "累積報酬": st.column_config.NumberColumn(format="%.2f%%"),
        "最大回撤": st.column_config.NumberColumn(format="%.2f%%"), "created_at": "建立時間"})
    st.caption("比較不同回測時，請確認 config_id 相同，避免混用不同參數版本的結果。")

ui.meaning(
    ["在這組模擬資料、這組規則與成本假設下，依當時訊號持有的歷史結果", "不同策略的換手率與成本差異"],
    ["策略在未來或真實基金上一定有效（只有一條模擬路徑）", "回測勝出的策略是最好的策略——換一個種子結果可能不同",
     "真實基金可以用隔日 NAV 申贖（實務有申購截止時間、贖回 T+N 等限制）"],
)
