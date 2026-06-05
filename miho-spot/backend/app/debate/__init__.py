"""
Miho-spot 多 Agent 瑞士轮辩论引擎

三个专业 Agent（私有数据 / 官媒 / 公域论坛）进行 8 轮结构化辩论，
由监督 Agent 整合生成舆情深度分析报告。
"""

from .orchestrator import SwissDebateOrchestrator
from .agents import AgentA1, AgentA2, AgentA3, SupervisorAgent
from .data_exchange import DataExchange
from .search_tools import SearchEngine
