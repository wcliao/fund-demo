"""基金量化策略 Demo — Streamlit 主入口（Dashboard + 導覽）。執行：streamlit run app.py"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

import config
from services.analysis_service import eval_date_options
from services.fund_service import plain_summary
from simulation.generate_funds import data_fingerprint
from ui import components as ui
from ui.data import (backtests, fund_label, get_data, ma_frame_for, ma_snapshot_at, momentum_at, multi_factor_at,
                     preset_test, session_weights)

st.set_page_config(page_title="基金量化策略 Demo", page_icon="📊", layout="wide",
                   initial_sidebar_state="auto")


def key_points(master, nav) -> None:
    """30 秒看懂：從資料即時算出的 4 個重點。"""
    ps = plain_summary(master, nav)
    years = (len(nav) - 1) / config.TRADING_DAYS
    best = ps["end_value"].idxmax()
    calm = ps["volatility"].idxmin()
    gap = (ps.loc["F002", "end_value"] - ps.loc["F010", "end_value"]) * 1000  # 每投入 10 萬元
    ds = f"{nav.index[-1]:%Y-%m-%d}"
    mom_w, fac_w = session_weights()
    m1 = momentum_at(ds, mom_w).index[0]
    f1 = multi_factor_at(ds, fac_w)[0].index[0]
    n_bull = int((ma_snapshot_at(ds)["state"] == "多頭排列").sum())

    ui.cards([
        (f"💰 賺最多：{ps.loc[best, 'name']}", f"100 元 → {ps.loc[best, 'end_value']:.0f} 元",
         f"但途中曾從高點跌掉 {ps.loc[best, 'max_drawdown']:.0%}，坐雲霄飛車的人不一定撐得住"),
        (f"🛡️ 最平穩：{ps.loc[calm, 'name']}", f"100 元 → {ps.loc[calm, 'end_value']:.0f} 元",
         "上下起伏最小，但平穩不等於會賺錢"),
        ("🧾 費用的影響：F002 vs F010", f"每 10 萬少賺 {gap:,.0f} 元",
         f"兩檔走勢一模一樣，只差每年費用 1%，{years:.0f} 年下來的差距"),
        ("🧭 三種方法，三種答案", f"{master.loc[m1, 'name']} vs {master.loc[f1, 'name']}" if m1 != f1
         else master.loc[m1, "name"],
         ("動能第一名與綜合評分第一名不同" if m1 != f1 else "這次兩種方法第一名相同，但其餘排名不同")
         + f"；目前 {n_bull} 檔處於上升趨勢"),
    ])


def _holdings(targets: str) -> set[str]:
    return set() if targets == "全數現金" else {t.split()[0] for t in targets.split(", ")}


def trading_rules(master, nav) -> None:
    """三種方法實際怎麼進出：共通流程、各方法規則、取自回測的實例。"""
    st.header("三種方法實際怎麼「進出」？")
    st.markdown("三種方法用的是**同一套買賣流程**，差別只在「每個月要持有哪幾檔」怎麼挑。")
    flow = [("月底檢查", "每月最後一個交易日收盤後，用「當天以前」的資料算出新名單；月中不動作"),
            ("隔天成交", "下一個交易日用當天淨值買賣，不偷看未來"),
            ("調回等權", "不在名單的賣掉、新進名單的買進；持股沒變也會調回每檔一樣多"),
            ("收手續費", "每筆買賣（含第一次買進）收成交金額的 0.2%")]
    cols = st.columns(4)
    for i, (t, d) in enumerate(flow):
        with cols[i]:
            st.markdown(f'<div class="card step"><div class="n">{i + 1}</div><div><b>{t}</b>'
                        f'<div class="d" style="font-size:.85rem;color:#52514e">{d}</div></div></div>',
                        unsafe_allow_html=True)
            st.write("")

    st.markdown("""
