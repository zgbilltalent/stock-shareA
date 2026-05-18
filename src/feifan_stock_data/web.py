"""
Web 应用入口 - A股全栈数据工具包

提供 Web API 和可视化界面，自动将数据持久化到 MySQL。

Usage:
    python -m feifan_stock_data.web
"""

import json
import hashlib
import secrets
import traceback
from pathlib import Path
from flask import Flask, render_template, jsonify, request, session, make_response
from flask_cors import CORS
from datetime import timedelta

_HERE = Path(__file__).resolve().parent

app = Flask(__name__,
            template_folder=str(_HERE / 'templates'),
            static_folder=str(_HERE / 'static'))
CORS(app, supports_credentials=True)
app.secret_key = secrets.token_hex(32)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

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


def _log_search(keyword: str, search_type: str, result=None):
    """记录搜索行为（仅记录股票搜索，跳过信号类）"""
    if search_type == "signals":
        return
    try:
        result_summary = None
        if result is not None:
            # 只存摘要，避免存大数据
            if isinstance(result, dict):
                result_summary = json.dumps(
                    {k: v for k, v in result.items() if k in ("name", "price", "change_pct", "pe_ttm", "pb")},
                    ensure_ascii=False,
                ) if result else None
            elif isinstance(result, list):
                result_summary = json.dumps({"count": len(result)}, ensure_ascii=False)
        ip = request.remote_addr if request else None
        db.save_search(keyword, search_type, result_summary, ip)
    except Exception as e:
        app.logger.warning(f"Search log failed: {e}")


# ==================== 行情 API ====================

@app.route('/api/quote/<code>')
def api_quote(code):
    """单股票实时行情"""
    try:
        data = single_quote(code)
        data["code"] = code
        _db_save(db.save_quote, data)
        _log_search(code, "quote", data)
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


# ==================== K线 & 逐笔成交 API ====================

@app.route('/api/kline/<code>')
def api_kline(code):
    """个股K线数据"""
    try:
        from .quotes import klines
        category = request.args.get('category', 4, type=int)  # 4=日线
        offset = request.args.get('offset', 120, type=int)
        df = klines(code, category=category, offset=offset)
        if df is None or df.empty:
            return format_response([], True, "暂无K线数据")
        # 统一字段名为前端友好的格式
        df = df.rename(columns={
            "open": "open", "close": "close", "high": "high", "low": "low",
            "vol": "volume", "amount": "amount",
        })
        cols = ["open", "close", "high", "low", "volume", "amount"]
        available = [c for c in cols if c in df.columns]
        # 确保索引为日期字符串
        if hasattr(df.index, "strftime"):
            df["_datetime"] = df.index.strftime("%Y-%m-%d %H:%M")
        else:
            df["_datetime"] = df.index.astype(str)
        result = df[["_datetime"] + available].to_dict("records")
        return format_response(result)
    except Exception as e:
        msg = str(e)
        if "unpack" in msg or "通达信" in msg or "mootdx" in msg.lower():
            msg = (
                "K线服务暂不可用：无法连接通达信行情服务器。"
                "若在 Docker 中运行，请在 docker-compose.yml 的 web 服务下添加 "
                "MOOTDX_SERVER=119.147.212.81:7709 后执行 docker compose restart web"
            )
        return format_response(None, False, msg)


@app.route('/api/transaction/<code>')
def api_transaction(code):
    """个股逐笔成交"""
    try:
        from .quotes import transaction
        from datetime import datetime
        date = request.args.get('date', '').strip()
        if not date:
            date = datetime.now().strftime("%Y%m%d")
        df = transaction(code, date)
        if df is None or df.empty:
            return format_response([], True, "暂无成交数据（非交易时间或无数据）")
        df = df.rename(columns={
            "buyorsell": "direction",
        })
        cols = ["time", "price", "vol", "num", "direction"]
        available = [c for c in cols if c in df.columns]
        data = df[available].to_dict("records")
        return format_response(data)
    except Exception as e:
        msg = str(e)
        if "unpack" in msg or "通达信" in msg or "mootdx" in msg.lower():
            msg = (
                "逐笔成交暂不可用：无法连接通达信行情服务器。"
                "若在 Docker 中运行，请设置 MOOTDX_SERVER=119.147.212.81:7709 并重启 web 容器；"
                "非交易时间也可能无数据。"
            )
        return format_response(None, False, msg)


