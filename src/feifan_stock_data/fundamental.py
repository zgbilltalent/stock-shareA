"""
基础数据层模块

提供财务快照、公司资料、个股基本面等数据。

数据源:
- mootdx finance: 季报快照 (37字段)
- mootdx F10: 公司资料 (9大类文本)
- akshare: 个股基本面
"""

import akshare as ak
import pandas as pd

from .utils import get_mootdx_market, normalize_code


def _mootdx_client():
    """获取 mootdx Quotes 客户端实例"""
    from mootdx.quotes import Quotes

    return Quotes.factory(market="std")


def finance_snapshot(symbol: str) -> pd.DataFrame:
    """
    获取财务季报快照（37字段）

    Args:
        symbol: 6位股票代码

    Returns:
        DataFrame，含37个财务字段:
        liutongguben(流通股本), zongguben(总股本)
        eps(每股收益), bvps(每股净资产), roe(净资产收益率%)
        profit(净利润), income(主营收入)
        meigujingzichan(每股净资产), meigugongjijin(每股公积金)
        meiguweifeipeili(每股未分配利润)
        等37个季报财务字段

    Examples:
        >>> df = finance_snapshot("688017")
        >>> print(df[["eps", "roe", "profit"]])
    """
    client = _mootdx_client()
    code = normalize_code(symbol)
    return client.finance(symbol=code)


def f10_company_info(symbol: str, category: str = "最新提示") -> str:
    """
    获取F10公司资料

    Args:
        symbol: 6位股票代码
        category: 资料类别
            - "最新提示"
            - "公司概况"
            - "财务分析"
            - "股东研究"
            - "股本结构"
            - "资本运作"
            - "业内点评"
            - "行业分析"
            - "公司大事"

    Returns:
        文本内容（截断后约2000字符）

    Examples:
        >>> text = f10_company_info("688017", "公司概况")
        >>> print(text[:500])
    """
    client = _mootdx_client()
    code = normalize_code(symbol)
    text = client.F10(symbol=code, name=category)
    # V2.1 截断优化：股东研究含大量历史列表，截断至合理长度
    if text and len(text) > 2000:
        text = text[:2000] + "\n...(已截断)"
    return text or ""


def f10_all_categories(symbol: str) -> dict[str, str]:
    """
    获取F10所有类别资料

    Args:
        symbol: 6位股票代码

    Returns:
        dict[category, content]，9大类的文本内容

    Examples:
        >>> data = f10_all_categories("688017")
        >>> for cat, text in data.items():
        >>>     print(f"=== {cat} ===")
        >>>     print(text[:200])
    """
    categories = [
        "最新提示",
        "公司概况",
        "财务分析",
        "股东研究",
        "股本结构",
        "资本运作",
        "业内点评",
        "行业分析",
        "公司大事",
    ]

    client = _mootdx_client()
    code = normalize_code(symbol)
    result = {}

    for cat in categories:
        text = client.F10(symbol=code, name=cat)
        # V2.1 截断优化
        if text and len(text) > 2000:
            text = text[:2000] + "\n...(已截断)"
        result[cat] = text or ""

    return result


def individual_info(symbol: str) -> pd.DataFrame:
    """
    获取个股基本面信息

    Args:
        symbol: 6位股票代码

    Returns:
        DataFrame，2列格式 (item / value)
        含: 股票代码, 股票简称, 总股本, 流通股, 总市值(元), 流通市值(元), 行业, 上市时间
        注意: 市值单位是"元"不是亿元

    Examples:
        >>> df = individual_info("688017")
        >>> print(df[df["item"].str.contains("市值|行业")])
    """
    code = normalize_code(symbol)
    return ak.stock_individual_info_em(symbol=code)


def _df_item_value_to_dict(df: pd.DataFrame) -> dict:
    """akshare item/value 两列 DataFrame → dict"""
    if df is None or df.empty:
        return {}
    cols = {c.lower(): c for c in df.columns}
    item_col = cols.get("item") or cols.get("项目")
    val_col = cols.get("value") or cols.get("值")
    if item_col and val_col:
        return {
            str(row[item_col]): row[val_col]
            for _, row in df.iterrows()
        }
    return df.iloc[0].to_dict() if len(df) else {}


def get_stock_info(symbol: str) -> dict:
    """个股基本信息（东财 item/value 格式）"""
    try:
        return _df_item_value_to_dict(individual_info(symbol))
    except Exception:
        return {}


def get_financial_indicators(symbol: str) -> dict:
    """季报财务快照（mootdx 37 字段）"""
    try:
        df = finance_snapshot(symbol)
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            return {}
        if isinstance(df, pd.DataFrame):
            return df.iloc[-1].to_dict() if len(df) else {}
        return dict(df) if df else {}
    except Exception:
        return {}


def main_index(symbol: str) -> dict:
    """主要财务指标摘要"""
    snap = get_financial_indicators(symbol)
    if not snap:
        return {}
    keys = (
        "eps", "roe", "profit", "income", "bvps",
        "meigujingzichan", "liutongguben", "zongguben",
    )
    return {k: snap[k] for k in keys if k in snap and snap[k] is not None}
