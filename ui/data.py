"""Streamlit 快取包裝：頁面透過這裡取得資料與計算結果。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from services import analysis_service as svc
from services.fund_service import load_data, nav_until
from strategies import momentum, moving_average, multi_factor
from strategies.common import normalize_weights


@st.cache_data(show_spinner="載入模擬資料…")
def get_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    return load_data()


def clear_cache() -> None:
    st.cache_data.clear()


def eval_date() -> pd.Timestamp:
    _, nav = get_data()
    return pd.Timestamp(st.session_state.get("eval_date", nav.index[-1]))


def hist() -> pd.DataFrame:
    _, nav = get_data()
    return nav_until(nav, eval_date())


def to_weights(pct: dict) -> dict:
    """百分比 → 正規化權重；全為 0 時拋出 ValueError。"""
    return normalize_weights({k: float(v) for k, v in pct.items()})


@st.cache_data(show_spinner=False)
def momentum_at(date: str, weights: tuple) -> pd.DataFrame:
    _, nav = get_data()
    return momentum.compute_momentum(nav_until(nav, date), dict(weights))


@st.cache_data(show_spinner=False)
def ma_snapshot_at(date: str) -> pd.DataFrame:
    _, nav = get_data()
    return moving_average.ma_snapshot(nav_until(nav, date))


@st.cache_data(show_spinner=False)
def ma_frame_for(fid: str) -> pd.DataFrame:
    _, nav = get_data()
    return moving_average.ma_frame(nav[fid])


@st.cache_data(show_spinner=False)
def multi_factor_at(date: str, weights: tuple) -> tuple[pd.DataFrame, dict]:
    master, nav = get_data()
    return multi_factor.compute_multi_factor(nav_until(nav, date), master["expense_ratio"], dict(weights))


@st.cache_data(show_spinner="執行回測中…")
def backtests(mom_w: tuple, fac_w: tuple):
    master, nav = get_data()
    return svc.run_all_backtests(nav, master["expense_ratio"], dict(mom_w), dict(fac_w))


@st.cache_data(show_spinner="計算歷史排名…")
def rank_history(mom_w: tuple, fac_w: tuple) -> pd.DataFrame:
    """每個月底的動能與多因子排名（長表）。"""
    master, nav = get_data()
    rows = []
    for d in svc.eval_date_options(nav):
        h = nav_until(nav, d)
        m = momentum.compute_momentum(h, dict(mom_w))
        f, _ = multi_factor.compute_multi_factor(h, master["expense_ratio"], dict(fac_w))
        for fid in nav.columns:
            rows.append(dict(date=d, fund_id=fid, mom_rank=m.loc[fid, "rank"], mom_score=m.loc[fid, "score"],
                             mf_rank=f.loc[fid, "rank"], mf_score=f.loc[fid, "score"]))
    return pd.DataFrame(rows)


def session_weights() -> tuple[tuple, tuple]:
    """目前使用者設定的動能、多因子權重（已正規化，可作為快取鍵）。"""
    ss = st.session_state
    mom = ss.get("mom_w", {k: v * 100 for k, v in config.DEFAULT_MOMENTUM_WEIGHTS.items()})
    fac = ss.get("fac_w", {k: v * 100 for k, v in config.DEFAULT_FACTOR_WEIGHTS.items()})
    try:
        mom_n = to_weights(mom)
    except ValueError:
        mom_n = dict(config.DEFAULT_MOMENTUM_WEIGHTS)
    try:
        fac_n = to_weights(fac)
    except ValueError:
        fac_n = dict(config.DEFAULT_FACTOR_WEIGHTS)
    return tuple(sorted(mom_n.items())), tuple(sorted(fac_n.items()))


def fund_label(master: pd.DataFrame, fid: str) -> str:
    return f"{fid} {master.loc[fid, 'name']}"
