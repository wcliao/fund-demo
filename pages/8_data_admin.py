"""模擬資料管理：產生、重建、瀏覽資料，顯示資料檢查結果。"""
import pandas as pd
import streamlit as st

import config
from database import repository as repo
from database.init_db import build_database
from simulation.generate_funds import data_fingerprint, generate_funds
from simulation.validate import check_data, check_scenarios
from ui import components as ui
from ui.data import clear_cache, fund_label, get_data

master, nav = get_data()

ui.page_header("模擬資料管理", "資料從哪裡來？是否完整？相同種子是否產生完全相同的資料？")

conn = repo.connect()
try:
    counts = repo.table_counts(conn)
finally:
    conn.close()

ui.cards([
    ("資料庫", config.DB_PATH.name, str(config.DB_PATH.parent)),
    ("資料指紋", data_fingerprint(nav), f"種子 {config.SEED}"),
    ("基金／NAV 筆數", f"{counts['fund_master']}／{counts['fund_nav']:,}", None),
    ("已存策略結果", f"{counts['strategy_result']:,}", f"參數版本 {counts['strategy_config']} 組"),
    ("已存回測", f"{counts['backtest_run']}", f"交易明細 {counts['backtest_trades']:,} 筆"),
])

st.subheader("資料檢查（規格 4.4）")
st.caption("任一項失敗即停止後續計算。")
data_checks = check_data(master, nav)
st.dataframe(pd.DataFrame([{"結果": "✅ 通過" if c.passed else "❌ 失敗", "檢查項目": c.item, "說明": c.detail}
                           for c in data_checks]), hide_index=True)

st.subheader("情境驗證（規格 4.5）")
st.caption("確認設計的走勢真的出現在資料中；失敗時只能調整情境參數，不可修改策略或回測結果。")
st.dataframe(pd.DataFrame([{"結果": "✅ 通過" if c.passed else "❌ 失敗", "檢查項目": c.item, "實際數值": c.detail}
                           for c in check_scenarios(nav)]), hide_index=True)

st.subheader("可重現性驗證")
st.markdown("用指定種子在記憶體中重新產生資料，與資料庫中的資料比對指紋（不寫入資料庫）。")
c1, c2 = st.columns([1, 2])
with c1:
    seed = st.number_input("種子", min_value=0, max_value=2**31 - 1, value=config.SEED, step=1)
with c2:
    st.write("")
    if st.button("產生並比對"):
        _, test_nav = generate_funds(seed=int(seed))
        fp = data_fingerprint(test_nav)
        if fp == data_fingerprint(nav):
            st.success(f"種子 {seed} 產生的資料指紋 {fp} 與資料庫完全相同。")
        else:
            st.warning(f"種子 {seed} 的資料指紋 {fp} 與資料庫（{data_fingerprint(nav)}）不同——不同種子產生不同資料。")

st.subheader("重建資料庫")
st.caption("清空 7 張資料表（含已儲存的策略結果與回測紀錄），以種子 42 重新產生模擬資料。")
confirm = st.checkbox("我了解重建會刪除所有已儲存的結果")
if st.button("重建資料庫", type="primary", disabled=not confirm):
    build_database()
    clear_cache()
    st.success("已重建資料庫。")
    st.rerun()

st.subheader("瀏覽原始資料")
c1, c2 = st.columns([2, 1])
with c1:
    fid = st.selectbox("基金", list(master.index), format_func=lambda f: fund_label(master, f), key="admin_fund")
with c2:
    n_rows = st.selectbox("顯示筆數", [20, 100, 500, len(nav)], format_func=lambda n: "全部" if n == len(nav) else f"最近 {n} 筆")
st.dataframe(master.loc[[fid]].T.rename(columns={fid: "值"}).astype(str))
raw = nav[[fid]].rename(columns={fid: "NAV"}).iloc[-n_rows:][::-1]
raw["日報酬"] = (nav[fid] / nav[fid].shift(1) - 1).reindex(raw.index) * 100
st.dataframe(raw, column_config={"NAV": st.column_config.NumberColumn(format="%.4f"),
                                 "日報酬": st.column_config.NumberColumn(format="%+.3f%%")})
st.download_button("下載全部 NAV（CSV）", nav.to_csv().encode("utf-8-sig"), file_name="fund_nav_synthetic.csv",
                   mime="text/csv")
