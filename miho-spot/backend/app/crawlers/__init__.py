"""
Miho-spot Crawlers - Uses Tophub API (api.tophubdata.com)
"""
import hashlib
import re
import httpx
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import quote

# Known board hashids for Zhihu, Douyin, Tieba
PLATFORM_HASHIDS = {
    "zhihu": "mproPpoq6O",
    "douyin": "DpQvNABoNE",
    "tieba": None,  # Will be discovered via /nodes
}

MIHOYO_SEARCH_KEYWORD = "米哈游"
TOPHUB_SEARCH_KEYWORD = "米哈游"

# Default API key (user can override)
TOPHUB_API_KEY = ""  # Set via Account page
TOPHUB_BASE = "https://api.tophubdata.com"


def _get_api_key() -> str:
    """Get Tophub API key from DB or default"""
    try:
        from app.models import SessionLocal, AccountModel
        db = SessionLocal()
        acc = db.query(AccountModel).filter(AccountModel.platform == "tophub").first()
        db.close()
        if acc and acc.username:  # username field stores API key
            return acc.username
    except:
        pass
    return TOPHUB_API_KEY


def _api_get(path: str, params: dict = None) -> dict:
    """Make authenticated Tophub API request"""
    key = _get_api_key()
    headers = {"Authorization": key}
    url = f"{TOPHUB_BASE}{path}"
    resp = httpx.get(url, headers=headers, params=params, timeout=20)
    data = resp.json()
    if data.get("error"):
        print(f"[Tophub API] Error: {data.get('msg', 'unknown')} (status={data.get('status')})")
        return {}
    return data


def _discover_tieba_hashid() -> str:
    """Find Tieba hashid from nodes list"""
    p = 1
    while p <= 5:
        data = _api_get("/nodes", {"p": p})
        nodes = data.get("data", [])
        if not nodes:
            break
        for n in nodes:
            if "贴吧" in n.get("name", "") or "tieba" in n.get("domain", ""):
                print(f"[Discover] Tieba hashid = {n['hashid']}")
                PLATFORM_HASHIDS["tieba"] = n["hashid"]
                return n["hashid"]
        if len(nodes) < 100:
            break
        p += 1
    return None


