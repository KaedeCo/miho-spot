"""
Miho-spot Backend - Database Models
"""
import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "miho_spot.db")

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class HotTopicModel(Base):
    __tablename__ = "hot_topics"

    id = Column(String, primary_key=True)
    platform = Column(String, nullable=False)  # zhihu, douyin, tieba
    title = Column(Text, nullable=False)
    rank = Column(Integer, nullable=False)
    heat = Column(Float, default=0)
    url = Column(Text)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    sentiment = Column(String, default="Neutral")  # Positive, Negative, Neutral, Irrelevant
    related_game = Column(String, nullable=True)
    is_game_related = Column(Boolean, default=False)

    posts = relationship("PostItemModel", back_populates="topic", cascade="all, delete-orphan")


class PostItemModel(Base):
    __tablename__ = "post_items"

    id = Column(String, primary_key=True)
    topic_id = Column(String, ForeignKey("hot_topics.id"), nullable=False)
    platform = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    author = Column(String)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    timestamp = Column(DateTime)
    sentiment = Column(String, default="Neutral")
    url = Column(Text)

    topic = relationship("HotTopicModel", back_populates="posts")


class DailyStatsModel(Base):
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, unique=True, nullable=False)
    total_topics = Column(Integer, default=0)
    game_related = Column(Integer, default=0)
    positive = Column(Integer, default=0)
    negative = Column(Integer, default=0)
    neutral = Column(Integer, default=0)
    irrelevant = Column(Integer, default=0)
    by_platform = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class KeywordModel(Base):
    __tablename__ = "keywords"

    id = Column(String, primary_key=True)
    keyword = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    added_by = Column(String, default="system")  # system or user


class AccountModel(Base):
    __tablename__ = "accounts"

    platform = Column(String, primary_key=True)
    username = Column(String)
    cookie = Column(Text)
    is_valid = Column(Boolean, default=False)
    last_verified = Column(DateTime, nullable=True)


class BiliUserProfile(Base):
    """Persistent B站 user profile with analysis results."""
    __tablename__ = "bili_user_profiles"

    uid = Column(Integer, primary_key=True)
    name = Column(String)
    face = Column(String, default="")
    score_x = Column(Integer, default=50)   # 米哈游态度 0-100
    score_y = Column(Integer, default=50)   # 理性程度 0-100
    mihoyo_attitude = Column(Text)
    active_areas = Column(Text)
    personality = Column(Text)
    summary = Column(Text)
    comments_json = Column(JSON, default=list)  # [{rpid, content, time_str, matched_keywords, ...}, ...]
    content_json = Column(JSON, default=list)   # [{type, id, title, url, time_str, play, ...}, ...]
    saved_at = Column(DateTime, default=datetime.utcnow)


# ==================== Video Analysis Models ====================

class VideoAnalysisTask(Base):
    """Video comment analysis task record."""
    __tablename__ = "video_analysis_tasks"

    id = Column(String, primary_key=True)          # UUID
    bvid = Column(String, nullable=False)
    aid = Column(Integer, default=0)
    title = Column(Text, default="")
    cover_url = Column(Text, default="")

    # Status: idle | fetching | fetched | analyzing | done | error
    status = Column(String, default="idle")
    error_msg = Column(Text, default="")

    # Counts
    total_comments = Column(Integer, default=0)     # total main+sub replies fetched
    matched_count = Column(Integer, default=0)      # keyword-matched comments
    analyzed_count = Column(Integer, default=0)     # DeepSeek-analyzed comments

    # Centroid result (weighted average of all analyzed points)
    centroid_x = Column(Float, default=0.0)         # 0-100: anti↔pro mihoyo (all points including origin)
    centroid_y = Column(Float, default=0.0)         # 0-100: rational↔emotional (all points including origin)

    # Centroid excluding (0,0) origin points — avoids skew from neutral/unanalyzable comments
    centroid_x_no_origin = Column(Float, default=0.0)  # 0-100: anti↔pro mihoyo (excl origin)
    centroid_y_no_origin = Column(Float, default=0.0)  # 0-100: rational↔emotional (excl origin)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at =Column(DateTime, default=datetime.utcnow)


