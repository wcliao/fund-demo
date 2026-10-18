"""多因子評分頁（規格書 5.C）。"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from database import repository as repo
from services.analysis_service import save_strategy_snapshot, strategy_params
from ui import components as ui
from ui.data import eval_date, fund_label, get_data, multi_factor_at, to_weights

master, _ = get_data()
d = eval_date()
ds = f"{d:%Y-%m-%d}"
KEYS = list(config.FACTORS)
SHORT = {"momentum": "動能", "volatility": "波動率", "sharpe": "Sharpe", "drawdown": "最大回撤", "expense": "費用率"}

ui.page_header("多因子評分 Multi-Factor", "不能只看報酬率，如何同時比較基金的績效、風險及費用？",
               f"評估日 {ds} 往前 252 個交易日的 NAV（需索引 t ≥ 252），以及各基金年度費用率。")

st.subheader("方法與公式")
st.markdown("""
| 因子 | 計算方法（最近 252 日滾動窗） | 預設權重 | 方向 |
| --- | --- | --- | --- |
| 動能 M | 12M 報酬 | 30% | 越高越好 |
| 波動率 V | 日報酬標準差 × √252 | 20% | 越低越好 |
| Sharpe S | (年化平均報酬 − 1%) ／ 年化波動率 | 20% | 越高越好 |
| 最大回撤 D | 窗內高點至其後低點跌幅（正數） | 20% | 越小越好 |
| 費用率 F | 年度費用率 | 10% | 越低越好 |
""")
c1, c2 = st.columns(2)
with c1:
    ui.formula(r"S=\frac{\bar r\times252-r_f}{\mathrm{std}(r)\times\sqrt{252}},\quad r_f=1\%",
               "無風險利率 1% 為 Demo 常數。")
    ui.formula(r"D=\max_t\left(1-\frac{NAV_t}{\max_{s\le t}NAV_s}\right)")
with c2:
    ui.formula(r"\text{FactorScore}=\frac{\text{rank}_{avg}-1}{n-1}\times100",
               "百分位標準化：同一評估日 10 檔一起排名，同分取平均名次；反向因子（V、D、F）先乘 −1。"
               "有效樣本 < 3 時該因子不評分；全部相同給 50 分。")
    ui.formula(r"Score=w_M M+w_V V+w_S S+w_D D+w_F F")
st.warning("**費用重複計入是刻意設計：** 模擬 NAV 已扣除費用，所以動能、Sharpe 已反映費用；費用因子再獨立計分一次，"
           "讓成本差異更明顯。")

st.subheader("可調整參數：因子權重")
raw_w = ui.weight_sliders("fac_w", config.DEFAULT_FACTOR_WEIGHTS, {k: f"{SHORT[k]} 權重" for k in KEYS}, cols=5)
try:
    w = to_weights(raw_w)
except ValueError as e:
    st.error(f"權重設定錯誤：{e}。")
    st.stop()
df, eff = multi_factor_at(ds, tuple(sorted(w.items())))
st.markdown("實際使用權重：" + "、".join(f"**{SHORT[k]} {eff[k]:.0%}**" for k in KEYS))
if any(eff[k] == 0 and w[k] > 0 for k in KEYS):
    st.warning("部分因子有效樣本不足，已不評分並重新正規化其餘權重。")
if df["score"].isna().all():
    st.info("此評估日資料不足（需至少 253 筆資料），請選擇較晚的評估日。")
    st.stop()

# ---- 綜合排名 ----
st.subheader("綜合排名")
board = pd.DataFrame({"排名": df["rank"], "基金": [fund_label(master, f) for f in df.index], "總分": df["score"]},
                     index=df.index)
for k in KEYS:
    board[f"{SHORT[k]}分"] = df[f"s_{k}"]
st.dataframe(board, hide_index=True, column_config={
    "排名": st.column_config.NumberColumn(format="%d"),
    "總分": st.column_config.ProgressColumn(format="%.1f", min_value=0, max_value=100),
    **{f"{SHORT[k]}分": st.column_config.NumberColumn(format="%.1f") for k in KEYS},
})

order = df.index[::-1]
fig = go.Figure()
for i, k in enumerate(KEYS):
    fig.add_trace(go.Bar(y=[fund_label(master, f) for f in order], x=df.loc[order, f"c_{k}"], orientation="h",
                         name=f"{SHORT[k]}（{eff[k]:.0%}）", marker=dict(color=ui.SERIES[i],
                                                                       line=dict(color="#fcfcfb", width=2)),
                         hovertemplate="%{x:.1f} 分"))
fig.update_layout(barmode="stack")
ui.style_fig(fig, "總分拆解：各因子加權貢獻（滿分 100）", "", "分數", height=500)
fig.update_layout(hovermode="y unified")
fig.update_xaxes(range=[0, 100])
ui.show_fig(fig, "mf_stack")
ui.chart_note(f"評估日 {ds}，因子窗 {df.index.size} 檔 × 252 日", "分（0～100）", "每段長度＝因子分數 × 權重")

st.subheader("原始因子值")
rawt = df[KEYS].copy()
rawt.insert(0, "基金", [fund_label(master, f) for f in rawt.index])
for k in ["momentum", "volatility", "drawdown", "expense"]:
    rawt[k] = rawt[k] * 100
st.dataframe(rawt, hide_index=True, column_config={
    "momentum": st.column_config.NumberColumn("12M 報酬", format="%.2f%%"),
    "volatility": st.column_config.NumberColumn("年化波動率", format="%.2f%%"),
    "sharpe": st.column_config.NumberColumn("Sharpe", format="%.2f"),
    "drawdown": st.column_config.NumberColumn("最大回撤", format="%.2f%%"),
    "expense": st.column_config.NumberColumn("費用率", format="%.2f%%"),
})

# ---- 計算範例 ----
st.subheader("具體計算範例：百分位標準化")
c1, c2 = st.columns(2)
with c1:
    fac = st.selectbox("選擇因子", KEYS, format_func=lambda k: config.FACTORS[k][0], index=4)
with c2:
    fid = st.selectbox("選擇基金", list(master.index), index=list(master.index).index("F010"),
                       format_func=lambda f: fund_label(master, f), key="mf_example")
higher = config.FACTORS[fac][1]
vals = df[fac]
signed = vals if higher else -vals
ranks = signed.rank(method="average")
ex = pd.DataFrame({"基金": [fund_label(master, f) for f in vals.index], "原始值": vals,
                   "排名用值": signed, "平均名次": ranks, "分數": df[f"s_{fac}"]}).sort_values("平均名次")
st.dataframe(ex, hide_index=True, column_config={
    "原始值": st.column_config.NumberColumn(format="%.4f"), "排名用值": st.column_config.NumberColumn(format="%.4f"),
    "平均名次": st.column_config.NumberColumn(format="%.1f"), "分數": st.column_config.NumberColumn(format="%.1f")})
n = vals.notna().sum()
st.latex(rf"\text{{{fid} 的{SHORT[fac]}分}}=\frac{{{ranks[fid]:.1f}-1}}{{{n}-1}}\times100={df.loc[fid, f's_{fac}']:.1f}")
st.caption(("此因子越高越好，直接排名。" if higher else "此因子越低越好，先乘以 −1 再排名，使數值最低者得最高分。")
           + " 同分取平均名次。")
st.latex(r"Score_{" + fid + "}=" + "+".join(rf"{eff[k]:.2f}\times{df.loc[fid, f's_{k}']:.1f}" for k in KEYS)
         + rf"={df.loc[fid, 'score']:.1f}")

# ---- F002 vs F010 ----
st.subheader("展示案例：F002 vs F010——走勢幾乎相同，費用不同")
pair = ["F002", "F010"]
fig2 = go.Figure()
for i, f in enumerate(pair):
    fig2.add_trace(go.Bar(x=[SHORT[k] for k in KEYS], y=[df.loc[f, f"s_{k}"] for k in KEYS],
                          name=fund_label(master, f), marker_color=ui.SERIES[i],
                          marker_line=dict(color="#fcfcfb", width=2),
                          text=[f"{df.loc[f, f's_{k}']:.0f}" for k in KEYS], textposition="outside",
                          hovertemplate="%{y:.1f} 分"))
ui.style_fig(fig2, "因子分數比較", "因子分數（0～100）", "因子", height=380)
fig2.update_yaxes(range=[0, 115])
ui.show_fig(fig2, "mf_pair")
ui.chart_note(f"評估日 {ds}", "分", "F010 與 F002 共用同一組隨機衝擊，差異只來自費用率（2.5% vs 1.5%）")
ui.cards([(fund_label(master, f), f"{df.loc[f, 'score']:.1f} 分",
           f"排名第 {int(df.loc[f, 'rank'])}；費用率 {df.loc[f, 'expense']:.1%}；12M {df.loc[f, 'momentum']:.1%}")
          for f in pair])

with st.expander("💾 儲存本次計算結果至資料庫"):
    st.caption("拖拉權重只在記憶體計算；按下儲存才寫入。相同參數會重用同一個 config_id。")
    if st.button("儲存結果", key="mf_save", type="primary"):
        conn = repo.connect()
        try:
            cid, n_saved = save_strategy_snapshot(conn, "multi_factor", strategy_params("multi_factor", fac_w=w), d, df)
        finally:
            conn.close()
        st.success(f"已儲存 {n_saved} 筆結果，config_id = {cid}，評估日 {ds}。")

ui.meaning(
    ["在同一組 10 檔示範樣本中，綜合歷史績效、風險、成本後的相對排序", "每個因子對總分的貢獻"],
    ["高分基金未來一定較好", "分數是絕對品質——百分位分數只代表在這 10 檔中的相對位置",
     "跨資產類別（股票 vs 債券）排名具投資合理性"],
)
