"""基金詳細分析：同一檔基金在三種策略下的判斷。"""
import plotly.graph_objects as go
import streamlit as st

import config
from services.analysis_service import fund_verdict
from ui import components as ui
from ui.data import (eval_date, fund_label, get_data, ma_frame_for, ma_snapshot_at, momentum_at, multi_factor_at,
                     rank_history, session_weights)

master, _ = get_data()
d = eval_date()
ds = f"{d:%Y-%m-%d}"
mom_w, fac_w = session_weights()
SHORT = {"momentum": "動能", "volatility": "波動率", "sharpe": "Sharpe", "drawdown": "最大回撤", "expense": "費用率"}

ui.page_header("基金詳細分析", "同一檔基金，在三種量化方法下的判斷一樣嗎？為什麼？",
               "該基金評估日以前的 NAV、費用率；動能與多因子使用目前在策略頁設定的權重。")

fid = st.selectbox("選擇基金", list(master.index), format_func=lambda f: fund_label(master, f), key="detail_fund")
info = master.loc[fid]
mom = momentum_at(ds, mom_w)
mf, eff = multi_factor_at(ds, fac_w)
ma = ma_snapshot_at(ds)
f = ma_frame_for(fid).loc[:d]

ui.cards([
    ("最新 NAV", f"{f['nav'].iloc[-1]:.2f}", f"評估日 {ds}"),
    ("分類／費用率", f"{info['category']}", f"費用率 {info['expense_ratio']:.1%}"),
    ("動能排名", "—" if mom.loc[fid, "rank"] != mom.loc[fid, "rank"] else f"#{int(mom.loc[fid, 'rank'])}",
     f"分數 {ui.pct(mom.loc[fid, 'score'])}"),
    ("均線狀態", ma.loc[fid, "state"], f"NAV 相對 SMA200 {ui.pct(ma.loc[fid, 'gap_pct'])}"),
    ("多因子排名", "—" if mf.loc[fid, "rank"] != mf.loc[fid, "rank"] else f"#{int(mf.loc[fid, 'rank'])}",
     "總分 —" if mf.loc[fid, "score"] != mf.loc[fid, "score"] else f"總分 {mf.loc[fid, 'score']:.1f}"),
])
st.markdown(f"**情境設定：** {info['scenario_type']}　｜　**展示目的：** {info['purpose']}")

st.subheader("三策略判斷摘要")
for line in fund_verdict(fid, mom, ma, mf):
    st.markdown(f"- {line}")

fig = go.Figure()
fig.add_trace(go.Scatter(x=f.index, y=f["nav"], name="NAV", line=dict(width=1.5, color="#9a9994"),
                         hovertemplate="%{y:.2f}"))
fig.add_trace(go.Scatter(x=f.index, y=f["sma_short"], name="SMA60", line=dict(width=2, color=ui.SERIES[0]),
                         hovertemplate="%{y:.2f}"))
fig.add_trace(go.Scatter(x=f.index, y=f["sma_long"], name="SMA200", line=dict(width=2, color=ui.SERIES[1]),
                         hovertemplate="%{y:.2f}"))
ui.style_fig(fig, f"{fund_label(master, fid)} 淨值與均線", "NAV（TWD／單位）", "日期", height=400)
ui.show_fig(fig, "detail_nav")
ui.chart_note(f"{f.index[0]:%Y-%m-%d} ～ {ds}", "TWD／單位", "均線定義見均線策略頁")

tab1, tab2, tab3, tab4 = st.tabs(["📈 動能", "〰️ 均線", "🧮 多因子", "🕒 歷史排名"])
with tab1:
    row = mom.loc[fid]
    st.latex(r"R_n=\frac{NAV_t}{NAV_{t-n}}-1,\quad Score=\sum w_p R_p")
    if row["status"] == "OK":
        w = dict(mom_w)
        st.latex("Score=" + "+".join(rf"{w[p]:.2f}\times{row[f'R_{p}'] * 100:.2f}\%" for p in config.MOMENTUM_WINDOWS)
                 + rf"={row['score'] * 100:.2f}\%")
        ui.cards([(f"{p} 報酬", ui.pct(row[f"R_{p}"]), f"貢獻 {row[f'c_{p}'] * 100:+.2f} 百分點")
                  for p in config.MOMENTUM_WINDOWS])
    else:
        st.info("資料不足。")
