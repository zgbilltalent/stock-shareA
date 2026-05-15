# feifan-stock-data

A股全栈数据工具包 — 覆盖行情、估值、信号、研报、新闻、公告六层数据源，提供 Web API 和可视化界面，数据自动持久化到 MySQL。

## 功能概览

### 数据层（六大数据源）

| 模块 | 说明 | 数据源 |
|------|------|--------|
| 行情 (quotes) | 实时行情、K线、五档盘口、逐笔成交 | 通达信 TCP + 腾讯财经 HTTP |
| 估值 (valuation) | PE/PB/PEG/ROE/股息率，多维度估值评分 | 东方财富 |
| 信号 (signals) | 强势股、热门题材、行业涨跌、北向资金、龙虎榜、解禁日历 | 同花顺 / 东方财富 |
| 研报 (research) | 个股研报列表、机构评级、目标价 | 东方财富 |
| 新闻 (news) | 市场快讯 | 东方财富 |
| 公告 (disclosure) | 个股公告及 PDF 链接 | 巨潮资讯 |
| 基础面 (fundamental) | 公司基本信息、财务指标、主要指数 | 东方财富 |

### 用户系统

- 手机号 + 短信验证码注册/登录（测试环境验证码固定为 `0000`）
- Session 认证，30 天有效期
- 登录后可使用笔记功能

### 笔记模块

- 支持关联股票代码，记录投资观点
- 支持标签分类
- 仅登录用户可用，数据按用户隔离

### 搜索历史与评论

- 自动记录股票搜索行为（信号类搜索不记录）
- 对搜索记录添加评论和评分
- 搜索统计与去重查询

## 技术栈

- **后端**: Python 3.9+ / Flask / PyMySQL / DBUtils
- **前端**: 原生 HTML + CSS + JavaScript（Tailwind 风格）
- **数据库**: MySQL 8.0
- **部署**: Docker Compose

## 快速开始

### Docker 部署（推荐）

```bash
# 克隆项目
git clone https://github.com/simonlin1212/feifan-stock-data.git
cd feifan-stock-data

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f web
```

服务启动后访问 `http://localhost:5001`

### 本地开发

```bash
# 安装依赖
pip install -e ".[web,dev]"

# 配置数据库环境变量
export FEIFAN_DB_HOST=127.0.0.1
export FEIFAN_DB_PORT=3306
export FEIFAN_DB_USER=root
export FEIFAN_DB_PASSWORD=your_password
export FEIFAN_DB_NAME=feifan_stock

# 启动 Web 服务
python -m feifan_stock_data.web
```

## API 文档

### 行情

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/quote/<code>` | GET | 单股票实时行情 |
| `/api/quotes` | POST | 批量实时行情，body: `{"codes": ["600519", "000858"]}` |

### 估值

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/valuation/<code>` | GET | 完整估值数据 |
| `/api/valuation/summary/<code>` | GET | 估值摘要（含评分与信号） |

### 信号

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/signals/hot` | GET | 当日强势股 |
| `/api/signals/topics` | GET | 热门题材 |
| `/api/signals/industry` | GET | 行业涨跌幅 |
| `/api/signals/northbound` | GET | 北向资金汇总 |
| `/api/signals/dragon_tiger` | GET | 龙虎榜 |
| `/api/signals/unlock` | GET | 解禁信息 |

### 研报 / 新闻 / 公告 / 基础面

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/research/stock/<code>` | GET | 个股研报 |
| `/api/news/market` | GET | 市场快讯 |
| `/api/disclosure/<code>` | GET | 个股公告 |
| `/api/fundamental/<code>` | GET | 基础面数据 |

### 历史数据查询

所有历史接口统一前缀 `/api/history/`，支持 `limit` 参数：

