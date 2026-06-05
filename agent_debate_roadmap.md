# 多 Agent 瑞士轮辩论 —— 实现路线图

## 一、功能概览

三个 Agent（A1 私有数据、A2 官媒数据、A3 公域论坛）进行 8 轮瑞士轮辩论，最终由监督 Agent 整合出一份舆情深度分析报告。前端以三个黑底终端框实时展示每个 Agent 的输出。

---

## 二、架构设计

### 2.1 整体架构

```
┌─ 前端 ─────────────────────────────────────────────────┐
│  Sidebar 新增入口 "舆情辩论厅"                            │
│  /debate-hall 页面                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ A1 终端   │  │ A2 终端   │  │ A3 终端   │              │
│  │ (黑框)   │  │ (黑框)   │  │ (黑框)   │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│  [事实确认面板] [辩论进度条] [最终报告预览]               │
└────────────────────────────────────────────────────────┘
          │ SSE (Server-Sent Events) 实时推送
          ▼
┌─ 后端 ─────────────────────────────────────────────────┐
│  /api/debate/create       创建辩论会话                   │
│  /api/debate/stream/{id}  SSE 实时流                    │
│  /api/debate/confirm-fact 玩家确认事实                   │
│  /api/debate/report/{id}  获取最终报告                   │
│                                                         │
│  debate_orchestrator.py                                 │
│    ├─ DebateSession      会话状态管理                    │
│    ├─ SwissRoundManager  轮次调度器                      │
│    ├─ AgentA1/A2/A3      三个专业 Agent                  │
│    ├─ SupervisorAgent    监督 Agent                     │
│    └─ DataExchange       事实/论点 JSON 管理             │
└────────────────────────────────────────────────────────┘
```

### 2.2 关键技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 实时通信 | **SSE (Server-Sent Events)** | 单向推送，比 WebSocket 简单，比轮询实时；FastAPI 原生支持 |
| Agent 实现 | **手工 Agent Loop** | 直接复用现有 `_call_deepseek` + tool calling，零新框架依赖 |
| 后端线程模型 | **asyncio + BackgroundTasks** | FastAPI 原生，SSE 和辩论引擎在同一事件循环 |
| 搜索能力 | **双轨制：火山方舟 Bot 插件（主）+ Tavily（Fallback）** | 火山月免 2 万次覆盖日常消耗，Tavily 兜底防止配额耗尽中断 |
| 前端状态 | **React state + SSE EventSource** | 轻量，无需引入 WebSocket 库 |
| 辩论持久化 | **每轮自动快照 + 全量归档 JSON** | 每轮完成后将完整 Agent 上下文、JSON 交换、事实库全量写入 debate_sessions 归档目录 |

---

## 三、数据模型设计

### 3.1 核心 JSON 结构

```
debate_session/
├── session_{id}.json          # 会话元数据
├── fact_check.json             # 共享事实库（后端维护）
├── debate_point.json           # 当前轮次结构化上下文（Agent 间传递）
├── a1_defend_point.json        # A1 防守论点（4-6 轮可编辑）
├── a2_defend_point.json        # A2 防守论点
├── a3_defend_point.json        # A3 防守论点
└── supervisor_report.json      # 监督 Agent 最终整合报告
```

### 3.2 `fact_check.json` 结构

```json
{
  "facts": [
    {
      "id": "f1",
      "content": "视频发布于2025年6月1日，截至6月3日已获得120万播放",
      "source": "A1",
      "status": "confirmed",           // pending | confirmed | disputed | rejected
      "confidence": 1.0,               // 1.0=确认, 0.5=争议, 0.0=驳回
      "confirmed_by_user": true,
      "user_action": "confirm",        // modify | confirm | dispute | reject
      "original_content": "视频发布于...已获得120万播放",  // 用户修改前的原始内容
      "modified_by_user": null,        // 若被修改，存修改后内容
      "evidence": "paper/xxx.pdf 第3页",
      "created_at": "2025-06-03T10:00:00",
      "confirmed_at": "2025-06-03T10:02:00",
      "disputes": [
        {
          "agent": "A2",
          "reason": "播放量数据可能不准确，官方显示为115万",
          "timestamp": "2025-06-03T10:05:00"
        }
      ]
    }
  ],
  "confirmed_count": 15,
  "disputed_count": 3,
  "rejected_count": 1,
  "pending_count": 2
}
```

**用户四种操作定义：**

| 操作 | API 字段 | confidence | 效果 |
|------|---------|-----------|------|
| **修改** | `action: "modify"` | 1.0 | 用户编辑事实内容后确认，`content` 更新为修改后文本，`original_content` 保留原始值 |
| **确认** | `action: "confirm"` | 1.0 | 直接采信，该事实可作为任意 Agent 的论据 |
| **争议** | `action: "dispute"` | 0.5 | 事实可信度减半，Agent 引用时需标注"存疑"，仍可作为辅助论据 |
| **驳回** | `action: "reject"` | 0.0 | 判定为非事实，禁止任何 Agent 在后续轮次中将其作为论据引用；`debate_point.json` 和 `defend_point.json` 中对该事实的引用自动标记为无效 |

