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
    """Seed 750+ game circle keywords into database"""
    from app.models import SessionLocal, KeywordModel
    from datetime import datetime
    import hashlib

    keywords = [
        # === 米哈游本体 (6) ===
        ("米哈游", MIHOYO_GAME), ("miHoYo", MIHOYO_GAME),
        ("米忽悠", MIHOYO_GAME), ("mhy", MIHOYO_GAME),
        ("大伟哥", MIHOYO_GAME), ("蔡浩宇", MIHOYO_GAME),

        # === 原神 (55) ===
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
        ("至冬", MIHOYO_GAME), ("层岩巨渊", MIHOYO_GAME), ("鹤观", MIHOYO_GAME),
        ("渊下宫", MIHOYO_GAME), ("神樱树", MIHOYO_GAME), ("恒常果列", MIHOYO_GAME),
        ("旅行者", MIHOYO_CHAR), ("空", MIHOYO_CHAR), ("荧", MIHOYO_CHAR),
        ("阿贝多", MIHOYO_CHAR), ("优菈", MIHOYO_CHAR), ("一斗", MIHOYO_CHAR),
        ("五郎", MIHOYO_CHAR), ("心海", MIHOYO_CHAR), ("托马", MIHOYO_CHAR),
        ("九条裟罗", MIHOYO_CHAR), ("早柚", MIHOYO_CHAR), ("辛焱", MIHOYO_CHAR),
        ("烟绯", MIHOYO_CHAR), ("行秋", MIHOYO_CHAR), ("香菱", MIHOYO_CHAR),
        ("重云", MIHOYO_CHAR), ("诺艾尔", MIHOYO_CHAR), ("菲谢尔", MIHOYO_CHAR),
        ("芭芭拉", MIHOYO_CHAR), ("迪奥娜", MIHOYO_CHAR), ("莫娜", MIHOYO_CHAR),
        ("凝光", MIHOYO_CHAR), ("北斗", MIHOYO_CHAR), ("辛焱", MIHOYO_CHAR),

        # === 星穹铁道 (50) ===
        ("崩坏：星穹铁道", MIHOYO_GAME), ("星穹铁道", MIHOYO_GAME), ("崩坏星穹铁道", MIHOYO_GAME),
        ("三月七", MIHOYO_CHAR), ("丹恒", MIHOYO_CHAR), ("景元", MIHOYO_CHAR),
        ("卡芙卡", MIHOYO_CHAR), ("银狼", MIHOYO_CHAR), ("刃", MIHOYO_CHAR),
        ("流萤", MIHOYO_CHAR), ("知更鸟", MIHOYO_CHAR), ("姬子", MIHOYO_CHAR),
        ("瓦尔特", MIHOYO_CHAR), ("希儿", MIHOYO_CHAR), ("布洛妮娅", MIHOYO_CHAR),
        ("罗刹", MIHOYO_CHAR), ("符玄", MIHOYO_CHAR), ("镜流", MIHOYO_CHAR),
        ("阮梅", MIHOYO_CHAR), ("黑塔", MIHOYO_CHAR),
        ("差分宇宙", MIHOYO_GAME), ("模拟宇宙", MIHOYO_GAME),
        ("忘却之庭", MIHOYO_GAME), ("匹诺康尼", MIHOYO_GAME),
        ("仙舟", MIHOYO_GAME), ("雅利洛", MIHOYO_GAME), ("空间站", MIHOYO_GAME),
        ("开拓者", MIHOYO_CHAR), ("停云", MIHOYO_CHAR), ("花火", MIHOYO_CHAR),
        ("藿藿", MIHOYO_CHAR), ("寒鸦", MIHOYO_CHAR), ("银枝", MIHOYO_CHAR),
        ("真理医生", MIHOYO_CHAR), ("记忆主", MIHOYO_CHAR), ("欢愉主", MIHOYO_CHAR),
        ("虚无主", MIHOYO_CHAR), ("存护主", MIHOYO_CHAR), ("丰饶主", MIHOYO_CHAR),
        ("毁灭主", MIHOYO_CHAR), ("巡猎主", MIHOYO_CHAR),
        ("星期日", MIHOYO_CHAR), ("飞霄", MIHOYO_CHAR), ("椒丘", MIHOYO_CHAR),
        ("灵砂", MIHOYO_CHAR), ("貊泽", MIHOYO_CHAR), ("刻律德菈", MIHOYO_CHAR),
        ("伯恩恒", MIHOYO_CHAR), ("云璃", MIHOYO_CHAR), ("斯沃克", MIHOYO_CHAR),
        ("乱破", MIHOYO_CHAR), ("明霄", MIHOYO_CHAR), ("归终", MIHOYO_CHAR),

        # === 崩坏3 (25) ===
        ("崩坏3", MIHOYO_GAME), ("崩坏三", MIHOYO_GAME), ("崩坏3rd", MIHOYO_GAME),
        ("琪亚娜", MIHOYO_CHAR), ("芽衣", MIHOYO_CHAR), ("八重樱", MIHOYO_CHAR),
        ("爱莉希雅", MIHOYO_CHAR), ("无量塔姬子", MIHOYO_CHAR),
        ("德丽莎", MIHOYO_CHAR), ("符华", MIHOYO_CHAR),
        ("理之律者", MIHOYO_GAME), ("空之律者", MIHOYO_GAME),
        ("后崩坏书", MIHOYO_GAME), ("往世乐土", MIHOYO_GAME),
        ("律者", MIHOYO_GAME), ("崩坏兽", MIHOYO_GAME),
        ("幽兰黛尔", MIHOYO_CHAR), ("布洛妮娅", MIHOYO_CHAR),
        ("丽塔", MIHOYO_CHAR), ("李素裳", MIHOYO_CHAR),
        ("爱衣", MIHOYO_CHAR), ("维尔薇", MIHOYO_CHAR),
        ("始源之律者", MIHOYO_GAME), ("终焉之律者", MIHOYO_GAME),
        ("人之律者", MIHOYO_GAME), ("真我之人", MIHOYO_CHAR),

        # === 绝区零 (20) ===
        ("绝区零", MIHOYO_GAME), ("Zenless Zone Zero", MIHOYO_GAME),
        ("安比", MIHOYO_CHAR), ("妮可", MIHOYO_CHAR), ("比利", MIHOYO_CHAR),
        ("猫又", MIHOYO_CHAR), ("艾莲", MIHOYO_CHAR), ("朱鸢", MIHOYO_CHAR),
        ("青衣", MIHOYO_CHAR), ("新艾利都", MIHOYO_GAME),
        ("绳匠", MIHOYO_GAME), ("法厄同", MIHOYO_GAME),
        ("格莉丝", MIHOYO_CHAR), ("珂蕾妲", MIHOYO_CHAR), ("11号", MIHOYO_CHAR),
        ("莱卡恩", MIHOYO_CHAR), ("柏妮思", MIHOYO_CHAR), ("耀嘉音", MIHOYO_CHAR),
        ("虚狩", MIHOYO_GAME), ("以骸", MIHOYO_GAME),

        # === 未定事件簿 (5) ===
        ("未定事件簿", MIHOYO_GAME), ("陆景和", MIHOYO_CHAR), ("左然", MIHOYO_CHAR),
        ("夏彦", MIHOYO_CHAR), ("莫弈", MIHOYO_CHAR),

        # === 崩坏：星穹铁道 (5) ===
        ("何者", MIHOYO_GAME), ("星铁OP", MIHOYO_GAME), ("星铁动画", MIHOYO_GAME),
        ("银河球棒侠", MIHOYO_CHAR), ("无名客", MIHOYO_CHAR),

        # === 米哈游其他产品 (10) ===
        ("鹿隐村", MIHOYO_GAME), ("原神动画", MIHOYO_GAME),
        ("绝区零二测", MIHOYO_GAME), ("绝区零三测", MIHOYO_GAME),
        ("星铁前瞻", MIHOYO_GAME), ("原神前瞻", MIHOYO_GAME),
        ("HoYoverse", MIHOYO_GAME), ("Hoyo", MIHOYO_GAME),
        ("米游社", MIHOYO_GAME), ("HoYoLAB", MIHOYO_GAME),

        # === 竞品游戏 (35) ===
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
        ("阴阳师", COMPETITOR), ("决战平安京", COMPETITOR),
        ("王者荣耀", COMPETITOR), ("和平精英", COMPETITOR),
        ("英雄联盟手游", COMPETITOR), ("逆水寒手游", COMPETITOR),
        ("天谕手游", COMPETITOR), ("天刀手游", COMPETITOR),
        ("梦幻新诛仙", COMPETITOR), ("斗罗大陆", COMPETITOR),
        ("火影忍者手游", COMPETITOR),

        # === 竞品角色 (20) ===
        ("博士", COMPETITOR), ("阿米娅", COMPETITOR), ("凯尔希", COMPETITOR),
        ("伤痕", COMPETITOR), ("漂泊者", COMPETITOR), ("吟霖", COMPETITOR),
        ("暖暖", COMPETITOR), ("安洁莉娜", COMPETITOR),
        ("马娘", COMPETITOR), ("御主", COMPETITOR),
        ("鲁路修", COMPETITOR), ("初音未来", COMPETITOR),
        ("刻耳柏洛斯", COMPETITOR), ("守岸人", COMPETITOR),
        ("烛煌", COMPETITOR), ("红云", COMPETITOR),
        ("芙提雅", COMPETITOR), ("莫尔索", COMPETITOR),
        ("亚索", COMPETITOR), ("瑶", COMPETITOR),

        # === 二游圈通用术语 (60) ===
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
        ("黑红", GENERAL), ("强度党", GENERAL), ("XP党", GENERAL),
        ("厨力放出", GENERAL), ("氪金", GENERAL), ("零氪", GENERAL),
        ("月卡", GENERAL), ("战双帕弥什", GENERAL), ("碧蓝幻想", GENERAL),
        ("公主连结", GENERAL), ("少前", GENERAL), ("舰C", GENERAL),
        ("FGO国服", GENERAL), ("B服", GENERAL), ("官服", GENERAL),
        ("IOS服", GENERAL), ("安卓", GENERAL), ("渠道服", GENERAL),
        (" TapTap ", GENERAL), ("好游快爆", GENERAL), ("小黑盒", GENERAL),

        # === 舆论情感词-负面 (50) ===
        ("差评", "sentiment_neg"), ("垃圾", "sentiment_neg"), ("恶心", "sentiment_neg"),
        ("退坑", "sentiment_neg"), ("弃坑", "sentiment_neg"), ("失望", "sentiment_neg"),
        ("摆烂", "sentiment_neg"), ("数值膨胀", "sentiment_neg"), ("逼氪", "sentiment_neg"),
        ("骗氪", "sentiment_neg"), ("扣", "sentiment_neg"), ("敷衍", "sentiment_neg"),
        ("翻车", "sentiment_neg"), ("节奏", "sentiment_neg"), ("bug", "sentiment_neg"),
        ("BUG", "sentiment_neg"), ("抄袭", "sentiment_neg"), ("炎上", "sentiment_neg"),
        ("烂", "sentiment_neg"), ("骂", "sentiment_neg"), ("喷", "sentiment_neg"),
        ("吐槽", "sentiment_neg"), ("暴跌", "sentiment_neg"), ("凉凉", "sentiment_neg"),
        ("暴死", "sentiment_neg"), ("喂史", "sentiment_neg"), ("狗都不玩", "sentiment_neg"),
        ("逆天", "sentiment_neg"), ("无聊", "sentiment_neg"), ("垃圾游戏", "sentiment_neg"),
        ("退钱", "sentiment_neg"), ("退款", "sentiment_neg"), ("举报", "sentiment_neg"),
        ("和谐", "sentiment_neg"), ("暗改", "sentiment_neg"), ("削弱", "sentiment_neg"),
        ("背刺", "sentiment_neg"), ("撕卡", "sentiment_neg"), ("膨胀", "sentiment_neg"),
        ("骗钱", "sentiment_neg"), ("阴间", "sentiment_neg"), ("答辩", "sentiment_neg"),
        ("粪作", "sentiment_neg"), ("逼肝", "sentiment_neg"), ("坐牢", "sentiment_neg"),
        ("电子盆栽", "sentiment_neg"), ("阴兵", "sentiment_neg"), ("注水", "sentiment_neg"),
        ("缝合怪", "sentiment_neg"), ("换皮", "sentiment_neg"), ("割韭菜", "sentiment_neg"),

        # === 舆论情感词-正面 (45) ===
        ("好评", "sentiment_pos"), ("神作", "sentiment_pos"), ("吹爆", "sentiment_pos"),
        ("入坑", "sentiment_pos"), ("真香", "sentiment_pos"), ("惊艳", "sentiment_pos"),
        ("厉害", "sentiment_pos"), ("牛逼", "sentiment_pos"), ("震撼", "sentiment_pos"),
        ("良心", "sentiment_pos"), ("完美", "sentiment_pos"), ("优秀", "sentiment_pos"),
        ("美", "sentiment_pos"), ("燃", "sentiment_pos"), ("感动", "sentiment_pos"),
        ("哭了", "sentiment_pos"), ("用心", "sentiment_pos"), ("巅峰", "sentiment_pos"),
        ("越来越", "sentiment_pos"), ("顶级", "sentiment_pos"), ("封神", "sentiment_pos"),
        ("无敌", "sentiment_pos"), ("起飞", "sentiment_pos"), ("爽", "sentiment_pos"),
        ("爱了", "sentiment_pos"), ("宝藏", "sentiment_pos"), ("惊喜", "sentiment_pos"),
        ("绝美", "sentiment_pos"), ("细节满满", "sentiment_pos"), ("沉浸", "sentiment_pos"),
        ("好玩", "sentiment_pos"), ("精致", "sentiment_pos"), ("良心企业", "sentiment_pos"),
        ("业界标杆", "sentiment_pos"), ("国产之光", "sentiment_pos"),
        ("yyds", "sentiment_pos"), ("永远滴神", "sentiment_pos"),
        ("太强了", "sentiment_pos"), ("太美了", "sentiment_pos"),
        ("必须吹", "sentiment_pos"), ("安利", "sentiment_pos"),
        ("种草", "sentiment_pos"), ("上头", "sentiment_pos"), ("真不错", "sentiment_pos"),
        ("好评如潮", "sentiment_pos"),

        # === 社区/平台术语 (30) ===
        ("B站", "platform"), ("哔哩哔哩", "platform"), ("bilibili", "platform"),
        ("UP主", "platform"), ("弹幕", "platform"), ("投币", "platform"),
        ("一键三连", "platform"), ("点赞", "platform"), ("收藏", "platform"),
        ("转发", "platform"), ("动态", "platform"), ("专栏", "platform"),
        ("视频", "platform"), ("直播", "platform"), ("舰长", "platform"),
        ("SC", "platform"), ("醒目留言", "platform"), ("高能", "platform"),
        ("播放量", "platform"), ("弹幕数", "platform"), ("评论区", "platform"),
        ("楼中楼", "platform"), ("回复", "platform"), ("@@", "platform"),
        ("关注", "platform"), ("粉丝", "platform"), ("牌面", "platform"),
        ("热门", "platform"), ("推荐", "platform"), ("热搜", "platform"),

        # === 米哈游CV (70) ===
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
        ("宴俊", MIHOYO_GAME), ("杨超然", MIHOYO_GAME), ("丁润苍", MIHOYO_GAME),
        ("关帅", MIHOYO_GAME), ("唐雅菁", MIHOYO_GAME), ("林朗均", MIHOYO_GAME),
        ("陈亦承", MIHOYO_GAME), ("韩佳怡", MIHOYO_GAME), ("陈昊卿", MIHOYO_GAME),
        ("周杉", MIHOYO_GAME), ("蒋巍", MIHOYO_GAME),

        # === 游戏系统/机制术语 (40) ===
        ("圣遗物", "game_mechanic"), ("武器", "game_mechanic"),
        ("天赋", "game_mechanic"), ("突破", "game_mechanic"),
        ("精炼", "game_mechanic"), ("命座", "game_mechanic"),
        ("元素反应", "game_mechanic"), ("蒸发", "game_mechanic"),
        ("融化", "game_mechanic"), ("超载", "game_mechanic"),
        ("感电", "game_mechanic"), ("冻结", "game_mechanic"),
        ("扩散", "game_mechanic"), ("绽放", "game_mechanic"),
        ("光锥", "game_mechanic"), ("遗器", "game_mechanic"),
        ("行迹", "game_mechanic"), ("星魂", "game_mechanic"),
        ("专武", "game_mechanic"), ("绘卷", "game_mechanic"),
        ("模拟宇宙", "game_mechanic"), ("忘却之庭", "game_mechanic"),
        ("深境螺旋", "game_mechanic"), ("海灯节", "game_mechanic"),
        ("风花节", "game_mechanic"), ("逐月节", "game_mechanic"),
        ("归凤祭", "game_mechanic"), ("振晶的复核实验", "game_mechanic"),
        ("幻想真境剧诗", "game_mechanic"), ("混沌回忆", "game_mechanic"),
        ("末日幻影", "game_mechanic"), ("无尽位面", "game_mechanic"),
        ("虚卒", "game_mechanic"), ("式舆防卫战", "game_mechanic"),
        ("聚灵击破", "game_mechanic"), ("灼烧", "game_mechanic"),
        ("电击", "game_mechanic"), ("风化", "game_mechanic"),
        ("物理击破", "game_mechanic"),

        # === 玩家群体/社区称呼 (30) ===
        ("旅行者", "player_group"), ("开拓者", "player_group"),
        ("舰长", "player_group"), ("指挥官", "player_group"),
        ("绳匠", "player_group"), ("律师", "player_group"),
        ("博士", "player_group"), ("驯兽师", "player_group"),
        ("海坊主", "player_group"), ("刀客塔", "player_group"),
        ("御主", "player_group"),("Master", "player_group"),
        ("训练师", "player_group"),("舰长", "player_group"),
        ("酋长", "player_group"), ("欧皇", "player_group"),
        ("非酋", "player_group"), ("海豹", "player_group"),
        ("咸鱼", "player_group"), ("大佬", "player_group"),
        ("萌新", "player_group"), ("小白", "player_group"),
        ("老玩家", "player_group"), ("开服玩家", "player_group"),
        ("回坑玩家", "player_group"), ("退坑玩家", "player_group"),
        ("云玩家", "player_group"), ("云考据", "player_group"),
        ("数据帝", "player_group"), ("强度党", "player_group"),
        ("厨力党", "player_group"),

        # === 原神新增角色/地名 (40) ===
        ("克洛琳德", MIHOYO_CHAR), ("希诺宁", MIHOYO_CHAR), ("玛拉妮", MIHOYO_CHAR),
        ("基尼奇", MIHOYO_CHAR), ("恰斯卡", MIHOYO_CHAR), ("茜特菈莉", MIHOYO_CHAR),
        ("赛索斯", MIHOYO_CHAR), ("欧洛伦", MIHOYO_CHAR), ("卡齐娜", MIHOYO_CHAR),
        ("姆米", MIHOYO_CHAR), ("伊安珊", MIHOYO_CHAR), ("伊涅芙", MIHOYO_CHAR),
        ("闲云", MIHOYO_CHAR), ("千织", MIHOYO_CHAR), ("嘉明", MIHOYO_CHAR),
        ("夏沃蕾", MIHOYO_CHAR), ("娜维娅", MIHOYO_CHAR), ("夏洛蒂", MIHOYO_CHAR),
        ("莱依拉", MIHOYO_CHAR), ("珐露珊", MIHOYO_CHAR), ("多莉", MIHOYO_CHAR),
        ("坎蒂丝", MIHOYO_CHAR), ("鹿野院平藏", MIHOYO_CHAR), ("五郎", MIHOYO_CHAR),
        ("久岐忍", MIHOYO_CHAR), ("荒泷一斗", MIHOYO_CHAR), ("荒泷派蒙", MIHOYO_CHAR),
        ("戴因斯雷布", MIHOYO_CHAR), ("凯瑟琳", MIHOYO_CHAR),
        ("提纳里", MIHOYO_CHAR), ("赛诺", MIHOYO_CHAR), ("艾尔海森", MIHOYO_CHAR),
        ("白术", MIHOYO_CHAR), ("卡维", MIHOYO_CHAR), ("莱欧斯利", MIHOYO_CHAR),
        ("那维莱特", MIHOYO_CHAR), ("夏洛蒂", MIHOYO_CHAR),("弗雷米特", MIHOYO_CHAR),
        ("林尼", MIHOYO_CHAR), ("琳妮特", MIHOYO_CHAR),

        # === 星铁新增角色 (25) ===
        ("白露", MIHOYO_CHAR), ("青雀", MIHOYO_CHAR), ("素裳", MIHOYO_CHAR),
        ("佩拉", MIHOYO_CHAR), ("杰帕德", MIHOYO_CHAR), ("克拉拉", MIHOYO_CHAR),
        ("史瓦罗", MIHOYO_CHAR), ("托帕", MIHOYO_CHAR), ("账账", MIHOYO_CHAR),
        ("桂乃芬", MIHOYO_CHAR), ("雪衣", MIHOYO_CHAR), ("幻胧", MIHOYO_CHAR),
        ("黄泉", MIHOYO_CHAR), ("砂金", MIHOYO_CHAR), ("花火", MIHOYO_CHAR),
        ("知更鸟", MIHOYO_CHAR), ("流萤", MIHOYO_CHAR), ("缇宝", MIHOYO_CHAR),
        ("大黑塔", MIHOYO_CHAR), ("星期日", MIHOYO_CHAR), ("阿格莱雅", MIHOYO_CHAR),
        ("波提欧", MIHOYO_CHAR), ("迷火", MIHOYO_CHAR), ("舍友", MIHOYO_CHAR),
        ("记忆主", MIHOYO_CHAR),

        # === 热梗/网络用语 (35) ===
        ("原神怎么你了", "meme"), ("原神启动", "meme"), ("原来你也玩原神", "meme"),
        ("启动！", "meme"), ("原来你是这样的旅行者", "meme"),
        ("星铁启动", "meme"), ("铁道怎么你了", "meme"),
        ("这游戏真好玩", "meme"), ("我从未见过如此厚颜无耻之人", "meme"),
        ("电子骨灰盒", "meme"), ("电子榨菜", "meme"),
        ("电子仙人掌", "meme"), ("电子宠物", "meme"),
        ("坐牢", "meme"), ("牢铁", "meme"), ("牢原", "meme"),
        ("牢崩", "meme"), ("牢零", "meme"),
        ("小保底", "meme"), ("大保底", "meme"), ("歪了七七", "meme"),
        ("定规", "meme"), ("跳过", "meme"),
        ("满命", "meme"), ("0命", "meme"), ("1命", "meme"),
        ("2命", "meme"), ("满精", "meme"),
        ("毕业", "meme"), ("小毕业", "meme"), ("大毕业", "meme"),
        ("下岗", "meme"), ("退环境", "meme"),

        # === 行业/商业术语 (25) ===
        ("流水", "industry"), ("营收", "industry"), ("DAU", "industry"),
        ("MAU", "industry"), ("ARPU", "industry"), ("ARPPU", "industry"),
        ("LTV", "industry"), ("CAC", "industry"), ("留存率", "industry"),
        ("付费率", "industry"), ("转化率", "industry"), ("日活", "industry"),
        ("月活", "industry"), ("畅销榜", "industry"), ("免费榜", "industry"),
        ("Taptap评分", "industry"), ("App Store", "industry"),
        ("Google Play", "industry"), ("Steam", "industry"),
        ("买量", "industry"), ("获客成本", "industry"), ("ROI", "industry"),
        ("KPI", "industry"), ("OKR", "industry"), ("Q1", "industry"),
        ("Q2", "industry"), ("Q3", "industry"), ("Q4", "industry"),

        # === 二次元文化/ACG (30) ===
        ("二次元", "acg"), ("动漫", "acg"), ("番剧", "acg"),
        ("声优", "acg"), ("CV", "acg"), ("cosplay", "acg"),
        ("Cos", "acg"), ("漫展", "acg"), ("同人", "acg"),
        ("二创", "acg"), ("手办", "acg"), ("周边", "acg"),
        ("谷子", "acg"), ("吧唧", "acg"), ("立牌", "acg"),
        ("痛包", "acg"), ("应援棒", "acg"), ("打call", "acg"),
        ("萌", "acg"), ("傲娇", "acg"), ("病娇", "acg"),
        ("腹黑", "acg"), ("元气", "acg"), ("三无", "acg"),
        ("萝莉", "acg"), ("正太", "acg"), ("御姐", "acg"),
        ("大叔", "acg"), ("乙女", "acg"), ("耽美", "acg"),
        ("BL", "acg"), ("GL", "acg"),

        # === B站/视频圈特色 (25) ===
        ("一键三连", "bili_slang"), ("下次一定", "bili_slang"),
        ("只有我看懂了吗", "bili_slang"), ("前方高能", "bili_slang"),
        ("注意看", "bili_slang"), ("这个男人叫", "bili_slang"),
        ("细品", "bili_slang"), ("绝了", "bili_slang"),
        ("破防了", "bili_slang"), ("蚌埠住了", "bili_slang"),
        ("我真的会谢", "bili_slang"), ("芭比Q了", "bili_slang"),
        ("栓Q", "bili_slang"), ("尊嘟假嘟", "bili_slang"),
        ("泰裤辣", "bili_slang"), ("显眼包", "bili_slang"),
        ("纯纯的", "bili_slang"), ("真的假的", "bili_slang"),
        ("家人们", "bili_slang"), ("谁懂啊", "bili_slang"),
        ("狠狠地", "bili_slang"), ("直接", "bili_slang"),
        ("属于是", "bili_slang"), ("基本上", "bili_slang"),
        ("怎么说呢", "bili_slang"), ("有一说一", "bili_slang"),

        # === 更多竞品/泛娱乐 (20) ===
        ("第五人格", COMPETITOR), ("蛋仔派对", COMPETITOR),
        ("光遇", COMPETITOR), ("我的世界", COMPETITOR),
        ("迷你世界", COMPETITOR), ("香肠派对", COMPETITOR),
        ("荒野行动", COMPETITOR), ("QQ飞车手游", COMPETITOR),
        ("跑跑卡丁车手游", COMPETITOR), ("决战平安京", COMPETITOR),
        ("三国志战略版", COMPETITOR), ("率土之滨", COMPETITOR),
        ("万国觉醒", COMPETITOR), ("部落冲突", COMPETITOR),
        ("皇室战争", COMPETITOR), ("炉石传说", COMPETITOR),
        ("阴阳师百闻牌", COMPETITOR), ("碧蓝航线", COMPETITOR),
        ("少女前线", COMPETITOR), ("战双帕弥什", COMPETITOR),
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
