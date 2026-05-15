"""
数据库模块 - A股数据持久化存储 (MySQL)

使用 MySQL 存储历史数据，支持日后回顾分析。
通过环境变量或 db_config 配置连接参数。

Usage:
    from feifan_stock_data.db import init_db, get_db
    init_db()  # 初始化表结构

环境变量:
    FEIFAN_DB_HOST     主机 (默认 127.0.0.1)
    FEIFAN_DB_PORT     端口 (默认 3306)
    FEIFAN_DB_USER     用户名 (默认 root)
    FEIFAN_DB_PASSWORD 密码 (默认空)
    FEIFAN_DB_NAME     数据库名 (默认 feifan_stock)
"""

import json
import os
from contextlib import contextmanager

import pymysql
from dbutils.pooled_db import PooledDB

# ==================== 连接配置 ====================

def _db_config() -> dict:
    """延迟读取数据库配置（确保环境变量已注入）"""
    return {
        "host": os.environ.get("FEIFAN_DB_HOST", "127.0.0.1"),
        "port": int(os.environ.get("FEIFAN_DB_PORT", "3306")),
        "user": os.environ.get("FEIFAN_DB_USER", "root"),
        "password": os.environ.get("FEIFAN_DB_PASSWORD", ""),
        "database": os.environ.get("FEIFAN_DB_NAME", "feifan_stock"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }

_pool: PooledDB | None = None


def _get_pool() -> PooledDB:
    """获取连接池（懒初始化）"""
    global _pool
    if _pool is None:
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=10,
            mincached=2,
            maxcached=5,
            blocking=True,
            **_db_config(),
        )
    return _pool


