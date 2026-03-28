from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.postgres import Base

class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class EvalResult(Base):
    __tablename__ = "eval_results"

    team_id: Mapped[str] = mapped_column(String, primary_key=True)
    final_cash: Mapped[float] = mapped_column(Float, nullable=False)
    total_penalty: Mapped[float] = mapped_column(Float, nullable=False)
    total_buy_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_sell_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ticks_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

class EvalCheckpoint(Base):
    __tablename__ = "eval_checkpoints"

    team_id: Mapped[str] = mapped_column(String, primary_key=True)
    last_tick: Mapped[int] = mapped_column(Integer, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    inventory: Mapped[float] = mapped_column(Float, nullable=False)
    total_penalty: Mapped[float] = mapped_column(Float, nullable=False)
    total_buy_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_sell_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bid_queue_pos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ask_queue_pos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )