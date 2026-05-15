"""
研报层模块

提供研报列表、PDF下载、机构一致预期EPS、NL语义搜索等功能。

数据源:
- 东财 reportapi: 研报列表 + PDF下载 + 评级 + 三年EPS
- akshare THS: 一致预期EPS
- iwencai: NL语义搜索研报 (需API Key)
"""

import os
import re
import secrets
import time
from pathlib import Path
from typing import Optional

import requests

from .utils import normalize_code

# HTTP 请求头
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# API 端点
REPORT_API = "https://reportapi.eastmoney.com/report/list"
PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"

# iwencai 配置
IWENCAI_BASE = os.environ.get("IWENCAI_BASE_URL", "https://openapi.iwencai.com")
IWENCAI_KEY = os.environ.get("IWENCAI_API_KEY", "")


def _claw_headers(call_type: str = "normal") -> dict:
    """
    生成 SkillHub 2.0 X-Claw 鉴权头

    Args:
        call_type: 调用类型

    Returns:
        X-Claw 相关 HTTP 头字典
    """
    return {
        "X-Claw-Call-Type": call_type,
        "X-Claw-Skill-Id": "report-search",
        "X-Claw-Skill-Version": "2.0.0",
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": secrets.token_hex(32),
    }


def eastmoney_reports(code: str, max_pages: int = 5) -> list[dict]:
    """
    拉取指定股票的研报列表

    Args:
        code: 6位股票代码
        max_pages: 最大页数

    Returns:
        研报记录列表，每条记录含字段:
        - title: 研报标题
        - publishDate: 发布日期
        - orgSName: 机构简称
        - infoCode: 用于拼 PDF URL
        - predictThisYearEps: 今年EPS预测
        - predictNextYearEps: 明年EPS预测
        - predictNextTwoYearEps: 后年EPS预测
        - emRatingName: 评级(买入/增持/...)
        - indvInduName: 行业分类

    Examples:
        >>> reports = eastmoney_reports("688017")
        >>> print(f"共 {len(reports)} 篇研报")
        >>> for r in reports[:5]:
        >>>     print(f"  {r['publishDate'][:10]} | {r['orgSName']} | {r['title'][:60]}")
    """
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Referer": "https://data.eastmoney.com/"})

    all_records = []
    code = normalize_code(code)

    for page in range(1, max_pages + 1):
        params = {
            "industryCode": "*",
            "pageSize": "100",
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": "2000-01-01",
            "endTime": "2030-01-01",
            "pageNo": str(page),
            "fields": "",
            "qType": "0",
            "orgCode": "",
            "code": code,
            "rcode": "",
            "p": str(page),
            "pageNum": str(page),
            "pageNumber": str(page),
        }
        r = session.get(REPORT_API, params=params, timeout=30)
        d = r.json()
        rows = d.get("data") or []

        if not rows:
            break

        all_records.extend(rows)

        if page >= (d.get("TotalPage", 1) or 1):
            break

        time.sleep(0.3)

    return all_records


def download_pdf(record: dict, target_dir: str = "./reports") -> Optional[str]:
    """
    下载单份研报PDF

    Args:
        record: eastmoney_reports 返回的研报记录
        target_dir: 保存目录

    Returns:
        保存路径或 None（下载失败时）

    Examples:
        >>> reports = eastmoney_reports("688017")
        >>> if reports:
        >>>     path = download_pdf(reports[0])
        >>>     print(f"PDF已保存: {path}")
    """
    info_code = record.get("infoCode", "")
    if not info_code:
        return None

    date = (record.get("publishDate") or "")[:10]
    org = record.get("orgSName") or "未知"
    title = re.sub(r'[\\/:*?"<>|]', "_", record.get("title", ""))[:80]
    fname = f"{date}_{org}_{title}.pdf"

    target = Path(target_dir) / fname
    if target.exists():
        return str(target)

    url = PDF_TPL.format(info_code=info_code)
    r = requests.get(
        url,
        headers={"User-Agent": UA, "Referer": "https://data.eastmoney.com/"},
        timeout=60,
    )

    if r.status_code == 200 and len(r.content) >= 1024:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(r.content)
        return str(target)

    return None


