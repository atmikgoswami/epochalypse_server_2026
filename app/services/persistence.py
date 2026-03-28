from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.orm import EvalCheckpoint, EvalResult


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def upsert_checkpoint(db: AsyncSession, team_id: str, state: dict):
    stmt = (
        insert(EvalCheckpoint)
        .values(
            team_id=team_id,
            last_tick=state["current_tick"],
            cash=state["cash"],
            inventory=state["inventory"],
            total_penalty=state["total_penalty"],
            total_buy_volume=state["total_buy_volume"],
            total_sell_volume=state["total_sell_volume"],
            bid_queue_pos=state["bid_queue_pos"],
            ask_queue_pos=state["ask_queue_pos"],
        )
        .on_conflict_do_update(
            index_elements=["team_id"],
            set_={
                "last_tick": state["current_tick"],
                "cash": state["cash"],
                "inventory": state["inventory"],
                "total_penalty": state["total_penalty"],
                "total_buy_volume": state["total_buy_volume"],
                "total_sell_volume": state["total_sell_volume"],
                "bid_queue_pos": state["bid_queue_pos"],
                "ask_queue_pos": state["ask_queue_pos"],
                "updated_at": _now(),
            },
        )
    )
    await db.execute(stmt)
    await db.commit()


async def load_checkpoint(db: AsyncSession, team_id: str) -> EvalCheckpoint | None:
    result = await db.execute(
        select(EvalCheckpoint).where(EvalCheckpoint.team_id == team_id)
    )
    return result.scalar_one_or_none()


async def save_final_result(db: AsyncSession, team_id: str, state: dict, total_ticks: int):
    now = _now()
    stmt = (
        insert(EvalResult)
        .values(
            team_id=team_id,
            final_cash=state["cash"],
            total_penalty=state["total_penalty"],
            total_buy_volume=state["total_buy_volume"],
            total_sell_volume=state["total_sell_volume"],
            ticks_completed=total_ticks,
            completed=True,
            completed_at=now,
        )
        .on_conflict_do_update(
            index_elements=["team_id"],
            set_={
                "final_cash": state["cash"],
                "total_penalty": state["total_penalty"],
                "total_buy_volume": state["total_buy_volume"],
                "total_sell_volume": state["total_sell_volume"],
                "ticks_completed": total_ticks,
                "completed": True,
                "completed_at": now,
                "updated_at": now,
            },
        )
    )
    await db.execute(stmt)
    await db.commit()


async def is_eval_complete(db: AsyncSession, team_id: str) -> bool:
    result = await db.execute(
        select(EvalResult.completed).where(
            EvalResult.team_id == team_id, EvalResult.completed == True
        )
    )
    return result.scalar_one_or_none() is not None


def should_checkpoint(tick: int) -> bool:
    return tick > 0 and tick % settings.eval_checkpoint_interval == 0