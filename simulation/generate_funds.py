"""可重現的模擬基金資料（GBM + 分段市場階段，規格書 4.2、4.3）。"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

import config


def trading_calendar(start: str = config.START_DATE, n_days: int = config.N_DAYS) -> pd.DatetimeIndex:
    """模擬交易日：只排除週末，不考慮假日。"""
    return pd.bdate_range(start, periods=n_days)


def draw_shocks(funds: list[dict], seed: int = config.SEED, n_days: int = config.N_DAYS) -> dict[str, np.ndarray]:
    """每檔基金用 SeedSequence(seed).spawn(n) 的第 i 個子種子抽 n_days-1 個 Z_t。

    基金順序固定，改某一檔的參數不會改變其他基金的亂數。
    """
    children = np.random.SeedSequence(seed).spawn(len(funds))
    return {
        f["fund_id"]: np.random.default_rng(child).standard_normal(n_days - 1)
        for f, child in zip(funds, children)
    }


def phase_arrays(phases: list[tuple], n_days: int) -> tuple[np.ndarray, np.ndarray]:
    """展開每個交易日（t=1..n_days-1）所屬階段的 μ、σ。"""
    mu = np.full(n_days, np.nan)
    sigma = np.full(n_days, np.nan)
    for start, end, m, s in phases:
        mu[start : end + 1] = m
        sigma[start : end + 1] = s
    if np.isnan(mu[1:]).any():
        raise ValueError("情境階段未涵蓋所有交易日")
    return mu[1:], sigma[1:]


def simulate_path(phases: list[tuple], z: np.ndarray, initial_nav: float = config.INITIAL_NAV) -> np.ndarray:
    """NAV_t = NAV_{t-1} × exp[(μ − σ²/2)Δt + σ√Δt · Z_t]。"""
    n_days = len(z) + 1
    mu, sigma = phase_arrays(phases, n_days)
    dt = 1.0 / config.TRADING_DAYS
    log_ret = (mu - sigma**2 / 2) * dt + sigma * np.sqrt(dt) * z
    return initial_nav * np.exp(np.concatenate([[0.0], np.cumsum(log_ret)]))


def generate_funds(funds: list[dict] | None = None, seed: int = config.SEED,
                   n_days: int = config.N_DAYS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """回傳 (fund_master, nav_wide)。nav_wide：index 為日期、欄位為 fund_id。"""
    funds = funds or config.FUNDS
    dates = trading_calendar(n_days=n_days)
    shocks = draw_shocks(funds, seed, n_days)

    navs = {}
    for f in funds:
        z = shocks[f.get("shock_source") or f["fund_id"]]
        navs[f["fund_id"]] = simulate_path(f["phases"], z)
    nav_wide = pd.DataFrame(navs, index=dates)
    nav_wide.index.name = "nav_date"

    master = pd.DataFrame(
        [
            dict(fund_id=f["fund_id"], name=f["name"], category=f["category"], currency=config.CURRENCY,
                 expense_ratio=f["expense_ratio"], scenario_type=f["scenario_type"], purpose=f["purpose"],
                 data_source=config.DATA_SOURCE)
            for f in funds
        ]
    ).set_index("fund_id")
    return master, nav_wide


def data_fingerprint(nav_wide: pd.DataFrame) -> str:
    """資料指紋（SHA-256 前 12 碼），用來展示相同種子產生完全相同資料。"""
    payload = nav_wide.round(10).to_csv().encode()
    return hashlib.sha256(payload).hexdigest()[:12]
