# 基金量化策略 Demo

以 Python + SQLite + Streamlit 實作的展示型 Prototype，依《[規格書_v2.md](規格書_v2.md)》開發。
用 10 檔**虛構基金**、可重現的**模擬淨值**，呈現動能策略、均線策略、多因子評分三種量化方法，以及不含未來資料的簡易回測。

> ⚠️ 本系統僅為量化教學與技術展示，所有基金、數據與績效均為模擬（SYNTHETIC），不代表真實基金績效或投資建議。

## 安裝與啟動

需要 Python 3.11 以上（開發時使用 3.14）。

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux：.venv/bin/python
.venv/Scripts/python -m streamlit run app.py
```

瀏覽器開啟 <http://localhost:8501>。首次啟動若沒有資料庫，會自動建立 `data/fund_demo.db` 並產生模擬資料。

### 資料重建

- 網頁：「模擬資料管理」頁 → 勾選確認 → 重建資料庫。
- 命令列：`python -m database.init_db --rebuild`

重建會清空 7 張資料表（含已儲存的策略結果與回測），再以種子 42 重新產生，資料指紋應相同。

### 測試

```bash
.venv/Scripts/python -m pytest -q
```

48 個測試涵蓋：報酬率、SMA、交叉事件、波動率、Sharpe、最大回撤、百分位標準化、權重、回測時點與成本、可重現性、F010 < F002、config 版本化、前後段切分與換種子重跑。

## 架構

```
app.py                 Streamlit 入口：首頁 Dashboard、st.navigation、全域評估日
config.py              常數、預設權重、附錄 A 情境參數
simulation/            generate_funds（GBM + 市場階段）、validate（資料檢查 4.4、情境驗證 4.5）
strategies/            common（報酬、風險、標準化、排名）、momentum、moving_average、multi_factor
backtest/              engine（月底訊號、t+1 成交、再平衡、成本）、metrics
database/              schema.sql、repository（存取層）、init_db（建立／重建）
services/              fund_service、analysis_service（串接策略、回測、儲存）、validation_service（方法驗證）——UI 只呼叫這層
ui/                    components（RWD 樣式、公式、說明框、圖表版面）、data（st.cache_data 包裝）
pages/1~8              基金總覽、動能、均線、多因子、基金詳細分析、回測、方法說明、資料管理
tests/                 pytest
```

計算邏輯全部在 `strategies/`、`backtest/`，頁面程式只負責呈現。

## 資料庫 Schema（7 張表）

| 資料表 | 用途 |
| --- | --- |
| `fund_master` | 基金基本資料（費用率、情境） |
| `fund_nav` | 每日 NAV，PK (fund_id, nav_date) |
| `strategy_config` | 參數版本，`params_hash` 去重、只新增不覆寫 |
| `strategy_result` | 策略結果，PK (config_id, fund_id, eval_date) |
| `backtest_run` | 回測執行與摘要績效，關聯 config_id |
| `backtest_daily` | 回測逐日淨值、現金、持倉 |
| `backtest_trades` | 回測交易明細 |

完整 DDL 見 [database/schema.sql](database/schema.sql)。拖拉權重只在記憶體計算；按「儲存結果」或「執行並儲存回測」才寫入。

## 策略公式

| 項目 | 公式 |
| --- | --- |
| 模擬 NAV | $NAV_t=NAV_{t-1}\exp[(\mu_p-\sigma_p^2/2)\Delta t+\sigma_p\sqrt{\Delta t}Z_t]$，Δt = 1/252 |
| 期間報酬 | $R_n=NAV_t/NAV_{t-n}-1$，n = 63／126／252 |
| 動能 | $Score=0.2R_{3M}+0.3R_{6M}+0.5R_{12M}$ |
| 均線 | $SMA_n(t)=\frac1n\sum_{i=0}^{n-1}NAV_{t-i}$；多頭：NAV>SMA200 且 SMA60>SMA200 |
| 波動率 | std(r, ddof=1) × √252（最近 252 日） |
| Sharpe | (mean(r)×252 − 1%) ／ 波動率 |
| 最大回撤 | max(1 − NAV／前高)，正數 |
| 百分位分數 | (平均名次 − 1)／(n − 1) × 100；反向因子先乘 −1 |
| 多因子 | 0.3M + 0.2V + 0.2S + 0.2D + 0.1F |
| 交易成本 | 0.2% × 成交金額（買、賣、建倉都收） |

## 展示操作順序

1. **首頁**：研究問題、報酬 × 風險散佈圖、三策略簡介。
2. **基金總覽**：篩選、排序，比較走勢與 10 檔小倍數圖。
3. **動能策略**：比較 F002 vs F006；調整權重觀察排名變化（權重敏感度表）。
4. **均線策略**：切換 F004、F009，看交叉事件與「訊號落後」表。
5. **多因子評分**：比較 F002 vs F010（走勢相同、費用不同 → 總分不同）。
6. **基金詳細分析**：同一檔基金的三策略判斷、雷達圖、歷史排名。
7. **回測比較**：累積淨值、回撤、持倉熱圖、交易紀錄；可存入資料庫。
   「方法驗證」區塊：前段（~2023/12）設計、後段（2024/01~）驗證，五組動能權重的樣本外排名；換 10～30 組種子重跑的報酬分布。
8. **方法與資料說明**：公式總表、假設、限制、Schema。

側邊欄的「評估日」可切換到任一月底，策略頁只使用該日以前的資料。

## 設計決策（規格未定義或調整之處）

- **情境參數 v2.1 調整**：以原附錄 A 參數生成時，F008 期末呈「多頭排列」，不符情境驗證。依規格只調整情境參數：
  - F008：最後 252 日 μ 由 −10% 改為 −15%。
  - F005：下跌階段由 −35%／35% 改為 −25%／30%（原設定回撤達 84%，過於極端）。
  - 調整後 4.5 情境驗證全部通過，已同步更新規格書附錄 A。
- **再平衡成本**：規格 6.2 的「總值 ÷ (1 + 0.2%)」近似在全換倉時仍可能讓現金為負。改以迭代求縮放係數 k，使 `V − Σ k·wᵢ·V − c·Σ|k·wᵢ·V − hᵢ| = 0`，扣除成本後現金恰好不為負。
- **均線策略存檔**：score 欄位存 NAV 相對 SMA200 偏離，rank 為空；狀態與事件放 details_json。
- **圖表顏色**：類別色固定順序、最多 4 檔疊圖；10 檔全覽改用小倍數圖。
- **頁面檔名**：英文檔名 + `st.Page(title=…)` 中文標題。

## 已知限制

- GBM 不代表真實基金報酬（無肥尾、波動群聚、基金間相關性）。
- 只有一條模擬路徑，回測不具統計顯著性；情境是事先設計的，策略結果部分反映情境本身。
- 不處理匯率、配息再投資、休市、級別、申購手續費、贖回 T+N。
- 隔日 NAV 成交為研究假設。
- 無登入、權限、排程或交易 API。
