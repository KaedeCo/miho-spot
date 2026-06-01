# Miho-spot 米哈游舆情监测系统

> "从此以后，每个人都是社管，亦或者都不是社管。" — By Chronostasis

**v1.1**

Miho-spot 是一个多平台二游圈舆情监测与分析系统，覆盖知乎、抖音、贴吧、B站等平台。通过热搜爬取、关键词匹配、SnowNLP 本地情感分析、DeepSeek AI 增强分析，实时追踪米哈游相关舆论风向。

新增 **B站"查成分"** 功能：输入任意 B站用户 UID，自动拉取其历史评论，经关键词筛选后由 DeepSeek 生成用户人格画像（米哈游态度、活跃领域、性格推测），为社区舆情研究提供数据支撑。

---

## 功能特性

### 舆情监测
- **多平台热搜爬取** — 自动爬取知乎、抖音、贴吧热榜，支持 Tophub 付费关键词搜索
- **关键词词典** — 内置 200+ 二游圈关键词（米哈游本体、原神/星铁/绝区零角色、竞品游戏、CV 等），支持用户增删改查与导入导出
- **情感分析** — 三级分类（正面/负面/无关），融合关键词匹配 + SnowNLP 语义分析
- **DeepSeek 增强** — 一键调用 DeepSeek API 对所有二游相关热搜进行 AI 情感判定

### B站"查成分"（v1.1 新增）
- **历史评论拉取** — 通过 AICU API 获取指定 UID 用户的所有视频评论记录
- **关键词筛选** — 自动匹配关键词词典，高亮命中评论
- **人格画像生成** — DeepSeek 三维修分析：米哈游态度评分（0-100）、主要活跃领域、性格推测
- **评论分页展示** — 所有评论 100 条/页完整展示，命中关键词的评论紫色高亮

### 数据可视化
- **仪表盘** — 6 个统计卡片 + 情感分布饼图/柱状图 + 平台分布图
- **历史统计** — 支持 7 天 / 30 天 / 自定义时间范围，面积图 + 折线图趋势展示
- **账号管理** — Tophub API Key + DeepSeek API Key 配置，验证即用

### 桌面版
- **PyInstaller 单文件 EXE** — 双击运行，无需 Python 环境
- **PyQt6 暗黑 GUI** — 实时状态监控、日志面板、社区段子轮播
- **内嵌前端** — GUI 启动后浏览器访问 `localhost:8000` 即可使用完整前端

---

## 技术栈

### 前端
| 技术 | 版本 |
|------|------|
| React | 19 |
| TypeScript | 6.0 |
| Vite | 8 |
| TDesign React | 1.17 |
| Tailwind CSS | 4.3 |
| Recharts | 3.8 |
| React Router | 7.1 |

### 后端
| 技术 | 用途 |
|------|------|
| FastAPI | REST API 服务 |
| PyQt6 | 桌面 GUI 面板 |
| SQLAlchemy + SQLite | 数据持久化 |
| SnowNLP + jieba | 本地中文情感分析 |
| curl_cffi | 绕过 Cloudflare 防护 |
| DeepSeek API | AI 增强分析 |
| AICU API | B站用户历史评论数据源 |

---

## 快速开始

### 开发模式

```bash
# 1. 后端
cd miho-spot/backend
pip install -r requirements.txt
python main.py --port 8000

# 2. 前端
cd miho-spot/frontend
npm install
npm run dev

# 3. 访问 http://localhost:5173
```

### 桌面版（打包后）

双击 `dist/Miho-spot-Backend.exe`，自动启动后端服务 + 内嵌前端。

### 配置 API Key

在前端 **"账号管理"** 页面配置：
- **Tophub API Key** — 用于付费关键词搜索（可选，无 Key 不影响热榜爬取）
- **DeepSeek API Key** — 用于 AI 增强分析 + 查成分人格画像（可选，无 Key 仅使用本地分析）

---

## 项目结构

```
miho-spot/
├── frontend/                     # React 前端
│   └── src/
│       ├── components/           # Layout, Sidebar, StatCard, SentimentChart, etc.
│       ├── pages/                # Dashboard, HotTopics, Keywords, History, Accounts
│       │   └── CheckIdentity.tsx  # [v1.1] B站"查成分"
│       ├── services/api.ts       # API 调用层
│       └── types/index.ts        # TypeScript 类型定义
├── backend/                      # Python 后端
│   ├── main.py                   # FastAPI 入口
│   └── app/
│       ├── api/routes.py         # 全部 API 路由
│       ├── bilibili/__init__.py  # [v1.1] B站评论拉取 + DeepSeek 分析
│       ├── crawlers/__init__.py  # 爬虫引擎（知乎/抖音/贴吧/Tophub）
│       ├── sentiment/__init__.py # 情感分析（关键词匹配 + SnowNLP）
│       ├── models/__init__.py    # SQLAlchemy 模型
│       ├── monitor.py            # PyQt6 监控面板
│       └── gui/main_window.py    # PyQt6 桌面窗口
├── start.bat                     # Windows 一键启动脚本
└── README.md
```

---

## API 端点摘要

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/dashboard` | GET | 仪表盘汇总数据 |
| `/api/topics` | GET | 热搜列表（支持平台/来源过滤） |
| `/api/crawl/hot` | POST | 触发热榜爬取 |
| `/api/keywords` | GET/POST | 关键词词典管理 |
| `/api/stats/daily` | GET | 历史统计数据 |
| `/api/deepseek/analyze-all` | POST | DeepSeek 一键批量分析 |
| `/api/bilibili/user/info` | GET | B站用户基本信息 |
| `/api/bilibili/analyze` | POST | 触发查成分分析 |
| `/api/bilibili/analyze/result` | GET | 获取分析结果（分页） |

---

## 关键词词典

内置 200+ 二游圈关键词，覆盖以下分类：

| 分类 | 内容示例 |
|------|---------|
| 米哈游游戏 | 原神、星穹铁道、绝区零、崩坏3、未定事件簿 |
| 米哈游角色 | 钟离、胡桃、流萤、纳西妲、芙宁娜、艾莲 |
| 米哈游CV | kinsen、花玲、林簌、多多poi、菊花花 |
| 竞品游戏 | 明日方舟、鸣潮、幻塔、蔚蓝档案、无限暖暖 |
| 二游圈通用 | 二游、抽卡、648、策划、保底、退坑 |

---

## 注意事项

- **API Key 安全** — 本项目不内置任何 API Key，所有 Key 需用户在前端"账号管理"页面自行填写
- **AICU 数据延迟** — B站评论数据来自第三方 AICU 服务，非实时更新。如遇风控拦截，请切换网络/IP 后重试
- **DeepSeek 可选** — 未配置 DeepSeek API Key 时，舆情分析使用本地 SnowNLP，查成分功能仍可拉取评论但无 AI 分析

---

## 更新日志

### v1.1 (2026-06)
- 新增 B站"查成分"功能：UID 输入 → 历史评论拉取 → 关键词筛选 → DeepSeek 人格画像
- 集成 AICU API 作为 B站评论数据源
- 引入 curl_cffi 绕过 Cloudflare 防护
- 前端新增 CheckIdentity 页面，评论 100 条/页完整展示
- 一键启动脚本 `start.bat` 自动安装依赖

### v1.0 (2026-05)
- 知乎、抖音、贴吧三平台热榜爬取
- 200+ 关键词词典 + 分类管理
- SnowNLP 本地情感分析
- DeepSeek AI 批量分析
- Recharts 数据可视化（饼图/柱状图/面积图/折线图）
- PyQt6 桌面 GUI + PyInstaller 打包

---

## License

MIT