@contextmanager
def get_db():
    """获取数据库连接（上下文管理器，自动归还连接池）"""
    pool = _get_pool()
    conn = pool.connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """初始化数据库和表结构（自动创建数据库）"""
    # 先不指定数据库，连接 MySQL 创建库
    cfg = _db_config()
    db_name = cfg.pop("database")
    conn = pymysql.connect(**cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()

    # 重新用连接池建表
    with get_db() as conn:
        for stmt in _TABLE_SQLS:
            with conn.cursor() as cur:
                cur.execute(stmt)
        conn.commit()


# ==================== 建表 SQL ====================

_TABLE_SQLS = [
    """CREATE TABLE IF NOT EXISTS quote_snapshot (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        code        VARCHAR(10) NOT NULL,
        name        VARCHAR(40),
        price       DOUBLE,
        last_close  DOUBLE,
        open        DOUBLE,
        high        DOUBLE,
        low         DOUBLE,
        change_amt  DOUBLE,
        change_pct  DOUBLE,
        amount_wan  DOUBLE,
        turnover_pct DOUBLE,
        pe_ttm      DOUBLE,
        amplitude_pct DOUBLE,
        mcap_yi     DOUBLE,
        float_mcap_yi DOUBLE,
        pb          DOUBLE,
        limit_up    DOUBLE,
        limit_down  DOUBLE,
        volume_ratio DOUBLE,
        captured_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_quote_code_time (code, captured_at),
        INDEX idx_quote_code (code),
        INDEX idx_quote_captured (captured_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    """CREATE TABLE IF NOT EXISTS valuation_record (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        code            VARCHAR(10) NOT NULL,
        name            VARCHAR(40),
        pe_ttm          DOUBLE,
        pb              DOUBLE,
        peg             DOUBLE,
        forward_pe      DOUBLE,
        roe_pct         DOUBLE,
        revenue_yoy     DOUBLE,
        profit_yoy      DOUBLE,
        dividend_yield  DOUBLE,
        total_score     DOUBLE,
        signal          VARCHAR(20),
        summary_json    JSON,
        raw_json        JSON,
        captured_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_val_code_time (code, captured_at),
        INDEX idx_valuation_code (code),
        INDEX idx_valuation_captured (captured_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    """CREATE TABLE IF NOT EXISTS northbound_flow (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        hgt_today   DOUBLE,
        sgt_today   DOUBLE,
        total       DOUBLE,
        signal      VARCHAR(20),
        captured_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_nb_captured (captured_at),
        INDEX idx_nb_captured (captured_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    """CREATE TABLE IF NOT EXISTS dragon_tiger (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        trade_date  DATE NOT NULL,
        code        VARCHAR(10) NOT NULL,
        name        VARCHAR(40),
        reason      TEXT,
        close       DOUBLE,
        change_pct  DOUBLE,
        net_buy_wan DOUBLE,
        buy_wan     DOUBLE,
        sell_wan    DOUBLE,
        turnover_pct DOUBLE,
        captured_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_dt_date_code (trade_date, code),
        INDEX idx_dt_date (trade_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    """CREATE TABLE IF NOT EXISTS hot_stock (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        code        VARCHAR(10) NOT NULL,
        name        VARCHAR(40),
        close_price DOUBLE,
        change_pct  DOUBLE,
        turnover_pct DOUBLE,
        amount      DOUBLE,
        volume      DOUBLE,
        big_order_net DOUBLE,
        market      VARCHAR(10),
        theme       TEXT,
        captured_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_hs_code_time (code, captured_at),
        INDEX idx_hs_code (code),
        INDEX idx_hs_captured (captured_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    """CREATE TABLE IF NOT EXISTS hot_topic (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        topic       VARCHAR(80) NOT NULL,
        count       INT NOT NULL,
        captured_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_ht_topic_time (topic, captured_at),
        INDEX idx_ht_captured (captured_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    """CREATE TABLE IF NOT EXISTS industry_rank (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        rank_num        INT NOT NULL,
        name            VARCHAR(40) NOT NULL,
        change_pct      DOUBLE,
        turnover_yi     DOUBLE,
        net_inflow_yi   DOUBLE,
        up_count        INT,
        down_count      INT,
        leader          VARCHAR(40),
        direction       VARCHAR(10) NOT NULL DEFAULT 'top',
        captured_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_ir_name_dir_time (name, direction, captured_at),
        INDEX idx_ir_captured (captured_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    """CREATE TABLE IF NOT EXISTS research_report (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        code        VARCHAR(10) NOT NULL,
        title       VARCHAR(200),
        org         VARCHAR(60),
        rating      VARCHAR(20),
        target_price DOUBLE,
        date        DATE,
        captured_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_rr_code_title_date (code, title, date),
        INDEX idx_rr_code (code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    """CREATE TABLE IF NOT EXISTS market_news (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        title       VARCHAR(200) NOT NULL,
        source      VARCHAR(60),
        time        DATETIME,
        captured_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_news_title_time (title, time),
        INDEX idx_news_captured (captured_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    """CREATE TABLE IF NOT EXISTS announcement (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        code        VARCHAR(10) NOT NULL,
        title       VARCHAR(200) NOT NULL,
        time        DATETIME,
        pdf_url     TEXT,
        captured_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_ann_code_title_time (code, title, time),
        INDEX idx_ann_code (code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    """CREATE TABLE IF NOT EXISTS fundamental_data (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        code            VARCHAR(10) NOT NULL,
        name            VARCHAR(40),
        industry        VARCHAR(60),
        total_share     DOUBLE,
        float_share     DOUBLE,
        roe_pct         DOUBLE,
        eps             DOUBLE,
        bvps            DOUBLE,
        revenue_yoy     DOUBLE,
        profit_yoy      DOUBLE,
        gross_margin    DOUBLE,
        net_margin      DOUBLE,
        raw_json        JSON,
        captured_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_fd_code_time (code, captured_at),
        INDEX idx_fd_code (code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]


# ==================== 存储函数 ====================


def save_quote(data: dict):
    """保存单股票行情快照"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT IGNORE INTO quote_snapshot
                (code, name, price, last_close, open, high, low, change_amt, change_pct,
                 amount_wan, turnover_pct, pe_ttm, amplitude_pct, mcap_yi, float_mcap_yi,
                 pb, limit_up, limit_down, volume_ratio)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    data.get("code", ""), data.get("name"), data.get("price"),
                    data.get("last_close"), data.get("open"), data.get("high"),
                    data.get("low"), data.get("change_amt"), data.get("change_pct"),
                    data.get("amount_wan"), data.get("turnover_pct"), data.get("pe_ttm"),
                    data.get("amplitude_pct"), data.get("mcap_yi"), data.get("float_mcap_yi"),
                    data.get("pb"), data.get("limit_up"), data.get("limit_down"),
                    data.get("volume_ratio"),
                ),
            )
        conn.commit()


def save_quotes(data: dict):
    """保存批量行情快照"""
    with get_db() as conn:
        with conn.cursor() as cur:
            for code, q in data.items():
                cur.execute(
                    """INSERT IGNORE INTO quote_snapshot
                    (code, name, price, last_close, open, high, low, change_amt, change_pct,
                     amount_wan, turnover_pct, pe_ttm, amplitude_pct, mcap_yi, float_mcap_yi,
                     pb, limit_up, limit_down, volume_ratio)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        code, q.get("name"), q.get("price"), q.get("last_close"),
                        q.get("open"), q.get("high"), q.get("low"), q.get("change_amt"),
                        q.get("change_pct"), q.get("amount_wan"), q.get("turnover_pct"),
                        q.get("pe_ttm"), q.get("amplitude_pct"), q.get("mcap_yi"),
                        q.get("float_mcap_yi"), q.get("pb"), q.get("limit_up"),
                        q.get("limit_down"), q.get("volume_ratio"),
                    ),
                )
        conn.commit()


def save_valuation(code: str, data: dict):
    """保存估值记录"""
    with get_db() as conn:
        with conn.cursor() as cur:
            summary = data.get("summary", {})
            cur.execute(
                """INSERT IGNORE INTO valuation_record
                (code, name, pe_ttm, pb, peg, forward_pe, roe_pct, revenue_yoy, profit_yoy,
                 dividend_yield, total_score, signal, summary_json, raw_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    code, data.get("name"), data.get("pe_ttm"), data.get("pb"),
                    data.get("peg"), data.get("forward_pe"), data.get("roe_pct"),
                    data.get("revenue_yoy"), data.get("profit_yoy"), data.get("dividend_yield"),
                    summary.get("total_score"), summary.get("signal"),
                    json.dumps(summary, ensure_ascii=False) if summary else None,
                    json.dumps(data, ensure_ascii=False),
                ),
            )
        conn.commit()


def save_northbound(data: dict):
    """保存北向资金"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT IGNORE INTO northbound_flow (hgt_today, sgt_today, total, signal) VALUES (%s,%s,%s,%s)",
                (data.get("hgt_today"), data.get("sgt_today"), data.get("total"), data.get("signal")),
            )
        conn.commit()


def save_dragon_tiger(data: dict):
    """保存龙虎榜"""
    with get_db() as conn:
        with conn.cursor() as cur:
            trade_date = data.get("date", "")
            for s in data.get("stocks", []):
                cur.execute(
                    """INSERT IGNORE INTO dragon_tiger
                    (trade_date, code, name, reason, close, change_pct, net_buy_wan,
                     buy_wan, sell_wan, turnover_pct)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        trade_date, s.get("code"), s.get("name"), s.get("reason"),
                        s.get("close"), s.get("change_pct"), s.get("net_buy_wan"),
                        s.get("buy_wan"), s.get("sell_wan"), s.get("turnover_pct"),
                    ),
                )
        conn.commit()


def save_hot_stocks(df):
    """保存强势股"""
    if df is None or (hasattr(df, "empty") and df.empty):
        return
    cols_map = {
        "代码": "code", "名称": "name", "收盘价": "close_price",
        "涨幅%": "change_pct", "换手率%": "turnover_pct", "成交额": "amount",
        "成交量": "volume", "大单净量": "big_order_net", "市场": "market", "题材归因": "theme",
    }
    with get_db() as conn:
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                v = {en: row[cn] for cn, en in cols_map.items() if cn in row.index}
                cur.execute(
                    """INSERT IGNORE INTO hot_stock
                    (code, name, close_price, change_pct, turnover_pct, amount, volume,
                     big_order_net, market, theme)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        v.get("code"), v.get("name"), v.get("close_price"),
                        v.get("change_pct"), v.get("turnover_pct"), v.get("amount"),
                        v.get("volume"), v.get("big_order_net"), v.get("market"), v.get("theme"),
                    ),
                )
        conn.commit()


def save_hot_topics(topics: list):
    """保存热门题材"""
    if not topics:
        return
    with get_db() as conn:
        with conn.cursor() as cur:
            for topic, count in topics:
                cur.execute(
                    "INSERT IGNORE INTO hot_topic (topic, count) VALUES (%s, %s)",
                    (topic, count),
                )
        conn.commit()


def save_industry(data: dict):
    """保存行业涨跌"""
    if not data:
        return
    with get_db() as conn:
        with conn.cursor() as cur:
            for direction in ("top", "bottom"):
                for item in data.get(direction, []):
                    cur.execute(
                        """INSERT IGNORE INTO industry_rank
                        (rank_num, name, change_pct, turnover_yi, net_inflow_yi,
                         up_count, down_count, leader, direction)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            item.get("rank"), item.get("name"), item.get("change_pct"),
                            item.get("turnover_yi"), item.get("net_inflow_yi"),
                            item.get("up_count"), item.get("down_count"),
                            item.get("leader"), direction,
                        ),
                    )
        conn.commit()


def save_research(code: str, reports: list):
    """保存研报"""
    if not reports:
        return
    with get_db() as conn:
        with conn.cursor() as cur:
            for r in reports:
                cur.execute(
                    """INSERT IGNORE INTO research_report
                    (code, title, org, rating, target_price, date)
                    VALUES (%s,%s,%s,%s,%s,%s)""",
                    (
                        code,
                        r.get("title") or r.get("标题"),
                        r.get("org") or r.get("机构"),
                        r.get("rating") or r.get("评级"),
                        r.get("target_price") or r.get("目标价"),
                        r.get("date") or r.get("日期"),
                    ),
                )
        conn.commit()


def save_news(df):
    """保存市场新闻"""
    if df is None or (hasattr(df, "empty") and df.empty):
        return
    with get_db() as conn:
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                cur.execute(
                    "INSERT IGNORE INTO market_news (title, source, time) VALUES (%s, %s, %s)",
                    (row.get("新闻标题", ""), row.get("文章来源", ""), row.get("发布时间", "")),
                )
        conn.commit()


def save_announcement(code: str, df):
    """保存公告"""
    if df is None or (hasattr(df, "empty") and df.empty):
        return
    with get_db() as conn:
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                cur.execute(
                    "INSERT IGNORE INTO announcement (code, title, time, pdf_url) VALUES (%s, %s, %s, %s)",
                    (code, row.get("公告标题", ""), row.get("公告时间", ""), row.get("pdf链接", "")),
                )
        conn.commit()


def save_fundamental(code: str, data: dict):
    """保存基础数据"""
    if not data:
        return
    with get_db() as conn:
        with conn.cursor() as cur:
            basic = data.get("basic", {}) or {}
            indicators = data.get("indicators", {}) or {}
            cur.execute(
                """INSERT IGNORE INTO fundamental_data
                (code, name, industry, total_share, float_share, roe_pct, eps, bvps,
                 revenue_yoy, profit_yoy, gross_margin, net_margin, raw_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    code,
                    basic.get("name") or indicators.get("名称"),
                    basic.get("industry") or indicators.get("行业"),
                    basic.get("total_share"), basic.get("float_share"),
                    indicators.get("roe_pct") or indicators.get("ROE"),
                    indicators.get("eps") or indicators.get("每股收益"),
                    indicators.get("bvps") or indicators.get("每股净资产"),
                    indicators.get("revenue_yoy") or indicators.get("营收同比"),
                    indicators.get("profit_yoy") or indicators.get("净利润同比"),
                    indicators.get("gross_margin") or indicators.get("毛利率"),
                    indicators.get("net_margin") or indicators.get("净利率"),
                    json.dumps(data, ensure_ascii=False),
                ),
            )
        conn.commit()


# ==================== 查询函数 ====================


def _serialize_row(row: dict) -> dict:
    """将 MySQL 返回的行转为 JSON 可序列化格式"""
    result = {}
    for k, v in row.items():
        if v is not None and hasattr(v, "isoformat"):
            v = v.isoformat()
        result[k] = v
    return result


def query_quote_history(code: str, limit: int = 30) -> list[dict]:
    """查询个股行情历史"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM quote_snapshot WHERE code = %s ORDER BY captured_at DESC LIMIT %s",
                (code, limit),
            )
            return [_serialize_row(r) for r in cur.fetchall()]


def query_valuation_history(code: str, limit: int = 30) -> list[dict]:
    """查询个股估值历史"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM valuation_record WHERE code = %s ORDER BY captured_at DESC LIMIT %s",
                (code, limit),
            )
            return [_serialize_row(r) for r in cur.fetchall()]


def query_northbound_history(limit: int = 30) -> list[dict]:
    """查询北向资金历史"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM northbound_flow ORDER BY captured_at DESC LIMIT %s", (limit,)
            )
            return [_serialize_row(r) for r in cur.fetchall()]


def query_dragon_tiger_history(limit: int = 30) -> list[dict]:
    """查询龙虎榜历史"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM dragon_tiger ORDER BY trade_date DESC, net_buy_wan DESC LIMIT %s",
                (limit,),
            )
            return [_serialize_row(r) for r in cur.fetchall()]


def query_hot_stock_history(code: str = None, limit: int = 50) -> list[dict]:
    """查询强势股历史"""
    with get_db() as conn:
        with conn.cursor() as cur:
            if code:
                cur.execute(
                    "SELECT * FROM hot_stock WHERE code = %s ORDER BY captured_at DESC LIMIT %s",
                    (code, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM hot_stock ORDER BY captured_at DESC LIMIT %s", (limit,)
                )
            return [_serialize_row(r) for r in cur.fetchall()]


def query_topic_history(limit: int = 30) -> list[dict]:
    """查询热门题材历史"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM hot_topic ORDER BY captured_at DESC LIMIT %s", (limit,)
            )
            return [_serialize_row(r) for r in cur.fetchall()]


def query_industry_history(limit: int = 30) -> list[dict]:
    """查询行业涨跌历史"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM industry_rank ORDER BY captured_at DESC LIMIT %s", (limit,)
            )
            return [_serialize_row(r) for r in cur.fetchall()]


def query_research_history(code: str = None, limit: int = 30) -> list[dict]:
    """查询研报历史"""
    with get_db() as conn:
        with conn.cursor() as cur:
            if code:
                cur.execute(
                    "SELECT * FROM research_report WHERE code = %s ORDER BY captured_at DESC LIMIT %s",
                    (code, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM research_report ORDER BY captured_at DESC LIMIT %s", (limit,)
                )
            return [_serialize_row(r) for r in cur.fetchall()]


def query_news_history(limit: int = 50) -> list[dict]:
    """查询新闻历史"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM market_news ORDER BY captured_at DESC LIMIT %s", (limit,)
            )
            return [_serialize_row(r) for r in cur.fetchall()]


def query_announcement_history(code: str = None, limit: int = 30) -> list[dict]:
    """查询公告历史"""
    with get_db() as conn:
        with conn.cursor() as cur:
            if code:
                cur.execute(
                    "SELECT * FROM announcement WHERE code = %s ORDER BY captured_at DESC LIMIT %s",
                    (code, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM announcement ORDER BY captured_at DESC LIMIT %s", (limit,)
                )
            return [_serialize_row(r) for r in cur.fetchall()]


def query_fundamental_history(code: str = None, limit: int = 30) -> list[dict]:
    """查询基础数据历史"""
    with get_db() as conn:
        with conn.cursor() as cur:
            if code:
                cur.execute(
                    "SELECT * FROM fundamental_data WHERE code = %s ORDER BY captured_at DESC LIMIT %s",
                    (code, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM fundamental_data ORDER BY captured_at DESC LIMIT %s", (limit,)
                )
            return [_serialize_row(r) for r in cur.fetchall()]


def check_connection() -> bool:
    """检查 MySQL 连接是否正常"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return True
    except Exception:
        return False
