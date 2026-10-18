"""共用計算：報酬、風險指標、權重正規化、百分位標準化、排名（規格書第五章）。"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config


def daily_returns(nav: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    """簡單日報酬 r_t = NAV_t / NAV_{t-1} − 1。"""
    return nav / nav.shift(1) - 1


def period_return(nav: pd.Series, n: int) -> float:
    """R_n = NAV_t / NAV_{t-n} − 1，t 為序列最後一筆；資料不足回傳 NaN。"""
    if len(nav) < n + 1:
        return float("nan")
    return float(nav.iloc[-1] / nav.iloc[-1 - n] - 1)


def annualized_volatility(returns: pd.Series) -> float:
    """std(r, ddof=1) × √252。"""
    r = returns.dropna()
    if len(r) < 2:
        return float("nan")
    return float(r.std(ddof=1) * np.sqrt(config.TRADING_DAYS))


def sharpe_ratio(returns: pd.Series, rf: float = config.RISK_FREE) -> float:
    """(mean(r) × 252 − rf) / (std(r) × √252)。"""
    r = returns.dropna()
    vol = annualized_volatility(r)
    if not np.isfinite(vol) or vol == 0:
        return float("nan")
    return float((r.mean() * config.TRADING_DAYS - rf) / vol)


def max_drawdown(nav: pd.Series) -> float:
    """max_t(1 − NAV_t / max_{s≤t} NAV_s)，以正數表示幅度。"""
    s = pd.Series(nav).dropna()
    if s.empty:
        return float("nan")
    return float((1 - s / s.cummax()).max())


def drawdown_series(nav: pd.Series) -> pd.Series:
    return 1 - nav / nav.cummax()


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """權重需 ≥ 0，自動正規化為總和 1；全部為 0 時報錯。"""
    if any(w < 0 for w in weights.values()):
        raise ValueError("權重不可為負數")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("權重總和必須大於 0")
    return {k: w / total for k, w in weights.items()}


def percentile_score(values: pd.Series, higher_is_better: bool = True,
                     min_samples: int = config.MIN_FACTOR_SAMPLES) -> pd.Series:
    """百分位標準化：(rank_avg − 1) / (n − 1) × 100。

    - 反向因子先乘以 −1；同分取平均名次。
    - 有效樣本 < min_samples：全部回傳 NaN（該因子不評分）。
    - 有效值全部相同：給 50 分。
    """
    v = values.astype(float).replace([np.inf, -np.inf], np.nan)
    valid = v.dropna()
    out = pd.Series(np.nan, index=values.index, dtype=float)
    n = len(valid)
    if n < min_samples:
        return out
    if valid.nunique() == 1:
        out[valid.index] = 50.0
        return out
    signed = valid if higher_is_better else -valid
    rank_avg = signed.rank(method="average")
    out[valid.index] = (rank_avg - 1) / (n - 1) * 100
    return out


def rank_desc(scores: pd.Series) -> pd.Series:
    """由高至低排名；同分依 fund_id 升冪；NaN 不排名。"""
    valid = scores.dropna()
    order = sorted(valid.index, key=lambda fid: (-valid[fid], fid))
    ranks = pd.Series(np.nan, index=scores.index, dtype=float)
    for i, fid in enumerate(order, start=1):
        ranks[fid] = i
    return ranks
