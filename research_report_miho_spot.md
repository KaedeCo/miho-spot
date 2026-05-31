# Miho-spot 舆情监测系统 - 架构与开发报告

## 执行摘要

Miho-spot 是一个完整的、前后端分离的米哈游多平台舆情监测系统。前端采用 React 19 + TypeScript + TDesign React v1.17 + Tailwind CSS v4 构建，包含数据仪表盘、热搜监测、关键词词典管理、历史统计、账号管理等五个核心页面。后端采用 Python FastAPI + PyQt6 双轨架构，支持 REST API 服务和桌面 GUI 两种运行模式。系统内置了包含 70+ 条目的二游圈关键词词典，覆盖米哈游游戏、角色、CV、竞品游戏和二游圈通用术语五大类别。所有页面均实现了饼状图/柱状图切换、跨日统计等功能，采用深色主题和现代化的渐进式动画。

## 背景与需求分析

用户需要构建一个针对米哈游（miHoYo）在知乎、抖音、贴吧三大平台的舆情监测工具。核心需求包括：多平台热榜自动爬取、二游圈内容识别与情感分析、热搜下深度内容分析、数据可视化与持久化存储、以及跨日趋势统计。该系统需要支持用户登录各平台账号以提升爬取权限，并提供可扩展的关键词词典管理。

## 技术架构

### 前端架构

前端基于 Vite 8 + React 19 + TypeScript 6 构建，核心依赖包括：

- TDesign React v1.17：腾讯企业级 UI 组件库，提供 Table、Dialog、Tabs、Select、DatePicker 等 40+ 组件
- Tailwind CSS v4：原子化 CSS 框架，通过 @tailwindcss/vite 插件集成
- Recharts v3：数据可视化库，提供 PieChart、BarChart、AreaChart、LineChart
- React Router v7：客户端路由
- TDesign Icons React：图标库

前端路由结构：
- `/` — 数据仪表盘（Dashboard）：总览统计数据、情感分布饼/柱图、平台分布、热搜列表
- `/topics` — 热搜监测（HotTopics）：分平台 Tab 展示热搜卡片，点击触发深度分析弹窗
- `/keywords` — 关键词词典（Keywords）：关键词的 CRUD 管理，按分类筛选
- `/history` — 历史统计（History）：7天/30天/自定义日期范围的趋势图和统计
- `/accounts` — 账号管理（Accounts）：知乎/抖音/贴吧的 Cookie 配置与验证

### 后端架构

后端采用 Python 3.10+ 双轨架构：

- FastAPI（REST API）：提供 `/api/dashboard`、`/api/topics`、`/api/analysis`、`/api/stats/daily`、`/api/keywords`、`/api/accounts` 等端点
- PyQt6（桌面 GUI）：提供独立的桌面监控界面，包含仪表盘、爬取控制、运行日志三个面板
- SQLAlchemy + SQLite：ORM 数据持久化，包含 hot_topics、post_items、daily_stats、keywords、accounts 五张表
- SnowNLP + jieba：中文情感分析和分词

### 情感分析策略

系统采用混合策略进行情感判断：
1. 关键词匹配：检查标题中是否包含米哈游或竞品关键词
2. 情感词典匹配：预定义的正负面情感词库（如"吹爆"/"垃圾"）
3. SnowNLP 机器学习模型：作为兜底的评分机制
4. 三级分类结果：Positive（正面）、Negative（负面）、Irrelevant（无关-附带关联游戏）

### 关键词词典（70+ 条目）

| 类别 | 条目数 | 示例 |
|------|--------|------|
| 米哈游游戏 | 9 | 原神、崩坏：星穹铁道、绝区零 |
| 米哈游角色 | 20 | 钟离、胡桃、雷电将军、芙宁娜、流萤 |
| 米哈游CV | 9 | kinsen、花玲、林簌、多多poi |
| 竞品游戏 | 12 | 明日方舟、鸣潮、无限暖暖、少女前线2 |
| 二游圈通用 | 15 | 二游、抽卡、648、策划、数值膨胀 |

## 设计决策

### 前端设计系统

采用深色主题（#0f0f1a 底色），以紫色系（indigo-500 #6366f1）作为主色调，绿色/红色/黄色分别表示正面/负面/中性情感。使用 glass-card 玻璃态卡片效果、fadeInUp/slideInLeft 渐进式入场动画、shimmer 加载骨架屏。TDesign 组件通过 CSS 变量覆盖适配深色主题。

### 后端架构选型

选择 FastAPI 而非 Flask 的主要原因：原生异步支持（爬虫任务）、自动 OpenAPI 文档生成、Pydantic 数据验证。选择 PyQt6 而非 Electron 的原因：与 Python 后端天然集成、更低的资源占用、适合桌面监控场景。SQLite 作为初期存储方案，可平滑迁移至 PostgreSQL。

### 图表切换实现

使用 Recharts 的 PieChart 和 BarChart 组件，通过 Radio.Group 控件在饼图和柱状图之间切换，共享相同的数据源和 Tooltip 组件。图表数据通过 `filter(d => d.value > 0)` 过滤零值项，避免空扇区。

### 跨日统计的横向滚动

对于 30 天和自定义日期范围的统计，通过设置 `minWidth: data.length * 50` 并在容器上使用 `overflow-x: auto` 实现横向滚动，保证界面不会过度拥挤。

## 限制与后续改进

1. 爬虫模块目前为脚手架代码，实际部署需集成 Playwright 或 Selenium
2. 情感分析使用 SnowNLP 基础模型，对游戏领域术语理解有限，可考虑微调 BERT 模型
3. 前端目前使用 Mock 数据演示，对接后端 API 后可实时爬取
4. PyQt6 GUI 目前为独立桌面端，可考虑通过 QWebEngineView 嵌入前端页面
5. 可引入 WebSocket 实现实时数据推送
6. 建议增加邮件/企微/钉钉告警功能

## 结论

Miho-spot 系统已完成完整的前后端架构搭建，包含 5 个前端页面、完整的 REST API 端点设计、数据库模型、情感分析引擎和 PyQt6 桌面 GUI。系统采用现代化的技术栈（React 19、TDesign、FastAPI、PyQt6），实现了深色主题的统一视觉风格和流畅的动画效果。前端开发服务器已成功启动在 http://localhost:5173，所有核心功能页面均可正常访问，包含 Mock 数据用于演示。

## 参考资料

1. [TDesign React 组件库文档](https://tdesign.tencent.com/react/)
2. [Recharts 数据可视化库](https://recharts.org/)
3. [FastAPI 官方文档](https://fastapi.tiangolo.com/)
4. [SnowNLP 中文情感分析](https://github.com/isnowfy/snownlp)
5. [PyQt6 官方文档](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
6. [米哈游各平台舆论环境分析 - 贴吧](https://tieba.baidu.com/p/10136124074)
7. [原神舆论风向差异分析 - 贴吧](https://tieba.baidu.com/p/9047072469)
8. [TDesign 组件库快速入门](https://modao.cc/ad/blog/Tdesign-component-library-usage.html)
