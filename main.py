"""
阅流·书星平台 — FastAPI 后端主程序（最小化测试版）
"""
import os
import sqlite3
import asyncio
import logging
from datetime import datetime
from contextlib import contextmanager, asynccontextmanager

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("yueliu")

# ---------- 数据库 ----------
DB_PATH = os.path.join("/tmp", "yueliu.db")

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS creators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                member_level TEXT DEFAULT '免费',
                balance REAL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS publishers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS book_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                publisher_id INTEGER,
                book_name TEXT NOT NULL,
                book_isbn TEXT,
                book_type TEXT DEFAULT '综合',
                book_intro TEXT,
                buy_link TEXT,
                status TEXT DEFAULT '待认领',
                creator_id INTEGER,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                creator_id INTEGER,
                script TEXT,
                video_url TEXT,
                coze_task_id TEXT,
                status TEXT DEFAULT '生成中',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS distributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER,
                platform TEXT,
                post_url TEXT,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                viral_level TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                task_id INTEGER,
                amount REAL,
                order_type TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
    logger.info("数据库初始化完成（6张表）")

# ---------- Pydantic 模型 ----------
class CreatorCreate(BaseModel):
    name: str
    phone: str = ""
    member_level: str = "免费"

class PublisherCreate(BaseModel):
    name: str
    contact: str = ""

class TaskCreate(BaseModel):
    book_name: str
    book_isbn: str = ""
    book_type: str = "综合"
    book_intro: str = ""
    buy_link: str = ""

# ---------- 生命周期 ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== 阅流·书星 启动中 ===")
    try:
        init_db()
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
    logger.info("=== 阅流·书星 启动完成 ===")
    yield
    logger.info("=== 阅流·书星 关闭 ===")

# ---------- FastAPI 应用 ----------
app = FastAPI(
    title="阅流·书星平台 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
#  基础接口
# ============================================================

@app.get("/")
async def root():
    return {"status": "running", "service": "阅流·书星平台", "time": datetime.now().isoformat()}

@app.get("/api/keepalive")
async def keepalive():
    return {"alive": True, "timestamp": datetime.now().isoformat()}

# ============================================================
#  创作者接口
# ============================================================

@app.post("/api/creators")
async def create_creator(data: CreatorCreate):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO creators (name, phone, member_level) VALUES (?, ?, ?)",
            (data.name, data.phone, data.member_level),
        )
        creator_id = cursor.lastrowid
    return {"code": 0, "msg": "注册成功", "data": {"creator_id": creator_id}}

@app.get("/api/creators")
async def list_creators():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM creators ORDER BY id DESC").fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}

@app.get("/api/creators/{creator_id}")
async def get_creator(creator_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM creators WHERE id=?", (creator_id,)).fetchone()
    if not row:
        return {"code": 1, "msg": "创作者不存在"}
    return {"code": 0, "data": dict(row)}

# ============================================================
#  出版社接口
# ============================================================

@app.post("/api/publishers")
async def create_publisher(data: PublisherCreate):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO publishers (name, contact) VALUES (?, ?)",
            (data.name, data.contact),
        )
        pub_id = cursor.lastrowid
    return {"code": 0, "msg": "注册成功", "data": {"publisher_id": pub_id}}

@app.get("/api/publishers")
async def list_publishers():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM publishers ORDER BY id DESC").fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}

@app.post("/api/publishers/{publisher_id}/tasks")
async def create_task(publisher_id: int, data: TaskCreate):
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO book_tasks (publisher_id, book_name, book_isbn, book_type, book_intro, buy_link)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (publisher_id, data.book_name, data.book_isbn, data.book_type, data.book_intro, data.buy_link),
        )
        task_id = cursor.lastrowid
    return {"code": 0, "msg": "任务发布成功", "data": {"task_id": task_id}}

# ============================================================
#  任务接口
# ============================================================

@app.get("/api/tasks")
async def list_tasks(status: str = None):
    with get_db() as conn:
        if status:
            rows = conn.execute("SELECT * FROM book_tasks WHERE status=? ORDER BY id DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM book_tasks ORDER BY id DESC").fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM book_tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        return {"code": 1, "msg": "任务不存在"}
    return {"code": 0, "data": dict(row)}

# ============================================================
#  健康检查（排除线路问题）
# ============================================================

@app.get("/ping")
async def ping():
    return {"pong": True, "time": datetime.now().isoformat()}

# ============================================================
#  启动入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"启动服务，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
