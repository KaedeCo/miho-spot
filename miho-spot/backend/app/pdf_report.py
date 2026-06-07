"""
PDF Report Generator for Miho-spot v2.1 — modular, with DeepSeek AI, TOC links, page numbers.
格式参考：武汉大学《多核架构及编程技术 实验指导书》A4/宋体12pt
"""
import io, os, json, re, traceback, copy
from io import BytesIO
from datetime import datetime
from collections import defaultdict

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image, Table,
                                 TableStyle, PageBreak, Flowable)
from reportlab.platypus.flowables import HRFlowable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ======================================================================
#  Font Setup
# ======================================================================
_FONT_SIMSUN = None; _FONT_TNR = None; _FONT_CAMBRIA = None; _FONT_CASCADIA = None

for _f in ["C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/simsun.ttf"]:
    if os.path.exists(_f): _FONT_SIMSUN = _f; break
for _f in ["C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/times.ttc"]:
    if os.path.exists(_f): _FONT_TNR = _f; break
for _f in ["C:/Windows/Fonts/cambria.ttc", "C:/Windows/Fonts/cambriamath.ttf",
           "C:/Windows/Fonts/cambria.ttf"]:
    if os.path.exists(_f): _FONT_CAMBRIA = _f; break
for _f in ["C:/Windows/Fonts/CascadiaCode.ttf", "C:/Windows/Fonts/cascadia.ttf",
           "C:/Windows/Fonts/Cascadia.ttf"]:
    if os.path.exists(_f): _FONT_CASCADIA = _f; break

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

if _FONT_SIMSUN: pdfmetrics.registerFont(TTFont("SimSun", _FONT_SIMSUN))
if _FONT_TNR: pdfmetrics.registerFont(TTFont("TimesNewRoman", _FONT_TNR))
if _FONT_CAMBRIA: pdfmetrics.registerFont(TTFont("CambriaMath", _FONT_CAMBRIA))
if _FONT_CASCADIA: pdfmetrics.registerFont(TTFont("CascadiaCode", _FONT_CASCADIA))

FONT_CN = "SimSun" if _FONT_SIMSUN else "Helvetica"
FONT_EN = "TimesNewRoman" if _FONT_TNR else FONT_CN
FONT_MT = "CambriaMath" if _FONT_CAMBRIA else FONT_CN
FONT_CD = "CascadiaCode" if _FONT_CASCADIA else "Courier"

_CJK_MPL = None
for _f in ["C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/msyh.ttc",
           "C:/Windows/Fonts/simhei.ttf"]:
    if os.path.exists(_f): _CJK_MPL = _f; break
if _CJK_MPL:
    plt.rcParams["font.family"] = matplotlib.font_manager.FontProperties(
        fname=_CJK_MPL).get_name()
plt.rcParams["axes.unicode_minus"] = False

# ======================================================================
#  Style Definitions
# ======================================================================
MARGIN_L = 20 * mm; MARGIN_R = 18 * mm
MARGIN_T = 26 * mm; MARGIN_B = 16 * mm

CHAP_STYLE = ParagraphStyle("Chapter", fontName=FONT_CN, fontSize=16, leading=24,
                             textColor=black, spaceAfter=10, spaceBefore=18,
                             alignment=TA_CENTER)
SEC_STYLE = ParagraphStyle("Section", fontName=FONT_CN, fontSize=14, leading=20,
                            textColor=HexColor("#1e40af"), spaceAfter=8, spaceBefore=12)
SUB_STYLE = ParagraphStyle("SubSection", fontName=FONT_CN, fontSize=13, leading=19,
                             textColor=HexColor("#3b82f6"), spaceAfter=6, spaceBefore=10)
BODY_STYLE = ParagraphStyle("Body", fontName=FONT_CN, fontSize=12, leading=20,
                             textColor=black, spaceAfter=4, firstLineIndent=24)
BODY_NO_INDENT = ParagraphStyle("BodyNI", fontName=FONT_CN, fontSize=12, leading=20,
                                 textColor=black, spaceAfter=4)
SMALL_STYLE = ParagraphStyle("Small", fontName=FONT_CN, fontSize=9, leading=14,
                              textColor=HexColor("#64748b"))
CENTER_STYLE = ParagraphStyle("Center", fontName=FONT_CN, fontSize=12, leading=20,
                               textColor=black, alignment=TA_CENTER)
CAPTION_STYLE = ParagraphStyle("Caption", fontName=FONT_CN, fontSize=10, leading=14,
                                textColor=HexColor("#475569"), alignment=TA_CENTER,
                                spaceBefore=6, spaceAfter=4)
FORMULA_STYLE = ParagraphStyle("Formula", fontName=FONT_MT, fontSize=11, leading=16,
                                textColor=black, alignment=TA_CENTER,
                                spaceBefore=4, spaceAfter=4)
TITLE_STYLE = ParagraphStyle("Title", fontName=FONT_CN, fontSize=22, leading=30,
                              textColor=black, alignment=TA_CENTER, spaceAfter=12)
COVER_LABEL = ParagraphStyle("CoverLbl", fontName=FONT_CN, fontSize=14, leading=22,
                              textColor=black, alignment=TA_CENTER, spaceAfter=4)
COVER_INFO = ParagraphStyle("CoverInfo", fontName=FONT_CN, fontSize=12, leading=20,
                             textColor=HexColor("#475569"), alignment=TA_CENTER, spaceAfter=2)
TOC_ENTRY = ParagraphStyle("TOCEntry", fontName=FONT_CN, fontSize=12, leading=24,
                            textColor=black, spaceAfter=4, leftIndent=8)

# ======================================================================
#  Figure/Table Numbering
# ======================================================================
_fig_cnt = defaultdict(int)
_tbl_cnt = defaultdict(int)

def fig_label(ch: str) -> str:
    _fig_cnt[ch] += 1; return f"图{ch}.{_fig_cnt[ch]}"

def tbl_label(ch: str) -> str:
    _tbl_cnt[ch] += 1; return f"表{ch}.{_tbl_cnt[ch]}"

def reset_counters():
    _fig_cnt.clear(); _tbl_cnt.clear()


# ======================================================================
#  Text helpers — Times New Roman for English/numerals
# ======================================================================

def _en_tnr(text: str) -> str:
    """Wrap English words and standalone numbers in TimesNewRoman font tags.
    Skips text already inside HTML tags, and skips formula/code sections."""
    if not _FONT_TNR:
        return text
    
    # Split by existing HTML tags to avoid double-wrapping
    parts = re.split(r'(<[^>]+>)', text)
    result = []
    for part in parts:
        if part.startswith('<'):
            result.append(part)
        else:
            # Wrap English words (2+ letters, may start lowercase)
            part = re.sub(r'\b([A-Za-z]{2,}[A-Za-z.-]*)\b',
                          r'<font face="TimesNewRoman">\1</font>', part)
            # Wrap standalone numbers (except those already in sub/super tags)
            part = re.sub(r'(?<![>a-zA-Z0-9])(\d+(?:\.\d+)?)(?![<0-9a-zA-Z])',
                          r'<font face="TimesNewRoman">\1</font>', part)
            result.append(part)
    return ''.join(result)


def _p(text: str, style=None) -> Paragraph:
    """Create Paragraph with automatic TNR wrapping for English/numbers."""
    return Paragraph(_en_tnr(text), style or BODY_STYLE)


def _pni(text: str, style=None) -> Paragraph:
    """No-indent Paragraph with TNR wrapping."""
    return Paragraph(_en_tnr(text), style or BODY_NO_INDENT)