### 3.3 `debate_point.json` 结构

```json
{
  "round": 3,
  "agent": "A3",
  "timestamp": "2025-06-03T10:15:00",
  "stage": "rebuttal",           // opening | rebuttal | defense | final_thesis
  "targets": ["A1", "A2"],
  "arguments": [
    {
      "id": "arg_3_1",
      "type": "rebuttal",
      "target_fact_id": "f3",
      "claim": "A1声称的社区情绪统计样本量不足",
      "reasoning": "仅采样200条评论，置信度低于95%",
      "evidence": [
        {"type": "web", "url": "https://...", "snippet": "..."},
        {"type": "private", "source": "paper/xxx.pdf"}
      ],
      "refers_to": ["A1.arg_1_2", "A2.arg_2_1"]
    }
  ],
  "concessions": ["同意A1关于视频具有争议性的判断"],
  "key_insights": ["三方均认为官方回应时机存疑"]
}
```

### 3.4 `defend_point.json` 结构

```json
{
  "agent": "A1",
  "version": 2,
  "last_modified_round": 5,
  "core_thesis": "该视频引发的争议主要源于信息不对称...",
  "supporting_evidence": [...],
  "responses_to_challenges": [
    {
      "challenge_from": "A2",
      "challenge_id": "arg_2_1",
      "response": "A2引用的官方数据发布于争议之后...",
      "new_evidence": [...]
    }
  ],
  "acknowledged_strengths_of_others": [
    {"agent": "A3", "point": "公域讨论热度确实在争议后48小时达到峰值"}
  ]
}
```

### 3.5 SQLite 模型（新增）

```python
class DebateSession(Base):
    __tablename__ = "debate_sessions"
    id            = Column(Integer, primary_key=True)
    topic         = Column(String(500))       # 辩论主题
    status        = Column(String(20))         # created | running | waiting_facts | completed | failed | saved
    current_round = Column(Integer, default=0) # 0-8
    created_at    = Column(DateTime)
    completed_at  = Column(DateTime)
    final_report  = Column(Text)              # 最终报告内容
    data_dir      = Column(String(500))       # debate_session/{id}/ 目录路径
    archive_dir   = Column(String(500))       # 全量持久化归档目录路径

class DebateFact(Base):
    __tablename__ = "debate_facts"
    id            = Column(Integer, primary_key=True)
    session_id    = Column(Integer, ForeignKey)
    fact_id       = Column(String(20))
    content       = Column(Text)
    status        = Column(String(20))         # pending | confirmed | disputed | rejected
    confidence    = Column(Float, default=1.0) # 1.0/0.5/0.0
    source_agent  = Column(String(10))         # A1/A2/A3
    user_action   = Column(String(20))         # modify | confirm | dispute | reject

class DebateRoundSnapshot(Base):
    """每轮辩论完成后，全量序列化该轮所有 Agent 的上下文和输出"""
    __tablename__ = "debate_round_snapshots"
    id            = Column(Integer, primary_key=True)
    session_id    = Column(Integer, ForeignKey)
    round_num     = Column(Integer)            # 第几轮
    agent_id      = Column(String(10))         # 哪个 Agent
    stage         = Column(String(20))         # open | rebuttal | defense | curation | supervise
    system_prompt = Column(Text)               # 该 Agent 当前轮次的 system prompt
    input_context = Column(Text)               # 输入上下文（含其他 Agent 的 debate_point）
    tool_calls    = Column(Text)               # JSON: 该轮所有 tool call 记录
    raw_output    = Column(Text)               # Agent 原始完整输出
    fact_changes  = Column(Text)               # JSON: 本轮新增/修改的事实
    created_at    = Column(DateTime)
```

### 3.6 辩论全程持久化存储机制

```
backend/debate_sessions/
└── {session_id}/
    ├── session_meta.json             # 会话元数据
    ├── fact_check.json               # 实时事实库（最新状态）
    ├── debate_point.json             # 当前轮次上下文（最新状态）
    ├── a1_defend_point.json          # A1 防守论点（最新状态）
    ├── a2_defend_point.json          # A2 防守论点（最新状态）
    ├── a3_defend_point.json          # A3 防守论点（最新状态）
    ├── supervisor_report.json        # 最终报告
    └── archive/                      # 全量归档（每轮完成后快照）
        ├── round_01/
        │   ├── a1_debate_point.json       # A1 立论输出
        │   ├── a1_input_context.json      # A1 收到的输入上下文
        │   ├── a1_tool_calls.json         # A1 本轮所有 tool 调用记录
        │   ├── fact_check_snapshot.json   # 本轮结束后事实库快照
        │   └── round_summary.json         # 本轮摘要
        ├── round_02/
        │   ├── a2_debate_point.json
        │   ├── a2_input_context.json
        │   ├── ...
        │   └── round_summary.json
        ├── ...
        └── round_08/
            └── ...

用户可以在任意轮次完成后点击"保存"，将当前 debate_session/{id}/ 全量打包存入 SQLite 的 debate_round_snapshots 表，便于后续回溯查看每轮每个 Agent 的完整思考过程。
```