| 方法 | 什麼時候買進（留在名單） | 什麼時候賣出 | 會不會全部轉現金 |
| --- | --- | --- | --- |
| 📈 動能 | 動能分數**前 3 名**，各 1/3 | 掉出前 3 名 | 不會，永遠持有 3 檔 |
| 〰️ 均線 | 月底處於**多頭排列**的基金全部買，平均分配（0～10 檔） | 月底已不是多頭排列 | **會**，沒有任何一檔符合時全數轉現金 |
| 🧮 多因子 | 綜合總分**前 3 名**，各 1/3 | 掉出前 3 名 | 不會，永遠持有 3 檔 |
""")

    mom_w, fac_w = session_weights()
    results = backtests(mom_w, fac_w)
    names = {"momentum": "📈 動能", "moving_average": "〰️ 均線", "multi_factor": "🧮 多因子"}
    rows = []
    for sid, label in names.items():
        sig = results[sid][0].signals
        first = sig.iloc[0]
        prev, swap, n_swap = _holdings(first["targets"]), None, 0
        for _, r in sig.iloc[1:].iterrows():
            cur = _holdings(r["targets"])
            if cur != prev:
                n_swap += 1
                if swap is None:
                    swap = (r, sorted(prev - cur), sorted(cur - prev))
            prev = cur
        swap_txt = "—"
        if swap:
            r, out, inn = swap
            swap_txt = (f"{r['signal_date']:%Y/%m/%d} 月底 → {r['exec_date']:%m/%d} "
                        + ("賣 " + "、".join(out) if out else "") + ("，" if out and inn else "")
                        + ("買 " + "、".join(inn) if inn else ""))
        rows.append({"方法": label,
                     "第一次買進": f"{first['exec_date']:%Y/%m/%d}：{first['targets']}",
                     "第一次換股": swap_txt,
                     "換股月數": f"{n_swap} / {len(sig)}",
                     "平均持有檔數": f"{sig['n_holdings'].mean():.1f}",
                     "全現金月數": int((sig['n_holdings'] == 0).sum())})
    st.markdown("**實際例子**（取自回測紀錄，使用策略頁目前的權重）")
    st.dataframe(rows, hide_index=True)

    # 均線：交叉當天 vs 實際成交
    f = ma_frame_for("F004")
    sig = results["moving_average"][0].signals
    lag_rows = []
    for d, r in f.dropna(subset=["event"]).iterrows():
        nxt = sig[sig["signal_date"] >= d]
        if nxt.empty:
            continue
        ex = nxt.iloc[0]["exec_date"]
        before = sig[sig["signal_date"] < d]
        was_held = bool(len(before)) and "F004" in _holdings(before.iloc[-1]["targets"])
        now_held = "F004" in _holdings(nxt.iloc[0]["targets"])
        if now_held and not was_held:
            action = "買進"
        elif was_held and not now_held:
            action = "賣出"
        else:
            action = "已持有，不動" if now_held else "未持有，不動"
        lag_rows.append({"F004 交叉事件": f"{d:%Y/%m/%d} {r['event']}",
                         "月底檢查後": f"{ex:%Y/%m/%d} {action}",
                         "晚了幾個交易日": nav.index.get_loc(ex) - nav.index.get_loc(d),
                         "這段期間淨值變化": f"{nav.loc[ex, 'F004'] / nav.loc[d, 'F004'] - 1:+.1%}"})

    st.subheader("兩個容易誤會的地方")
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("#### ① 均線不是「交叉當天」就買賣")
        st.markdown("回測只在**月底**檢查狀態，所以交叉發生後要等到月底、再隔一天才成交。"
                    "均線本身已經慢半拍，再加上等月底，**落後是兩層**。")
        if lag_rows:
            st.dataframe(lag_rows, hide_index=True)
            st.caption("「未持有，不動」：淨值先跌破 SMA200 時狀態已轉為「混合」，在更早的月底就賣掉了；"
                       "所以實際出場有時比死亡交叉更早。買進則必須同時滿足 NAV 與 SMA60 都在 SMA200 之上。")
    with c2, st.container(border=True):
        st.markdown("#### ② 動能、多因子永遠「滿倉」")
        st.markdown("就算 10 檔全部在跌，也會買「跌最少的 3 檔」。這兩種方法只回答**誰相對比較好**，"
                    "不回答**現在該不該進場**；三種方法中只有均線有「全部轉現金」的出場機制。")
        st.markdown("另外，每月都調回等權重會產生許多小額交易，"
                    "這是換手率與手續費偏高的主要原因（見「回測比較」頁）。")
    ui.plain("可以把三種方法想成三位基金經理人，<b>每個月底開一次會</b>決定下個月持有哪些基金，隔天下單。"
             "動能經理人只挑最近跑最快的 3 檔；多因子經理人看綜合成績挑 3 檔；"
             "均線經理人只買「大方向往上」的基金，一檔都沒有就全部抱現金。"
             "他們都<b>只能看當天以前的資料</b>，不能偷看未來。")
    ui.formula(r"\text{目標金額}_i=k\cdot w_i\cdot V,\qquad \text{手續費}=0.2\%\times|\text{目標金額}_i-\text{現有金額}_i|",
               "V 為成交前的總資產，w_i 為目標權重（3 檔時各 1/3），k 是扣掉手續費後的縮放係數，讓現金不會變成負數。")


def home() -> None:
    master, nav = get_data()
    ui.page_header(
        "基金量化策略 Demo",
        "能不能先用歷史資料驗證一套買賣規則，確認有效後，未來就照著這套規則買賣？",
    )

    st.header("量化分析怎麼用在買賣？")
    st.markdown("量化分析的核心是：**把買賣決策寫成明確規則 → 用歷史資料檢驗 → 通過檢驗才照規則執行**。"
                "不靠感覺，每一筆決策都能說出原因。")
    flow = [("寫成規則", "例：「每月底買最近漲最多的 3 檔」"),
            ("歷史回測", "假設過去照規則操作，結果如何（含手續費）"),
            ("樣本外驗證", "換一段沒看過的期間、換一組資料，還有效嗎？"),
            ("照規則執行", "每月底用最新資料跑規則，隔天依名單買賣"),
            ("追蹤檢討", "實際結果和回測差太多，就檢討或停用")]
    st.markdown('<div class="card-grid flow-grid">' + "".join(
        f'<div class="card step"><div class="n">{i + 1}</div><div><b>{t}</b>'
        f'<div class="d" style="font-size:.85rem;color:#52514e">{d}</div></div></div>'
        for i, (t, d) in enumerate(flow)) + "</div>", unsafe_allow_html=True)
    st.markdown("""