def ths_consensus_eps(code: str, indicator: str = "预测年报每股收益") -> "pd.DataFrame":
    """
    获取机构一致预期EPS（akshare 同花顺封装）

    Args:
        code: 6位股票代码
        indicator: 指标类型
            - "预测年报每股收益": EPS共识（最稳定）
            - "预测年报净利润": 净利润预测
            - "预测详细指标": 综合维度（有时返回空）
            - "业绩预测详表-机构": 按机构展示

    Returns:
        DataFrame，列: 年度, 预测机构数, 最小值, 均值, 最大值, 行业平均数
        "均值" = 机构一致预期EPS
        "预测机构数" < 3 的要谨慎

    Examples:
        >>> df = ths_consensus_eps("688017")
        >>> print(df)
    """
    import akshare as ak

    code = normalize_code(code)
    return ak.stock_profit_forecast_ths(symbol=code, indicator=indicator)


def iwencai_search(query: str, channel: str = "report", size: int = 50) -> list[dict]:
    """
    iwencai NL语义搜索

    需要 IWENCAI_API_KEY 环境变量

    Args:
        query: 自然语言查询，如 "人形机器人 行星滚柱丝杠 2026"
        channel: 搜索渠道
            - "report": 研报
            - "announcement": 公告
            - "news": 新闻
        size: 返回数量，默认50（隐藏参数）

    Returns:
        搜索结果列表

    Examples:
        >>> articles = iwencai_search("人形机器人 行星滚柱丝杠 2026", channel="report", size=50)
        >>> for a in articles[:5]:
        >>>     print(f"{a.get('publish_date','')[:10]} | {a.get('title','')[:60]}")
    """
    if not IWENCAI_KEY:
        raise ValueError("需要设置 IWENCAI_API_KEY 环境变量")

    headers = {
        "Authorization": f"Bearer {IWENCAI_KEY}",
        "Content-Type": "application/json",
        **_claw_headers(),
    }
    payload = {
        "channels": [channel],
        "app_id": "AIME_SKILL",
        "query": query,
        "size": size,
    }

    r = requests.post(
        f"{IWENCAI_BASE}/v1/comprehensive/search",
        json=payload,
        headers=headers,
        timeout=30,
    )

    if r.status_code != 200:
        raise RuntimeError(f"iwencai HTTP {r.status_code}: {r.text[:200]}")

    data = r.json()
    if data.get("status_code", 0) != 0:
        raise RuntimeError(f"iwencai error: {data.get('status_msg', '')}")

    return data.get("data") or []


def iwencai_query(query: str, page: int = 1, limit: int = 50) -> list[dict]:
    """
    iwencai NL数据查询（结构化字段）

    Args:
        query: 自然语言查询，如 "贵州茅台 ROE"
        page: 页码
        limit: 每页数量

    Returns:
        查询结果列表（DataFrame-like rows）

    Examples:
        >>> results = iwencai_query("贵州茅台 ROE")
        >>> for r in results:
        >>>     print(r)
    """
    if not IWENCAI_KEY:
        raise ValueError("需要设置 IWENCAI_API_KEY 环境变量")

    headers = {
        "Authorization": f"Bearer {IWENCAI_KEY}",
        "Content-Type": "application/json",
        **_claw_headers(),
    }
    payload = {
        "query": query,
        "page": str(page),
        "limit": str(limit),
        "is_cache": "1",
        "expand_index": "true",
    }

    r = requests.post(
        f"{IWENCAI_BASE}/v1/query2data",
        json=payload,
        headers=headers,
        timeout=30,
    )

    if r.status_code != 200:
        raise RuntimeError(f"iwencai HTTP {r.status_code}: {r.text[:200]}")

    data = r.json()
    if data.get("status_code", 0) != 0:
        raise RuntimeError(f"iwencai error: {data.get('status_msg', '')}")

    return data.get("datas") or []


def dedup_articles(articles: list[dict]) -> list[dict]:
    """
    研报去重：同一uid仅保留score最高的段落

    Args:
        articles: iwencai_search 返回的结果列表

    Returns:
        去重后的结果列表，按发布日期倒序

    Examples:
        >>> articles = iwencai_search("人形机器人 2026")
        >>> articles = dedup_articles(articles)
    """
    import json

    best = {}
    for a in articles:
        uid = a.get("uid", "") or f"{a.get('title', '')}|{a.get('publish_date', '')}"
        score = float(a.get("score", 0))
        if uid not in best or score > float(best[uid].get("score", 0)):
            best[uid] = a

    return sorted(best.values(), key=lambda x: x.get("publish_date", ""), reverse=True)
