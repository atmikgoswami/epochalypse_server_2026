from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.market_data import market_data
from app.db.postgres import get_db
from app.db.redis_client import get_redis
from app.models.schemas import (
    EvalCompleteResponse,
    SessionSummary,
    TickMarketData,
    TickRequest,
    TickResponse,
)
from app.services.auth import authenticate_team
from app.services.engine import apply_action_to_state, get_initial_tick_data
from app.services.persistence import (
    is_eval_complete,
    load_checkpoint,
    save_final_result,
    should_checkpoint,
    upsert_checkpoint,
)
from app.services.session import (
    create_eval_session,
    delete_eval_session,
    eval_attempt_exists,
    get_eval_session,
    mark_eval_attempted,
    save_eval_session,
)

router = APIRouter(prefix="/eval", tags=["eval"])


async def _resolve_team(team_id: str, api_key: str, db: AsyncSession):
    team = await authenticate_team(db, team_id, api_key)
    if not team:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return team


async def _restore_from_checkpoint(redis, db: AsyncSession, team_id: str) -> dict:
    """Rebuild an in-memory eval session from the latest Postgres checkpoint."""
    checkpoint = await load_checkpoint(db, team_id)
    if checkpoint is None:
        # Attempted but never hit a checkpoint interval yet: restart from tick 0.
        state = await create_eval_session(redis, team_id)
    else:
        state = {
            "session_id": "restored",
            "mode": "eval",
            "current_tick": checkpoint.last_tick,
            "cash": checkpoint.cash,
            "inventory": checkpoint.inventory,
            "total_penalty": checkpoint.total_penalty,
            "total_buy_volume": checkpoint.total_buy_volume,
            "total_sell_volume": checkpoint.total_sell_volume,
            "bid_queue_pos": checkpoint.bid_queue_pos,
            "ask_queue_pos": checkpoint.ask_queue_pos,
        }
        await save_eval_session(redis, team_id, state)
    return state


def _current_tick_response(state: dict, current_tick: int, total_ticks: int) -> TickResponse:
    tick_data = market_data.eval_tick(current_tick)
    return TickResponse(
        tick=current_tick - 1,
        market_data=TickMarketData(
            tick=tick_data["tick"],
            b_p=tick_data["b_p"],
            b_v=tick_data["b_v"],
            a_p=tick_data["a_p"],
            a_v=tick_data["a_v"],
            trade_flow=tick_data["trade_flow"],
            volatility=tick_data["volatility"],
        ),
        cash=state["cash"],
        inventory=state["inventory"],
        penalty_this_tick=0.0,
        buy_filled_amount=0.0,
        sell_filled_amount=0.0,
        ticks_remaining=total_ticks - current_tick,
    )


def _deadline_check():
    deadline = datetime.fromisoformat(settings.eval_deadline)
    
    # If the deadline in the .env file lacks a timezone, assign UTC to it
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
        
    # Compare it against the current timezone-aware UTC time
    if datetime.now(timezone.utc) > deadline:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The evaluation window has closed. No further submissions are accepted.",
        )


async def _resolve_eval_state(redis, db: AsyncSession, team_id: str) -> dict | None:
    """

    Priority order:
      1. Redis live session  
      2. Postgres checkpoint 
      3. None               

    """
    # still in Redis
    state = await get_eval_session(redis, team_id)
    if state is not None:
        return state

    # Redis key gone. Check Postgres 
    checkpoint = await load_checkpoint(db, team_id)
    if checkpoint is not None:
        await mark_eval_attempted(redis, team_id)
        return await _restore_from_checkpoint(redis, db, team_id)

    if await eval_attempt_exists(redis, team_id):
        return await _restore_from_checkpoint(redis, db, team_id)

    # Genuinely new team
    return None


@router.post("/tick", response_model=TickResponse | EvalCompleteResponse)
async def eval_tick(
    body: TickRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    _deadline_check()
    await _resolve_team(body.team_id, body.api_key, db)

    if await is_eval_complete(db, body.team_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation already completed. No further attempts permitted.",
        )

    total_ticks = market_data.eval_len()
    state = await _resolve_eval_state(redis, db, body.team_id)

    if state is None:
        await mark_eval_attempted(redis, body.team_id)
        state = await create_eval_session(redis, body.team_id)
        return TickResponse(
            tick=-1,
            market_data=get_initial_tick_data(market_data, "eval"),
            cash=state["cash"],
            inventory=state["inventory"],
            penalty_this_tick=0.0,
            buy_filled_amount=0.0,
            sell_filled_amount=0.0,
            ticks_remaining=total_ticks,
        )

    if body.action is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Action required. To resume after a disconnect, call /eval/resume first.",
        )

    current_tick = state["current_tick"]
    state, response = apply_action_to_state(state, body.action, market_data, current_tick, "eval")

    # Engine returns response=None on the final tick.
    if state["current_tick"] >= total_ticks:
        await save_final_result(db, body.team_id, state, total_ticks)
        await delete_eval_session(redis, body.team_id)
        summary = SessionSummary(
            total_ticks=total_ticks,
            final_cash=state["cash"],
            net_profit=state["cash"] - settings.initial_cash,
            total_penalty=state["total_penalty"],
            total_buy_volume=state["total_buy_volume"],
            total_sell_volume=state["total_sell_volume"],
        )
        return EvalCompleteResponse(message="Evaluation complete. Results recorded.", summary=summary)

    # persist to Redis, checkpoint to Postgres every N ticks.
    await save_eval_session(redis, body.team_id, state)
    if should_checkpoint(state["current_tick"]):
        await upsert_checkpoint(db, body.team_id, state)

    return response 


@router.post("/resume", response_model=TickResponse)
async def eval_resume(
    body: TickRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    _deadline_check()
    await _resolve_team(body.team_id, body.api_key, db)

    if await is_eval_complete(db, body.team_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation already completed. No further attempts permitted.",
        )

    total_ticks = market_data.eval_len()
    state = await _resolve_eval_state(redis, db, body.team_id)

    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No eval session found. Call /eval/tick with no action to start.",
        )

    current_tick = state["current_tick"]
    return _current_tick_response(state, current_tick, total_ticks)