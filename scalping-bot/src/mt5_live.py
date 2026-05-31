"""LIVE execution against MetaTrader 5 / Exness.

This module is for running on a Windows machine or VPS with the MT5 terminal
installed and logged into your Exness account. It CANNOT run in the Linux
backtest sandbox (the MetaTrader5 package needs a live Windows terminal).

Safety: DEMO_ONLY defaults to True. Flip it off deliberately, and only after a
strategy has survived backtest + walk-forward + weeks of demo forward-testing.

Install on the VPS:  pip install MetaTrader5
Docs: https://www.mql5.com/en/docs/integration/python_metatrader5
"""
from __future__ import annotations

DEMO_ONLY = True  # <-- hard safety. Do not change until validated on demo.


def connect(login: int, password: str, server: str):
    import MetaTrader5 as mt5
    if not mt5.initialize(login=login, password=password, server=server):
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
    info = mt5.account_info()
    if DEMO_ONLY and info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        mt5.shutdown()
        raise RuntimeError("Refusing to run: account is LIVE but DEMO_ONLY=True.")
    return mt5


def resolve_symbol(mt5, base: str) -> str:
    """Exness instruments often carry an 'm' suffix (BTCUSDm, XAUUSDm)."""
    for name in (base, base + "m"):
        if mt5.symbol_select(name, True) and mt5.symbol_info(name) is not None:
            return name
    raise ValueError(f"Symbol {base} not found on this account")


def _filling_mode(mt5, info):
    if info.filling_mode & mt5.SYMBOL_FILLING_IOC:
        return mt5.ORDER_FILLING_IOC
    if info.filling_mode & mt5.SYMBOL_FILLING_FOK:
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def lots_for_risk(mt5, symbol: str, sl_points: float, risk_frac: float = 0.01) -> float:
    """Risk-based sizing. Prefer this over fixed lots once live - it caps loss
    per trade to a fraction of equity instead of a fixed (large) size."""
    info = mt5.symbol_info(symbol)
    equity = mt5.account_info().equity
    risk_money = equity * risk_frac
    sl_ticks = sl_points * info.point / info.trade_tick_size
    raw = risk_money / (sl_ticks * info.trade_tick_value)
    step = info.volume_step
    lot = max(info.volume_min, round(raw / step) * step)
    return float(min(lot, info.volume_max))


def open_trade(mt5, symbol: str, side: str, lots: float, sl_points: float, tp_points: float):
    """Market order with attached SL/TP. side = 'buy' | 'sell'."""
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    is_buy = side == "buy"
    price = tick.ask if is_buy else tick.bid
    sign = 1 if is_buy else -1

    # respect broker minimum stop distance
    min_dist = max(info.trade_stops_level, 1) * info.point
    sl_dist = max(sl_points * info.point, min_dist)
    tp_dist = max(tp_points * info.point, min_dist)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lots,
        "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": price - sign * sl_dist,
        "tp": price + sign * tp_dist,
        "deviation": 20,
        "magic": 770001,
        "comment": "zrev-scalp",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": _filling_mode(mt5, info),
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(f"order_send failed: {result.retcode} {result.comment}")
    return result


def move_to_breakeven_and_trail(mt5, symbol: str, be_points: float, trail_points: float):
    """Trade management: lock breakeven once in profit, then trail the stop."""
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    for pos in mt5.positions_get(symbol=symbol) or []:
        is_buy = pos.type == mt5.POSITION_TYPE_BUY
        cur = tick.bid if is_buy else tick.ask
        profit_pts = (cur - pos.price_open) / info.point * (1 if is_buy else -1)
        new_sl = None
        if profit_pts >= be_points:
            new_sl = pos.price_open
        if profit_pts >= trail_points:
            trail = cur - (trail_points * info.point) * (1 if is_buy else -1)
            new_sl = max(new_sl or trail, trail) if is_buy else min(new_sl or trail, trail)
        if new_sl is not None and abs(new_sl - pos.sl) > info.point:
            mt5.order_send({"action": mt5.TRADE_ACTION_SLTP,
                            "position": pos.ticket, "sl": new_sl, "tp": pos.tp})