class VideoComment(Base):
    """Individual video comment with DeepSeek coordinates."""
    __tablename__ = "video_comments"

    id = Column(String, primary_key=True)           # f"{task_id}_{rpid}"
    task_id = Column(String, ForeignKey("video_analysis_tasks.id"), nullable=False, index=True)

    rpid = Column(Integer, default=0)               # Bilibili reply ID
    parent_rpid = Column(Integer, default=0)        # 0=main comment, >0=sub-reply
    root_rpid = Column(Integer, default=0)          # root for sub-replies (0 if main)

    uid = Column(Integer, default=0)                # commenter UID
    user = Column(String, default="")               # display name
    content = Column(Text, default="")              # comment text

    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)        # sub-reply count
    ctime = Column(Integer, default=0)              # unix timestamp

    sort_mode = Column(String, default="hot")       # "hot" or "time"

    # Keyword match result
    matched_keywords = Column(JSON, default=list)   # ["原神", "米哈游", ...]

    # DeepSeek coordinate analysis result
    coord_x = Column(Integer, default=-1)           # 0-100: anti↔pro (-1=not analyzed)
    coord_y = Column(Integer, default=-1)           # 0-100: rational↔emotional (-1=not analyzed)

    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("VideoAnalysisTask", backref="comments")


# ==================== Saved Video Analysis Task (归档) ====================

class SavedVaTask(Base):
    """Archived/saved video analysis tasks for long-term storage."""
    __tablename__ = "saved_va_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_task_id = Column(String, nullable=False)  # original VideoAnalysisTask.id
    bvid = Column(String, nullable=False)
    title = Column(Text, default="")
    cover_url = Column(Text, default="")

    # Snapshot of key metrics at save time
    total_comments = Column(Integer, default=0)
    matched_count = Column(Integer, default=0)
    analyzed_count = Column(Integer, default=0)
    centroid_x = Column(Float, default=0.0)
    centroid_y = Column(Float, default=0.0)
    centroid_x_no_origin = Column(Float, default=0.0)
    centroid_y_no_origin = Column(Float, default=0.0)

    saved_at = Column(DateTime, default=datetime.utcnow)


# ==================== Word Cloud (词云) ====================

class WordCloudItem(Base):
    """Generated word cloud data for a saved video analysis task."""
    __tablename__ = "word_clouds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    saved_va_task_id = Column(Integer, ForeignKey("saved_va_tasks.id"), nullable=False)
    
    # Word frequency data as JSON: [{"text": "原神", "count": 150, "weight": 15}, ...]
    words_json = Column(JSON, default=list)
    total_words = Column(Integer, default=0)
    
    generated_at = Column(DateTime, default=datetime.utcnow)


# ==================== Deep Analysis (深度分析) ====================

class DeepAnalysis(Base):
    """DeepSeek deep analysis result for a video's comments."""
    __tablename__ = "deep_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    saved_va_task_id = Column(Integer, ForeignKey("saved_va_tasks.id"), nullable=False)
    
    status = Column(String, default="pending")  # pending | running | done | error
    
    # Analysis content (from DeepSeek)
    overall_trend = Column(Text, default="")       # 舆论总体趋势
    kol_viewpoints = Column(Text, default="")       # 高赞KOL持有观点
    opposition_analysis = Column(Text, default="")  # 对立面解析
    
    raw_response = Column(Text, default="")         # Full LLM response for reference
    error_msg = Column(Text, default="")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# ==================== Identity Queue (查成分任务队列) ====================

class IdentityQueue(Base):
    """Queue for identity-check (查成分) tasks with drag-reorder support."""
    __tablename__ = "identity_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(Integer, nullable=False)
    name = Column(String, default="")
    face = Column(String, default="")
    source = Column(String, default="manual")  # manual | video_analysis_kol
    sort_order = Column(Integer, default=0)     # for drag-reorder
    status = Column(String, default="pending")  # pending | running | done | error
    added_at = Column(DateTime, default=datetime.utcnow)


