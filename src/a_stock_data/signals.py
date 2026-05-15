"""
信号层模块

提供同花顺热点、北向资金、百度股市通、龙虎榜、解禁日历、行业对比等信号数据。

数据源:
- 同花顺热点: 当日强势股 + 题材归因 reason tags
- 同花顺北向: hgt/sgt 分钟资金流向 + 本地自缓存历史
- 百度股市通: 概念板块归属 + 个股资金流向
- akshare 龙虎榜: 上榜记录 + 买卖席位 + 机构动向
- akshare 解禁: 限售解禁日历
- akshare 行业: 行业横向对比
"""

from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import akshare as ak
import pandas as pd
import requests

from .utils import normalize_code

# HTTP 请求头
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36"

# 同花顺北向请求头
HSGT_HEADERS = {
    "User-Agent": UA,
    "Host": "data.hexin.cn",
    "Referer": "https://data.hexin.cn/",
}

# 百度股市通请求头
BAIDU_PAE_HEADERS = {
    "Host": "finance.pae.baidu.com",
    "User-Agent": UA,
    "Accept": "application/vnd.finance-web.v1+json",
    "Origin": "https://gushitong.baidu.com",
    "Referer": "https://gushitong.baidu.com/",
}

# 缓存路径
CACHE_DIR = Path.home() / ".tradingagents" / "cache"


# ============ 同花顺热点 ============


def ths_hot_reason(date_str: str = None) -> pd.DataFrame:
    """
    同花顺当日强势股归因

    核心价值：提供题材标签 reason（人工运营），告诉你"为什么走强"

    Args:
        date_str: 日期，'YYYY-MM-DD' 格式，None=今天

    Returns:
        DataFrame，列:
        - 代码, 名称, 收盘价, 涨跌额, 涨幅%, 换手率%, 成交额, 成交量, 大单净量, 市场
        - 题材归因: 核心字段，如"算力租赁+Token工厂+AI政务"

    Examples:
        >>> df = ths_hot_reason("2026-05-09")
        >>> print(f"当日强势股: {len(df)} 只")
        >>> print(df[["代码", "名称", "涨幅%", "题材归因"]].head(10))
    """
    if date_str is None:
        date_str = date.today().strftime("%Y-%m-%d")

    url = (
        f"http://zx.10jqka.com.cn/event/api/getharden/"
        f"date/{date_str}/orderby/date/orderway/desc/charset/GBK/"
    )
    r = requests.get(url, headers={"User-Agent": UA}, timeout=10)
    data = r.json()

    if data.get("errocode", 0) != 0:
        raise RuntimeError(f"同花顺热点错误: {data.get('errormsg', '')}")

    rows = data.get("data") or []
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # 字段重命名（中文友好）
    rename_map = {
        "name": "名称",
        "code": "代码",
        "reason": "题材归因",
        "close": "收盘价",
        "zhangdie": "涨跌额",
        "zhangfu": "涨幅%",
        "huanshou": "换手率%",
        "chengjiaoe": "成交额",
        "chengjiaoliang": "成交量",
        "ddejingliang": "大单净量",
        "market": "市场",
    }
    df = df.rename(columns=rename_map)
    return df


# ============ 同花顺北向资金 ============


def hsgt_realtime() -> pd.DataFrame:
    """
    沪深股通当日实时分钟流向（含集合竞价 09:10–15:00，262 个时间点）

    Returns:
        DataFrame，列: time, hgt_yi(沪股通累计净买入), sgt_yi(深股通累计净买入)
        单位: 亿元

    Examples:
        >>> df = hsgt_realtime()
        >>> print(f"分钟点数: {len(df)}")
        >>> print(df.tail(5))
    """
    url = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"
    r = requests.get(url, headers=HSGT_HEADERS, timeout=10)
    d = r.json()

    times = d.get("time", [])
    hgt = d.get("hgt", [])
    sgt = d.get("sgt", [])

    n = len(times)
    return pd.DataFrame({
        "time": times,
        "hgt_yi": hgt[:n] + [None] * (n - len(hgt)),
        "sgt_yi": sgt[:n] + [None] * (n - len(sgt)),
    })