| 接口 | 说明 |
|------|------|
| `/api/history/quote/<code>` | 行情历史 |
| `/api/history/valuation/<code>` | 估值历史 |
| `/api/history/northbound` | 北向资金历史 |
| `/api/history/dragon_tiger` | 龙虎榜历史 |
| `/api/history/hot_stock` | 强势股历史（支持 `code` 筛选） |
| `/api/history/topics` | 题材历史 |
| `/api/history/industry` | 行业历史 |
| `/api/history/research` | 研报历史（支持 `code` 筛选） |
| `/api/history/news` | 新闻历史 |
| `/api/history/announcement` | 公告历史（支持 `code` 筛选） |
| `/api/history/fundamental` | 基础面历史（支持 `code` 筛选） |

### 搜索历史

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/search/history` | GET | 搜索历史（支持 `keyword`、`type` 筛选） |
| `/api/search/recent` | GET | 最近搜索（去重） |
| `/api/search/stats` | GET | 搜索统计 |
| `/api/search/delete` | POST | 删除搜索记录 |

### 搜索评论

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/search/comment` | POST | 添加评论 |
| `/api/search/comment` | PUT | 更新评论 |
| `/api/search/comment` | DELETE | 删除评论 |
| `/api/search/comments` | GET | 查询评论列表 |
| `/api/search/comment/stats` | GET | 评论统计 |

### 用户认证

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/auth/send_code` | POST | 发送验证码（测试环境固定 `0000`） |
| `/api/auth/register` | POST | 注册（自动登录） |
| `/api/auth/login` | POST | 登录 |
| `/api/auth/logout` | POST | 退出登录 |
| `/api/auth/me` | GET | 获取当前用户信息 |

### 笔记

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/notes` | GET | 笔记列表（支持 `keyword` 筛选） |
| `/api/notes` | POST | 新建笔记 |
| `/api/notes` | PUT | 更新笔记 |
| `/api/notes` | DELETE | 删除笔记 |
| `/api/notes/<id>` | GET | 笔记详情 |

### 系统

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查（含数据库状态） |
| `/api/version` | GET | 版本信息 |

## 数据库配置

通过环境变量配置 MySQL 连接：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FEIFAN_DB_HOST` | 127.0.0.1 | MySQL 主机 |
| `FEIFAN_DB_PORT` | 3306 | MySQL 端口 |
| `FEIFAN_DB_USER` | root | 用户名 |
| `FEIFAN_DB_PASSWORD` | (空) | 密码 |
| `FEIFAN_DB_NAME` | feifan_stock | 数据库名 |

Docker Compose 环境下已自动配置，无需手动设置。

## 数据库表结构

| 表名 | 说明 |
|------|------|
| `quote_snapshot` | 行情快照 |
| `valuation_record` | 估值记录 |
| `northbound_flow` | 北向资金 |
| `dragon_tiger` | 龙虎榜 |
| `hot_stock` | 强势股 |
| `hot_topic` | 热门题材 |
| `industry_rank` | 行业涨跌排名 |
| `research_report` | 研报 |
| `market_news` | 市场新闻 |
| `announcement` | 公告 |
| `fundamental_data` | 基础面数据 |
| `search_log` | 搜索记录 |
| `search_comment` | 搜索评论 |
| `user` | 用户 |
| `note` | 笔记 |

## 项目结构

```
src/feifan_stock_data/
├── __init__.py         # 包入口、版本号
├── cli.py              # 命令行工具
├── db.py               # 数据库模块（MySQL 持久化）
├── disclosure.py       # 公告数据
├── fundamental.py      # 基础面数据
├── news.py             # 市场新闻
├── quotes.py           # 行情数据（通达信 + 腾讯）
├── research.py         # 研报数据
├── signals.py          # 信号数据（强势股/题材/北向/龙虎榜等）
├── utils.py            # 工具函数
├── valuation.py        # 估值数据
├── web.py              # Web 服务入口（Flask API + 页面路由）
└── templates/
    └── index.html      # 前端单页应用
```

## License

MIT
