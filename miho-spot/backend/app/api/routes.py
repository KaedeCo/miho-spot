"""
Miho-spot Backend API Routes - Hot crawl + Keyword search
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import threading
import hashlib
import json

from app.models import get_db, SessionLocal, init_db
from app.models import HotTopicModel, PostItemModel, DailyStatsModel, KeywordModel, AccountModel
from app.crawlers import get_crawler

router = APIRouter(prefix="/api")

# Centralized data directory — can be overridden for frozen EXE
_DATA_BASE_DIR: Optional[str] = None

def set_data_base_dir(path: str):
    """Override the data base directory (for frozen EXE that can't use __file__)."""
    global _DATA_BASE_DIR, TOPHUB_SEARCH_DATA_DIR, CATEGORIES_FILE, _DSSTORE_LOCK_FILE
    _DATA_BASE_DIR = path
    # Reset cached paths so they re-resolve
    TOPHUB_SEARCH_DATA_DIR = None
    CATEGORIES_FILE = None
    _DSSTORE_LOCK_FILE = None

def _get_data_base() -> Path:
    if _DATA_BASE_DIR:
        return Path(_DATA_BASE_DIR)
    return Path(__file__).resolve().parent.parent / "data"

# Separate caches for hot and search results
_hot_cache: dict = {"zhihu": [], "douyin": [], "tieba": []}
_search_cache: dict = {"zhihu": [], "douyin": [], "tieba": []}
_hot_time: Optional[datetime] = None
_search_time: Optional[datetime] = None

# User-configurable search keywords - persist in module-level
_search_keywords: Optional[List[str]] = None  # Lazy init from DB or default

# DeepSeek analyze lock file management
_DSSTORE_LOCK_FILE: Optional[Path] = None


def _get_dsstore_dir() -> Path:
    global _DSSTORE_LOCK_FILE
    if _DSSTORE_LOCK_FILE is None:
        d = _get_data_base() / "tophub_search"
        d.mkdir(parents=True, exist_ok=True)
        _DSSTORE_LOCK_FILE = d
    return _DSSTORE_LOCK_FILE


# Startup: clean stale .dsstored files from previous days
def _cleanup_stale_dsstore():
    data_dir = _get_dsstore_dir()
    if not data_dir.exists():
        return
    today = datetime.utcnow().strftime("%Y%m%d")
    for f in data_dir.glob("*.dsstored"):
        if f.stem != today:
            try:
                f.unlink()
                print(f"[DSStore] Cleaned stale lock: {f.name}")
            except Exception as e:
                print(f"[DSStore] Failed to clean {f.name}: {e}")


_cleanup_stale_dsstore()

def _get_search_keywords() -> List[str]:
    global _search_keywords
    if _search_keywords is None:
        _search_keywords = ["米哈游", "原神", "星穹铁道", "绝区零"]
    return _search_keywords


def _run_analyze(items):
    """Fast keyword matching + SnowNLP sentiment analysis.
    DeepSeek is separate - only via the 'one-click analyze' button."""
    from app.sentiment import analyze_topic_sentiment
    for item in items:
        sentiment, related_game = analyze_topic_sentiment(item["title"])
        item["sentiment"] = sentiment
        item["related_game"] = related_game
        item["is_game_related"] = sentiment != "Irrelevant"


# ==================== Hot List Crawl (Free — Accumulate) ====================

def _persist_hot_crawl(items: list):
    """Save hot crawl results to a cumulative file. Merges new items with existing."""
    data_dir = _get_search_data_dir()
    hot_file = data_dir / "hot_crawl.json"

    existing = []
    if hot_file.exists():
        try:
            with open(hot_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except:
            existing = []

    # Merge: dedup by id, keep new items
    existing_ids = {i["id"] for i in existing}
    new_count = 0
    for item in items:
        if item["id"] not in existing_ids:
            existing.append(item)
            existing_ids.add(item["id"])
            new_count += 1

    with open(hot_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"[HotCrawl] Persisted: {new_count} new, total {len(existing)} accumulated in hot_crawl.json")


def _load_hot_crawl_from_file() -> bool:
    """Load accumulated hot crawl data from file into memory cache. Returns True if successful."""
    global _hot_cache, _hot_time
    data_dir = _get_search_data_dir()
    hot_file = data_dir / "hot_crawl.json"
    if not hot_file.exists():
        return False
    try:
        with open(hot_file, "r", encoding="utf-8") as f:
            items = json.load(f)
        if items:
            # Keep stored sentiment labels (may include DeepSeek results)
            # Ensure is_game_related is populated for older files
            for i in items:
                if "is_game_related" not in i:
                    i["is_game_related"] = i.get("sentiment", "Neutral") != "Irrelevant"
            _hot_cache = {}
            for i in items:
                p = i.get("platform", "other")
                if p not in _hot_cache:
                    _hot_cache[p] = []
                _hot_cache[p].append(i)
            _hot_time = datetime.utcnow()
            print(f"[HotCrawl] Loaded {len(items)} items from hot_crawl.json")
            return True
    except Exception as e:
        print(f"[HotCrawl] Failed to load hot_crawl.json: {e}")
    return False


def _run_hot_crawl():
    global _hot_cache, _hot_time
    print("[HotCrawl] Starting direct hot list crawl...")
    platforms = ["zhihu", "douyin", "tieba"]
    all_items = []

    for platform in platforms:
        try:
            crawler = get_crawler(platform)
            items = crawler.fetch_hot_list()
            _hot_cache[platform] = items
            all_items.extend(items)
            print(f"[HotCrawl] {platform}: {len(items)} items")
        except Exception as e:
            print(f"[HotCrawl] {platform} error: {e}")

    _run_analyze(all_items)
    _persist_hot_crawl(all_items)  # Accumulate to file (free API, safe to re-run)
    _store_to_db(all_items, platforms)
    _hot_time = datetime.utcnow()
    print(f"[HotCrawl] Done: {len(all_items)} total")


# ==================== Keyword Search (Tophub /search API - Paid) ====================

TOPHUB_SEARCH_DATA_DIR: Optional[Path] = None  # Resolved lazily


def _get_search_data_dir() -> Path:
    global TOPHUB_SEARCH_DATA_DIR
    if TOPHUB_SEARCH_DATA_DIR is None:
        d = _get_data_base() / "tophub_search"
        d.mkdir(parents=True, exist_ok=True)
        TOPHUB_SEARCH_DATA_DIR = d
    return TOPHUB_SEARCH_DATA_DIR


def _persist_search_file(keyword: str, items: list, raw_data: dict = None):
    """Immediately save Tophub search results to a local JSON file (paid API, don't lose data)."""
    data_dir = _get_search_data_dir()
    today = datetime.utcnow().strftime("%Y%m%d")
    filename = f"{today}.json"  # Date-only filename for foolproof daily check
    filepath = data_dir / filename

    payload = {
        "keyword": keyword,
        "fetched_at": datetime.utcnow().isoformat(),
        "total_items": len(items),
        "raw_response": raw_data,
        "parsed_items": items,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[Search] Persisted {len(items)} items to {filepath}")
    return str(filepath)


def _check_today_search_exists() -> bool:
    """Check if today's search data file already exists (foolproof: prevent duplicate paid API calls)."""
    data_dir = _get_search_data_dir()
    today = datetime.utcnow().strftime("%Y%m%d")
    filepath = data_dir / f"{today}.json"
    return filepath.exists()


def _load_today_search_to_cache() -> bool:
    """Load today's search data into memory cache. Returns True if successful."""
    global _search_cache, _search_time
    data_dir = _get_search_data_dir()
    today = datetime.utcnow().strftime("%Y%m%d")
    filepath = data_dir / f"{today}.json"
    if not filepath.exists():
        return False
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            file_data = json.load(f)
        items = file_data.get("parsed_items", [])
        if items:
            # Keep stored sentiment labels (may include DeepSeek results)
            # Ensure is_game_related is populated for older files
            for i in items:
                if "is_game_related" not in i:
                    i["is_game_related"] = i.get("sentiment", "Neutral") != "Irrelevant"
            _search_cache = {}
            for i in items:
                p = i.get("platform", "other")
                if p not in _search_cache:
                    _search_cache[p] = []
                _search_cache[p].append(i)
            _search_time = datetime.utcnow()
            print(f"[Search] Loaded {len(items)} items from {filepath}")
            return True
    except Exception as e:
        print(f"[Search] Failed to load {filepath}: {e}")
    return False


def _run_keyword_search(keywords: List[str] = None):
    """Call Tophub /search API (paid endpoint) and persist results to local file immediately."""
    global _search_cache, _search_time

    # Foolproof: check if today's data already exists
    if _check_today_search_exists():
        print(f"[Search] Today's data already exists, skipping paid API call. Loading from file...")
        _load_today_search_to_cache()
        return

    keyword = "米哈游"
    if keywords and len(keywords) > 0:
        keyword = keywords[0]

    print(f"[Search] Calling Tophub /search API with q={keyword}...")

    from app.crawlers import fetch_tophub_search, _extract_platform_from_url

    all_items = []
    raw_data = None

    try:
        result = fetch_tophub_search(keyword, 1)
        raw_data = result
        if result.get("error"):
            print(f"[Search] API returned error: {result.get('msg', 'unknown')}")
            return

        data = result.get("data", {})
        items = data.get("items", [])
        total_pages = data.get("totalpage", 1)
        totalsize = data.get("totalsize", 0)
        print(f"[Search] Page 1: {len(items)} items, total {total_pages} pages, {totalsize} results")

        for item in items:
            platform = _extract_platform_from_url(item.get("url", ""))
            all_items.append({
                "id": hashlib.md5(f"tophub-search-{item.get('title', '')}".encode()).hexdigest()[:16],
                "platform": platform,
                "title": item.get("title", ""),
                "rank": 0,
                "heat": 0,
                "url": item.get("url", ""),
                "description": item.get("description", ""),
                "extra": item.get("extra", ""),
                "time": item.get("time"),
                "source": "search",
                "fetched_at": datetime.utcnow().isoformat(),
            })

        # Optionally fetch more pages (up to 3 total to limit paid API cost)
        for p in range(2, min(total_pages + 1, 4)):
            r = fetch_tophub_search(keyword, p)
            if r.get("error"):
                break
            page_data = r.get("data", {})
            page_items = page_data.get("items", [])
            for item in page_items:
                platform = _extract_platform_from_url(item.get("url", ""))
                all_items.append({
                    "id": hashlib.md5(f"tophub-search-{item.get('title', '')}".encode()).hexdigest()[:16],
                    "platform": platform,
                    "title": item.get("title", ""),
                    "rank": 0,
                    "heat": 0,
                    "url": item.get("url", ""),
                    "description": item.get("description", ""),
                    "extra": item.get("extra", ""),
                    "time": item.get("time"),
                    "source": "search",
                    "fetched_at": datetime.utcnow().isoformat(),
                })
            print(f"[Search] Page {p}: {len(page_items)} items (cumulative: {len(all_items)})")

    except Exception as e:
        print(f"[Search] Error: {e}")
        return

    # Analyze sentiment BEFORE persisting (so saved file has analyzed data)
    _run_analyze(all_items)

    # Persist to local file (paid data, includes sentiment labels now)
    _persist_search_file(keyword, all_items, raw_data)

    # Group by platform for cache
    _search_cache = {}
    for item in all_items:
        p = item["platform"]
        if p not in _search_cache:
            _search_cache[p] = []
        _search_cache[p].append(item)

    platforms = list(_search_cache.keys())
    _store_to_db(all_items, platforms)
    _search_time = datetime.utcnow()
    print(f"[Search] Done: {len(all_items)} items across {len(platforms)} platforms")


def _store_to_db(all_items, platforms):
    try:
        db = SessionLocal()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        for item in all_items:
            existing = db.query(HotTopicModel).filter(HotTopicModel.id == item["id"]).first()
            if not existing:
                db.add(HotTopicModel(
                    id=item["id"], platform=item["platform"], title=item["title"],
                    rank=item.get("rank", 0), heat=item.get("heat", 0),
                    url=item.get("url", ""), fetched_at=datetime.utcnow(),
                    sentiment=item.get("sentiment", "Neutral"),
                    related_game=item.get("related_game"),
                    is_game_related=item.get("is_game_related", False),
                ))

        # Merge ALL cached items for accurate daily stats (hot + search combined)
        all_combined = []
        for p, items in _hot_cache.items():
            all_combined.extend(items)
        for p, items in _search_cache.items():
            all_combined.extend(items)
        if not all_combined:
            all_combined = all_items  # Fallback

        all_platforms = set(list(_hot_cache.keys()) + list(_search_cache.keys()))
        if not all_platforms:
            all_platforms = set(platforms)

        game_related = [i for i in all_combined if i.get("is_game_related")]
        by_platform_data = {p: {
            "total": len([i for i in all_combined if i["platform"] == p]),
            "positive": sum(1 for i in all_combined if i["platform"] == p and i.get("sentiment") == "Positive"),
            "negative": sum(1 for i in all_combined if i["platform"] == p and i.get("sentiment") == "Negative"),
            "neutral": sum(1 for i in all_combined if i["platform"] == p and i.get("sentiment") == "Neutral"),
            "irrelevant": sum(1 for i in all_combined if i["platform"] == p and i.get("sentiment") == "Irrelevant"),
        } for p in all_platforms}

        existing_stats = db.query(DailyStatsModel).filter(DailyStatsModel.date == today).first()
        if existing_stats:
            existing_stats.total_topics = len(all_combined)
            existing_stats.game_related = len(game_related)
            existing_stats.positive = sum(1 for i in game_related if i.get("sentiment") == "Positive")
            existing_stats.negative = sum(1 for i in game_related if i.get("sentiment") == "Negative")
            existing_stats.neutral = sum(1 for i in game_related if i.get("sentiment") == "Neutral")
            existing_stats.irrelevant = sum(1 for i in all_combined if i.get("sentiment") == "Irrelevant")
            existing_stats.by_platform = by_platform_data
        else:
            db.add(DailyStatsModel(
                date=today, total_topics=len(all_combined), game_related=len(game_related),
                positive=sum(1 for i in game_related if i.get("sentiment") == "Positive"),
                negative=sum(1 for i in game_related if i.get("sentiment") == "Negative"),
                neutral=sum(1 for i in game_related if i.get("sentiment") == "Neutral"),
                irrelevant=sum(1 for i in all_combined if i.get("sentiment") == "Irrelevant"),
                by_platform=by_platform_data,
            ))
        db.commit(); db.close()
    except Exception as e:
        print(f"[DB] Error: {e}")


# ==================== API Endpoints ====================

@router.get("/dashboard")
async def get_dashboard():
    global _search_cache
    all_topics = []

    # Fallback: if caches are empty, try loading from persisted files
    if not any(len(v) for v in _search_cache.values()):
        _load_today_search_to_cache()
    if not any(len(v) for v in _hot_cache.values()):
        _load_hot_crawl_from_file()

    # Ensure daily stats exist in DB (for history page after restart)
    try:
        db = SessionLocal()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        existing = db.query(DailyStatsModel).filter(DailyStatsModel.date == today).first()
        if not existing and (any(len(v) for v in _hot_cache.values()) or any(len(v) for v in _search_cache.values())):
            all_items = []
            for p in set(list(_hot_cache.keys()) + list(_search_cache.keys())):
                for items in [_hot_cache.get(p, []), _search_cache.get(p, [])]:
                    all_items.extend(items)
            platforms = list(set(list(_hot_cache.keys()) + list(_search_cache.keys())))
            _store_to_db(all_items, platforms)
            print(f"[Dashboard] Synced {len(all_items)} items to daily stats")
        db.close()
    except:
        pass

    all_platforms = set(list(_hot_cache.keys()) + list(_search_cache.keys()))
    for p in all_platforms:
        for items in [_hot_cache.get(p, []), _search_cache.get(p, [])]:
            for i in items:
                all_topics.append({
                    "id": i["id"], "platform": i["platform"], "title": i["title"],
                    "rank": i.get("rank", 0), "heat": i.get("heat", 0),
                    "url": i.get("url", ""), "fetchedAt": i.get("fetched_at", ""),
                    "sentiment": i.get("sentiment", "Neutral"),
                    "relatedGame": i.get("related_game"),
                    "isGameRelated": i.get("is_game_related", False),
                    "source": i.get("source", "hot"),
                })

    total = len(all_topics)
    gr = [t for t in all_topics if t.get("isGameRelated")]
    return {
        "summary": {
            "totalTopics": total, "gameRelated": len(gr),
            "positive": sum(1 for t in gr if t.get("sentiment") == "Positive"),
            "negative": sum(1 for t in gr if t.get("sentiment") == "Negative"),
            "neutral": sum(1 for t in gr if t.get("sentiment") == "Neutral"),
            "irrelevant": sum(1 for t in all_topics if t.get("sentiment") == "Irrelevant"),
        },
        "hotTopics": [t for t in all_topics if t.get("source") == "hot"][:150],
        "searchTopics": [t for t in all_topics if t.get("source") != "hot"][:150],
        "topics": all_topics[:60],
    }


@router.get("/topics")
async def get_topics(platform: Optional[str] = None, source: Optional[str] = None):
    cache = _hot_cache if source == "hot" else _search_cache if source == "search" else {}
    all_p = list(set(list(_hot_cache.keys()) + list(_search_cache.keys())))
    platforms_to_use = all_p if not platform else [platform]
    result = []
    for p in platforms_to_use:
        items = cache.get(p, []) if source else _hot_cache.get(p, []) + _search_cache.get(p, [])
        for i in items:
            result.append({
                "id": i["id"], "platform": i["platform"], "title": i["title"],
                "rank": i.get("rank", 0), "heat": i.get("heat", 0),
                "url": i.get("url", ""), "fetchedAt": i.get("fetched_at", ""),
                "sentiment": i.get("sentiment", "Neutral"),
                "relatedGame": i.get("related_game"),
                "isGameRelated": i.get("is_game_related", False),
                "source": i.get("source", "hot"),
            })
    return result


@router.post("/crawl/hot")
async def trigger_hot_crawl():
    threading.Thread(target=_run_hot_crawl, daemon=True).start()
    return {"message": "正在爬取三大平台热搜（每平台50条）...", "status": "crawling"}


@router.post("/crawl/search")
async def trigger_search(keywords: List[str] = None):
    global _search_keywords
    if keywords:
        _search_keywords = keywords
    threading.Thread(target=lambda: _run_keyword_search(keywords), daemon=True).start()
    return {"message": f"正在执行热点搜索（高级）: {keywords or _search_keywords}", "status": "crawling"}


@router.get("/crawl/status")
async def crawl_status():
    hot_total = sum(len(v) for v in _hot_cache.values())
    search_total = sum(len(v) for v in _search_cache.values())
    all_p = set(list(_hot_cache.keys()) + list(_search_cache.keys()))
    return {
        "hasData": (hot_total + search_total) > 0,
        "hotTotal": hot_total, "searchTotal": search_total,
        "byPlatform": {
            p: {"hot": len(_hot_cache.get(p, [])), "search": len(_search_cache.get(p, []))}
            for p in sorted(all_p)
        },
        "lastHotCrawl": _hot_time.isoformat() if _hot_time else None,
        "lastSearch": _search_time.isoformat() if _search_time else None,
    }


# ==================== Search Keywords Config ====================

@router.get("/search/keywords")
async def get_search_keywords():
    return {"keywords": _get_search_keywords()}


@router.post("/search/keywords")
async def set_search_keywords(data: dict):
    global _search_keywords
    words = data.get("keywords", [])
    if isinstance(words, str):
        words = [w.strip() for w in words.split(",") if w.strip()]
    if words:
        _search_keywords = words
    return {"keywords": _get_search_keywords()}


# ==================== Tophub Search File Persistence ====================

@router.get("/tophub/search/files")
async def list_search_files():
    """List saved Tophub search result files (for backup/export)."""
    data_dir = _get_search_data_dir()
    if not data_dir.exists():
        return {"files": [], "data_dir": str(data_dir)}
    files = []
    for f in sorted(data_dir.glob("*.json"), reverse=True):
        stat = f.stat()
        files.append({
            "filename": f.name,
            "size_bytes": stat.st_size,
            "size_kb": round(stat.st_size / 1024, 1),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        })
    return {"files": files, "data_dir": str(data_dir), "total": len(files)}


@router.get("/tophub/search/export/{filename}")
async def export_search_file(filename: str):
    """Download a specific Tophub search result JSON file for backup."""
    data_dir = _get_search_data_dir()
    filepath = data_dir / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"文件 {filename} 不存在")
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="仅支持导出 .json 文件")
    # Prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")
    return FileResponse(str(filepath), media_type="application/json", filename=filename)


@router.get("/tophub/search/latest")
async def get_latest_search():
    """Get the latest Tophub search results from the persisted file."""
    data_dir = _get_search_data_dir()
    today = datetime.utcnow().strftime("%Y%m%d")
    filepath = data_dir / f"{today}.json"
    if not filepath.exists():
        # Fallback to any available date file
        existing = sorted(data_dir.glob("*.json"), reverse=True)
        if existing:
            filepath = existing[0]
        else:
            return {"hasData": False, "message": "暂无搜索数据，请先执行热点搜索（高级）"}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"hasData": True, "data": data, "sourceFile": filepath.name}
    except Exception as e:
        return {"hasData": False, "message": f"读取文件失败: {e}"}


