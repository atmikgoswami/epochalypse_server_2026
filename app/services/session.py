import json
import uuid
from enum import StrEnum

from redis.asyncio import Redis

from app.core.config import settings

LOCAL_SESSION_TTL = 60 * 60 * 12   # 12 hours
EVAL_ATTEMPTED_TTL = 60 * 60 * 24 * 30  # 30 days


class SessionMode(StrEnum):
    LOCAL = "local"
    EVAL = "eval"


def _local_key(team_id: str) -> str:
    return f"session:local:{team_id}"


def _eval_key(team_id: str) -> str:
    return f"session:eval:{team_id}"


def _initial_state(mode: SessionMode) -> dict:
    return {
        "session_id": str(uuid.uuid4()),
        "mode": mode,
        "current_tick": 0,
        "cash": settings.initial_cash,
        "inventory": 0.0,
        "total_penalty": 0.0,
        "total_buy_fills": 0,
        "total_sell_fills": 0,
        "bid_queue_pos": 0.0,
        "ask_queue_pos": 0.0,
    }


# Local session helpers
async def get_local_session(redis: Redis, team_id: str) -> dict | None:
    raw = await redis.get(_local_key(team_id))
    return json.loads(raw) if raw else None


async def create_local_session(redis: Redis, team_id: str) -> dict:
    state = _initial_state(SessionMode.LOCAL)
    await redis.set(_local_key(team_id), json.dumps(state), ex=LOCAL_SESSION_TTL)
    return state


async def save_local_session(redis: Redis, team_id: str, state: dict):
    await redis.set(_local_key(team_id), json.dumps(state), ex=LOCAL_SESSION_TTL)


async def delete_local_session(redis: Redis, team_id: str):
    await redis.delete(_local_key(team_id))


# Eval session helpers
async def get_eval_session(redis: Redis, team_id: str) -> dict | None:
    raw = await redis.get(_eval_key(team_id))
    return json.loads(raw) if raw else None


async def create_eval_session(redis: Redis, team_id: str) -> dict:
    state = _initial_state(SessionMode.EVAL)
    await redis.set(_eval_key(team_id), json.dumps(state))
    return state


async def save_eval_session(redis: Redis, team_id: str, state: dict):
    await redis.set(_eval_key(team_id), json.dumps(state))


async def delete_eval_session(redis: Redis, team_id: str):
    await redis.delete(_eval_key(team_id))


async def eval_attempt_exists(redis: Redis, team_id: str) -> bool:
    return bool(await redis.exists(f"eval:attempted:{team_id}"))


async def mark_eval_attempted(redis: Redis, team_id: str):
    await redis.set(f"eval:attempted:{team_id}", "1", ex=EVAL_ATTEMPTED_TTL)