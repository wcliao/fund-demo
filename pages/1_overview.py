"""基金總覽：白話試算、走勢比較、詳細數字表（可排序、篩選）。"""
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from services.fund_service import overview_table, plain_summary
from ui import components as ui
from ui.data import eval_date, fund_label, get_data, hist

master, _ = get_data()
nav = hist()
d = eval_date()
start, end = f"{nav.index[0]:%Y-%m-%d}", f"{d:%Y-%m-%d}"
years = (len(nav) - 1) / 252

ui.page_header("基金總覽", "如果當初買了這 10 檔基金，現在會怎樣？一路上會經歷多大的起伏？",
               f"每日淨值（{start} ～ {end}，約 {years:.1f} 年）、基金類型、每年費用。")

# ---- 1. 投入試算 ----
st.subheader("① 如果一開始投入一筆錢…")
c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    amount = st.number_input("投入金額（元）", min_value=1_000, max_value=100_000_000, value=100_000, step=10_000,
                             format="%d")
cats = sorted(master["category"].unique())
with c2:
    sel_cats = st.multiselect("基金類型", cats, default=cats)
with c3:
    sort_opts = {"最後變成多少": ("end_value", False), "途中最大跌幅（小→大）": ("max_drawdown", True),
                 "波動程度（小→大）": ("volatility", True), "每年費用（低→高）": ("expense", True),
                 "基金代碼": (None, True)}
    sort_by = st.selectbox("排序", list(sort_opts))

ps = plain_summary(master, nav, amount)
ps = ps[ps["category"].isin(sel_cats)]
col, asc = sort_opts[sort_by]
ps = ps.sort_values(col, ascending=asc) if col else ps.sort_index()


def money(x: float) -> str:
    return f"{x / 10_000:,.1f} 萬" if amount >= 10_000 else f"{x:,.0f}"


items = []
for fid, r in ps.iterrows():
    cls = "up" if r.total_return >= 0 else "down"
    items.append(dict(
        name=f"{fid} {r['name']}", level=r.risk, tag=f"{r.category}｜{r.scenario}",
        headline=f'{money(amount)} → <span class="{cls}">{money(r.end_value)}</span>'
                 f'（<span class="{cls}">{r.total_return:+.0%}</span>）',
        lines=[("途中最低曾剩", f"{money(r.low_value)}（{r.low_date:%Y/%m}）"),
               ("從高點最多跌掉", f"{r.max_drawdown:.0%}"),
               ("一年常見起伏", f"±{r.volatility:.0%}"),
               ("每年費用", f"{r.expense:.1%}")],
    ))
ui.fund_cards(items)
ui.plain(f"每張卡片都是「{start} 投入 {amount:,.0f} 元，放到 {end}」的結果。"
         "<b>途中最低曾剩</b>：這段期間帳戶最難看的時候剩多少錢；"
         "<b>從高點最多跌掉</b>：從最賺的時候一路跌到谷底，跌掉幾成（專業名詞「最大回撤」）；"
         "<b>一年常見起伏</b>：一年之內上下這個幅度很平常（專業名詞「年化波動率」）；"
         "<b>風險等級</b>依起伏分為低（&lt; 8%）、中（&lt; 20%）、高（≥ 20%）。")
st.warning("看最後結果前，先問自己：**如果途中帳戶剩那麼少，我真的抱得住嗎？** "
           "很多人會在最低點賣掉，就拿不到後面的回升。")

with st.expander("🔍 這些數字怎麼算（公式）", expanded=not ui.is_plain()):
    st.latex(r"\text{最後價值}=\text{投入金額}\times\frac{NAV_{末}}{NAV_{初}},\qquad "
             r"\text{途中最低}=\text{投入金額}\times\frac{\min_t NAV_t}{NAV_{初}}")
    st.latex(r"\text{最大跌幅}=\max_t\left(1-\frac{NAV_t}{\max_{s\le t}NAV_s}\right),\qquad "
             r"\text{一年常見起伏}=\mathrm{std}(r_t)\times\sqrt{252}")
    st.caption("NAV 為每單位淨值；r_t 為每日漲跌幅；一年以 252 個交易日計。")

# ---- 2. 走勢比較 ----
st.subheader("② 100 元的旅程：走勢比較")
choices = list(ps.index)
default = [f for f in ["F002", "F003", "F006", "F010"] if f in choices][:ui.MAX_OVERLAY]
picked = st.multiselect("選擇基金（最多 4 檔，避免顏色難以辨識）", choices, default=default,
                        max_selections=ui.MAX_OVERLAY, format_func=lambda f: fund_label(master, f))
log_y = st.toggle("對數座標", value=False, help="對數座標下，相同斜率代表相同的百分比變化，適合比較漲幅差很多的基金。")
fig = go.Figure()
fig.add_hline(y=100, line=dict(color=ui.NEUTRAL, width=1, dash="dot"))
for i, fid in enumerate(picked):
    fig.add_trace(go.Scatter(x=nav.index, y=nav[fid], name=fund_label(master, fid), mode="lines",
                             line=dict(width=2, color=ui.SERIES[i]), hovertemplate="%{y:.1f} 元"))
