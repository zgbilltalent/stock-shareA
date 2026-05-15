"""
feifan_stock_data - A股全栈数据工具包

六层数据架构，21 个端点。
覆盖行情(mootdx+腾讯)、研报(东财+iwencai)、信号(同花顺热点+北向+百度PAE+龙虎榜+解禁+行业)、
新闻(akshare)、基础数据(mootdx财务/F10)、公告(巨潮)六层数据源。

快速开始:

    from feifan_stock_data import quotes, signals, valuation

    # 拉取实时行情
    q = quotes.tencent_quote(["688017", "300476"])

    # 获取当日强势股题材归因
    df = signals.ths_hot_reason()

    # 单票完整估值分析
    result = valuation.full_valuation("688017")

Web 服务:

    from feifan_stock_data.web import run
    run()  # 启动 Web 服务，访问 http://localhost:5000
"""

__version__ = "2.1.0"
__author__ = "Simon Lin"

from . import quotes
from . import research
from . import news
from . import fundamental
from . import disclosure
from . import signals
from . import valuation
from . import utils
from . import web
from .cli import main as cli_main

__all__ = [
    # Version
    "__version__",
    # Submodules
    "quotes",
    "research",
    "news",
    "fundamental",
    "disclosure",
    "signals",
    "valuation",
    "utils",
    "web",
    # CLI
    "cli_main",
]