def _cell(text: str, style=None) -> Paragraph:
    st = style or ParagraphStyle("Tc", fontName=FONT_CN, fontSize=9, leading=13,
                                  textColor=black, wordWrap="CJK")
    return Paragraph(_en_tnr(text), st)


def _md_to_html(text: str) -> str:
    """Convert common Markdown patterns to ReportLab-compatible HTML markup."""
    import html as html_module
    # Decode HTML entities first (e.g. &nbsp; &amp; &lt; &gt;)
    text = html_module.unescape(text)
    # Headers
    text = re.sub(r"^####\s+(.+)", r"<b>\1</b>", text, flags=re.MULTILINE)
    text = re.sub(r"^###\s+(.+)", r"<font size='12' color='#1e40af'><b>\1</b></font>", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+(.+)", r"<font size='13' color='#2563eb'><b>\1</b></font>", text, flags=re.MULTILINE)
    # Bold / italic
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", text)
    # Numbered lists
    text = re.sub(r"^(\d+)\.\s+(.+)", r"• \2", text, flags=re.MULTILINE)
    # Bullet lists
    text = re.sub(r"^- (.+)", r"• \1", text, flags=re.MULTILINE)
    text = re.sub(r"^\* (.+)", r"• \1", text, flags=re.MULTILINE)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"<font face='CascadiaCode' size='9'>\1</font>", text)
    # Clean up excessive newlines but keep paragraph breaks
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _call_deepseek(prompt: str, api_key: str, max_tokens=800,
                    temperature=0.5, timeout=90) -> str:
    import httpx
    resp = httpx.post("https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"model": "deepseek-chat",
              "messages": [{"role": "user", "content": prompt}],
              "max_tokens": max_tokens, "temperature": temperature},
        timeout=timeout)
    return resp.json()["choices"][0]["message"]["content"].strip()


# ======================================================================
#  Image helper
# ======================================================================

def _image_from_fig(fig, width=460, max_height=380) -> Image:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    plt.close(fig)
    return Image(buf, width=width, height=max_height, kind="proportional")


# ======================================================================
#  Bookmark flowable (for two-pass TOC with page numbers)
# ======================================================================

class BookmarkFlowable(Flowable):
    """Invisible flowable that registers a PDF bookmark and records page number."""
    def __init__(self, key: str, tracker: dict):
        Flowable.__init__(self)
        self.key = key
        self.tracker = tracker
        self.width = 0
        self.height = 0

    def draw(self):
        self.canv.bookmarkPage(self.key)
        self.tracker[self.key] = self.canv.getPageNumber()


# ======================================================================
#  Page number callback
# ======================================================================

def _page_number_callback(canvas, doc):
    """Draw page number at bottom center on every page."""
    canvas.saveState()
    canvas.setFont(FONT_CN, 9)
    canvas.setFillColor(HexColor("#64748b"))
    num = canvas.getPageNumber()
    canvas.drawCentredString(A4[0] / 2, 15 * mm, str(num))
    canvas.restoreState()


# ======================================================================
#  Chapter numbering resolver
# ======================================================================

def _resolve_module_order(modules: list, ds_api_key: str = None):
    _cn = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
    ordered = []
    non_overview = [m for m in modules if m != "overview"]
    has_overview = "overview" in modules
    if ds_api_key and has_overview:
        for i, m in enumerate(non_overview):
            ordered.append((m, _cn[i], i + 1))
        ordered.append(("overview", _cn[len(non_overview)], len(non_overview) + 1))
    else:
        for i, m in enumerate(modules):
            ordered.append((m, _cn[i], i + 1))
    return ordered

def _get_module_label(mod_key: str) -> str:
    return {
        "overview": "事件总览", "heatmap": "舆论地形图",
        "camps": "情感阵营分布", "trail": "时间轴推演——质心漂移轨迹",
        "clusters": "群体聚类画廊", "opposition": "高赞观点与对立面解析",
        "wordcloud": "词云与争议词", "users": "评论区用户图谱",
        "ai_summary": "AI综合研判摘要",
    }.get(mod_key, mod_key)


# ======================================================================
#  Module functions — unchanged logic, now using _p/_pni for TNR
# ======================================================================

def module_overview(story, saved_ot, saved_va, video_task, ch_num: str,
                     ds_api_key=None, db=None, ds_heatmap_analysis=None,
                     camps_data=None, cluster_summaries=None):
    story.append(_p(f"第{ch_num}章  事件总览", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.5, color=black))

    title = saved_ot and saved_ot.title or (video_task and video_task.title or "未知视频")
    bvid = saved_ot and saved_ot.bvid or (video_task and video_task.bvid or "")

    if ds_api_key and ds_heatmap_analysis and camps_data and cluster_summaries:
        parts = []
        if ds_heatmap_analysis:
            parts.append(f"【舆论地形图AI分析】\n{ds_heatmap_analysis}")
        if camps_data:
            parts.append(
                f"【情感阵营分布】\n反对:{camps_data.get('anti',0)}人"
                f"({camps_data.get('anti_pct',0):.1f}%) "
                f"中立:{camps_data.get('neutral',0)}人"
                f"({camps_data.get('neutral_pct',0):.1f}%) "
                f"支持:{camps_data.get('pro',0)}人"
                f"({camps_data.get('pro_pct',0):.1f}%)")
        if cluster_summaries:
            cl = "\n".join(f"- {s}" for s in cluster_summaries[:6])
            parts.append(f"【群体聚类总结】\n{cl}")
        prompt = f"""你是一位专业的舆情分析师。请基于以下B站视频《{title}》的评论分析数据，撰写一段400~500字的开门见山式的舆情事件总览。

{chr(10).join([chr(10)+p for p in parts])}

要求：语言精炼、开门见山、直接陈述核心发现。包含：视频引发的舆论总体态势、阵营分歧的关键张力、群体分布的主要特征。
直接输出概括文字，不要序号、不要JSON、不要分段标题。"""
        try:
            ai_overview = _call_deepseek(prompt, ds_api_key, max_tokens=1000,
                                          temperature=0.5, timeout=120)
            story.append(_p("AI事件总览：", SEC_STYLE))
            parsed_ov = _md_to_html(ai_overview)
            for line in parsed_ov.split("\n"):
                line = line.strip()
                if line:
                    story.append(_pni(line))
                else:
                    story.append(Spacer(1, 4))
            story.append(Spacer(1, 10))
        except Exception as e:
            story.append(Paragraph(
                _en_tnr(f"（AI总览生成失败：{e}，降级使用基础模式）"), SMALL_STYLE))

    total = (saved_ot and saved_ot.total_comments) or (video_task and video_task.total_comments or 0)
    analyzed = (saved_ot and saved_ot.analyzed_count) or (video_task and video_task.analyzed_count or 0)
    matched = (saved_va and saved_va.matched_count) or (video_task and video_task.matched_count or 0)
    cx = (saved_ot and saved_ot.centroid_x) or (video_task and video_task.centroid_x_no_origin or 0)
    cy = (saved_ot and saved_ot.centroid_y) or (video_task and video_task.centroid_y_no_origin or 0)

    story.append(_p(f"视频：{title}", SEC_STYLE))
    story.append(_pni(f"BV号：{bvid}"))
    story.append(_p(
        f"共采集 <b>{total}</b> 条评论，其中 <b>{matched}</b> 条命中游戏关键词，"
        f"成功生成 <b>{analyzed}</b> 组坐标。"))
    story.append(_p(
        f"修正质心（去中立）：({cx:.1f}, {cy:.1f}) —— "
        f"X轴0=反对/100=支持，Y轴0=理性/100=感性"))

    cover_url = (saved_ot and saved_ot.cover_url) or (video_task and video_task.cover_url or "")
    if cover_url:
        try:
            import httpx
            resp = httpx.get(cover_url, timeout=10)
            if resp.status_code == 200:
                story.append(Spacer(1, 6))
                story.append(Image(BytesIO(resp.content), width=240, height=180,
                                    kind="proportional"))
        except: pass
    story.append(Spacer(1, 12))


