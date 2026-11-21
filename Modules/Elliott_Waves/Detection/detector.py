"""Multi-scale, causally confirmed ZigZag pivots for Elliott Wave research."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import Sequence
from eurusd_ai.market_data import Candle

@dataclass(frozen=True)
class Pivot:
    index: int
    time: str
    price: float
    kind: str
    confirmed: bool = True
    confirmation_index: int | None = None
    confirmation_time: str | None = None

def _close_time(value: str, seconds: int) -> str:
    try:
        return (datetime.fromisoformat(value.replace("Z", "+00:00")) + timedelta(seconds=seconds)).isoformat()
    except ValueError:
        return value

def _infer_bar_seconds(candles: Sequence[Candle]) -> int:
    deltas = []
    for left, right in zip(candles, candles[1:]):
        try:
            delta = int((_parse(right.time) - _parse(left.time)).total_seconds())
            if delta > 0:
                deltas.append(delta)
        except ValueError:
            continue
    return int(median(deltas)) if deltas else 0

def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def detect_pivots(
    candles: Sequence[Candle],
    min_leg_pips: float = 5.0,
    pip_size: float = 0.0001,
    include_provisional: bool = False,
    confirmation_delay_seconds: int | None = None,
    intrabar_events: Sequence[list[tuple[str, str, float]] | None] | None = None,
    intrabar_seconds: int = 60,
    ambiguities: list[dict] | None = None,
) -> list[Pivot]:
    """Detect pivots without inventing OHLC intrabar order.

    When timed lower-TF extremes are supplied, their order resolves the parent
    candle. Missing/mismatched lower-TF coverage and same-lower-bar extremes
    create an explicit ambiguity and reset the active segment.
    """
    if min_leg_pips <= 0 or pip_size <= 0 or intrabar_seconds <= 0:
        raise ValueError("thresholds and intrabar duration must be positive")
    if len(candles) < 2:
        return []
    if intrabar_events is not None and len(intrabar_events) != len(candles):
        raise ValueError("intrabar_events length must match candles")
    delay = confirmation_delay_seconds
    if delay is None:
        delay = _infer_bar_seconds(candles)
    if delay < 0:
        raise ValueError("confirmation delay must be non-negative")
    threshold = min_leg_pips * pip_size
    found: list[Pivot] = []
    ambiguity_log = ambiguities if ambiguities is not None else []
    direction = 0
    high_i = low_i = 0
    high = low = candles[0].open if intrabar_events is not None else candles[0].close
    high_time = low_time = candles[0].time
    high_order = low_order = -1
    order = 0

    def reset(i: int, candle: Candle, reason: str):
        nonlocal direction, high_i, low_i, high, low, high_time, low_time, high_order, low_order
        ambiguity_log.append({"index": i, "time": candle.time, "reason": reason})
        direction = 0
        high_i = low_i = i
        high = low = candle.close
        high_time = low_time = _close_time(candle.time, delay)
        high_order = low_order = order

    def process_event(i: int, candle: Candle, kind: str, event_time: str, price: float, event_seconds: int):
        nonlocal direction, high_i, low_i, high, low, high_time, low_time, high_order, low_order, order
        order += 1
        if direction == 0:
            if kind == "H" and price >= high:
                high_i, high, high_time, high_order = i, price, event_time, order
            elif kind == "L" and price <= low:
                low_i, low, low_time, low_order = i, price, event_time, order
            if high - low >= threshold:
                if high_order == low_order:
                    reset(i, candle, "high_and_low_order_unresolved")
                elif high_order < low_order:
                    found.append(Pivot(high_i, high_time, high, "H", True, i, _close_time(event_time, event_seconds)))
                    direction = -1
                    low_i, low, low_time, low_order = i, price, event_time, order
                else:
                    found.append(Pivot(low_i, low_time, low, "L", True, i, _close_time(event_time, event_seconds)))
                    direction = 1
                    high_i, high, high_time, high_order = i, price, event_time, order
        elif direction == 1:
            if kind == "H" and price >= high:
                high_i, high, high_time, high_order = i, price, event_time, order
            elif kind == "L" and high - price >= threshold:
                found.append(Pivot(high_i, high_time, high, "H", True, i, _close_time(event_time, event_seconds)))
                direction = -1
                low_i, low, low_time, low_order = i, price, event_time, order
        else:
            if kind == "L" and price <= low:
                low_i, low, low_time, low_order = i, price, event_time, order
            elif kind == "H" and price - low >= threshold:
                found.append(Pivot(low_i, low_time, low, "L", True, i, _close_time(event_time, event_seconds)))
                direction = 1
                high_i, high, high_time, high_order = i, price, event_time, order

    if intrabar_events is not None:
        first_events = intrabar_events[0]
        if first_events is None:
            reset(0, candles[0], "lower_timeframe_missing_or_extremes_mismatch")
        elif len(first_events) == 2 and first_events[0][1] == first_events[1][1]:
            reset(0, candles[0], "high_and_low_inside_same_lower_timeframe_bar")
        else:
            for kind, event_time, price in first_events:
                process_event(0, candles[0], kind, event_time, price, intrabar_seconds)

    for i, candle in enumerate(candles[1:], 1):
        if intrabar_events is not None:
            events = intrabar_events[i]
            if events is None:
                reset(i, candle, "lower_timeframe_missing_or_extremes_mismatch")
                continue
            if len(events) == 2 and events[0][1] == events[1][1]:
                reset(i, candle, "high_and_low_inside_same_lower_timeframe_bar")
                continue
            for kind, event_time, price in events:
                process_event(i, candle, kind, event_time, price, intrabar_seconds)
            continue

        # OHLC alone cannot order a new extreme against a reversal in the same bar.
        new_high = candle.high > high if direction >= 0 else False
        new_low = candle.low < low if direction <= 0 else False
        if direction == 1 and new_high and high - candle.low >= threshold:
            reset(i, candle, "new_high_and_reversal_low_same_ohlc_bar")
            continue
        if direction == -1 and new_low and candle.high - low >= threshold:
            reset(i, candle, "new_low_and_reversal_high_same_ohlc_bar")
            continue
        if direction == 0:
            if new_high:
                high_i, high, high_time, high_order = i, candle.high, candle.time, order + 1
            if new_low:
                low_i, low, low_time, low_order = i, candle.low, candle.time, order + 2
            if high - low >= threshold:
                if high_i == low_i:
                    reset(i, candle, "high_and_low_order_unresolved")
                elif high_i < low_i:
                    found.append(Pivot(high_i, high_time, high, "H", True, i, _close_time(candle.time, delay)))
                    direction = -1
                    low_i, low, low_time = i, candle.low, candle.time
                else:
                    found.append(Pivot(low_i, low_time, low, "L", True, i, _close_time(candle.time, delay)))
                    direction = 1
                    high_i, high, high_time = i, candle.high, candle.time
        elif direction == 1:
            if candle.high >= high:
                high_i, high, high_time = i, candle.high, candle.time
            if high - candle.low >= threshold:
                found.append(Pivot(high_i, high_time, high, "H", True, i, _close_time(candle.time, delay)))
                direction = -1
                low_i, low, low_time = i, candle.low, candle.time
        else:
            if candle.low <= low:
                low_i, low, low_time = i, candle.low, candle.time
            if candle.high - low >= threshold:
                found.append(Pivot(low_i, low_time, low, "L", True, i, _close_time(candle.time, delay)))
                direction = 1
                high_i, high, high_time = i, candle.high, candle.time

    if include_provisional and direction:
        if direction == 1:
            found.append(Pivot(high_i, high_time, high, "H", False, None, None))
        else:
            found.append(Pivot(low_i, low_time, low, "L", False, None, None))
    return found

def find_five_wave_candidates(pivots: Sequence[Pivot]) -> list[tuple[Pivot, ...]]:
    """Compatibility API: geometrically valid rolling six-pivot impulses."""
    from .engine import ElliottEngine
    return [c.pivots for c in ElliottEngine().analyze_pivots(pivots)
            if c.pattern == "impulse" and c.hard_valid]