| 步驟 | 本系統對應頁面 | 狀態 |
| --- | --- | --- |
| 1. 寫成規則 | 動能策略、均線策略、多因子評分 | ✅ 已示範 |
| 2. 歷史回測 | 回測比較 | ✅ 已示範 |
| 3. 樣本外驗證 | 回測比較 →「方法驗證」 | ✅ 已示範（模擬資料） |
| 4. 照規則執行 | 側邊欄評估日選最後一天＝本月名單 | ⚠️ 僅示範流程 |
| 5. 追蹤檢討 | — | ⬜ 未包含 |
""")
    pt = preset_test()
    best = pt.index[0]
    ui.cards([
        ("回測：動能策略", f"{backtests(*session_weights())['momentum'][1]['cumulative_return']:+.0%}",
         "照規則操作約 4 年的累積報酬，看起來很好"),
        ("但是：前段最佳的權重組合", best, f"到後段驗證期掉到第 {pt.loc[best, 'out_rank']} 名（共 {len(pt)} 組）"),
        ("結論", "回測好 ≠ 未來好", "一定要經過第 3 步樣本外驗證"),
    ])
    st.warning("本系統的基金與淨值都是**模擬資料**，所以只能示範「驗證流程」怎麼做，**不能證明任何方法在真實市場有效**。"
               "要用在實際買賣，必須換成真實基金淨值，重新跑完第 2、3 步。")

    st.header("30 秒看懂這組資料")
    key_points(master, nav)
    ui.plain("挑基金就像挑車子。只看「最高時速」（報酬率）不夠，還要看「穩不穩」（風險）、"
             "「耗不耗油」（費用），以及「現在是上坡還是下坡」（趨勢）。三種量化方法分別從不同面向，"
             "把這些<b>寫成數字與一致的規則</b>，再交給回測檢驗。")

    st.header("三種方法，用一句話說明")
    c1, c2, c3 = st.columns(3)
    blocks = [
        (c1, "📈 動能策略", "看誰「最近跑得快」",
         "像看賽跑選手最近幾圈的成績：過去 3 個月、半年、一年漲最多的排前面。",
         "簡單直覺，跟上強勢基金", "跑得快的可能突然跌倒（反轉）；完全不看風險",
         r"Score=0.2R_{3M}+0.3R_{6M}+0.5R_{12M}"),
        (c2, "〰️ 均線策略", "看「大方向」是上坡還是下坡",
         "像看「過去 60 天」與「過去 200 天」的平均氣溫來判斷季節，過濾掉每天的冷熱變化。",
         "過濾雜訊，避開長期下跌", "總是慢半拍（訊號落後）；盤整時容易來回誤判",
         r"SMA_n=\frac{1}{n}\sum_{i=0}^{n-1}NAV_{t-i}"),
        (c3, "🧮 多因子評分", "看「綜合成績單」",
         "像選模範生不只看數學：報酬、穩定度、風險報酬比、最慘跌幅、費用，五科加權算總分。",
         "兼顧報酬、風險與成本", "分數只是這 10 檔之間的相對排名，不保證未來",
         r"Score=0.3M+0.2V+0.2S+0.2D+0.1F"),
    ]
    for col, title, one, story, pro, con, latex in blocks:
        with col, st.container(border=True):
            st.markdown(f"#### {title}")
            st.markdown(f"**{one}**")
            st.markdown(story)
            st.markdown(f"✅ **優點：** {pro}  \n⚠️ **盲點：** {con}")
            ui.formula(latex)

    trading_rules(master, nav)

    st.header("為什麼不能只看報酬率？")
    ps = plain_summary(master, nav)
    fig = go.Figure(go.Scatter(
        x=ps["volatility"] * 100, y=ps["total_return"] * 100, mode="markers+text", text=list(ps.index),
        textposition="top center",
        marker=dict(size=ps["expense"] * 600 + 8, color=ui.SERIES[0], opacity=.85, line=dict(color="#fcfcfb", width=2)),
        customdata=[[fund_label(master, f), r.end_value, r.max_drawdown * 100, r.expense * 100]
                    for f, r in ps.iterrows()],
        hovertemplate="%{customdata[0]}<br>100 元 → %{customdata[1]:.0f} 元（%{y:+.1f}%）"
                      "<br>一年常見起伏 ±%{x:.1f}%<br>最大跌幅 %{customdata[2]:.1f}%<br>費用率 %{customdata[3]:.1f}%"
                      "<extra></extra>",
    ))
    fig.add_hline(y=0, line=dict(color=ui.NEUTRAL, width=1, dash="dot"))
    ui.style_fig(fig, "5 年總報酬 vs 波動程度（點越大＝費用越高）", "5 年總報酬（%）",
                 "波動程度：一年常見起伏幅度（%）", legend=False)
    fig.update_layout(hovermode="closest")
    ui.show_fig(fig, "home_scatter")
    ui.chart_note(f"{nav.index[0]:%Y-%m-%d} ～ {nav.index[-1]:%Y-%m-%d}", "%",
                  "滑鼠移到點上可看細節；虛線以下代表 5 年後賠錢")
    ui.plain("<b>越往上</b>＝賺越多；<b>越往右</b>＝漲跌越劇烈、心臟要越大顆。"
             "左上角是「又賺又穩」的理想位置，右下角是「又跌又晃」的最差位置。"
             "你會發現賺最多的基金都在右邊——<b>高報酬通常伴隨高波動</b>，這就是只看報酬率會漏掉的事。")
    ui.formula(r"\text{波動程度}=\mathrm{std}(r_t)\times\sqrt{252},\qquad r_t=\frac{NAV_t}{NAV_{t-1}}-1",
               "每日漲跌幅的標準差換算成一年；數值 20% 大約代表一年內上下 20% 的起伏很常見。")

    st.header("系統怎麼運作？")
    steps = [("準備資料", "電腦產生 10 檔虛構基金、5 年每天的淨值（不是真實基金）"),
             ("檢查資料", "確認沒有缺漏、錯誤，走勢符合設計"),
             ("三種方法計算", "動能排名、均線趨勢、多因子總分"),
             ("解釋結果", "每個數字附上公式、代入範例與白話說明"),
             ("歷史驗證", "假設當時照規則買賣，後來結果如何（含手續費）"),
             ("結論與限制", "方法能說明什麼、不能保證什麼")]
    cols = st.columns(3)
    for i, (t, d) in enumerate(steps):
        with cols[i % 3]:
            st.markdown(f'<div class="card step"><div class="n">{i + 1}</div><div><b>{t}</b>'
                        f'<div class="d" style="font-size:.85rem;color:#52514e">{d}</div></div></div>',
                        unsafe_allow_html=True)
            st.write("")

    st.header("10 檔虛構基金一覽")
    ui.cards([
        ("基金數", f"{len(master)} 檔", "名稱與走勢皆為設計"),
        ("資料期間", f"{nav.index[0]:%Y/%m} ～ {nav.index[-1]:%Y/%m}", f"{len(nav):,} 個交易日"),
        ("起始淨值", "每檔 100 元", "方便直接比較"),
        ("可重現", f"種子 {config.SEED}", f"資料指紋 {data_fingerprint(nav)}"),
    ])
    tbl = ps[["name", "category", "scenario", "end_value", "max_drawdown", "risk", "expense"]].copy()
    tbl["max_drawdown"] *= 100
    tbl["expense"] *= 100
    st.dataframe(tbl, column_config={
        "name": "基金名稱", "category": "類型", "scenario": "走勢個性",
        "end_value": st.column_config.NumberColumn("100 元變成", format="%.0f 元",
                                                   help="第一天投入 100 元，最後一天的價值"),
        "max_drawdown": st.column_config.NumberColumn("最大跌幅", format="%.0f%%",
                                                      help="從最高點跌到後來最低點，最多跌掉幾 %"),
        "risk": st.column_config.TextColumn("風險等級", help="依一年常見起伏：低 < 8%、中 < 20%、高 ≥ 20%"),
        "expense": st.column_config.NumberColumn("每年費用", format="%.1f%%", help="基金每年收取的管理等費用"),
    })
    st.caption("想看更多細節（金額試算、走勢圖），請到「基金總覽」頁。")

    st.header("常見問題")
    faqs = [
        ("這些基金和數據是真的嗎？",
         "不是。10 檔基金的名稱、走勢都是電腦依設定產生的模擬資料，目的是讓三種方法的差異容易看出來。"
         "所以這裡的任何數字都<b>不代表真實基金的表現</b>。"),
        ("我可以照著排名買基金嗎？",
         "不行。這是教學與技術展示，不是投資建議。排名只代表「在這組假資料、這套規則下」的結果；"
         "真實投資還要考慮你的目標、期間、風險承受度，並應諮詢合格顧問。"),
        ("為什麼要用假資料？",
         "假資料可以「設計」出特定走勢（例如先跌後漲、長期衰退），讓每種方法的優缺點清楚呈現；"
         "而且固定種子每次產生一樣的資料，方便檢查計算是否正確。"),
        ("「量化」是什麼意思？",
         "把判斷標準寫成明確的公式與規則，讓電腦一致地計算，而不是靠感覺。好處是可重複、可檢查；"
         "缺點是規則只會照過去的資料運作，遇到沒見過的狀況不一定有效。"),
        ("回測賺最多的方法就是最好的嗎？",
         "不一定。回測只是「假設過去照規則操作」的結果，這裡只有一條模擬路徑，換一組資料結果可能完全不同。"
         "回測的價值在於了解方法的<b>風險、成本與限制</b>，而不是預測未來。"),
    ]
    for q, a in faqs:
        with st.expander(f"❓ {q}"):
            st.markdown(a, unsafe_allow_html=True)

    st.header("最後要記住的事")
    st.markdown("""
