"""
PDF Report Generator for Miho-spot — modular, user-selectable sections.
Uses reportlab for PDF, matplotlib for charts, wordcloud for clouds.
"""
import io, os, json
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image, Table,
                                 TableStyle, PageBreak, KeepTogether)
from reportlab.platypus.flowables import HRFlowable

# ── Chinese undergraduate thesis page settings ──
THESIS_LEFT = 30 * mm
THESIS_RIGHT = 25 * mm
THESIS_TOP = 30 * mm
THESIS_BOTTOM = 25 * mm

# ── matplotlib ──
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ── font setup for CJK ──
_CJK_FONT = None
for _f in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/msyhbd.ttc"]:
    if os.path.exists(_f):
        _CJK_FONT = _f
        break

if _CJK_FONT:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("CJK", _CJK_FONT))
    plt.rcParams["font.family"] = matplotlib.font_manager.FontProperties(fname=_CJK_FONT).get_name()
else:
    plt.rcParams["font.family"] = "sans-serif"

plt.rcParams["axes.unicode_minus"] = False

# ── Styles (Chinese undergraduate thesis standard) ──
_styles = getSampleStyleSheet()
FONT = "CJK" if _CJK_FONT else "Helvetica"

# 论文标题：二号(22pt) 黑体居中
THESIS_TITLE = ParagraphStyle("ThesisTitle", fontName=FONT, fontSize=22, leading=30,
                               textColor=black, alignment=TA_CENTER, spaceAfter=12)
# 章标题：三号(16pt) 黑体
CHAP_STYLE = ParagraphStyle("Chapter", fontName=FONT, fontSize=16, leading=24,
                              textColor=black, spaceAfter=10, spaceBefore=18)
# 节标题：小三号(15pt) 黑体
SEC_STYLE = ParagraphStyle("Section", fontName=FONT, fontSize=15, leading=22,
                             textColor=HexColor("#1e40af"), spaceAfter=8, spaceBefore=12)
# 小节标题：四号(14pt) 黑体
SUB_STYLE = ParagraphStyle("SubSection", fontName=FONT, fontSize=14, leading=20,
                              textColor=HexColor("#3b82f6"), spaceAfter=6, spaceBefore=10)
# 正文：小四号(12pt) 宋体/黑体，1.5倍行距≈20pt
BODY_STYLE = ParagraphStyle("Body", fontName=FONT, fontSize=12, leading=20,
                             textColor=black, spaceAfter=4, firstLineIndent=24)
BODY_NO_INDENT = ParagraphStyle("BodyNoIndent", fontName=FONT, fontSize=12, leading=20,
                                 textColor=black, spaceAfter=4)
SMALL_STYLE = ParagraphStyle("Small", fontName=FONT, fontSize=9, leading=14,
                              textColor=HexColor("#64748b"))
CENTER_STYLE = ParagraphStyle("Center", fontName=FONT, fontSize=12, leading=20,
                               textColor=black, alignment=TA_CENTER)
CAPTION_STYLE = ParagraphStyle("Caption", fontName=FONT, fontSize=10, leading=14,
                                textColor=HexColor("#475569"), alignment=TA_CENTER, spaceBefore=4)
# Cover-specific
COVER_LABEL = ParagraphStyle("CoverLabel", fontName=FONT, fontSize=14, leading=22,
                              textColor=black, alignment=TA_CENTER, spaceAfter=4)
COVER_INFO = ParagraphStyle("CoverInfo", fontName=FONT, fontSize=12, leading=20,
                             textColor=HexColor("#475569"), alignment=TA_CENTER, spaceAfter=2)

# ── Chapter numbering ──
_CHAP_NUMS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
_MODULE_TO_CHAPTER = {
    "overview": "一", "heatmap": "二", "camps": "三", "trail": "四",
    "clusters": "五", "opposition": "六", "wordcloud": "七", "users": "八", "ai_summary": "九",
}


# ─────────────────────────────────────────────────────────────
#  Helper utilities
# ─────────────────────────────────────────────────────────────

def _image_from_fig(fig, width=480, max_height=400) -> Image:
    """Convert matplotlib figure → reportlab Image, capped to fit page."""
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    plt.close(fig)
    img = Image(buf, width=width, height=max_height, kind="proportional")
    return img

def _box(text: str, color: str = "#e2e8f0") -> Paragraph:
    return Paragraph(f'<font color="#64748b" size="9">{text}</font>', BODY_STYLE)


