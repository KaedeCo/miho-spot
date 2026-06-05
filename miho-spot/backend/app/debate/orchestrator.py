"""
瑞士轮辩论编排引擎

管理完整的 8 轮辩论生命周期：
- 轮次调度（立论 → 驳论 → 防守 → 策展 → 监督整合）
- SSE 事件推送（逐 token 流式输出 + 结构事件）
- 事实确认暂停/恢复机制
- 每轮自动快照归档
"""

import asyncio
import json
import traceback
from datetime import datetime
from pathlib import Path

import httpx

from .agents import create_agents, _execute_tool
from .data_exchange import DataExchange
from .search_tools import SearchEngine, QuotaExhaustedError
from .prompts import STAGE_OPENING, STAGE_REBUTTAL, STAGE_DEFENSE, STAGE_CURATION


# ── 轮次定义 ──────────────────────────────────────────────

ROUND_DEFINITIONS = [
    # (round_num, stage, agent_id, targets, label)
    (1, "open",     "A1",  None,          "A1 立论"),
    (2, "rebuttal", "A2",  ["A1"],        "A2 对 A1 驳论"),
    (3, "rebuttal", "A3",  ["A1", "A2"],  "A3 对 A1/A2 驳论"),
    (4, "defense",  "A1",  ["A2", "A3"],  "A1 反驳 A2/A3，最终立论"),
    (5, "defense",  "A2",  ["A1", "A3"],  "A2 反驳 A1/A3，最终立论"),
    (6, "defense",  "A3",  ["A1", "A2"],  "A3 反驳 A1/A2，最终立论"),
    (7, "curation", "ALL", None,          "材料取舍"),
    (8, "supervise","SUPERVISOR", None,   "监督整合最终报告"),
]


# ── 编排器 ────────────────────────────────────────────────