---

## 四、后端实现规划

### 4.1 新建文件

```
backend/app/
├── debate/
│   ├── __init__.py
│   ├── orchestrator.py        # 辩论编排引擎（核心）
│   ├── agents.py              # A1/A2/A3 + 监督 Agent 定义
│   ├── data_exchange.py       # JSON 读写、合并、同步
│   ├── search_tools.py        # 各 Agent 的搜索工具定义
│   └── prompts.py             # 各 Agent 的 System Prompt 模板
```

### 4.2 `orchestrator.py` —— 瑞士轮调度核心

```python
class SwissDebateOrchestrator:
    """
    管理整个辩论生命周期：
    1. 初始化3个Agent + 1个监督Agent
    2. 按瑞士轮规则调度8个轮次
    3. 通过SSE向前端推送每个Agent的输出
    4. 管理 fact_check.json / debate_point.json / defend_point.json
    """

    ROUNDS = [
        # 阶段一：立论与驳论（1-3轮）
        ("open",      "A1", None,        "立论"),
        ("rebuttal",  "A2", ["A1"],      "对A1驳论"),
        ("rebuttal",  "A3", ["A1","A2"], "对A1/A2驳论"),

        # 阶段二：防守与反驳（4-6轮）
        ("defense",   "A1", ["A2","A3"], "反驳A2/A3，立论"),
        ("defense",   "A2", ["A1","A3"], "反驳A1/A3，立论"),
        ("defense",   "A3", ["A1","A2"], "反驳A1/A2，立论"),

        # 阶段三：材料取舍（第7轮）
        ("curation",  "ALL", None,       "各自决定进入报告的材料"),

        # 阶段四：监督整合（第8轮）
        ("supervise", "SUPERVISOR", None,"监督整合最终报告"),
    ]

    async def run(self, topic: str, ds_api_key: str,
                   volcano_key: str, volcano_bot_id: str,
                   tavily_key: str, event_queue: asyncio.Queue):
        """主循环"""
        ...

    async def _pause_for_fact_confirmation(self):
        """暂停辩论，等待用户确认事实（支持修改/确认/争议/驳回四种操作）"""
        ...

    async def _archive_round(self, round_num: int):
        """每轮完成后自动快照归档"""
        ...

    async def _save_full_session(self):
        """用户手动保存——全量打包当前状态到 archive"""
        ...

    async def _filter_rejected_facts(self, context: dict) -> dict:
        """从上下文中剔除 confidence=0 的驳回事实"""
        ...
```

### 4.3 `agents.py` —— Agent 定义

```python
class BaseAgent:
    """每个Agent具有独立的 System Prompt、工具集、数据源偏好"""

    agent_id: str       # "A1" / "A2" / "A3"
    personality: str    # "数据驱动的实证主义者" / "官方立场分析者" / "草根舆论观察者"
    tools: list[dict]   # OpenAI-format tool definitions
    search_bias: dict   # 搜索偏向（域名白名单/黑名单）

class AgentA1(BaseAgent):
    """私有数据专家 —— 检索 paper/ 目录下的历史报告"""
    search_bias = {"include": ["file://paper/*.pdf"], "exclude": []}
    tools = ["search_private_reports", "extract_data_from_report",
             "query_historical_trends"]

class AgentA2(BaseAgent):
    """官媒数据专家 —— 人民网、新华网、米游社、官方公告"""
    search_bias = {
        "include": ["people.com.cn", "xinhuanet.com",
                    "mihoyo.com", "mys.mihoyo.com"],
        "exclude": ["tieba.baidu.com"]
    }
    tools = ["search_official_media", "search_mihoyo_official",
             "verify_official_statement"]

class AgentA3(BaseAgent):
    """公域论坛专家 —— B站、知乎、小红书、贴吧、NGA、小黑盒"""
    search_bias = {
        "include": ["bilibili.com", "zhihu.com", "xiaohongshu.com",
                    "tieba.baidu.com", "nga.cn", "xiaoheihe.cn"],
        "exclude": []
    }
    tools = ["search_public_forums", "analyze_sentiment_trend",
             "track_hot_topics"]

class SupervisorAgent:
    """监督Agent —— 整合论点，生成最终报告"""
```

