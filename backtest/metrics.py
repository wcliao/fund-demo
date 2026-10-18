"""回測績效指標（規格書 6.4）。"""
from __future__ import annotations

import pandas as pd

import config
from strategies.common import annualized_volatility, max_drawdown, sharpe_ratio

METRIC_LABELS = {
    "cumulative_return": "累積報酬",
    "annual_return": "年化報酬",
    "annual_volatility": "年化波動率",
    "max_drawdown": "最大回撤",
    "sharpe": "Sharpe",
    "total_cost": "總交易成本（元）",
    "turnover": "年化換手率",
    "final_equity": "期末淨值（元）",
}


def compute_metrics(equity: pd.Series, trades: pd.DataFrame,
                    initial_capital: float = config.INITIAL_CAPITAL) -> dict:
    rets = equity.pct_change().iloc[1:]
    n = len(rets)
    cum = equity.iloc[-1] / initial_capital - 1
    years = n / config.TRADING_DAYS if n else float("nan")
    return dict(
        cumulative_return=float(cum),
        annual_return=float((1 + cum) ** (config.TRADING_DAYS / n) - 1) if n else float("nan"),
        annual_volatility=annualized_volatility(rets),
        max_drawdown=max_drawdown(equity),
        sharpe=sharpe_ratio(rets),
        total_cost=float(trades["cost"].sum()) if len(trades) else 0.0,
        turnover=float(trades["amount"].sum() / equity.mean() / years) if len(trades) and years else 0.0,
        final_equity=float(equity.iloc[-1]),
    )
