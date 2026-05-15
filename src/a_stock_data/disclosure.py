"""
公告层模块

提供巨潮公告、F10公告摘要等公告数据。

数据源:
- akshare cninfo: 巨潮公告全文
- mootdx F10: 最新公告摘要
"""

import akshare as ak
import pandas as pd

from .utils import get_market, normalize_code


def cninfo_disclosure(symbol: str, market: str = None) -> pd.DataFrame:
    """
    获取巨潮公告列表

    Args:
        symbol: 6位股票代码
        market: 市场类型
            - "沪市" (6开头)
            - "深市" (0/3开头)
            - "北交所" (8开头)
            自动推断

    Returns:
        DataFrame，列: 公告标题, 公告类型, 公告日期, 公告链接

    Examples:
        >>> df = cninfo_disclosure("688017")
        >>> print(df.head())
    """
    code = normalize_code(symbol)
    if market is None:
        market = get_market(code)
    return ak.stock_zh_a_disclosure_report_cninfo(symbol=code, market=market)


def f10_announcement_summary(symbol: str) -> str:
    """
    获取F10最新公告摘要

    Args:
        symbol: 6位股票代码

    Returns:
        文本内容，含最近公告/分红/股东大会决议等摘要

    Examples:
        >>> text = f10_announcement_summary("688017")
        >>> print(text[:500])
    """
    from mootdx.quotes import Quotes

    client = Quotes.factory(market="std")
    code = normalize_code(symbol)
    return client.F10(symbol=code, name="最新提示") or ""