def _northbound_cache_path() -> Path:
    """北向资金本地 CSV 缓存路径"""
    p = CACHE_DIR / "northbound_daily.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _save_northbound_snapshot(date_str: str, hgt: float, sgt: float):
    """
    写入/更新当天北向收盘数据到 CSV

    Args:
        date_str: 日期 "YYYY-MM-DD"
        hgt: 沪股通净买入(亿元)
        sgt: 深股通净买入(亿元)
    """
    path = _northbound_cache_path()
    rows = {}

    if path.exists():
        for line in path.read_text().strip().split("\n")[1:]:
            parts = line.split(",")
            if len(parts) == 3:
                rows[parts[0]] = line

    rows[date_str] = f"{date_str},{hgt},{sgt}"

    with open(path, "w") as f:
        f.write("date,hgt,sgt\n")
        for d in sorted(rows.keys()):
            f.write(rows[d] + "\n")


def _load_northbound_history(n: int = 20) -> pd.DataFrame:
    """
    读取最近 N 天北向历史

    Args:
        n: 返回最近天数

    Returns:
        DataFrame，列: date, hgt, sgt
    """
    path = _northbound_cache_path()
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df.tail(n)


# ============ 百度股市通 ============


def baidu_concept_blocks(code: str) -> dict:
    """
    百度股市通概念板块归属

    核心价值：一次调用拿到行业/概念/地域三维分类

    Args:
        code: 6位股票代码

    Returns:
        dict，含字段:
        - industry: [{name, change_pct, desc}, ...]
        - concept: [{name, change_pct, desc}, ...]
        - region: [{name, change_pct, desc}, ...]
        - concept_tags: [name1, name2, ...] 纯标签列表

    Examples:
        >>> blocks = baidu_concept_blocks("688017")
        >>> print("行业:", [b["name"] for b in blocks["industry"]])
        >>> print("概念:", blocks["concept_tags"])
    """
    code = normalize_code(code)
    url = (
        f"https://finance.pae.baidu.com/api/getrelatedblock"
        f"?code={code}&market=ab"
        f"&typeCode=all&finClientType=pc"
    )
    r = requests.get(url, headers=BAIDU_PAE_HEADERS, timeout=10)
    d = r.json()

    if str(d.get("ResultCode", -1)) != "0":
        raise RuntimeError(f"百度PAE错误: {d}")

    result = {"industry": [], "concept": [], "region": [], "concept_tags": []}

    for block in d.get("Result", []):
        block_type = block.get("type", "")
        for item in block.get("list", []):
            entry = {
                "name": item.get("name", ""),
                "change_pct": item.get("increase", ""),
                "desc": item.get("desc", ""),
            }
            if "行业" in block_type:
                result["industry"].append(entry)
            elif "概念" in block_type:
                result["concept"].append(entry)
                result["concept_tags"].append(entry["name"])
            elif "地域" in block_type:
                result["region"].append(entry)

    return result


def baidu_fund_flow_realtime(code: str, date_str: str) -> list[dict]:
    """
    个股资金流向（分钟级）

    Args:
        code: 6位股票代码
        date_str: 日期，YYYYMMDD 紧凑格式，如 "20260512"

    Returns:
        list[dict]，每项含: time, mainForce, retail, super, large, price

    Examples:
        >>> realtime = baidu_fund_flow_realtime("000858", "20260512")
        >>> if realtime:
        >>>     last = realtime[-1]
        >>>     print(f"主力净流入: {last['mainForce']}万")
    """
    code = normalize_code(code)
    url = (
        f"https://finance.pae.baidu.com/vapi/v1/fundflow"
        f"?code={code}&market=ab&date={date_str}"
        f"&finClientType=pc"
    )
    r = requests.get(url, headers=BAIDU_PAE_HEADERS, timeout=10)
    d = r.json()

    if str(d.get("ResultCode", -1)) != "0":
        return []

    raw = d.get("Result", {}).get("update_data", "")
    if not raw:
        return []

    rows = []
    for segment in raw.split(";"):
        parts = segment.split(",")
        if len(parts) >= 9:
            rows.append({
                "time": parts[0],
                "mainForce": float(parts[2]) if parts[2] else 0,
                "retail": float(parts[3]) if parts[3] else 0,
                "super": float(parts[4]) if parts[4] else 0,
                "large": float(parts[5]) if parts[5] else 0,
                "price": float(parts[8]) if parts[8] else 0,
            })
    return rows


