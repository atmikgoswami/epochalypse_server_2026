import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Team

_auth_cache: dict[str, tuple[str, "Team"]] = {}


def hash_api_key(key: str) -> str:
    return bcrypt.hashpw(key.encode()[:72], bcrypt.gensalt()).decode()


def verify_api_key(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode()[:72], hashed.encode())


async def authenticate_team(db: AsyncSession, team_id: str, api_key: str) -> "Team | None":
    if team_id in _auth_cache:
        cached_hash, cached_team = _auth_cache[team_id]
        return cached_team if verify_api_key(api_key, cached_hash) else None

    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if team is None:
        return None
    if not verify_api_key(api_key, team.api_key_hash):
        return None

    _auth_cache[team_id] = (team.api_key_hash, team)
    return team


async def register_team(db: AsyncSession, team_id: str, name: str, api_key: str) -> "Team":
    team = Team(id=team_id, name=name, api_key_hash=hash_api_key(api_key))
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team