"""
估值计算模块

提供前向PE、PE消化时间、PEG等估值指标计算。

投资框架：
壁垒 → 增速 → PE消化 → PEG校验

1. 有壁垒吗？(tech_moat / capacity_moat) → 没有则排除
2. 增速多少？(CAGR > 30% 才有意义)
3. PE多久消化到30x？(< 2年合理, > 4年太贵)
4. PEG多少？(< 1 便宜, 1-1.5 合理, > 1.5 贵)

30x PE 锚点: A股成长股的合理估值重力线
"""

import math
from typing import Optional

import akshare as ak

from .quotes import single_quote, tencent_quote
from .research import ths_consensus_eps
from .utils import get_prefix, normalize_code


def forward_pe(price: float, eps_forecast: float) -> float:
    """
    计算前向PE

    前向PE = 当前股价 / 未来年度一致预期EPS

    Args:
        price: 当前股价
        eps_forecast: 未来年度一致预期EPS

    Returns:
        前向PE值，eps_forecast <= 0 返回 inf

    Examples:
        >>> pe = forward_pe(100.0, 2.5)
        >>> print(f"前向PE: {pe}x")
    """
    if eps_forecast <= 0:
        return float("inf")
    return price / eps_forecast


def pe_digestion(
    current_pe: float,
    cagr: float,
    target_pe: float = 30,
) -> float:
    """
    计算PE消化时间

    当前PE消化到目标PE需要多少年

    Args:
        current_pe: 当前PE
        cagr: 年复合增长率（EPS增长率）
        target_pe: 目标PE，默认30x（A股成长股合理估值锚点）

    Returns:
        消化年数，current_pe <= target_pe 返回 0，cagr <= 0 返回 inf

    Examples:
        >>> years = pe_digestion(100, 0.3)
        >>> print(f"消化到30x需要: {years:.1f}年")
    """
    if current_pe <= target_pe:
        return 0.0
    if cagr <= 0:
        return float("inf")
    return math.log(current_pe / target_pe) / math.log(1 + cagr)


def calc_peg(pe: float, cagr: float) -> float:
    """
    计算PEG

    PEG = 前向PE / (CAGR * 100)

    判断标准：
    - PEG < 1: 便宜
    - PEG 1-1.5: 合理
    - PEG > 1.5: 贵

    Args:
        pe: 前向PE
        cagr: 年复合增长率（小数形式，如 0.3 表示 30%）

    Returns:
        PEG值，cagr <= 0 返回 inf

    Examples:
        >>> peg = calc_peg(50, 0.4)
        >>> print(f"PEG: {peg}")  # 1.25
    """
    if cagr <= 0:
        return float("inf")
    return pe / (cagr * 100)


def full_valuation(code: str) -> dict:
    """
    单票完整估值分析

    综合腾讯实时行情 + 机构一致预期EPS 计算估值指标

    Args:
        code: 6位股票代码

    Returns:
        dict，含字段:
        - name: 股票名称
        - price: 当前价
        - mcap_yi: 总市值(亿)
        - pe_ttm: PE(TTM)
        - pb: PB(市净率)
        - eps_cur: 今年一致预期EPS
        - eps_next: 明年一致预期EPS
        - pe_fwd: 前向PE
        - cagr_pct: EPS年复合增长率%
        - peg: PEG值
        - digest_years: PE消化年数
        - analyst_count: 预测机构数

    Examples:
        >>> result = full_valuation("688017")
        >>> print(f"{result['name']}: PE_fwd={result['pe_fwd']}x "
        >>>       f"PEG={result['peg']} 消化={result['digest_years']}年")
    """
    code = normalize_code(code)

    # 1. 腾讯实时行情
    prefix = "sh" if code.startswith(("6", "9")) else ("bj" if code.startswith("8") else "sz")
    quotes = tencent_quote([code])
    q = quotes.get(code, {})

    price = q.get("price", 0)
    mcap = q.get("mcap_yi", 0)
    pe_ttm = q.get("pe_ttm", 0)
    pb = q.get("pb", 0)

    # 2. 机构一致预期
    df = ths_consensus_eps(code, indicator="预测年报每股收益")
    eps_cur: Optional[float] = None
    eps_next: Optional[float] = None
    analyst_count = 0

    if not df.empty:
        years_sorted = sorted(df["年度"].unique())
        for _, row in df.iterrows():
            y = str(row["年度"])
            if len(years_sorted) > 0 and y == str(years_sorted[0]):
                eps_cur = float(row["均值"])
                analyst_count = int(row["预测机构数"])
            elif len(years_sorted) > 1 and y == str(years_sorted[1]):
                eps_next = float(row["均值"])

    # 3. 估值指标
    pe_fwd = price / eps_cur if eps_cur else float("inf")
    cagr = (eps_next / eps_cur - 1) if (eps_cur and eps_next) else 0
    peg = pe_fwd / (cagr * 100) if cagr > 0 else float("inf")
    digest = (
        math.log(pe_fwd / 30) / math.log(1 + cagr)
        if pe_fwd > 30 and cagr > 0 else 0
    )

    return {
        "name": q.get("name", ""),
        "price": price,
        "mcap_yi": mcap,
        "pe_ttm": pe_ttm,
        "pb": pb,
        "eps_cur": eps_cur,
        "eps_next": eps_next,
        "pe_fwd": round(pe_fwd, 1) if eps_cur else None,
        "cagr_pct": round(cagr * 100, 0) if cagr else None,
        "peg": round(peg, 2) if peg != float("inf") else None,
        "digest_years": round(digest, 1),
        "analyst_count": analyst_count,
    }


def batch_valuation(codes: list[str]) -> list[dict]:
    """
    批量估值对比

    Args:
        codes: 股票代码列表

    Returns:
        list[dict]，每项同 full_valuation 返回值

    Examples:
        >>> stocks = ["688017", "300308", "300476", "002463"]
        >>> for r in batch_valuation(stocks):
        >>>     print(f"{r['name']}: PE_fwd={r['pe_fwd']}x "
        >>>           f"PEG={r['peg']} 消化={r['digest_years']}年")
    """
    results = []
    for code in codes:
        try:
            result = full_valuation(code)
            results.append(result)
        except Exception as e:
            results.append({
                "name": code,
                "error": str(e),
            })
    return results


def valuation_summary(result: dict) -> str:
    """
    估值结果转易读文本

    Args:
        result: full_valuation 返回的dict

    Returns:
        易读的估值摘要文本

    Examples:
        >>> r = full_valuation("688017")
        >>> print(valuation_summary(r))
    """
    if "error" in result:
        return f"{result['name']}: 失败 - {result['error']}"

    name = result.get("name", "")
    pe_fwd = result.get("pe_fwd")
    peg = result.get("peg")
    digest = result.get("digest_years")
    analysts = result.get("analyst_count", 0)

    parts = [f"{name}({result['name']})"]

    if pe_fwd:
        parts.append(f"PE={pe_fwd}x")
    if peg:
        parts.append(f"PEG={peg}")
    if digest is not None:
        parts.append(f"消化={digest}年")
    if analysts:
        parts.append(f"覆盖={analysts}家")

    return " ".join(parts)
