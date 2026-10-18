"""均線策略（規格書 5.B）。"""
from __future__ import annotations

import pandas as pd

import config

BULL, BEAR, MIXED, NA = "多頭排列", "空頭排列", "混合／轉換中", "資料不足"
GOLDEN, DEATH = "黃金交叉", "死亡交叉"


def sma(nav: pd.Series, n: int) -> pd.Series:
    """SMA_n(t) = (1/n) Σ_{i=0}^{n-1} NAV_{t-i}；索引 < n−1 為 NaN。"""
    return nav.rolling(window=n, min_periods=n).mean()


def classify_state(nav: float, sma_short: float, sma_long: float) -> str:
    if any(pd.isna(x) for x in (nav, sma_short, sma_long)):
        return NA
    if nav > sma_long and sma_short > sma_long:
        return BULL
    if nav < sma_long and sma_short < sma_long:
        return BEAR
    return MIXED


def detect_crosses(sma_short: pd.Series, sma_long: pd.Series) -> pd.Series:
    """事件只在穿越當日成立；前一日或當日任一均線為 NaN 時不判斷。"""
    s0, l0 = sma_short.shift(1), sma_long.shift(1)
    valid = sma_short.notna() & sma_long.notna() & s0.notna() & l0.notna()
    golden = valid & (s0 <= l0) & (sma_short > sma_long)
    death = valid & (s0 >= l0) & (sma_short < sma_long)
    out = pd.Series(None, index=sma_short.index, dtype=object)
    out[golden] = GOLDEN
    out[death] = DEATH
    return out


def ma_frame(nav: pd.Series, short: int = config.SMA_SHORT, long: int = config.SMA_LONG) -> pd.DataFrame:
    """單一基金的 NAV、SMA、狀態、事件。"""
    df = pd.DataFrame({"nav": nav})
    df["sma_short"] = sma(nav, short)
    df["sma_long"] = sma(nav, long)
    df["state"] = [classify_state(a, b, c) for a, b, c in zip(df["nav"], df["sma_short"], df["sma_long"])]
    df["event"] = detect_crosses(df["sma_short"], df["sma_long"])
    df["gap_pct"] = df["nav"] / df["sma_long"] - 1
    return df


def ma_snapshot(nav_hist: pd.DataFrame, short: int = config.SMA_SHORT, long: int = config.SMA_LONG) -> pd.DataFrame:
    """以 nav_hist 最後一筆為評估日，回傳各基金最新狀態與最近一次交叉事件。"""
    rows = {}
    for fid in nav_hist.columns:
        f = ma_frame(nav_hist[fid].dropna(), short, long)
        last = f.iloc[-1]
        events = f["event"].dropna()
        rows[fid] = dict(
            nav=last["nav"], sma_short=last["sma_short"], sma_long=last["sma_long"],
            gap_pct=last["gap_pct"], state=last["state"],
            last_event=events.iloc[-1] if len(events) else None,
            last_event_date=events.index[-1] if len(events) else None,
            n_golden=int((events == GOLDEN).sum()), n_death=int((events == DEATH).sum()),
        )
    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index.name = "fund_id"
    return df


def select_bull(nav_hist: pd.DataFrame) -> dict[str, float]:
    """回測持有規則：多頭排列者等權，無符合者全數現金。"""
    snap = ma_snapshot(nav_hist)
    picks = snap.index[snap["state"] == BULL].tolist()
    return {fid: 1 / len(picks) for fid in picks} if picks else {}


def state_runs(state: pd.Series) -> list[tuple]:
    """把連續相同狀態壓成區間 [(start, end, state)]，供圖表上色。"""
    runs = []
    if state.empty:
        return runs
    vals = state.to_numpy()
    idx = state.index
    start = 0
    for i in range(1, len(vals) + 1):
        if i == len(vals) or vals[i] != vals[start]:
            runs.append((idx[start], idx[i - 1], vals[start]))
            start = i
    return runs