# ─────────────────────────────────────────────────────────

def module_heatmap(story, saved_ot, ch_num: str, ds_api_key=None,
                   db=None, video_task_id=None):
    story.append(_p(f"第{ch_num}章  舆论地形图", CHAP_STYLE))
    t = saved_ot and saved_ot.title or "未知视频"
    story.append(HRFlowable(width="100%", thickness=0.5, color=black))

    story.append(Paragraph(f"{fig_label(ch_num)} 舆论质心计算公式", CAPTION_STYLE))
    story.append(Paragraph(
        "C<sub>x</sub> = Σ(w<sub>i</sub>·x<sub>i</sub>) / Σw<sub>i</sub>",
        FORMULA_STYLE))
    story.append(Paragraph(
        "C<sub>y</sub> = Σ(w<sub>i</sub>·y<sub>i</sub>) / Σw<sub>i</sub>",
        FORMULA_STYLE))
    story.append(Paragraph(
        "其中 w<sub>i</sub>=1+log(1+like<sub>i</sub>)，坐标(x<sub>i</sub>,y<sub>i</sub>)∈[0,100]",
        ParagraphStyle("Fn", fontName=FONT_CN, fontSize=9, leading=13,
                        textColor=HexColor("#64748b"), alignment=TA_CENTER)))

    grid_data = None; cx, cy = 50.0, 50.0
    if saved_ot and saved_ot.heatmap_grid:
        grid_data = saved_ot.heatmap_grid
        cx = saved_ot.centroid_x or 50; cy = saved_ot.centroid_y or 50
    if not grid_data:
        story.append(_p("（无热力图数据）"))
        return ""

    arr = np.array(grid_data, dtype=float)
    if arr.shape != (101, 101):
        arr = arr.T if arr.shape == (101, 101) else np.zeros((101, 101))
    if arr.max() == 0: arr[50, 50] = 1

    try:
        from scipy.ndimage import gaussian_filter
        arr_bloom = gaussian_filter(arr, sigma=6.0)
    except ImportError:
        arr_bloom = arr

    fig, ax = plt.subplots(figsize=(7, 7))
    im = ax.imshow(np.flipud(arr_bloom.T), cmap="YlOrRd", extent=[0, 100, 0, 100],
                    aspect="equal", origin="lower", interpolation="bilinear",
                    vmin=0, vmax=max(arr_bloom.max() * 0.8, 1))

    # Scatter: every coordinate that has comments gets a small triangle
    # Also add larger halo circles for dense coordinates
    for gx in range(0, 101):
        for gy in range(0, 101):
            cnt = int(arr[gx, gy])
            if cnt > 0:
                # Small triangle marker at each occupied coordinate
                ax.plot(gx, gy, marker="^", color="#dc2626", markersize=3,
                        alpha=0.6, zorder=4)
                # Halo circle for dense points (>= 3 comments or top 10%)
                if cnt >= 3 or cnt >= arr[arr > 0].max() * 0.5:
                    radius = min(4, 1 + np.log1p(cnt) * 1.5)
                    circle = plt.Circle((gx, gy), radius, color="#ef4444",
                                       alpha=0.15, zorder=2)
                    ax.add_patch(circle)

    # Centroid golden triangle (larger, on top)
    ax.plot(cx, 100 - cy, marker="^", color="#f59e0b", markersize=16,
             markeredgecolor="#78350f", markeredgewidth=2, zorder=10)
    ax.axhline(50, color="white", alpha=0.3, linewidth=1)
    ax.axvline(50, color="white", alpha=0.3, linewidth=1)
    ax.set_xlabel("反对米哈游 ← → 支持米哈游")
    ax.set_ylabel("理性 ← → 感性")
    ax.set_title("舆论二维密度分布 + 整体质心(▲)")
    plt.colorbar(im, ax=ax, label="评论密度")
    story.append(_image_from_fig(fig))
    story.append(Paragraph(_en_tnr(f"整体质心：({cx:.1f}, {cy:.1f})"), CENTER_STYLE))

    ds_analysis = ""
    if ds_api_key:
        # Build grid JSON for overall distribution
        grid_json = {}
        for gx in range(0, 101, 10):
            for gy in range(0, 101, 10):
                xs_, xe_ = max(0, gx - 5), min(100, gx + 5)
                ys_, ye_ = max(0, gy - 5), min(100, gy + 5)
                cnt = int(arr[xs_:xe_+1, ys_:ye_+1].sum())
                if cnt > 0: grid_json[f"({gx},{gy})"] = cnt
        dense_points = sorted(grid_json.items(), key=lambda x: x[1], reverse=True)[:3]

        # Fetch actual comment samples per dense coordinate
        import random
        coord_comments = {}
        try:
            from app.models import VideoComment
            if db and video_task_id:
                all_coords = db.query(VideoComment).filter(
                    VideoComment.task_id == video_task_id,
                    VideoComment.coord_x >= 0, VideoComment.coord_y >= 0
                ).all()
            elif db and saved_ot:
                all_coords = []
                # Try to get all coords from saved_ot context
                pass
            else:
                all_coords = []

            for pt_str, cnt in dense_points:
                # Parse coordinate like "(30,70)"
                m = re.match(r'\((\d+),(\d+)\)', pt_str)
                if not m: continue
                px, py = int(m.group(1)), int(m.group(2))
                # Gather comments within ±5 of this grid center
                bucket = [c for c in all_coords
                         if abs(c.coord_x - px) <= 5 and abs(c.coord_y - py) <= 5]
                # Random sample up to 50
                if len(bucket) > 50:
                    bucket = random.sample(bucket, 50)
                samples = "\n".join(
                    f"  @{c.user}: {c.content[:150]} [赞{c.like_count}]"
                    for c in bucket)
                coord_comments[pt_str] = samples
        except Exception as e_coord:
            coord_comments = {}

        # Axis semantics explanation
        AXIS_CONTEXT = (
            "【坐标轴定义（必须严格遵循）】\n"
            "X轴：0=强烈反对米哈游，100=全力支持米哈游\n"
            "Y轴：0=完全理性分析，100=纯感性情绪表达\n"
            "这是B站视频评论区的舆论情感坐标系，不是地理位置！\n"
            f"当前视频：《{t}》\n"
            f"整体质心：({cx:.1f}, {cy:.1f})\n")

        # Overall analysis with axis context + actual samples
        try:
            overall_samples_text = ""
            for pt_str, samples in list(coord_comments.items())[:3]:
                overall_samples_text += f"\n--- {pt_str}区域评论样例 ---\n{samples}\n"

            ds_analysis = _call_deepseek(
                f"{AXIS_CONTEXT}\n"
                f"【各网格区域评论数统计】\n"
                f"{json.dumps(grid_json, ensure_ascii=False)}\n\n"
                f"【热点区域实际评论内容】\n{overall_samples_text}\n"
                f"请基于以上真实评论内容和分布数据，进行200字以内的舆情分析：\n"
                f"1. 评论主要集中在哪些舆论立场区间？\n"
                f"2. 支持方/反对方各自在讨论什么核心话题？\n"
                f"3. 理性派与感性派的论点差异是什么？\n"
                f"4. 是否存在明显的极化或共识趋势？\n"
                f"直接输出分析文字，不要JSON。",
                ds_api_key, max_tokens=500, temperature=0.3, timeout=90)
            if ds_analysis:
                story.append(Spacer(1, 8))
                story.append(_p("AI热力分布分析：", SEC_STYLE))
                story.append(_pni(_md_to_html(ds_analysis)))
        except: ds_analysis = ""

        # Per-dense-point deep analysis with real comments
        for pt_str, cnt in dense_points:
            try:
                samples = coord_comments.get(pt_str, "")
                if not samples:
                    p_pt = _call_deepseek(
                        f"坐标{pt_str}集中{cnt}条评论。100字分析该区域的舆论特征。"
                        f"注意：X轴是反对-支持米哈游，Y轴是理性-感性。",
                        ds_api_key, max_tokens=180, temperature=0.4, timeout=60)
                else:
                    p_pt = _call_deepseek(
                        f"{AXIS_CONTEXT}"
                        f"热点坐标{pt_str}聚集了{cnt}条评论，以下是该区域的真实评论内容：\n"
                        f"{samples}\n"
                        f"请用150字深度分析该区域用户的典型观点、情绪特征、核心论据和群体画像。"
                        f"直接输出分析文字。",
                        ds_api_key, max_tokens=300, temperature=0.4, timeout=60)
                if p_pt:
                    story.append(_p(f"热点坐标 {pt_str}（{cnt}条）：", SUB_STYLE))
                    story.append(_pni(_md_to_html(p_pt)))
            except: pass
    return ds_analysis


