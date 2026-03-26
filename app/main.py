from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import admin, eval, local
from app.core.market_data import market_data
from app.db.postgres import Base, engine
from app.db.redis_client import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    market_data.load()

    yield

    await close_redis()
    await engine.dispose()


app = FastAPI(title="Epochalypse Master Server", lifespan=lifespan)

app.include_router(local.router)
app.include_router(eval.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}