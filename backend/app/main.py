from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis.asyncio import Redis
from .database import get_db
from .config import settings
from .auth import router as auth_router
from .tasks import router as tasks_router
from .custom_tasks import router as custom_tasks_router

app = FastAPI(title="BERP Recitation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tasks_router)
app.include_router(custom_tasks_router)

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    db_ok = False
    redis_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    
    try:
        r = Redis.from_url(settings.REDIS_URL)
        await r.ping()
        redis_ok = True
    except Exception:
        pass
    
    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "services": {
            "db": db_ok,
            "redis": redis_ok
        }
    }

if __name__ == "__main__":
    import uvicorn
    import sys
    import asyncio
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(app, host="0.0.0.0", port=8000)
