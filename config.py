"""全域常數與模擬情境參數（規格書 v2 第四章、附錄 A）。"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "fund_demo.db"

# ---- 模擬資料 ----
SEED = 42
START_DATE = "2021-01-04"
N_DAYS = 1260
INITIAL_NAV = 100.0
TRADING_DAYS = 252
CURRENCY = "TWD"
DATA_SOURCE = "SYNTHETIC"

# ---- 策略參數 ----
RISK_FREE = 0.01
MOMENTUM_WINDOWS = {"3M": 63, "6M": 126, "12M": 252}
DEFAULT_MOMENTUM_WEIGHTS = {"3M": 0.2, "6M": 0.3, "12M": 0.5}
SMA_SHORT = 60
SMA_LONG = 200
FACTOR_WINDOW = 252
MIN_FACTOR_SAMPLES = 3

# 因子代碼 → (中文名稱, 越高越好?)
FACTORS = {
    "momentum": ("動能 M（12M 報酬）", True),
    "volatility": ("波動率 V", False),
    "sharpe": ("Sharpe S", True),
    "drawdown": ("最大回撤 D", False),
    "expense": ("費用率 F", False),
}
DEFAULT_FACTOR_WEIGHTS = {
    "momentum": 0.3,
    "volatility": 0.2,
    "sharpe": 0.2,
    "drawdown": 0.2,
    "expense": 0.1,
}

# ---- 回測 ----
INITIAL_CAPITAL = 1_000_000.0
COST_RATE = 0.002
TOP_N = 3
WARMUP_INDEX = 252  # 訊號日索引需 >= 252（至少 253 筆資料）

DISCLAIMER = "本系統僅為量化教學與技術展示，所有基金、數據與績效均為模擬（SYNTHETIC），不代表真實基金績效或投資建議。"

# ---- 附錄 A：10 檔虛構基金情境 ----
# phases: (起始索引, 結束索引, 年化 μ, 年化 σ)，索引含起訖；μ 為扣除費用後的淨值漂移。
# shock_source：共用另一檔基金的亂數序列（F010 → F002）。
FUNDS = [
    dict(fund_id="F001", name="穩健成長基金", category="股票型", expense_ratio=0.012,
         scenario_type="緩慢上漲、低波動", purpose="動能中等、風險分數高",
         phases=[(0, 1259, 0.08, 0.10)]),
    dict(fund_id="F002", name="科技成長基金", category="股票型", expense_ratio=0.015,
         scenario_type="高報酬、高波動", purpose="動能高但風險較大",
         phases=[(0, 1259, 0.18, 0.28)]),
    dict(fund_id="F003", name="債券收益基金", category="債券型", expense_ratio=0.006,
         scenario_type="低報酬、低波動", purpose="低風險型基金",
         phases=[(0, 1259, 0.03, 0.04)]),
    dict(fund_id="F004", name="景氣循環基金", category="股票型", expense_ratio=0.015,
         scenario_type="明顯週期性漲跌", purpose="均線交叉訊號",
         phases=[(0, 251, 0.25, 0.18), (252, 503, -0.20, 0.18), (504, 755, 0.25, 0.18),
                 (756, 1007, -0.20, 0.18), (1008, 1259, 0.25, 0.18)]),
    dict(fund_id="F005", name="新興市場基金", category="股票型", expense_ratio=0.018,
         scenario_type="高波動、較大回撤", purpose="風險因子測試",
         phases=[(0, 629, 0.12, 0.30), (630, 881, -0.25, 0.30), (882, 1259, 0.10, 0.30)]),
    dict(fund_id="F006", name="價值投資基金", category="股票型", expense_ratio=0.014,
         scenario_type="前期下跌、近期回升", purpose="短期與長期動能不同",
         phases=[(0, 1133, -0.10, 0.16), (1134, 1259, 0.35, 0.16)]),
    dict(fund_id="F007", name="全球平衡基金", category="平衡型", expense_ratio=0.010,
         scenario_type="中等報酬、中低波動", purpose="綜合評分比較",
         phases=[(0, 1259, 0.07, 0.09)]),
    dict(fund_id="F008", name="長期衰退基金", category="股票型", expense_ratio=0.013,
         scenario_type="持續下降", purpose="動能及均線偏弱",
         phases=[(0, 1007, -0.10, 0.15), (1008, 1259, -0.15, 0.15)]),
    dict(fund_id="F009", name="趨勢反轉基金", category="股票型", expense_ratio=0.016,
         scenario_type="長期下跌後強力反彈", purpose="均線落後及短期動能",
         phases=[(0, 1007, -0.15, 0.22), (1008, 1259, 0.40, 0.25)]),
    dict(fund_id="F010", name="高費用成長基金", category="股票型", expense_ratio=0.025,
         scenario_type="與 F002 共用隨機衝擊，費用更高", purpose="展示成本因子的作用",
         phases=[(0, 1259, 0.17, 0.28)], shock_source="F002"),
]

FUND_IDS = [f["fund_id"] for f in FUNDS]