ui.style_fig(fig, "每日淨值：第一天都是 100 元", "價值（元，起始 100）", "日期", height=440)
if log_y:
    fig.update_yaxes(type="log")
ui.show_fig(fig, "ov_lines")
ui.chart_note(f"{start} ～ {end}", "元（起始 100）", "虛線＝本金 100 元，線在虛線下方代表當時是賠錢的")
all_ps = plain_summary(master, nav)
top, calm = all_ps["end_value"].idxmax(), all_ps["volatility"].idxmin()
ui.plain(f"線越往上越好，但也要看<b>線抖得多厲害</b>。這段期間{all_ps.loc[top, 'name']}最後漲最多"
         f"（{all_ps.loc[top, 'total_return']:+.0%}），但從高點最多跌掉 {all_ps.loc[top, 'max_drawdown']:.0%}；"
         f"{all_ps.loc[calm, 'name']}起伏最小，結果是 {all_ps.loc[calm, 'total_return']:+.0%}。"
         "<b>最賺的和最穩的，通常不是同一檔。</b>")

# ---- 3. 小倍數 ----
st.subheader("③ 10 檔基金的走勢「長相」")
ids = list(master.index)
fig2 = make_subplots(rows=5, cols=2, subplot_titles=[f"{fund_label(master, f)}（{master.loc[f, 'scenario_type']}）"
                                                     for f in ids],
                     shared_xaxes=True, vertical_spacing=.06, horizontal_spacing=.06)
for i, fid in enumerate(ids):
    fig2.add_trace(go.Scatter(x=nav.index, y=nav[fid], mode="lines", name=fid, showlegend=False,
                              line=dict(width=1.6, color=ui.SERIES[0]),
                              hovertemplate=f"{fid}<br>%{{x|%Y-%m-%d}}<br>%{{y:.1f}} 元<extra></extra>"),
                   row=i // 2 + 1, col=i % 2 + 1)
    fig2.add_hline(y=100, line=dict(color=ui.NEUTRAL, width=1, dash="dot"), row=i // 2 + 1, col=i % 2 + 1)
ui.style_fig(fig2, "", "", height=950, legend=False)
fig2.update_layout(hovermode="closest", margin=dict(t=30, l=10, r=10, b=10))
fig2.update_annotations(font_size=11)
ui.show_fig(fig2, "ov_small")
ui.chart_note(f"{start} ～ {end}", "元（起始 100）", "虛線為本金 100 元；各圖刻度不同，請看「形狀」而不是高度")
ui.plain("這 10 種形狀是刻意設計的「考題」：一路漲、一路跌、景氣循環、先跌後漲……"
         "後面三種方法會在這些不同情境下，各自交出不同的答案。")

# ---- 4. 詳細數字表 ----
tbl = overview_table(master, nav)
tbl = tbl[tbl["category"].isin(sel_cats)].sort_index()
pct_cols = ["3M 報酬", "6M 報酬", "12M 報酬", "成立以來報酬", "年化波動率（全期）", "最大回撤（全期）"]
show = tbl.copy()
show[pct_cols + ["expense_ratio"]] = show[pct_cols + ["expense_ratio"]] * 100
helps = {"3M 報酬": "最近 3 個月（63 個交易日）漲跌幅", "6M 報酬": "最近半年（126 個交易日）漲跌幅",
         "12M 報酬": "最近一年（252 個交易日）漲跌幅", "成立以來報酬": "從第一天到評估日的總漲跌幅",
         "年化波動率（全期）": "一年常見起伏幅度", "最大回撤（全期）": "從高點跌到低點的最大跌幅"}
with st.expander("④ 詳細數字表（專業版，可點欄位排序）", expanded=not ui.is_plain()):
    st.dataframe(show, column_config={
        "name": "基金名稱", "category": "類型", "scenario_type": "走勢個性",
        "expense_ratio": st.column_config.NumberColumn("費用率", format="%.1f%%", help="每年費用"),
        "最新 NAV": st.column_config.NumberColumn(format="%.2f", help="評估日的每單位淨值"),
        **{c: st.column_config.NumberColumn(c, format="%.2f%%", help=helps[c]) for c in pct_cols},
    })
    st.latex(r"R_n(t)=\frac{NAV_t}{NAV_{t-n}}-1,\quad n=63\,(3M),\ 126\,(6M),\ 252\,(12M)")
    st.caption(f"評估日 {end}。手機可左右滑動表格。")

ui.meaning(
    ["每檔基金在這段模擬期間「賺多少、晃多大、最慘跌多深、費用多少」", "不同走勢情境長什麼樣子"],
    ["過去賺最多的基金，未來也會賺最多", "股票型和債券型基金可以只用報酬高低比較好壞",
     "這些是真實基金的數據（全部為模擬）"],
)
