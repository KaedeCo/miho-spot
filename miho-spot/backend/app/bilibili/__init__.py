"""
Bilibili User Comment Fetcher (via AICU API + B站 card API)
- User info: B站 x/web-interface/card (reliable, no WBI needed)
- User comments: AICU api.aicu.cc (reliable, no WBI, no rate limit)
"""
import json
import re
import time
from typing import List, Dict, Any
from datetime import datetime, timedelta
from curl_cffi import requests as cffi_requests
import httpx

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# ---- AICU API (for comment history) ----

AICU_HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": "https://www.aicu.cc/",
    "Origin": "https://www.aicu.cc",
}


def _aicu_get(url: str, params: dict = None) -> dict:
    """Call AICU API with curl_cffi (bypasses Cloudflare)."""
    if params is None:
        params = {}
    try:
        resp = cffi_requests.get(
            url, params=params, headers=AICU_HEADERS,
            impersonate="chrome131", timeout=30
        )
        if resp.status_code != 200:
            hint = ""
            if resp.status_code == 403:
                hint = " (可能被Cloudflare拦截，建议切换IP或稍后重试)"
            raise RuntimeError(f"AICU API HTTP {resp.status_code}{hint}: {resp.text[:200]}")
        data = resp.json()
    except Exception as e:
        if "403" in str(e) or "Cloudflare" in str(e):
            raise RuntimeError(f"AICU API 被风控拦截，请切换网络/IP后重试。详情: {str(e)[:200]}")
        raise
    # Validate response
    if data.get("code") != 0:
        msg = data.get("message", "unknown error")
        raise RuntimeError(f"AICU API error: {msg}")
    return data.get("data", {})


# ---- Public API Functions ----

async def get_user_info(uid: int) -> dict:
    """Get B站 user basic info via B站 card API (no WBI needed)."""
    import asyncio
    headers = {"User-Agent": USER_AGENT, "Referer": f"https://space.bilibili.com/{uid}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.bilibili.com/x/web-interface/card",
            params={"mid": uid}, headers=headers, timeout=15
        )
        data = resp.json()
    card = (data.get("data") or {}).get("card", {})
    return {
        "uid": card.get("mid", uid),
        "name": card.get("name", ""),
        "face": card.get("face", ""),
        "sign": card.get("sign", ""),
        "level": 0,
        "sex": card.get("sex", ""),
        "home_url": f"https://space.bilibili.com/{uid}",
        "fans": card.get("fans", 0),
        "attention": card.get("friend", 0),
    }


async def fetch_user_video_comments(
    uid: int, max_videos: int = 50,
    max_comments_per_video: int = 500,
    months_limit: int = 6
) -> List[dict]:
    """
    Fetch user's video comments via AICU API.
    AICU returns ALL video comments the user has ever made.
    We first try the time window; if 0 results, fall back to all data.
    """
    import asyncio

    cutoff_ts = (datetime.utcnow() - timedelta(days=months_limit * 30)).timestamp()
    print(f"[Bilibili] Fetching AICU comments for uid={uid}, months_limit={months_limit}, cutoff={datetime.utcfromtimestamp(cutoff_ts)}")

    raw_comments = []
    page = 1
    max_results = 2000  # safety cap

    while len(raw_comments) < max_results:
        try:
            data = await asyncio.to_thread(
                _aicu_get,
                "https://api.aicu.cc/api/v3/search/getreply",
                {"uid": str(uid), "pn": str(page), "ps": "100", "mode": "0", "keyword": ""}
            )
            replies = data.get("replies", [])
            if not replies:
                break

            cursor = data.get("cursor", {})
            all_count = cursor.get("all_count", 0)
            is_end = cursor.get("is_end", False)
            if page == 1:
                print(f"[Bilibili] AICU total: {all_count} comments across {(all_count + 99) // 100} pages")
            
            raw_comments.extend(replies)
            
            if is_end or page >= (all_count + 99) // 100:
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"[Bilibili] AICU page {page} error: {e}")
            break

    print(f"[Bilibili] AICU fetched {len(raw_comments)} raw comments")

    # Convert to our format
    all_comments = []
    for r in raw_comments:
        ctime = r.get("time", 0)
        message = r.get("message", "")
        if not message:
            continue
        all_comments.append({
            "rpid": r.get("rpid", ""),
            "content": message,
            "ctime": ctime,
            "time_str": datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S") if ctime else "未知",
            "video_title": "",
            "video_bvid": "",
            "video_aid": 0,
            "video_url": f"https://www.bilibili.com/video/av{r.get('oid', '')}" if r.get('oid') else "",
            "comment_url": "",
            "likes": r.get("like", 0),
            "reply_count": 0,
        })

    # Try time window first
    recent = [c for c in all_comments if c["ctime"] >= cutoff_ts]
    if recent:
        recent.sort(key=lambda c: c["ctime"], reverse=True)
        print(f"[Bilibili] AICU Done: {len(recent)} comments within {months_limit} months (of {len(all_comments)} total)")
        return recent

    # Fallback: return all comments with a flag
    print(f"[Bilibili] AICU: 0 comments within {months_limit} months, returning all {len(all_comments)} instead")
    all_comments.sort(key=lambda c: c["ctime"], reverse=True)
    # Mark the first comment to indicate data age
    if all_comments:
        oldest = all_comments[-1]
        newest = all_comments[0]
        all_comments[0]["content"] = f"[数据提示：AICU数据非实时，最新评论时间: {newest.get('time_str')}, 最早: {oldest.get('time_str')}] " + all_comments[0]["content"]
    return all_comments


