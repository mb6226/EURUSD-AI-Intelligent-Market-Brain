"""Audit same-H1-bar pivot collisions against the underlying M1 sequence.

This is a diagnostic only: it does not modify the production detector or labels.
It independently mirrors the current detector's raw directional-change loop so
that same-index H/L events removed by the production final filter remain visible.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from eurusd_ai.data_catalog import EURUSD_TIMEFRAMES, require_dataset
from eurusd_ai.market_data import Candle, load_ohlcv_csv
from Modules.Elliott_Waves.Detection.detector import Pivot, _known_at


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _raw_pivots(candles: list[Candle], threshold: float) -> list[Pivot]:
    """Mirror detector.py before its strictly-increasing-index output filter."""
    if len(candles) < 2:
        return []
    raw: list[Pivot] = []
    direction = 0
    high_i, high = 0, candles[0].high
    low_i, low = 0, candles[0].low

    for i, candle in enumerate(candles[1:], 1):
        pivot = None
        if direction == 0:
            if candle.high >= high:
                high_i, high = i, candle.high
            if candle.low <= low:
                low_i, low = i, candle.low
            if high - low >= threshold and high_i != low_i:
                if high_i < low_i:
                    pivot = Pivot(high_i, candles[high_i].time, high, "H", True, i,
                                  _known_at(candle, 0))
                    direction = -1
                    low_i, low = i, candle.low
                else:
                    pivot = Pivot(low_i, candles[low_i].time, low, "L", True, i,
                                  _known_at(candle, 0))
                    direction = 1
                    high_i, high = i, candle.high
        elif direction == 1:
            if candle.high >= high:
                high_i, high = i, candle.high
            if high - candle.low >= threshold:
                pivot = Pivot(high_i, candles[high_i].time, high, "H", True, i,
                              _known_at(candle, 0))
                direction = -1
                low_i, low = i, candle.low
        else:
            if candle.low <= low:
                low_i, low = i, candle.low
            if candle.high - low >= threshold:
                pivot = Pivot(low_i, candles[low_i].time, low, "L", True, i,
                              _known_at(candle, 0))
                direction = 1
                high_i, high = i, candle.high
        if pivot is not None:
            raw.append(pivot)
    return raw


def _m1_time(row: dict[str, str]) -> datetime:
    if row.get("time"):
        return _parse_time(row["time"])
    value = float(row["timestamp"])
    seconds = value / 1000.0 if abs(value) >= 100_000_000_000 else value
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def audit(h1_path: Path, m1_path: Path, threshold_pips: float) -> dict:
    h1 = load_ohlcv_csv(h1_path)
    raw = _raw_pivots(h1, threshold_pips * 0.0001)
    collisions = []
    for left, right in zip(raw, raw[1:]):
        if left.index == right.index:
            collisions.append({
                "h1_index": left.index,
                "h1_time": left.time,
                "left_kind": left.kind,
                "left_price": left.price,
                "left_confirmation_index": left.confirmation_index,
                "right_kind": right.kind,
                "right_price": right.price,
                "right_confirmation_index": right.confirmation_index,
            })

    # One compact record per affected H1 candle; M1 is streamed to avoid loading
    # 8.8M rows into memory.
    targets: dict[datetime, dict] = {}
    for item in collisions:
        start = _parse_time(item["h1_time"])
        state = targets.setdefault(start, {
            "h1_index": item["h1_index"],
            "h1_time": item["h1_time"],
            "high": None,
            "low": None,
        })
        for kind, price in ((item["left_kind"], item["left_price"]),
                            (item["right_kind"], item["right_price"])):
            state[kind.lower()] = price

    tol = 0.00000005
    for start, state in targets.items():
        state["end"] = start + timedelta(hours=1)
        state["first_high_m1"] = None
        state["first_low_m1"] = None
        state["m1_rows"] = 0

    with m1_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            t = _m1_time(row)
            # H1 data are sorted; only inspect rows that fall in a target hour.
            start = t.replace(minute=0, second=0, microsecond=0)
            state = targets.get(start)
            if state is None or not (start <= t < state["end"]):
                continue
            state["m1_rows"] += 1
            high = float(row["high"])
            low = float(row["low"])
            if state["high"] is not None and state["first_high_m1"] is None:
                if abs(high - state["high"]) <= tol:
                    state["first_high_m1"] = t.isoformat()
            if state["low"] is not None and state["first_low_m1"] is None:
                if abs(low - state["low"]) <= tol:
                    state["first_low_m1"] = t.isoformat()

    outcomes = Counter()
    examples = []
    for start, state in sorted(targets.items()):
        hi = state["first_high_m1"]
        lo = state["first_low_m1"]
        if not state["m1_rows"] or hi is None or lo is None:
            outcome = "missing_m1_or_extreme"
        elif hi == lo:
            outcome = "same_m1_bar_ambiguous"
        elif _parse_time(hi) < _parse_time(lo):
            outcome = "high_first"
        else:
            outcome = "low_first"
        outcomes[outcome] += 1
        if len(examples) < 12:
            examples.append({
                "h1_time": state["h1_time"],
                "m1_rows": state["m1_rows"],
                "first_high_m1": hi,
                "first_low_m1": lo,
                "outcome": outcome,
            })

    return {
        "audit": "eurusd_h1_intrabar_pivot_collision_audit_v1",
        "threshold_pips": threshold_pips,
        "h1_candles": len(h1),
        "raw_pivots": len(raw),
        "same_index_collision_pairs": len(collisions),
        "affected_h1_candles": len(targets),
        "m1_outcomes": dict(sorted(outcomes.items())),
        "examples": examples,
        "limitations": [
            "M1 ordering resolves only cases where the H1 high and low first occur in different M1 candles.",
            "If both extremes occur in one M1 candle, their internal order remains unknown.",
            "Missing M1 bars or unmatched extrema remain unresolved; no order is guessed.",
            "This report is diagnostic and does not change production pivots or Elliott labels.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold-pips", type=float, default=5.0)
    parser.add_argument("--output", type=Path,
                        default=Path("reports/intrabar_pivot_collision_audit.json"))
    args = parser.parse_args()
    h1_path = require_dataset(EURUSD_TIMEFRAMES["H1"])
    m1_path = require_dataset(EURUSD_TIMEFRAMES["M1"])
    report = audit(h1_path, m1_path, args.threshold_pips)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("AUDIT:", report["audit"])
    print("H1_CANDLES:", report["h1_candles"])
    print("RAW_PIVOTS:", report["raw_pivots"])
    print("SAME_INDEX_COLLISIONS:", report["same_index_collision_pairs"])
    print("AFFECTED_H1_CANDLES:", report["affected_h1_candles"])
    print("M1_OUTCOMES:", json.dumps(report["m1_outcomes"], sort_keys=True))
    print("REPORT:", args.output)
    print("INTRABAR_AUDIT_COMPLETE")


if __name__ == "__main__":
    main()