# ==================== 估值 API ====================

@app.route('/api/valuation/<code>')
def api_valuation(code):
    """单股票完整估值"""
    try:
        data = val.full_valuation(code)
        data["summary"] = val.valuation_summary(data)
        _db_save(db.save_valuation, code, data)
        _log_search(code, "valuation", data)
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
        _log_search(code, "valuation", data)
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
        _log_search("强势股", "signals", data)
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
        _log_search("热门题材", "signals", data)
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
        data['intraday'] = sig.northbound_intraday()
        _db_save(db.save_northbound, data)
        _log_search("北向资金", "signals", data)
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/signals/concept/<code>')
def api_signals_concept(code):
    """个股概念板块归属（百度股市通）"""
    try:
        data = sig.baidu_concept_blocks(code)
        _log_search(code, "concept", data)
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/signals/fund_flow/<code>')
def api_signals_fund_flow(code):
    """个股资金流向（日级 + 可选分钟级）"""
    try:
        from datetime import datetime
        days = request.args.get('days', 20, type=int)
        include_realtime = request.args.get('realtime', '0') == '1'
        history = sig.baidu_fund_flow_history(code, days=days)
        result = {"history": history}
        if include_realtime:
            date_str = datetime.now().strftime("%Y%m%d")
            result["realtime"] = sig.baidu_fund_flow_realtime(code, date_str)
        _log_search(code, "fund_flow", {"count": len(history)})
        return format_response(result)
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/signals/dragon_tiger/<code>')
def api_signals_dragon_tiger_stock(code):
    """个股龙虎榜（上榜记录 + 席位 + 机构）"""
    try:
        from datetime import datetime
        look_back = request.args.get('look_back', 30, type=int)
        trade_date = request.args.get('date', '').strip()
        if not trade_date:
            trade_date = datetime.now().strftime("%Y-%m-%d")
        data = sig.dragon_tiger_board(code, trade_date, look_back=look_back)
        _log_search(code, "dragon_tiger", data)
        return format_response(data)
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/signals/lockup/<code>')
def api_signals_lockup_stock(code):
    """个股限售解禁（历史 + 未来90天）"""
    try:
        from datetime import datetime
        forward_days = request.args.get('forward_days', 90, type=int)
        trade_date = request.args.get('date', '').strip()
        if not trade_date:
            trade_date = datetime.now().strftime("%Y-%m-%d")
        data = sig.lockup_expiry(code, trade_date, forward_days=forward_days)
        _log_search(code, "lockup", data)
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
        data = research.eastmoney_reports(code)
        # 映射为统一字段
        result = []
        for r in (data or []):
            result.append({
                "title": r.get("title", ""),
                "org": r.get("orgSName", ""),
                "rating": r.get("emRatingName", ""),
                "date": (r.get("publishDate", "") or "")[:10],
                "infoCode": r.get("infoCode", ""),
                "industry": r.get("indvInduName", ""),
                "eps_this_year": r.get("predictThisYearEps"),
                "eps_next_year": r.get("predictNextYearEps"),
            })
        _db_save(db.save_research, code, result)
        _log_search(code, "research", result)
        return format_response(result)
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
        _log_search("市场快讯", "signals", data)
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
        df = disclosure.cninfo_disclosure(code)
        if df is None or (hasattr(df, "empty") and df.empty):
            return format_response([], True, "暂无数据")
        # 映射为统一字段（akshare 返回中文名列）
        col_map = {
            "公告标题": "title", "公告类型": "type", "公告日期": "date",
            "公告链接": "pdf_url", "公告时间": "date",
        }
        rename = {cn: en for cn, en in col_map.items() if cn in df.columns}
        df = df.rename(columns=rename)
        cols = ["title", "type", "date", "pdf_url"]
        available_cols = [c for c in cols if c in df.columns]
        data = df[available_cols].head(limit).to_dict('records')
        _db_save(db.save_announcement, code, df)
        _log_search(code, "disclosure", data)
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
        _log_search(code, "fundamental", data)
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