def _cell(text: str, style=None) -> Paragraph:
    """Wrap cell text in a Paragraph so it auto-wraps inside table cells."""
    st = style or ParagraphStyle("TableCell", fontName=FONT, fontSize=9, leading=13,
                                  textColor=black, wordWrap="CJK")
    return Paragraph(text, st)


# ─────────────────────────────────────────────────────────────
#  Module 1: Event Overview (事件总览)
# ─────────────────────────────────────────────────────────────

def module_overview(story, saved_ot, saved_va, video_task):
    story.append(Paragraph("第一章  事件总览", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.5, color=black))

    title = saved_ot and saved_ot.title or (video_task and video_task.title or "未知视频")
    bvid = saved_ot and saved_ot.bvid or (video_task and video_task.bvid or "")

    total = (saved_ot and saved_ot.total_comments) or (video_task and video_task.total_comments or 0)
    analyzed = (saved_ot and saved_ot.analyzed_count) or (video_task and video_task.analyzed_count or 0)
    matched = (saved_va and saved_va.matched_count) or (video_task and video_task.matched_count or 0)

    cx = (saved_ot and saved_ot.centroid_x) or (video_task and video_task.centroid_x_no_origin or 0)
    cy = (saved_ot and saved_ot.centroid_y) or (video_task and video_task.centroid_y_no_origin or 0)

    story.append(Paragraph(f"视频：{title}", SEC_STYLE))
    story.append(Paragraph(f"BV号：{bvid}", BODY_STYLE))

    summary = f"共采集 <b>{total}</b> 条评论，其中 <b>{matched}</b> 条命中游戏关键词，成功生成 <b>{analyzed}</b> 组坐标。"
    story.append(Paragraph(summary, BODY_STYLE))

    story.append(Paragraph(f"修正质心（去中立）：({cx:.1f}, {cy:.1f}) —— X轴0=反对/100=支持，Y轴0=理性/100=感性", BODY_STYLE))

    # Try embedding cover image if available
    cover_url = saved_ot and saved_ot.cover_url or (video_task and video_task.cover_url or "")
    if cover_url:
        try:
            import httpx
            resp = httpx.get(cover_url, timeout=10)
            if resp.status_code == 200:
                img = Image(BytesIO(resp.content), width=200, height=150, kind="proportional")
                story.append(Spacer(1, 6))
                story.append(img)
        except:
            pass

    story.append(Spacer(1, 12))


# ─────────────────────────────────────────────────────────────
#  Module 2: Heatmap (舆论地形图)
# ─────────────────────────────────────────────────────────────

def module_heatmap(story, saved_ot):
    story.append(PageBreak())
    story.append(Paragraph("第二章  舆论地形图", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.5, color=black))

    grid_data = None
    cx, cy = 50.0, 50.0
    if saved_ot and saved_ot.heatmap_grid:
        grid_data = saved_ot.heatmap_grid
        cx = saved_ot.centroid_x or 50
        cy = saved_ot.centroid_y or 50

    if not grid_data:
        story.append(Paragraph("（无热力图数据）", BODY_STYLE))
        return

    # Render heatmap with matplotlib
    arr = np.array(grid_data, dtype=float)
    if arr.shape != (101, 101):
        arr = arr.T if arr.shape == (101, 101) else np.zeros((101, 101))

    if arr.max() == 0:
        arr[50, 50] = 1

    fig, ax = plt.subplots(figsize=(7, 7))
    im = ax.imshow(np.flipud(arr.T), cmap="YlOrRd", extent=[0, 100, 0, 100],
                    aspect="equal", origin="lower", interpolation="bilinear")

    # Centroid
    ax.plot(cx, 100 - cy, marker="*", color="gold", markersize=14, markeredgecolor="black", markeredgewidth=1)
    ax.axhline(50, color="white", alpha=0.3, linewidth=1)
    ax.axvline(50, color="white", alpha=0.3, linewidth=1)
    ax.set_xlabel("反对米哈游 ← → 支持米哈游")
    ax.set_ylabel("理性 ← → 感性")
    ax.set_title("舆论二维密度分布 + 整体质心(★)")
    plt.colorbar(im, ax=ax, label="评论密度")
    story.append(_image_from_fig(fig))
    story.append(Paragraph(f"整体质心：({cx:.1f}, {cy:.1f})", CENTER_STYLE))


