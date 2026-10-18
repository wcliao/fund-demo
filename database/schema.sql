-- 基金量化策略 Demo：SQLite Schema（規格書第七章，共 7 張表）
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS fund_master (
    fund_id        TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    category       TEXT NOT NULL,
    currency       TEXT NOT NULL DEFAULT 'TWD',
    expense_ratio  REAL NOT NULL,
    scenario_type  TEXT NOT NULL,
    purpose        TEXT,
    data_source    TEXT NOT NULL DEFAULT 'SYNTHETIC'
);

CREATE TABLE IF NOT EXISTS fund_nav (
    fund_id   TEXT NOT NULL REFERENCES fund_master(fund_id),
    nav_date  TEXT NOT NULL,
    nav       REAL NOT NULL CHECK (nav > 0),
    PRIMARY KEY (fund_id, nav_date)
);

CREATE TABLE IF NOT EXISTS strategy_config (
    config_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id  TEXT NOT NULL,
    params_json  TEXT NOT NULL,
    params_hash  TEXT NOT NULL UNIQUE,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_result (
    config_id     INTEGER NOT NULL REFERENCES strategy_config(config_id),
    fund_id       TEXT NOT NULL REFERENCES fund_master(fund_id),
    eval_date     TEXT NOT NULL,
    strategy_id   TEXT NOT NULL,
    score         REAL,
    rank          INTEGER,
    details_json  TEXT,
    PRIMARY KEY (config_id, fund_id, eval_date)
);

CREATE TABLE IF NOT EXISTS backtest_run (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id   TEXT NOT NULL,
    config_id     INTEGER NOT NULL REFERENCES strategy_config(config_id),
    cost_rate     REAL NOT NULL,
    start_date    TEXT NOT NULL,
    end_date      TEXT NOT NULL,
    metrics_json  TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backtest_daily (
    run_id          INTEGER NOT NULL REFERENCES backtest_run(run_id) ON DELETE CASCADE,
    nav_date        TEXT NOT NULL,
    equity          REAL NOT NULL,
    cash            REAL NOT NULL,
    positions_json  TEXT NOT NULL,
    PRIMARY KEY (run_id, nav_date)
);

CREATE TABLE IF NOT EXISTS backtest_trades (
    trade_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       INTEGER NOT NULL REFERENCES backtest_run(run_id) ON DELETE CASCADE,
    signal_date  TEXT NOT NULL,
    exec_date    TEXT NOT NULL,
    fund_id      TEXT NOT NULL,
    side         TEXT NOT NULL,
    amount       REAL NOT NULL,
    units        REAL NOT NULL,
    cost         REAL NOT NULL
);
