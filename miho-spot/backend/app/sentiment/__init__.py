"""
Miho-spot Sentiment Analysis - Keyword-first matching
"""
from typing import Tuple, Optional
from snownlp import SnowNLP

# Built-in keyword cache
_KEYWORD_CACHE: Optional[dict] = None  # {"米哈游": "mihoyo_game", "原神": "mihoyo_game", ...}

MIHOYO_GAME = "mihoyo_game"
MIHOYO_CHAR = "mihoyo_character"
COMPETITOR = "competitor"
GENERAL = "general"

COMPETITOR_NAMES = {
    "明日方舟": "明日方舟", "鸣潮": "鸣潮", "无限暖暖": "无限暖暖",
    "幻塔": "幻塔", "少女前线2": "少女前线2", "重返未来1999": "重返未来1999",
    "蔚蓝档案": "蔚蓝档案", "碧蓝航线": "碧蓝航线", "无期迷途": "无期迷途",
    "明日方舟终末地": "明日方舟终末地", "异环": "异环",
    "赛马娘": "赛马娘", "FGO": "FGO", "白夜极光": "白夜极光",
}


def _load_keywords() -> dict:
    """Load all keywords from DB into memory cache"""
    global _KEYWORD_CACHE
    if _KEYWORD_CACHE is not None:
        return _KEYWORD_CACHE
    try:
        from app.models import SessionLocal, KeywordModel
        db = SessionLocal()
        rows = db.query(KeywordModel).all()
        _KEYWORD_CACHE = {row.keyword: row.category for row in rows}
        db.close()
    except:
        _KEYWORD_CACHE = {}
    return _KEYWORD_CACHE


def analyze_topic_sentiment(title: str) -> Tuple[str, Optional[str]]:
    """
    Step 1: Match title against keyword dictionary
    Step 2: No keyword match → Irrelevant
    Step 3: Keyword matched → SnowNLP sentiment analysis
    Returns: (sentiment, related_game_or_None)
    """
    keywords = _load_keywords()
    if not keywords:
        return "Neutral", None

    matched_categories = set()
    matched_game = None

    for kw, category in keywords.items():
        if kw.lower() in title.lower():
            matched_categories.add(category)
            if category == COMPETITOR and not matched_game:
                matched_game = COMPETITOR_NAMES.get(kw, kw)

    if not matched_categories:
        return "Irrelevant", None

    # Determine if miHoYo-related
    is_mihoyo = MIHOYO_GAME in matched_categories or MIHOYO_CHAR in matched_categories

    if not is_mihoyo:
        return "Irrelevant", matched_game or "竞品"

    # Sentiment analysis via SnowNLP
    try:
        negative_words = [
            "差评", "垃圾", "恶心", "退坑", "弃坑", "失望", "摆烂", "摆",
            "数值膨胀", "逼氪", "骗氪", "扣", "敷衍", "翻车", "节奏",
            "bug", "BUG", "抄袭", "炎上", "烂", "骂", "喷", "吐槽",
            "暴跌", "凉凉", "暴死", "喂史", "狗都不玩", "逆天",
            "无聊", "垃圾游戏", "退钱", "退款", "举报", "和谐",
            "暗改", "削弱", "背刺", "撕卡", "膨胀", "骗钱",
        ]
        positive_words = [
            "好评", "神作", "吹爆", "入坑", "真香", "惊艳", "厉害",
            "牛逼", "震撼", "良心", "完美", "优秀", "美", "燃",
            "感动", "哭了", "用心", "巅峰", "越来越", "顶级",
            "封神", "无敌", "起飞", "爽", "爱了", "宝藏",
            "惊喜", "绝美", "细节满满", "沉浸", "好玩",
        ]

        has_neg = any(w in title for w in negative_words)
        has_pos = any(w in title for w in positive_words)

        if has_neg and not has_pos:
            return "Negative", None
        if has_pos and not has_neg:
            return "Positive", None

        s = SnowNLP(title)
        score = s.sentiments
        if score > 0.7:
            return "Positive", None
        elif score < 0.3:
            return "Negative", None
        return "Neutral", None
    except:
        return "Neutral", None


