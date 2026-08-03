"""
阅流·书星平台 — FastAPI 后端主程序
替代 Replit 运行主服务、API 接口、SQLite 数据库、定时任务
"""

import os
import sqlite3
import json
import time
import asyncio
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager, asynccontextmanager
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ---------- 环境变量 ----------
# Render 平台通过 Dashboard 设置环境变量，不需要 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
COZE_WORKFLOW_ID = os.getenv("COZE_WORKFLOW_ID", "")
COZE_TOKEN = os.getenv("COZE_TOKEN", "")
YUELIU_AK = os.getenv("YUELIU_AK", "")
YUELIU_SK = os.getenv("YUELIU_SK", "")
BACKEND_URL = os.getenv("BACKEND_URL", "")  # Render 部署后的公网地址，用于保活

# ---------- 日志 ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("yueliu-bookstar")

# ---------- 数据库 ----------
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yueliu.db")


@contextmanager
def get_db():
    """获取数据库连接（上下文管理器，自动提交/关闭）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库 — 创建全部 5 张数据表"""
    with get_db() as conn:
        # 1. 创作者表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS creators (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                phone       TEXT,
                member_level TEXT DEFAULT '免费',   -- 免费 / 基础会员 / 专业会员
                balance     REAL DEFAULT 0,           -- 账户余额
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        # 2. 出版社表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS publishers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                contact     TEXT,
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        # 3. 图书推广任务表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS book_tasks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                publisher_id    INTEGER NOT NULL,
                book_name       TEXT NOT NULL,
                book_isbn       TEXT,
                book_type       TEXT NOT NULL,          -- 童书/职场/心理/文学/综合
                book_info       TEXT,
                commission_rate REAL DEFAULT 0.3,       -- 出版社设定的佣金比例
                digital_human_id TEXT DEFAULT 'default',
                status          TEXT DEFAULT 'pending', -- pending/claimed/generating/published/completed
                creator_id      INTEGER,
                video_id        INTEGER,
                created_at      TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (publisher_id) REFERENCES publishers(id),
                FOREIGN KEY (creator_id) REFERENCES creators(id)
            )
        """)

        # 4. 视频素材存储记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS video_resources (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id         INTEGER NOT NULL,
                script_content  TEXT,       -- 口播文案
                storyboard      TEXT,       -- 分镜文案 JSON
                audio_url       TEXT,       -- 语音合成音频地址
                images_json     TEXT,       -- AI 绘图背景画面 JSON
                video_url       TEXT,       -- 数字人成片 MP4 链接
                distribute_plan TEXT,       -- 分发策略 JSON
                coze_run_id     TEXT,       -- Coze 工作流运行ID
                yueliu_video_id TEXT,       -- 阅流素材库视频ID
                status          TEXT DEFAULT 'pending',  -- pending/generating/completed/failed
                created_at      TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (task_id) REFERENCES book_tasks(id)
            )
        """)

        # 5. 矩阵分发发布记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS distribute_records (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id    INTEGER NOT NULL,
                platform    TEXT NOT NULL,   -- 抖音/小红书/视频号
                publish_time TEXT,            -- 计划发布时间
                title       TEXT,             -- 发布标题
                status      TEXT DEFAULT 'pending',  -- pending/published/failed
                created_at  TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (video_id) REFERENCES video_resources(id)
            )
        """)

        # 6. 订单回调记录表（分账用）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id         INTEGER NOT NULL,
                creator_id      INTEGER NOT NULL,
                order_amount    REAL NOT NULL,        -- 订单金额
                commission_amount REAL DEFAULT 0,     -- 总佣金
                platform_fee    REAL DEFAULT 0,        -- 平台服务费
                creator_earnings REAL DEFAULT 0,      -- 创作者实得
                status          TEXT DEFAULT 'settled',
                created_at      TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (task_id) REFERENCES book_tasks(id),
                FOREIGN KEY (creator_id) REFERENCES creators(id)
            )
        """)

    logger.info("数据库初始化完成，5 张业务表 + 1 张订单表已就绪")