### 4.4 `search_tools.py` —— 双轨制搜索引擎

```python
class SearchEngine:
    """
    双轨制搜索引擎：
    - 主轨道：火山方舟 Bot 插件（月免 2 万次，优先使用）
    - 备轨道：Tavily Search API（月免 1000 次，Fallback）
    
    切换逻辑：
    1. 每次搜索先尝试火山方舟
    2. 火山返回 429（配额耗尽）或超时 → 自动切 Tavily
    3. Tavily 也失败 → 返回空结果 + SSE 推送 warning 事件
    """

    def __init__(self, volcano_key: str, volcano_bot_id: str, tavily_key: str):
        self.volcano_key = volcano_key
        self.volcano_bot_id = volcano_bot_id
        self.tavily_key = tavily_key
        self.volcano_available = True   # 动态标记火山是否可用

    async def search(self, query: str, domains: list[str] = None) -> str:
        """统一搜索入口，自动选择可用轨道"""
        if self.volcano_available:
            try:
                return await self._search_volcano(query)
            except QuotaExhaustedError:
                self.volcano_available = False
                # SSE 推送: volcano_quota_exhausted 事件
        return await self._search_tavily(query, domains)

    async def _search_volcano(self, query: str) -> str:
        """火山方舟 Bot 插件 —— 主轨道"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://ark.cn-beijing.volces.com/api/v3/bots/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.volcano_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.volcano_bot_id,
                    "messages": [{"role": "user", "content": query}],
                    "stream": False,
                },
                timeout=30,
            )
            if resp.status_code == 429:
                raise QuotaExhaustedError()
            data = resp.json()
            return self._format_volcano_results(data)

    async def _search_tavily(self, query: str, domains: list[str] = None) -> str:
        """Tavily Search API —— Fallback 轨道"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "query": query,
                    "api_key": self.tavily_key,
                    "max_results": 5,
                    "include_domains": domains or [],
                    "search_depth": "basic",
                },
                timeout=30,
            )
            return self._format_tavily_results(resp.json())

# A1 专用：私有数据不经过搜索引擎，直接解析 paper/ 目录 PDF
def search_private_reports(keywords: list[str]) -> str:
    """扫描 backend/paper/*.pdf，pdfplumber 提取文本，TF-IDF 匹配"""
    ...

# A2 专用：官媒搜索（通过双轨制，限定官媒域名）
async def search_official_media(engine: SearchEngine, query: str) -> str:
    return await engine.search(query, domains=[
        "people.com.cn", "xinhuanet.com",
        "mihoyo.com", "mys.mihoyo.com", "bbs.mihoyo.com"
    ])

# A3 专用：公域论坛搜索（通过双轨制，限定公域域名）
async def search_public_forums(engine: SearchEngine, query: str) -> str:
    return await engine.search(query, domains=[
        "bilibili.com", "zhihu.com", "xiaohongshu.com",
        "tieba.baidu.com", "nga.cn", "xiaoheihe.cn"
    ])

# 监督 Agent：通用搜索（不限域名）
async def search_web(engine: SearchEngine, query: str) -> str:
    return await engine.search(query)
```

### 4.5 `data_exchange.py` —— JSON 数据管理

```python
class DataExchange:
    """管理 debate_session 目录下的所有 JSON 文件"""
    
    def __init__(self, session_dir: Path):
        self.dir = session_dir

    # fact_check.json
    def add_fact(self, fact: dict) -> str:
    def mark_pending(self, fact_ids: list[str]):
    def confirm_fact(self, fact_id: str):
    def dispute_fact(self, fact_id: str, agent: str, reason: str):
    def get_new_facts_for_user(self) -> list[dict]:  # 需要玩家确认的

    # debate_point.json
    def write_round_output(self, agent_id: str, round_num: int, data: dict):
    def merge_incoming_points(self, agent_id: str) -> dict:  # 合并其他Agent的论点

    # defend_point.json
    def get_defend_point(self, agent_id: str) -> dict:
    def update_defend_point(self, agent_id: str, updates: dict):
    def sync_defend_points(self):  # 4-6轮后互相同步
```

---

## 五、SSE 通信协议设计

### 5.1 SSE 事件类型