@router.get("/tophub/search/today")
async def check_today_search():
    """Check if today's Tophub search data already exists (foolproof)."""
    exists = _check_today_search_exists()
    return {
        "exists": exists,
        "today": datetime.utcnow().strftime("%Y%m%d"),
        "message": "今日已搜索，无需重复调用付费API" if exists else "今日尚未搜索",
    }


# ==================== DeepSeek API Sentiment Analysis ====================

def _get_deepseek_key() -> str:
    """Get DeepSeek API key from DB"""
    try:
        db = SessionLocal()
        acc = db.query(AccountModel).filter(AccountModel.platform == "deepseek").first()
        db.close()
        if acc and acc.username:
            return acc.username
    except:
        pass
    return ""


def _deepseek_analyze(title: str) -> Optional[str]:
    """Use DeepSeek API to analyze sentiment of a hot topic title.
    Returns: "Positive"/"Negative"/"Neutral"/"Irrelevant" or None if failed."""
    import httpx
    api_key = _get_deepseek_key()
    if not api_key:
        return None

    prompt = f"""你是米哈游舆情分析专家。判断以下标题对米哈游的情感倾向。
规则：
- 赞扬、推荐、好消息、正面数据 → 正面
- 批评、抱怨、负面数据、节奏 → 负面
- 客观陈述、中性数据、事实报道 → 中性
- 与米哈游/二游完全无关 → 无关
只回复两个字：正面、负面、中性 或 无关

标题：{title}"""

    try:
        resp = httpx.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 10,
            },
            timeout=15,
        )
        data = resp.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        if "正面" in answer:
            return "Positive"
        elif "负面" in answer:
            return "Negative"
        elif "无关" in answer:
            return "Irrelevant"
        elif "中性" in answer:
            return "Neutral"
        else:
            return None
    except Exception as e:
        print(f"[DeepSeek] Error: {e}")
        return None


