"""多因子評分（規格書 5.C）。"""
from __future__ import annotations

import pandas as pd

import config
from strategies.common import (annualized_volatility, daily_returns, max_drawdown, normalize_weights,
                               percentile_score, period_return, rank_desc, sharpe_ratio)


def compute_factors(nav_hist: pd.DataFrame, expense: pd.Series,
                    window: int = config.FACTOR_WINDOW) -> pd.DataFrame:
    """各基金於評估日（nav_hist 最後一筆）的原始因子值；風險因子使用最近 window 日滾動窗。"""
    rows = {}
    for fid in nav_hist.columns:
        nav = nav_hist[fid].dropna()
        if len(nav) < window + 1:
            rows[fid] = dict(momentum=float("nan"), volatility=float("nan"), sharpe=float("nan"),
                             drawdown=float("nan"), expense=float(expense.get(fid, float("nan"))))
            continue
        win = nav.iloc[-(window + 1):]
        r = daily_returns(win).iloc[1:]
        rows[fid] = dict(
            momentum=period_return(nav, window),
            volatility=annualized_volatility(r),
            sharpe=sharpe_ratio(r),
            drawdown=max_drawdown(win),
            expense=float(expense.get(fid, float("nan"))),
        )
    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index.name = "fund_id"
    return df


def score_factors(raw: pd.DataFrame, weights: dict[str, float] | None = None) -> tuple[pd.DataFrame, dict]:
    """百分位標準化 + 加權。

    回傳 (結果表, 實際使用權重)。結果表欄位：s_<因子>（0~100 分）、c_<因子>（加權貢獻）、score、rank。
    有效樣本 < 3 的因子不評分，權重依其餘因子重新正規化。
    """
    w = normalize_weights(weights or config.DEFAULT_FACTOR_WEIGHTS)
    out = pd.DataFrame(index=raw.index)
    usable = {}
    for key, (_, higher) in config.FACTORS.items():
        s = percentile_score(raw[key], higher_is_better=higher)
        out[f"s_{key}"] = s
        if s.notna().any() and w.get(key, 0) > 0:
            usable[key] = w[key]
    eff = normalize_weights(usable) if usable and sum(usable.values()) > 0 else {}
    for key in config.FACTORS:
        out[f"c_{key}"] = out[f"s_{key}"] * eff.get(key, 0.0)
    # 任何有效因子分數缺漏者，總分為 NaN（資料不足）
    cols = [f"s_{k}" for k in eff]
    complete = out[cols].notna().all(axis=1) if cols else pd.Series(False, index=out.index)
    out["score"] = out[[f"c_{k}" for k in eff]].sum(axis=1).where(complete) if eff else float("nan")
    out["rank"] = rank_desc(out["score"])
    effective = {k: eff.get(k, 0.0) for k in config.FACTORS}
    return out.sort_values("rank", na_position="last"), effective


def compute_multi_factor(nav_hist: pd.DataFrame, expense: pd.Series,
                         weights: dict[str, float] | None = None) -> tuple[pd.DataFrame, dict]:
    raw = compute_factors(nav_hist, expense)
    scored, eff = score_factors(raw, weights)
    return raw.join(scored).sort_values("rank", na_position="last"), eff


def select_top(nav_hist: pd.DataFrame, expense: pd.Series, weights: dict[str, float] | None = None,
               top_n: int = config.TOP_N) -> dict[str, float]:
    df, _ = compute_multi_factor(nav_hist, expense, weights)
    picks = df.dropna(subset=["score"]).index[:top_n].tolist()
    return {fid: 1 / len(picks) for fid in picks} if picks else {}
