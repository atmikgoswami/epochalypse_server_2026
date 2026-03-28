from dataclasses import dataclass
from app.core.config import settings

@dataclass
class TickResult:
    buy_filled_amount: float
    sell_filled_amount: float
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

    buy_filled_amount = 0.0
    sell_filled_amount = 0.0
    cash_delta = 0.0
    inventory_delta = 0.0

    flow_per_side = trade_flow / 2.0

    bid_exec_price = b_p[action_bid_level - 1]
    ask_exec_price = a_p[action_ask_level - 1]

    if size > 0:
        # Partial fill logic for Bids
        available_bid_flow = max(0.0, flow_per_side - prev_bid_queue_pos)
        if available_bid_flow > 0:
            buy_filled_amount = min(size, available_bid_flow)
            inventory_delta += buy_filled_amount
            cash_delta -= bid_exec_price * buy_filled_amount

        # Partial fill logic for Asks
        available_ask_flow = max(0.0, flow_per_side - prev_ask_queue_pos)
        if available_ask_flow > 0:
            sell_filled_amount = min(size, available_ask_flow)
            inventory_delta -= sell_filled_amount
            cash_delta += ask_exec_price * sell_filled_amount

    new_inventory = current_inventory + inventory_delta
    penalty = settings.inventory_penalty_gamma * (new_inventory ** 2) * volatility

    if size > 0:
        # Sums all volume from Level 1 up to the Agent's chosen level
        new_bid_queue_pos = sum(b_v[:action_bid_level])
        new_ask_queue_pos = sum(a_v[:action_ask_level])
    else:
        new_bid_queue_pos = 0.0
        new_ask_queue_pos = 0.0

    return TickResult(
        buy_filled_amount=buy_filled_amount,
        sell_filled_amount=sell_filled_amount,
        inventory_delta=inventory_delta,
        cash_delta=cash_delta,
        penalty=penalty,
        net_cash_delta=cash_delta - penalty,
        new_bid_queue_pos=new_bid_queue_pos,
        new_ask_queue_pos=new_ask_queue_pos,
    )