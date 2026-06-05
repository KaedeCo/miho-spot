## v1.5 -- 多Agent瑞士轮辩论厅 (2026-06-06)

### 多Agent瑞士轮辩论系统 (`/debate-hall`)

v1.5 引入了 Miho-spot 最具野心的功能：一个基于 DeepSeek API 的**三Agent瑞士轮辩论引擎**，让AI通过结构化辩论流程探索舆情问题的多维度真相。

#### 辩论架构

三个专业化Agent在8轮结构化辩论中交替发言，通过JSON文件交换论据：

- **A1 私有数据专家**：检索 `paper/` 目录下的 PDF 报告，提取非公开数据
- **A2 官媒分析专家**：通过火山方舟/Tavily 搜索引擎抓取官方媒体报道
- **A3 公域扫描专家**：搜索B站/知乎/小红书/贴吧等公共论坛的民间讨论
- **监督Agent**：第7轮整理三方策展输出，第8轮生成结构化最终报告

#### 8轮瑞士轮流程

| 轮次 | 类型 | 内容 |
|------|------|------|
| R1 | 开局立论 | A1/A2/A3 各自搜索并立论 |
| R2 | 质疑反驳 | A1驳A2 → A2驳A3 → A3驳A1 |
| R3 | 防守答辩 | A1防A3 → A2防A1 → A3防A2 |
| R4 | 第二波驳论 | 交叉驳论第二轮 |
| R5 | 第二波防守 | 交叉防守第二轮 |
| R6 | 自由辩论 | 不限方向，综合攻防 |
| R7 | 三方策展 | A1/A2/A3 并行独立策展 |
| R8 | 监督整理 | 监督Agent融合三方输出，生成最终报告 |

#### 双轨搜索引擎

- **火山方舟**（Ark Bot）— 主力搜索引擎，月免费2万次，通过 `/api/v3/responses` 的 `web_search` tool 实现
- **Tavily** — Fallback 备用引擎，配额耗尽时自动切换
- 配置入口：前端"账号管理"页面新增火山方舟 API Key + Endpoint ID、Tavily API Key 独立卡片，含验证和测试搜索按钮

#### Two-Pass 智能体架构（核心技术突破）

传统单次调用模式导致Agent只搜索不分析。v1.5 创新的两阶段架构解决了这一问题：

- **Pass 1（搜索阶段）**：`tool_choice: "required"` 强制Agent调用搜索工具，收集所有结果
- **Pass 2（分析阶段）**：移除 tool 参数，将搜索摘要作为系统上下文注入，Agent专注于撰写完整分析

#### 用户交互：事实确认面板

辩论过程中每轮提取的关键事实实时推送到前端"事实确认面板"，支持四种操作：
- **确认** (confidence=1.0) — 认可事实
- **争议** (0.5) — 部分认可
- **驳回** (0.0) — 完全否定
- **修改** — 用户可直接编辑事实内容后确认

#### 事实质量保障

三步提取 + 质量过滤确保每条事实具备新闻三要素（时间/地点/事件）：
- 一级提取：匹配 `【事实X】` 标记格式
- 二级提取：搜索摘要中的结构化段落
- 三级提取：自然段拆分 + 短句合并 + 质量过滤（最小40字符、排除纯标题词、去重）

#### 辩论回放 (`/debate-replay`)

已保存的辩论支持完整回放：
- 竖向时间轴展示8轮辩论全过程
- 每个Agent发言以醒目彩色横栏标注（A1蓝/A2金/A3绿/监督紫）
- 支持 react-markdown 渲染辩论正文
- PDF报告一键下载
- 兼容后端重启后的数据恢复（DB + 磁盘双层查找）

#### 实时辩论终端

三个黑色终端面板（Cascadia Code 等宽字体），SSE 流式输出：
- 蓝色 — A1/A2/A3 辩论正文
- 灰色 — 工具调用（搜索引擎/文件读取）
- 紫色 — 文件传输（JSON存档）
- 绿色 — 事实提取通知
- 黄色 — Markdown 标题（##）
- 闪烁光标 — 最后输出行

#### 健壮性设计

- 每轮独立 try/except，单轮失败不中断辩论
- 发生错误时自动保存不完整结果，允许用户手动存档
- PDF 生成采用 reportlab（与已有 paper/ 输出一致），支持 SimSun 中文字体
- 监督报告 max_tokens 可配置（分析阶段 4000，监督阶段 6000），防止截断

### 后端新增

- **`debate/` 模块**（2003 行）：
  - `orchestrator.py`（1089行）— 瑞士轮调度引擎，SSE事件推送，Two-Pass调用，事实提取与质量过滤
  - `agents.py`（203行）— BaseAgent + 4个子类，Tool Calling schema映射
  - `prompts.py`（236行）— 系统提示词模板，4阶段辩论指令，强制4段式输出格式
  - `search_tools.py`（221行）— SearchEngine双轨搜索（火山方舟+Tavily），QuotaExhaustedError自动切换
  - `data_exchange.py`（243行）— JSON文件I/O（fact_check/defend_point/debate_point/supervisor_report），轮次快照，全量存档
- **3个SQLAlchemy模型**：`DebateSession`、`DebateFact`、`DebateRoundSnapshot`
- **7个API路由**：create / stream(SSE) / confirm-facts / save / sessions / report / replay / pdf / delete
- **Accounts页**：新增火山方舟+Tavily配置卡片，含验证+测试搜索按钮

### 前端新增

- `DebateHall.tsx`（~298行）— 辩论主页面，SSE事件流管理
- `DebateReplay.tsx`（~200行）— 竖向时间轴回放
- `AgentTerminal.tsx` — 颜色编码流式终端
- `DebateProgress.tsx` — 进度条+待确认事实计数
- `FactConfirmPanel.tsx` — 事实确认面板（4项操作）
- `DebateReportPreview.tsx` — react-markdown报告预览+PDF下载

### Bug修复汇总

- data_dir null 导致辩论回放无数据（创建记录在 orchestrator.run() 之前，_session_dir未设置）
- PDF下载端点仅查内存_DEBUG_sessions，重启后404 — 新增DB/磁盘二级查找
- Agent只搜索不分析 — Two-Pass架构从根本上解决
- 事实确认面板单条提交后整面板关闭
- 事实字段显示raw_text标签而非内容
- 监督报告字数截断（max_tokens=1500硬编码 → 参数化）
- React重复Key警告（fact UUID长度不足 + 前端Set去重）
- 辩论回放404（缺少archive目录时返回空数组而非报错）

### 技术栈新增

| 技术 | 用途 |
|------|------|
| Volcano Ark API | 联网搜索引擎（主） |
| Tavily API | 联网搜索引擎（备） |
| react-markdown | 前端Markdown渲染 |
| Cascadia Code | 终端等宽字体 |
| SSE (Server-Sent Events) | 实时流式传输 |
