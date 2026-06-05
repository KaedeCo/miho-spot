"""
JSON 数据交换与持久化管理

管理 debate_session 目录下的所有 JSON 文件：
- fact_check.json      — 共享事实库（后端维护）
- debate_point.json    — 当前轮次结构化上下文（Agent 间传递）
- defend_point.json    — 各 Agent 防守论点（4-6 轮可编辑）
- supervisor_report.json — 最终报告

同时负责每轮辩论完成后的全量快照归档。
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional


class DataExchange:
    """管理单个辩论会话的所有 JSON 文件读写和快照归档"""

    def __init__(self, session_dir: Path):
        self.dir = Path(session_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir = self.dir / "archive"
        self.archive_dir.mkdir(exist_ok=True)

    # ── fact_check.json ──────────────────────────────────

    @property
    def fact_check_path(self) -> Path:
        return self.dir / "fact_check.json"

    def load_fact_check(self) -> dict:
        if self.fact_check_path.exists():
            return json.loads(self.fact_check_path.read_text(encoding="utf-8"))
        return {"facts": [], "confirmed_count": 0, "disputed_count": 0,
                "rejected_count": 0, "pending_count": 0}

    def save_fact_check(self, data: dict):
        counts = {"confirmed": 0, "disputed": 0, "rejected": 0, "pending": 0}
        for f in data.get("facts", []):
            s = f.get("status", "pending")
            counts[s] = counts.get(s, 0) + 1
        data["confirmed_count"] = counts.get("confirmed", 0)
        data["disputed_count"] = counts.get("disputed", 0)
        data["rejected_count"] = counts.get("rejected", 0)
        data["pending_count"] = counts.get("pending", 0)
        self.fact_check_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_fact(self, content: str, source_agent: str,
                 evidence: str = "", table_fields: dict = None) -> str:
        """添加新事实，返回事实 ID。自动生成 table_fields。"""
        import uuid
        data = self.load_fact_check()
        fact_id = f"f{uuid.uuid4().hex[:12]}"
        fact = {
            "id": fact_id,
            "content": content,
            "original_content": content,
            "modified_by_user": None,
            "source": source_agent,
            "status": "pending",
            "confidence": 1.0,
            "confirmed_by_user": False,
            "user_action": None,
            "evidence": evidence,
            "table_fields": table_fields or self._extract_table_fields(content),
            "created_at": datetime.now().isoformat(),
            "confirmed_at": None,
            "disputes": [],
        }
        data["facts"].append(fact)
        self.save_fact_check(data)
        return fact_id

    def _extract_table_fields(self, content: str) -> dict:
        """从自然语言事实中提取简单的 key-value 表格字段"""
        return {"raw_text": content}

    def confirm_fact(self, fact_id: str, action: str = "confirm",
                     modified_content: str = None):
        """用户对事实执行四种操作：confirm | dispute | reject | modify"""
        data = self.load_fact_check()
        for f in data["facts"]:
            if f["id"] == fact_id:
                f["user_action"] = action
                f["confirmed_by_user"] = True
                f["confirmed_at"] = datetime.now().isoformat()
                if action == "confirm":
                    f["status"] = "confirmed"
                    f["confidence"] = 1.0
                elif action == "dispute":
                    f["status"] = "disputed"
                    f["confidence"] = 0.5
                elif action == "reject":
                    f["status"] = "rejected"
                    f["confidence"] = 0.0
                elif action == "modify" and modified_content is not None:
                    f["original_content"] = f["content"]
                    f["content"] = modified_content
                    f["modified_by_user"] = True
                    f["status"] = "confirmed"
                    f["confidence"] = 1.0
                break
        self.save_fact_check(data)

    def get_pending_facts(self) -> list:
        """获取需要用户确认的事实列表"""
        return [f for f in self.load_fact_check().get("facts", [])
                if f.get("status") == "pending" and not f.get("confirmed_by_user")]

    def get_active_facts(self) -> list:
        """获取可被 Agent 引用的事实（排除 rejected）"""
        return [f for f in self.load_fact_check().get("facts", [])
                if f.get("status") != "rejected"]

    def add_dispute(self, fact_id: str, agent: str, reason: str):
        """Agent 对事实提出质疑"""
        data = self.load_fact_check()
        for f in data["facts"]:
            if f["id"] == fact_id:
                f.setdefault("disputes", []).append({
                    "agent": agent,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat(),
                })
                break
        self.save_fact_check(data)

    # ── debate_point.json ────────────────────────────────

    @property
    def debate_point_path(self) -> Path:
        return self.dir / "debate_point.json"

    def load_debate_point(self) -> dict:
        if self.debate_point_path.exists():
            return json.loads(self.debate_point_path.read_text(encoding="utf-8"))
        return {}

    def save_debate_point(self, round_num: int, agent_id: str,
                          stage: str, targets: list, arguments: list,
                          concessions: list = None,
                          key_insights: list = None):
        """写入当前轮次的辩论输出"""
        data = {
            "round": round_num,
            "agent": agent_id,
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "targets": targets,
            "arguments": arguments,
            "concessions": concessions or [],
            "key_insights": key_insights or [],
        }
        self.debate_point_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── defend_point.json ────────────────────────────────

    def _defend_point_path(self, agent_id: str) -> Path:
        return self.dir / f"{agent_id.lower()}_defend_point.json"

    def load_defend_point(self, agent_id: str) -> dict:
        p = self._defend_point_path(agent_id)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {}

    def save_defend_point(self, agent_id: str, data: dict):
        data["agent"] = agent_id
        data["version"] = data.get("version", 0) + 1
        data["last_modified_round"] = data.get("last_modified_round", 0)
        self._defend_point_path(agent_id).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 快照归档 ─────────────────────────────────────────

    def snapshot_round(self, round_num: int, agent_id: str,
                       system_prompt: str, input_context: str,
                       tool_calls: list, raw_output: str,
                       fact_changes: list):
        """每轮完成后自动快照——保存 Agent 完整上下文到 archive/"""
        snap_dir = self.archive_dir / f"round_{round_num:02d}"
        snap_dir.mkdir(exist_ok=True)

        files = {
            f"{agent_id.lower()}_system_prompt.txt": system_prompt,
            f"{agent_id.lower()}_input_context.json": json.dumps(
                input_context, ensure_ascii=False, indent=2),
            f"{agent_id.lower()}_tool_calls.json": json.dumps(
                tool_calls, ensure_ascii=False, indent=2),
            f"{agent_id.lower()}_raw_output.txt": raw_output,
            "fact_changes.json": json.dumps(
                fact_changes, ensure_ascii=False, indent=2),
        }
        for filename, content in files.items():
            (snap_dir / filename).write_text(content, encoding="utf-8")

        # 事实库快照
        fact_snapshot = self.load_fact_check()
        (snap_dir / "fact_check_snapshot.json").write_text(
            json.dumps(fact_snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8")

        # 轮次摘要
        summary = {
            "round": round_num,
            "agent": agent_id,
            "timestamp": datetime.now().isoformat(),
            "tool_call_count": len(tool_calls),
            "fact_changes_count": len(fact_changes),
        }
        (snap_dir / "round_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8")

    def save_full_session(self):
        """用户手动保存——全量打包当前状态"""
        # 复制当前所有实时文件到 archive/full_save/
        save_dir = self.archive_dir / f"full_save_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        save_dir.mkdir(exist_ok=True)
        for f in self.dir.glob("*.json"):
            shutil.copy2(f, save_dir / f.name)
        return str(save_dir)

    # ── 监督报告 ─────────────────────────────────────────

    @property
    def report_path(self) -> Path:
        return self.dir / "supervisor_report.json"

    def save_supervisor_report(self, report: dict):
        self.report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_supervisor_report(self) -> dict:
        if self.report_path.exists():
            return json.loads(self.report_path.read_text(encoding="utf-8"))
        return {}