@router.post("/deepseek/verify")
async def verify_deepseek(body: dict = None):
    """Verify DeepSeek API key and save if valid."""
    api_key = (body or {}).get("apiKey", "")
    if not api_key:
        return {"isValid": False, "message": "请输入API Key"}

    try:
        import httpx
        resp = httpx.get(
            "https://api.deepseek.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            # Save valid key
            db = SessionLocal()
            acc = db.query(AccountModel).filter(AccountModel.platform == "deepseek").first()
            if acc:
                acc.username = api_key
                acc.is_valid = True
                acc.last_verified = datetime.utcnow()
            else:
                db.add(AccountModel(platform="deepseek", username=api_key, cookie="", is_valid=True, last_verified=datetime.utcnow()))
            db.commit()
            db.close()
            return {"isValid": True, "message": "DeepSeek API Key 有效"}
        else:
            return {"isValid": False, "message": f"验证失败: HTTP {resp.status_code}"}
    except Exception as e:
        return {"isValid": False, "message": f"网络错误: {str(e)[:60]}"}


@router.get("/deepseek/status")
async def deepseek_status():
    """Get DeepSeek API connection status."""
    api_key = _get_deepseek_key()
    if not api_key:
        return {"configured": False, "isValid": False, "message": "未配置DeepSeek API Key"}
    try:
        db = SessionLocal()
        acc = db.query(AccountModel).filter(AccountModel.platform == "deepseek").first()
        db.close()
        return {
            "configured": True,
            "isValid": acc.is_valid if acc else False,
            "lastVerified": acc.last_verified.isoformat() if (acc and acc.last_verified) else "",
        }
    except:
        return {"configured": True if api_key else False, "isValid": False, "message": ""}


# ==================== DeepSeek Batch Analyze All ====================

@router.get("/deepseek/analyze-status")
async def deepseek_analyze_status():
    """Check if today's DeepSeek batch analysis has been run."""
    data_dir = _get_dsstore_dir()
    today = datetime.utcnow().strftime("%Y%m%d")
    lock_file = data_dir / f"{today}.dsstored"
    has_deepseek = bool(_get_deepseek_key())

    # Count how many topics need analysis
    all_items = []
    for p in set(list(_hot_cache.keys()) + list(_search_cache.keys())):
        for items in [_hot_cache.get(p, []), _search_cache.get(p, [])]:
            all_items.extend(items)
    game_related = [i for i in all_items if i.get("is_game_related")]
    total = len(all_items)

    return {
        "analyzed": lock_file.exists(),
        "today": today,
        "deepseekConfigured": has_deepseek,
        "totalTopics": total,
        "gameRelated": len(game_related),
        "pendingAnalysis": len(game_related) if not lock_file.exists() else 0,
    }


@router.post("/deepseek/analyze-all")
async def deepseek_analyze_all():
    """One-click DeepSeek batch analysis of all hot topics."""
    api_key = _get_deepseek_key()
    if not api_key:
        return {"ok": False, "message": "请先在账号管理页面配置 DeepSeek API Key"}

    data_dir = _get_dsstore_dir()
    today = datetime.utcnow().strftime("%Y%m%d")
    lock_file = data_dir / f"{today}.dsstored"

    if lock_file.exists():
        return {"ok": False, "message": f"今日（{today}）已完成 DeepSeek 分析，不可重复调用"}

    # Create lock immediately to prevent concurrent runs
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_file.touch()

    threading.Thread(target=_run_deepseek_batch_analyze, args=(lock_file,), daemon=True).start()

    # Count items to analyze
    all_items = []
    for p in set(list(_hot_cache.keys()) + list(_search_cache.keys())):
        for items in [_hot_cache.get(p, []), _search_cache.get(p, [])]:
            all_items.extend(items)
    game_related = [i for i in all_items if i.get("is_game_related")]

    return {
        "ok": True,
        "message": f"正在调用 DeepSeek 分析 {len(game_related)} 条二游相关热搜（共 {len(all_items)} 条）...",
        "totalTopics": len(all_items),
        "gameRelated": len(game_related),
    }


def _run_deepseek_batch_analyze(lock_file: Path):
    """Background thread: analyze all game-related topics with DeepSeek."""
    global _hot_cache, _search_cache
    print("[DeepSeek-Batch] Starting full analysis...")

    # Collect all game-related items
    all_items = []
    for p in set(list(_hot_cache.keys()) + list(_search_cache.keys())):
        for items in [_hot_cache.get(p, []), _search_cache.get(p, [])]:
            for i in items:
                if i.get("is_game_related"):
                    all_items.append(i)

    total = len(all_items)
    analyzed = 0
    changed = 0

    for item in all_items:
        title = item.get("title", "")
        try:
            ds_sentiment = _deepseek_analyze(title)
            if ds_sentiment and ds_sentiment != item.get("sentiment"):
                old = item.get("sentiment")
                item["sentiment"] = ds_sentiment
                changed += 1
                print(f"[DeepSeek-Batch] [{analyzed+1}/{total}] {title[:30]}... {old} -> {ds_sentiment}")
            analyzed += 1
        except Exception as e:
            print(f"[DeepSeek-Batch] Error on item {analyzed+1}: {e}")
            analyzed += 1

    # Update DB with new sentiment values
    try:
        db = SessionLocal()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        game_related = [i for i in all_items if i.get("is_game_related")]
        all_topic_items = []
        for p in set(list(_hot_cache.keys()) + list(_search_cache.keys())):
            for items in [_hot_cache.get(p, []), _search_cache.get(p, [])]:
                all_topic_items.extend(items)

        for item in all_items:
            existing = db.query(HotTopicModel).filter(HotTopicModel.id == item["id"]).first()
            if existing and item.get("sentiment") != existing.sentiment:
                existing.sentiment = item["sentiment"]

        # Update daily stats with new sentiment counts
        all_platforms = set(list(_hot_cache.keys()) + list(_search_cache.keys()))
        game_related_all = [i for i in all_topic_items if i.get("is_game_related")]

        by_platform_data = {p: {
            "total": len([i for i in all_topic_items if i["platform"] == p]),
            "positive": sum(1 for i in [i for i in all_topic_items if i["platform"] == p] if i.get("sentiment") == "Positive"),
            "negative": sum(1 for i in [i for i in all_topic_items if i["platform"] == p] if i.get("sentiment") == "Negative"),
            "neutral": sum(1 for i in [i for i in all_topic_items if i["platform"] == p] if i.get("sentiment") == "Neutral"),
            "irrelevant": sum(1 for i in [i for i in all_topic_items if i["platform"] == p] if i.get("sentiment") == "Irrelevant"),
        } for p in all_platforms}

        existing_stats = db.query(DailyStatsModel).filter(DailyStatsModel.date == today).first()
        if existing_stats:
            existing_stats.total_topics = len(all_topic_items)
            existing_stats.game_related = len(game_related_all)
            existing_stats.positive = sum(1 for i in game_related_all if i.get("sentiment") == "Positive")
            existing_stats.negative = sum(1 for i in game_related_all if i.get("sentiment") == "Negative")
            existing_stats.neutral = sum(1 for i in game_related_all if i.get("sentiment") == "Neutral")
            existing_stats.irrelevant = sum(1 for i in all_topic_items if i.get("sentiment") == "Irrelevant")
            existing_stats.by_platform = by_platform_data
        else:
            db.add(DailyStatsModel(
                date=today, total_topics=len(all_topic_items), game_related=len(game_related_all),
                positive=sum(1 for i in game_related_all if i.get("sentiment") == "Positive"),
                negative=sum(1 for i in game_related_all if i.get("sentiment") == "Negative"),
                neutral=sum(1 for i in game_related_all if i.get("sentiment") == "Neutral"),
                irrelevant=sum(1 for i in all_topic_items if i.get("sentiment") == "Irrelevant"),
                by_platform=by_platform_data,
            ))
        db.commit()
        db.close()
        print(f"[DeepSeek-Batch] DB updated with new sentiment counts")
    except Exception as e:
        print(f"[DeepSeek-Batch] DB update error: {e}")

    print(f"[DeepSeek-Batch] Done: {analyzed}/{total} analyzed, {changed} sentiment changed")

    # Re-persist all data files with updated DeepSeek sentiments (survive restart)
    try:
        data_dir = _get_search_data_dir()
        today = datetime.utcnow().strftime("%Y%m%d")
        # Update paid search JSON
        paid_file = data_dir / f"{today}.json"
        if paid_file.exists():
            with open(paid_file, "r", encoding="utf-8") as f:
                paid = json.load(f)
            paid_items = paid.get("parsed_items", [])
            for pi in paid_items:
                for item in all_items:
                    if pi.get("id") == item.get("id"):
                        pi["sentiment"] = item.get("sentiment")
            paid["parsed_items"] = paid_items
            with open(paid_file, "w", encoding="utf-8") as f:
                json.dump(paid, f, ensure_ascii=False, indent=2)
            print(f"[DeepSeek-Batch] Updated {paid_file}")
        # Update hot crawl JSON
        hot_file = data_dir / "hot_crawl.json"
        if hot_file.exists():
            with open(hot_file, "r", encoding="utf-8") as f:
                hot_list = json.load(f)
            for hi in hot_list:
                for item in all_items:
                    if hi.get("id") == item.get("id"):
                        hi["sentiment"] = item.get("sentiment")
            with open(hot_file, "w", encoding="utf-8") as f:
                json.dump(hot_list, f, ensure_ascii=False, indent=2)
            print(f"[DeepSeek-Batch] Updated {hot_file}")
    except Exception as e:
        print(f"[DeepSeek-Batch] Persist error: {e}")
    # Lock file already exists, keeping it for the day


# ==================== Analysis / Stats / Keywords / Accounts ====================

@router.get("/analysis/{topic_id}")
async def get_topic_analysis(topic_id: str):
    db = SessionLocal()
    try:
        topic = db.query(HotTopicModel).filter(HotTopicModel.id == topic_id).first()
        if not topic:
            raise HTTPException(status_code=404, detail="Not found")
        posts = db.query(PostItemModel).filter(PostItemModel.topic_id == topic_id).limit(100).all()
        dist = {"positive": 0, "negative": 0, "neutral": 0}
        for p in posts:
            if p.sentiment == "Positive": dist["positive"] += 1
            elif p.sentiment == "Negative": dist["negative"] += 1
            else: dist["neutral"] += 1
        return {"topicId": topic.id, "topic": _t(topic), "posts": [_p(p) for p in posts], "postSentimentDistribution": dist}
    finally:
        db.close()


@router.get("/stats/daily")
async def get_daily_stats(range: str = "7d", start: Optional[str] = None, end: Optional[str] = None):
    db = SessionLocal()
    try:
        q = db.query(DailyStatsModel)
        if range == "custom" and start and end:
            q = q.filter(DailyStatsModel.date >= start, DailyStatsModel.date <= end)
        else:
            days = {"7d": 7, "30d": 30}.get(range, 7)
            since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
            q = q.filter(DailyStatsModel.date >= since)
        return [_s(s) for s in q.order_by(DailyStatsModel.date.asc()).all()]
    finally:
        db.close()


@router.get("/keywords")
async def get_kw():
    db = SessionLocal(); r = [_k(k) for k in db.query(KeywordModel).all()]; db.close(); return r

@router.post("/keywords")
async def add_kw(d: dict):
    db = SessionLocal()
    k = KeywordModel(id=hashlib.md5(d["keyword"].encode()).hexdigest()[:16], keyword=d["keyword"], category=d.get("category","general"), added_at=datetime.utcnow(), added_by="user")
    db.add(k); db.commit(); db.close(); return _k(k)

@router.put("/keywords/{kid}")
async def update_kw(kid: str, d: dict):
    """Update keyword name and/or category."""
    db = SessionLocal()
    k = db.query(KeywordModel).filter(KeywordModel.id == kid).first()
    if not k:
        db.close()
        raise HTTPException(status_code=404, detail="关键词不存在")
    if "keyword" in d and d["keyword"]:
        k.keyword = d["keyword"]
    if "category" in d and d["category"]:
        k.category = d["category"]
    k.added_at = datetime.utcnow()  # Update timestamp
    db.commit()
    result = _k(k)
    db.close()
    # Invalidate sentiment cache so changes take effect
    try:
        from app.sentiment import _KEYWORD_CACHE
        import app.sentiment as sm
        sm._KEYWORD_CACHE = None
    except:
        pass
    return result

@router.delete("/keywords/{kid}")
async def del_kw(kid: str):
    db = SessionLocal(); k = db.query(KeywordModel).filter(KeywordModel.id==kid).first()
    if k:
        db.delete(k); db.commit()
    db.close()
    # Invalidate sentiment cache
    try:
        from app.sentiment import _KEYWORD_CACHE
        import app.sentiment as sm
        sm._KEYWORD_CACHE = None
    except:
        pass
    return {"ok":True}


# ==================== Keyword Import / Export ====================

def _clear_keyword_cache():
    """Invalidate the sentiment keyword cache so changes take effect."""
    try:
        import app.sentiment as sm
        sm._KEYWORD_CACHE = None
    except:
        pass


@router.get("/keywords/export")
async def export_keywords():
    """Export all keywords as downloadable JSON file."""
    db = SessionLocal()
    rows = db.query(KeywordModel).all()
    data = {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "total": len(rows),
        "keywords": [{"keyword": r.keyword, "category": r.category} for r in rows],
    }
    db.close()
    import io
    content = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=miho_keywords.json"},
    )