with tab2:
    a = ma.loc[fid]
    st.latex(r"SMA_n(t)=\frac{1}{n}\sum_{i=0}^{n-1}NAV_{t-i}")
    st.markdown(f"狀態：{ui.state_tag(a['state'])}", unsafe_allow_html=True)
    ui.cards([("NAV", f"{a['nav']:.2f}", None), ("SMA60", f"{a['sma_short']:.2f}", None),
              ("SMA200", f"{a['sma_long']:.2f}", None),
              ("交叉次數", f"黃金 {a['n_golden']}／死亡 {a['n_death']}",
               f"最近：{a['last_event_date']:%Y-%m-%d} {a['last_event']}" if a["last_event"] else "無事件")])
with tab3:
    st.latex(r"Score=\sum_k w_k\cdot\frac{\text{rank}_{avg,k}-1}{n-1}\times100")
    if mf.loc[fid, "score"] == mf.loc[fid, "score"]:
        avg = {k: mf[f"s_{k}"].mean() for k in config.FACTORS}
        cats = [SHORT[k] for k in config.FACTORS]
        fig3 = go.Figure()
        fig3.add_trace(go.Scatterpolar(r=[avg[k] for k in config.FACTORS] + [avg["momentum"]], theta=cats + cats[:1],
                                       name="10 檔平均", line=dict(color=ui.NEUTRAL, width=2, dash="dot")))
        fig3.add_trace(go.Scatterpolar(r=[mf.loc[fid, f"s_{k}"] for k in config.FACTORS] + [mf.loc[fid, "s_momentum"]],
                                       theta=cats + cats[:1], name=fid, fill="toself",
                                       line=dict(color=ui.SERIES[0], width=2), fillcolor="rgba(42,120,214,.15)"))
        fig3.update_layout(polar=dict(radialaxis=dict(range=[0, 100], ticksuffix=" 分")), height=400,
                           margin=dict(l=30, r=30, t=40, b=20), meta={"title": "因子分數雷達圖（0～100）"},
                           legend=dict(orientation="h", y=1.08), paper_bgcolor="rgba(0,0,0,0)")
        ui.show_fig(fig3, "detail_radar")
        ui.chart_note(f"評估日 {ds}", "分", "外圈越大越好；虛線為 10 檔平均")
        rows = [(SHORT[k], f"{mf.loc[fid, f's_{k}']:.1f} 分",
                 f"原始值 {mf.loc[fid, k]:.4f}；權重 {eff[k]:.0%}；貢獻 {mf.loc[fid, f'c_{k}']:.1f}")
                for k in config.FACTORS]
        ui.cards(rows)
    else:
        st.info("資料不足。")
with tab4:
    rh = rank_history(mom_w, fac_w)
    rh = rh[rh["fund_id"] == fid]
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(x=rh["date"], y=rh["mom_rank"], name="動能排名", mode="lines+markers",
                              line=dict(width=2, color=ui.SERIES[0], shape="hv"), marker=dict(size=6)))
    fig4.add_trace(go.Scatter(x=rh["date"], y=rh["mf_rank"], name="多因子排名", mode="lines+markers",
                              line=dict(width=2, color=ui.SERIES[2], shape="hv"), marker=dict(size=6)))
    ui.style_fig(fig4, f"{fid} 每月底排名變化（1 = 最佳）", "排名", "訊號日（每月最後交易日）", height=380)
    fig4.update_yaxes(autorange="reversed", dtick=1, range=[10.5, 0.5])
    ui.show_fig(fig4, "detail_rank")
    ui.chart_note(f"{rh['date'].min():%Y-%m-%d} ～ {rh['date'].max():%Y-%m-%d}", "名次（共 10 檔）",
                  "每個點只使用當時以前的資料計算——這也是回測選股的依據")
