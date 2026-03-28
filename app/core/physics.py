from dataclasses import dataclass
from app.core.config import settings

@dataclass
class TickResult:
    buy_filled: bool
    sell_filled: bool
    inventory_delta: float
    cash_delta: float
    penalty: float
    net_cash_delta: float
    new_bid_queue_pos: float
    new_ask_queue_pos: float

def process_tick(
    action_bid_level: int,
    action_ask_level: int,
    size: float,
    current_inventory: float,
    market_data: dict,
    prev_bid_queue_pos: float,
    prev_ask_queue_pos: float,
) -> TickResult:

    b_p, b_v = market_data["b_p"], market_data["b_v"]
    a_p, a_v = market_data["a_p"], market_data["a_v"]
    trade_flow = market_data["trade_flow"]
    volatility = market_data["volatility"]

    buy_filled = False
    sell_filled = False
    cash_delta = 0.0
    inventory_delta = 0.0

    # Trade flow is split evenly between hitting bids and lifting asks.
    flow_per_side = trade_flow / 2.0

    bid_exec_price = b_p[action_bid_level - 1]
    ask_exec_price = a_p[action_ask_level - 1]
    
    if prev_bid_queue_pos > 0 and size > 0 and flow_per_side >= (prev_bid_queue_pos + size):
        buy_filled = True
        inventory_delta += size
        cash_delta -= bid_exec_price * size

    if prev_ask_queue_pos > 0 and size > 0 and flow_per_side >= (prev_ask_queue_pos + size):
        sell_filled = True
        inventory_delta -= size
        cash_delta += ask_exec_price * size

    new_inventory = current_inventory + inventory_delta
    penalty = settings.inventory_penalty_gamma * (new_inventory ** 2) * volatility

    if size > 0:
        new_bid_queue_pos = b_v[action_bid_level - 1]
        new_ask_queue_pos = a_v[action_ask_level - 1]
    else:
        new_bid_queue_pos = 0.0
        new_ask_queue_pos = 0.0

    return TickResult(
        buy_filled=buy_filled,
        sell_filled=sell_filled,
        inventory_delta=inventory_delta,
        cash_delta=cash_delta,
        penalty=penalty,
        net_cash_delta=cash_delta - penalty,
        new_bid_queue_pos=new_bid_queue_pos,
        new_ask_queue_pos=new_ask_queue_pos,
    )