@router.post("/keywords/import")
async def import_keywords(body: dict):
    """Import keywords from JSON. Modes: 'replace' (clear all first) or 'merge' (add new only)."""
    from fastapi.responses import Response
    mode = body.get("mode", "merge")  # 'replace' or 'merge'
    items = body.get("keywords", [])

    if not items:
        raise HTTPException(status_code=400, detail="keywords array is required")

    db = SessionLocal()
    try:
        if mode == "replace":
            # Wipe all existing keywords
            db.query(KeywordModel).delete()

        count_added = 0
        count_skipped = 0
        import hashlib

        for item in items:
            kw = item.get("keyword", "").strip()
            cat = item.get("category", "general").strip()
            if not kw:
                continue

            existing = db.query(KeywordModel).filter(KeywordModel.keyword == kw).first()
            if existing:
                if mode == "replace":
                    existing.category = cat
                else:
                    count_skipped += 1
            else:
                db.add(KeywordModel(
                    id=hashlib.md5(kw.encode()).hexdigest()[:16],
                    keyword=kw, category=cat,
                    added_at=datetime.utcnow(), added_by="import",
                ))
                count_added += 1

        db.commit()

        # Seed defaults if DB is empty after replace with no items
        if mode == "replace" and count_added == 0 and not items:
            pass  # User explicitly cleared all keywords

        remaining = db.query(KeywordModel).count()
    except Exception as e:
        db.rollback()
        db.close()
        raise HTTPException(status_code=500, detail=str(e))
    db.close()

    _clear_keyword_cache()

    return {
        "ok": True,
        "mode": mode,
        "added": count_added,
        "skipped": count_skipped,
        "total": remaining,
        "message": f"导入完成: 新增 {count_added} 条, 跳过 {count_skipped} 条, 共计 {remaining} 条",
    }


