"""
三轨搜索引擎 + Agent 专用搜索工具

主力：DuckDuckGo (ddgs) — 免费无限，纯搜索不消耗 LLM Token
备轨1：Tavily        — 月免 1000 次，结构化结果
备轨2：Serper.dev    — 2500 次免费，Google 品质
A1：私有数据         — 本地 paper/ 目录 PDF 检索（不走搜索引擎）
"""

import os
from pathlib import Path
from typing import Optional

import httpx


class QuotaExhaustedError(Exception):
    pass


class SearchEngine:
    """三轨制搜索引擎。自动降级：DDGS → Tavily → Serper。"""

    def __init__(self, volcano_key: str = None, volcano_bot_id: str = None,
                 tavily_key: str = None, serper_key: str = None):
        self.tavily_key = tavily_key
        self.serper_key = serper_key or os.environ.get("SERPER_API_KEY", "")

        self._ddgs_available = True
        self._tavily_available = bool(tavily_key)
        self._serper_available = bool(self.serper_key)

        self._ddgs_calls = 0
        self._tavily_calls = 0
        self._serper_calls = 0

    @property
    def current_track(self) -> str:
        if self._ddgs_available:
            return "ddgs"
        if self._tavily_available:
            return "tavily"
        if self._serper_available:
            return "serper"
        return "none"

    @property
    def stats(self) -> dict:
        return {
            "current_track": self.current_track,
            "ddgs_calls": self._ddgs_calls,
            "tavily_calls": self._tavily_calls,
            "serper_calls": self._serper_calls,
        }

    async def search(self, query: str,
                     include_domains: list = None,
                     exclude_domains: list = None) -> dict:
        """统一搜索入口，三轨自动降级"""
        # Track 1: DuckDuckGo
        if self._ddgs_available:
            try:
                result = await self._search_ddgs(query)
                self._ddgs_calls += 1
                return {"results": result, "track": "ddgs", "raw": None}
            except Exception:
                self._ddgs_available = False

        # Track 2: Tavily
        if self._tavily_available:
            try:
                result = await self._search_tavily(query, include_domains, exclude_domains)
                self._tavily_calls += 1
                return {"results": result, "track": "tavily", "raw": None}
            except Exception:
                self._tavily_available = False

        # Track 3: Serper.dev
        if self._serper_available:
            try:
                result = await self._search_serper(query)
                self._serper_calls += 1
                return {"results": result, "track": "serper", "raw": None}
            except Exception:
                self._serper_available = False

        return {"results": [], "track": "none", "raw": None}

    # ── DDGS ────────────────────────────────────────────

    async def _search_ddgs(self, query: str, max_results: int = 5) -> list:
        """DuckDuckGo 即时搜索（纯搜索，零 Token）"""
        import asyncio as _asyncio
        from ddgs import DDGS

        def _sync():
            results = []
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(query, max_results=max_results):
                        results.append({
                            "title": r.get("title", ""),
                            "content": r.get("body", ""),
                            "url": r.get("href", ""),
                            "source": "ddgs",
                        })
            except Exception:
                raise QuotaExhaustedError()
            return results

        loop = _asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync)

    # ── Tavily ──────────────────────────────────────────

    async def _search_tavily(self, query: str,
                             include_domains: list = None,
                             exclude_domains: list = None) -> list:
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
                json=body, timeout=30)
            data = resp.json()

        results = []
        for r in data.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "content": r.get("content", ""),
                "url": r.get("url", ""),
                "source": "tavily",
            })
        return results

    # ── Serper.dev ──────────────────────────────────────

    async def _search_serper(self, query: str) -> list:
        """Serper.dev Google 搜索（2500 次免费）"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": self.serper_key,
                    "Content-Type": "application/json",
                },
                json={"q": query, "num": 5, "gl": "cn", "hl": "zh-cn"},
                timeout=20,
            )
            data = resp.json()

        results = []
        for r in data.get("organic", []):
            results.append({
                "title": r.get("title", ""),
                "content": r.get("snippet", ""),
                "url": r.get("link", ""),
                "source": "serper",
            })
        return results


# ======================================================================
#  Agent 专用搜索函数
# ======================================================================

async def search_private_reports(keywords: str) -> dict:
    """A1 专用：扫描 backend/paper/*.pdf，关键词匹配检索"""
    paper_dir = Path(__file__).resolve().parent.parent.parent / "paper"
    result_text = []
    files_found = []

    if paper_dir.exists():
        for pdf_file in sorted(paper_dir.glob("*.pdf")):
            filename = pdf_file.stem
            kw_list = [k.strip() for k in keywords.replace("，", ",").split(",") if k.strip()]
            matched = any(kw.lower() in filename.lower() for kw in kw_list)

            if matched or not kw_list:
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
