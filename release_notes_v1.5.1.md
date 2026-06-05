## v1.5.1 — 搜索引擎重构 + 监督Agent修复 (2026-06-06)

### 三轨搜索引擎：零 LLM Token 搜索

将搜索主力从火山方舟 Bot 迁移到纯搜索 API，辩论过程中不再消耗任何 LLM Token：

- **主力**：DuckDuckGo (`ddgs`) — 免费无限，纯 Python 调用
- **备轨1**：Tavily — 月免 1000 次，结构化结果
- **备轨2**：Serper.dev — 2500 次免费，Google 品质

火山方舟的 50 万 Token 额度完全回归 DeepSeek 辩论分析。

### 监督 Agent 报告产出修复

修复三个导致监督 Agent 输出空白的 Bug：
- 移除强制 JSON 格式化指令（流式输出与 JSON 冲突）
- 移除监督 Agent 的搜索工具（它只需整合现有辩论数据）
- 修复 `max_tool_calls=0` 时跳过 LLM 调用的死循环
- 提示词改为直接写报告指令，Token 上限提升至 8000

### 新增 Docker SearXNG 配置

`searxng/` 目录包含 docker-compose + 配置文件，待 WSL 就绪后可部署本地元搜索引擎作为搜索主力。
