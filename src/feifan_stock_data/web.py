"""
Web 应用入口 - A股全栈数据工具包

提供 Web API 和可视化界面，自动将数据持久化到 MySQL。

Usage:
    python -m feifan_stock_data.web
"""

import json
import traceback
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

_HERE = Path(__file__).resolve().parent

app = Flask(__name__,
            template_folder=str(_HERE / 'templates'),
            static_folder=str(_HERE / 'static'))
CORS(app)

from . import signals as sig
from . import valuation as val
from .quotes import single_quote, tencent_quote
from . import __version__
from . import db


def format_response(data, success=True, message=""):
    """统一响应格式"""
    return jsonify({
        "success": success,
        "message": message,
        "data": data
    })


def _db_save(func, *args, **kwargs):
    """安全执行数据库存储，失败不影响 API 响应"""
    try:
        func(*args, **kwargs)
    except Exception as e:
        app.logger.warning(f"DB save failed: {e}")


# ==================== 行情 API ====================

@app.route('/api/quote/<code>')
def api_quote(code):
    """单股票实时行情"""
    try:
        data = single_quote(code)
        data["code"] = code
        _db_save(db.save_quote, data)
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/quotes', methods=['POST'])
def api_quotes():
    """批量股票实时行情"""
    try:
        codes = request.json.get('codes', [])
        data = tencent_quote(codes)
        _db_save(db.save_quotes, data)
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


# ==================== 估值 API ====================

@app.route('/api/valuation/<code>')
def api_valuation(code):
    """单股票完整估值"""
    try:
        data = val.full_valuation(code)
        _db_save(db.save_valuation, code, data)
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/valuation/summary/<code>')
def api_valuation_summary(code):
    """单股票估值摘要"""
    try:
        data = val.full_valuation(code)
        summary = val.valuation_summary(data)
        _db_save(db.save_valuation, code, data)
        return format_response({"raw": data, "summary": summary})
    except Exception as e:
        return format_response(None, False, str(e))


# ==================== 信号 API ====================

@app.route('/api/signals/hot')
def api_signals_hot():
    """当日强势股"""
    try:
        limit = request.args.get('limit', 10, type=int)
        df = sig.ths_hot_reason()
        if df.empty:
            return format_response([], True, "暂无数据（非交易日或盘后未更新）")
        cols = ["代码", "名称", "涨幅%", "题材归因"]
        available_cols = [c for c in cols if c in df.columns]
        data = df[available_cols].head(limit).to_dict('records')
        _db_save(db.save_hot_stocks, df)
        return format_response(data, True, f"共 {len(df)} 只")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/signals/topics')
def api_signals_topics():
    """当日TOP题材"""
    try:
        limit = request.args.get('limit', 10, type=int)
        topics = sig.hot_topics(limit)
        data = [{"topic": tag, "count": cnt} for tag, cnt in topics]
        _db_save(db.save_hot_topics, topics)
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/signals/industry')
def api_signals_industry():
    """行业涨跌幅"""
    try:
        limit = request.args.get('limit', 10, type=int)
        data = sig.industry_comparison(limit)
        _db_save(db.save_industry, data)
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/signals/northbound')
def api_signals_northbound():
    """北向资金汇总"""
    try:
        data = sig.northbound_summary()
        signal_map = {
            "bullish": "偏多",
            "bearish": "偏空",
            "neutral": "中性",
        }
        data['signal_cn'] = signal_map.get(data.get("signal", ""), "未知")
        _db_save(db.save_northbound, data)
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/signals/dragon_tiger')
def api_signals_dragon_tiger():
    """龙虎榜"""
    try:
        limit = request.args.get('limit', 10, type=int)
        data = sig.daily_dragon_tiger(min_net_buy=1000)
        stocks = data.get("stocks", [])[:limit]
        _db_save(db.save_dragon_tiger, data)
        return format_response({
            "date": data.get("date"),
            "total_records": data.get("total_records"),
            "stocks": stocks
        })
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/signals/unlock')
def api_signals_unlock():
    """解禁信息"""
    try:
        limit = request.args.get('limit', 10, type=int)
        df = sig.unlock_calendar()
        if df.empty:
            return format_response([], True, "暂无数据")
        cols = ["股票代码", "股票简称", "解禁日期", "解禁数量_万股", "解禁市值_万元", "解禁股份类型"]
        available_cols = [c for c in cols if c in df.columns]
        data = df[available_cols].head(limit).to_dict('records')
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


# ==================== 研报 API ====================

@app.route('/api/research/stock/<code>')
def api_research_stock(code):
    """个股研报"""
    try:
        from . import research
        data = research.em_report(code)
        _db_save(db.save_research, code, data if isinstance(data, list) else [data])
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