def baidu_fund_flow_history(code: str, days: int = 20) -> list[dict]:
    """
    个股资金流向（日级，最近 N 交易日）

    Args:
        code: 6位股票代码
        days: 返回天数

    Returns:
        list[dict]，每项含: date, close, change_pct, superNetIn, largeNetIn,
        mediumNetIn, littleNetIn, mainIn

    Examples:
        >>> history = baidu_fund_flow_history("000858")
        >>> for h in history[:5]:
        >>>     print(f"{h['date']}: 主力={h['mainIn']}万")
    """
    code = normalize_code(code)
    url = (
        f"https://finance.pae.baidu.com/vapi/v1/fundsortlist"
        f"?code={code}&market=ab&pn=0&rn={days}"
        f"&finClientType=pc"
    )
    r = requests.get(url, headers=BAIDU_PAE_HEADERS, timeout=10)
    d = r.json()

    if str(d.get("ResultCode", -1)) != "0":
        return []

    rows = []
    for item in d.get("Result", {}).get("list", []):
        rows.append({
            "date": item.get("showtime", ""),
            "close": item.get("closepx", ""),
            "change_pct": item.get("ratio", ""),
            "superNetIn": item.get("superNetIn", ""),
            "largeNetIn": item.get("largeNetIn", ""),
            "mediumNetIn": item.get("mediumNetIn", ""),
            "littleNetIn": item.get("littleNetIn", ""),
            "mainIn": item.get("extMainIn", ""),
        })
    return rows


# ============ 龙虎榜 ============


def dragon_tiger_board(
    code: str, trade_date: str, look_back: int = 30
) -> dict:
    """
    龙虎榜数据聚合

    Args:
        code: 6位股票代码
        trade_date: 交易日期 "YYYY-MM-DD"
        look_back: 回看天数

    Returns:
        dict，含字段:
        - records: [{date, reason, net_buy, turnover}, ...] 上榜记录
        - seats: {buy: [...], sell: [...]} 买卖席位TOP5
        - institution: {buy_count, sell_count, net_amount} 机构买卖统计

    Examples:
        >>> data = dragon_tiger_board("002475", "2026-05-12")
        >>> print(f"近30日上榜 {len(data['records'])} 次")
    """
    code = normalize_code(code)
    start = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=look_back)
    start_str = start.strftime("%Y%m%d")
    end_str = trade_date.replace("-", "")

    # 1. 上榜记录
    records = []
    try:
        df = ak.stock_lhb_detail_em(start_date=start_str, end_date=end_str)
        if not df.empty:
            df_stock = df[df["代码"] == code]
            for _, row in df_stock.iterrows():
                records.append({
                    "date": str(row.get("日期", "")),
                    "reason": row.get("解读", ""),
                    "net_buy": row.get("龙虎榜净买额", 0),
                    "turnover": row.get("换手率", 0),
                })
    except Exception:
        pass

    # 2. 买卖席位
    seats = {"buy": [], "sell": []}
    if records:
        latest_date = records[0]["date"].replace("-", "")[:8]
        try:
            df_detail = ak.stock_lhb_stock_detail_em(
                symbol=code, date=latest_date, flag="买入"
            )
            if not df_detail.empty:
                for _, row in df_detail.head(5).iterrows():
                    seats["buy"].append({
                        "name": row.get("营业部名称", ""),
                        "buy_amt": row.get("买入额", 0),
                        "sell_amt": row.get("卖出额", 0),
                        "net": row.get("净额", 0),
                    })
        except Exception:
            pass

        try:
            df_detail = ak.stock_lhb_stock_detail_em(
                symbol=code, date=latest_date, flag="卖出"
            )
            if not df_detail.empty:
                for _, row in df_detail.head(5).iterrows():
                    seats["sell"].append({
                        "name": row.get("营业部名称", ""),
                        "buy_amt": row.get("买入额", 0),
                        "sell_amt": row.get("卖出额", 0),
                        "net": row.get("净额", 0),
                    })
        except Exception:
            pass

    # 3. 机构买卖统计
    institution = {}
    try:
        df_inst = ak.stock_lhb_jgmmtj_em(symbol=code)
        if not df_inst.empty:
            row = df_inst.iloc[0]
            institution = {
                "buy_count": row.get("买入机构数", 0),
                "sell_count": row.get("卖出机构数", 0),
                "net_amount": row.get("机构净买入额", 0),
            }
    except Exception:
        pass

    return {"records": records, "seats": seats, "institution": institution}


def daily_dragon_tiger(
    trade_date: str = None, min_net_buy: float = None
) -> dict:
    """
    全市场龙虎榜（东财 datacenter API）

    Args:
        trade_date: 日期 "YYYY-MM-DD"，默认当日
        min_net_buy: 净买入下限（万元），None 不过滤

    Returns:
        dict，含字段:
        - date: 实际日期
        - total_records: 记录数
        - stocks: [{code, name, reason, close, change_pct,
                   net_buy_wan, buy_wan, sell_wan, turnover_pct}, ...]

    Examples:
        >>> data = daily_dragon_tiger("2026-05-09")
        >>> print(f"龙虎榜共 {data['total_records']} 条记录")
    """
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
        "columns": "ALL",
        "filter": f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
        "pageNumber": "1",
        "pageSize": "500",
        "sortTypes": "-1",
        "sortColumns": "BILLBOARD_NET_AMT",
        "source": "WEB",
        "client": "WEB",
    }
    headers = {
        "User-Agent": UA,
        "Referer": "https://data.eastmoney.com/",
    }
    r = requests.get(url, params=params, headers=headers, timeout=15)
    d = r.json()

    if not d.get("success") or not d.get("result") or not d["result"].get("data"):
        return {
            "date": trade_date,
            "total_records": 0,
            "stocks": [],
            "note": "无数据（非交易日或盘后未更新）",
        }

    data = d["result"]["data"]
    actual_date = data[0].get("TRADE_DATE", "")[:10] if data else trade_date
    stocks = []

    for row in data:
        net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
        if min_net_buy is not None and net_buy < min_net_buy:
            continue
        stocks.append({
            "code": row.get("SECURITY_CODE", ""),
            "name": row.get("SECURITY_NAME_ABBR", ""),
            "reason": row.get("EXPLANATION", ""),
            "close": row.get("CLOSE_PRICE") or 0,
            "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
            "net_buy_wan": round(net_buy, 1),
            "buy_wan": round((row.get("BILLBOARD_BUY_AMT") or 0) / 10000, 1),
            "sell_wan": round((row.get("BILLBOARD_SELL_AMT") or 0) / 10000, 1),
            "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
        })

    return {"date": actual_date, "total_records": len(stocks), "stocks": stocks}


# ============ 限售解禁 ============


