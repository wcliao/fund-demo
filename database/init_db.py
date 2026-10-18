"""初始化／重建 SQLite 資料庫。可直接執行：python -m database.init_db [--rebuild]"""
from __future__ import annotations

import sys
from pathlib import Path

import config
from database import repository as repo
from simulation.generate_funds import generate_funds
from simulation.validate import check_data


def build_database(db_path: Path | str = config.DB_PATH, seed: int = config.SEED) -> None:
    """清空所有資料（含衍生結果）後重新產生模擬資料。資料檢查失敗則中止。"""
    master, nav_wide = generate_funds(seed=seed)
    failed = [c for c in check_data(master, nav_wide) if not c.passed]
    if failed:
        raise RuntimeError("資料檢查失敗：" + "；".join(f"{c.item}（{c.detail}）" for c in failed))
    conn = repo.connect(db_path)
    try:
        repo.init_schema(conn)
        repo.reset_all(conn)
        repo.save_funds(conn, master, nav_wide)
    finally:
        conn.close()


def ensure_database(db_path: Path | str = config.DB_PATH) -> bool:
    """首次啟動若無資料庫或無資料，自動建立。回傳是否新建立。"""
    conn = repo.connect(db_path)
    try:
        repo.init_schema(conn)
        empty = repo.fund_count(conn) == 0
    finally:
        conn.close()
    if empty:
        build_database(db_path)
    return empty


if __name__ == "__main__":
    if "--rebuild" in sys.argv:
        build_database()
        print(f"已重建資料庫：{config.DB_PATH}")
    else:
        created = ensure_database()
        print(f"{'已建立' if created else '已存在'}資料庫：{config.DB_PATH}")