```
event: round_start
data: {"round": 1, "agent": "A1", "stage": "open", "label": "A1 立论"}

event: agent_thinking
data: {"agent": "A1", "message": "正在检索 paper/ 目录下的历史报告..."}

event: tool_call
data: {"agent": "A1", "tool": "search_private_reports", "args": {"keywords": ["原神", "争议"]}}

event: tool_result
data: {"agent": "A1", "tool": "search_private_reports", "result_summary": "找到3份相关报告"}

event: agent_output
data: {"agent": "A1", "type": "partial", "content": "根据历史报告数据..."}

event: agent_output
data: {"agent": "A1", "type": "complete", "content": "...综上，本视频争议的核心在于信息不对称。"}

event: new_facts
data: {"facts": [
  {"id": "f1", "content": "视频发布于6月1日，播放量120万",
   "source": "A1", "evidence": "paper/xxx.pdf",
   "needs_confirmation": true, "table_fields": {  // 前端表格化解析字段
     "date": "2025-06-01", "play_count": 1200000, "platform": "B站"
   }}
]}

event: round_complete
data: {"round": 1, "agent": "A1", "summary": "立论完成：围绕3个核心论点展开",
       "round_snapshot_saved": true}

event: waiting_for_facts
data: {"pending_count": 5, "timeout_seconds": 300}

event: fact_user_action
data: {"fact_id": "f1", "action": "confirm", "agent": "user"}

event: round_saved              # 用户手动保存辩论进度
data: {"round": 3, "archive_path": "debate_sessions/abc123/archive/round_03/"}

event: volcano_quota_exhausted  # 火山方舟配额耗尽，自动切换
data: {"message": "火山方舟月免配额已用完，已自动切换至 Tavily 备轨", "fallback": "tavily"}

event: debate_complete
data: {"report": "markdown content...", "archive_path": "debate_sessions/abc123/"}

event: error
data: {"agent": "A1", "message": "搜索超时，重试中..."}
```

### 5.2 前端 SSE 消费（伪代码）

```typescript
const eventSource = new EventSource(`/api/debate/stream/${sessionId}`);

eventSource.addEventListener('agent_output', (e) => {
  const { agent, type, content } = JSON.parse(e.data);
  if (type === 'partial') {
    setAgentOutput(agent, prev => prev + content);  // 逐字追加
  } else {
    setAgentOutput(agent, content);                  // 完整替换
  }
});

eventSource.addEventListener('new_facts', (e) => {
  const { facts } = JSON.parse(e.data);
  setPendingFacts(prev => [...prev, ...facts]);      // 加入待确认列表
});

eventSource.addEventListener('debate_complete', (e) => {
  const { report } = JSON.parse(e.data);
  setFinalReport(report);
  eventSource.close();
});
```

---

## 六、前端实现规划

### 6.1 文件清单

```
frontend/src/
├── pages/
│   └── DebateHall.tsx          # 辩论厅主页（新页面，约600行）
├── components/
│   ├── AgentTerminal.tsx       # 单个 Agent 终端黑框组件（约150行）
│   ├── DebateProgress.tsx      # 辩论进度条（约80行）
│   ├── FactConfirmPanel.tsx    # 事实确认面板 —— 表格化编辑+四种操作（约200行）
│   └── DebateReportPreview.tsx # 最终报告预览（约100行）
```

### 6.2 路由和侧边栏修改

**`App.tsx`**：新增路由 `/debate-hall`

```tsx
<Route path="/debate-hall" element={<DebateHall />} />
```

**`Sidebar.tsx`**：新增菜单项

```tsx
{
  path: '/debate-hall',
  label: '舆情辩论厅',
  icon: <ChatBubbleIcon />,   // TDesign 图标
}
```

### 6.3 `DebateHall.tsx` 页面布局

```
┌───────────────────────────────────────────────────────────────┐
│  顶部控制栏                                                    │
│  [主题输入________________________] [开始辩论] [保存进度 💾]    │
│  [辩论轮次: 3/8] ████████░░░░░░░░░░░  [搜索轨: 火山 █ 备轨:就绪]│
├──────────────┬──────────────┬──────────────┤                  │
│  A1 私有数据  │  A2 官媒挖掘  │  A3 公域扫描  │                  │
│  ┌──────────┐│┌──────────┐│┌──────────┐│                    │
│  │ █ 终端   │││ █ 终端   │││ █ 终端   ││                    │
│  │ Cascadia │││ Cascadia │││ Cascadia ││                    │
│  │ 输出...  │││ 输出...  │││ 输出...  ││                    │
│  │          │││          │││          ││                    │
│  │ █        │││ █        │││ █        ││                    │
│  └──────────┘│└──────────┘│└──────────┘│                    │
│  [Tool调用]  │ [Tool调用]  │ [Tool调用]  │                    │
├──────────────┴──────────────┴──────────────┤                  │
│  事实确认面板（needs_confirmation 时展开）    │                  │
│  ┌────────────────────────────────────────┐│                  │
│  │ 事实 #1  来源: A1  证据: paper/xxx.pdf   ││                  │
│  │ ┌──────────────┬──────────────────────┐││                  │
│  │ │ 字段   │ 值              │                   ││                  │
│  │ ├────────┼─────────────────┤                   ││                  │
│  │ │ 日期   │ 2025-06-01  [✎] │  ← 单元格可编辑   ││                  │
│  │ │ 播放量 │ 1,200,000  [✎]  │                   ││                  │
│  │ │ 平台   │ B站        [✎]  │                   ││                  │
│  │ └────────┴─────────────────┘                   ││                  │
│  │ [确认 ✓] [争议 ≈] [驳回 ✗] [应用修改 📝]       ││                  │
│  │ ──────────────────────────────────────        ││                  │
│  │ 事实 #2  来源: A2  ...                        ││                  │
│  │ ...                                          ││                  │
│  └──────────────────────────────────────────────┘│                  │
├──────────────────────────────────────────────────┤                  │
│  最终报告预览区（辩论结束后显示）                    │                  │
│  ┌────────────────────────────────────────────┐ │                  │
│  │ # 舆情深度分析报告                          │ │                  │
│  │ ...                                        │ │                  │
│  │ [导出PDF] [复制Markdown]                     │ │                  │
│  └────────────────────────────────────────────┘ │                  │
└──────────────────────────────────────────────────────┘
```

