"""資料檢查（規格書 4.4）與情境驗證（4.5）。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import config
from strategies.common import annualized_volatility, daily_returns, max_drawdown, period_return
from strategies.moving_average import BEAR, DEATH, GOLDEN, ma_frame


@dataclass
class Check:
    item: str
    passed: bool
    detail: str


def check_data(master: pd.DataFrame, nav_wide: pd.DataFrame) -> list[Check]:
    checks = []
    counts = nav_wide.notna().sum()
    checks.append(Check("每檔基金筆數 = %d" % config.N_DAYS, bool((counts == config.N_DAYS).all()),
                        "、".join(f"{k}:{v}" for k, v in counts.items())))
    values = nav_wide.to_numpy(dtype=float)
    finite = bool(np.isfinite(values).all())
    checks.append(Check("NAV 無 NaN／Inf", finite, "全部為有限值" if finite else "發現缺值或無限值"))
    positive = bool((values[np.isfinite(values)] > 0).all())
    checks.append(Check("所有 NAV > 0", positive, f"最小 NAV = {np.nanmin(values):.4f}"))
    idx = nav_wide.index
    checks.append(Check("日期嚴格遞增、無重複", bool(idx.is_monotonic_increasing and idx.is_unique),
                        f"{idx[0].date()} ～ {idx[-1].date()}"))
    checks.append(Check("10 檔基金日期一致", len(nav_wide.columns) == len(config.FUNDS),
                        "寬表格共用同一日期索引"))
    er = master["expense_ratio"]
    ok = bool(er.notna().all() and ((er >= 0) & (er < 0.05)).all())
    checks.append(Check("費用率存在且 0 ≤ 費用率 < 5%", ok,
                        f"範圍 {er.min():.2%} ～ {er.max():.2%}"))
    return checks


def check_scenarios(nav_wide: pd.DataFrame) -> list[Check]:
    rets = daily_returns(nav_wide).iloc[1:]
    vol = rets.apply(annualized_volatility)
    mdd = nav_wide.apply(max_drawdown)
    vol_rank = vol.rank()  # 1 = 最低
    mdd_rank = mdd.rank(ascending=False)  # 1 = 最大
    last = nav_wide.iloc[-1]
    r = lambda fid, n: period_return(nav_wide[fid], n)  # noqa: E731

    checks = []
    checks.append(Check("F001 穩健成長", bool(last["F001"] > 100 and vol_rank["F001"] <= 3),
                        f"期末 NAV {last['F001']:.2f}；波動率 {vol['F001']:.2%}（第 {vol_rank['F001']:.0f} 低）"))
    checks.append(Check("F003 波動最低", bool(vol_rank["F003"] == 1), f"波動率 {vol['F003']:.2%}"))
    ev = ma_frame(nav_wide["F004"])["event"]
    ng, nd = int((ev == GOLDEN).sum()), int((ev == DEATH).sum())
    checks.append(Check("F004 至少 2 次黃金與 2 次死亡交叉", ng >= 2 and nd >= 2, f"黃金 {ng} 次、死亡 {nd} 次"))
    checks.append(Check("F005 最大回撤屬前三大", bool(mdd_rank["F005"] <= 3),
                        f"MDD {mdd['F005']:.2%}（第 {mdd_rank['F005']:.0f} 大）"))
    r3, r12 = r("F006", 63), r("F006", 252)
    checks.append(Check("F006 短期轉強", bool(r3 > 0 and r3 > r12 / 4), f"3M {r3:.2%}、12M {r12:.2%}"))
    st8 = ma_frame(nav_wide["F008"])["state"].iloc[-1]
    checks.append(Check("F008 長期衰退", bool(last["F008"] < 100 and st8 == BEAR),
                        f"期末 NAV {last['F008']:.2f}；狀態 {st8}"))
    nav9 = nav_wide["F009"]
    checks.append(Check("F009 先跌後反彈", bool(nav9.iloc[1007] < 100 and r("F009", 252) > 0),
                        f"第 1007 日 NAV {nav9.iloc[1007]:.2f}；最後 252 日報酬 {r('F009', 252):.2%}"))
    below = bool((nav_wide["F010"].iloc[1:] < nav_wide["F002"].iloc[1:]).all())
    checks.append(Check("F010 每日 NAV 低於 F002", below and r("F010", 252) < r("F002", 252),
                        f"12M：F010 {r('F010', 252):.2%} vs F002 {r('F002', 252):.2%}"))
    return checks