# ─────────────────────────────────────────────────────────

def module_camps(story, saved_ot, db, ch_num: str, ds_api_key=None, video_task_id=None):
    story.append(_p(f"第{ch_num}章  情感阵营分布", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.5, color=black))

    from app.models import VideoComment
    comments = []
    if video_task_id and db:
        comments = db.query(VideoComment).filter(
            VideoComment.task_id == video_task_id,
            VideoComment.coord_x >= 0, VideoComment.coord_y >= 0
        ).order_by(VideoComment.like_count.desc()).limit(500).all()
    if not comments:
        story.append(_p("（无评论坐标数据）"))
        return {}

    camps = {"反对": [], "中立": [], "支持": []}
    for c in comments:
        if c.coord_x < 40: camps["反对"].append(c)
        elif c.coord_x > 60: camps["支持"].append(c)
        else: camps["中立"].append(c)
    total = len(comments)

    story.append(Paragraph(f"{tbl_label(ch_num)} 情感阵营统计", CAPTION_STYLE))
    cr, cs_ = [], {}
    for name in ["反对", "中立", "支持"]:
        clist = camps[name]
        pct = len(clist) / total * 100 if total else 0
        avg_y = np.mean([c.coord_y for c in clist]) if clist else 0
        yl = "偏理性" if avg_y < 45 else ("偏感性" if avg_y > 55 else "中性")
        cr.append([_cell(name), _cell(str(len(clist))),
                   _cell(f"{pct:.1f}%"), _cell(f"{avg_y:.1f} ({yl})")])
        cs_[name] = {"count": len(clist), "pct": pct, "avg_y": avg_y}
    t = Table([[_cell("阵营"), _cell("人数"), _cell("占比"), _cell("平均理性度(Y)")]] + cr,
              colWidths=[70, 60, 60, 120])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#93c5fd")),
        ("TEXTCOLOR", (0, 0), (-1, 0), black),
        ("FONTNAME", (0, 0), (-1, -1), FONT_CN),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f8fafc"), white]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))

    for name in ["反对", "中立", "支持"]:
        clist = sorted(camps[name], key=lambda x: x.like_count, reverse=True)[:5]
        if not clist: continue
        story.append(_p(f"{name}阵营 — 点赞最高评论：", SEC_STYLE))
        for c in clist:
            story.append(Paragraph(
                _en_tnr(f"<b>@{c.user}</b> (赞{c.like_count}) "
                        f"[{c.coord_x},{c.coord_y}]：{c.content[:120]}"), SMALL_STYLE))
        if ds_api_key and len(clist) >= 3:
            samples = "\n".join(f"- @{c.user}: {c.content[:80]}" for c in clist[:5])
            try:
                s = _call_deepseek(
                    f"用一句话（20字以内）概括B站评论区{name}阵营的典型心态：\n{samples}\n请只返回概括文字。",
                    ds_api_key, max_tokens=60, temperature=0.3, timeout=30)
                if s:
                    story.append(Paragraph(
                        _en_tnr(f'<font color="#6366f1"><b>AI总结：</b>{_md_to_html(s)}</font>'),
                        BODY_STYLE))
            except: pass
        story.append(Spacer(1, 6))

    return {"anti": cs_["反对"]["count"], "anti_pct": cs_["反对"]["pct"],
            "neutral": cs_["中立"]["count"], "neutral_pct": cs_["中立"]["pct"],
            "pro": cs_["支持"]["count"], "pro_pct": cs_["支持"]["pct"]}


# ─────────────────────────────────────────────────────────

