"""
使用示例脚本

演示 feifan_stock_data 包的主要功能。
"""

from feifan_stock_data import quotes, signals, valuation


def demo_quotes():
    """演示行情查询"""
    print("\n" + "=" * 60)
    print("1. 行情查询")
    print("=" * 60)

    # 腾讯财经实时行情
    codes = ["688017", "300476", "002463"]
    quotes_data = quotes.tencent_quote(codes)

    for code, q in quotes_data.items():
        print(
            f"{q['name']}({code}): "
            f"价格={q['price']}元 "
            f"PE={q['pe_ttm']} "
            f"PB={q['pb']} "
            f"市值={q['mcap_yi']}亿"
        )


def demo_signals():
    """演示信号查询"""
    print("\n" + "=" * 60)
    print("2. 信号查询")
    print("=" * 60)

    # 当日强势股
    print("\n--- 同花顺热点TOP10 ---")
    df = signals.ths_hot_reason()
    if not df.empty:
        cols = ["代码", "名称", "涨幅%", "题材归因"]
        available = [c for c in cols if c in df.columns]
        print(df[available].head(10).to_string(index=False))
    else:
        print("暂无数据（非交易日或盘后未更新）")

    # TOP题材
    print("\n--- 当日TOP10题材 ---")
    topics = signals.hot_topics(10)
    for tag, cnt in topics:
        print(f"  {tag}: {cnt} 只")

    # 北向资金
    print("\n--- 北向资金汇总 ---")
    summary = signals.northbound_summary()
    if summary["total"] is not None:
        print(f"  沪股通: {summary['hgt_today']:.1f} 亿")
        print(f"  深股通: {summary['sgt_today']:.1f} 亿")
        print(f"  合计: {summary['total']:.1f} 亿 [{summary['signal']}]")
    else:
        print("暂无数据")


def demo_valuation():
    """演示估值分析"""
    print("\n" + "=" * 60)
    print("3. 估值分析")
    print("=" * 60)

    codes = ["688017", "300476"]
    for code in codes:
        try:
            result = valuation.full_valuation(code)
            summary = valuation.valuation_summary(result)
            print(f"\n{summary}")
        except Exception as e:
            print(f"\n{code}: 查询失败 - {e}")


def main():
    """运行所有演示"""
    print("A股全栈数据工具包 - 使用示例")
    print("=" * 60)

    demo_quotes()
    demo_signals()
    demo_valuation()

    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
