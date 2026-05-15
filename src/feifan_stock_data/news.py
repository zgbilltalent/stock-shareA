"""
新闻层模块

提供个股新闻、财联社快讯、东财全球资讯等新闻数据。

数据源:
- akshare stock_news_em: 个股新闻 (东财)
- akshare stock_info_global_cls: 财联社快讯
- akshare stock_info_global_em: 东财全球资讯
"""

import akshare as ak
import pandas as pd

from .utils import normalize_code


def stock_news(symbol: str) -> pd.DataFrame:
    """
    获取个股新闻（东财来源）

    Args:
        symbol: 6位股票代码

    Returns:
        DataFrame，列: 新闻标题, 新闻内容, 发布时间, 文章来源, 新闻链接

    Examples:
        >>> df = stock_news("688017")
        >>> print(df.head())
    """
    code = normalize_code(symbol)
    return ak.stock_news_em(symbol=code)


def cls_flash_news() -> pd.DataFrame:
    """
    获取财联社快讯

    Returns:
        DataFrame，列: 标题, 内容, 发布时间
        更新频率极高（分钟级）

    Examples:
        >>> df = cls_flash_news()
        >>> print(df.head(10))
    """
    return ak.stock_info_global_cls()


def em_global_news() -> pd.DataFrame:
    """
    获取东财全球资讯

    Returns:
        DataFrame，列: 标题, 摘要, 发布时间, 链接

    Examples:
        >>> df = em_global_news()
        >>> print(df.head())
    """
    return ak.stock_info_global_em()
