from pydantic import BaseModel, Field


class ActionPayload(BaseModel):
    bid_level: int = Field(..., ge=1, le=10, description="LOB level for Buy order (1=most aggressive, 10=most passive)")
    ask_level: int = Field(..., ge=1, le=10, description="LOB level for Sell order (1=most aggressive, 10=most passive)")
    size: float = Field(..., ge=0, le=100, description="Volume to transact (0.0 = pull liquidity this tick, max 100).")


class TickRequest(BaseModel):
    team_id: str
    api_key: str
    action: ActionPayload | None = None


class TickMarketData(BaseModel):
    tick: int
    b_p: list[float]   
    b_v: list[float]   
    a_p: list[float]   
    a_v: list[float]   
    trade_flow: float  
    volatility: float


class TickResponse(BaseModel):
    tick: int
    market_data: TickMarketData
    cash: float
    inventory: float
    penalty_this_tick: float
    buy_filled: bool
    sell_filled: bool
    ticks_remaining: int


class SessionSummary(BaseModel):
    total_ticks: int
    final_cash: float
    net_profit: float
    total_penalty: float
    total_buy_fills: int
    total_sell_fills: int


class ResetResponse(BaseModel):
    message: str
    session_id: str


class EvalCompleteResponse(BaseModel):
    message: str
    summary: SessionSummary