def module_trail(story, saved_ot, db, ch_num: str, ds_api_key=None, progress_cb=None):
    story.append(_p(f"第{ch_num}章  时间轴推演——质心漂移轨迹", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.5, color=black))

    story.append(Paragraph(f"{fig_label(ch_num)} 质心间欧氏距离公式", CAPTION_STYLE))
    story.append(Paragraph(
        "d(P<sub>i</sub>, P<sub>i+1</sub>) = "
        "√[(x<sub>i+1</sub>−x<sub>i</sub>)²+(y<sub>i+1</sub>−y<sub>i</sub>)²]",
        FORMULA_STYLE))

    trail = saved_ot and saved_ot.centroid_trail or []
    if not trail or len(trail) < 2:
        story.append(_p("（无漂移数据）"))
        return

    xs = [p["x"] for p in trail]; ys = [p["y"] for p in trail]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    pad_x = max(5, (x_max - x_min) * 0.2)
    pad_y = max(5, (y_max - y_min) * 0.2)
    vx0, vx1 = max(0, x_min - pad_x), min(100, x_max + pad_x)
    vy0, vy1 = max(0, y_min - pad_y), min(100, y_max + pad_y)

    ds_nodes = None
    if ds_api_key and len(trail) >= 5:
        td = "\n".join(
            f"节点{i}: 时间={trail[i].get('t','?')}, 质心=({xs[i]:.0f},{ys[i]:.0f}), "
            f"评论={trail[i].get('count',0)}" for i in range(len(trail)))
        try:
            if progress_cb: progress_cb(0, 3, "AI分析：选择关键节点...")
            r = _call_deepseek(
                f"以下B站舆论质心漂移{len(trail)}个节点。选5个转折最剧烈的：\n{td}\n只返回JSON如[0,3,7,12,19]。",
                ds_api_key, max_tokens=100, temperature=0.2, timeout=60)
            m = re.search(r'\[[\d,\s]+\]', r)
            if m: ds_nodes = [n for n in json.loads(m.group()) if 0 <= n < len(trail)][:5]
        except: pass
    if not ds_nodes:
        ds_nodes = [i for i in range(1, len(trail))
                     if np.sqrt((xs[i]-xs[i-1])**2+(ys[i]-ys[i-1])**2) > 12]
        if len(ds_nodes) < 5:
            step = max(1, len(trail) // 5)
            ds_nodes = list(range(0, len(trail), step))[:5]
        if ds_nodes and ds_nodes[0] != 0: ds_nodes = [0] + ds_nodes[:4]
        ds_nodes = ds_nodes[:5]

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_xlim(vx0, vx1); ax.set_ylim(vy0, vy1)
    ax.set_xlabel("反对 ← → 支持"); ax.set_ylabel("理性 ← → 感性")
    ax.set_title("质心漂移轨迹（智能缩放）")
    ax.axhline(50, color="gray", alpha=0.2, linestyle="--")
    ax.axvline(50, color="gray", alpha=0.2, linestyle="--")
    sizes = [max(5, p.get("count", 1) * 2) for p in trail]
    sc = ax.scatter(xs, ys, s=sizes, c=range(len(xs)), cmap="viridis", alpha=0.7, zorder=3)
    ax.plot(xs, ys, "gold", alpha=0.5, linewidth=1.5, zorder=2)
    for ni in ds_nodes:
        if ni < len(xs):
            ax.plot(xs[ni], ys[ni], marker="*", color="gold", markersize=14,
                     markeredgecolor="black", markeredgewidth=0.5, zorder=5)
    if len(xs) > 1:
        mid = len(xs) // 2
        ax.annotate("", xy=(xs[mid], ys[mid]), xytext=(xs[mid-1], ys[mid-1]),
                     arrowprops=dict(arrowstyle="->", color="red", lw=1.5))
    plt.colorbar(sc, ax=ax, label="时间顺序（早→晚）")
    story.append(_image_from_fig(fig))
    story.append(Paragraph(_en_tnr(
        f"显示范围：X [{vx0:.0f}, {vx1:.0f}] Y [{vy0:.0f}, {vy1:.0f}]"), CENTER_STYLE))
    story.append(Paragraph(_en_tnr(
        f"共 {len(trail)} 个时间节点，标记 {len(ds_nodes)} 个关键节点（★）"), CENTER_STYLE))

    if ds_api_key:
        from app.models import VideoComment
        all_comments = []
        if db and saved_ot:
            all_comments = db.query(VideoComment).filter(
                VideoComment.coord_x >= 0, VideoComment.coord_y >= 0
            ).order_by(VideoComment.ctime.asc()).all()
        for idx, ni in enumerate(ds_nodes[:5]):
            if progress_cb:
                progress_cb(idx + 1, len(ds_nodes) + 1,
                            f"AI分析：关键节点 {idx+1}/{len(ds_nodes)}...")
            t = trail[ni].get("t", f"节点{ni}")
            story.append(_p(f"关键节点{idx+1} — {t}：", SEC_STYLE))
            story.append(_p(
                f"质心 ({xs[ni]:.1f}, {ys[ni]:.1f})，评论 {trail[ni].get('count',0)} 条"))
            node_comments = []
            if all_comments and len(trail) > 1:
                sec = max(1, len(all_comments) // len(trail))
                si = ni * sec
                ei = min(len(all_comments), si + sec)
                node_comments = sorted(all_comments[si:ei],
                                       key=lambda x: x.like_count, reverse=True)[:10]
            if node_comments:
                ct = "\n".join(
                    f"  @{c.user}: {c.content[:100]} [赞{c.like_count}]" for c in node_comments)
                try:
                    a = _call_deepseek(
                        f"B站评论时间线关键转折\"{t}\"，质心({xs[ni]:.0f},{ys[ni]:.0f})。"
                        f"评论：\n{ct}\n\n100字分析舆论转向原因。直接输出。",
                        ds_api_key, max_tokens=200, temperature=0.5, timeout=60)
                    if a:
                        # Split into shorter paragraphs to avoid ReportLab
                        # truncation at page boundaries (single Paragraph
                        # flowable cannot span pages reliably for long text)
                        html_text = _en_tnr(f"<b>AI分析：</b>{_md_to_html(a)}")
                        paragraphs = html_text.split("\n\n")
                        for i, para in enumerate(paragraphs):
                            para = para.strip()
                            if para:
                                # Small spacer between paragraph chunks (none before first)
                                if i == 0:
                                    story.append(Paragraph(para, BODY_NO_INDENT))
                                else:
                                    story.append(Spacer(1, 4))
                                    story.append(Paragraph(para, BODY_STYLE))
                except:
                    story.append(Paragraph("（AI分析暂不可用）", SMALL_STYLE))
            else:
                story.append(Paragraph("（该节点无关联评论）", SMALL_STYLE))
            story.append(Spacer(1, 8))


# ─────────────────────────────────────────────────────────

def module_clusters(story, saved_ot, db, ch_num: str):
    story.append(_p(f"第{ch_num}章  群体聚类画廊", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.5, color=black))

    story.append(Paragraph(f"{fig_label(ch_num)} 加权凝聚聚类距离公式", CAPTION_STYLE))
    story.append(Paragraph(
        "D(A,B) = (1/|A|·|B|)·∑<sub>a∈A</sub>∑<sub>b∈B</sub> "
        "w<sub>a</sub>·w<sub>b</sub>·d(a,b)", FORMULA_STYLE))
    story.append(Paragraph(
        "其中 w<sub>i</sub>=1+log(1+like<sub>i</sub>)，d(a,b)为欧氏距离",
        ParagraphStyle("Fn2", fontName=FONT_CN, fontSize=9, leading=13,
                        textColor=HexColor("#64748b"), alignment=TA_CENTER)))

    from app.models import ClusterAnalysis
    ca = None
    if db and saved_ot:
        ca = db.query(ClusterAnalysis).filter(
            ClusterAnalysis.saved_timeline_id == saved_ot.id
        ).order_by(ClusterAnalysis.created_at.desc()).first()
    if not ca or not ca.clusters:
        story.append(_p("（无聚类数据）"))
        return []

    summaries = []
    for c in ca.clusters:
        ds = c.get("deepseek") or {}; cl_id = c.get('id', '?')
        pct = c.get('percentage', 0); cnt = c.get('memberCount', 0)
        story.append(_p(f"群体 C{cl_id} — {pct}% · {cnt}条", SEC_STYLE))
        defn = ds.get("definition", "")
        if defn: story.append(_p(defn))
        claim = ds.get("coreClaim", "")
        if claim:
            story.append(Paragraph(
                _en_tnr(f'<font color="#6366f1"><b>核心主张：</b>{claim}</font>'),
                BODY_STYLE))
        for a in (ds.get("arguments", []) or []):
            if a.strip(): story.append(Paragraph(f"  • {_en_tnr(a)}", SMALL_STYLE))
        basis = ds.get("materialBasis", "")
        if basis:
            story.append(Paragraph(
                _en_tnr(f'<font color="#64748b"><b>物质基础：</b>{basis}</font>'),
                SMALL_STYLE))
        story.append(Spacer(1, 10))
        sl = f"C{cl_id}（{pct}%·{cnt}条）"
        if defn: sl += f"：{defn[:80]}"
        summaries.append(sl)
    return summaries


# ─────────────────────────────────────────────────────────

def module_opposition(story, saved_ot, db, ch_num: str,
                       ds_api_key=None, video_task_id=None):
    story.append(_p(f"第{ch_num}章  高赞观点与对立面解析", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.5, color=black))

    from app.models import VideoComment
    comments = []
    if video_task_id and db:
        comments = db.query(VideoComment).filter(
            VideoComment.task_id == video_task_id, VideoComment.coord_x >= 0
        ).order_by(VideoComment.like_count.desc()).limit(20).all()
    if not comments:
        story.append(_p("（无评论数据）"))
        return

    story.append(Paragraph(f"{tbl_label(ch_num)} 点赞TOP15评论", CAPTION_STYLE))
    rows = [[_cell("作者"), _cell("点赞"), _cell("坐标"), _cell("内容")]]
    cs = ParagraphStyle("TblC", fontName=FONT_CN, fontSize=8, leading=11,
                         textColor=black, wordWrap="CJK")
    for c in comments[:15]:
        rows.append([_cell(c.user or ""), _cell(str(c.like_count)),
                     _cell(f"({c.coord_x},{c.coord_y})"),
                     _cell(c.content[:120], cs)])
    t = Table(rows, colWidths=[60, 40, 60, 300])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_CN),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#93c5fd")),
        ("TEXTCOLOR", (0, 0), (-1, 0), black),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)

    from app.models import DeepAnalysis, SavedVaTask
    da = None
    if saved_ot and db:
        sv = db.query(SavedVaTask).filter(SavedVaTask.bvid == saved_ot.bvid).first()
        if sv:
            da = db.query(DeepAnalysis).filter(
                DeepAnalysis.saved_va_task_id == sv.id
            ).order_by(DeepAnalysis.created_at.desc()).first()
    if da:
        if da.kol_viewpoints:
            story.append(Spacer(1, 8))
            story.append(_p("KOL观点分析（历史存档）：", SEC_STYLE))
            story.append(Paragraph(_en_tnr(da.kol_viewpoints.replace("\n", "<br/>")), BODY_STYLE))
        if da.opposition_analysis:
            story.append(Spacer(1, 8))
            story.append(_p("对立面解析（历史存档）：", SEC_STYLE))
            story.append(Paragraph(
                _en_tnr(da.opposition_analysis.replace("\n", "<br/>")), BODY_STYLE))


