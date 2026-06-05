"""
双轨制搜索引擎 + 各 Agent 专用搜索工具

主轨：火山方舟 Bot 插件（月免 2 万次）
备轨：Tavily Search API（月免 1000 次）
A1：私有数据 —— 本地 paper/ 目录 PDF 检索（不走搜索引擎）
"""

import asyncio
import httpx
import json
from pathlib import Path
from typing import Optional


class QuotaExhaustedError(Exception):
    """火山方舟月免配额耗尽"""
    pass


class SearchEngine:
    """
    双轨制搜索引擎。优先使用火山方舟 Bot，配额耗尽自动切 Tavily。
    """

    def __init__(self, volcano_key: str = None, volcano_bot_id: str = None,
                 tavily_key: str = None):
        self.volcano_key = volcano_key
        self.volcano_bot_id = volcano_bot_id
        self.tavily_key = tavily_key
        self.volcano_available = bool(volcano_key and volcano_bot_id)
        self.tavily_available = bool(tavily_key)
        self._volcano_call_count = 0
        self._tavily_call_count = 0

    @property
    def current_track(self) -> str:
        return "volcano" if self.volcano_available else "tavily"

    @property
    def stats(self) -> dict:
        return {
            "current_track": self.current_track,
            "volcano_calls": self._volcano_call_count,
            "tavily_calls": self._tavily_call_count,
        }

    async def search(self, query: str,
                     include_domains: list = None,
                     exclude_domains: list = None) -> dict:
        """
        统一搜索入口，自动选择可用轨道。
        返回 {"results": [...], "track": "volcano"|"tavily", "raw": ...}
        """
        if self.volcano_available:
            try:
                result = await self._search_volcano(query)
                self._volcano_call_count += 1
                return {"results": result, "track": "volcano", "raw": None}
            except QuotaExhaustedError:
                self.volcano_available = False

        if self.tavily_available:
            result = await self._search_tavily(
                query, include_domains, exclude_domains)
            self._tavily_call_count += 1
            return {"results": result, "track": "tavily", "raw": None}

        return {"results": [], "track": "none", "raw": None}

    async def _search_volcano(self, query: str) -> list:
        """火山方舟端点 + web_search 工具搜索"""
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
            resp = await client.post(
                "https://ark.cn-beijing.volces.com/api/v3/responses",
                headers={
                    "Authorization": f"Bearer {self.volcano_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.volcano_bot_id,   # 端点 ID，如 ep-20260605220808-nt2nk
                    "stream": False,
                    "tools": [{"type": "web_search", "max_keyword": 3}],
                    "input": [{
                        "role": "user",
                        "content": [{"type": "input_text", "text": query}],
                    }],
                },
                timeout=60,
            )
            if resp.status_code == 429:
                raise QuotaExhaustedError()
            data = resp.json()
            return self._parse_volcano_results(data)

    async def _search_tavily(self, query: str,
                             include_domains: list = None,
                             exclude_domains: list = None) -> list:
        """Tavily Search API"""
        body = {
            "query": query,
            "api_key": self.tavily_key,
            "max_results": 5,
            "search_depth": "basic",
        }
        if include_domains:
            body["include_domains"] = include_domains
        if exclude_domains:
            body["exclude_domains"] = exclude_domains

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json=body,
                timeout=30,
            )
            data = resp.json()
            return self._parse_tavily_results(data)

    @staticmethod
    def _parse_volcano_results(data: dict) -> list:
        """解析火山方舟 Responses API 返回（含 web_search 结果）"""
        results = []
        # Extract assistant message text
        output = data.get("output", [])
        for item in output:
            if item.get("type") == "message" and item.get("role") == "assistant":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        results.append({
                            "title": "火山方舟搜索",
                            "content": c.get("text", "")[:3000],
                            "url": "",
                            "source": "volcano",
                        })
        if not results:
            results.append({
                "title": "无结果",
                "content": str(data)[:500],
                "url": "",
                "source": "volcano",
            })
        return results

    @staticmethod
    def _parse_tavily_results(data: dict) -> list:
        """解析 Tavily 返回"""
        results = []
        for r in data.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "content": r.get("content", ""),
                "url": r.get("url", ""),
                "source": "tavily",
            })
        return results


# ======================================================================
#  Agent 专用搜索函数
# ======================================================================

async def search_private_reports(keywords: str) -> dict:
    """
    A1 专用：扫描 backend/paper/*.pdf，关键词匹配检索。
    不经过搜索引擎，纯本地操作。
    """
    paper_dir = Path(__file__).resolve().parent.parent.parent / "paper"
    result_text = []
    files_found = []

    if paper_dir.exists():
        for pdf_file in sorted(paper_dir.glob("*.pdf")):
            filename = pdf_file.stem
            # 简单关键词匹配（文件名 + 大小信息）
            kw_list = [k.strip() for k in keywords.replace("，", ",").split(",") if k.strip()]
            matched = any(kw.lower() in filename.lower() for kw in kw_list)

            if matched or not kw_list:  # 无关键词则返回所有
                size_kb = pdf_file.stat().st_size / 1024
                result_text.append(
                    f"标题：{filename}\n"
                    f"大小：{size_kb:.0f}KB\n"
                    f"路径：{pdf_file}\n")
                files_found.append({
                    "title": filename,
                    "path": str(pdf_file),
                    "size_kb": round(size_kb, 1),
                })

    if not result_text:
        result_text.append("未在 paper/ 目录中找到匹配的历史报告。")

    return {
        "results_text": "\n---\n".join(result_text),
        "files": files_found,
        "track": "local",
    }


async def search_official_media(engine: SearchEngine, query: str) -> dict:
    """A2 专用：官媒 + 米游社搜索"""
    official_domains = [
        "people.com.cn", "xinhuanet.com", "cctv.com",
        "mihoyo.com", "mys.mihoyo.com", "bbs.mihoyo.com",
    ]
    return await engine.search(query, include_domains=official_domains)


async def search_public_forums(engine: SearchEngine, query: str) -> dict:
    """A3 专用：B站、知乎、贴吧、小红书等公域论坛"""
    public_domains = [
        "bilibili.com", "zhihu.com", "xiaohongshu.com",
        "tieba.baidu.com", "nga.cn", "xiaoheihe.cn",
    ]
    return await engine.search(query, include_domains=public_domains)


async def search_web(engine: SearchEngine, query: str) -> dict:
    """通用搜索（监督 Agent 使用）"""
    return await engine.search(query)