### 6.4 `FactConfirmPanel.tsx` 组件设计

每个待确认事实渲染为一张可编辑表格卡片：

- **表格化解析**：后端在生成事实时调用 DeepSeek 将自然语言事实自动拆解为 key-value 表格字段（`table_fields`），前端渲染为可编辑表格
- **单元格编辑**：双击任意单元格进入编辑模式，修改后"应用修改"按钮高亮
- **四种操作按钮**：
  - **确认** (绿色)：confidence=1.0，`action: "confirm"`，立即通过
  - **争议** (黄色)：confidence=0.5，`action: "dispute"`，事实标注为存疑但仍可引用
  - **驳回** (红色)：confidence=0.0，`action: "reject"`，后续所有 Agent 禁止引用，已引用处自动标记无效
  - **应用修改** (蓝色)：`action: "modify"`，将编辑后的表格内容写回 `content` 字段，`original_content` 保留原始值，confidence=1.0
- **批量操作**：顶部提供 [全部确认] [全部争议] 快捷按钮
- **已驳回标签**：被驳回的事实显示红色删除线和"已驳回"标签，后续轮次不再出现在面板中

- **配色**：全黑背景 `#0a0a0a`，亮绿色输出 `#00ff41`，白色思考中 `#aaaaaa`
- **字体**：Cascadia Code（项目已在 pdf_report.py 中注册），前端用 CSS `@font-face` 引入
- **滚动**：自动滚到底部，带平滑过渡
- **光标闪烁**：正在输出时末尾显示闪烁绿色光标 `█`
- **Tool 调用提示**：灰色前缀 `[tool]` 标记
- **角色标签**：终端顶部固定 Agent 名称 + 数据源图标

CSS 关键样式：
```css
.agent-terminal {
  background: #0a0a0a;
  border: 1px solid #1a3a1a;
  border-radius: 8px;
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #00ff41;
  height: 100%;
  overflow-y: auto;
  padding: 16px;
}

.agent-terminal .tool-call {
  color: #6b7280;
}

.agent-terminal .thinking {
  color: #9ca3af;
  font-style: italic;
}

.agent-terminal .cursor-blink {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}
```

---

## 七、辩论流程时序图

```
时间 →
前端:  输入主题 → [开始辩论]
后端:  ┌─ 创建会话 → 初始化双轨搜索引擎（火山主 + Tavily备）
       │   └─ SSE: debate_started
       │
第1轮: ├─ A1 搜索 paper/ → A1 分析 → A1 立论 → 输出 → 生成 fact_check.json → 广播给 A2/A3
       │   ├─ SSE: agent_output(A1, streaming...)
       │   └─ 💾 快照: archive/round_01/ 写入（A1 完整上下文）
       │
第2轮: ├─ A2 搜索官媒（火山主→Tavily备）→ A2 分析 → 驳论 → 更新 fact_check → 广播
       │   ├─ SSE: agent_output(A2, streaming...), new_facts[...]
       │   └─ 💾 快照: archive/round_02/ 写入
       │
第3轮: ├─ A3 搜索公域 → A3 分析 → 驳论 A1/A2 → 输出 → 更新 → 广播
       │   ├─ SSE: agent_output(A3, streaming...), new_facts[...]
       │   ├─ 💾 快照: archive/round_03/ 写入
       │   └─ 📌 用户可在此按 [保存进度]，全量归档打包
       │
📌:    ├─ 等待玩家事实确认（SSE: waiting_for_facts, timeout=300s）
       │   前端弹出 FactConfirmPanel
       │   ├─ 表格化编辑 → 用户可修改任意单元格内容
       │   ├─ [确认✓] confidence=1.0 | [争议≈] confidence=0.5 | [驳回✗] confidence=0.0
       │   └─ POST /api/debate/confirm-facts  (批量提交)
       │
第4轮: ├─ A1 搜索反驳 → 分析（排除 confidence=0 的驳回事实）→ 反驳 A2/A3 → 最终立论
       │   ├─ SSE: agent_output(A1, ...)
       │   └─ 💾 快照: archive/round_04/ 写入
       │
第5轮: ├─ A2 搜索反驳 → 分析 → 反驳 A1/A3 → 最终立论
       │   └─ 💾 快照: archive/round_05/ 写入
       │
第6轮: ├─ A3 搜索反驳 → 分析 → 反驳 A1/A2 → 最终立论
       │   ├─ 💾 快照: archive/round_06/ 写入
       │   └─ 📌 用户可再次 [保存进度]
       │
第7轮: ├─ A1/A2/A3 并行执行 → 各自决定进入报告的材料（curation）
       │   ├─ SSE: agent_output(A1/A2/A3, parallel streaming...)
       │   └─ 💾 快照: archive/round_07/ 写入
       │
第8轮: └─ 监督 Agent 整合全量辩论记录 → 生成最终报告
           ├─ SSE: debate_complete + final_report
           └─ 💾 全量归档: archive/round_08/ + session_meta.json 最终版本

前端:  显示最终报告 → [导出PDF] [复制Markdown] [查看辩论回放]
```