# ==================== 新闻 API ====================

@app.route('/api/news/market')
def api_news_market():
    """市场快讯"""
    try:
        from . import news
        limit = request.args.get('limit', 20, type=int)
        df = news.market_news(limit)
        if df.empty:
            return format_response([], True, "暂无数据")
        cols = ["发布时间", "新闻标题", "文章来源"]
        available_cols = [c for c in cols if c in df.columns]
        data = df[available_cols].to_dict('records')
        _db_save(db.save_news, df)
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


# ==================== 公告 API ====================

@app.route('/api/disclosure/<code>')
def api_disclosure(code):
    """个股公告"""
    try:
        from . import disclosure
        limit = request.args.get('limit', 10, type=int)
        df = disclosure.juchao_announcement(code, limit)
        if df.empty:
            return format_response([], True, "暂无数据")
        cols = ["公告标题", "公告时间", "pdf链接"]
        available_cols = [c for c in cols if c in df.columns]
        data = df[available_cols].to_dict('records')
        _db_save(db.save_announcement, code, df)
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


# ==================== 基础数据 API ====================

@app.route('/api/fundamental/<code>')
def api_fundamental(code):
    """个股基础数据"""
    try:
        from . import fundamental
        data = {
            "basic": fundamental.get_stock_info(code),
            "indicators": fundamental.get_financial_indicators(code),
            "main_index": fundamental.main_index(code),
        }
        _db_save(db.save_fundamental, code, data)
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


# ==================== 历史 API ====================

@app.route('/api/history/quote/<code>')
def api_history_quote(code):
    """查询个股行情历史"""
    try:
        limit = request.args.get('limit', 30, type=int)
        data = db.query_quote_history(code, limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/history/valuation/<code>')
def api_history_valuation(code):
    """查询个股估值历史"""
    try:
        limit = request.args.get('limit', 30, type=int)
        data = db.query_valuation_history(code, limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/history/northbound')
def api_history_northbound():
    """查询北向资金历史"""
    try:
        limit = request.args.get('limit', 30, type=int)
        data = db.query_northbound_history(limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/history/dragon_tiger')
def api_history_dragon_tiger():
    """查询龙虎榜历史"""
    try:
        limit = request.args.get('limit', 30, type=int)
        data = db.query_dragon_tiger_history(limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/history/hot_stock')
def api_history_hot_stock():
    """查询强势股历史"""
    try:
        code = request.args.get('code')
        limit = request.args.get('limit', 50, type=int)
        data = db.query_hot_stock_history(code, limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/history/topics')
def api_history_topics():
    """查询热门题材历史"""
    try:
        limit = request.args.get('limit', 30, type=int)
        data = db.query_topic_history(limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/history/industry')
def api_history_industry():
    """查询行业涨跌历史"""
    try:
        limit = request.args.get('limit', 30, type=int)
        data = db.query_industry_history(limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/history/research')
def api_history_research():
    """查询研报历史"""
    try:
        code = request.args.get('code')
        limit = request.args.get('limit', 30, type=int)
        data = db.query_research_history(code, limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/history/news')
def api_history_news():
    """查询新闻历史"""
    try:
        limit = request.args.get('limit', 50, type=int)
        data = db.query_news_history(limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/history/announcement')
def api_history_announcement():
    """查询公告历史"""
    try:
        code = request.args.get('code')
        limit = request.args.get('limit', 30, type=int)
        data = db.query_announcement_history(code, limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/history/fundamental')
def api_history_fundamental():
    """查询基础数据历史"""
    try:
        code = request.args.get('code')
        limit = request.args.get('limit', 30, type=int)
        data = db.query_fundamental_history(code, limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


# ==================== 系统 API ====================

@app.route('/api/version')
def api_version():
    """版本信息"""
    return format_response({"version": __version__})


@app.route('/api/health')
def api_health():
    """健康检查（含数据库状态）"""
    db_ok = db.check_connection()
    return format_response({
        "status": "ok",
        "database": "connected" if db_ok else "disconnected",
    })


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """主页"""
    return render_template('index.html', version=__version__)


# ==================== 启动 ====================

def run(host='0.0.0.0', port=5000, debug=None):
    """启动 Web 服务"""
    import os
    if debug is None:
        debug = os.environ.get("FLASK_ENV", "development") == "development"
    # 启动时自动初始化数据库
    try:
        db.init_db()
        app.logger.info("Database initialized successfully")
    except Exception as e:
        app.logger.warning(f"Database init failed: {e}")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run()
