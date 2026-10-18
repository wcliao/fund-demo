"""方法與資料說明：名詞、公式、範例、假設、限制。"""
import streamlit as st

import config
from database.repository import SCHEMA_PATH
from ui import components as ui

ui.page_header("方法與資料說明", "每一個數字從哪裡來？用了什麼假設？有哪些限制？")

t1, t2, t3, t4, t5 = st.tabs(["📘 名詞", "📐 公式總表", "🧾 資料與假設", "⚠️ 限制", "🗃️ 資料庫"])

with t1:
    st.markdown("""
| 名詞 | 說明 |
| --- | --- |
| NAV | 基金每單位淨值；本系統為已扣除費用後的模擬值 |
| 交易日 | 本系統以「只排除週末」的工作日模擬，1 年 ≈ 252 日 |
| 3M／6M／12M | 以 63／126／252 個交易日近似 |
| SMA | 簡單移動平均：最近 n 日 NAV 的平均 |
| 多頭／空頭排列 | 每日判斷的**狀態**，可持續很多天 |
| 黃金／死亡交叉 | 短期均線向上／向下穿越長期均線的**當日事件** |
| 年化波動率 | 日報酬標準差 × √252，衡量上下震盪幅度 |
| Sharpe | 每承擔一單位波動所得到的超額報酬 |
| 最大回撤 | 從最高點到其後最低點的最大跌幅（以正數表示） |
| 百分位分數 | 在同一組基金中的相對位置，0 = 最差、100 = 最佳 |
| 未來函數（look-ahead bias） | 在決策時點使用了當時尚無法取得的資料 |
| 換手率 | 一年內成交金額相對平均資產的倍數 |
""")

with t2:
    st.markdown("#### 模擬資料（GBM + 市場階段）")
    ui.formula(r"NAV_t=NAV_{t-1}\times\exp\left[\left(\mu_p-\frac{\sigma_p^2}{2}\right)\Delta t+\sigma_p\sqrt{\Delta t}\,Z_t\right],\ \Delta t=\frac{1}{252}",
               "μ_p、σ_p 為第 p 階段的年化漂移與波動；Z_t 為標準常態亂數（SeedSequence(42) 子種子）。")
    st.markdown("#### 報酬與風險")
    ui.formula(r"r_t=\frac{NAV_t}{NAV_{t-1}}-1,\qquad R_n(t)=\frac{NAV_t}{NAV_{t-n}}-1")
    ui.formula(r"\sigma=\mathrm{std}(r,\mathrm{ddof}=1)\sqrt{252},\qquad S=\frac{\bar r\cdot252-r_f}{\sigma},\ r_f=1\%")
    ui.formula(r"MDD=\max_t\left(1-\frac{NAV_t}{\max_{s\le t}NAV_s}\right)")
    st.markdown("#### 動能")
    ui.formula(r"Score=w_{3M}R_{3M}+w_{6M}R_{6M}+w_{12M}R_{12M},\quad \sum w=1")
    st.markdown("#### 均線")
    ui.formula(r"SMA_n(t)=\frac{1}{n}\sum_{i=0}^{n-1}NAV_{t-i}")
    st.markdown("#### 多因子")
    ui.formula(r"\text{FactorScore}=\frac{\text{rank}_{avg}-1}{n-1}\times100,\qquad Score=\sum_k w_k\,\text{FactorScore}_k")
    st.markdown("#### 回測")
    ui.formula(r"\text{成本}=0.2\%\times|\Delta\text{金額}|,\qquad \text{年化報酬}=(1+R_{累積})^{252/N}-1")
    st.markdown("#### 共通規則")
    st.markdown("""
- **資料不足**：所需歷史不足時指標為空白、標示「資料不足」，不納入排名。
- **同分**：排名同分時依基金代碼升冪；百分位標準化同分取平均名次。
- **權重**：必須 ≥ 0，自動正規化為總和 100%；全為 0 時不計算。
- **有效樣本不足**：某因子有效樣本 < 3 檔時不評分，其餘權重重新正規化。
""")

with t3:
    st.markdown(f"""
| 項目 | 設定 |
| --- | --- |
| 資料來源 | `{config.DATA_SOURCE}`（程式產生，不連線任何行情 API） |
| 基金 | 10 檔虛構基金，名稱與情境皆為設計 |
| 期間 | `pd.bdate_range("{config.START_DATE}", periods={config.N_DAYS})` |
| 初始 NAV | {config.INITIAL_NAV:.0f}；幣別 {config.CURRENCY}；配息 0 |
| 隨機種子 | {config.SEED}；每檔基金使用獨立子種子 |
| F010 | 與 F002 共用相同 Z_t，μ 低 1.0%（費用差），兩者差異只來自費用 |
| 費用 | NAV 已扣除費用；回測不再扣管理費；多因子另將費用率當獨立因子（刻意重複計入） |
| 無風險利率 | {config.RISK_FREE:.0%}（Demo 常數） |
| 回測 | 月底訊號、隔日 NAV 成交、成本 {config.COST_RATE:.1%}、現金報酬 0 |
""")
    st.markdown("**情境參數（附錄 A）**")
    rows = []
    for f in config.FUNDS:
        ph = "；".join(f"{a}–{b}：μ {m:+.0%} / σ {s:.0%}" for a, b, m, s in f["phases"])
        rows.append({"代碼": f["fund_id"], "名稱": f["name"], "費用率": f"{f['expense_ratio']:.1%}", "階段（索引區間）": ph,
                     "備註": f"共用 {f['shock_source']} 的亂數" if f.get("shock_source") else ""})
    st.dataframe(rows, hide_index=True)
    st.caption("若情境驗證失敗，只能調整這張表的參數，不得修改策略或回測結果。")

with t4:
    st.markdown("""
| 策略 | 可以回答 | 無法單獨保證 |
| --- | --- | --- |
| 動能 | 過去哪些基金較強 | 未來一定持續上漲 |
| 均線 | 目前淨值是否符合趨勢條件 | 訊號一定即時或準確 |
| 多因子 | 綜合歷史績效、風險、成本後如何排序 | 高分基金未來一定較好 |

**模型與資料限制**
- GBM 是合成價格的演示模型，真實基金報酬不服從 GBM，存在肥尾、波動群聚、基金間相關性等。
- 10 檔基金的亂數彼此獨立（F010 除外），真實市場中基金常高度相關。
- 只有一條模擬路徑；回測結果高度依賴這條路徑，不具統計顯著性。
- 不處理外幣匯率、配息再投資、基金休市、不同級別、申購手續費與贖回 T+N。
- 隔日 NAV 成交是研究假設，不是真實基金申贖計價承諾。
- 情境是事先設計的，策略在這組資料上的表現部分反映了情境設計本身。
""")
    st.error(config.DISCLAIMER)

with t5:
    st.markdown("""
| 資料表 | 用途 |
| --- | --- |
| `fund_master` | 基金基本資料與模擬特徵 |
| `fund_nav` | 每日歷史淨值（PK：fund_id, nav_date） |
| `strategy_config` | 策略參數版本（params_hash 去重，只新增不覆寫） |
| `strategy_result` | 各策略計算結果（PK：config_id, fund_id, eval_date） |
| `backtest_run` | 回測執行與摘要績效（關聯 config_id） |
| `backtest_daily` | 回測組合逐日淨值、現金、持倉 |
| `backtest_trades` | 回測交易明細 |
""")
    st.code(SCHEMA_PATH.read_text(encoding="utf-8"), language="sql")