# ---- Keyword Filtering ----

def filter_comments_by_keywords(comments: List[dict]) -> List[dict]:
    """Filter comments that match any keyword from the sentiment dictionary."""
    from app.sentiment import _load_keywords
    keywords = _load_keywords()
    if not keywords:
        return comments

    matched = []
    for c in comments:
        content = c.get("content", "")
        matched_kws = []
        matched_categories = set()
        for kw, category in keywords.items():
            if kw.lower() in content.lower():
                matched_kws.append(kw)
                matched_categories.add(category)
        if matched_kws:
            c["matched_keywords"] = matched_kws
            c["matched_categories"] = list(matched_categories)
            matched.append(c)
    return matched


# ---- DeepSeek Personality Analysis ----

async def analyze_user_personality(all_comments: List[dict], matched_comments: List[dict], api_key: str) -> dict:
    """
    Analyze user personality from their comments via DeepSeek.
    Uploads ALL keyword-matched comments + latest comments (totaling 100).
    Returns: {"mihoyo_attitude": str, "active_areas": str, "personality": str, "score": int}
    """
    import asyncio

    if not api_key or not all_comments:
        return {
            "score": 50,
            "mihoyo_attitude": "无评论数据",
            "active_areas": "未知",
            "personality": "无法分析",
            "summary": "该用户无评论数据",
        }

    # Combine: all keyword-matched + fill with latest by time to reach 100
    matched_set = {c["rpid"] for c in matched_comments if c.get("rpid")}
    combined = list(matched_comments)
    for c in all_comments:
        if len(combined) >= 100:
            break
        if c.get("rpid") not in matched_set:
            combined.append(c)
            matched_set.add(c.get("rpid"))

    print(f"[DeepSeek-Personality] Uploading {len(combined)} comments (matched={len(matched_comments)}, total={len(all_comments)})")

    max_chars = 8000
    comments_texts = []
    total_chars = 0
    for c in combined:
        kw_tags = ""
        if c.get("matched_keywords"):
            kw_tags = f" [命中: {','.join(c['matched_keywords'][:5])}]"
        line = f"[{c.get('time_str', '')}]{kw_tags} {c.get('content', '')}"
        if total_chars + len(line) > max_chars:
            break
        comments_texts.append(line)
        total_chars += len(line)

    joined_text = "\n\n".join(comments_texts)

    prompt = f"""你是一个专业的用户画像分析师。请根据以下B站用户的评论记录，分析该用户的人格特征。

分析维度：
1. 对米哈游游戏的态度：请分析该用户对米哈游（原神、星穹铁道、绝区零、崩坏等）的总体态度。描述其是支持还是反对，情绪倾向如何，并给出0-100的分数（0=极度反对，50=中立，100=极度支持）。
2. 主要活跃领域：根据评论内容推断该用户活跃的游戏圈子、讨论话题和关注点。
3. 性格推测：根据语言风格、互动方式推断该用户可能的人格类型和特点。

请注意：标记了[命中]的评论表示提到了米哈游相关关键词，是重点分析对象。

用户评论记录：
---
{joined_text}
---

请严格按照以下JSON格式回复（不要添加任何其他文字）：
{{"score": 0到100的整数, "mihoyo_attitude": "对米哈游态度的详细分析（100字以内）", "active_areas": "主要活跃领域推断（80字以内）", "personality": "性格推测（100字以内）", "summary": "一句话总结（20字以内）"}}"""

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.5, "max_tokens": 500},
                timeout=60,
            )
            data = resp.json()
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "{}").strip()
            answer = re.sub(r'^```(?:json)?\s*', '', answer)
            answer = re.sub(r'\s*```$', '', answer)
            result = json.loads(answer)
            score = max(0, min(100, int(result.get("score", 50))))
            return {
                "score": score,
                "mihoyo_attitude": result.get("mihoyo_attitude", "分析完成"),
                "active_areas": result.get("active_areas", "分析完成"),
                "personality": result.get("personality", "分析完成"),
                "summary": result.get("summary", "分析完成"),
            }
    except json.JSONDecodeError as e:
        print(f"[DeepSeek] JSON parse error: {e}")
        return {"score": 50, "mihoyo_attitude": "AI分析结果解析失败", "active_areas": "未知", "personality": "分析异常", "summary": "分析异常"}
    except Exception as e:
        print(f"[DeepSeek] Error: {e}")
        return {"score": 50, "mihoyo_attitude": f"AI分析失败: {str(e)[:100]}", "active_areas": "未知", "personality": "分析失败", "summary": "分析失败"}