# ─────────────────────────────────────────────────────────

def module_wordcloud(story, saved_ot, db, ch_num: str, video_task_id=None):
    story.append(_p(f"第{ch_num}章  词云与争议词", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.5, color=black))

    from app.models import WordCloudItem, SavedVaTask, VideoComment
    word_items = None
    if db and saved_ot:
        sv = db.query(SavedVaTask).filter(SavedVaTask.bvid == saved_ot.bvid).first()
        if sv:
            wc = db.query(WordCloudItem).filter(WordCloudItem.saved_va_task_id == sv.id).first()
            if wc and wc.words_json: word_items = wc.words_json
    if not word_items:
        story.append(_p("（无词云数据）"))
        return

    try:
        from wordcloud import WordCloud
        wfreq = {w["text"]: int(w.get("count", w.get("weight", 1))) for w in word_items[:100]}
        if wfreq:
            wc_img = WordCloud(width=600, height=300, background_color="white",
                                font_path=_CJK_MPL, colormap="viridis",
                                max_words=80).generate_from_frequencies(wfreq)
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.imshow(wc_img, interpolation="bilinear"); ax.axis("off")
            story.append(Paragraph(f"{fig_label(ch_num)} 高频词云图", CAPTION_STYLE))
            story.append(_image_from_fig(fig, width=450))
    except:
        story.append(_p("（词云渲染失败）"))

    story.append(_p("争议关键词（反对 vs 支持阵营词频差）：", SEC_STYLE))
    if video_task_id and db:
        all_comments = db.query(VideoComment).filter(
            VideoComment.task_id == video_task_id, VideoComment.coord_x >= 0).all()
        anti_count = sum(1 for c in all_comments if c.coord_x < 40)
        pro_count = sum(1 for c in all_comments if c.coord_x > 60)
        if anti_count > 0 and pro_count > 0:
            keywords = [w["text"] for w in word_items[:50]]
            scores = []
            for kw in keywords:
                ah = sum(1 for c in all_comments if c.coord_x < 40 and kw in (c.content or ""))
                ph = sum(1 for c in all_comments if c.coord_x > 60 and kw in (c.content or ""))
                if ah + ph >= 2:
                    d = abs(ah / max(1, anti_count) - ph / max(1, pro_count))
                    scores.append((kw, ah, ph, d, "anti" if ah > ph else "pro"))
            scores.sort(key=lambda x: x[3], reverse=True)
            if scores:
                for kw, ah, ph, d, bias in scores[:10]:
                    color = "#ef4444" if bias == "anti" else "#3b82f6"
                    side = "反对阵营" if bias == "anti" else "支持阵营"
                    story.append(Paragraph(
                        _en_tnr(f'<font color="{color}"><b>{kw}</b></font> — '
                                f'{side}高频（反对{ah}次 vs 支持{ph}次，差{d:.3f}）'),
                        SMALL_STYLE))
            else: story.append(Paragraph("（样本不足）", SMALL_STYLE))
        else: story.append(Paragraph("（阵营数不足）", SMALL_STYLE))
    else: story.append(Paragraph("（数据不可用）", SMALL_STYLE))


# ─────────────────────────────────────────────────────────

def module_users(story, saved_ot, db, ch_num: str, video_task_id=None):
    story.append(_p(f"第{ch_num}章  评论区用户图谱", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.5, color=black))

    from app.models import BiliUserProfile, VideoComment
    if not video_task_id or not db:
        story.append(_p("（无数据）")); return
    comment_uids = [r[0] for r in db.query(VideoComment.uid).filter(
        VideoComment.task_id == video_task_id, VideoComment.uid > 0).distinct().limit(50).all()]
    profiles = db.query(BiliUserProfile).filter(
        BiliUserProfile.uid.in_(comment_uids)).limit(30).all()
    if not profiles:
        story.append(_p("（无用户画像）")); return

    xs, ys = [p.score_x for p in profiles], [p.score_y for p in profiles]
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(xs, ys, c="steelblue", alpha=0.6, s=30)
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.axhline(50, color="gray", alpha=0.2); ax.axvline(50, color="gray", alpha=0.2)
    ax.set_xlabel("反对 ← → 支持"); ax.set_ylabel("理性 ← → 感性")
    ax.set_title("评论区活跃用户分布")
    story.append(Paragraph(f"{fig_label(ch_num)} 活跃用户舆论分布", CAPTION_STYLE))
    story.append(_image_from_fig(fig, width=350))

    extremes = sorted(profiles, key=lambda p: abs(p.score_x-50)+abs(p.score_y-50), reverse=True)[:4]
    for p in extremes:
        story.append(Paragraph(
            _en_tnr(f"<b>@{p.name}</b> — 位置({p.score_x},{p.score_y}) — {p.summary or ''}"),
            SMALL_STYLE))


# ─────────────────────────────────────────────────────────