@router.post("/keywords/reset")
async def reset_keywords_to_default():
    """Delete all keywords and re-seed the default 200+ dictionary."""
    db = SessionLocal()
    try:
        db.query(KeywordModel).delete()
        db.commit()
    except:
        db.rollback()
    db.close()

    # Re-invoke seed
    from app.sentiment import seed_default_keywords
    seed_default_keywords()

    # Count
    db = SessionLocal()
    total = db.query(KeywordModel).count()
    db.close()

    _clear_keyword_cache()
    return {"ok": True, "total": total, "message": f"已重置为默认关键词词典 ({total} 条)"}


# ==================== Category Management ====================

CATEGORIES_FILE: Optional[Path] = None

def _get_categories_path() -> Path:
    global CATEGORIES_FILE
    if CATEGORIES_FILE is None:
        d = _get_data_base()
        d.mkdir(parents=True, exist_ok=True)
        CATEGORIES_FILE = d / "categories.json"
    return CATEGORIES_FILE

def _load_categories() -> dict:
    path = _get_categories_path()
    if not path.exists():
        defaults = {"categories": {"mihoyo_game": {"name": "米哈游游戏", "order": 1}, "mihoyo_character": {"name": "米哈游角色", "order": 2}, "mihoyo_cv": {"name": "米哈游CV", "order": 3}, "competitor": {"name": "竞品游戏", "order": 4}, "general": {"name": "二游圈通用", "order": 5}}}
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(defaults, f, ensure_ascii=False, indent=2)
        return defaults
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_categories(data: dict):
    path = _get_categories_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.get("/categories")
