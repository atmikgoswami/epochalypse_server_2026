from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.market_data import market_data
from app.db.postgres import get_db
from app.db.redis_client import get_redis
from app.models.schemas import (
    EvalCompleteResponse,
    ResetResponse,
    SessionSummary,
    TickMarketData,
    TickRequest,
    TickResponse,
)
from app.services.auth import authenticate_team
from app.services.engine import apply_action_to_state, get_initial_tick_data
from app.services.session import (
    create_local_session,
    delete_local_session,
    get_local_session,
    save_local_session,
)

router = APIRouter(prefix="/local", tags=["local"])


async def _resolve_team(team_id: str, api_key: str, db: AsyncSession):
    team = await authenticate_team(db, team_id, api_key)
    if not team:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return team


def _current_tick_response(state: dict, current_tick: int, total_ticks: int) -> TickResponse:
    tick_data = market_data.local_tick(current_tick)
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


@router.post("/tick", response_model=TickResponse | EvalCompleteResponse)
async def local_tick(
    body: TickRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    await _resolve_team(body.team_id, body.api_key, db)

    state = await get_local_session(redis, body.team_id)
    total_ticks = market_data.local_len()

    if state is None:
        state = await create_local_session(redis, body.team_id)
        return TickResponse(
            tick=-1,
            market_data=get_initial_tick_data(market_data, "local"),
            cash=state["cash"],
            inventory=state["inventory"],
            penalty_this_tick=0.0,
            buy_filled_amount=0.0,
            sell_filled_amount=0.0,
            ticks_remaining=total_ticks,
        )

    current_tick = state["current_tick"]

    if current_tick >= total_ticks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session complete. Call /local/reset to start over.",
        )

    if body.action is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Action required. To resume after a disconnect, call /local/resume first.",
        )

    state, response = apply_action_to_state(state, body.action, market_data, current_tick, "local")

    if state["current_tick"] >= total_ticks:
        summary = SessionSummary(
            total_ticks=total_ticks,
            final_cash=state["cash"],
            net_profit=state["cash"] - settings.initial_cash,
            total_penalty=state["total_penalty"],
            total_buy_volume=state["total_buy_volume"],
            total_sell_volume=state["total_sell_volume"],
        )
        await delete_local_session(redis, body.team_id)
        return EvalCompleteResponse(message="Local simulation complete.", summary=summary)

    await save_local_session(redis, body.team_id, state)
    return response  


@router.post("/resume", response_model=TickResponse)
async def local_resume(
    body: TickRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    await _resolve_team(body.team_id, body.api_key, db)

    state = await get_local_session(redis, body.team_id)
    total_ticks = market_data.local_len()

    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session found. Call /local/tick with no action to start a new one.",
        )

    current_tick = state["current_tick"]

    if current_tick >= total_ticks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session complete. Call /local/reset to start over.",
        )

    return _current_tick_response(state, current_tick, total_ticks)


@router.post("/reset", response_model=ResetResponse)
async def local_reset(
    body: TickRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    await _resolve_team(body.team_id, body.api_key, db)
    state = await create_local_session(redis, body.team_id)
    return ResetResponse(message="Local session reset.", session_id=state["session_id"])