# ---------- 生命周期 ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的生命周期管理"""
    try:
        init_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
    asyncio.create_task(keepalive_loop())
    logger.info("阅流·书星平台后端启动完成")
    yield


# ---------- FastAPI 应用 ----------
app = FastAPI(
    title="阅流·书星平台 API",
    description="图书数字人短视频全自动生产 + 多平台分发带货 + 自动分账盈利系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 允许所有来源跨域（GitHub Pages 前端需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
#  数据模型 (Pydantic)
# ============================================================

class CreatorCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    member_level: str = "免费"

class PublisherCreate(BaseModel):
    name: str
    contact: Optional[str] = None

class BookTaskCreate(BaseModel):
    publisher_id: int
    book_name: str
    book_isbn: Optional[str] = None
    book_type: str  # 童书/职场/心理/文学/综合
    book_info: Optional[str] = None
    commission_rate: float = 0.3
    digital_human_id: str = "default"

class TaskClaim(BaseModel):
    creator_id: int

class CozeCallRequest(BaseModel):
    task_id: int

class OrderCallback(BaseModel):
    task_id: int
    creator_id: int
    order_amount: float


# ============================================================
#  基础接口
# ============================================================

@app.get("/")
async def root():
    """健康检查 / 根路径"""
    return {"status": "running", "service": "阅流·书星平台", "time": datetime.now().isoformat()}


@app.get("/api/keepalive")
async def keepalive():
    """保活接口 — 供定时器自调用，防止 Render 休眠"""
    return {"alive": True, "timestamp": datetime.now().isoformat()}


# ============================================================
#  创作者接口
# ============================================================

@app.post("/api/creators")
async def create_creator(data: CreatorCreate):
    """注册创作者"""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO creators (name, phone, member_level) VALUES (?, ?, ?)",
            (data.name, data.phone, data.member_level),
        )
        creator_id = cursor.lastrowid
    return {"code": 0, "msg": "注册成功", "data": {"creator_id": creator_id}}


@app.get("/api/creators")
async def list_creators():
    """创作者列表"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM creators ORDER BY id DESC").fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}


@app.get("/api/creators/{creator_id}")
async def get_creator(creator_id: int):
    """创作者详情（含余额、作品数）"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM creators WHERE id=?", (creator_id,)).fetchone()
        if not row:
            raise HTTPException(404, "创作者不存在")
        video_count = conn.execute(
            "SELECT COUNT(*) FROM video_resources v JOIN book_tasks t ON v.task_id=t.id WHERE t.creator_id=?",
            (creator_id,),
        ).fetchone()[0]
        order_count = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(creator_earnings),0) FROM orders WHERE creator_id=?",
            (creator_id,),
        ).fetchone()
    result = dict(row)
    result["video_count"] = video_count
    result["total_earnings"] = order_count[1]
    return {"code": 0, "data": result}


# ============================================================
#  出版社接口
# ============================================================

@app.post("/api/publishers")
async def create_publisher(data: PublisherCreate):
    """注册出版社"""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO publishers (name, contact) VALUES (?, ?)",
            (data.name, data.contact),
        )
        publisher_id = cursor.lastrowid
    return {"code": 0, "msg": "注册成功", "data": {"publisher_id": publisher_id}}


@app.get("/api/publishers")
async def list_publishers():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM publishers ORDER BY id DESC").fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}


# ============================================================
#  图书任务接口
# ============================================================

