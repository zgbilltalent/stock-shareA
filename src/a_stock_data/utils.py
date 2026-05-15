"""
工具函数模块

提供代码归一化、市场前缀转换等通用工具函数。
"""

from typing import Literal


def get_prefix(code: str) -> Literal["sh", "sz", "bj"]:
    """
    6位代码 → 市场前缀

    Args:
        code: 6位股票代码

    Returns:
        "sh" (上海/科创板), "sz" (深圳/创业板), "bj" (北交所)

    Examples:
        >>> get_prefix("688017")
        'sh'
        >>> get_prefix("300476")
        'sz'
        >>> get_prefix("832000")
        'bj'
    """
    code = code.strip()
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith("8"):
        return "bj"
    else:
        return "sz"


def normalize_code(code: str) -> str:
    """
    股票代码归一化为纯6位数字

    支持格式:
    - 688017
    - SH688017 / sh688017
    - 688017.SH / 688017.sh
    - SZ000001
    - BJ832000

    Args:
        code: 各种格式的股票代码

    Returns:
        归一化的6位股票代码

    Examples:
        >>> normalize_code("688017")
        '688017'
        >>> normalize_code("SH688017")
        '688017'
        >>> normalize_code("688017.SH")
        '688017'
    """
    # 移除常见前缀后缀
    code = code.strip().upper()
    code = code.replace("SH", "").replace("SZ", "").replace("BJ", "")
    code = code.replace("sh", "").replace("sz", "").replace("bj", "")
    code = code.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    code = code.replace(".sh", "").replace(".sz", "").replace(".bj", "")
    code = code.strip(".")
    return code


def get_market(code: str) -> Literal["沪市", "深市", "北交所"]:
    """
    根据代码判断市场

    Args:
        code: 6位股票代码

    Returns:
        "沪市" / "深市" / "北交所"

    Examples:
        >>> get_market("688017")
        '沪市'
        >>> get_market("300476")
        '深市'
        >>> get_market("832000")
        '北交所'
    """
    code = normalize_code(code)
    if code.startswith("6"):
        return "沪市"
    elif code.startswith("8"):
        return "北交所"
    else:
        return "深市"


def get_mootdx_market(code: str) -> int:
    """
    获取 mootdx 所需的市场参数

    Args:
        code: 6位股票代码

    Returns:
        0=深圳, 1=上海

    Examples:
        >>> get_mootdx_market("300476")
        0
        >>> get_mootdx_market("688017")
        1
    """
    code = normalize_code(code)
    if code.startswith("6"):
        return 1
    return 0