class BaseCrawler:
    def __init__(self, platform: str):
        self.platform = platform
        self.hashid = PLATFORM_HASHIDS.get(platform)
        self.client = httpx.Client(
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            follow_redirects=True,
        )

    def generate_id(self, *args) -> str:
        return hashlib.md5("-".join(str(a) for a in args).encode()).hexdigest()[:16]

    @staticmethod
    def _parse_heat(text: str) -> float:
        text = text.replace(",", "").replace("，", "").strip()
        if "万" in text or "w" in text.lower():
            return float(re.sub(r'[^\d.]', '', text)) * 10000
        if "亿" in text:
            return float(re.sub(r'[^\d.]', '', text)) * 100000000
        try:
            return float(re.sub(r'[^\d.]', '', text))
        except:
            return 0

    def fetch_hot_list(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def fetch_keyword_search(self, keyword: str = None) -> List[Dict[str, Any]]:
        """Generate search links for game-related keywords on this platform.
        The free API tier only returns node metadata, not content.
        Content endpoints (/nodes/{hashid}) are paid, so we generate direct search links."""
        items = []
        search_terms = ["米哈游", "原神", "星穹铁道", "绝区零", "崩坏3",
                        "原神 剧情", "星穹铁道 卡池", "绝区零 新角色",
                        "米哈游 流水", "原神 节奏"]
        for term in search_terms:
            if len(items) >= 50: break
            if self.platform == "tieba":
                url = f"https://tieba.baidu.com/f/search/res?qw={quote(term)}"
            elif self.platform == "douyin":
                url = f"https://www.douyin.com/search/{quote(term)}"
            else:
                url = f"https://www.zhihu.com/search?type=content&q={quote(term)}"
            items.append({
                "id": self.generate_id(self.platform, "search", term),
                "platform": self.platform, "title": f"[搜索] {term}",
                "rank": len(items) + 1, "heat": 0, "url": url,
                "source": "search", "fetched_at": datetime.utcnow().isoformat(),
            })
        print(f"[{self.platform}] Generated {len(items)} search links")
        return items


class ZhihuCrawler(BaseCrawler):
    TOPHUB_URL = "https://tophub.today/n/mproPpoq6O"

    def __init__(self):
        super().__init__("zhihu")

    def fetch_hot_list(self) -> List[Dict[str, Any]]:
        print(f"[Zhihu] Fetching hot list...")
        items = []
        try:
            from bs4 import BeautifulSoup
            resp = self.client.get(self.TOPHUB_URL)
            soup = BeautifulSoup(resp.text, "html.parser")
            for row in soup.select("table tr"):
                tds = row.find_all("td")
                if len(tds) < 3: continue
                rank_text = tds[0].get_text(strip=True).rstrip(".")
                try: rank = int(rank_text)
                except: continue
                full_text = tds[2].get_text(" ", strip=False)
                parts = re.split(r'\s{2,}', full_text.strip())
                if len(parts) >= 2:
                    title = " ".join(parts[:-1]).strip()
                    heat = self._parse_heat(parts[-1])
                else:
                    m = re.match(r'^(.*?)\s+(\d[\d,.]*\s*万?\s*热度?)$', full_text.strip())
                    title = m.group(1).strip() if m else full_text.strip()
                    heat = self._parse_heat(m.group(2)) if m else 0
                if not title or len(title) < 3: continue
                items.append({
                    "id": self.generate_id("zhihu", title), "platform": "zhihu",
                    "title": title, "rank": rank, "heat": heat,
                    "url": f"https://www.zhihu.com/search?type=content&q={quote(title)}",
                    "source": "hot", "fetched_at": datetime.utcnow().isoformat(),
                })
            items.sort(key=lambda x: x["rank"])
            print(f"[Zhihu] Hot: {len(items)}")
        except Exception as e: print(f"[Zhihu] Error: {e}")
        return items[:50]


class DouyinCrawler(BaseCrawler):
    TOPHUB_URL = "https://tophub.today/n/DpQvNABoNE"

    def __init__(self):
        super().__init__("douyin")

    def fetch_hot_list(self) -> List[Dict[str, Any]]:
        print(f"[Douyin] Fetching hot list...")
        items = []
        try:
            from bs4 import BeautifulSoup
            resp = self.client.get(self.TOPHUB_URL)
            soup = BeautifulSoup(resp.text, "html.parser")
            for row in soup.select("table tr"):
                tds = row.find_all("td")
                if len(tds) < 3: continue
                rank_text = tds[0].get_text(strip=True).rstrip(".")
                try: rank = int(rank_text)
                except: continue
                td2_text = tds[2].get_text("\n", strip=True)
                lines = [l.strip() for l in td2_text.split("\n") if l.strip()]
                if not lines: continue
                title = re.sub(r'@\S+$', '', lines[0]).strip()
                heat = 0
                if lines[-1]:
                    hm = re.search(r'(\d[\d,.]*)\s*次播放', lines[-1])
                    if hm: heat = float(hm.group(1).replace(',', ''))
                if not title or len(title) < 3: continue
                items.append({
                    "id": self.generate_id("douyin", title), "platform": "douyin",
                    "title": title, "rank": rank, "heat": heat,
                    "url": f"https://www.douyin.com/search/{quote(title)}",
                    "source": "hot", "fetched_at": datetime.utcnow().isoformat(),
                })
            print(f"[Douyin] Hot: {len(items)}")
        except Exception as e: print(f"[Douyin] Error: {e}")
        return items


class TiebaCrawler(BaseCrawler):
    API_URL = "https://tieba.baidu.com/hottopic/browse/topicList"

    def __init__(self):
        super().__init__("tieba")

    def fetch_hot_list(self) -> List[Dict[str, Any]]:
        print(f"[Tieba] Fetching hot list...")
        items = []
        try:
            resp = self.client.get(self.API_URL)
            data = resp.json()
            for topic in data.get("data", {}).get("bang_topic", {}).get("topic_list", []):
                name = topic.get("topic_name", "")
                if not name: continue
                url = topic.get("topic_url", "")
                if url and not url.startswith("http"): url = f"https://tieba.baidu.com{url}"
                items.append({
                    "id": self.generate_id("tieba", str(topic.get("topic_id", name))),
                    "platform": "tieba", "title": name,
                    "rank": topic.get("idx_num", 0), "heat": topic.get("discuss_num", 0),
                    "url": url or f"https://tieba.baidu.com/f/search/res?qw={quote(name)}",
                    "source": "hot", "fetched_at": datetime.utcnow().isoformat(),
                })
            items.sort(key=lambda x: x["rank"])
            print(f"[Tieba] Hot: {len(items)}")
        except Exception as e: print(f"[Tieba] Error: {e}")
        return items


def fetch_tophub_search(keyword: str = "米哈游", page: int = 1, max_retries: int = 2) -> dict:
    """Call Tophub /search API endpoint (paid) - returns raw response data.
    Includes retry logic with increasing timeout for unreliable network."""
    key = _get_api_key()
    headers = {"Authorization": key}
    url = f"{TOPHUB_BASE}/search"

    for attempt in range(1, max_retries + 1):
        # Progressive timeout: 30s -> 45s -> 60s
        t = min(30 * attempt, 60)
        try:
            resp = httpx.get(url, headers=headers, params={"q": keyword, "p": page}, timeout=t)
            print(f"[Tophub Search] HTTP {resp.status_code} q={keyword} p={page} (attempt={attempt}/{max_retries})")
            try:
                data = resp.json()
            except Exception:
                print(f"[Tophub Search] Bad JSON: {resp.text[:200]}")
                if attempt < max_retries:
                    print(f"[Tophub Search] Retrying ({attempt+1}/{max_retries})...")
                    continue
                return {"error": True, "msg": "Invalid JSON response"}
            if data.get("error"):
                print(f"[Tophub Search] API error: {data.get('msg', 'unknown')}")
            return data
        except httpx.TimeoutException as e:
            print(f"[Tophub Search] Timeout ({t}s): {e}")
            if attempt < max_retries:
                import time as _t; _t.sleep(2)
                continue
            return {"error": True, "msg": f"Request timed out after {t}s (retried {max_retries} times)"}
        except Exception as e:
            print(f"[Tophub Search] Error: {e}")
            if attempt < max_retries:
                import time as _t; _t.sleep(2)
                continue
            return {"error": True, "msg": str(e)[:200]}

    return {"error": True, "msg": "All retries exhausted"}


def _extract_platform_from_url(url: str) -> str:
    """Infer platform from item URL domain."""
    if not url:
        return "other"
    url_lower = url.lower()
    if "zhihu.com" in url_lower:
        return "zhihu"
    if "douyin.com" in url_lower:
        return "douyin"
    if "tieba.baidu.com" in url_lower:
        return "tieba"
    if "bilibili.com" in url_lower:
        return "bilibili"
    if "weibo.com" in url_lower:
        return "weibo"
    return "other"


def get_crawler(platform: str) -> BaseCrawler:
    crawlers = {
        "zhihu": ZhihuCrawler(),
        "douyin": DouyinCrawler(),
        "tieba": TiebaCrawler(),
    }
    return crawlers.get(platform, BaseCrawler(platform))