---

## 八、关键技术难点和解决方案

### 8.1 实时流式输出

**难点**：三个 Agent 并发输出，前端需要同时展示三个终端的实时文本。

**方案**：后端用 `asyncio.Queue` 收集所有 Agent 输出事件，SSE 端点从 Queue 读取并推送。Agent 调用 DeepSeek 时用 `stream=True`，每收到一个 token 就推送到 Queue。

```python
async def agent_stream_to_queue(agent_id, messages, tools, queue):
    """调用 DeepSeek streaming，逐 token 推送到 SSE queue"""
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", DEEPSEEK_URL, json={...}) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0].get("delta", {})
                    if delta.get("content"):
                        await queue.put({
                            "event": "agent_output",
                            "data": {"agent": agent_id, "type": "partial",
                                     "content": delta["content"]}
                        })
```

这将使三个 Agent 的输出在前端近乎同时滚动，非常酷。

### 8.2 三个 Agent 的并行与串行

**第1-3轮**：按顺序（A1→A2→A3），因为每轮需要等待上一轮的输出才能驳论。

**第4-6轮**：可以部分并行——A2 和 A3 的初始搜索可以在 A1 运行时预加载，但驳论逻辑仍需串行。

**第7轮**：A1/A2/A3 可以完全并行执行。

### 8.3 PDF 报告解析（A1 搜私有数据）

`paper/` 目录下的 PDF 需要用 `pdfplumber` 或 `markitdown` 提取文本，然后建立简单的检索索引（关键词匹配或 TF-IDF）。

### 8.4 事实确认的交互设计

SSE 推送 `new_facts` 事件后，前端展开确认面板。辩论暂停（`waiting_facts` 状态），直到玩家确认所有事实才继续。超时后（如 5 分钟）自动将所有 `pending` 事实标记为 `disputed` 并继续。

### 8.5 Token 管理

8 轮辩论的上下文累计可能很大。使用 `debate_point.json` 结构化压缩上下文（只传关键论点和事实ID，不传完整文本），而不是每次都传完整历史。DeepSeek v4 支持 1M 上下文，对于精心压缩后的辩论应该是足够的。

---

## 九、依赖新增

### 后端新依赖

```
# 搜索 —— 双轨制
tavily-python>=0.3.0       # Tavily 搜索 API（备轨）
# 火山方舟无需额外 SDK，直接 httpx 调用 Bot API（主轨）

# PDF 解析（A1 用）
pdfplumber>=0.11.0         # PDF 文本提取 + 检索
markitdown>=0.0.1          # 备选 PDF/Audio 提取

# 流式 HTTP（已有 httpx，确认支持 async stream）
# httpx 已安装，async stream 原生支持

# SSE
sse-starlette>=2.0.0       # FastAPI SSE 支持

# 文本检索（A1 私有数据搜索）
scikit-learn>=1.3.0        # TF-IDF 向量化（用于 paper/ 目录的 PDF 内容检索）
```

### 环境变量/配置新增

```
# 火山方舟
VOLCANO_API_KEY=           # 火山方舟 API Key
VOLCANO_BOT_ID=            # 已配置联网搜索插件的 Bot ID

# Tavily（备轨）
TAVILY_API_KEY=            # Tavily API Key

# DeepSeek（沿用现有）
DEEPSEEK_API_KEY=          # 现有 accounts 表中的 key
```

---

## 十、实施步骤（分 4 个 Phase）

