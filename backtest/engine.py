"""簡易回測引擎（規格書第六章）。

時點：t 日收盤後只用索引 ≤ t 的 NAV 產生訊號，於 t+1 日以 NAV_{t+1} 成交。
成本：0.2% × 每筆成交金額（買、賣、初始建倉都收）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

import config

Selector = Callable[[pd.DataFrame], dict[str, float]]


@dataclass
class BacktestResult:
    daily: pd.DataFrame  # index nav_date；equity、cash、positions(dict fund→市值)
    trades: pd.DataFrame
    signals: pd.DataFrame  # signal_date、exec_date、targets
    params: dict = field(default_factory=dict)


def signal_indices(dates: pd.DatetimeIndex, min_index: int = config.WARMUP_INDEX) -> list[int]:
    """每月最後一個交易日，且索引 ≥ min_index。"""
    s = pd.Series(np.arange(len(dates)), index=dates)
    month_last = s.groupby([dates.year, dates.month]).max().to_numpy()
    return [int(i) for i in month_last if i >= min_index]


def rebalance(units: dict[str, float], cash: float, prices: pd.Series, targets: dict[str, float],
              cost_rate: float) -> tuple[dict[str, float], float, list[dict]]:
    """把組合調整到目標權重，成本從現金扣除，並使交易後現金不為負。

    以 k 縮放目標金額：target_i = k · w_i · V，求 k 使
    V − Σ target_i − c · Σ|target_i − h_i| = V · (1 − Σw)（未投資部分留現金）。
    c 很小時此迭代為收縮映射，數次即收斂。
    """
    holdings = {f: u * prices[f] for f, u in units.items()}
    value = cash + sum(holdings.values())
    funds = sorted(set(holdings) | set(targets))
    w = {f: targets.get(f, 0.0) for f in funds}
    reserved = value * (1 - sum(w.values()))
    k = 1.0
    for _ in range(100 if sum(w.values()) > 0 else 0):
        turnover = sum(abs(k * w[f] * value - holdings.get(f, 0.0)) for f in funds)
        k_new = (value - reserved - cost_rate * turnover) / value / max(sum(w.values()), 1e-12)
        if abs(k_new - k) < 1e-14:
            k = k_new
            break
        k = k_new
    k = max(k, 0.0) * (1 - 1e-12) if sum(w.values()) > 0 else 0.0

    trades = []
    new_units = {}
    total_cost = 0.0
    for f in funds:
        target_val = k * w[f] * value
        diff = target_val - holdings.get(f, 0.0)
        if abs(diff) > 1e-9:
            cost = cost_rate * abs(diff)
            total_cost += cost
            trades.append(dict(fund_id=f, side="買進" if diff > 0 else "賣出", amount=abs(diff),
                               units=abs(diff) / prices[f], price=float(prices[f]), cost=cost))
        if target_val > 1e-9:
            new_units[f] = target_val / prices[f]
    new_cash = value - sum(u * prices[f] for f, u in new_units.items()) - total_cost
    if new_cash < 0:
        if new_cash < -1e-6:
            raise RuntimeError(f"現金為負：{new_cash}")
        new_cash = 0.0
    return new_units, new_cash, trades


def run_backtest(nav_wide: pd.DataFrame, selector: Selector, cost_rate: float = config.COST_RATE,
                 initial_capital: float = config.INITIAL_CAPITAL, min_index: int = config.WARMUP_INDEX,
                 params: dict | None = None) -> BacktestResult:
    dates = nav_wide.index
    sig_idx = signal_indices(dates, min_index)
    if not sig_idx:
        raise ValueError("資料不足以產生任何訊號")
    exec_plan = {}
    sig_rows = []
    for s in sig_idx:
        if s + 1 >= len(dates):
            continue  # 最後一日的訊號不執行
        targets = selector(nav_wide.iloc[: s + 1])  # 只傳入 t 以前（含）的資料
        exec_plan[s + 1] = (s, targets)
        sig_rows.append(dict(signal_date=dates[s], exec_date=dates[s + 1],
                             targets=", ".join(f"{k} {v:.0%}" for k, v in targets.items()) or "全數現金",
                             n_holdings=len(targets)))

    units: dict[str, float] = {}
    cash = initial_capital
    daily_rows, trade_rows = [], []
    for i in range(sig_idx[0], len(dates)):
        prices = nav_wide.iloc[i]
        if i in exec_plan:
            s, targets = exec_plan[i]
            units, cash, trades = rebalance(units, cash, prices, targets, cost_rate)
            for t in trades:
                trade_rows.append(dict(signal_date=dates[s], exec_date=dates[i], **t))
        positions = {f: u * prices[f] for f, u in units.items()}
        daily_rows.append(dict(nav_date=dates[i], equity=cash + sum(positions.values()), cash=cash,
                               positions=positions))
    daily = pd.DataFrame(daily_rows).set_index("nav_date")
    trades = pd.DataFrame(trade_rows, columns=["signal_date", "exec_date", "fund_id", "side", "amount",
                                               "units", "price", "cost"])
    return BacktestResult(daily=daily, trades=trades, signals=pd.DataFrame(sig_rows), params=params or {})
