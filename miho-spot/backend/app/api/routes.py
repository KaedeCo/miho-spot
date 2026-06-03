"""
Miho-spot Backend API Routes - Hot crawl + Keyword search
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import func as _sql_func
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import threading
import hashlib
import json

from app.models import get_db, SessionLocal, init_db
from app.models import HotTopicModel, PostItemModel, DailyStatsModel, KeywordModel, AccountModel, BiliUserProfile, VideoAnalysisTask, VideoComment
from app.models import SavedVaTask, WordCloudItem, DeepAnalysis, IdentityQueue
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

# Search error state (separate from AICU/Bilibili)
_search_error: Optional[str] = None
_search_error_code: Optional[str] = None
_search_running: bool = False

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
    global _search_cache, _search_time, _search_error, _search_error_code, _search_running

    # Reset error state at start
    _search_error = None
    _search_error_code = None
    _search_running = True

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
            msg = result.get("msg", "unknown Tophub API error")
            code = str(result.get("code", result.get("status", "TOPHUB_ERR")))
            print(f"[Search] API returned error: code={code}, msg={msg}")
            _search_error = msg
            _search_error_code = f"TOPHUB_{code}"
            _search_running = False
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
                _search_error = r.get("msg", f"Tophub API error on page {p}")
                _search_error_code = f"TOPHUB_PAGE_{p}_ERR"
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
        err_str = str(e)
        print(f"[Search] Error: {err_str}")
        _search_error = err_str[:200]
        _search_error_code = "SEARCH_EXCEPTION"
        _search_running = False
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
    _search_running = False
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

    # Fallback 1: if caches are empty, try loading from persisted JSON files
    if not any(len(v) for v in _search_cache.values()):
        _load_today_search_to_cache()
    if not any(len(v) for v in _hot_cache.values()):
        _load_hot_crawl_from_file()

    # Fallback 2: if caches are still empty after file restore, rebuild from latest daily_stats DB record
    if not any(len(v) for v in _hot_cache.values()) and not any(len(v) for v in _search_cache.values()):
        try:
            db = SessionLocal()
            latest = db.query(DailyStatsModel).order_by(DailyStatsModel.date.desc()).first()
            if latest and latest.total_topics > 0:
                # Rebuild hot_topics from DB
                topics = db.query(HotTopicModel).filter(
                    HotTopicModel.fetched_at >= datetime.utcnow() - timedelta(days=3)
                ).limit(300).all()
                if topics:
                    for t in topics:
                        p = t.platform or "other"
                        if p not in _hot_cache:
                            _hot_cache[p] = []
                        _hot_cache[p].append({
                            "id": t.id, "platform": t.platform, "title": t.title,
                            "rank": t.rank or 0, "heat": float(t.heat or 0),
                            "url": t.url or "", "fetched_at": (t.fetched_at or "").isoformat() if t.fetched_at else "",
                            "sentiment": t.sentiment or "Neutral",
                            "related_game": t.related_game, "is_game_related": bool(t.is_game_related),
                        })
                    print(f"[Dashboard] Fallback: rebuilt {_hot_cache} items ({sum(len(v) for v in _hot_cache.values())} total) from DB")
            db.close()
        except Exception as e:
            print(f"[Dashboard] DB fallback failed: {e}")

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
    seen = set()
    for p in platforms_to_use:
        items = cache.get(p, []) if source else _hot_cache.get(p, []) + _search_cache.get(p, [])
        for i in items:
            if i["id"] in seen:
                continue
            seen.add(i["id"])
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
    # Determine search state: idle / running / done / error
    if _search_running:
        search_status = "running"
    elif _search_error:
        search_status = "error"
    elif search_total > 0 or _search_time:
        search_status = "done"
    else:
        search_status = "idle"
    return {
        "hasData": (hot_total + search_total) > 0,
        "hotTotal": hot_total, "searchTotal": search_total,
        "byPlatform": {
            p: {"hot": len(_hot_cache.get(p, [])), "search": len(_search_cache.get(p, []))}
            for p in sorted(all_p)
        },
        "lastHotCrawl": _hot_time.isoformat() if _hot_time else None,
        "lastSearch": _search_time.isoformat() if _search_time else None,
        # Tophub-specific error state (separate from AICU)
        "searchError": _search_error,
        "searchErrorCode": _search_error_code,
        "searchStatus": search_status,
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


def _build_stats_from_json(date_str: str) -> Optional[dict]:
    """Build daily stats dict from the tophub_search JSON file for a given date (YYYYMMDD).

    If parsed_items lack sentiment/is_game_related fields (raw crawl data),
    backfill from the hot_topics DB table which may have analysed data.
    """
    data_dir = _get_search_data_dir()
    filepath = data_dir / f"{date_str}.json"
    if not filepath.exists():
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            jdata = json.load(f)
        items = jdata.get("parsed_items", [])
        if not items:
            return None

        # Backfill missing sentiment/is_game_related from hot_topics DB table
        missing_ids = [i.get("id") for i in items if not i.get("sentiment") or i.get("is_game_related") is None]
        if missing_ids:
            db = SessionLocal()
            try:
                db_rows = db.query(HotTopicModel).filter(HotTopicModel.id.in_(missing_ids)).all()
                db_map = {r.id: r for r in db_rows}
                for item in items:
                    rid = item.get("id")
                    if rid in db_map:
                        r = db_map[rid]
                        if not item.get("sentiment"):
                            item["sentiment"] = r.sentiment or "Neutral"
                        if item.get("is_game_related") is None:
                            item["is_game_related"] = r.is_game_related if r.is_game_related is not None else False
            finally:
                db.close()

        # Also backfill extra_items (hot_crawl.json) from DB later
        game_related = [i for i in items if i.get("is_game_related")]
        all_platforms = set(i.get("platform", "other") for i in items)
        by_platform = {}
        for p in all_platforms:
            pi = [i for i in items if i.get("platform") == p]
            by_platform[p] = {
                "total": len(pi),
                "positive": sum(1 for i in pi if i.get("sentiment") == "Positive"),
                "negative": sum(1 for i in pi if i.get("sentiment") == "Negative"),
                "neutral": sum(1 for i in pi if i.get("sentiment") == "Neutral"),
                "irrelevant": sum(1 for i in pi if i.get("sentiment") == "Irrelevant"),
            }
        # Also merge hot_crawl.json
        hot_file = data_dir / "hot_crawl.json"
        extra_items = []
        if hot_file.exists():
            try:
                with open(hot_file, "r", encoding="utf-8") as f:
                    hlist = json.load(f)
                extra_items = hlist if isinstance(hlist, list) else []
            except Exception:
                pass

        total = len(items) + len(extra_items)

        # Backfill missing fields in extra_items from DB
        extra_missing = [i.get("id") for i in extra_items if not i.get("sentiment") or i.get("is_game_related") is None]
        if extra_missing:
            db2 = SessionLocal()
            try:
                db_rows2 = db2.query(HotTopicModel).filter(HotTopicModel.id.in_(extra_missing)).all()
                db_map2 = {r.id: r for r in db_rows2}
                for item in extra_items:
                    rid = item.get("id")
                    if rid in db_map2:
                        r = db_map2[rid]
                        if not item.get("sentiment"):
                            item["sentiment"] = r.sentiment or "Neutral"
                        if item.get("is_game_related") is None:
                            item["is_game_related"] = r.is_game_related if r.is_game_related is not None else False
            finally:
                db2.close()

        extra_game = [i for i in extra_items if i.get("is_game_related")]
        all_items = items + extra_items

        for i in extra_items:
            p = i.get("platform", "other")
            if p not in by_platform:
                by_platform[p] = {"total": 0, "positive": 0, "negative": 0, "neutral": 0, "irrelevant": 0}
            by_platform[p]["total"] += 1
            s = i.get("sentiment", "")
            if s in by_platform[p]:
                by_platform[p][s] += 1

        all_game = game_related + extra_game
        return {
            "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
            "totalTopics": total,
            "gameRelated": len(all_game),
            "positive": sum(1 for i in all_game if i.get("sentiment") == "Positive"),
            "negative": sum(1 for i in all_game if i.get("sentiment") == "Negative"),
            "neutral": sum(1 for i in all_game if i.get("sentiment") == "Neutral"),
            "irrelevant": sum(1 for i in all_items if i.get("sentiment") == "Irrelevant"),
            "byPlatform": by_platform,
        }
    except Exception as e:
        print(f"[stats/daily] Error reading {filepath}: {e}")
        return None


def sync_daily_stats_from_json():
    """Scan all tophub_search/*.json files and upsert daily_stats into DB.
    Call this once at startup so that /api/stats/daily can be a fast DB-only query."""
    data_dir = _get_search_data_dir()
    if not data_dir.exists():
        print("[StatsSync] Data dir not found, skipping")
        return 0

    json_files = sorted(data_dir.glob("*.json"))
    # Exclude non-date files like hot_crawl.json (8-digit numeric names only)
    date_files = [f for f in json_files if f.stem.isdigit() and len(f.stem) == 8]

    db = SessionLocal()
    synced = 0
    try:
        for fpath in date_files:
            date_str = fpath.stem  # e.g. "20260602"
            stat = _build_stats_from_json(date_str)
            if not stat:
                continue
            date_iso = stat["date"]  # "2026-06-02"

            existing = db.query(DailyStatsModel).filter(DailyStatsModel.date == date_iso).first()
            if existing:
                # Update only if totals differ (avoid unnecessary writes)
                if existing.total_topics != stat["totalTopics"] or existing.game_related != stat["gameRelated"]:
                    existing.total_topics = stat["totalTopics"]
                    existing.game_related = stat["gameRelated"]
                    existing.positive = stat["positive"]
                    existing.negative = stat["negative"]
                    existing.neutral = stat["neutral"]
                    existing.irrelevant = stat["irrelevant"]
                    existing.by_platform = stat["byPlatform"]
                    synced += 1
            else:
                db.add(DailyStatsModel(
                    date=date_iso,
                    total_topics=stat["totalTopics"],
                    game_related=stat["gameRelated"],
                    positive=stat["positive"],
                    negative=stat["negative"],
                    neutral=stat["neutral"],
                    irrelevant=stat["irrelevant"],
                    by_platform=stat["byPlatform"],
                ))
                synced += 1
        db.commit()
    except Exception as e:
        print(f"[StatsSync] Error: {e}")
        db.rollback()
    finally:
        db.close()

    print(f"[StatsSync] Synced {synced} days from {len(date_files)} JSON files")
    return synced


def sync_hot_topics_from_json():
    """Scan all tophub_search/*.json files (hot_crawl.json + YYYYMMDD.json) and 
    upsert every item into hot_topics table. Call once at startup."""
    data_dir = _get_search_data_dir()
    if not data_dir.exists():
        print("[TopicSync] Data dir not found, skipping")
        return 0
    
    db = SessionLocal()
    imported = 0
    skipped = 0
    try:
        json_files = sorted(data_dir.glob("*.json"))
        
        for fpath in json_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"[TopicSync] Skip {fpath.name}: {e}")
                continue
            
            # Extract items based on file format
            if isinstance(data, list):
                items = data  # hot_crawl.json is a flat array
            elif isinstance(data, dict) and "parsed_items" in data:
                items = data["parsed_items"]  # YYYYMMDD.json has parsed_items
            else:
                continue
            
            for item in items:
                item_id = item.get("id")
                if not item_id:
                    continue
                existing = db.query(HotTopicModel).filter(HotTopicModel.id == item_id).first()
                if existing:
                    skipped += 1
                    continue
                # Parse fetched_at
                fa_str = item.get("fetched_at", "")
                fetched_at = datetime.utcnow()
                if fa_str:
                    try:
                        fetched_at = datetime.fromisoformat(fa_str)
                    except Exception:
                        pass
                db.add(HotTopicModel(
                    id=item_id,
                    platform=item.get("platform", "other"),
                    title=item.get("title", ""),
                    rank=item.get("rank", 0),
                    heat=item.get("heat", 0),
                    url=item.get("url", ""),
                    fetched_at=fetched_at,
                    sentiment=item.get("sentiment", "Neutral"),
                    related_game=item.get("related_game"),
                    is_game_related=item.get("is_game_related", False),
                ))
                imported += 1
            
            # Commit per-file to avoid massive transactions
            db.commit()
        
    except Exception as e:
        print(f"[TopicSync] Error: {e}")
        db.rollback()
    finally:
        db.close()
    
    print(f"[TopicSync] Imported {imported} topics, skipped {skipped} duplicates from JSON files")
    return imported


@router.get("/stats/daily")
async def get_daily_stats(range: str = "7d", start: Optional[str] = None, end: Optional[str] = None):
    """Return daily stats from DB (populated at startup from JSON files)."""
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
        defaults = {"categories": {
            "mihoyo_game": {"name": "米哈游游戏", "order": 1},
            "mihoyo_character": {"name": "米哈游角色", "order": 2},
            "mihoyo_cv": {"name": "米哈游CV", "order": 3},
            "competitor": {"name": "竞品游戏", "order": 4},
            "general": {"name": "二游圈通用", "order": 5},
            "sentiment_neg": {"name": "负面情感词", "order": 6},
            "sentiment_pos": {"name": "正面情感词", "order": 7},
            "platform": {"name": "社区/平台术语", "order": 8},
            "game_mechanic": {"name": "游戏系统/机制", "order": 9},
            "player_group": {"name": "玩家群体/称呼", "order": 10},
            "meme": {"name": "热梗/网络用语", "order": 11},
            "industry": {"name": "行业/商业术语", "order": 12},
            "acg": {"name": "二次元/ACG文化", "order": 13},
            "bili_slang": {"name": "B站/视频圈用语", "order": 14},
        }}
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
        from app.bilibili import fetch_user_video_comments, fetch_user_content, filter_comments_by_keywords, analyze_user_personality, get_user_info
        print(f"[BiliAnalyze] Fetching user info...")
        user_info = loop.run_until_complete(get_user_info(uid))
        print(f"[BiliAnalyze] User: {user_info.get('name')}")
        print(f"[BiliAnalyze] Fetching comments...")
        all_comments = loop.run_until_complete(
            fetch_user_video_comments(uid, max_videos=max_videos,
                                       max_comments_per_video=max_comments,
                                       months_limit=months_limit)
        )
        print(f"[BiliAnalyze] Fetching video/articles...")
        user_content = loop.run_until_complete(fetch_user_content(uid))
        loop.close()
        print(f"[BiliAnalyze] Got {len(all_comments)} comments, {len(user_content)} content items")

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
            spectrum = loop2.run_until_complete(analyze_user_personality(all_comments, matched_comments, ds_key, user_content))
            loop2.close()
            print(f"[BiliAnalyze] DeepSeek result: score={spectrum.get('score')}, summary={spectrum.get('summary')}")
        elif ds_key and not all_comments:
            spectrum = {
                "score": 50, "score_x": 50, "score_y": 50,
                "mihoyo_attitude": "该用户无历史评论记录", "active_areas": "未知",
                "personality": "无法分析", "summary": "无评论数据"
            }
        else:
            spectrum = {
                "score": 50, "score_x": 50, "score_y": 50,
                "mihoyo_attitude": "未配置DeepSeek API Key", "active_areas": "未知",
                "personality": "无法分析", "summary": "请先配置API Key"
            }

        result = {
            "status": "done",
            "uid": uid,
            "user_info": user_info,
            "total_comments": len(all_comments),
            "matched_count": len(matched_comments),
            "all_comments": all_comments,
            "comments": matched_comments,
            "user_content": user_content,
            "content_count": len(user_content),
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
        "user_content": result.get("user_content", []),
        "content_count": result.get("content_count", 0),
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "spectrum": result.get("spectrum"),
        "analyzed_at": result.get("analyzed_at"),
    }


@router.post("/bilibili/analyze")
async def trigger_bili_analyze(body: dict):
    """Trigger Bilibili user comment analysis."""
    import sys
    print(f"[API] /bilibili/analyze POST received: {body}", flush=True)
    sys.stdout.flush()
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


# ==================== Bilibili Profile Persistence ====================

@router.post("/bilibili/save")
async def save_bili_profile(body: dict):
    """Save a B站 user's analysis result to SQLite for 2D spectrum display."""
    uid = body.get("uid")
    if not uid:
        raise HTTPException(status_code=400, detail="请提供UID")
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="UID必须是数字")

    with _bili_analysis_lock:
        cached = _bili_analysis_cache.get(str(uid))
    if not cached or cached.get("status") != "done":
        raise HTTPException(status_code=400, detail="该用户尚未完成分析，请先执行查成分")

    spectrum = cached.get("spectrum", {})
    user_info = cached.get("user_info", {})
    all_comments = cached.get("all_comments", [])
    user_content = cached.get("user_content", [])

    # Build lightweight comment storage (strip heavy fields)
    comments_save = []
    for c in all_comments[:2000]:  # max 2000 comments
        comments_save.append({
            "rpid": c.get("rpid", ""),
            "content": c.get("content", ""),
            "ctime": c.get("ctime", 0),
            "time_str": c.get("time_str", ""),
            "matched_keywords": c.get("matched_keywords", []),
            "matched_categories": c.get("matched_categories", []),
        })

    # Build lightweight content storage
    content_save = []
    for c in user_content:
        content_save.append({
            "type": c.get("type", ""),
            "id": c.get("id", ""),
            "title": c.get("title", ""),
            "bvid": c.get("bvid", ""),
            "url": c.get("url", ""),
            "time_str": c.get("time_str", ""),
            "play": c.get("play", 0),
            "duration": c.get("duration", 0),
            "cover": c.get("cover", ""),
        })

    db = SessionLocal()
    try:
        existing = db.query(BiliUserProfile).filter(BiliUserProfile.uid == uid).first()
        if existing:
            existing.name = user_info.get("name", "")
            existing.face = user_info.get("face", "")
            existing.score_x = spectrum.get("score_x", 50)
            existing.score_y = spectrum.get("score_y", 50)
            existing.mihoyo_attitude = spectrum.get("mihoyo_attitude", "")
            existing.active_areas = spectrum.get("active_areas", "")
            existing.personality = spectrum.get("personality", "")
            existing.summary = spectrum.get("summary", "")
            existing.comments_json = comments_save
            existing.content_json = content_save
            existing.saved_at = datetime.utcnow()
        else:
            db.add(BiliUserProfile(
                uid=uid,
                name=user_info.get("name", ""),
                face=user_info.get("face", ""),
                score_x=spectrum.get("score_x", 50),
                score_y=spectrum.get("score_y", 50),
                mihoyo_attitude=spectrum.get("mihoyo_attitude", ""),
                active_areas=spectrum.get("active_areas", ""),
                personality=spectrum.get("personality", ""),
                summary=spectrum.get("summary", ""),
                comments_json=comments_save,
                content_json=content_save,
            ))
        db.commit()
        print(f"[Save] Profile saved: uid={uid}, name={user_info.get('name')}, X={spectrum.get('score_x')}, Y={spectrum.get('score_y')}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

    return {"ok": True, "message": f"用户 {user_info.get('name', uid)} 的数据已存储", "uid": uid}


@router.get("/bilibili/profiles")
async def get_bili_profiles():
    """Get all saved B站 user profiles for 2D spectrum display."""
    db = SessionLocal()
    try:
        profiles = db.query(BiliUserProfile).order_by(BiliUserProfile.saved_at.desc()).all()
        return {
            "ok": True,
            "profiles": [{
                "uid": p.uid,
                "name": p.name,
                "face": p.face,
                "score_x": p.score_x,
                "score_y": p.score_y,
                "summary": p.summary or "",
                "saved_at": p.saved_at.isoformat() if p.saved_at else "",
            } for p in profiles],
        }
    finally:
        db.close()


@router.get("/bilibili/profile/{uid}")
async def get_bili_profile(uid: int, tab: str = "comments", page: int = 1):
    """Get a saved profile with paginated comments or content."""
    db = SessionLocal()
    try:
        p = db.query(BiliUserProfile).filter(BiliUserProfile.uid == uid).first()
        if not p:
            raise HTTPException(status_code=404, detail="该用户未存储")
        result = {
            "ok": True,
            "uid": p.uid,
            "name": p.name,
            "face": p.face,
            "score_x": p.score_x,
            "score_y": p.score_y,
            "mihoyo_attitude": p.mihoyo_attitude or "",
            "active_areas": p.active_areas or "",
            "personality": p.personality or "",
            "summary": p.summary or "",
        }
        if tab == "content":
            items = (p.content_json or [])
            page_size = 30
            total = len(items)
            start = (page - 1) * page_size
            result["items"] = items[start:start + page_size]
            result["total"] = total
            result["page"] = page
            result["page_size"] = page_size
            result["total_pages"] = max(1, (total + page_size - 1) // page_size)
        else:
            items = (p.comments_json or [])
            page_size = 100
            total = len(items)
            start = (page - 1) * page_size
            result["items"] = items[start:start + page_size]
            result["total"] = total
            result["page"] = page
            result["page_size"] = page_size
            result["total_pages"] = max(1, (total + page_size - 1) // page_size)
        return result
    finally:
        db.close()


@router.delete("/bilibili/profile/{uid}")
async def delete_bili_profile(uid: int):
    """Delete a saved profile."""
    db = SessionLocal()
    try:
        p = db.query(BiliUserProfile).filter(BiliUserProfile.uid == uid).first()
        if p:
            db.delete(p)
            db.commit()
            return {"ok": True, "message": "已删除"}
        return {"ok": False, "message": "未找到该用户"}
    finally:
        db.close()


# ==================== Bilibili Profile Export/Import ====================

@router.get("/bilibili/export")
async def export_bili_profiles():
    """Export all saved B站 profiles as downloadable JSON."""
    db = SessionLocal()
    try:
        profiles = db.query(BiliUserProfile).all()
        data = {
            "version": "1.1",
            "exported_at": datetime.utcnow().isoformat(),
            "profiles": []
        }
        for p in profiles:
            data["profiles"].append({
                "uid": p.uid, "name": p.name, "face": p.face,
                "score_x": p.score_x, "score_y": p.score_y,
                "mihoyo_attitude": p.mihoyo_attitude or "",
                "active_areas": p.active_areas or "",
                "personality": p.personality or "",
                "summary": p.summary or "",
                "comments_json": p.comments_json or [],
                "content_json": p.content_json or [],
                "saved_at": p.saved_at.isoformat() if p.saved_at else "",
            })
        json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        return Response(content=json_str, media_type="application/json",
                       headers={"Content-Disposition": "attachment; filename=miho_profiles.json"})
    finally:
        db.close()


@router.post("/bilibili/import")
async def import_bili_profiles(body: dict):
    """Import B站 profiles from JSON. Modes: 'merge' (add new) or 'replace' (clear first)."""
    mode = body.get("mode", "merge")
    profiles = body.get("profiles", [])
    if not profiles:
        raise HTTPException(status_code=400, detail="profiles array is required")

    db = SessionLocal()
    imported = 0
    updated = 0
    try:
        if mode == "replace":
            db.query(BiliUserProfile).delete()
        for p in profiles:
            uid = p.get("uid")
            if not uid:
                continue
            existing = db.query(BiliUserProfile).filter(BiliUserProfile.uid == uid).first()
            if existing:
                existing.name = p.get("name", existing.name)
                existing.face = p.get("face", existing.face)
                existing.score_x = p.get("score_x", existing.score_x)
                existing.score_y = p.get("score_y", existing.score_y)
                existing.mihoyo_attitude = p.get("mihoyo_attitude", existing.mihoyo_attitude)
                existing.active_areas = p.get("active_areas", existing.active_areas)
                existing.personality = p.get("personality", existing.personality)
                existing.summary = p.get("summary", existing.summary)
                existing.comments_json = p.get("comments_json", existing.comments_json)
                existing.content_json = p.get("content_json", existing.content_json)
                existing.saved_at = datetime.utcnow()
                updated += 1
            else:
                db.add(BiliUserProfile(
                    uid=uid, name=p.get("name", ""), face=p.get("face", ""),
                    score_x=p.get("score_x", 50), score_y=p.get("score_y", 50),
                    mihoyo_attitude=p.get("mihoyo_attitude", ""),
                    active_areas=p.get("active_areas", ""),
                    personality=p.get("personality", ""),
                    summary=p.get("summary", ""),
                    comments_json=p.get("comments_json", []),
                    content_json=p.get("content_json", []),
                ))
                imported += 1
        db.commit()
        total = db.query(BiliUserProfile).count()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

    return {"ok": True, "imported": imported, "updated": updated, "total": total,
            "message": f"导入完成：新增 {imported}，更新 {updated}，共 {total} 个用户"}


# ==================== Video Comment Analysis ====================

import uuid as _uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

_va_state: dict = {"task_id": None, "status": "idle", "progress": ""}  # simple state for polling

def _parse_bilibili_url(url: str) -> tuple:
    """Extract BVID from Bilibili URL. Returns (bvid, error_msg)."""
    url = url.strip()
    # Direct BV id
    if url.startswith("BV") and len(url) >= 10:
        return url, ""
    # URL patterns
    import re
    m = re.search(r'BV[a-zA-Z0-9]+', url)
    if m:
        return m.group(0), ""
    return "", f"无法从URL中提取BV号: {url}"


def _bili_get_aid(bvid: str) -> tuple:
    """Convert BVID to AID via Bilibili API. Returns (aid, title, cover, error)."""
    import httpx
    try:
        resp = httpx.get(
            f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"},
            timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            return 0, "", "", f"API错误: {data.get('message', 'unknown')}"
        d = data["data"]
        return d["aid"], d.get("title", ""), d.get("pic", ""), ""
    except Exception as e:
        return 0, "", "", str(e)


def _bili_fetch_comments(aid: int, mode: int = 3, max_count: int = 500) -> list:
    """Fetch comments from Bilibili reply API.
    mode=3: hot sort, mode=2: time sort.
    Returns list of comment dicts including sub-replies."""
    import httpx
    import time as _time

    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"}
    all_items = []
    cursor = 0
    page = 0

    while len(all_items) < max_count:
        page += 1
        try:
            resp = httpx.get(
                "https://api.bilibili.com/x/v2/reply/main",
                params={"type": 1, "oid": aid, "mode": mode, "next": cursor, "ps": 20},
                headers=headers, timeout=15,
            )
            d = resp.json()
        except Exception as e:
            print(f"[Video-Fetch] Page {page} error: {e}")
            break
        if d.get("code") != 0:
            print(f"[Video-Fetch] Page {page} API error: {d.get('message')}")
            break

        replies = d.get("data", {}).get("replies", [])
        cur = d.get("data", {}).get("cursor", {})
        is_end = cur.get("is_end", False)
        cursor = cur.get("next", 0)

        for r in replies:
            if len(all_items) >= max_count:
                break
            m = r.get("member", {})
            content_obj = r.get("content", {})
            message = content_obj.get("message", "")
            item = {
                "rpid": r["rpid"], "parent_rpid": 0, "root_rpid": 0,
                "uid": m.get("mid", 0), "user": m.get("uname", ""),
                "content": message[:500], "like_count": r.get("like", 0),
                "reply_count": r.get("rcount", 0),
                "ctime": r.get("ctime", 0),
                "sort_mode": "hot" if mode == 3 else "time",
                "matched_keywords": [],
            }
            all_items.append(item)

            # Fetch sub-replies for this main comment if any
            rcount = r.get("rcount", 0)
            if rcount > 0:
                sub_replies = _bili_fetch_sub_replies(aid, r["rpid"], max_count - len(all_items))
                all_items.extend(sub_replies)

        if is_end or not cursor:
            break
        _time.sleep(0.4)

    return all_items


def _bili_fetch_sub_replies(aid: int, root_rpid: int, remaining: int) -> list:
    """Fetch sub-replies for a given root comment."""
    import httpx
    import time as _time

    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"}
    subs = []
    pn = 1
    ps = 20  # sub-replies per page

    while True:
        try:
            resp = httpx.get(
                "https://api.bilibili.com/x/v2/reply/reply",
                params={"type": 1, "oid": aid, "root": root_rpid, "pn": pn, "ps": ps},
                headers=headers, timeout=15,
            )
            d = resp.json()
        except Exception as e:
            print(f"[Video-Sub] Error fetching subs for root {root_rpid}: {e}")
            break
        if d.get("code") != 0:
            break

        replies = d.get("data", {}).get("replies", [])
        for r in replies:
            if len(subs) >= remaining:
                return subs
            m = r.get("member", {})
            content_obj = r.get("content", {})
            message = content_obj.get("message", "")
            subs.append({
                "rpid": r["rpid"], "parent_rpid": r.get("parent", 0), "root_rpid": root_rpid,
                "uid": m.get("mid", 0), "user": m.get("uname", ""),
                "content": message[:500], "like_count": r.get("like", 0),
                "reply_count": 0, "ctime": r.get("ctime", 0),
                "sort_mode": "hot",
                "matched_keywords": [],
            })

        total = d.get("data", {}).get("page", {}).get("count", 0)
        if pn * ps >= total or not replies:
            break
        pn += 1
        _time.sleep(0.3)

    return subs


def _match_keywords_for_comment(content: str, keywords_dict: dict) -> list:
    """Match comment against keyword dictionary. Returns list of matched keywords."""
    if not content or not keywords_dict:
        return []
    matched = []
    lower_content = content.lower()
    for kw in keywords_dict:
        if kw.lower() in lower_content:
            matched.append(kw)
    return matched


def _deepseek_score_comment(content: str, api_key: str) -> tuple:
    """Ask DeepSeek to score a comment on X,Y coordinates.
    Returns (X, Y) or (-1, -1) on failure.
    X: 0=anti-mihoyo, 100=pro-mihoyo
    Y: 0=rational, 100=emotional"""
    import httpx
    prompt = f"""你是一个专业的舆情分析AI。请分析以下B站评论的情感坐标。

坐标定义：
- X轴（横轴，0-100）：0代表极度反对米哈游，50代表中立，100代表极度支持米哈游
- Y轴（纵轴，0-100）：0代表极度理性客观，50代表中性，100代表极度感性情绪化

规则：
1. 只根据评论内容判断，不要过度解读
2. 考虑用词、语气、表情符号、标点符号的使用
3. 支持米哈游的正面评价 → X偏高（60-100）
4. 反对/批评米哈游 → X偏低（0-40）
5. 理性分析、讲道理、摆数据 → Y偏低（0-40）
6. 感性表达、情绪宣泄、玩梗 → Y偏高（60-100）

评论内容：
{content[:400]}

请只返回JSON格式：{{"X":数字,"Y":数字}}
不要返回任何其他文字。"""

    try:
        resp = httpx.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 30,
            },
            timeout=25,
        )
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        # Try parse JSON from response
        import re
        json_match = re.search(r'\{[^{}]*"X"\s*:\s*\d+[^{}]*"Y"\s*:\s*\d+[^{}]*\}', text)
        if json_match:
            coords = eval(json_match.group(0))  # safe enough for numeric JSON
            x = max(0, min(100, int(coords.get("X", 50))))
            y = max(0, min(100, int(coords.get("Y", 50))))
            return x, y

        # Fallback: look for two numbers
        nums = re.findall(r'\d+', text)
        if len(nums) >= 2:
            x = max(0, min(100, int(nums[0])))
            y = max(0, min(100, int(nums[1])))
            return x, y

        return -1, -1
    except Exception as e:
        print(f"[Video-DS] Score error: {e}")
        return -1, -1


@router.get("/video-analysis/tasks")
async def va_list_tasks():
    """List all video analysis tasks."""
    db = SessionLocal()
    try:
        tasks = db.query(VideoAnalysisTask).order_by(VideoAnalysisTask.created_at.desc()).all()
        return [{
            "id": t.id, "bvid": t.bvid, "title": t.title, "status": t.status,
            "totalComments": t.total_comments, "matchedCount": t.matched_count,
            "analyzedCount": t.analyzed_count,
            "centroidX": t.centroid_x, "centroidY": t.centroid_y,
            "errorMsg": t.error_msg, "coverUrl": t.cover_url,
            "createdAt": t.created_at.isoformat() if t.created_at else "",
            "updatedAt": t.updated_at.isoformat() if t.updated_at else "",
        } for t in tasks]
    finally:
        db.close()


@router.post("/video-analysis/fetch")
async def va_fetch_comments(body: dict):
    """Trigger video comment fetch for a Bilibili URL."""
    global _va_state

    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="请提供B站视频链接")

    bvid, err = _parse_bilibili_url(url)
    if err:
        raise HTTPException(status_code=400, detail=err)

    # Check if already running
    if _va_state.get("status") in ("fetching", "analyzing"):
        return {"ok": False, "message": "已有任务正在运行，请等待完成"}

    # Get video info first
    aid, title, cover, info_err = _bili_get_aid(bvid)
    if info_err:
        return {"ok": False, "message": f"获取视频信息失败: {info_err}"}

    # Create task record
    task_id = str(_uuid.uuid4())[:12]
    db = SessionLocal()
    try:
        task = VideoAnalysisTask(
            id=task_id, bvid=bvid, aid=aid, title=title, cover_url=cover,
            status="fetching",
        )
        db.add(task)
        db.commit()
    finally:
        db.close()

    # Start background thread
    _va_state = {"task_id": task_id, "status": "fetching", "progress": "正在拉取热度排序评论..."}
    threading.Thread(target=_va_run_fetch, args=(task_id, bvid, aid), daemon=True).start()

    return {
        "ok": True, "taskId": task_id, "bvid": bvid, "title": title,
        "message": f"开始拉取《{title}》的评论...",
    }


def _va_run_fetch(task_id: str, bvid: str, aid: int):
    """Background: fetch comments (hot + time, each up to 500 + sub-replies)."""
    global _va_state
    db = SessionLocal()
    try:
        _va_state["progress"] = "正在拉取热度排序评论..."
        hot_comments = _bili_fetch_comments(aid, mode=3, max_count=1000)
        print(f"[VA-Fetch] Hot sort: {len(hot_comments)} items")
        _va_state["progress"] = f"已获取{len(hot_comments)}条热度评论，正在拉取时间排序..."

        time_comments = _bili_fetch_comments(aid, mode=2, max_count=1000)
        print(f"[VA-Fetch] Time sort: {len(time_comments)} items")
        _va_state["progress"] = f"已获取{len(time_comments)}条时间评论，正在保存..."

        all_comments = hot_comments + time_comments

        # Keyword matching
        from app.sentiment import _load_keywords
        kw_dict = _load_keywords()
        matched_total = 0
        for c in all_comments:
            c["matched_keywords"] = _match_keywords_for_comment(c.get("content", ""), kw_dict)
            if c["matched_keywords"]:
                matched_total += 1

        # Save to DB (dedup by rpid — same comment may appear in both hot & time)
        saved = 0
        seen_rpids = set()
        for c in all_comments:
            if c["rpid"] in seen_rpids:
                continue
            seen_rpids.add(c["rpid"])
            cid = f"{task_id}_{c['rpid']}"
            vc = VideoComment(
                id=cid, task_id=task_id,
                rpid=c["rpid"], parent_rpid=c["parent_rpid"], root_rpid=c["root_rpid"],
                uid=c["uid"], user=c["user"][:50], content=c["content"],
                like_count=c["like_count"], reply_count=c["reply_count"],
                ctime=c["ctime"], sort_mode=c["sort_mode"],
                matched_keywords=c["matched_keywords"],
            )
            db.add(vc)
            saved += 1

        # Update task
        task = db.query(VideoAnalysisTask).filter(VideoAnalysisTask.id == task_id).first()
        if task:
            task.status = "fetched"
            task.total_comments = saved
            task.matched_count = matched_total
            task.updated_at = datetime.utcnow()
        db.commit()

        _va_state = {"task_id": task_id, "status": "fetched", "progress": f"完成! 共{saved}条评论, {matched_total}条匹配关键词"}
        print(f"[VA-Fetch] Done: {saved} comments, {matched_total} matched keywords")

    except Exception as e:
        print(f"[VA-Fetch] ERROR: {e}")
        import traceback as _tb; _tb.print_exc()
        task = db.query(VideoAnalysisTask).filter(VideoAnalysisTask.id == task_id).first()
        if task:
            task.status = "error"
            task.error_msg = str(e)[:300]
            task.updated_at = datetime.utcnow()
            db.commit()
        _va_state = {"task_id": task_id, "status": "error", "progress": f"错误: {str(e)[:100]}"}
    finally:
        db.close()


@router.get("/video-analysis/status")
async def va_status():
    """Get current video analysis status."""
    return _va_state


@router.post("/video-analysis/analyze")
async def va_analyze(body: dict = None):
    """Trigger DeepSeek coordinate analysis for fetched comments."""
    global _va_state
    task_id = (body or {}).get("taskId") or _va_state.get("task_id")

    if not task_id:
        raise HTTPException(status_code=400, detail="没有可分析的任务")

    api_key = _get_deepseek_key()
    if not api_key:
        return {"ok": False, "message": "请先在账号管理页面配置 DeepSeek API Key"}

    # Check task exists and has comments
    db = SessionLocal()
    try:
        task = db.query(VideoAnalysisTask).filter(VideoAnalysisTask.id == task_id).first()
        if not task:
            return {"ok": False, "message": "任务不存在"}
        if task.status not in ("fetched", "done"):
            return {"ok": False, "message": f"当前任务状态为 '{task.status}'，需要先完成评论拉取"}
        if task.status == "done":
            return {"ok": False, "message": "该任务已经分析完成"}

        matched_comments = db.query(VideoComment).filter(
            VideoComment.task_id == task_id,
            VideoComment.coord_x == -1,
        ).filter(VideoComment.matched_keywords != []).all()

        if not matched_comments:
            # No unmatched matched-comments → mark as done directly
            task.status = "done"
            task.analyzed_count = db.query(VideoComment).filter(
                VideoComment.task_id == task_id, VideoComment.coord_x >= 0
            ).count()
            db.commit()
            _calc_centroid(task_id, db)
            return {"ok": True, "message": "没有新的待分析评论（可能已全部分析或无匹配）"}
    finally:
        db.close()

    task.status = "analyzing"
    db.commit()
    _va_state = {"task_id": task_id, "status": "analyzing", "progress": f"正在调用 DeepSeek 分析 {len(matched_comments)} 条匹配评论..."}

    threading.Thread(target=_va_run_analyze, args=(task_id, len(matched_comments)), daemon=True).start()

    return {
        "ok": True, "taskId": task_id,
        "message": f"正在使用 DeepSeek 分析 {len(matched_comments)} 条匹配评论...",
        "pendingCount": len(matched_comments),
    }


def _va_run_analyze(task_id: str, pending_count: int):
    """Background: run DeepSeek coordinate analysis with concurrency=100."""
    global _va_state
    import time as _time
    api_key = _get_deepseek_key()
    db = SessionLocal()

    try:
        comments = db.query(VideoComment).filter(
            VideoComment.task_id == task_id,
            VideoComment.coord_x == -1,
        ).filter(VideoComment.matched_keywords != None).all()

        analyzed = 0
        failed = 0

        def analyze_one(vc):
            x, y = _deepseek_score_comment(vc.content, api_key)
            return vc.id, x, y

        executor = ThreadPoolExecutor(max_workers=100)
        futures = {executor.submit(analyze_one, vc): vc for vc in comments}

        # Collect ALL results first — no DB writes inside the thread loop to avoid session sharing issues
        results: list[tuple[str, int, int]] = []  # [(cid, x, y), ...]
        done_count = 0
        total = len(comments)
        for future in as_completed(futures):
            try:
                cid, x, y = future.result(timeout=30)
                results.append((cid, x, y))
                if x >= 0:
                    analyzed += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                print(f"[VA-Analyze] Future error: {e}")

            done_count += 1
            if done_count % 20 == 0 or done_count == total:
                _va_state["progress"] = f"分析进度: {done_count}/{total} (成功{analyzed}, 失败{failed})"

        executor.shutdown(wait=False)

        # Bulk write all results in a single transaction (fresh session to avoid stale state)
        write_db = SessionLocal()
        try:
            for cid, x, y in results:
                vc = write_db.query(VideoComment).filter(VideoComment.id == cid).first()
                if vc:
                    vc.coord_x = x
                    vc.coord_y = y
            write_db.commit()
        except Exception as e:
            print(f"[VA-Analyze] Batch write error: {e}")
            write_db.rollback()
            raise
        finally:
            write_db.close()

        # Update task status
        task = db.query(VideoAnalysisTask).filter(VideoAnalysisTask.id == task_id).first()
        if task:
            task.status = "done"
            task.analyzed_count = db.query(VideoComment).filter(
                VideoComment.task_id == task_id, VideoComment.coord_x >= 0
            ).count()
            task.updated_at = datetime.utcnow()
            db.commit()

            # Calculate centroid
            _calc_centroid(task_id, db)

        _va_state = {
            "task_id": task_id, "status": "done",
            "progress": f"分析完成! 成功{analyzed}, 失败{failed}",
        }
        print(f"[VA-Analyze] Done: analyzed={analyzed}, failed={failed}")

    except Exception as e:
        print(f"[VA-Analyze] ERROR: {e}")
        import traceback as _tb; _tb.print_exc()
        task = db.query(VideoAnalysisTask).filter(VideoAnalysisTask.id == task_id).first()
        if task:
            task.status = "error"
            task.error_msg = str(e)[:300]
            db.commit()
        _va_state = {"task_id": task_id, "status": "error", "progress": f"错误: {str(e)[:100]}"}
    finally:
        db.close()


def _calc_centroid(task_id: str, db):
    """Calculate weighted centroid (a,b) where weight Z = count of identical (x,y) coordinates.
    Computes TWO centroids:
      1. all-points centroid (including neutral center)
      2. no-neutral centroid (excluding x=50,y=50 to avoid skew from neutral/unopinionated comments)
    Formula: a = Σ(x_i * z_i) / Σ(z_i), b = Σ(y_i * z_i) / Σ(z_i)"""
    comments = db.query(VideoComment).filter(
        VideoComment.task_id == task_id,
        VideoComment.coord_x >= 0,
        VideoComment.coord_y >= 0,
    ).all()

    if not comments:
        return

    # Separate into all-points and no-neutral sets
    coord_counts_all: dict[tuple[int, int], int] = {}
    coord_counts_no_neutral: dict[tuple[int, int], int] = {}
    for c in comments:
        key = (c.coord_x, c.coord_y)
        coord_counts_all[key] = coord_counts_all.get(key, 0) + 1
        if key != (50, 50):
            coord_counts_no_neutral[key] = coord_counts_no_neutral.get(key, 0) + 1

    if not coord_counts_all:
        return

    def _compute_centroid(cc: dict[tuple[int, int], int]) -> tuple[float, float]:
        total_weight = sum(cc.values())
        weighted_sum_x = sum(x * z for (x, _y), z in cc.items())
        weighted_sum_y = sum(y * z for (_x, y), z in cc.items())
        cx = weighted_sum_x / total_weight if total_weight > 0 else 50.0
        cy = weighted_sum_y / total_weight if total_weight > 0 else 50.0
        return round(cx, 2), round(cy, 2)

    centroid_x, centroid_y = _compute_centroid(coord_counts_all)

    # No-neutral centroid — fall back to all-point centroid if all points are at center
    if coord_counts_no_neutral:
        centroid_x_no, centroid_y_no = _compute_centroid(coord_counts_no_neutral)
    else:
        centroid_x_no, centroid_y_no = centroid_x, centroid_y

    task = db.query(VideoAnalysisTask).filter(VideoAnalysisTask.id == task_id).first()
    if task:
        task.centroid_x = centroid_x
        task.centroid_y = centroid_y
        task.centroid_x_no_origin = centroid_x_no
        task.centroid_y_no_origin = centroid_y_no
        db.commit()
    print(f"[VA-Centroid] ALL=({centroid_x:.2f},{centroid_y:.2f}) NO_NEUTRAL=({centroid_x_no:.2f},{centroid_y_no:.2f}) "
          f"from {len(comments)} pts, neutral_center_count={coord_counts_all.get((50, 50), 0)}, "
          f"unique={len(coord_counts_all)}, no_neutral_unique={len(coord_counts_no_neutral)}")


@router.get("/video-analysis/result/{task_id}")
async def va_result(task_id: str):
    """Get heatmap grid data and centroid for a completed task."""
    db = SessionLocal()
    try:
        task = db.query(VideoAnalysisTask).filter(VideoAnalysisTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        comments = db.query(VideoComment).filter(
            VideoComment.task_id == task_id,
            VideoComment.coord_x >= 0,
            VideoComment.coord_y >= 0,
        ).all()

        # Build heatmap grid: key=(x,y) → z(count)
        heatmap_grid: dict[str, list] = {}  # {"x,y": [count, sample_contents]}
        for c in comments:
            key = f"{c.coord_x},{c.coord_y}"
            if key not in heatmap_grid:
                heatmap_grid[key] = [0, []]
            heatmap_grid[key][0] += 1
            if len(heatmap_grid[key][1]) < 3:  # keep up to 3 sample contents per cell
                heatmap_grid[key][1].append(c.content[:80])

        # Convert to array format for frontend
        points = []
        for k, v in heatmap_grid.items():
            xy = k.split(",")
            points.append({
                "x": int(xy[0]), "y": int(xy[1]),
                "z": v[0],  # height = frequency
                "samples": v[1],
            })

        return {
            "task": {
                "id": task.id, "bvid": task.bvid, "title": task.title,
                "status": task.status,
                "totalComments": task.total_comments,
                "matchedCount": task.matched_count,
                "analyzedCount": task.analyzed_count,
                "centroidX": task.centroid_x,
                "centroidY": task.centroid_y,
                "centroidXNoNeutral": task.centroid_x_no_origin,
                "centroidYNoNeutral": task.centroid_y_no_origin,
                "coverUrl": task.cover_url,
            },
            "points": points,
            "totalPoints": len(points),
            "totalAnalyzedComments": len(comments),
            "neutralCenterCount": heatmap_grid.get("50,50", [0])[0],
        }
    finally:
        db.close()


@router.delete("/video-analysis/task/{task_id}")
async def va_delete_task(task_id: str):
    """Delete a video analysis task and all its comments."""
    global _va_state
    db = SessionLocal()
    try:
        task = db.query(VideoAnalysisTask).filter(VideoAnalysisTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # Delete all comments for this task
        db.query(VideoComment).filter(VideoComment.task_id == task_id).delete()
        db.delete(task)
        db.commit()

        if _va_state.get("task_id") == task_id:
            _va_state = {"task_id": None, "status": "idle", "progress": ""}

        return {"ok": True, "message": "已删除"}
    finally:
        db.close()


# Helpers
def _t(t): return {"id":t.id,"platform":t.platform,"title":t.title,"rank":t.rank,"heat":t.heat,"url":t.url or "","fetchedAt":t.fetched_at.isoformat() if t.fetched_at else "","sentiment":t.sentiment,"relatedGame":t.related_game,"isGameRelated":t.is_game_related}
def _p(p): return {"id":p.id,"topicId":p.topic_id,"platform":p.platform,"content":p.content,"author":p.author or "","likes":p.likes or 0,"comments":p.comments or 0,"timestamp":p.timestamp.isoformat() if t.timestamp else "","sentiment":p.sentiment,"url":p.url or ""}
def _s(s): return {"date":s.date,"totalTopics":s.total_topics,"gameRelated":s.game_related,"positive":s.positive,"negative":s.negative,"neutral":s.neutral,"irrelevant":s.irrelevant,"byPlatform":s.by_platform or {}}
def _k(k): return {"id":k.id,"keyword":k.keyword,"category":k.category,"addedAt":k.added_at.isoformat() if k.added_at else "","addedBy":k.added_by}
def _a(a): return {"platform":a.platform,"username":a.username or "","cookie":a.cookie or "","isValid":a.is_valid,"lastVerified":a.last_verified.isoformat() if a.last_verified else ""}


# ==================== Saved Video Analysis Tasks (已存储任务) ====================

@router.post("/video-analysis/saved")
async def save_va_task(body: dict):
    """Archive a completed video analysis task."""
    task_id = body.get("taskId")
    if not task_id:
        raise HTTPException(status_code=400, detail="缺少taskId")
    db = SessionLocal()
    try:
        source = db.query(VideoAnalysisTask).filter(VideoAnalysisTask.id == task_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="任务不存在")
        if source.status != "done":
            raise HTTPException(status_code=400, detail="只能存储已完成的分析")
        # Check already saved
        existing = db.query(SavedVaTask).filter(SavedVaTask.source_task_id == task_id).first()
        if existing:
            return {"ok": True, "id": existing.id, "message": "已存在归档"}
        saved = SavedVaTask(
            source_task_id=task_id,
            bvid=source.bvid,
            title=source.title,
            cover_url=source.cover_url,
            total_comments=source.total_comments,
            matched_count=source.matched_count,
            analyzed_count=source.analyzed_count,
            centroid_x=source.centroid_x,
            centroid_y=source.centroid_y,
            centroid_x_no_origin=source.centroid_x_no_origin,
            centroid_y_no_origin=source.centroid_y_no_origin,
        )
        db.add(saved)
        db.commit()
        print(f"[SavedVA] Archived task {task_id} -> saved_id={saved.id}")
        return {"ok": True, "id": saved.id, "message": "已存储"}
    finally:
        db.close()


@router.get("/video-analysis/saved")
async def list_saved_va_tasks():
    """List all archived video analysis tasks."""
    db = SessionLocal()
    try:
        items = db.query(SavedVaTask).order_by(SavedVaTask.saved_at.desc()).all()
        return {
            "items": [{
                "id": s.id, "sourceTaskId": s.source_task_id, "bvid": s.bvid,
                "title": s.title, "coverUrl": s.cover_url,
                "totalComments": s.total_comments, "matchedCount": s.matched_count,
                "analyzedCount": s.analyzed_count,
                "centroidX": s.centroid_x, "centroidY": s.centroid_y,
                "centroidXNoOrigin": s.centroid_x_no_origin, "centroidYNoOrigin": s.centroid_y_no_origin,
                "savedAt": s.saved_at.isoformat(),
            } for s in items],
            "total": len(items),
        }
    finally:
        db.close()


@router.delete("/video-analysis/saved/{saved_id}")
async def delete_saved_va_task(saved_id: int):
    """Delete an archived task and its associated word cloud / deep analysis."""
    db = SessionLocal()
    try:
        saved = db.query(SavedVaTask).filter(SavedVaTask.id == saved_id).first()
        if not saved:
            raise HTTPException(status_code=404, detail="不存在")
        # Cascade delete word clouds and deep analyses
        db.query(WordCloudItem).filter(WordCloudItem.saved_va_task_id == saved_id).delete()
        db.query(DeepAnalysis).filter(DeepAnalysis.saved_va_task_id == saved_id).delete()
        db.delete(saved)
        db.commit()
        return {"ok": True, "message": "已删除"}
    finally:
        db.close()


# ==================== Word Cloud (词云) ====================

@router.post("/word-cloud/generate")
async def generate_word_cloud(body: dict):
    """Generate word cloud from all comments of a saved task. Uses jieba for segmentation."""
    import jieba
    import jieba.analyse
    saved_id = body.get("savedTaskId")
    if not saved_id:
        raise HTTPException(status_code=400, detail="缺少savedTaskId")
    db = SessionLocal()
    try:
        saved = db.query(SavedVaTask).filter(SavedVaTask.id == saved_id).first()
        if not saved:
            raise HTTPException(status_code=404, detail="已存储任务不存在")
        
        # Get all comments content for this task
        comments = db.query(VideoComment.content).filter(
            VideoComment.task_id == saved.source_task_id,
            VideoComment.content != "",
        ).all()
        
        if not comments:
            raise HTTPException(status_code=400, detail="该任务无评论数据")
        
        # Concatenate all comment text
        full_text = "\n".join([c[0] for c in comments])
        
        # Use jieba to extract keywords with TF-IDF
        # Add custom stop words
        stop_words = set("的 了 在 是 我 你 他 她 它 们 这 那 有 就 和 与 或 但 而 因为 所以 如果 虽然 但是 可以 这个 那个 什么 怎么 为什么 哪 一个 一些 也 都 很 太 更 最 啊 吧 呢 吗 哦 哈 嗯 嗯嗯".split())
        
        words = jieba.analyse.extract_tags(full_text, topK=150, withWeight=True)
        # Filter out single-char and stop words
        filtered = [(w, round(float(weight) * 1000)) for w, weight in words if len(w) >= 2 and w not in stop_words]
        
        if not filtered:
            raise HTTPException(status_code=500, detail="分词结果为空")
        
        # Take top 100
        filtered = filtered[:100]
        
        # Delete existing word cloud for this saved task
        db.query(WordCloudItem).filter(WordCloudItem.saved_va_task_id == saved_id).delete()
        
        wc = WordCloudItem(
            saved_va_task_id=saved_id,
            words_json=[{"text": w, "count": c, "weight": min(max(c, 10), 80)} for w, c in filtered],
            total_words=len(filtered),
        )
        db.add(wc)
        db.commit()
        
        print(f"[WordCloud] Generated for saved_task={saved_id}, {len(filtered)} words")
        return {"ok": True, "id": wc.id, "wordCount": len(filtered), "words": wc.words_json}
    finally:
        db.close()


@router.get("/word-cloud/list")
async def list_word_clouds():
    """List all generated word clouds."""
    db = SessionLocal()
    try:
        items = db.query(WordCloudItem).order_by(WordCloudItem.generated_at.desc()).all()
        result = []
        for wc in items:
            saved = db.query(SavedVaTask).filter(SavedVaTask.id == wc.saved_va_task_id).first()
            result.append({
                "id": wc.id, "savedVaTaskId": wc.saved_va_task_id,
                "taskTitle": saved.title if saved else "(已删除)",
                "taskBvid": saved.bvid if saved else "",
                "totalWords": wc.total_words,
                "words": wc.words_json,
                "generatedAt": wc.generated_at.isoformat(),
            })
        return {"items": result, "total": len(result)}
    finally:
        db.close()


@router.delete("/word-cloud/{wc_id}")
async def delete_word_cloud(wc_id: int):
    """Delete a word cloud record."""
    db = SessionLocal()
    try:
        wc = db.query(WordCloudItem).filter(WordCloudItem.id == wc_id).first()
        if not wc:
            raise HTTPException(status_code=404, detail="不存在")
        db.delete(wc)
        db.commit()
        return {"ok": True, "message": "已删除"}
    finally:
        db.close()


# ==================== Deep Analysis (深度分析) ====================

_deep_analysis_state: dict = {"status": "idle", "progress": "", "analysis_id": None}

@router.post("/deep-analysis/start")
async def start_deep_analysis(body: dict):
    """Start DeepSeek deep analysis on key comments of a saved task."""
    saved_id = body.get("savedTaskId")
    if not saved_id:
        raise HTTPException(status_code=400, detail="缺少savedTaskId")
    
    global _deep_analysis_state
    if _deep_analysis_state.get("status") in ("running",):
        raise HTTPException(status_code=409, detail="已有分析任务在运行中")
    
    db = SessionLocal()
    try:
        saved = db.query(SavedVaTask).filter(SavedVaTask.id == saved_id).first()
        if not saved:
            raise HTTPException(status_code=404, detail="已存储任务不存在")
        
        # Get top 100 hot comments + their sub-replies
        comments = db.query(VideoComment).filter(
            VideoComment.task_id == saved.source_task_id,
            VideoComment.sort_mode == "hot",
        ).order_by(VideoComment.like_count.desc()).limit(100).all()
        
        if not comments:
            raise HTTPException(status_code=400, detail="该任务无分析完成的评论")
        
        # Build comment text for LLM (include sub-reply context)
        comment_texts = []
        for c in comments[:50]:  # Send up to 50 main comments to save tokens
            text = f"[用户:{c.user} 点赞:{c.like_count}] {c.content}"
            # Get some sub replies
            subs = db.query(VideoComment).filter(
                VideoComment.task_id == saved.source_task_id,
                VideoComment.root_rpid == c.rpid,
            ).limit(3).all()
            if subs:
                text += "\n楼中楼:"
                for s in subs:
                    text += f"\n  @{s.user}: {s.content}"
            comment_texts.append(text)
        
        # Create analysis record
        da = DeepAnalysis(
            saved_va_task_id=saved_id,
            status="running",
        )
        db.add(da)
        db.commit()
        
        _deep_analysis_state = {"status": "running", "progress": "正在调用DeepSeek进行深度分析...", "analysis_id": da.id}
        
        # Background thread for DeepSeek call
        threading.Thread(target=_run_deep_analysis, args=(da.id, comment_texts, saved.title), daemon=True).start()
        
        return {"ok": True, "analysisId": da.id, "message": "深度分析已启动"}
    finally:
        db.close()


def _run_deep_analysis(analysis_id: int, comment_texts: list[str], title: str):
    """Background: call DeepSeek for deep opinion analysis."""
    global _deep_analysis_state
    ds_key = _get_deepseek_key()
    db = SessionLocal()
    try:
        _deep_analysis_state["progress"] = f"正在整理{len(comment_texts)}条关键评论..."
        
        if not ds_key:
            da = db.query(DeepAnalysis).filter(DeepAnalysis.id == analysis_id).first()
            da.status = "error"
            da.error_msg = "未配置DeepSeek API Key"
            da.completed_at = datetime.utcnow()
            db.commit()
            _deep_analysis_state = {"status": "idle", "progress": "", "analysis_id": None}
            return
        
        import httpx
        
        # Build prompt
        system_prompt = """你是一个专业的舆论场分析师。请对以下B站视频的评论区内容进行深度分析，输出JSON格式：
{
  "overall_trend": "舆论总体趋势总结（200字以内）",
  "kol_viewpoints": "高赞用户的主要观点分类和代表言论（300字以内）",
  "opposition_analysis": "与主流意见对立的观点及其理由（200字以内）"
}
请用中文回答，客观中立，不要带个人立场。"""
        
        user_content = f"视频标题：{title}\n\n关键评论（按点赞排序）：\n" + "\n---\n".join(comment_texts[:40])
        
        _deep_analysis_state["progress"] = "正在等待DeepSeek响应..."
        
        resp = httpx.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {ds_key}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            timeout=120,
        )
        
        data = resp.json()
        raw_text = data["choices"][0]["message"]["content"]
        
        # Parse JSON from response
        import re
        json_match = re.search(r'\{[^{}]*"overall_trend"[^{}]*\}', raw_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = {
                "overall_trend": raw_text,
                "kol_viewpoints": "",
                "opposition_analysis": "",
            }
        
        da = db.query(DeepAnalysis).filter(DeepAnalysis.id == analysis_id).first()
        da.status = "done"
        da.overall_trend = parsed.get("overall_trend", "")
        da.kol_viewpoints = parsed.get("kol_viewpoints", "")
        da.opposition_analysis = parsed.get("opposition_analysis", "")
        da.raw_response = raw_text
        da.completed_at = datetime.utcnow()
        db.commit()
        
        _deep_analysis_state = {"status": "idle", "progress": "done", "analysis_id": None}
        print(f"[DeepAnalysis] Completed analysis_id={analysis_id}")
        
    except Exception as e:
        print(f"[DeepAnalysis] ERROR: {e}")
        import traceback; traceback.print_exc()
        da = db.query(DeepAnalysis).filter(DeepAnalysis.id == analysis_id).first()
        if da:
            da.status = "error"
            da.error_msg = str(e)[:500]
            da.completed_at = datetime.utcnow()
            db.commit()
        _deep_analysis_state = {"status": "idle", "progress": "", "analysis_id": None}
    finally:
        db.close()


@router.get("/deep-analysis/status")
async def get_deep_analysis_status():
    """Get current deep analysis status."""
    return _deep_analysis_state


@router.get("/deep-analysis/list")
async def list_deep_analyses():
    """List all deep analysis results."""
    db = SessionLocal()
    try:
        items = db.query(DeepAnalysis).order_by(DeepAnalysis.created_at.desc()).all()
        result = []
        for da in items:
            saved = db.query(SavedVaTask).filter(SavedVaTask.id == da.saved_va_task_id).first()
            result.append({
                "id": da.id, "savedVaTaskId": da.saved_va_task_id,
                "taskTitle": saved.title if saved else "(已删除)",
                "status": da.status,
                "overallTrend": da.overall_trend,
                "kolViewpoints": da.kol_viewpoints,
                "oppositionAnalysis": da.opposition_analysis,
                "errorMsg": da.error_msg,
                "createdAt": da.created_at.isoformat(),
                "completedAt": da.completed_at.isoformat() if da.completed_at else None,
            })
        return {"items": result, "total": len(result)}
    finally:
        db.close()


@router.get("/deep-analysis/result/{analysis_id}")
async def get_deep_analysis_result(analysis_id: int):
    """Get a specific deep analysis result."""
    db = SessionLocal()
    try:
        da = db.query(DeepAnalysis).filter(DeepAnalysis.id == analysis_id).first()
        if not da:
            raise HTTPException(status_code=404, detail="不存在")
        return {
            "id": da.id, "savedVaTaskId": da.saved_va_task_id,
            "status": da.status,
            "overallTrend": da.overall_trend,
            "kolViewpoints": da.kol_viewpoints,
            "oppositionAnalysis": da.opposition_analysis,
            "errorMsg": da.error_msg,
            "rawResponse": da.raw_response,
            "createdAt": da.created_at.isoformat(),
            "completedAt": da.completed_at.isoformat() if da.completed_at else None,
        }
    finally:
        db.close()


@router.delete("/deep-analysis/{analysis_id}")
async def delete_deep_analysis(analysis_id: int):
    """Delete a deep analysis record."""
    db = SessionLocal()
    try:
        da = db.query(DeepAnalysis).filter(DeepAnalysis.id == analysis_id).first()
        if not da:
            raise HTTPException(status_code=404, detail="不存在")
        db.delete(da)
        db.commit()
        return {"ok": True, "message": "已删除"}
    finally:
        db.close()


# ==================== KOL Top Users (高赞KOL) ====================

@router.get("/video-analysis/kol-top")
async def get_kol_top_users(task_id: str, sort: str = "hot"):
    """Get top 10 users by likes (hot) or by most recent (time) for KOL identity check."""
    db = SessionLocal()
    try:
        query = db.query(
            VideoComment.uid,
            VideoComment.user,
            _sql_func.sum(VideoComment.like_count).label("like_sum"),
            _sql_func.count().label("comment_count"),
        ).filter(
            VideoComment.task_id == task_id,
            VideoComment.uid > 0,
            VideoComment.parent_rpid == 0,  # only main comments
        ).group_by(VideoComment.uid, VideoComment.user)
        
        if sort == "hot":
            query = query.order_by(_sql_func.sum(VideoComment.like_count).desc())
        else:
            query = query.order_by(VideoComment.ctime.desc())
        
        users = query.limit(10).all()
        
        # Get face URLs via batch info lookup (optional, use placeholder if unavailable)
        result = []
        for row in users:
            uid = row[0]
            user = row[1]
            like_sum = row[2]
            cnt = row[3]
            result.append({
                "uid": uid,
                "name": user or f"UID_{uid}",
                "face": f"https://i2.hdslb.com/bfs/face/{uid}_medium.jpg",
                "likeSum": like_sum or 0,
                "commentCount": cnt,
            })
        
        return {"users": result, "sort": sort, "taskId": task_id}
    except Exception as e:
        print(f"[KOL-TOP] ERROR: {e}")
        import traceback; traceback.print_exc()
        return {"users": [], "sort": sort, "taskId": task_id, "error": str(e)}
    finally:
        db.close()


# ==================== Identity Queue (查成分队列) ====================

_identity_queue_lock = threading.Lock()

@router.get("/identity-queue")
async def list_identity_queue():
    """List all queued identity-check tasks, ordered by sort_order."""
    db = SessionLocal()
    try:
        items = db.query(IdentityQueue).order_by(IdentityQueue.sort_order.asc(), IdentityQueue.added_at.asc()).all()
        return {
            "items": [{
                "id": q.id, "uid": q.uid, "name": q.name, "face": q.face,
                "source": q.source, "sortOrder": q.sort_order,
                "status": q.status, "addedAt": q.added_at.isoformat(),
            } for q in items],
            "total": len(items),
        }
    finally:
        db.close()


@router.post("/identity-queue")
async def add_to_identity_queue(body: dict):
    """Add a UID to the identity-check queue."""
    uid = body.get("uid")
    name = body.get("name", "")
    face = body.get("face", "")
    source = body.get("source", "manual")
    if not uid:
        raise HTTPException(status_code=400, detail="缺少uid")
    db = SessionLocal()
    try:
        # Check duplicate
        existing = db.query(IdentityQueue).filter(
            IdentityQueue.uid == uid,
            IdentityQueue.status == "pending",
        ).first()
        if existing:
            return {"ok": True, "id": existing.id, "message": "已在队列中"}
        
        # Get max sort order
        max_order = db.query(_sql_func.max(IdentityQueue.sort_order)).scalar() or 0
        
        q = IdentityQueue(uid=int(uid), name=name, face=face, source=source, sort_order=max_order + 1)
        db.add(q)
        db.commit()
        return {"ok": True, "id": q.id, "message": "已加入队列"}
    finally:
        db.close()


@router.delete("/identity-queue/{q_id}")
async def remove_from_identity_queue(q_id: int):
    """Remove a task from the identity queue."""
    db = SessionLocal()
    try:
        q = db.query(IdentityQueue).filter(IdentityQueue.id == q_id).first()
        if not q:
            raise HTTPException(status_code=404, detail="不存在")
        db.delete(q)
        # Re-index remaining
        remaining = db.query(IdentityQueue).order_by(IdentityQueue.sort_order.asc()).all()
        for i, item in enumerate(remaining):
            item.sort_order = i + 1
        db.commit()
        return {"ok": True, "message": "已移除"}
    finally:
        db.close()


@router.put("/identity-queue/reorder")
async def reorder_identity_queue(body: dict):
    """Reorder queue items. Body: {"orderedIds": [1, 3, 2, ...]}"""
    ordered_ids = body.get("orderedIds", [])
    if not ordered_ids:
        raise HTTPException(status_code=400, detail="缺少orderedIds")
    db = SessionLocal()
    try:
        for idx, q_id in enumerate(ordered_ids):
            q = db.query(IdentityQueue).filter(IdentityQueue.id == q_id).first()
            if q:
                q.sort_order = idx + 1
        db.commit()
        return {"ok": True, "message": "顺序已更新"}
    finally:
        db.close()