def seed_default_keywords():
    """Seed 200+ game circle keywords into database"""
    from app.models import SessionLocal, KeywordModel
    from datetime import datetime
    import hashlib

    keywords = [
        # === 米哈游本体 (4) ===
        ("米哈游", MIHOYO_GAME), ("miHoYo", MIHOYO_GAME),
        ("米忽悠", MIHOYO_GAME), ("mhy", MIHOYO_GAME),

        # === 原神 (30) ===
        ("原神", MIHOYO_GAME), ("Genshin Impact", MIHOYO_GAME),
        ("钟离", MIHOYO_CHAR), ("胡桃", MIHOYO_CHAR), ("雷电将军", MIHOYO_CHAR),
        ("纳西妲", MIHOYO_CHAR), ("芙宁娜", MIHOYO_CHAR), ("那维莱特", MIHOYO_CHAR),
        ("散兵", MIHOYO_CHAR), ("万叶", MIHOYO_CHAR), ("可莉", MIHOYO_CHAR),
        ("达达利亚", MIHOYO_CHAR), ("派蒙", MIHOYO_CHAR), ("魈", MIHOYO_CHAR),
        ("甘雨", MIHOYO_CHAR), ("刻晴", MIHOYO_CHAR), ("温迪", MIHOYO_CHAR),
        ("神里绫华", MIHOYO_CHAR), ("夜兰", MIHOYO_CHAR), ("八重神子", MIHOYO_CHAR),
        ("提瓦特", MIHOYO_GAME), ("七圣召唤", MIHOYO_GAME),
        ("尘歌壶", MIHOYO_GAME), ("原魔", MIHOYO_GAME),
        ("枫丹", MIHOYO_GAME), ("须弥", MIHOYO_GAME), ("璃月", MIHOYO_GAME),
        ("蒙德", MIHOYO_GAME), ("稻妻", MIHOYO_GAME), ("纳塔", MIHOYO_GAME),

        # === 星穹铁道 (25) ===
        ("崩坏：星穹铁道", MIHOYO_GAME), ("星穹铁道", MIHOYO_GAME), ("崩坏星穹铁道", MIHOYO_GAME),
        ("三月七", MIHOYO_CHAR), ("丹恒", MIHOYO_CHAR), ("景元", MIHOYO_CHAR),
        ("卡芙卡", MIHOYO_CHAR), ("银狼", MIHOYO_CHAR), ("刃", MIHOYO_CHAR),
        ("流萤", MIHOYO_CHAR), ("知更鸟", MIHOYO_CHAR), ("姬子", MIHOYO_CHAR),
        ("瓦尔特", MIHOYO_CHAR), ("希儿", MIHOYO_CHAR), ("布洛妮娅", MIHOYO_CHAR),
        ("罗刹", MIHOYO_CHAR), ("符玄", MIHOYO_CHAR), ("镜流", MIHOYO_CHAR),
        ("阮梅", MIHOYO_CHAR), ("黑塔", MIHOYO_CHAR),
        ("差分宇宙", MIHOYO_GAME), ("模拟宇宙", MIHOYO_GAME),
        ("忘却之庭", MIHOYO_GAME), ("匹诺康尼", MIHOYO_GAME),
        ("仙舟", MIHOYO_GAME),

        # === 崩坏3 (15) ===
        ("崩坏3", MIHOYO_GAME), ("崩坏三", MIHOYO_GAME), ("崩坏3rd", MIHOYO_GAME),
        ("琪亚娜", MIHOYO_CHAR), ("芽衣", MIHOYO_CHAR), ("八重樱", MIHOYO_CHAR),
        ("爱莉希雅", MIHOYO_CHAR), ("无量塔姬子", MIHOYO_CHAR),
        ("德丽莎", MIHOYO_CHAR), ("符华", MIHOYO_CHAR),
        ("理之律者", MIHOYO_GAME), ("空之律者", MIHOYO_GAME),
        ("后崩坏书", MIHOYO_GAME), ("往世乐土", MIHOYO_GAME),
        ("律者", MIHOYO_GAME),

        # === 绝区零 (12) ===
        ("绝区零", MIHOYO_GAME), ("Zenless Zone Zero", MIHOYO_GAME),
        ("安比", MIHOYO_CHAR), ("妮可", MIHOYO_CHAR), ("比利", MIHOYO_CHAR),
        ("猫又", MIHOYO_CHAR), ("艾莲", MIHOYO_CHAR), ("朱鸢", MIHOYO_CHAR),
        ("青衣", MIHOYO_CHAR), ("新艾利都", MIHOYO_GAME),
        ("绳匠", MIHOYO_GAME), ("法厄同", MIHOYO_GAME),

        # === 未定事件簿 (3) ===
        ("未定事件簿", MIHOYO_GAME), ("陆景和", MIHOYO_CHAR), ("左然", MIHOYO_CHAR),

        # === 竞品游戏 (25) ===
        ("明日方舟", COMPETITOR), ("明日方舟终末地", COMPETITOR),
        ("鸣潮", COMPETITOR), ("无限暖暖", COMPETITOR), ("幻塔", COMPETITOR),
        ("少女前线2", COMPETITOR), ("少前2", COMPETITOR),
        ("重返未来1999", COMPETITOR), ("蔚蓝档案", COMPETITOR),
        ("碧蓝航线", COMPETITOR), ("无期迷途", COMPETITOR),
        ("异环", COMPETITOR), ("赛马娘", COMPETITOR),
        ("FGO", COMPETITOR), ("白夜极光", COMPETITOR),
        ("尘白禁区", COMPETITOR), ("卡拉彼丘", COMPETITOR),
        ("星之翼", COMPETITOR), ("归龙潮", COMPETITOR),
        ("永劫无间手游", COMPETITOR), ("代号鸢", COMPETITOR),
        ("墨剑江湖", COMPETITOR), ("仙境传说RO", COMPETITOR),
        ("原神竞品", COMPETITOR), ("开放世界手游", COMPETITOR),

        # === 竞品角色 (10) ===
        ("博士", COMPETITOR), ("阿米娅", COMPETITOR), ("凯尔希", COMPETITOR),
        ("伤痕", COMPETITOR), ("漂泊者", COMPETITOR), ("吟霖", COMPETITOR),
        ("暖暖", COMPETITOR), ("安洁莉娜", COMPETITOR),
        ("马娘", COMPETITOR), ("御主", COMPETITOR),

        # === 二游圈术语 (40) ===
        ("二游", GENERAL), ("二次元手游", GENERAL), ("gacha", GENERAL),
        ("抽卡", GENERAL), ("648", GENERAL), ("保底", GENERAL),
        ("策划", GENERAL), ("版本更新", GENERAL), ("前瞻直播", GENERAL),
        ("角色PV", GENERAL), ("流水", GENERAL), ("卡池", GENERAL),
        ("命座", GENERAL), ("专武", GENERAL), ("数值膨胀", GENERAL),
        ("深渊", GENERAL), ("大世界", GENERAL), ("剧情", GENERAL),
        ("主线", GENERAL), ("支线", GENERAL), ("活动", GENERAL),
        ("限定", GENERAL), ("常驻", GENERAL), ("UP池", GENERAL),
        ("双UP", GENERAL), ("歪了", GENERAL), ("欧皇", GENERAL),
        ("非酋", GENERAL), ("初始号", GENERAL), ("自抽号", GENERAL),
        ("脱坑", GENERAL), ("回坑", GENERAL), ("入坑", GENERAL),
        ("原批", GENERAL), ("米卫兵", GENERAL), ("米黑", GENERAL),
        ("内鬼", GENERAL), ("内鬼吧", GENERAL), ("米孝子", GENERAL),
        ("黑红", GENERAL),

        # === 米哈游CV (60) ===
        ("kinsen", MIHOYO_GAME), ("花玲", MIHOYO_GAME), ("林簌", MIHOYO_GAME),
        ("多多poi", MIHOYO_GAME), ("陶典", MIHOYO_GAME), ("Mace", MIHOYO_GAME),
        ("菊花花", MIHOYO_GAME), ("彭博", MIHOYO_GAME), ("赵路", MIHOYO_GAME),
        ("孙晔", MIHOYO_GAME), ("杨梦露", MIHOYO_GAME), ("喵酱", MIHOYO_GAME),
        ("小N", MIHOYO_GAME), ("牛奶君", MIHOYO_GAME), ("宋媛媛", MIHOYO_GAME),
        ("鹿喑", MIHOYO_GAME), ("宴宁", MIHOYO_GAME), ("唐雅菁", MIHOYO_GAME),
        ("杜冥鸦", MIHOYO_GAME), ("谢莹", MIHOYO_GAME), ("秦紫翼", MIHOYO_GAME),
        ("苏子芜", MIHOYO_GAME), ("龟娘", MIHOYO_GAME), ("诺亚", MIHOYO_GAME),
        ("张安琪", MIHOYO_GAME), ("子音", MIHOYO_GAME), ("陈婷婷", MIHOYO_GAME),
        ("钱琛", MIHOYO_GAME), ("刘北辰", MIHOYO_GAME), ("斑马", MIHOYO_GAME),
        ("金娜", MIHOYO_GAME), ("小敢", MIHOYO_GAME), ("张沛", MIHOYO_GAME),
        ("刘照坤", MIHOYO_GAME), ("杨昕燃", MIHOYO_GAME), ("林景", MIHOYO_GAME),
        ("马洋", MIHOYO_GAME), ("周帅", MIHOYO_GAME), ("穆雪婷", MIHOYO_GAME),
        ("鱼冻", MIHOYO_GAME), ("秦且歌", MIHOYO_GAME), ("王晓彤", MIHOYO_GAME),
        ("李轻扬", MIHOYO_GAME), ("紫苏九月", MIHOYO_GAME), ("锦鲤", MIHOYO_GAME),
        ("可可味", MIHOYO_GAME), ("赵爽", MIHOYO_GAME), ("蔡海婷", MIHOYO_GAME),
        ("张琦", MIHOYO_GAME), ("黄莺", MIHOYO_GAME), ("吴磊", MIHOYO_GAME),
        ("孙艳琦", MIHOYO_GAME), ("浮梦若薇", MIHOYO_GAME), ("木子橙", MIHOYO_GAME),
        ("李晔", MIHOYO_GAME), ("刘颐诺", MIHOYO_GAME), ("贺文潇", MIHOYO_GAME),
        ("桑毓泽", MIHOYO_GAME), ("张若瑜", MIHOYO_GAME), ("梁达伟", MIHOYO_GAME),
    ]

    db = SessionLocal()
    try:
        count = 0
        for kw, cat in keywords:
            existing = db.query(KeywordModel).filter(KeywordModel.keyword == kw).first()
            if not existing:
                db.add(KeywordModel(
                    id=hashlib.md5(kw.encode()).hexdigest()[:16],
                    keyword=kw, category=cat,
                    added_at=datetime.utcnow(), added_by="system",
                ))
                count += 1
        db.commit()
        if count > 0:
            print(f"[Seed] Added {count} new keywords")
        _KEYWORD_CACHE = None  # Invalidate cache
    finally:
        db.close()
