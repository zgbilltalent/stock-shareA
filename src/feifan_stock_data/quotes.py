"""
行情层模块

提供 K线、五档盘口、逐笔成交、PE/PB/市值/换手率/涨跌停 等实时行情数据。

数据源:
- mootdx: K线 + 五档盘口 + 逐笔成交 (TCP 7709)
- 腾讯财经 API: PE/PB/市值/换手率/涨跌停 (HTTP)
"""

import urllib.request
from typing import Optional

import pandas as pd

from .utils import get_prefix, normalize_code

# HTTP 请求头
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# 通达信行情服务器备选（Docker 内 bestip 常无法选服，需显式指定）
_DEFAULT_TDX_SERVERS = [
    ("119.147.212.81", 7709),
    ("114.80.63.12", 7709),
    ("218.75.126.9", 7709),
    ("124.74.236.94", 7709),
]

_mootdx_client_cache = None


def _parse_tdx_server_env() -> tuple[str, int] | None:
    """MOOTDX_SERVER=host:port 可选覆盖"""
    import os

    raw = os.environ.get("MOOTDX_SERVER", "").strip()
    if not raw or ":" not in raw:
        return None
    host, _, port_s = raw.partition(":")
    try:
        return host.strip(), int(port_s.strip())
    except ValueError:
        return None


def _mootdx_client():
    """
    获取 mootdx Quotes 客户端实例（带连接缓存与备选服务器）

    Returns:
        mootdx.quotes.Quotes 实例

    Raises:
        RuntimeError: 所有服务器均不可达
    """
    global _mootdx_client_cache
    if _mootdx_client_cache is not None:
        return _mootdx_client_cache

    from mootdx.quotes import Quotes

    candidates: list[tuple | None] = []
    env_server = _parse_tdx_server_env()
    if env_server:
        candidates.append(env_server)
    candidates.append(None)  # 默认 bestip
    candidates.extend(_DEFAULT_TDX_SERVERS)

    last_err: Exception | None = None
    for server in candidates:
        try:
            if server is None:
                client = Quotes.factory(market="std")
            else:
                client = Quotes.factory(market="std", server=server)
            _mootdx_client_cache = client
            return client
        except (ValueError, TypeError, OSError, TimeoutError) as e:
            last_err = e
            # Docker 内常见: not enough values to unpack (expected 2, got 0)
            continue

    raise RuntimeError(
        "无法连接通达信行情服务器（mootdx）。"
        "Docker/海外网络可设置环境变量 MOOTDX_SERVER=119.147.212.81:7709 后重启 web 容器。"
    ) from last_err


def klines(
    symbol: str,
    category: int = 4,
    offset: int = 10,
    market: Optional[int] = None,
) -> pd.DataFrame:
    """
    获取K线数据

    Args:
        symbol: 6位股票代码
        category: K线类型
            - 4=日线, 5=周线, 6=月线
            - 7=1分钟, 8=5分钟, 9=15分钟
            - 10=30分钟, 11=60分钟
        offset: 返回数量
        market: 市场代码 (0=深圳, 1=上海)，自动推断

    Returns:
        DataFrame，含字段: open, close, high, low, vol, amount, datetime

    Examples:
        >>> df = klines("688017", category=4, offset=10)
        >>> print(df.head())
    """
    from .utils import get_mootdx_market

    client = _mootdx_client()
    if market is None:
        market = get_mootdx_market(symbol)
    return client.bars(symbol=normalize_code(symbol), category=category, offset=offset)


def realtime_quotes(symbols: list[str]) -> pd.DataFrame:
    """
    获取实时报价（五档盘口）

    Args:
        symbols: 股票代码列表，如 ["688017", "300476"]

    Returns:
        DataFrame，46个字段:
        price(现价), open, high, low, last_close(昨收)
        bid1~bid5, ask1~ask5, bid_vol1~bid_vol5, ask_vol1~ask_vol5
        vol(成交量), amount(成交额), servertime

    Examples:
        >>> df = realtime_quotes(["688017", "300476"])
        >>> print(df[["code", "name", "price"]])
    """
    codes = [normalize_code(s) for s in symbols]
    client = _mootdx_client()
    return client.quotes(symbol=codes)


def transaction(symbol: str, date: str) -> pd.DataFrame:
    """
    获取逐笔成交数据（非交易时间返回空）

    Args:
        symbol: 6位股票代码
        date: 日期，YYYYMMDD 格式，如 "20260502"

    Returns:
        DataFrame，含字段: time, price, vol, num, buyorsell(0买/1卖/2中性)

    Examples:
        >>> df = transaction("688017", "20260502")
        >>> print(df.head())
    """
    from .utils import get_mootdx_market

    client = _mootdx_client()
    market = get_mootdx_market(symbol)
    return client.transaction(symbol=normalize_code(symbol), date=date)


def tencent_quote(codes: list[str]) -> dict[str, dict]:
    """
    批量拉取腾讯财经实时行情

    提供 PE/PB/市值/换手率/涨跌停 等估值数据

    Args:
        codes: 股票代码列表，如 ["688017", "300476", "002463"]

    Returns:
        dict[code, dict]，每个dict含字段:
        - name: 股票名称
        - price: 当前价
        - last_close: 昨收价
        - open: 今开
        - change_amt: 涨跌额
        - change_pct: 涨跌幅%
        - high: 最高价
        - low: 最低价
        - amount_wan: 成交额(万)
        - turnover_pct: 换手率%
        - pe_ttm: PE(TTM)
        - amplitude_pct: 振幅%
        - mcap_yi: 总市值(亿)
        - float_mcap_yi: 流通市值(亿)
        - pb: PB(市净率)
        - limit_up: 涨停价
        - limit_down: 跌停价
        - vol_ratio: 量比
        - pe_static: PE(静)

    Examples:
        >>> quotes = tencent_quote(["688017", "300476"])
        >>> for code, q in quotes.items():
        >>>     print(f"{q['name']}({code}): {q['price']}元 PE={q['pe_ttm']} PB={q['pb']} 市值={q['mcap_yi']}亿")
    """
    prefixed = []
    for c in codes:
        c = normalize_code(c)
        prefix = get_prefix(c)
        prefixed.append(f"{prefix}{c}")

    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")

    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]  # 去掉 sh/sz/bj 前缀
        result[code] = {
            "name": vals[1],
            "price": float(vals[3]) if vals[3] else 0,
            "last_close": float(vals[4]) if vals[4] else 0,
            "open": float(vals[5]) if vals[5] else 0,
            "change_amt": float(vals[31]) if vals[31] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "high": float(vals[33]) if vals[33] else 0,
            "low": float(vals[34]) if vals[34] else 0,
            "volume": float(vals[36]) if vals[36] else 0,
            "amount_wan": float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "amplitude_pct": float(vals[43]) if vals[43] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
            "float_mcap_yi": float(vals[45]) if vals[45] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "limit_up": float(vals[47]) if vals[47] else 0,
            "limit_down": float(vals[48]) if vals[48] else 0,
            "vol_ratio": float(vals[49]) if vals[49] else 0,
            "pe_static": float(vals[52]) if vals[52] else 0,
        }
    return result


def single_quote(code: str) -> dict:
    """
    获取单只股票腾讯财经实时行情

    Args:
        code: 6位股票代码

    Returns:
        dict，同 tencent_quote 返回的单个股票数据

    Examples:
        >>> q = single_quote("688017")
        >>> print(f"价格: {q['price']}, PE: {q['pe_ttm']}")
    """
    result = tencent_quote([code])
    return result.get(normalize_code(code), {})
