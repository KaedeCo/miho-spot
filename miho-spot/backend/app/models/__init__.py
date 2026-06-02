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


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
