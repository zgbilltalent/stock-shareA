"""
命令行入口

提供简单的 CLI 接口用于快速查询

Usage:
    python -m feifan_stock_data 688017
    python -m feifan_stock_data --hot
    python -m feifan_stock_data --industry
"""

import argparse
import json
import sys

from . import __version__
from . import signals as sig
from . import valuation as val
from .quotes import single_quote


def main():
    parser = argparse.ArgumentParser(
        description="A股全栈数据工具包",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("code", nargs="?", help="股票代码，如 688017")
    parser.add_argument("--quote", action="store_true", help="查询实时行情")
    parser.add_argument("--valuation", action="store_true", help="完整估值分析")
    parser.add_argument("--hot", action="store_true", help="当日强势股TOP10")
    parser.add_argument("--topics", action="store_true", help="当日TOP题材")
    parser.add_argument("--industry", action="store_true", help="行业涨跌幅排名")
    parser.add_argument("--northbound", action="store_true", help="北向资金汇总")
    parser.add_argument("--lhb", action="store_true", help="全市场龙虎榜TOP10")
    parser.add_argument("--limit", type=int, default=10, help="返回数量限制")

    args = parser.parse_args()

    # 无参数时显示帮助
    if len(sys.argv) == 1:
        parser.print_help()
        return

    # 单票查询
    if args.code:
        if args.valuation:
            r = val.full_valuation(args.code)
            print(json.dumps(r, ensure_ascii=False, indent=2))
        elif args.quote:
            q = single_quote(args.code)
            print(json.dumps(q, ensure_ascii=False, indent=2))
        else:
            # 默认显示完整估值
            r = val.full_valuation(args.code)
            print(val.valuation_summary(r))

    # 信号查询
    if args.hot:
        df = sig.ths_hot_reason()
        if df.empty:
            print("暂无数据（非交易日或盘后未更新）")
        else:
            print(f"当日强势股共 {len(df)} 只:")
            cols = ["代码", "名称", "涨幅%", "题材归因"]
            available_cols = [c for c in cols if c in df.columns]
            print(df[available_cols].head(args.limit).to_string(index=False))

    if args.topics:
        topics = sig.hot_topics(args.limit)
        print(f"当日TOP{args.limit}题材热度:")
        for tag, cnt in topics:
            print(f"  {tag}: {cnt} 只")

    if args.industry:
        data = sig.industry_comparison(args.limit)
        print(f"共 {data['total']} 个行业")
        print("\n涨幅TOP10:")
        for r in data["top"][:10]:
            print(f"  {r['rank']:2d}. {r['name']}: {r['change_pct']:+.2f}% 领涨{r['leader']}")
        print("\n跌幅TOP5:")
        for r in data["bottom"][-5:]:
            print(f"  {r['rank']:2d}. {r['name']}: {r['change_pct']:+.2f}%")

    if args.northbound:
        summary = sig.northbound_summary()
        if summary["total"] is None:
            print("暂无数据")
        else:
            signal = {
                "bullish": "偏多",
                "bearish": "偏空",
                "neutral": "中性",
            }.get(summary["signal"], "未知")
            print(f"北向资金汇总:")
            print(f"  沪股通: {summary['hgt_today']:.1f} 亿")
            print(f"  深股通: {summary['sgt_today']:.1f} 亿")
            print(f"  合计: {summary['total']:.1f} 亿 [{signal}]")

    if args.lhb:
        data = sig.daily_dragon_tiger(min_net_buy=1000)
        if data["total_records"] == 0:
            print("暂无数据（非交易日或盘后未更新）")
        else:
            print(f"{data['date']} 龙虎榜共 {data['total_records']} 条记录:")
            for s in data["stocks"][:args.limit]:
                print(f"  {s['code']} {s['name']}: {s['reason'][:20] if s['reason'] else 'N/A'}")
                print(f"    净买{s['net_buy_wan']:.0f}万 涨跌{s['change_pct']:+.2f}%")


if __name__ == "__main__":
    main()