# ==================== 搜索历史 API ====================

@app.route('/api/search/history')
def api_search_history():
    """查询搜索历史"""
    try:
        keyword = request.args.get('keyword')
        search_type = request.args.get('type')
        limit = request.args.get('limit', 50, type=int)
        data = db.query_search_history(keyword, search_type, limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/search/recent')
def api_search_recent():
    """查询最近搜索（去重）"""
    try:
        limit = request.args.get('limit', 20, type=int)
        data = db.query_recent_searches(limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/search/stats')
def api_search_stats():
    """查询搜索统计"""
    try:
        data = db.query_search_stats()
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/search/delete', methods=['POST'])
def api_search_delete():
    """删除搜索历史"""
    try:
        keyword = request.json.get('keyword') if request.json else None
        search_type = request.json.get('type') if request.json else None
        deleted = db.delete_search_history(keyword, search_type)
        return format_response({"deleted": deleted}, True, f"已删除 {deleted} 条记录")
    except Exception as e:
        return format_response(None, False, str(e))


# ==================== 搜索评论 API ====================

@app.route('/api/search/comment', methods=['POST'])
def api_search_comment_add():
    """添加搜索评论"""
    try:
        data = request.json or {}
        search_id = data.get('search_id')
        keyword = data.get('keyword', '')
        content = data.get('content', '').strip()
        rating = data.get('rating')
        if not search_id or not content:
            return format_response(None, False, "缺少 search_id 或评论内容")
        if rating is not None:
            rating = max(1, min(5, int(rating)))
        ip = request.remote_addr
        db.save_comment(search_id, keyword, content, rating, ip)
        return format_response(None, True, "评论已保存")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/search/comment', methods=['PUT'])
def api_search_comment_update():
    """更新搜索评论"""
    try:
        data = request.json or {}
        comment_id = data.get('comment_id')
        content = data.get('content')
        rating = data.get('rating')
        if not comment_id:
            return format_response(None, False, "缺少 comment_id")
        if rating is not None:
            rating = max(1, min(5, int(rating)))
        db.update_comment(comment_id, content, rating)
        return format_response(None, True, "评论已更新")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/search/comment', methods=['DELETE'])
def api_search_comment_delete():
    """删除搜索评论"""
    try:
        data = request.json or {}
        comment_id = data.get('comment_id')
        if not comment_id:
            return format_response(None, False, "缺少 comment_id")
        ok = db.delete_comment(comment_id)
        return format_response({"deleted": ok}, True, "评论已删除" if ok else "评论不存在")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/search/comments')
def api_search_comments():
    """查询搜索评论"""
    try:
        search_id = request.args.get('search_id', type=int)
        keyword = request.args.get('keyword')
        limit = request.args.get('limit', 50, type=int)
        data = db.query_comments(search_id, keyword, limit)
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


@app.route('/api/search/comment/stats')
def api_search_comment_stats():
    """查询评论统计"""
    try:
        data = db.query_comment_stats()
        return format_response(data, True, f"共 {len(data)} 条")
    except Exception as e:
        return format_response(None, False, str(e))


# ==================== 用户认证 API ====================

# 内存中存储验证码（生产环境应用 Redis）
_sms_codes: dict[str, str] = {}


def _get_current_user() -> dict | None:
    """从 session 获取当前登录用户"""
    uid = session.get("user_id")
    if not uid:
        return None
    return db.get_user_by_id(uid)


@app.route('/api/auth/send_code', methods=['POST'])
def api_send_code():
    """发送短信验证码（测试环境固定 0000）"""
    data = request.json or {}
    phone = data.get("phone", "").strip()
    if not phone or len(phone) != 11 or not phone.isdigit():
        return format_response(None, False, "请输入正确的11位手机号")
    # 测试环境：固定验证码 0000
    _sms_codes[phone] = "0000"
    return format_response(None, True, "验证码已发送（测试环境固定为 0000）")


@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """注册新用户"""
    data = request.json or {}
    phone = data.get("phone", "").strip()
    code = data.get("code", "").strip()
    nickname = data.get("nickname", "").strip()

    if not phone or len(phone) != 11 or not phone.isdigit():
        return format_response(None, False, "请输入正确的11位手机号")
    if not code:
        return format_response(None, False, "请输入验证码")

    # 验证码校验
    saved_code = _sms_codes.get(phone)
    if not saved_code or code != saved_code:
        return format_response(None, False, "验证码错误")

    # 检查是否已注册
    existing = db.get_user_by_phone(phone)
    if existing:
        return format_response(None, False, "该手机号已注册，请直接登录")

    user = db.create_user(phone, nickname)
    if not user:
        return format_response(None, False, "注册失败")

    # 自动登录
    session.permanent = True
    session["user_id"] = user["id"]
    _sms_codes.pop(phone, None)

    return format_response({
        "id": user["id"],
        "phone": user["phone"],
        "nickname": user["nickname"],
    }, True, "注册成功")


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """登录"""
    data = request.json or {}
    phone = data.get("phone", "").strip()
    code = data.get("code", "").strip()

    if not phone or not code:
        return format_response(None, False, "请输入手机号和验证码")

    # 验证码校验
    saved_code = _sms_codes.get(phone)
    if not saved_code or code != saved_code:
        return format_response(None, False, "验证码错误")

    user = db.get_user_by_phone(phone)
    if not user:
        return format_response(None, False, "该手机号未注册，请先注册")

    # 登录
    session.permanent = True
    session["user_id"] = user["id"]
    db.update_user_login(user["id"])
    _sms_codes.pop(phone, None)

    return format_response({
        "id": user["id"],
        "phone": user["phone"],
        "nickname": user["nickname"],
    }, True, "登录成功")


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """退出登录"""
    session.clear()
    return format_response(None, True, "已退出登录")


@app.route('/api/auth/me')
def api_auth_me():
    """获取当前登录用户信息"""
    user = _get_current_user()
    if not user:
        return format_response(None, False, "未登录")
    return format_response({
        "id": user["id"],
        "phone": user["phone"],
        "nickname": user["nickname"],
    })


# ==================== 笔记 API ====================

@app.route('/api/notes', methods=['POST'])
def api_note_add():
    """添加笔记"""
    user = _get_current_user()
    if not user:
        return format_response(None, False, "请先登录")
    data = request.json or {}
    keyword = data.get("keyword", "").strip()
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    tags = data.get("tags", "").strip()
    if not title or not content:
        return format_response(None, False, "标题和内容不能为空")
    note = db.save_note(user["id"], keyword, title, content, tags)
    return format_response(note, True, "笔记已保存")


@app.route('/api/notes', methods=['PUT'])
def api_note_update():
    """更新笔记"""
    user = _get_current_user()
    if not user:
        return format_response(None, False, "请先登录")
    data = request.json or {}
    note_id = data.get("note_id")
    if not note_id:
        return format_response(None, False, "缺少 note_id")
    ok = db.update_note(
        note_id, user["id"],
        title=data.get("title"),
        content=data.get("content"),
        keyword=data.get("keyword"),
        tags=data.get("tags"),
    )
    return format_response(None, ok, "更新成功" if ok else "更新失败")


@app.route('/api/notes', methods=['DELETE'])
def api_note_delete():
    """删除笔记"""
    user = _get_current_user()
    if not user:
        return format_response(None, False, "请先登录")
    data = request.json or {}
    note_id = data.get("note_id")
    if not note_id:
        return format_response(None, False, "缺少 note_id")
    ok = db.delete_note(note_id, user["id"])
    return format_response(None, ok, "删除成功" if ok else "删除失败")


@app.route('/api/notes')
def api_notes_list():
    """查询笔记列表"""
    user = _get_current_user()
    if not user:
        return format_response(None, False, "请先登录")
    keyword = request.args.get("keyword")
    limit = request.args.get("limit", 50, type=int)
    data = db.query_notes(user["id"], keyword, limit)
    return format_response(data, True, f"共 {len(data)} 条")


@app.route('/api/notes/<int:note_id>')
def api_note_detail(note_id):
    """获取笔记详情"""
    user = _get_current_user()
    if not user:
        return format_response(None, False, "请先登录")
    note = db.get_note(note_id, user["id"])
    if not note:
        return format_response(None, False, "笔记不存在")
    return format_response(note)


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