async def get_categories():
    return _load_categories()


@router.post("/categories")
async def add_category(d: dict):
    key = d.get("key", "").strip()
    name = d.get("name", "").strip()
    if not key or not name:
        raise HTTPException(status_code=400, detail="key 和 name 不能为空")
    data = _load_categories()
    if key in data["categories"]:
        raise HTTPException(status_code=400, detail=f"分类 {key} 已存在")
    max_order = max((c.get("order", 0) for c in data["categories"].values()), default=0)
    data["categories"][key] = {"name": name, "order": max_order + 1}
    _save_categories(data)
    return data


@router.put("/categories/{cat_key}")
async def update_category(cat_key: str, d: dict):
    data = _load_categories()
    if cat_key not in data["categories"]:
        raise HTTPException(status_code=404, detail=f"分类 {cat_key} 不存在")
    old_key = cat_key
    new_key = d.get("key", old_key)
    new_name = d.get("name", data["categories"][old_key]["name"])

    if new_key != old_key:
        if new_key in data["categories"]:
            raise HTTPException(status_code=400, detail=f"分类 {new_key} 已存在")
        # Migrate keywords to new category key
        try:
            db = SessionLocal()
            kws = db.query(KeywordModel).filter(KeywordModel.category == old_key).all()
            for kw in kws:
                kw.category = new_key
            db.commit()
            db.close()
        except Exception as e:
            print(f"[Categories] Failed to migrate keywords: {e}")
        data["categories"][new_key] = data["categories"].pop(old_key)

    data["categories"][new_key]["name"] = new_name
    _save_categories(data)
    # Invalidate frontend cache
    try:
        import app.sentiment as sm
        sm._KEYWORD_CACHE = None
    except:
        pass
    return data


