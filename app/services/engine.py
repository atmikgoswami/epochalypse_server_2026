from app.core.market_data import MarketDataStore
from app.core.physics import process_tick
from app.models.schemas import ActionPayload, TickMarketData, TickResponse


def apply_action_to_state(
    state: dict,
    action: ActionPayload,
    market: MarketDataStore,
    tick_index: int,
    mode: str,
) -> tuple[dict, TickResponse | None]:

    if mode == "local":
        tick_data = market.local_tick(tick_index)
        total_ticks = market.local_len()
    else:
        tick_data = market.eval_tick(tick_index)
        total_ticks = market.eval_len()

    result = process_tick(
        action_bid_level=action.bid_level,
        action_ask_level=action.ask_level,
        size=action.size,
        current_inventory=state["inventory"],
        market_data=tick_data,
        prev_bid_queue_pos=state.get("bid_queue_pos", 0.0),
        prev_ask_queue_pos=state.get("ask_queue_pos", 0.0),
    )

    # Update state
    state["cash"] += result.net_cash_delta
    state["inventory"] += result.inventory_delta
    state["total_penalty"] += result.penalty
    state["total_buy_fills"] += int(result.buy_filled)
    state["total_sell_fills"] += int(result.sell_filled)
    state["bid_queue_pos"] = result.new_bid_queue_pos
    state["ask_queue_pos"] = result.new_ask_queue_pos
    state["current_tick"] = tick_index + 1

    next_tick_index = state["current_tick"]
    is_last = next_tick_index >= total_ticks

    if is_last:
        return state, None

    next_market = (
        market.local_tick(next_tick_index)
        if mode == "local"
        else market.eval_tick(next_tick_index)
    )

    market_payload = TickMarketData(
        tick=next_market["tick"],
        b_p=next_market["b_p"],
        b_v=next_market["b_v"],
        a_p=next_market["a_p"],
        a_v=next_market["a_v"],
        trade_flow=next_market["trade_flow"],
        volatility=next_market["volatility"],
    )

    response = TickResponse(
        tick=tick_index,
        market_data=market_payload,
        cash=state["cash"],
        inventory=state["inventory"],
        penalty_this_tick=result.penalty,
        buy_filled=result.buy_filled,
        sell_filled=result.sell_filled,
        ticks_remaining=max(0, total_ticks - state["current_tick"]),
    )

    return state, response


def get_initial_tick_data(market: MarketDataStore, mode: str) -> TickMarketData:
    d = market.local_tick(0) if mode == "local" else market.eval_tick(0)
    return TickMarketData(
        tick=d["tick"],
        b_p=d["b_p"],
        b_v=d["b_v"],
        a_p=d["a_p"],
        a_v=d["a_v"],
        trade_flow=d["trade_flow"],
        volatility=d["volatility"],
    )