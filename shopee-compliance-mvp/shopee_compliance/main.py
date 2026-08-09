"""
FastAPI 应用入口
"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

# 添加 shopee_compliance 目录到路径，使得 from config import ... 能够正常工作
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import CORS_ORIGINS
from database import init_db, get_db, get_trials_expiring_within_24h, get_expired_trials, expire_trials
from routers import api_scan, pages, api_batch, api_admin
from routers.api_creem import router as creem_router, webhook_router as creem_webhook_router
from routers.api_preferences import router as preferences_router

# URL 解析限流缓存（从 globals 导入）
from globals import URL_PARSE_LIMIT, URL_CACHE, cleanup_all_caches


async def trial_expiry_check():
    """每日定时检查trial到期任务"""
    while True:
        try:
            db = await get_db()
            
            expiring_users = await get_trials_expiring_within_24h(db)
            for user in expiring_users:
                trial_end = datetime.fromisoformat(user["trial_end"])
                date_str = trial_end.strftime('%Y-%m-%d')
                print(f"[WA Reminder] Trial expires tomorrow for {user['email']}, WA: {user['wa_number']}, expires: {date_str}")
            
            expired_users = await get_expired_trials(db)
            if expired_users:
                await expire_trials(db)
                print(f"[Trial Expiry] Expired {len(expired_users)} trials, status changed to free")
            
            await db.close()
        except Exception as e:
            print(f"[Trial Expiry Error] {e}")
        
        await asyncio.sleep(24 * 60 * 60)


async def memory_cache_cleanup():
    """P0-3: 每小时清理内存缓存，防止内存泄漏"""
    while True:
        try:
            cleanup_all_caches()
            # P0-4: 同时清理过期的 session_cache 记录
            db = await get_db()
            from database import cleanup_expired_session_cache
            deleted = await cleanup_expired_session_cache(db)
            if deleted > 0:
                print(f"[Cache Cleanup] session_cache: removed {deleted} expired entries")
            await db.close()
        except Exception as e:
            print(f"[Cache Cleanup Error] {e}")
        await asyncio.sleep(60 * 60)  # 每小时执行一次


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理 - 启动时初始化数据库和定时任务"""
    await init_db()
    
    asyncio.create_task(trial_expiry_check())
    asyncio.create_task(memory_cache_cleanup())  # P0-3: 内存缓存定时清理
    
    yield


app = FastAPI(
    title="Shopee 合规检测工具",
    description="检测商品标题/描述中的违禁词和类目冲突",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(pages.router)
app.include_router(api_scan.router)
app.include_router(api_batch.router)
app.include_router(creem_router)
app.include_router(creem_webhook_router)
app.include_router(api_admin.router)
app.include_router(preferences_router)

# 挂载静态文件 - 使用 shopee_compliance 目录下的 static 文件夹
static_dir = os.path.join(current_dir, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
# 指南静态聚合页（data.json + index.html），html=True 支持目录默认 index.html
guide_dir = os.path.join(current_dir, "static/guide")
app.mount("/guide", StaticFiles(directory=guide_dir, html=True), name="guide")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