@router.delete("/categories/{cat_key}")
async def delete_category(cat_key: str):
    data = _load_categories()
    if cat_key not in data["categories"]:
        raise HTTPException(status_code=404, detail=f"分类 {cat_key} 不存在")
    # Don't allow deleting the last category
    if len(data["categories"]) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个分类")

    # Reassign keywords to "general" or delete them
    reassign = data["categories"].get("general", None)
    target_key = "general" if reassign else list(data["categories"].keys())[0]

    try:
        db = SessionLocal()
        kws = db.query(KeywordModel).filter(KeywordModel.category == cat_key).all()
        for kw in kws:
            kw.category = target_key
        db.commit()
        db.close()
    except Exception as e:
        print(f"[Categories] Failed to reassign keywords: {e}")

    del data["categories"][cat_key]
    _save_categories(data)
    try:
        import app.sentiment as sm
        sm._KEYWORD_CACHE = None
    except:
        pass
    return data

@router.get("/accounts")
async def get_acc():
    db = SessionLocal(); r = [_a(a) for a in db.query(AccountModel).all()]; db.close(); return r

@router.post("/accounts")
async def save_acc(d: dict):
    db = SessionLocal()
    e = db.query(AccountModel).filter(AccountModel.platform==d["platform"]).first()
    if e:
        e.username = d.get("username", e.username)
        e.cookie = d.get("cookie", e.cookie)
        # Don't reset isValid when just saving cookie (verify will set it)
        if "isValid" in d:
            e.is_valid = d["isValid"]
    else:
        db.add(AccountModel(platform=d["platform"], username=d.get("username",""), cookie=d.get("cookie",""), is_valid=False))
    db.commit(); db.close(); return {"ok": True}

@router.post("/accounts/{platform}/verify")
async def verify(platform: str, body: dict = None):
    cookie = (body or {}).get("cookie", "")
    if platform == "tophub":
        return _verify_tophub(cookie)
    if not cookie:
        db = SessionLocal()
        a = db.query(AccountModel).filter(AccountModel.platform == platform).first()
        cookie = a.cookie if a else ""
        db.close()
    if not cookie:
        return {"isValid": False, "message": "未配置Cookie"}
    v = len(cookie) > 20
    db = SessionLocal()
    a = db.query(AccountModel).filter(AccountModel.platform == platform).first()
    if a:
        a.is_valid = v
        a.last_verified = datetime.utcnow()
        db.commit()
    db.close()
    return {"isValid": v, "message": "Cookie有效" if v else "Cookie过短"}


def _verify_tophub(api_key=""):
    """Verify Tophub API key by calling /nodes endpoint"""
    try:
        import httpx
        if not api_key:
            db = SessionLocal()
            acc = db.query(AccountModel).filter(AccountModel.platform == "tophub").first()
            api_key = acc.username if acc else ""
            db.close()
        if not api_key:
            print("[Verify-Tophub] No API key found")
            return {"isValid": False, "message": "请先输入API Key"}

        print(f"[Verify-Tophub] Testing key: {api_key[:10]}...")
        r = httpx.get("https://api.tophubdata.com/nodes?p=1",
                      headers={"Authorization": api_key}, timeout=15)
        print(f"[Verify-Tophub] HTTP {r.status_code}, body: {r.text[:200]}")
        data = r.json()
        if data.get("error") == False and data.get("data"):
            node_count = len(data["data"])
            print(f"[Verify-Tophub] SUCCESS: {node_count} nodes")
            db = SessionLocal()
            a = db.query(AccountModel).filter(AccountModel.platform == "tophub").first()
            if a:
                a.is_valid = True
                a.last_verified = datetime.utcnow()
                a.username = api_key
                db.commit()
            db.close()
            return {"isValid": True, "message": f"API Key有效，共{node_count}个榜单节点"}
        else:
            msg = data.get("msg", "密钥验证失败")
            print(f"[Verify-Tophub] FAIL: {msg}")
            return {"isValid": False, "message": msg if msg else "密钥无效"}
    except Exception as e:
        print(f"[Verify-Tophub] ERROR: {e}")
        return {"isValid": False, "message": f"网络错误: {str(e)[:60]}"}


# ==================== Bilibili User Comment Analysis ("查成分") ====================

import asyncio as _asyncio_mod

# In-memory cache for analysis results (uid → result dict)
_bili_analysis_cache: dict = {}
_bili_analysis_lock = threading.Lock()