def module_ai_summary(story, saved_ot, db, ch_num: str, ds_api_key=None, video_task_id=None):
    story.append(_p(f"第{ch_num}章  AI综合研判摘要", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.5, color=black))

    if not ds_api_key:
        story.append(_p("（未配置API Key）")); return

    trail = saved_ot and saved_ot.centroid_trail or []
    trail_samples = []
    if len(trail) >= 5:
        indices = [0, len(trail)//4, len(trail)//2, 3*len(trail)//4, len(trail)-1]
        trail_samples = [
            f"  {trail[i]['t']}: 质心({trail[i]['x']:.0f},{trail[i]['y']:.0f})，"
            f"{trail[i]['count']}条" for i in indices]

    from app.models import VideoComment
    top_comments = []
    if video_task_id and db:
        top_comments = db.query(VideoComment).filter(
            VideoComment.task_id == video_task_id, VideoComment.coord_x >= 0
        ).order_by(VideoComment.like_count.desc()).limit(5).all()

    prompt = (
        f"你是一位冷静的舆情分析师。请基于以下数据，生成500字以内的综合研判。\n\n"
        f"1. 质心漂移关键节点：\n"
        f"{chr(10).join(trail_samples) if trail_samples else '(无)'}\n\n"
        f"2. 点赞最高5条评论：\n"
        f"{chr(10).join(f'  @{c.user}: {c.content[:100]}' for c in top_comments) if top_comments else '(无)'}\n\n"
        f"请分析：舆论是否极化、事件演化逻辑、潜在风险点、建议关注方向。直接输出分析文字，不要JSON。")
    try:
        result = _call_deepseek(prompt, ds_api_key, max_tokens=800, temperature=0.5, timeout=120)
        parsed = _md_to_html(result)
        for line in parsed.split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 4))
            else:
                story.append(Paragraph(_en_tnr(line), BODY_NO_INDENT))
    except Exception as e:
        story.append(Paragraph(_en_tnr(f"AI分析失败：{e}"), BODY_STYLE))


# ======================================================================
#  Module Registry
# ======================================================================

MODULES = {
    "overview": module_overview, "heatmap": module_heatmap,
    "camps": module_camps, "trail": module_trail,
    "clusters": module_clusters, "opposition": module_opposition,
    "wordcloud": module_wordcloud, "users": module_users,
    "ai_summary": module_ai_summary,
}

MODULE_LABELS = {
    "overview": ("事件总览", "封面/摘要页，展示视频基本信息与AI总览"),
    "heatmap": ("舆论地形图", "101×101密度热力图 + DeepSeek分布分析"),
    "camps": ("情感阵营分布", "反对/中立/支持统计 + AI心态总结"),
    "trail": ("质心漂移轨迹", "智能缩放 + AI关键节点选择与原因分析"),
    "clusters": ("群体聚类画廊", "聚类分群：定义、主张、论据、物质基础"),
    "opposition": ("高赞观点与对立面", "TOP15评论表格 + 历史存档解析"),
    "wordcloud": ("词云与争议词", "高频词云图 + 阵营间争议关键词"),
    "users": ("评论区用户图谱", "活跃用户散点图 + 极端画像"),
    "ai_summary": ("AI综合研判摘要", "DeepSeek 500字舆情研判"),
}


# ======================================================================
#  Two-pass TOC builder
# ======================================================================

def _build_toc_story(ordered_modules, bm_pages: dict) -> list:
    """Build Word-style TOC: left chapter names, right page numbers, clean table layout."""
    toc = []
    toc.append(_p("目  录", CHAP_STYLE))
    toc.append(Spacer(1, 16))

    TOC_LEFT = ParagraphStyle("TOCLeft", fontName=FONT_CN, fontSize=12, leading=26,
                               textColor=black, spaceAfter=0, leftIndent=4)
    TOC_RIGHT = ParagraphStyle("TOCRight", fontName=FONT_CN, fontSize=12, leading=26,
                                textColor=black, spaceAfter=0, alignment=TA_RIGHT)

    available_w = A4[0] - MARGIN_L - MARGIN_R
    rows = []
    for mod_key, cn, _ar in ordered_modules:
        label = _get_module_label(mod_key)
        page = str(bm_pages.get(f"ch_{_ar}", "—"))
        rows.append([
            Paragraph(_en_tnr(f"第{cn}章  {label}"), TOC_LEFT),
            Paragraph(page, TOC_RIGHT),
        ])

    # References row
    rows.append([
        Paragraph(_en_tnr("参考文献"), TOC_LEFT),
        Paragraph("", TOC_RIGHT),
    ])

    t = Table(rows, colWidths=[available_w * 0.88, available_w * 0.12])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_CN),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (0, -1), 10),
        ("RIGHTPADDING", (1, 0), (1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, HexColor("#d1d5db")),
        ("LINEABOVE", (0, 0), (-1, -1), 0, white),
        ("LINEBEFORE", (0, 0), (-1, -1), 0, white),
        ("LINEAFTER", (0, 0), (-1, -1), 0, white),
    ]))
    toc.append(t)
    # No PageBreak here — first chapter's own PageBreak handles the break
    return toc


class PageTrackingCanvas:
    """Canvas wrapper that records bookmark page numbers."""
    def __init__(self, filename, pagesize, bm_pages, **kwargs):
        from reportlab.pdfgen import canvas
        self._c = canvas.Canvas(filename, pagesize=pagesize, **kwargs)
        self._bm_pages = bm_pages

    def bookmarkPage(self, key, **kw):
        self._bm_pages[key] = self._c.getPageNumber()
        return self._c.bookmarkPage(key, **kw)

    def showPage(self):
        self._c.showPage()

    def save(self):
        self._c.save()

    def __getattr__(self, name):
        return getattr(self._c, name)


# ======================================================================
#  Main Entry Point
# ======================================================================