# ==================== Opinion Timeline (舆情推演) ====================

class OpinionTimelineTask(Base):
    """Opinion timeline evolution task — time-ordered comment analysis with centroid drift tracking."""
    __tablename__ = "opinion_timeline_tasks"

    id = Column(String, primary_key=True)          # UUID
    bvid = Column(String, nullable=False)
    aid = Column(Integer, default=0)
    title = Column(Text, default="")
    cover_url = Column(Text, default="")
    url = Column(Text, default="")

    # Status: idle | fetching | fetched | analyzing | done | error
    status = Column(String, default="idle")
    error_msg = Column(Text, default="")

    # Counts
    total_comments = Column(Integer, default=0)
    analyzed_count = Column(Integer, default=0)

    # 2D heatmap grid: 101x101 array grid[x][y] = comment count at (x,y)
    heatmap_grid = Column(JSON, default=None)

    # Centroid trail: array of {x, y, t: timestamp_label, count: int}
    centroid_trail = Column(JSON, default=None)

    # Final centroid (all comments)
    centroid_x = Column(Float, default=0.0)
    centroid_y = Column(Float, default=0.0)

    # Time range
    time_start = Column(Integer, default=0)  # earliest comment ctime
    time_end = Column(Integer, default=0)    # latest comment ctime

    # Raw comment data with coordinates: [{content, ctime, x, y}, ...]
    comments_data = Column(JSON, default=None)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class SavedOpinionTimelineTask(Base):
    """Archived opinion timeline analysis results."""
    __tablename__ = "saved_opinion_timeline_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_task_id = Column(String, nullable=False)
    bvid = Column(String, nullable=False)
    title = Column(Text, default="")
    cover_url = Column(Text, default="")

    total_comments = Column(Integer, default=0)
    analyzed_count = Column(Integer, default=0)

    heatmap_grid = Column(JSON, default=None)
    centroid_trail = Column(JSON, default=None)
    centroid_x = Column(Float, default=0.0)
    centroid_y = Column(Float, default=0.0)
    time_start = Column(Integer, default=0)
    time_end = Column(Integer, default=0)

    # User-marked timeline landmark nodes (indices into centroid_trail)
    node_indices = Column(JSON, default=None)

    # Raw comment data with coordinates (for clustering)
    comments_data = Column(JSON, default=None)

    saved_at = Column(DateTime, default=datetime.utcnow)


class ClusterAnalysis(Base):
    """Cluster analysis results for opinion timeline data."""
    __tablename__ = "cluster_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    saved_timeline_id = Column(Integer, nullable=False)
    bvid = Column(String, default="")
    title = Column(Text, default="")

    total_comments = Column(Integer, default=0)
    cluster_count = Column(Integer, default=0)

    # clusters: [{id, centroid: {x,y}, members: [{x,y,content}], boundary: [[x,y],...],
    #             deepseek: {definition, coreClaim, arguments: [], materialBasis}}]
    clusters = Column(JSON, default=None)

    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_columns()


def _migrate_columns():
    """Add missing columns to existing tables without dropping data."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)

    # --- saved_opinion_timeline_tasks: add node_indices ---
    if "saved_opinion_timeline_tasks" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("saved_opinion_timeline_tasks")}
        if "node_indices" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE saved_opinion_timeline_tasks ADD COLUMN node_indices JSON"))
                conn.commit()
                print("[Migrate] Added node_indices column to saved_opinion_timeline_tasks")
        if "comments_data" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE saved_opinion_timeline_tasks ADD COLUMN comments_data JSON"))
                conn.commit()
                print("[Migrate] Added comments_data column to saved_opinion_timeline_tasks")

    # --- opinion_timeline_tasks: add comments_data ---
    if "opinion_timeline_tasks" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("opinion_timeline_tasks")}
        if "comments_data" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE opinion_timeline_tasks ADD COLUMN comments_data JSON"))
                conn.commit()
                print("[Migrate] Added comments_data column to opinion_timeline_tasks")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