class SwissDebateOrchestrator:
    """瑞士轮辩论主控引擎"""

    def __init__(self, topic: str, ds_api_key: str,
                 volcano_key: str = None, volcano_bot_id: str = None,
                 tavily_key: str = None, base_dir: Path = None):
        self.topic = topic
        self.ds_api_key = ds_api_key
        self.search_engine = SearchEngine(
            volcano_key=volcano_key,
            volcano_bot_id=volcano_bot_id,
            tavily_key=tavily_key,
        )
        self.agents = create_agents(self.search_engine)
        self._base_dir = base_dir or Path(__file__).resolve().parent.parent.parent
        self._session_dir = None
        self.data_exchange: DataExchange = None
        self.current_round = 0
        self.is_paused = False
        self.pause_event = asyncio.Event()
        self.pause_event.set()  # 初始不暂停

    # ── 主循环 ────────────────────────────────────────────

    async def run(self, event_queue: asyncio.Queue) -> dict:
        """
        执行完整辩论流程。
        event_queue 用于 SSE 推送事件到前端。
        返回最终报告 dict。
        """
        # 初始化会话目录
        session_id = datetime.now().strftime("debate_%Y%m%d_%H%M%S")
        self._session_dir = self._base_dir / "debate_sessions" / session_id
        self.data_exchange = DataExchange(self._session_dir)

        await self._push_event(event_queue, "debate_started", {
            "session_id": session_id,
            "topic": self.topic,
            "search_track": self.search_engine.current_track,
        })

        try:
            for round_num, stage, agent_id, targets, label in ROUND_DEFINITIONS:
                self.current_round = round_num

                await self._push_event(event_queue, "round_start", {
                    "round": round_num, "stage": stage,
                    "agent": agent_id, "label": label,
                    "total_rounds": len(ROUND_DEFINITIONS),
                })

                try:
                    if agent_id == "ALL":
                        # 第7轮：三个 Agent 并行策展
                        await self._execute_parallel_curation(event_queue, round_num)
                    elif agent_id == "SUPERVISOR":
                        # 第8轮：监督 Agent 整合
                        await self._execute_supervisor(event_queue, round_num)
                    else:
                        # 常规轮次：单 Agent 执行
                        await self._execute_agent_round(
                            event_queue, round_num, stage,
                            agent_id, targets, label)
                except Exception as round_err:
                    traceback.print_exc()
                    await self._push_event(event_queue, "round_error", {
                        "round": round_num, "agent": agent_id,
                        "error": str(round_err)[:300],
                    })
                    # 单轮失败 → 自动停止，允许保存不完整结果
                    raise  # 抛到外层 run() 的 except 中，触发自动保存

                # 每轮结束后推送文件传递信息（紫色可视化调试）
                if round_num < len(ROUND_DEFINITIONS):
                    next_round = ROUND_DEFINITIONS[round_num]  # round_num 从1开始
                    next_agent = next_round[2]
                    if next_agent not in ("ALL", "SUPERVISOR", agent_id):
                        await self._push_event(event_queue, "file_transfer", {
                            "from_agent": agent_id,
                            "to_agent": next_agent,
                            "files": [
                                "debate_point.json",
                                "fact_check.json"
                            ],
                            "message": f"{agent_id} → {next_agent}: debate_point.json + fact_check.json"
                        })
                    elif next_agent == agent_id:
                        pass  # 同一个agent不传给自己

                # 第3轮完成后，暂停等待用户确认事实
                if round_num == 3:
                    await self._pause_for_fact_confirmation(event_queue)

            # 生成最终报告
            final_report = self._build_final_report()

            # 生成 PDF
            pdf_path = ""
            try:
                pdf_path = self.generate_pdf()
                final_report["pdf_path"] = pdf_path
                # 将 PDF 路径写回 supervisor_report 供下载端点使用
                sr = self.data_exchange.load_supervisor_report()
                sr["pdf_path"] = pdf_path
                self.data_exchange.save_supervisor_report(sr)
            except Exception as pdf_err:
                print(f"[PDF] 生成失败: {pdf_err}", flush=True)

            await self._push_event(event_queue, "debate_complete", {
                "report": final_report,
                "pdf_path": pdf_path,
                "session_dir": str(self._session_dir),
            })
            return final_report

        except Exception as e:
            traceback.print_exc()
            # 自动保存不完整结果
            partial_report = self._build_final_report()
            try:
                if self.data_exchange:
                    save_path = self.data_exchange.save_full_session()
                    partial_report["saved_at"] = save_path
            except:
                pass
            await self._push_event(event_queue, "debate_error", {
                "error": str(e),
                "round": self.current_round,
                "partial_report": partial_report,
                "session_dir": str(self._session_dir) if self._session_dir else "",
            })

    # ── 单 Agent 轮次执行 ─────────────────────────────────

    async def _execute_agent_round(self, event_queue: asyncio.Queue,
                                   round_num: int, stage: str,
                                   agent_id: str, targets: list,
                                   label: str):
        """执行单个 Agent 的一轮辩论 — 两趟式：搜索趟 + 分析趟"""
        agent = self.agents[agent_id]

        # 构建 system prompt
        system_prompt = agent.build_system_prompt(
            stage=stage, targets=targets, topic=self.topic)

        # 构建输入上下文
        input_context = self._build_input_context(agent_id, round_num, stage)

        # ══════════ 第一趟：搜索 ══════════
        search_messages = [
            {"role": "system", "content": system_prompt},
        ]
        if input_context:
            search_messages.append({
                "role": "system",
                "content": f"【历史辩论上下文】\n{input_context}",
            })
        search_messages.append({
            "role": "user",
            "content": (
                f"第{round_num}轮 - 搜索阶段\n"
                f"任务：{label}\n\n"
                f"你现在只需要做一件事：调用搜索工具，围绕辩论主题尽可能多地收集相关信息和反证资料。"
                f"不要写分析，不要写结论，只做搜索。可以多次搜索不同关键词。"
            ),
        })

        # 搜索趟：强制使用工具
        search_results_text = await self._call_search_pass(
            agent, search_messages, event_queue, agent_id)

        await self._push_event(event_queue, "agent_thinking", {
            "agent": agent_id, "message": "搜索完成，正在整合分析...",
        })

        # ══════════ 第二趟：分析（无工具） ══════════
        analysis_messages = [
            {"role": "system", "content": system_prompt},
        ]
        if input_context:
            analysis_messages.append({
                "role": "system",
                "content": f"【历史辩论上下文】\n{input_context}",
            })
        analysis_messages.append({
            "role": "system",
            "content": f"【你的搜索结果 — 以下是你上一轮搜索获得的信息，请基于这些信息进行分析】\n{search_results_text}",
        })
        analysis_messages.append({
            "role": "user",
            "content": (
                f"第{round_num}轮 - 分析阶段\n"
                f"任务：{label}\n\n"
                f"搜索已经完成。现在请你基于上面【你的搜索结果】中的信息，"
                f"按照 System Prompt 中规定的完整格式（搜索摘要 → 核心论点/驳论 → 整体判断等），"
                f"输出一份完整的辩论分析。\n\n"
                f"你现在没有搜索工具可用——你的全部素材就是你上面看到的搜索结果。"
                f"请整合这些素材，完成你的完整论述。"
            ),
        })

        # 分析趟：无工具调用
        raw_output = await self._call_analysis_pass(
            agent, analysis_messages, event_queue, agent_id)

        # 提取事实，立即推送到前端面板
        fact_changes = self._extract_and_record_facts(raw_output, agent_id)
        if fact_changes:
            # 推送调试事件（终端紫色）
            await self._push_event(event_queue, "facts_extracted", {
                "agent": agent_id,
                "count": len(fact_changes),
                "facts": [{"id": f["fact_id"], "content": f["content"][:100]} for f in fact_changes[:5]],
            })
            # 推送事实确认面板事件
            await self._push_event(event_queue, "new_facts", {
                "facts": [
                    {
                        "id": f["fact_id"],
                        "content": f["content"],
                        "source": f"Agent {agent_id}",
                        "evidence": f"第{round_num}轮",
                        "table_fields": {"raw_text": f["content"]},
                        "needs_confirmation": True,
                    }
                    for f in fact_changes
                ],
            })

        # 保存 debate_point.json
        arguments = self._parse_arguments(raw_output, agent_id)
        self.data_exchange.save_debate_point(
            round_num=round_num, agent_id=agent_id, stage=stage,
            targets=targets or [], arguments=arguments,
            concessions=[], key_insights=[])

        # 更新 defend_point.json
        if stage == "open":
            self.data_exchange.save_defend_point(agent_id, {
                "core_thesis": arguments[0].get("claim", "") if arguments else "",
                "supporting_evidence": arguments,
                "responses_to_challenges": [],
                "acknowledged_strengths_of_others": [],
                "last_modified_round": round_num,
            })

        # 快照归档
        self.data_exchange.snapshot_round(
            round_num=round_num, agent_id=agent_id,
            system_prompt=system_prompt,
            input_context=input_context or "",
            tool_calls=[],
            raw_output=raw_output,
            fact_changes=fact_changes)


    # ── 第一趟：搜索（带 Tool Calling）─────────────────────

    async def _call_search_pass(self, agent, messages: list,
                                event_queue: asyncio.Queue,
                                agent_id: str) -> str:
        """搜索阶段：强制使用工具搜索，收集所有搜索结果文本。"""
        collected_results = []

        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": 200,
                "temperature": 0.3,
                "stream": False,
            }
            if agent.tools:
                payload["tools"] = agent.tools
                payload["tool_choice"] = "required"  # 强制调用工具

            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.ds_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
            data = resp.json()
            msg = data["choices"][0]["message"]

            # 收集 tool_calls
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except:
                        args = {}

                    await self._push_event(event_queue, "tool_call", {
                        "agent": agent_id,
                        "tool": tool_name,
                        "args": args,
                    })

                    result = await agent.execute_tool(tool_name, args)

                    await self._push_event(event_queue, "tool_result", {
                        "agent": agent_id,
                        "tool": tool_name,
                        "result_summary": result[:200] + ("..." if len(result) > 200 else ""),
                    })

                    collected_results.append(
                        f"【搜索工具: {tool_name}】\n参数: {json.dumps(args, ensure_ascii=False)}\n结果:\n{result}"
                    )

            # 如果还有任何文本输出也保存
            if msg.get("content"):
                collected_results.insert(0, f"【搜索思考】\n{msg['content']}")

        result_text = "\n\n---\n\n".join(collected_results) if collected_results else "（无搜索结果）"
        return result_text


    # ── 第二趟：分析（无工具，纯写分析）────────────────────

    async def _call_analysis_pass(self, agent, messages: list,
                                  event_queue: asyncio.Queue,
                                  agent_id: str) -> str:
        """分析阶段：无工具调用，纯文本 streaming 输出分析。"""
        full_content = ""

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": 4000,
                "temperature": 0.5,
                "stream": True,
                # 不传 tools — 无工具可用
            }

            async with client.stream(
                "POST",
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.ds_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120,
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk_data = line[6:].strip()
                    if chunk_data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(chunk_data)
                        delta = chunk["choices"][0].get("delta", {})
                        if delta.get("content"):
                            full_content += delta["content"]
                            await self._push_event(event_queue, "agent_output", {
                                "agent": agent_id,
                                "type": "partial",
                                "content": delta["content"],
                            })
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

        await self._push_event(event_queue, "agent_output", {
            "agent": agent_id,
            "type": "complete",
            "content": full_content,
        })

        return full_content

    # ── DeepSeek Streaming 调用 ───────────────────────────

    async def _call_deepseek_streaming(self, agent, messages: list,
                                       event_queue: asyncio.Queue,
                                       agent_id: str,
                                       max_tool_calls: int = 5,
                                       max_tokens: int = 1500) -> str:
        """
        调用 DeepSeek API，带 Tool Calling 的 Agent Loop。
        streaming 模式下逐 token 推送 event_queue。
        """
        full_content = ""
        current_messages = list(messages)
        tool_call_count = 0

        while tool_call_count < max_tool_calls:
            await self._push_event(event_queue, "agent_thinking", {
                "agent": agent_id,
                "message": "正在思考..." if tool_call_count == 0 else "正在调用工具...",
            })

            # 调用 DeepSeek
            async with httpx.AsyncClient() as client:
                payload = {
                    "model": "deepseek-chat",
                    "messages": current_messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.5,
                    "stream": True,
                }
                if agent.tools:
                    payload["tools"] = agent.tools
                    payload["tool_choice"] = "auto"

                tool_calls_buffer = []
                current_tool_call = None

                async with client.stream(
                    "POST",
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.ds_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=120,
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        chunk_data = line[6:].strip()
                        if chunk_data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(chunk_data)
                            delta = chunk["choices"][0].get("delta", {})

                            # 文本内容 → SSE 流式推送
                            if delta.get("content"):
                                full_content += delta["content"]
                                await self._push_event(event_queue, "agent_output", {
                                    "agent": agent_id,
                                    "type": "partial",
                                    "content": delta["content"],
                                })

                            # Tool calls → 收集
                            if delta.get("tool_calls"):
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    while len(tool_calls_buffer) <= idx:
                                        tool_calls_buffer.append(None)
                                    if tool_calls_buffer[idx] is None:
                                        tool_calls_buffer[idx] = {
                                            "id": tc.get("id", ""),
                                            "function": {
                                                "name": "",
                                                "arguments": "",
                                            },
                                        }
                                    if tc.get("id"):
                                        tool_calls_buffer[idx]["id"] = tc["id"]
                                    if tc.get("function", {}).get("name"):
                                        tool_calls_buffer[idx]["function"]["name"] = tc["function"]["name"]
                                    if tc.get("function", {}).get("arguments"):
                                        tool_calls_buffer[idx]["function"]["arguments"] += tc["function"]["arguments"]

                        except json.JSONDecodeError:
                            continue

            # 推完完整输出
            await self._push_event(event_queue, "agent_output", {
                "agent": agent_id,
                "type": "complete",
                "content": full_content,
            })

            # 处理 tool calls
            if not tool_calls_buffer:
                break  # 无工具调用，Agent 已完成

            # 执行工具调用
            assistant_msg = {"role": "assistant", "content": full_content or None,
                             "tool_calls": tool_calls_buffer}
            current_messages.append(assistant_msg)

            for tc in tool_calls_buffer:
                if tc is None:
                    continue
                tool_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                await self._push_event(event_queue, "tool_call", {
                    "agent": agent_id,
                    "tool": tool_name,
                    "args": args,
                })

                tool_result = await agent.execute_tool(tool_name, args)
                tool_call_count += 1

                await self._push_event(event_queue, "tool_result", {
                    "agent": agent_id,
                    "tool": tool_name,
                    "result_summary": tool_result[:200] + ("..." if len(tool_result) > 200 else ""),
                })

                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })

        return full_content

    # ── 第7轮：并行策展 ───────────────────────────────────

    async def _execute_parallel_curation(self, event_queue: asyncio.Queue,
                                         round_num: int):
        """三个 Agent 并行执行策展"""
        tasks = []
        for agent_id in ["A1", "A2", "A3"]:
            tasks.append(self._execute_curation_agent(
                event_queue, round_num, agent_id))
        await asyncio.gather(*tasks)

    async def _execute_curation_agent(self, event_queue: asyncio.Queue,
                                      round_num: int, agent_id: str):
        """单个 Agent 的策展执行"""
        agent = self.agents[agent_id]
        system_prompt = agent.build_system_prompt(
            stage="curation", topic=self.topic)

        input_context = self._build_input_context(agent_id, round_num, "curation")
        active_facts = self.data_exchange.get_active_facts()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"【可用事实库（已排除驳回项）】\n{json.dumps(active_facts, ensure_ascii=False, indent=2)}"},
            {"role": "user", "content": f"【历史辩论上下文】\n{input_context}\n\n请决定哪些材料应进入最终报告。"},
        ]

        raw_output = await self._call_deepseek_streaming(
            agent, messages, event_queue, agent_id,
            max_tool_calls=2)

        # 策展不需要额外 tool calls，直接保存
        self.data_exchange.snapshot_round(
            round_num=round_num, agent_id=agent_id,
            system_prompt=system_prompt,
            input_context=input_context,
            tool_calls=[], raw_output=raw_output,
            fact_changes=[])

    # ── 第8轮：监督整合 ───────────────────────────────────

    async def _execute_supervisor(self, event_queue: asyncio.Queue,
                                  round_num: int):
        """监督 Agent 整合全量辩论记录"""
        agent = self.agents["SUPERVISOR"]
        system_prompt = agent.build_system_prompt(stage="supervise", topic=self.topic)

        # 汇总所有 Agent 的策展输出
        all_curations = {}
        for agent_id in ["A1", "A2", "A3"]:
            # 从 archive 读取第7轮的输出
            curation_path = (self._session_dir / "archive" /
                             f"round_{7:02d}" / f"{agent_id.lower()}_raw_output.txt")
            if curation_path.exists():
                all_curations[agent_id] = curation_path.read_text(encoding="utf-8")[:3000]

        active_facts = self.data_exchange.get_active_facts()
        defend_points = {}
        for agent_id in ["A1", "A2", "A3"]:
            dp = self.data_exchange.load_defend_point(agent_id)
            if dp:
                defend_points[agent_id] = dp

        input_context = (
            f"【三方策展结果】\n"
            f"A1 策展: {all_curations.get('A1', '无')[:1500]}\n\n"
            f"A2 策展: {all_curations.get('A2', '无')[:1500]}\n\n"
            f"A3 策展: {all_curations.get('A3', '无')[:1500]}\n\n"
            f"【经用户确认的事实库】\n{json.dumps(active_facts, ensure_ascii=False, indent=2)}\n\n"
            f"【三方防守论点】\n{json.dumps(defend_points, ensure_ascii=False, indent=2)}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_context},
        ]

        raw_output = await self._call_deepseek_streaming(
            agent, messages, event_queue, "SUPERVISOR",
            max_tool_calls=2, max_tokens=6000)

        # 保存监督报告（PDF 路径稍后在 run() 中更新）
        self.data_exchange.save_supervisor_report({
            "report": raw_output,
            "generated_at": datetime.now().isoformat(),
            "session_dir": str(self._session_dir),
        })

        self.data_exchange.snapshot_round(
            round_num=round_num, agent_id="SUPERVISOR",
            system_prompt=system_prompt,
            input_context=input_context,
            tool_calls=[], raw_output=raw_output,
            fact_changes=[])

    # ── 事实确认暂停 ──────────────────────────────────────

    async def _pause_for_fact_confirmation(self, event_queue: asyncio.Queue):
        """暂停辩论，等待用户确认待定事实"""
        pending_facts = self.data_exchange.get_pending_facts()
        if not pending_facts:
            return

        self.is_paused = True
        await self._push_event(event_queue, "waiting_for_facts", {
            "pending_count": len(pending_facts),
            "timeout_seconds": 300,
        })

        # 推送待确认事实
        await self._push_event(event_queue, "new_facts", {
            "facts": [
                {
                    "id": f["id"],
                    "content": f["content"],
                    "source": f["source"],
                    "evidence": f.get("evidence", ""),
                    "table_fields": f.get("table_fields", {}),
                    "needs_confirmation": True,
                }
                for f in pending_facts
            ],
        })

        # 等待——由 API 端点 resume 时设置
        try:
            await asyncio.wait_for(
                self._wait_for_resume(), timeout=300)
        except asyncio.TimeoutError:
            # 超时：将所有 pending 标记为 disputed
            for f in pending_facts:
                self.data_exchange.confirm_fact(f["id"], action="dispute")
            await self._push_event(event_queue, "facts_timeout", {
                "message": '事实确认超时，所有待定事实已自动标记为"争议"',
            })
        finally:
            self.is_paused = False

    async def _wait_for_resume(self):
        """等待前端通过 API 恢复辩论"""
        while self.is_paused:
            await asyncio.sleep(0.5)

    def resume_debate(self):
        """由 API 调用，恢复暂停的辩论"""
        self.is_paused = False

    def confirm_facts_batch(self, actions: list):
        """
        批量确认事实。
        actions: [{"fact_id": "f1", "action": "confirm", "modified_content": null}, ...]
        """
        for action in actions:
            self.data_exchange.confirm_fact(
                fact_id=action["fact_id"],
                action=action.get("action", "confirm"),
                modified_content=action.get("modified_content"),
            )

    # ── 上下文构建 ─────────────────────────────────────────

    def _build_input_context(self, agent_id: str, round_num: int,
                             stage: str) -> str:
        """构建当前 Agent 的输入上下文——包含所有相关方的完整辩论记录"""
        parts = []

        # 1. 加载当前 debate_point.json（上一轮的输出）
        dp = self.data_exchange.load_debate_point()
        if dp and dp.get("agent") != agent_id:  # 不给自己看自己的
            parts.append(f"【上一轮 {dp.get('agent')} 的辩论输出】\n{json.dumps(dp, ensure_ascii=False, indent=2)[:3000]}")

        # 2. 从 archive 读取之前各轮的对方完整输出
        for prev_round in range(1, round_num):
            archive_round_dir = self._session_dir / "archive" / f"round_{prev_round:02d}"
            if not archive_round_dir.exists():
                continue
            for aid in ["A1", "A2", "A3"]:
                if aid == agent_id:
                    continue  # 不给自己看自己之前的输出
                raw_file = archive_round_dir / f"{aid.lower()}_raw_output.txt"
                if raw_file.exists():
                    text = raw_file.read_text(encoding="utf-8")[:2500]
                    parts.append(f"【第{prev_round}轮 {aid} 的完整输出】\n{text}")

        # 3. 加载所有 defend_point
        defend_context = {}
        for aid in ["A1", "A2", "A3"]:
            if aid == agent_id:
                continue
            df = self.data_exchange.load_defend_point(aid)
            if df:
                defend_context[aid] = {
                    "core_thesis": df.get("core_thesis", ""),
                    "responses": df.get("responses_to_challenges", [])[:3],
                }
        if defend_context:
            parts.append(f"【对方防守论点】\n{json.dumps(defend_context, ensure_ascii=False, indent=2)[:2000]}")

        # 4. 加载活跃事实
        active_facts = self.data_exchange.get_active_facts()
        if active_facts:
            # 只给对方生成的事实（不给自己生成的）
            other_facts = [f for f in active_facts if f.get("source") != agent_id]
            if other_facts:
                parts.append(f"【对方提交的事实（{len(other_facts)}条）】\n{json.dumps(other_facts, ensure_ascii=False, indent=2)[:2000]}")

        return "\n\n---\n\n".join(parts)

    def _parse_arguments(self, text: str, agent_id: str) -> list:
        """从 Agent 输出中解析结构化论点"""
        # 简化版：按段落分割，每段作为一个论点
        arguments = []
        for i, para in enumerate(text.split("\n\n")):
            para = para.strip()
            if para and len(para) > 20:
                arguments.append({
                    "id": f"arg_{agent_id}_{i+1}",
                    "type": "claim",
                    "claim": para[:200],
                    "reasoning": para[:500],
                })
        return arguments[:10]

    def _extract_and_record_facts(self, text: str, agent_id: str) -> list:
        """
        从 Agent 输出中提取事实并写入 fact_check.json。
        提取的事实必须是自包含的陈述句，包含具体信息（谁、什么事、什么时间/数据）。
        """
        import re
        facts = []
        seen_contents = set()  # 去重

        def _should_keep(content: str) -> bool:
            """质量过滤：太短/太泛的句子不收录"""
            if len(content) < 40:
                return False
            # 排除纯标题（如"设计分析"、"总结"等不足10字的概括词）
            if len(content) < 15 and not any(c.isdigit() for c in content):
                return False
            # 排除以明显标题词开头的片段
            title_prefixes = ['设计分析', '摘要', '总结', '引言', '概述', '结论', '建议', '对策']
            for tp in title_prefixes:
                if content.strip().startswith(tp) and len(content) < 30:
                    return False
            return True

        def _add_fact(content: str, evidence_label: str):
            content = content.strip()
            if not _should_keep(content):
                return
            # 去重
            key = content[:80]
            if key in seen_contents:
                return
            seen_contents.add(key)
            fact_id = self.data_exchange.add_fact(
                content=content[:400],
                source_agent=agent_id,
                evidence=f"{agent_id} 第{self.current_round}轮 — {evidence_label}",
            )
            facts.append({"fact_id": fact_id, "content": content[:400]})

        # 模式1: 标记格式 [证据: xxx] / [反证: xxx] / [来源: xxx]
        for pattern, label in [
            (r'\[证据[：:]\s*(.+?)\]', '显式证据'),
            (r'\[反证[：:]\s*(.+?)\]', '反证'),
            (r'\[来源[：:]\s*(.+?)\]', '来源引用'),
            (r'\[新证据[：:]\s*(.+?)\]', '新证据'),
        ]:
            for match in re.finditer(pattern, text):
                _add_fact(match.group(1).strip(), label)
                if len(facts) >= 8:
                    return facts

        # 模式2: 从 ## 搜索摘要 提取段落
        search_section = re.search(
            r'搜索摘要\s*\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
        if search_section:
            # 合并连续短行为完整句子
            lines = [l.strip().lstrip('- ').strip() for l in search_section.group(1).split('\n')]
            merged = []
            buf = ""
            for line in lines:
                if not line or line.startswith('#'):
                    continue
                if len(line) < 40 and buf:
                    buf += "；" + line
                elif len(line) < 40:
                    buf = line
                else:
                    if buf:
                        merged.append(buf)
                    buf = line
            if buf:
                merged.append(buf)
            for m in merged:
                _add_fact(m, "搜索摘要")
                if len(facts) >= 8:
                    return facts

        # 模式3: 从论点章节提取完整句子（不分割，按自然段落）
        for section_name in ['核心论点', '驳论', '我方立论', '最终立论', '整体判断']:
            section = re.search(
                rf'{section_name}\s*\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
            if section:
                # 按自然段落分割（空行分隔）
                paragraphs = re.split(r'\n\s*\n', section.group(1))
                for para in paragraphs:
                    para = para.strip()
                    # 跳过列表项符号
                    para = re.sub(r'^[-*]\s+', '', para)
                    para = re.sub(r'^\d+\.\s+', '', para)
                    if 40 < len(para) < 500:
                        _add_fact(para, section_name)
                        if len(facts) >= 8:
                            return facts
                if facts:
                    return facts

        return facts

    def _build_final_report(self) -> dict:
        """整合辩论结果生成最终报告"""
        report = self.data_exchange.load_supervisor_report()
        active_facts = self.data_exchange.get_active_facts()

        return {
            "title": f"舆情辩论报告：{self.topic}",
            "generated_at": datetime.now().isoformat(),
            "topic": self.topic,
            "total_facts": len(active_facts),
            "confirmed_facts": sum(1 for f in active_facts if f["status"] == "confirmed"),
            "disputed_facts": sum(1 for f in active_facts if f["status"] == "disputed"),
            "content": report.get("report", ""),
            "session_dir": str(self._session_dir),
        }

    async def _push_event(self, queue: asyncio.Queue, event: str, data: dict):
        """推送 SSE 事件到队列"""
        await queue.put({"event": event, "data": data})

    def generate_pdf(self) -> str:
        """
        生成辩论报告的 PDF，样式与 paper/ 目录下的 PDF 一致。
        返回 PDF 文件路径。
        """
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table
        )
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib import colors
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import re as _re

        # ── 字体设置（与 pdf_report.py 一致） ──
        FONT_CN = "Helvetica"
        try:
            font_paths = [
                "C:/Windows/Fonts/simsun.ttc",
                "C:/Windows/Fonts/SimSun.ttf",
            ]
            for fp in font_paths:
                if __import__('os').path.exists(fp):
                    pdfmetrics.registerFont(TTFont("SimSun", fp))
                    FONT_CN = "SimSun"
                    break
        except:
            pass

        black = colors.HexColor("#000000")
        MARGIN_L = 20 * mm; MARGIN_R = 18 * mm
        MARGIN_T = 26 * mm; MARGIN_B = 16 * mm

        TITLE_STYLE = ParagraphStyle("DB_Title", fontName=FONT_CN, fontSize=22,
                                     leading=30, textColor=black, alignment=TA_CENTER)
        CHAP_STYLE = ParagraphStyle("DB_Chap", fontName=FONT_CN, fontSize=16,
                                    leading=24, textColor=black, alignment=TA_CENTER)
        SEC_STYLE = ParagraphStyle("DB_Sec", fontName=FONT_CN, fontSize=14,
                                   leading=20, textColor=black)
        BODY_STYLE = ParagraphStyle("DB_Body", fontName=FONT_CN, fontSize=12,
                                    leading=20, textColor=black)
        CENTER_STYLE = ParagraphStyle("DB_Center", fontName=FONT_CN, fontSize=12,
                                      leading=20, textColor=black, alignment=TA_CENTER)

        # ── 构建 Story ──
        story = []
        story.append(Spacer(1, 40))
        story.append(Paragraph("<b>Miho-spot 智能体辩论报告</b>", TITLE_STYLE))
        story.append(Spacer(1, 16))
        story.append(Paragraph(f"《{self.topic}》", ParagraphStyle(
            "DB_Topic", fontName=FONT_CN, fontSize=18, leading=26,
            textColor=black, alignment=TA_CENTER)))
        story.append(Spacer(1, 24))
        story.append(Paragraph(
            f"生成日期：{datetime.now().strftime('%Y年%m月%d日')}",
            ParagraphStyle("DB_Date", fontName=FONT_CN, fontSize=12,
                           leading=20, textColor=black, alignment=TA_CENTER)))
        story.append(Spacer(1, 6))
        story.append(Paragraph("分析模式：三智能体瑞士轮辩论 + AI 监督整合",
                               CENTER_STYLE))
        story.append(PageBreak())

        # ── 摘要 ──
        active_facts = self.data_exchange.get_active_facts() if self.data_exchange else []
        confirmed = sum(1 for f in active_facts if f.get("status") == "confirmed")
        disputed = sum(1 for f in active_facts if f.get("status") == "disputed")

        story.append(Paragraph("摘  要", CHAP_STYLE))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"本报告由三个专业智能体（A1 私有数据专家、A2 官媒分析专家、"
            f"A3 公域扫描专家）通过 8 轮瑞士轮辩论机制生成，由监督智能体 "
            f"整合三方论点。辩论共涉及 {len(active_facts)} 条事实，其中确认 "
            f"{confirmed} 条，争议 {disputed} 条。", BODY_STYLE))
        story.append(PageBreak())

        # ── Supervisor 报告正文 ──
        report = self.data_exchange.load_supervisor_report() if self.data_exchange else {}
        report_text = report.get("report", "")

        content_added = False  # 追踪是否有有效内容被添加

        if not report_text:
            story.append(Paragraph("报告内容", CHAP_STYLE))
            story.append(Paragraph("（报告内容未能生成，请查看辩论原始记录）", BODY_STYLE))
            content_added = True
        else:
            # 尝试按 ## 标题分章节
            sections = _re.split(r'\n(##\s+.+)', report_text)

            if any('##' in s for s in sections) and len(sections) > 1:
                # Markdown 解析路径
                if not sections[0].startswith("##"):
                    intro = sections.pop(0).strip()
                    if intro:
                        story.append(Paragraph("报告正文", CHAP_STYLE))
                        story.append(Spacer(1, 6))
                        for line in intro.split("\n"):
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith("# "):
                                story.append(Paragraph(line[2:].lstrip("#").strip(), CHAP_STYLE))
                                content_added = True
                            else:
                                clean = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
                                clean = _re.sub(r'[#*]{1,3}\s*', '', clean)
                                story.append(Paragraph(clean, BODY_STYLE))
                                content_added = True

                for i in range(0, len(sections), 2):
                    heading = sections[i].strip().lstrip("#").strip() if i < len(sections) else ""
                    body = sections[i+1].strip() if i+1 < len(sections) else ""
                    if heading:
                        story.append(Paragraph(heading, SEC_STYLE))
                        story.append(Spacer(1, 4))
                        content_added = True
                    for line in body.split("\n"):
                        line = line.strip()
                        if not line:
                            story.append(Spacer(1, 6))
                            continue
                        if line.startswith("### "):
                            story.append(Paragraph(f"<b>{line[4:]}</b>", BODY_STYLE))
                        elif line.startswith("- ") or line.startswith("* "):
                            clean = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line[2:])
                            story.append(Paragraph(f"  • {clean}", BODY_STYLE))
                        else:
                            clean = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
                            story.append(Paragraph(clean, BODY_STYLE))
                        content_added = True

            if not content_added:
                # Fallback: markdown 解析失败或无结构化内容 → 渲染原始文本
                story.append(Paragraph("⚠ 报告解析说明", CHAP_STYLE))
                story.append(Spacer(1, 4))
                story.append(Paragraph(
                    "DeepSeek 输出的报告文本未包含标准 Markdown 章节标记（##），"
                    "以下为原始输出内容，已按段落自动排版。", BODY_STYLE))
                story.append(Spacer(1, 12))

                story.append(Paragraph("报告正文", CHAP_STYLE))
                story.append(Spacer(1, 6))
                # 按空行分段落渲染原始文本
                raw_paragraphs = _re.split(r'\n\s*\n', report_text)
                for para in raw_paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    # 处理内联 markdown
                    clean = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', para)
                    clean = _re.sub(r'^#+\s+', '', clean)
                    story.append(Paragraph(clean, BODY_STYLE))
                    story.append(Spacer(1, 6))
                    content_added = True

                if not content_added:
                    story.append(Paragraph("（原始内容为空或全部由非文本标记组成）", BODY_STYLE))

        # ── 事实清单 ──
        story.append(PageBreak())
        story.append(Paragraph("附录：事实清单", CHAP_STYLE))
        story.append(Spacer(1, 6))
        for f in active_facts:
            status_label = {"confirmed": "✓已确认", "disputed": "≈争议", "rejected": "✗已驳回"}.get(
                f.get("status", ""), "?待定")
            story.append(Paragraph(
                f"[{status_label}] (来源:{f.get('source','')}) {f.get('content','')[:200]}",
                BODY_STYLE))

        # ── 生成 PDF ──
        paper_dir = self._base_dir / "paper"
        paper_dir.mkdir(parents=True, exist_ok=True)
        safe_topic = _re.sub(r'[\\/:*?"<>|\r\n]+', '_', self.topic)[:40]
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_path = paper_dir / f"辩论报告_{safe_topic}-{ts}.pdf"

        buf = BytesIO()
        doc = SimpleDocTemplate(
            str(pdf_path), pagesize=A4,
            leftMargin=MARGIN_L, rightMargin=MARGIN_R,
            topMargin=MARGIN_T, bottomMargin=MARGIN_B,
            title=f"辩论报告-{self.topic[:30]}", author="Miho-spot Agent Debate")
        doc.build(story)

        print(f"[PDF] 辩论报告已生成: {pdf_path}", flush=True)
        return str(pdf_path)