### Phase 1：基础架构（2-3 天）
- [ ] 创建 `backend/app/debate/` 模块目录
- [ ] 实现 `data_exchange.py`（JSON 读写、合并、快照归档逻辑）
- [ ] 实现 `search_tools.py`（双轨制 SearchEngine 类 + A1/A2/A3 专用搜索函数）
- [ ] 实现 `agents.py`（BaseAgent + AgentA1/A2/A3 + SupervisorAgent + System Prompt 模板）
- [ ] 实现 `orchestrator.py` 基础框架（DebateSession 管理 + SwissRoundManager 调度骨架）
- [ ] 新增 SQLite 表：`debate_sessions`、`debate_facts`、`debate_round_snapshots`
- [ ] 新增 API 路由：`/api/debate/create`、`/api/debate/stream/{id}`、`/api/debate/confirm-facts`、`/api/debate/save/{id}`、`/api/debate/sessions`（历史列表）
- [ ] 火山方舟 Bot 创建和联网插件配置

### Phase 2：辩论引擎（2-3 天）
- [ ] 实现 DeepSeek async streaming 调用（逐 token SSE 推送）
- [ ] 实现 8 轮瑞士轮逻辑（串行 + 第7轮并行调度）
- [ ] 实现事实确认暂停/恢复机制（timeout 300s）
- [ ] 实现四种用户事实操作的处理逻辑（confirm/dispute/reject/modify）
- [ ] 实现驳回事实的全局过滤（confidence=0 的事实后续 Agent 不可引用）
- [ ] 实现 defend_point.json 的同步和合并逻辑
- [ ] 实现每轮完成后的自动快照归档（archive/round_NN/）
- [ ] 实现监督 Agent 整合逻辑
- [ ] 实现双轨制搜索自动切换（火山配额耗尽 → Tavily Fallback + SSE 通知）
- [ ] 端到端测试一个完整 8 轮辩论

### Phase 3：前端实现（2-3 天）
- [ ] 新增 `/debate-hall` 路由和页面
- [ ] 实现 `AgentTerminal.tsx`（三个黑框终端 + 逐字打字效果 + 光标闪烁）
- [ ] 实现 `DebateProgress.tsx`（轮次进度条 + 搜索轨道状态指示）
- [ ] 实现 `FactConfirmPanel.tsx`（表格化编辑 + 四种操作按钮 + 批量操作）
- [ ] 实现 `DebateReportPreview.tsx`（最终报告展示 + 导出）
- [ ] 侧边栏新增入口
- [ ] SSE EventSource 连接和状态管理
- [ ] 引入 Cascadia Code 字体（@font-face）
- [ ] [保存进度] 按钮交互（调用 `/api/debate/save/{id}`）

### Phase 4：打磨（1-2 天）
- [ ] PDF 解析集成（A1 的 paper/ 搜索 + TF-IDF 索引）
- [ ] 火山方舟 Bot 最终联调（确认联网搜索插件工作正常）
- [ ] Tavily Fallback 切换测试
- [ ] 搜索轨道状态指示器（前端实时显示当前使用的搜索引擎）
- [ ] 超时和错误恢复（单轮失败不中断整个辩论）
- [ ] 最终报告导出 PDF（复用现有 pdf_report.py 的样式系统）
- [ ] 辩论历史回放功能（读取 archive/ 目录重现辩论过程）
- [ ] UI 动画和细节打磨（终端闪烁、进度条渐变、事实确认面板滑入动画）
- [ ] 端到端完整测试

---

## 十一、总结

这个功能的本质是将 Miho-spot 从"工具型应用"升级为"自主分析型智能体平台"。核心创新点在于：

1. **多源异构数据融合**：私有数据（历史报告）+ 官方渠道 + 公域论坛，三个 Agent 各司其职
2. **对抗性辩论提升分析质量**：瑞士轮机制迫使 Agent 互相检验事实、挑战论点，比单一 Agent 分析更深入可靠
3. **四维度人机协同事实验证**：修改（保留原始值）、确认（采信）、争议（降权）、驳回（禁引），玩家对事实拥有最终裁判权，杜绝 AI 幻觉
4. **结构化上下文压缩**：debate_point.json 和 defend_point.json 大幅减少 token 消耗
5. **双轨制搜索容灾**：火山方舟（月免 2 万次）作为主轨，Tavily 作为备轨，配额耗尽自动切换不中断辩论
6. **辩论全程可追溯**：每轮自动归档 Agent 的完整输入/输出/工具调用/事实变更，支持辩论结束后回放任意轮次

技术实现上，新增约 2000 行代码（后端 ~800 行 + 前端 ~700 行 + 测试/配置 ~500 行），预计 10-15 个工作日完成。最关键的架构决策是手工 Agent Loop（复用现有 DeepSeek 调用）+ SSE 实时流推送 + 文件系统 + SQLite 双层持久化存储。
