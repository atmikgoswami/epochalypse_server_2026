from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.postgres import get_db
from app.models.orm import EvalResult, Team
from app.services.auth import register_team

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(x_admin_key: str = Header(...)):
    if x_admin_key != settings.secret_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


class RegisterTeamRequest(BaseModel):
    team_id: str
    name: str
    api_key: str


class LeaderboardEntry(BaseModel):
    rank: int
    team_id: str
    final_cash: float
    net_profit: float
    total_penalty: float
    total_buy_fills: int
    total_sell_fills: int
    ticks_completed: int


@router.post("/teams", dependencies=[Depends(_require_admin)])
async def create_team(body: RegisterTeamRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.get(Team, body.team_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Team ID already exists")
    team = await register_team(db, body.team_id, body.name, body.api_key)
    return {"team_id": team.id, "name": team.name}


@router.get("/leaderboard", dependencies=[Depends(_require_admin)])
async def leaderboard(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EvalResult)
        .where(EvalResult.completed == True)
        .order_by(EvalResult.final_cash.desc())
    )
    rows = result.scalars().all()
    return [
        LeaderboardEntry(
            rank=i + 1,
            team_id=r.team_id,
            final_cash=r.final_cash,
            net_profit=r.final_cash - settings.initial_cash,
            total_penalty=r.total_penalty,
            total_buy_fills=r.total_buy_fills,
            total_sell_fills=r.total_sell_fills,
            ticks_completed=r.ticks_completed,
        )
        for i, r in enumerate(rows)
    ]