"""
Agent 定义 —— 三个专业 Agent + 监督 Agent

每个 Agent 封装了 system prompt、search bias、tool schema，
与 DeepSeek API 的 Tool Calling 接口对齐。
"""

import json
from typing import Any, Optional

from .prompts import (
    A1_SYSTEM, A2_SYSTEM, A3_SYSTEM, SUPERVISOR_SYSTEM,
    STAGE_OPENING, STAGE_REBUTTAL, STAGE_DEFENSE, STAGE_CURATION,
)
from .search_tools import (
    search_private_reports, search_official_media,
    search_public_forums, search_web, SearchEngine,
)

# ── Tool Schema 定义（OpenAI / DeepSeek 兼容格式）────────────────

TOOL_SCHEMAS = {
    "search_private_reports": {
        "type": "function",
        "function": {
            "name": "search_private_reports",
            "description": "搜索 Miho-spot paper/ 目录下的历史舆情分析报告。输入逗号分隔的关键词",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "搜索关键词，多个关键词用逗号分隔",
                    }
                },
                "required": ["keywords"],
            },
        },
    },
    "search_official_media": {
        "type": "function",
        "function": {
            "name": "search_official_media",
            "description": "搜索人民网、新华网、央视网、米哈游官方等官媒渠道的信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询",
                    }
                },
                "required": ["query"],
            },
        },
    },
    "search_public_forums": {
        "type": "function",
        "function": {
            "name": "search_public_forums",
            "description": "搜索 B站、知乎、小红书、贴吧、NGA、小黑盒等公域社区论坛",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询",
                    }
                },
                "required": ["query"],
            },
        },
    },
    "search_web": {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "通用互联网搜索（不限域名）",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询",
                    }
                },
                "required": ["query"],
            },
        },
    },
}

# ── 工具执行映射 ──────────────────────────────────────────

async def _execute_tool(tool_name: str, args: dict,
                        engine: SearchEngine = None) -> str:
    """根据 tool_name 执行对应的搜索工具"""
    if tool_name == "search_private_reports":
        result = await search_private_reports(args.get("keywords", ""))
        return result["results_text"]
    elif tool_name == "search_official_media":
        result = await search_official_media(engine, args.get("query", ""))
        return json.dumps(result["results"], ensure_ascii=False, indent=2)
    elif tool_name == "search_public_forums":
        result = await search_public_forums(engine, args.get("query", ""))
        return json.dumps(result["results"], ensure_ascii=False, indent=2)
    elif tool_name == "search_web":
        result = await search_web(engine, args.get("query", ""))
        return json.dumps(result["results"], ensure_ascii=False, indent=2)
    return "未知工具"


# ── Agent 类 ──────────────────────────────────────────────

class BaseAgent:
    """Agent 基类"""

    agent_id: str = ""
    personality: str = ""
    system_prompt: str = ""
    tool_schemas: list = []
    search_engine: Optional[SearchEngine] = None

    def __init__(self, search_engine: SearchEngine = None):
        self.search_engine = search_engine

    @property
    def tools(self) -> list:
        return self.tool_schemas

    async def execute_tool(self, tool_name: str, args: dict) -> str:
        return await _execute_tool(tool_name, args, self.search_engine)

    def build_system_prompt(self, stage: str = "open",
                            targets: list = None,
                            topic: str = "") -> str:
        """根据辩论阶段构建完整的 system prompt"""
        prompt = self.system_prompt

        if stage == "open":
            prompt += STAGE_OPENING
        elif stage == "rebuttal":
            targets_str = "、".join(targets or [])
            prompt += STAGE_REBUTTAL.format(targets=targets_str)
        elif stage == "defense":
            targets_str = "、".join(targets or [])
            prompt += STAGE_DEFENSE.format(targets=targets_str)
        elif stage == "curation":
            prompt += STAGE_CURATION

        if topic:
            prompt = f"本次辩论主题：{topic}\n\n" + prompt

        prompt += "\n\n重要提醒：始终以 JSON 结构化格式组织你的论点，便于后续处理。"
        return prompt


class AgentA1(BaseAgent):
    """私有数据专家 —— 检索 paper/ 目录下的历史报告"""

    agent_id = "A1"
    personality = "数据驱动的实证主义者"
    system_prompt = A1_SYSTEM
    tool_schemas = [TOOL_SCHEMAS["search_private_reports"]]


class AgentA2(BaseAgent):
    """官媒数据专家 —— 人民网、新华网、米游社"""

    agent_id = "A2"
    personality = "官方立场分析者"
    system_prompt = A2_SYSTEM
    tool_schemas = [TOOL_SCHEMAS["search_official_media"]]


class AgentA3(BaseAgent):
    """公域论坛专家 —— B站、知乎、小红书、贴吧等"""

    agent_id = "A3"
    personality = "草根舆论观察者"
    system_prompt = A3_SYSTEM
    tool_schemas = [TOOL_SCHEMAS["search_public_forums"]]


class SupervisorAgent(BaseAgent):
    """监督 Agent —— 整合论点，生成最终报告"""

    agent_id = "SUPERVISOR"
    personality = "公正的舆情监督分析员"
    system_prompt = SUPERVISOR_SYSTEM
    tool_schemas = [TOOL_SCHEMAS["search_web"]]


# ── Agent 工厂 ────────────────────────────────────────────

def create_agents(search_engine: SearchEngine = None) -> dict:
    """创建三个辩论 Agent + 监督 Agent"""
    return {
        "A1": AgentA1(search_engine),
        "A2": AgentA2(search_engine),
        "A3": AgentA3(search_engine),
        "SUPERVISOR": SupervisorAgent(search_engine),
    }