# ─────────────────────────────────────────────────────────────
#  Module 3: Sentiment Camps (情感阵营分布)
# ─────────────────────────────────────────────────────────────

def module_camps(story, saved_ot, db, ds_api_key=None, video_task_id=None):
    story.append(PageBreak())
    story.append(Paragraph("第三章  情感阵营分布", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.5, color=black))

    # Get comments from video_comments table (keyed by VideoAnalysisTask.id)
    comments = []
    if video_task_id and db:
        from app.models import VideoComment
        comments = db.query(VideoComment).filter(
            VideoComment.task_id == video_task_id,
            VideoComment.coord_x >= 0,
            VideoComment.coord_y >= 0
        ).order_by(VideoComment.like_count.desc()).limit(500).all()

    if not comments:
        story.append(Paragraph("（无评论坐标数据）", BODY_STYLE))
        return

    camps = {"反对": [], "中立": [], "支持": []}
    for c in comments:
        if c.coord_x < 40: camps["反对"].append(c)
        elif c.coord_x > 60: camps["支持"].append(c)
        else: camps["中立"].append(c)

    total = len(comments)
    camps_rows = []
    for name in ["反对", "中立", "支持"]:
        clist = camps[name]
        pct = len(clist) / total * 100 if total else 0
        avg_y = np.mean([c.coord_y for c in clist]) if clist else 0
        avg_y_label = "偏理性" if avg_y < 45 else ("偏感性" if avg_y > 55 else "中性")
        camps_rows.append([_cell(name), _cell(str(len(clist))), _cell(f"{pct:.1f}%"),
                           _cell(f"{avg_y:.1f} ({avg_y_label})")])

    # Table
    t = Table([[_cell("阵营", SMALL_STYLE), _cell("人数", SMALL_STYLE),
                _cell("占比", SMALL_STYLE), _cell("平均理性度(Y)", SMALL_STYLE)]] + camps_rows,
              colWidths=[70, 60, 60, 110])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f8fafc"), white]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))

    # Top 5 liked per camp + DeepSeek summary
    for name in ["反对", "中立", "支持"]:
        clist = sorted(camps[name], key=lambda x: x.like_count, reverse=True)[:5]
        if not clist:
            continue

        story.append(Paragraph(f"{name}阵营 — 点赞最高评论：", SEC_STYLE))
        for c in clist:
            story.append(Paragraph(
                f"<b>@{c.user}</b> (赞{c.like_count}) [{c.coord_x},{c.coord_y}]：{c.content[:120]}",
                SMALL_STYLE))

        # DeepSeek one-sentence summary (if key available)
        if ds_api_key and len(clist) >= 3:
            summary = _ds_camp_summary(name, clist, ds_api_key)
            if summary:
                story.append(Paragraph(f'<font color="#6366f1"><b>AI总结：</b>{summary}</font>', BODY_STYLE))
        story.append(Spacer(1, 6))