def lockup_expiry(
    code: str, trade_date: str, forward_days: int = 90
) -> dict:
    """
    限售解禁日历

    Args:
        code: 6位股票代码
        trade_date: 日期 "YYYY-MM-DD"
        forward_days: 未来预警天数

    Returns:
        dict，含字段:
        - history: [{date, type, shares, ratio}, ...] 历史解禁
        - upcoming: [{date, type, shares, float_ratio}, ...] 未来待解禁

    Examples:
        >>> data = lockup_expiry("002475", "2026-05-12")
        >>> print(f"历史解禁 {len(data['history'])} 批")
    """
    code = normalize_code(code)

    # 历史解禁记录
    history = []
    try:
        df = ak.stock_restricted_release_queue_em(symbol=code)
        if not df.empty:
            for _, row in df.head(15).iterrows():
                history.append({
                    "date": str(row.get("解禁时间", "")),
                    "type": row.get("限售股类型", ""),
                    "shares": row.get("解禁数量", 0),
                    "ratio": row.get("实际解禁市值占总市值比例", 0),
                })
    except Exception:
        pass

    # 未来待解禁
    upcoming = []
    end_date = datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=forward_days)
    end_str = end_date.strftime("%Y%m%d")
    today_str = trade_date.replace("-", "")

    try:
        df = ak.stock_restricted_release_detail_em(date=today_str)
        if not df.empty:
            df_stock = df[df["股票代码"] == code]
            for _, row in df_stock.iterrows():
                upcoming.append({
                    "date": str(row.get("解禁日期", "")),
                    "type": row.get("限售股类型", ""),
                    "shares": row.get("解禁数量", 0),
                    "float_ratio": row.get("占流通股比例", 0),
                })
    except Exception:
        pass

    return {"history": history, "upcoming": upcoming}


# ============ 行业横向对比 ============


def industry_comparison(top_n: int = 20) -> dict:
    """
    全行业涨跌幅排名（同花顺 ~90 个行业）

    Args:
        top_n: 返回TOP/BOTTOM数量

    Returns:
        dict，含字段:
        - top: [{rank, name, change_pct, turnover_yi, net_inflow_yi, up_count, down_count, leader}, ...]
        - bottom: 同上
        - total: 行业总数

    Examples:
        >>> data = industry_comparison(20)
        >>> print(f"共 {data['total']} 个行业")
        >>> for r in data["top"][:10]:
        >>>     print(f"  {r['rank']}. {r['name']}: {r['change_pct']}%")
    """
    df = ak.stock_board_industry_summary_ths()
    if df.empty:
        return {"top": [], "bottom": [], "total": 0}

    rows = []
    for i, row in df.iterrows():
        rows.append({
            "rank": i + 1,
            "name": row.get("板块", ""),
            "change_pct": row.get("涨跌幅", 0),
            "turnover_yi": row.get("总成交额", 0),
            "net_inflow_yi": row.get("净流入", 0) if "净流入" in df.columns else None,
            "up_count": row.get("上涨家数", 0),
            "down_count": row.get("下跌家数", 0),
            "leader": row.get("领涨股", ""),
        })

    return {
        "top": rows[:top_n],
        "bottom": rows[-top_n:],
        "total": len(rows),
    }


# ============ 组合工具 ============


def hot_topics(n: int = 10) -> list[tuple[str, int]]:
    """
    统计当日TOP题材热度

    Args:
        n: 返回数量

    Returns:
        list[(题材名, 出现次数)]，按热度降序

    Examples:
        >>> topics = hot_topics(10)
        >>> for tag, cnt in topics:
        >>>     print(f"  {tag}: {cnt} 只")
    """
    df = ths_hot_reason()
    all_tags = []

    for r in df["题材归因"].dropna():
        tags = [t.strip() for t in str(r).split("+") if t.strip()]
        all_tags.extend(tags)

    cnt = Counter(all_tags)
    return cnt.most_common(n)


def northbound_summary() -> dict:
    """
    北向资金当日汇总

    Returns:
        dict，含: hgt_today, sgt_today, total, signal(bullish/bearish/neutral)

    Examples:
        >>> summary = northbound_summary()
        >>> print(f"沪股通: {summary['hgt_today']}亿")
    """
    df = hsgt_realtime()
    if df.empty:
        return {"hgt_today": None, "sgt_today": None, "total": None, "signal": "neutral"}

    last = df.dropna().iloc[-1]
    hgt = last["hgt_yi"]
    sgt = last["sgt_yi"]
    total = hgt + sgt

    if total > 20:
        signal = "bullish"
    elif total < -20:
        signal = "bearish"
    else:
        signal = "neutral"

    return {
        "hgt_today": hgt,
        "sgt_today": sgt,
        "total": total,
        "signal": signal,
    }