def generate_pdf(saved_ot_id: int, modules: list, db,
                  ds_api_key: str = None, refresh_camps: bool = False,
                  progress_cb=None) -> BytesIO:
    from app.models import SavedOpinionTimelineTask
    reset_counters()

    def _prog(step, msg):
        if progress_cb: progress_cb(step, len(modules) + 5, msg)

    _prog(0, "正在加载数据...")
    saved_ot = db.query(SavedOpinionTimelineTask).filter(
        SavedOpinionTimelineTask.id == saved_ot_id).first()
    if not saved_ot: raise ValueError("保存记录不存在")

    video_task = None; video_task_id = None; saved_va = None
    try:
        from app.models import SavedVaTask, VideoAnalysisTask
        saved_va = db.query(SavedVaTask).filter(SavedVaTask.bvid == saved_ot.bvid).first()
        video_task = db.query(VideoAnalysisTask).filter(
            VideoAnalysisTask.bvid == saved_ot.bvid
        ).order_by(VideoAnalysisTask.created_at.desc()).first()
        if video_task: video_task_id = video_task.id
    except: pass

    _prog(1, "正在构建文档...")
    ordered_modules = _resolve_module_order(modules, ds_api_key)
    t = saved_ot.title or saved_ot.bvid
    story = []
    bookmark_pages = {}

    # ── Cover ──
    story.append(Spacer(1, 50))
    story.append(Paragraph(_en_tnr("<b>Miho-spot 舆情分析报告</b>"), TITLE_STYLE))
    story.append(Spacer(1, 20))
    story.append(Paragraph(_en_tnr(f"《{t}》"), ParagraphStyle(
        "CvT", fontName=FONT_CN, fontSize=18, leading=26,
        textColor=black, alignment=TA_CENTER, spaceAfter=30)))
    story.append(Spacer(1, 40))
    story.append(Paragraph(
        _en_tnr(f"生成日期：{datetime.now().strftime('%Y年%m月%d日')}"), COVER_LABEL))
    story.append(Spacer(1, 8))
    story.append(Paragraph(_en_tnr("分析工具：Miho-spot 舆情监测系统 v1.4"), COVER_INFO))
    story.append(Spacer(1, 8))
    story.append(Paragraph(_en_tnr("数据来源：Bilibili 视频评论区"), COVER_INFO))
    story.append(Spacer(1, 8))
    story.append(Paragraph(_en_tnr("AI引擎：DeepSeek API"), COVER_INFO))
    story.append(PageBreak())

    # ── Abstract ──
    story.append(_p("摘  要", CHAP_STYLE))
    story.append(_p(
        f"本报告基于B站视频《{t}》的评论数据，运用DeepSeek AI情感分析与坐标映射技术，"
        f"从舆论地形分布、情感阵营划分、时间轴演化、群体聚类等多个维度，"
        f"对该视频的评论区舆论场进行全面、系统的分析。"))
    story.append(_p(
        f"共采集 {saved_ot.total_comments or 0} 条评论，成功分析 {saved_ot.analyzed_count or 0} 条。"
        f"整体舆论质心位于坐标 ({saved_ot.centroid_x or 50:.1f}, {saved_ot.centroid_y or 50:.1f})。"))

    # ── Module application table ──
    story.append(Spacer(1, 12))
    story.append(_p("本次报告模块应用情况：", SEC_STYLE))
    all_mods = ["overview", "heatmap", "camps", "trail", "clusters",
                "opposition", "wordcloud", "users", "ai_summary"]
    mr = [[_cell("模块"), _cell("状态"), _cell("说明")]]
    for mk in all_mods:
        applied = mk in modules
        status = "✓ 已应用" if applied else "✗ 未应用"
        desc = MODULE_LABELS.get(mk, (mk, ""))[1]
        mr.append([_cell(MODULE_LABELS.get(mk, (mk, ""))[0]), _cell(status), _cell(desc)])
    mt = Table(mr, colWidths=[100, 70, 290])
    mt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_CN),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#e2e8f0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#1e40af")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(mt)
    story.append(PageBreak())

    # ← Remember where to insert TOC
    toc_insert_idx = len(story)

    # ── Execute modules (each starts with PageBreak + Bookmark) ──
    ds_heatmap_analysis = ""; camps_data = {}; cluster_summaries = []; step = 1

    for mod_key, cn, ar_num in ordered_modules:
        step += 1
        label = _get_module_label(mod_key)
        _prog(step, f"正在生成：{label}")
        if mod_key not in MODULES: continue

        # ← Each chapter starts on a new page
        story.append(PageBreak())
        # Bookmark for TOC linking
        story.append(BookmarkFlowable(f"ch_{ar_num}", bookmark_pages))

        try:
            if mod_key == "overview":
                MODULES[mod_key](story, saved_ot, saved_va, video_task, cn,
                                  ds_api_key=ds_api_key, db=db,
                                  ds_heatmap_analysis=ds_heatmap_analysis,
                                  camps_data=camps_data,
                                  cluster_summaries=cluster_summaries)
            elif mod_key == "heatmap":
                ds_heatmap_analysis = (
                    MODULES[mod_key](story, saved_ot, cn, ds_api_key=ds_api_key,
                                     db=db, video_task_id=video_task_id) or "")
            elif mod_key == "camps":
                camps_data = (
                    MODULES[mod_key](story, saved_ot, db, cn, ds_api_key=ds_api_key,
                                     video_task_id=video_task_id) or {})
            elif mod_key == "trail":
                MODULES[mod_key](story, saved_ot, db, cn, ds_api_key=ds_api_key,
                                  progress_cb=progress_cb)
            elif mod_key == "clusters":
                cluster_summaries = (
                    MODULES[mod_key](story, saved_ot, db, cn) or [])
            elif mod_key == "opposition":
                MODULES[mod_key](story, saved_ot, db, cn, ds_api_key=ds_api_key,
                                  video_task_id=video_task_id)
            elif mod_key == "wordcloud":
                MODULES[mod_key](story, saved_ot, db, cn, video_task_id=video_task_id)
            elif mod_key == "users":
                MODULES[mod_key](story, saved_ot, db, cn, video_task_id=video_task_id)
            elif mod_key == "ai_summary":
                MODULES[mod_key](story, saved_ot, db, cn, ds_api_key=ds_api_key,
                                  video_task_id=video_task_id)
        except Exception as e:
            tb = traceback.format_exc()
            story.append(Paragraph(
                _en_tnr(f'<font color="#ef4444"><b>模块《{label}》生成失败：</b>'
                        f'{str(e)[:200]}</font>'), BODY_STYLE))
            story.append(Paragraph(
                f'<font color="#64748b" size="7">{tb[-300:]}</font>', SMALL_STYLE))

    # ── References ──
    story.append(PageBreak())
    story.append(_p("参考文献", CHAP_STYLE))
    refs = [
        "Miho-spot 舆情监测系统 v1.4",
        "Bilibili API, https://api.bilibili.com",
        "DeepSeek API, https://platform.deepseek.com",
        "ReportLab PDF Library, https://www.reportlab.com",
        "Matplotlib Visualization, https://matplotlib.org",
        "WordCloud Python Library",
        "Scipy Scientific Computing, https://scipy.org",
    ]
    for i, ref in enumerate(refs, 1):
        story.append(_pni(f"[{i}] {ref}"))

    # ── Two-pass build: Pass 1 to get bookmark pages ──
    _prog(step + 1, "正在计算页码（第一遍）...")
    
    # Deep-copy story for pass 1 so original flowables stay intact for pass 2
    # (Image and other stateful flowables are consumed during build)
    story_pass1 = copy.deepcopy(story)
    
    buf_pass1 = BytesIO()
    doc_pass1 = SimpleDocTemplate(
        buf_pass1, pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B,
        title=f"舆情分析报告-{t[:20]}", author="Miho-spot")

    def _canvas_pass1(filename, pagesize, **kwargs):
        return PageTrackingCanvas(filename, pagesize, bookmark_pages, **kwargs)

    doc_pass1.build(story_pass1, onFirstPage=_page_number_callback,
                    onLaterPages=_page_number_callback,
                    canvasmaker=_canvas_pass1)

    # ── Pass 2: Insert TOC at beginning with real page numbers ──
    _prog(step + 2, f"正在生成目录（{len(bookmark_pages)}个书签）...")

    toc_story = _build_toc_story(ordered_modules, bookmark_pages)

    # Insert TOC at the tracked position (after abstract, before chapters)
    final_story = story[:toc_insert_idx] + toc_story + story[toc_insert_idx:]

    # ── Final render ──
    _prog(step + 3, "正在渲染PDF（最终输出）...")
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=MARGIN_L, rightMargin=MARGIN_R,
                             topMargin=MARGIN_T, bottomMargin=MARGIN_B,
                             title=f"舆情分析报告-{t[:20]}", author="Miho-spot")

    try:
        doc.build(final_story, onFirstPage=_page_number_callback,
                  onLaterPages=_page_number_callback)
    except Exception as build_err:
        final_story.append(Paragraph(
            _en_tnr(f'<font color="#ef4444"><b>PDF渲染异常：</b>{build_err}</font>'),
            BODY_STYLE))
        final_story.append(Paragraph("正在降级重试（跳过图片）...", SMALL_STYLE))
        text_only = []
        for f in final_story:
            if isinstance(f, Image):
                text_only.append(Paragraph("[图片已跳过]", SMALL_STYLE))
            else:
                text_only.append(f)
        buf = BytesIO()
        doc2 = SimpleDocTemplate(buf, pagesize=A4,
                                  leftMargin=MARGIN_L, rightMargin=MARGIN_R,
                                  topMargin=MARGIN_T, bottomMargin=MARGIN_B)
        doc2.build(text_only, onFirstPage=_page_number_callback,
                   onLaterPages=_page_number_callback)

    buf.seek(0)
    _prog(step + 4, "完成！")
    return buf
