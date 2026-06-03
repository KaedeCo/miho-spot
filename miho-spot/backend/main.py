"""
Miho-spot Backend - FastAPI Server Entry Point
Usage: python main.py [--gui] [--port 8000]
"""
import sys
import os
import threading
from contextlib import asynccontextmanager

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.routes import router
from app.models import init_db, SessionLocal, KeywordModel, AccountModel
from datetime import datetime

# Initialize database and seed default data
def seed_default_data():
    db = SessionLocal()
    try:
        platforms = ["zhihu", "douyin", "tieba", "tophub"]
        for p in platforms:
            existing = db.query(AccountModel).filter(AccountModel.platform == p).first()
            if not existing:
                username = ""  # No pre-configured key in source
                db.add(AccountModel(platform=p, username=username, cookie="", is_valid=False))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_default_data()
    from app.sentiment import seed_default_keywords
    seed_default_keywords()
    # Sync JSON files → DB at startup
    from app.api.routes import sync_daily_stats_from_json, sync_hot_topics_from_json, _load_hot_crawl_from_file, _load_today_search_to_cache
    print("[Miho-spot] Syncing JSON files to database...")
    sync_hot_topics_from_json()
    sync_daily_stats_from_json()
    # Also preload into memory cache for instant dashboard rendering
    _load_hot_crawl_from_file()
    _load_today_search_to_cache()
    print("[Miho-spot] Database initialized and server started.")
    yield
    print("[Miho-spot] Server shutting down.")


app = FastAPI(
    title="Miho-spot API",
    description="米哈游舆情监测系统后端 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router)


@app.get("/")
async def root():
    return {
        "name": "Miho-spot API",
        "version": "1.0.0",
        "description": "米哈游舆情监测系统",
    }


def run_server(host: str = "0.0.0.0", port: int = 8000):
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Miho-spot Backend Server")
    parser.add_argument("--gui", action="store_true", help="Launch GUI monitor panel alongside the server")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    args = parser.parse_args()

    if args.gui:
        print("[Miho-spot] Starting server with GUI monitor...")
        # Start server in background thread
        server_thread = threading.Thread(target=run_server, args=("0.0.0.0", args.port), daemon=True)
        server_thread.start()
        # Launch GUI (blocking)
        from app.monitor import run_gui
        run_gui(host="0.0.0.0", port=args.port)
    else:
        run_server(port=args.port)