def _run_bili_analyze_sync(uid: int, max_videos: int, max_comments: int, months_limit: int):
    """Background task: fetch comments, filter, and analyze with DeepSeek."""
    global _bili_analysis_cache
    import traceback as _tb
    try:
        print(f"[BiliAnalyze] Starting analysis for uid={uid}")
        loop = _asyncio_mod.new_event_loop()
        _asyncio_mod.set_event_loop(loop)
        from app.bilibili import fetch_user_video_comments, filter_comments_by_keywords, analyze_user_personality, get_user_info
        print(f"[BiliAnalyze] Fetching user info...")
        user_info = loop.run_until_complete(get_user_info(uid))
        print(f"[BiliAnalyze] User: {user_info.get('name')}")
        print(f"[BiliAnalyze] Fetching comments...")
        all_comments = loop.run_until_complete(
            fetch_user_video_comments(uid, max_videos=max_videos,
                                       max_comments_per_video=max_comments,
                                       months_limit=months_limit)
        )
        loop.close()
        print(f"[BiliAnalyze] Got {len(all_comments)} comments total")

        # Filter by keywords (for marking, not for exclusion)
        print(f"[BiliAnalyze] Filtering by keywords...")
        matched_comments = filter_comments_by_keywords(all_comments)
        print(f"[BiliAnalyze] {len(matched_comments)} comments matched keywords")

        # DeepSeek personality analysis (always run if API key set, even 0 matched)
        ds_key = _get_deepseek_key()
        print(f"[BiliAnalyze] DeepSeek configured: {bool(ds_key)}, matched={len(matched_comments)}, total={len(all_comments)}")
        spectrum = None
        if ds_key and all_comments:
            print(f"[BiliAnalyze] Calling DeepSeek for personality analysis...")
            loop2 = _asyncio_mod.new_event_loop()
            _asyncio_mod.set_event_loop(loop2)
            spectrum = loop2.run_until_complete(analyze_user_personality(all_comments, matched_comments, ds_key))
            loop2.close()
            print(f"[BiliAnalyze] DeepSeek result: score={spectrum.get('score')}, summary={spectrum.get('summary')}")
        elif ds_key and not all_comments:
            spectrum = {
                "score": 50, "mihoyo_attitude": "该用户无历史评论记录", "active_areas": "未知",
                "personality": "无法分析", "summary": "无评论数据"
            }
        else:
            spectrum = {
                "score": 50, "mihoyo_attitude": "未配置DeepSeek API Key", "active_areas": "未知",
                "personality": "无法分析", "summary": "请先配置API Key"
            }

        result = {
            "status": "done",
            "uid": uid,
            "user_info": user_info,
            "total_comments": len(all_comments),
            "matched_count": len(matched_comments),
            "all_comments": all_comments,           # ALL comments for display
            "comments": matched_comments,            # keyword-matched subset
            "spectrum": spectrum,
            "analyzed_at": datetime.utcnow().isoformat(),
        }
        with _bili_analysis_lock:
            _bili_analysis_cache[str(uid)] = result
        print(f"[BiliAnalyze] Done: uid={uid}, {len(all_comments)} comments, {len(matched_comments)} matched, score={spectrum.get('score')}")
    except Exception as e:
        print(f"[BiliAnalyze] FATAL ERROR for uid={uid}: {e}")
        _tb.print_exc()
        error_result = {
            "status": "error",
            "uid": uid,
            "error": str(e),
            "total_comments": 0,
            "matched_count": 0,
            "comments": [],
            "spectrum": {"score": 50, "analysis": f"分析出错: {str(e)[:100]}", "summary": "出错"},
        }
        with _bili_analysis_lock:
            _bili_analysis_cache[str(uid)] = error_result


@router.get("/bilibili/user/info")
async def get_bili_user_info(uid: int):
    """Get Bilibili user basic info by UID."""
    import traceback as _tb
    try:
        from app.bilibili import get_user_info as _bili_get_user
        print(f"[API] /bilibili/user/info uid={uid}")
        info = await _bili_get_user(uid)
        print(f"[API] /bilibili/user/info OK: {info.get('name', '?')}")
        return {"ok": True, "data": info}
    except Exception as e:
        print(f"[API] /bilibili/user/info ERROR: {e}")
        _tb.print_exc()
        return {"ok": False, "error": str(e)}


@router.get("/bilibili/analyze/status")
async def get_bili_analyze_status(uid: int):
    """Check if analysis for a UID exists in cache."""
    with _bili_analysis_lock:
        result = _bili_analysis_cache.get(str(uid))
    if result:
        return {
            "exists": True,
            "status": result.get("status"),
            "uid": uid,
            "total_comments": result.get("total_comments", 0),
            "matched_count": result.get("matched_count", 0),
            "score": result.get("spectrum", {}).get("score"),
            "analyzed_at": result.get("analyzed_at", ""),
        }
    return {"exists": False, "uid": uid}


@router.get("/bilibili/analyze/result")
async def get_bili_analyze_result(uid: int, page: int = 1, page_size: int = 100):
    """Get cached analysis result with paginated ALL comments."""
    with _bili_analysis_lock:
        result = _bili_analysis_cache.get(str(uid))
    if not result:
        return {"ok": False, "error": "该UID尚未分析，请先执行分析"}

    # Return ALL comments (paginated). For old cache without all_comments, fall back to comments
    all_comments = result.get("all_comments") or result.get("comments") or []
    total = len(all_comments)
    start = (page - 1) * page_size
    end = start + page_size
    paged_comments = all_comments[start:end]

    return {
        "ok": True,
        "status": result.get("status"),
        "uid": result.get("uid"),
        "user_info": result.get("user_info"),
        "total_comments": result.get("total_comments", 0),
        "matched_count": result.get("matched_count", 0),
        "comments": paged_comments,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "spectrum": result.get("spectrum"),
        "analyzed_at": result.get("analyzed_at"),
    }


@router.post("/bilibili/analyze")
async def trigger_bili_analyze(body: dict):
    """Trigger Bilibili user comment analysis.
    Body: {"uid": int, "max_videos": int (opt), "max_comments_per_video": int (opt), "months_limit": int (opt)}
    """
    uid = body.get("uid")
    if not uid:
        raise HTTPException(status_code=400, detail="请提供用户UID")
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="UID必须是数字")

    max_videos = int(body.get("max_videos", 50))
    max_comments = int(body.get("max_comments_per_video", 500))
    months_limit = int(body.get("months_limit", 6))

    # Check if already analyzing
    with _bili_analysis_lock:
        existing = _bili_analysis_cache.get(str(uid))
        if existing and existing.get("status") == "processing":
            return {"ok": False, "error": "该UID正在分析中，请稍后查看结果"}

        _bili_analysis_cache[str(uid)] = {"status": "processing", "uid": uid}

    threading.Thread(
        target=_run_bili_analyze_sync,
        args=(uid, max_videos, max_comments, months_limit),
        daemon=True,
    ).start()

    return {
        "ok": True,
        "message": f"正在分析UID {uid} 的历史评论（近{months_limit}个月，最多扫描{max_videos}个视频）...",
        "uid": uid,
    }


# Helpers
def _t(t): return {"id":t.id,"platform":t.platform,"title":t.title,"rank":t.rank,"heat":t.heat,"url":t.url or "","fetchedAt":t.fetched_at.isoformat() if t.fetched_at else "","sentiment":t.sentiment,"relatedGame":t.related_game,"isGameRelated":t.is_game_related}
def _p(p): return {"id":p.id,"topicId":p.topic_id,"platform":p.platform,"content":p.content,"author":p.author or "","likes":p.likes or 0,"comments":p.comments or 0,"timestamp":p.timestamp.isoformat() if p.timestamp else "","sentiment":p.sentiment,"url":p.url or ""}
def _s(s): return {"date":s.date,"totalTopics":s.total_topics,"gameRelated":s.game_related,"positive":s.positive,"negative":s.negative,"neutral":s.neutral,"irrelevant":s.irrelevant,"byPlatform":s.by_platform or {}}
def _k(k): return {"id":k.id,"keyword":k.keyword,"category":k.category,"addedAt":k.added_at.isoformat() if k.added_at else "","addedBy":k.added_by}
def _a(a): return {"platform":a.platform,"username":a.username or "","cookie":a.cookie or "","isValid":a.is_valid,"lastVerified":a.last_verified.isoformat() if a.last_verified else ""}
