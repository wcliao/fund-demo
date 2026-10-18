"""動能策略（規格書 5.A）。"""
from __future__ import annotations

import pandas as pd

import config
from strategies.common import normalize_weights, period_return, rank_desc


def compute_momentum(nav_hist: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.DataFrame:
    """以 nav_hist 最後一筆為評估日 t，只使用 t 以前（含）的資料。

    回傳欄位：R_3M、R_6M、R_12M、c_3M…（加權貢獻）、score、rank、top_driver、status。
    """
    w = normalize_weights(weights or config.DEFAULT_MOMENTUM_WEIGHTS)
    rows = {}
    for fid in nav_hist.columns:
        nav = nav_hist[fid].dropna()
        row = {}
        for label, n in config.MOMENTUM_WINDOWS.items():
            row[f"R_{label}"] = period_return(nav, n)
        contribs = {label: w[label] * row[f"R_{label}"] for label in config.MOMENTUM_WINDOWS}
        for label, c in contribs.items():
            row[f"c_{label}"] = c
        if any(pd.isna(v) for v in contribs.values()):
            row["score"] = float("nan")
            row["top_driver"] = None
            row["status"] = "資料不足"
        else:
            row["score"] = sum(contribs.values())
            row["top_driver"] = max(contribs, key=lambda k: abs(contribs[k]))
            row["status"] = "OK"
        rows[fid] = row
    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index.name = "fund_id"
    df["rank"] = rank_desc(df["score"])
    return df.sort_values(["rank"], na_position="last")


def select_top(nav_hist: pd.DataFrame, weights: dict[str, float] | None = None,
               top_n: int = config.TOP_N) -> dict[str, float]:
    """回測持有規則：動能前 top_n 名等權。"""
    df = compute_momentum(nav_hist, weights).dropna(subset=["score"])
    picks = df.index[:top_n].tolist()
    return {fid: 1 / len(picks) for fid in picks} if picks else {}