@app.post("/api/publishers/{publisher_id}/tasks")
async def create_book_task(publisher_id: int, data: BookTaskCreate):
    """
    出版社发布图书推广任务
    发布后自动触发 Coze 工作流生成数字人短视频（全自动，无需人工二次操作）
    """
    with get_db() as conn:
        # 验证出版社存在
        pub = conn.execute("SELECT id FROM publishers WHERE id=?", (publisher_id,)).fetchone()
        if not pub:
            raise HTTPException(404, "出版社不存在")

        cursor = conn.execute(
            """INSERT INTO book_tasks
               (publisher_id, book_name, book_isbn, book_type, book_info, commission_rate, digital_human_id, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (publisher_id, data.book_name, data.book_isbn, data.book_type,
             data.book_info, data.commission_rate, data.digital_human_id),
        )
        task_id = cursor.lastrowid

        # 同时创建视频素材记录（pending 状态）
        conn.execute(
            "INSERT INTO video_resources (task_id, status) VALUES (?, 'pending')",
            (task_id,),
        )
        video_id = conn.execute(
            "SELECT id FROM video_resources WHERE task_id=? ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchone()[0]

        # 更新任务的 video_id
        conn.execute("UPDATE book_tasks SET video_id=? WHERE id=?", (video_id, task_id))

    logger.info(f"图书任务已创建: task_id={task_id}, book={data.book_name}, 自动触发AI生成...")

    # 异步触发 Coze 工作流（不阻塞响应）
    asyncio.create_task(trigger_coze_workflow(task_id, data.book_name, data.book_type,
                                               data.book_info or "", data.digital_human_id))

    return {
        "code": 0,
        "msg": "任务发布成功，AI 短视频正在自动生成中",
        "data": {"task_id": task_id, "video_id": video_id, "status": "generating"},
    }


@app.get("/api/tasks")
async def list_tasks(
    status: Optional[str] = Query(None, description="按状态筛选: pending/claimed/generating/published/completed"),
    creator_id: Optional[int] = Query(None),
):
    """图书任务列表（可按状态、创作者筛选）"""
    sql = """
        SELECT t.*, p.name as publisher_name,
               v.status as video_status, v.video_url
        FROM book_tasks t
        LEFT JOIN publishers p ON t.publisher_id = p.id
        LEFT JOIN video_resources v ON t.video_id = v.id
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND t.status=?"
        params.append(status)
    if creator_id:
        sql += " AND t.creator_id=?"
        params.append(creator_id)
    sql += " ORDER BY t.id DESC"

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: int):
    """任务详情（含视频素材信息）"""
    with get_db() as conn:
        task = conn.execute(
            """SELECT t.*, p.name as publisher_name FROM book_tasks t
               LEFT JOIN publishers p ON t.publisher_id = p.id WHERE t.id=?""",
            (task_id,),
        ).fetchone()
        if not task:
            raise HTTPException(404, "任务不存在")

        video = conn.execute(
            "SELECT * FROM video_resources WHERE task_id=? ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchone()

        distributes = conn.execute(
            "SELECT * FROM distribute_records WHERE video_id=? ORDER BY id DESC",
            (video["id"],) if video else (0,),
        ).fetchall()

    result = dict(task)
    result["video"] = dict(video) if video else None
    result["distributes"] = [dict(r) for r in distributes]
    return {"code": 0, "data": result}


@app.post("/api/tasks/{task_id}/claim")
async def claim_task(task_id: int, data: TaskClaim):
    """创作者认领图书任务"""
    with get_db() as conn:
        task = conn.execute("SELECT * FROM book_tasks WHERE id=?", (task_id,)).fetchone()
        if not task:
            raise HTTPException(404, "任务不存在")
        if task["status"] != "pending":
            raise HTTPException(400, f"任务当前状态为 {task['status']}，无法认领")

        conn.execute(
            "UPDATE book_tasks SET creator_id=?, status='claimed' WHERE id=?",
            (data.creator_id, task_id),
        )
    return {"code": 0, "msg": "认领成功", "data": {"task_id": task_id, "status": "claimed"}}


# ============================================================
#  Coze 工作流调用接口
# ============================================================

async def trigger_coze_workflow(task_id: int, book_name: str, book_type: str,
                                 book_info: str, digital_human_id: str):
    """
    后端调用 Coze 工作流，全自动生成短视频全套素材
    工作流 8 节点：分支提示词 → 口播文案 → 分镜 → 语音 → AI绘图 → 数字人视频 → 分发策略 → JSON返回
    """
    logger.info(f"[Coze] 开始调用工作流: task_id={task_id}, book={book_name}")

    # 更新任务状态为生成中
    with get_db() as conn:
        conn.execute("UPDATE book_tasks SET status='generating' WHERE id=?", (task_id,))
        conn.execute("UPDATE video_resources SET status='generating' WHERE task_id=?", (task_id,))

    try:
        # 调用 Coze 工作流 API
        headers = {
            "Authorization": f"Bearer {COZE_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "workflow_id": COZE_WORKFLOW_ID,
            "parameters": {
                "book_name": book_name,
                "book_type": book_type,
                "book_info": book_info,
                "digital_human_id": digital_human_id,
            },
        }

        # Coze 工作流执行 API
        resp = requests.post(
            "https://api.coze.cn/v1/workflow/run",
            headers=headers,
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()

        # 解析 Coze 返回的数据
        # Coze 工作流返回的 data 字段是 JSON 字符串
        workflow_data = result.get("data", "{}")
        if isinstance(workflow_data, str):
            workflow_data = json.loads(workflow_data)

        # 提取各节点产出
        script_content = workflow_data.get("script", "")
        storyboard = workflow_data.get("storyboard", "")
        audio_url = workflow_data.get("audio_url", "")
        images = workflow_data.get("images", "[]")
        video_url = workflow_data.get("video_url", "")
        distribute_plan = workflow_data.get("distribute_plan", "{}")
        coze_run_id = result.get("execute_id", str(task_id))

        # 保存到数据库
        with get_db() as conn:
            conn.execute(
                """UPDATE video_resources SET
                   script_content=?, storyboard=?, audio_url=?, images_json=?,
                   video_url=?, distribute_plan=?, coze_run_id=?, status='completed'
                   WHERE task_id=?""",
                (script_content, storyboard, audio_url, json.dumps(images, ensure_ascii=False),
                 video_url, json.dumps(distribute_plan, ensure_ascii=False), coze_run_id, task_id),
            )
            conn.execute("UPDATE book_tasks SET status='published' WHERE id=?", (task_id,))

        logger.info(f"[Coze] 工作流执行成功: task_id={task_id}, video_url={video_url}")

        # 自动上传阅流 Pro 素材库
        video_id = conn_execute_get_video_id(task_id)
        if video_url:
            asyncio.create_task(upload_to_yueliu(video_id, video_url, book_type))

        # 自动设置分发计划
        if distribute_plan:
            asyncio.create_task(setup_distribution(video_id, distribute_plan))

    except Exception as e:
        logger.error(f"[Coze] 工作流调用失败: task_id={task_id}, error={e}")
        with get_db() as conn:
            conn.execute("UPDATE video_resources SET status='failed' WHERE task_id=?", (task_id,))
            conn.execute("UPDATE book_tasks SET status='pending' WHERE id=?", (task_id,))


def conn_execute_get_video_id(task_id: int) -> int:
    """获取任务对应的最新视频记录ID"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM video_resources WHERE task_id=? ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchone()
    return row[0] if row else 0


@app.post("/api/call_coze")
async def call_coze(data: CozeCallRequest):
    """手动触发 Coze 工作流（管理接口）"""
    with get_db() as conn:
        task = conn.execute("SELECT * FROM book_tasks WHERE id=?", (data.task_id,)).fetchone()
        if not task:
            raise HTTPException(404, "任务不存在")

    asyncio.create_task(trigger_coze_workflow(
        data.task_id, task["book_name"], task["book_type"],
        task["book_info"] or "", task["digital_human_id"] or "default",
    ))
    return {"code": 0, "msg": "Coze 工作流已触发", "data": {"task_id": data.task_id}}


# ============================================================
#  阅流 Pro 素材存储接口
# ============================================================

async def upload_to_yueliu(video_id: int, video_url: str, book_type: str):
    """视频素材自动上传阅流 Pro 云端素材库，按赛道分类归档"""
    logger.info(f"[阅流] 开始上传视频到阅流Pro: video_id={video_id}, type={book_type}")

    try:
        # 阅流 Pro 开放平台 API — 上传素材
        headers = {
            "Authorization": f"AK {YUELIU_AK}",
            "Content-Type": "application/json",
        }
        payload = {
            "video_url": video_url,
            "category": book_type,  # 按赛道分类: 童书/职场/心理/文学/综合
            "ak": YUELIU_AK,
            "sk": YUELIU_SK,
        }

        resp = requests.post(
            "https://open.yueliu.com/api/v1/material/upload",
            headers=headers,
            json=payload,
            timeout=60,
        )

        if resp.status_code == 200:
            result = resp.json()
            yueliu_video_id = result.get("data", {}).get("video_id", "")
            with get_db() as conn:
                conn.execute(
                    "UPDATE video_resources SET yueliu_video_id=? WHERE id=?",
                    (yueliu_video_id, video_id),
                )
            logger.info(f"[阅流] 视频上传成功: yueliu_video_id={yueliu_video_id}")
        else:
            logger.warning(f"[阅流] 视频上传失败: HTTP {resp.status_code}")

    except Exception as e:
        logger.error(f"[阅流] 上传异常: {e}")


@app.post("/api/save_video")
async def save_video(task_id: int, video_url: str = "", script_content: str = ""):
    """手动保存视频素材信息（管理接口）"""
    with get_db() as conn:
        conn.execute(
            """UPDATE video_resources SET video_url=?, script_content=?, status='completed'
               WHERE task_id=?""",
            (video_url, script_content, task_id),
        )
    return {"code": 0, "msg": "视频素材已保存"}


# ============================================================
#  多平台分发接口
# ============================================================

async def setup_distribution(video_id: int, distribute_plan):
    """解析分发配置，设置多平台定时发布计划"""
    logger.info(f"[分发] 设置分发计划: video_id={video_id}")

    if isinstance(distribute_plan, str):
        try:
            distribute_plan = json.loads(distribute_plan)
        except json.JSONDecodeError:
            distribute_plan = {}

    platforms = distribute_plan.get("platforms", ["抖音", "小红书", "视频号"])
    publish_times = distribute_plan.get("publish_times", {})
    titles = distribute_plan.get("titles", {})

    now = datetime.now()
    records = []

    with get_db() as conn:
        for i, platform in enumerate(platforms):
            # 默认每隔 2 小时发一个平台
            publish_time = (now + timedelta(hours=2 * (i + 1))).strftime("%Y-%m-%d %H:%M")
            if isinstance(publish_times, dict):
                publish_time = publish_times.get(platform, publish_time)
            title = titles.get(platform, "") if isinstance(titles, dict) else ""

            cursor = conn.execute(
                """INSERT INTO distribute_records
                   (video_id, platform, publish_time, title, status)
                   VALUES (?, ?, ?, ?, 'pending')""",
                (video_id, platform, publish_time, title),
            )
            records.append({
                "platform": platform,
                "publish_time": publish_time,
                "record_id": cursor.lastrowid,
            })

    logger.info(f"[分发] 已创建 {len(records)} 条分发记录")
    return records


@app.post("/api/auto_distribute")
async def auto_distribute(video_id: int):
    """手动触发分发计划设置（管理接口）"""
    with get_db() as conn:
        video = conn.execute("SELECT * FROM video_resources WHERE id=?", (video_id,)).fetchone()
        if not video:
            raise HTTPException(404, "视频不存在")

        distribute_plan = video["distribute_plan"] or "{}"
        if isinstance(distribute_plan, str):
            distribute_plan = json.loads(distribute_plan)

    records = await setup_distribution(video_id, distribute_plan)
    return {"code": 0, "msg": "分发计划已设置", "data": records}


@app.get("/api/distributes")
async def list_distributes(video_id: Optional[int] = None):
    """分发记录列表"""
    sql = "SELECT d.*, v.task_id FROM distribute_records d LEFT JOIN video_resources v ON d.video_id=v.id"
    params = []
    if video_id:
        sql += " WHERE d.video_id=?"
        params.append(video_id)
    sql += " ORDER BY d.id DESC"

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}


# ============================================================
#  订单回调 & 分账计算接口（核心盈利闭环）
# ============================================================

# 分账比例配置 — 平台服务费抽成
RATIO_MAP = {
    "免费": 0.10,       # 平台抽 10%
    "基础会员": 0.08,    # 平台抽 8%
    "专业会员": 0.05,    # 平台抽 5%
}

# 拉新奖励
REFERRAL_BONUS = 5.0  # 每笔成交额外奖励 5 元


@app.post("/api/order_callback")
async def order_callback(data: OrderCallback):
    """
    订单成交回调接口 — 自动核算创作者佣金分账
    收益计算公式：创作者实得佣金 = 总佣金 - 平台服务费 + 拉新奖励
    """
    with get_db() as conn:
        # 查询任务和创作者信息
        task = conn.execute("SELECT * FROM book_tasks WHERE id=?", (data.task_id,)).fetchone()
        if not task:
            raise HTTPException(404, "任务不存在")

        creator = conn.execute("SELECT * FROM creators WHERE id=?", (data.creator_id,)).fetchone()
        if not creator:
            raise HTTPException(404, "创作者不存在")

        # 计算佣金
        commission_rate = task["commission_rate"]
        total_commission = round(data.order_amount * commission_rate, 2)

        # 根据会员等级计算平台服务费
        member_level = creator["member_level"]
        platform_fee_rate = RATIO_MAP.get(member_level, 0.10)
        platform_fee = round(total_commission * platform_fee_rate, 2)

        # 创作者实得 = 总佣金 - 平台服务费 + 拉新奖励
        creator_earnings = round(total_commission - platform_fee + REFERRAL_BONUS, 2)

        # 写入订单记录
        cursor = conn.execute(
            """INSERT INTO orders
               (task_id, creator_id, order_amount, commission_amount, platform_fee, creator_earnings, status)
               VALUES (?, ?, ?, ?, ?, ?, 'settled')""",
            (data.task_id, data.creator_id, data.order_amount,
             total_commission, platform_fee, creator_earnings),
        )
        order_id = cursor.lastrowid

        # 更新创作者余额
        conn.execute(
            "UPDATE creators SET balance = balance + ? WHERE id=?",
            (creator_earnings, data.creator_id),
        )

    logger.info(
        f"[分账] 订单结算成功: order_id={order_id}, "
        f"金额={data.order_amount}, 佣金={total_commission}, "
        f"平台费={platform_fee}, 创作者实得={creator_earnings}"
    )

    return {
        "code": 0,
        "msg": "订单分账结算成功",
        "data": {
            "order_id": order_id,
            "order_amount": data.order_amount,
            "total_commission": total_commission,
            "platform_fee": platform_fee,
            "creator_earnings": creator_earnings,
            "member_level": member_level,
        },
    }


@app.get("/api/orders")
async def list_orders(creator_id: Optional[int] = None):
    """订单列表（可按创作者筛选，用于「我的账单」）"""
    sql = """
        SELECT o.*, t.book_name, t.book_type FROM orders o
        LEFT JOIN book_tasks t ON o.task_id = t.id
    """
    params = []
    if creator_id:
        sql += " WHERE o.creator_id=?"
        params.append(creator_id)
    sql += " ORDER BY o.id DESC"

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}


# ============================================================
#  保活定时器 — 防止 Render 免费版 15 分钟休眠
# ============================================================

async def keepalive_loop():
    """每隔 10 分钟自动访问自身接口，最大程度减少休眠"""
    if not BACKEND_URL or BACKEND_URL == "pending":
        logger.warning("未配置有效的 BACKEND_URL，保活定时器未启动")
        return

    while True:
        await asyncio.sleep(600)  # 10 分钟
        try:
            resp = await asyncio.to_thread(requests.get, f"{BACKEND_URL}/api/keepalive", timeout=10)
            logger.info(f"[保活] 自检成功: {resp.status_code}")
        except Exception as e:
            logger.warning(f"[保活] 自检失败: {e}")


# ============================================================
#  启动入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
