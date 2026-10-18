"""方法驗證：前段設計／後段驗證、參數挑選的樣本外檢驗、換種子重跑的穩定度。"""
from __future__ import annotations

import pandas as pd

from backtest.metrics import compute_metrics
from services.analysis_service import STRATEGY_LABELS, run_all_backtests, run_strategy_backtest
from simulation.generate_funds import generate_funds

SPLIT_DATE = pd.Timestamp("2023-12-31")  # 前段（設計）：~2023-12；後段（驗證）：2024-01~

# 動能權重候選（3M, 6M, 12M），用來示範「在前段挑最佳參數，到後段還是最佳嗎？」
MOMENTUM_PRESETS = {
    "重短期 60/30/10": {"3M": 0.6, "6M": 0.3, "12M": 0.1},
    "均衡 34/33/33": {"3M": 0.34, "6M": 0.33, "12M": 0.33},
    "預設 20/30/50": {"3M": 0.2, "6M": 0.3, "12M": 0.5},
    "重長期 0/20/80": {"3M": 0.0, "6M": 0.2, "12M": 0.8},
    "只看 12M 0/0/100": {"3M": 0.0, "6M": 0.0, "12M": 1.0},
}


def segment_metrics(equity: pd.Series, trades: pd.DataFrame, start=None, end=None) -> dict:
    """截取一段期間的績效，以該段第一天淨值為起點重新計算。"""
    eq = equity.loc[start:end]
    tr = trades
    if len(trades):
        mask = pd.Series(True, index=trades.index)
        if start is not None:
            mask &= trades["exec_date"] > pd.Timestamp(start)
        if end is not None:
            mask &= trades["exec_date"] <= pd.Timestamp(end)
        tr = trades[mask]
    return compute_metrics(eq, tr, initial_capital=float(eq.iloc[0]))


def split_table(results: dict, split: pd.Timestamp = SPLIT_DATE) -> pd.DataFrame:
    """各策略的前段／後段績效。"""
    rows = []
    for sid, (res, _) in results.items():
        eq, tr = res.daily["equity"], res.trades
        a = segment_metrics(eq, tr, end=split)
        b = segment_metrics(eq, tr, start=split)
        rows.append({"strategy": sid, "in_return": a["annual_return"], "in_sharpe": a["sharpe"],
                     "in_mdd": a["max_drawdown"], "out_return": b["annual_return"], "out_sharpe": b["sharpe"],
                     "out_mdd": b["max_drawdown"]})
    df = pd.DataFrame(rows).set_index("strategy")
    df["in_rank"] = df["in_sharpe"].rank(ascending=False).astype(int)
    df["out_rank"] = df["out_sharpe"].rank(ascending=False).astype(int)
    return df


def momentum_preset_test(nav: pd.DataFrame, expense: pd.Series, split: pd.Timestamp = SPLIT_DATE) -> pd.DataFrame:
    """每組動能權重各跑一次回測，比較前段與後段的 Sharpe 排名。"""
    rows = []
    for name, w in MOMENTUM_PRESETS.items():
        res, _ = run_strategy_backtest(nav, expense, "momentum", mom_w=w)
        eq, tr = res.daily["equity"], res.trades
        a = segment_metrics(eq, tr, end=split)
        b = segment_metrics(eq, tr, start=split)
        rows.append({"preset": name, "in_return": a["annual_return"], "in_sharpe": a["sharpe"],
                     "out_return": b["annual_return"], "out_sharpe": b["sharpe"]})
    df = pd.DataFrame(rows).set_index("preset")
    df["in_rank"] = df["in_sharpe"].rank(ascending=False).astype(int)
    df["out_rank"] = df["out_sharpe"].rank(ascending=False).astype(int)
    return df.sort_values("in_rank")


def seed_robustness(seeds: list[int], mom_w: dict | None = None, fac_w: dict | None = None) -> pd.DataFrame:
    """換不同亂數種子重新產生資料（情境設定不變），每個種子跑四組回測。"""
    rows = []
    for s in seeds:
        master, nav = generate_funds(seed=s)
        results = run_all_backtests(nav, master["expense_ratio"], mom_w, fac_w)
        bench = results["benchmark"][1]["cumulative_return"]
        for sid, (_, m) in results.items():
            rows.append({"seed": s, "strategy": sid, "cumulative_return": m["cumulative_return"],
                         "annual_return": m["annual_return"], "max_drawdown": m["max_drawdown"],
                         "sharpe": m["sharpe"], "beat_benchmark": m["cumulative_return"] > bench})
    return pd.DataFrame(rows)


def seed_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("strategy")
    out = pd.DataFrame({
        "median_return": g["cumulative_return"].median(),
        "worst_return": g["cumulative_return"].min(),
        "best_return": g["cumulative_return"].max(),
        "median_mdd": g["max_drawdown"].median(),
        "beat_ratio": g["beat_benchmark"].mean(),
        "top_ratio": df.loc[df.groupby("seed")["cumulative_return"].idxmax()]["strategy"].value_counts()
        .reindex(g.size().index, fill_value=0) / df["seed"].nunique(),
    })
    return out.reindex([s for s in STRATEGY_LABELS if s in out.index])