| 方法 | 可以回答 | 不能保證 |
| --- | --- | --- |
| 動能 | 過去哪些基金比較強 | 未來一定繼續漲 |
| 均線 | 目前是不是在上升趨勢 | 訊號一定即時、準確 |
| 多因子 | 綜合報酬、風險、成本後怎麼排序 | 高分基金未來一定比較好 |
""")
    st.info("同一批資料，用不同方法看，會得到不同答案。重要的不是哪個方法「最準」，"
            "而是**每個結果都能說清楚怎麼來的、有什麼限制**。")


def sidebar() -> None:
    _, nav = get_data()
    opts = eval_date_options(nav)
    labels = [d.strftime("%Y-%m-%d") for d in opts]
    if "eval_date" not in st.session_state:
        st.session_state["eval_date"] = labels[-1]
    if "explain_mode" not in st.session_state:
        st.session_state["explain_mode"] = ui.EXPLAIN_MODES[0]
    with st.sidebar:
        st.markdown("### ⚙️ 全域設定")
        st.radio("說明方式", ui.EXPLAIN_MODES, key="explain_mode", horizontal=True,
                 help="白話版：公式收進「看公式」折疊區，適合一般讀者；專業版：公式全部展開。")
        st.selectbox("評估日", labels, key="eval_date",
                     help="策略頁面只使用此日（含）以前的資料計算。選項為每月最後交易日與資料最後一日。")
        st.caption("回測固定使用全期資料，與評估日無關。")
        st.divider()
        st.caption(config.DISCLAIMER)


ui.setup_page()
pages = {
    "總覽": [
        st.Page(home, title="首頁 Dashboard", icon="🏠", default=True),
        st.Page("pages/1_overview.py", title="基金總覽", icon="📋", url_path="overview"),
    ],
    "策略": [
        st.Page("pages/2_momentum.py", title="動能策略", icon="📈", url_path="momentum"),
        st.Page("pages/3_moving_average.py", title="均線策略", icon="〰️", url_path="moving-average"),
        st.Page("pages/4_multi_factor.py", title="多因子評分", icon="🧮", url_path="multi-factor"),
        st.Page("pages/5_fund_detail.py", title="基金詳細分析", icon="🔎", url_path="fund-detail"),
    ],
    "驗證與說明": [
        st.Page("pages/6_backtest.py", title="回測比較", icon="🧪", url_path="backtest"),
        st.Page("pages/7_methodology.py", title="方法與資料說明", icon="📘", url_path="methodology"),
        st.Page("pages/8_data_admin.py", title="模擬資料管理", icon="🗄️", url_path="data-admin"),
    ],
}
nav_page = st.navigation(pages)
sidebar()
nav_page.run()