def _ds_camp_summary(name, comments, api_key):
    try:
        import httpx
        samples = "\n".join(f"- @{c.user}: {c.content[:80]}" for c in comments[:5])
        prompt = f"用一句话（20字以内）概括B站评论区{name}米哈游阵营的典型心态：\n{samples}\n\n请只返回概括文字。"
        resp = httpx.post("https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 60, "temperature": 0.3}, timeout=30)
        return resp.json()["choices"][0]["message"]["content"].strip()
    except:
        return ""


# ─────────────────────────────────────────────────────────────
#  Module 4: Centroid Trail (质心漂移轨迹)
# ─────────────────────────────────────────────────────────────

def module_trail(story, saved_ot):
    story.append(PageBreak())
    story.append(Paragraph("第四章  时间轴推演——质心漂移轨迹", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#e2e8f0")))

    trail = saved_ot and saved_ot.centroid_trail or []
    if not trail or len(trail) < 2:
        story.append(Paragraph("（无漂移数据）", BODY_STYLE))
        return

    xs = [p["x"] for p in trail]
    ys = [p["y"] for p in trail]
    sizes = [max(5, p.get("count", 1) * 2) for p in trail]
    times = [p.get("t", "") for p in trail]
    nodes = saved_ot and saved_ot.node_indices or []

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.set_xlabel("反对 ← → 支持"); ax.set_ylabel("理性 ← → 感性")
    ax.set_title("质心漂移轨迹")
    ax.axhline(50, color="gray", alpha=0.2); ax.axvline(50, color="gray", alpha=0.2)

    scatter = ax.scatter(xs, ys, s=sizes, c=range(len(xs)), cmap="viridis", alpha=0.7, zorder=3)
    ax.plot(xs, ys, "gold", alpha=0.5, linewidth=1.5, zorder=2)

    # Arrow between consecutive points
    mid = len(xs) // 2
    if len(xs) > 1:
        ax.annotate("", xy=(xs[mid], ys[mid]), xytext=(xs[mid-1], ys[mid-1]),
                     arrowprops=dict(arrowstyle="->", color="red", lw=1.5))

    # Mark nodes with stars
    for ni in nodes:
        if ni < len(xs):
            ax.plot(xs[ni], ys[ni], marker="*", color="gold", markersize=12,
                     markeredgecolor="black", markeredgewidth=0.5, zorder=5)

    # Auto-detect abrupt shifts: distance between consecutive centroids > 15
    for i in range(1, len(trail)):
        d = np.sqrt((xs[i] - xs[i-1])**2 + (ys[i] - ys[i-1])**2)
        if d > 15:
            ax.annotate("!", (xs[i], ys[i]), fontsize=14, color="red", weight="bold",
                         ha="center", va="center")

    cbar = plt.colorbar(scatter, ax=ax, label="时间顺序（早→晚）")
    story.append(_image_from_fig(fig))


# ─────────────────────────────────────────────────────────────
#  Module 5: Cluster Gallery (群体聚类画廊)
# ─────────────────────────────────────────────────────────────

def module_clusters(story, saved_ot, db):
    story.append(PageBreak())
    story.append(Paragraph("第五章  群体聚类画廊", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#e2e8f0")))

    from app.models import ClusterAnalysis
    if db and saved_ot:
        ca = db.query(ClusterAnalysis).filter(
            ClusterAnalysis.saved_timeline_id == saved_ot.id
        ).order_by(ClusterAnalysis.created_at.desc()).first()
    else:
        ca = None

    if not ca or not ca.clusters:
        story.append(Paragraph("（无聚类数据）", BODY_STYLE))
        return

    for c in ca.clusters:
        ds = c.get("deepseek") or {}
        story.append(Paragraph(f"群体 C{c.get('id','?')} — {c.get('percentage',0)}% · {c.get('memberCount',0)}条", SEC_STYLE))

        # Definition
        defn = ds.get("definition", f"质心({c['centroid'].get('x',0):.0f},{c['centroid'].get('y',0):.0f})的群体")
        story.append(Paragraph(defn, BODY_STYLE))

        # Core claim
        claim = ds.get("coreClaim", "")
        if claim:
            story.append(Paragraph(f'<font color="#6366f1"><b>核心主张：</b>{claim}</font>', BODY_STYLE))

        # Arguments
        args = ds.get("arguments", [])
        if args:
            for a in args:
                if a.strip():
                    story.append(Paragraph(f"  • {a}", SMALL_STYLE))

        # Material basis
        basis = ds.get("materialBasis", "")
        if basis:
            story.append(Paragraph(f'<font color="#64748b"><b>物质基础：</b>{basis}</font>', SMALL_STYLE))

        story.append(Spacer(1, 10))


# ─────────────────────────────────────────────────────────────
#  Module 6: Top Comments & Opposition (高赞观点与对立面)
# ─────────────────────────────────────────────────────────────

def module_opposition(story, saved_ot, db, ds_api_key=None, video_task_id=None):
    story.append(PageBreak())
    story.append(Paragraph("第六章  高赞观点与对立面解析", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#e2e8f0")))

    from app.models import VideoComment
    comments = []
    if video_task_id and db:
        comments = db.query(VideoComment).filter(
            VideoComment.task_id == video_task_id, VideoComment.coord_x >= 0
        ).order_by(VideoComment.like_count.desc()).limit(20).all()

    if not comments:
        story.append(Paragraph("（无评论数据）", BODY_STYLE))
        return

    # Top 15 table
    story.append(Paragraph("点赞TOP15评论：", SEC_STYLE))
    rows = [[_cell("作者"), _cell("点赞"), _cell("坐标"), _cell("内容")]]
    content_style = ParagraphStyle("TblContent", fontName=FONT, fontSize=8, leading=11,
                                    textColor=black, wordWrap="CJK")
    for c in comments[:15]:
        rows.append([_cell(c.user or ""), _cell(str(c.like_count)),
                     _cell(f"({c.coord_x},{c.coord_y})"),
                     _cell(c.content[:120], content_style)])

    t = Table(rows, colWidths=[60, 40, 60, 300])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)

    # Deep Analyses text if available
    from app.models import DeepAnalysis
    da = None
    if saved_ot and db:
        from app.models import SavedVaTask
        saved_va = db.query(SavedVaTask).filter(SavedVaTask.bvid == saved_ot.bvid).first()
        if saved_va:
            da = db.query(DeepAnalysis).filter(
                DeepAnalysis.saved_va_task_id == saved_va.id
            ).order_by(DeepAnalysis.created_at.desc()).first()

    if da:
        if da.kol_viewpoints:
            story.append(Spacer(1, 8))
            story.append(Paragraph("KOL观点分析（历史存档）：", SEC_STYLE))
            story.append(Paragraph(da.kol_viewpoints.replace("\n", "<br/>"), BODY_STYLE))
        if da.opposition_analysis:
            story.append(Spacer(1, 8))
            story.append(Paragraph("对立面解析（历史存档）：", SEC_STYLE))
            story.append(Paragraph(da.opposition_analysis.replace("\n", "<br/>"), BODY_STYLE))


# ─────────────────────────────────────────────────────────────
#  Module 7: Word Cloud (词云与争议词)
# ─────────────────────────────────────────────────────────────

def module_wordcloud(story, saved_ot, db, video_task_id=None):
    story.append(PageBreak())
    story.append(Paragraph("第七章  词云与争议词", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#e2e8f0")))

    from app.models import WordCloudItem, SavedVaTask, VideoComment

    word_items = None
    if db and saved_ot:
        saved_va = db.query(SavedVaTask).filter(SavedVaTask.bvid == saved_ot.bvid).first()
        if saved_va:
            wc = db.query(WordCloudItem).filter(
                WordCloudItem.saved_va_task_id == saved_va.id
            ).first()
            if wc and wc.words_json:
                word_items = wc.words_json

    if not word_items:
        story.append(Paragraph("（无词云数据）", BODY_STYLE))
        return

    # Generate word cloud image
    try:
        from wordcloud import WordCloud
        wfreq = {w["text"]: int(w.get("count", w.get("weight", 1))) for w in word_items[:100]}
        if wfreq:
            wc_img = WordCloud(width=600, height=300, background_color="white",
                                font_path=_CJK_FONT, colormap="viridis",
                                max_words=80).generate_from_frequencies(wfreq)
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.imshow(wc_img, interpolation="bilinear")
            ax.axis("off")
            story.append(_image_from_fig(fig, width=450))
    except:
        story.append(Paragraph("（词云渲染失败）", BODY_STYLE))

    # Controversial words: diff between pro/anti camps (fully local, no API)
    story.append(Paragraph("争议关键词（反对 vs 支持阵营词频差）：", SEC_STYLE))
    if video_task_id and db:
        all_comments = db.query(VideoComment).filter(
            VideoComment.task_id == video_task_id, VideoComment.coord_x >= 0
        ).all()
        anti_count = sum(1 for c in all_comments if c.coord_x < 40)
        pro_count = sum(1 for c in all_comments if c.coord_x > 60)
        if anti_count > 0 and pro_count > 0:
            keywords = [w["text"] for w in word_items[:50]]
            scores = []
            for kw in keywords:
                anti_hits = sum(1 for c in all_comments if c.coord_x < 40 and kw in (c.content or ""))
                pro_hits = sum(1 for c in all_comments if c.coord_x > 60 and kw in (c.content or ""))
                if anti_hits + pro_hits >= 2:
                    diff = abs(anti_hits / max(1, anti_count) - pro_hits / max(1, pro_count))
                    scores.append((kw, anti_hits, pro_hits, diff, "anti" if anti_hits > pro_hits else "pro"))
            scores.sort(key=lambda x: x[3], reverse=True)
            if scores:
                for kw, ah, ph, d, bias in scores[:10]:
                    color = "#ef4444" if bias == "anti" else "#3b82f6"
                    side = "反对阵营" if bias == "anti" else "支持阵营"
                    story.append(Paragraph(
                        f'<font color="{color}"><b>{kw}</b></font> — {side}高频（反对{ah}次 vs 支持{ph}次, 差值{d:.3f}）',
                        SMALL_STYLE))
            else:
                story.append(Paragraph("（关键词样本不足，无法计算争议度）", SMALL_STYLE))
        else:
            story.append(Paragraph("（阵营评论数不足，无法计算争议词）", SMALL_STYLE))
    else:
        story.append(Paragraph("（评论坐标数据不可用）", SMALL_STYLE))


# ─────────────────────────────────────────────────────────────
#  Module 8: User Profiles (评论区用户图谱)
# ─────────────────────────────────────────────────────────────

def module_users(story, saved_ot, db, video_task_id=None):
    story.append(PageBreak())
    story.append(Paragraph("第八章  评论区用户图谱", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#e2e8f0")))

    from app.models import BiliUserProfile, VideoComment

    if not video_task_id or not db:
        story.append(Paragraph("（无数据）", BODY_STYLE))
        return

    comment_uids = [r[0] for r in db.query(VideoComment.uid).filter(
        VideoComment.task_id == video_task_id, VideoComment.uid > 0
    ).distinct().limit(50).all()]

    profiles = db.query(BiliUserProfile).filter(
        BiliUserProfile.uid.in_(comment_uids)
    ).limit(30).all()

    if not profiles:
        story.append(Paragraph("（无已分析的用户画像）", BODY_STYLE))
        return

    # Scatter plot
    xs = [p.score_x for p in profiles]
    ys = [p.score_y for p in profiles]
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(xs, ys, c="steelblue", alpha=0.6, s=30)
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.axhline(50, color="gray", alpha=0.2); ax.axvline(50, color="gray", alpha=0.2)
    ax.set_xlabel("反对 ← → 支持"); ax.set_ylabel("理性 ← → 感性")
    ax.set_title("评论区活跃用户分布")
    story.append(_image_from_fig(fig, width=350))

    # Extremes
    extremes = sorted(profiles, key=lambda p: abs(p.score_x - 50) + abs(p.score_y - 50), reverse=True)[:4]
    for p in extremes:
        story.append(Paragraph(
            f"<b>@{p.name}</b> — 位置({p.score_x},{p.score_y}) — {p.summary or ''}",
            SMALL_STYLE))


def _md_to_html(text: str) -> str:
    """Simple markdown → reportlab-compatible HTML tags."""
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)       # bold
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", text)  # italic
    text = re.sub(r"^###\s+(.+)", r"<b>\1</b>", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+(.+)", r'<font size="12"><b>\1</b></font>', text, flags=re.MULTILINE)
    text = re.sub(r"^- (.+)", r"• \1", text, flags=re.MULTILINE)  # bullet list
    return text


# ─────────────────────────────────────────────────────────────
#  Module 9: AI Summary (综合研判摘要)
# ─────────────────────────────────────────────────────────────

def module_ai_summary(story, saved_ot, db, ds_api_key=None, video_task_id=None):
    story.append(PageBreak())
    story.append(Paragraph("第九章  AI综合研判摘要", CHAP_STYLE))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#e2e8f0")))

    if not ds_api_key:
        story.append(Paragraph("（未配置DeepSeek API Key，无法生成）", BODY_STYLE))
        return

    # Collect seed data
    trail = saved_ot and saved_ot.centroid_trail or []
    trail_samples = []
    if len(trail) >= 5:
        indices = [0, len(trail)//4, len(trail)//2, 3*len(trail)//4, len(trail)-1]
        trail_samples = [f"  {trail[i]['t']}: 质心({trail[i]['x']:.0f},{trail[i]['y']:.0f})，{trail[i]['count']}条" for i in indices]

    # Top comments
    from app.models import VideoComment
    top_comments = []
    if video_task_id and db:
        top_comments = db.query(VideoComment).filter(
            VideoComment.task_id == video_task_id, VideoComment.coord_x >= 0
        ).order_by(VideoComment.like_count.desc()).limit(5).all()

    # Build prompt
    prompt = f"""你是一位冷静的舆情分析师。请基于以下数据，生成500字以内的综合研判。

1. 质心漂移关键节点：
{chr(10).join(trail_samples) if trail_samples else '(无)'}

2. 点赞最高5条评论：
{chr(10).join(f'  @{c.user}: {c.content[:100]}' for c in top_comments) if top_comments else '(无)'}

请分析：舆论是否极化、事件演化逻辑、潜在风险点、建议关注方向。直接输出分析文字，不要JSON。"""

    try:
        import httpx
        resp = httpx.post("https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {ds_api_key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 800, "temperature": 0.5}, timeout=90)
        result = resp.json()["choices"][0]["message"]["content"].strip()
        html_text = _md_to_html(result)
        for line in html_text.split("\n"):
            story.append(Paragraph(line or "&nbsp;", BODY_STYLE))
    except Exception as e:
        story.append(Paragraph(f"AI分析失败：{e}", BODY_STYLE))


# ─────────────────────────────────────────────────────────────
#  Main entry point
# ─────────────────────────────────────────────────────────────

MODULES = {
    "overview": module_overview,
    "heatmap": module_heatmap,
    "camps": module_camps,
    "trail": module_trail,
    "clusters": module_clusters,
    "opposition": module_opposition,
    "wordcloud": module_wordcloud,
    "users": module_users,
    "ai_summary": module_ai_summary,
}

MODULE_LABELS = {
    "overview": ("事件总览", "封面/摘要页，展示视频基本信息、评论统计、整体质心"),
    "heatmap": ("舆论地形图", "基于101×101密度矩阵的二维热力图，含质心标注"),
    "camps": ("情感阵营分布", "反对/中立/支持三阵营统计 + DeepSeek一句话总结"),
    "trail": ("质心漂移轨迹", "时间轴推演：质心随时间移动的轨迹图，含关键节点和转折标记"),
    "clusters": ("群体聚类画廊", "聚类分群结果卡片：定义、核心主张、论据、物质基础"),
    "opposition": ("高赞观点与对立面", "TOP15高赞评论表格 + 对立面解析文字"),
    "wordcloud": ("词云与争议词", "高频词云图 + 阵营间争议关键词"),
    "users": ("评论区用户图谱", "活跃用户散点图 + 极端位置用户画像"),
    "ai_summary": ("AI综合研判摘要", "DeepSeek生成500字舆情研判（需API Key）"),
}


def generate_pdf(saved_ot_id: int, modules: list, db, ds_api_key: str = None,
                  refresh_camps: bool = False, progress_cb=None) -> BytesIO:
    """Generate PDF report with user-selected modules.
    progress_cb(step, total, message) called between modules.
    Returns BytesIO buffer ready for streaming."""
    from app.models import SavedOpinionTimelineTask

    def _progress(step, msg):
        if progress_cb: progress_cb(step, len(modules) + 2, msg)

    _progress(0, "正在加载数据...")
    saved_ot = db.query(SavedOpinionTimelineTask).filter(
        SavedOpinionTimelineTask.id == saved_ot_id
    ).first()
    if not saved_ot:
        raise ValueError("保存记录不存在")

    video_task = None
    video_task_id = None
    saved_va = None
    try:
        from app.models import SavedVaTask, VideoAnalysisTask
        saved_va = db.query(SavedVaTask).filter(SavedVaTask.bvid == saved_ot.bvid).first()
        video_task = db.query(VideoAnalysisTask).filter(
            VideoAnalysisTask.bvid == saved_ot.bvid
        ).order_by(VideoAnalysisTask.created_at.desc()).first()
        if video_task:
            video_task_id = video_task.id
    except:
        pass

    _progress(1, "正在构建文档...")
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=THESIS_LEFT, rightMargin=THESIS_RIGHT,
                             topMargin=THESIS_TOP, bottomMargin=THESIS_BOTTOM)
    story = []

    # ── Cover page (thesis style) ──
    t = saved_ot.title or saved_ot.bvid
    story.append(Spacer(1, 40))
    story.append(Paragraph("Miho-spot 舆情分析报告", THESIS_TITLE))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"《{t}》", ParagraphStyle("CoverTitle", fontName=FONT, fontSize=18,
                         leading=26, textColor=black, alignment=TA_CENTER, spaceAfter=30)))
    story.append(Spacer(1, 40))
    story.append(Paragraph(f"生成日期：{datetime.now().strftime('%Y年%m月%d日')}", COVER_LABEL))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"分析工具：Miho-spot 舆情监测系统 v1.4", COVER_INFO))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"数据来源：Bilibili 视频评论区", COVER_INFO))
    story.append(PageBreak())

    # ── 摘要 ──
    story.append(Paragraph("摘  要", CHAP_STYLE))
    story.append(Paragraph(f"本报告基于B站视频《{t}》的评论数据，运用DeepSeek AI情感分析与坐标映射技术，"
                            f"从舆论地形分布、情感阵营划分、时间轴演化、群体聚类等多个维度，"
                            f"对该视频的评论区舆论场进行全面、系统的分析。", BODY_STYLE))
    story.append(Paragraph(f"共采集 {saved_ot.total_comments or 0} 条评论，成功分析 {saved_ot.analyzed_count or 0} 条。"
                            f"整体舆论质心位于坐标 ({saved_ot.centroid_x or 50:.1f}, {saved_ot.centroid_y or 50:.1f})。", BODY_STYLE))
    story.append(PageBreak())

    # ── 目录 (placeholder) ──
    story.append(Paragraph("目  录", CHAP_STYLE))
    for mod_key in modules:
        label = MODULE_LABELS.get(mod_key, (mod_key, ""))[0]
        cn = _MODULE_TO_CHAPTER.get(mod_key, "？")
        story.append(Paragraph(f"第{cn}章  {label} ...............................", BODY_NO_INDENT))
    story.append(Paragraph("参考文献  ............................................", BODY_NO_INDENT))
    story.append(PageBreak())

    step = 1
    for mod_key in modules:
        step += 1
        label = MODULE_LABELS.get(mod_key, (mod_key, ""))[0]
        _progress(step, f"正在生成：{label}")
        if mod_key not in MODULES:
            continue
        try:
            func = MODULES[mod_key]
            # Build kwargs per module — each takes only what it needs
            if mod_key == "overview":
                func(story, saved_ot, saved_va, video_task)
            elif mod_key == "heatmap":
                func(story, saved_ot)
            elif mod_key == "camps":
                func(story, saved_ot, db, ds_api_key, video_task_id)
            elif mod_key == "trail":
                func(story, saved_ot)
            elif mod_key == "clusters":
                func(story, saved_ot, db)
            elif mod_key == "opposition":
                func(story, saved_ot, db, ds_api_key, video_task_id)
            elif mod_key == "wordcloud":
                func(story, saved_ot, db, video_task_id)
            elif mod_key == "users":
                func(story, saved_ot, db, video_task_id)
            elif mod_key == "ai_summary":
                func(story, saved_ot, db, ds_api_key, video_task_id)
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            story.append(Paragraph(
                f'<font color="#ef4444"><b>模块《{label}》生成失败：</b>{str(e)[:200]}</font>',
                BODY_STYLE))
            story.append(Paragraph(
                f'<font color="#64748b" size="7">{err_msg[-300:]}</font>', SMALL_STYLE))

    # ── 参考文献 ──
    story.append(PageBreak())
    story.append(Paragraph("参考文献", CHAP_STYLE))
    refs = [
        "Miho-spot 舆情监测系统 v1.4, https://github.com/user/miho-spot",
        "Bilibili API 文档, https://api.bilibili.com",
        "DeepSeek API, https://platform.deepseek.com",
        "TDesign React 组件库, https://tdesign.tencent.com",
        "AICU 第三方数据接口, https://api.aicu.cc",
        "ReportLab PDF 生成库, https://www.reportlab.com",
        "Matplotlib 数据可视化库, https://matplotlib.org",
    ]
    for i, ref in enumerate(refs, 1):
        story.append(Paragraph(f"[{i}] {ref}", BODY_NO_INDENT))

    _progress(step + 1, "正在渲染PDF...")
    try:
        doc.build(story)
    except Exception as build_err:
        # Fallback: rebuild with text-only (skip images that overflow)
        story.append(Paragraph(
            f'<font color="#ef4444"><b>PDF渲染异常：</b>{build_err}</font>', BODY_STYLE))
        story.append(Paragraph("正在降级重试（跳过图片）...", SMALL_STYLE))
        text_only = []
        for f in story:
            if isinstance(f, Image):
                text_only.append(Paragraph("[图片已跳过以规避布局错误]", SMALL_STYLE))
            else:
                text_only.append(f)
        buf = BytesIO()
        doc2 = SimpleDocTemplate(buf, pagesize=A4,
                                  leftMargin=THESIS_LEFT, rightMargin=THESIS_RIGHT,
                                  topMargin=THESIS_TOP, bottomMargin=THESIS_BOTTOM)
        doc2.build(text_only)

    buf.seek(0)
    _progress(step + 2, "完成！")
    return buf
