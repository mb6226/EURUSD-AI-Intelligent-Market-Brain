"""Shared, dependency-free OHLCV CSV ingestion for every EURUSD-AI module."""
from __future__ import annotations
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Sequence

@dataclass(frozen=True)
class Candle:
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def __post_init__(self):
        if self.high < max(self.open, self.close, self.low):
            raise ValueError(f'Invalid high at {self.time}')
        if self.low > min(self.open, self.close, self.high):
            raise ValueError(f'Invalid low at {self.time}')

def _timestamp_to_utc(value: str) -> str:
    number = float(value)
    seconds = number / 1000.0 if abs(number) >= 100_000_000_000 else number
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()

def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def iter_ohlcv_csv(path: str | Path) -> Iterator[Candle]:
    """Stream normalized time CSV or Dukascopy timestamp CSV without retaining rows."""
    p = Path(path)
    with p.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fields = {x.strip().lower() for x in (reader.fieldnames or [])}
        required = {'open', 'high', 'low', 'close'}
        missing = required - fields
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")
        if 'time' not in fields and 'timestamp' not in fields:
            raise ValueError('CSV must contain either time or Dukascopy timestamp')
        count = 0
        for raw in reader:
            row = {str(k).strip().lower(): (v or '').strip() for k, v in raw.items() if k is not None}
            time_value = row.get('time') or _timestamp_to_utc(row['timestamp'])
            count += 1
            yield Candle(time_value, *(float(row[k]) for k in ('open', 'high', 'low', 'close')), float(row.get('volume') or 0.0))
        if count == 0:
            raise ValueError('CSV contains no candle rows')

def load_ohlcv_csv(path: str | Path) -> list[Candle]:
    """Compatibility loader. Use iter_ohlcv_csv for large files."""
    return list(iter_ohlcv_csv(path))

def collect_intrabar_extremes(
    higher_candles: Sequence[Candle],
    lower_path: str | Path,
    higher_seconds: int = 3600,
    lower_seconds: int = 60,
    tolerance: float = 1e-9,
) -> tuple[list[list[tuple[str, str, float]] | None], dict[str, int]]:
    """Stream lower-TF data and retain only each higher bar's timed high/low.

    A group is None if lower-TF coverage or its aggregated extremes do not match
    the higher candle. Events are (kind, lower-bar-open-time, price), ordered later.
    """
    if higher_seconds <= 0 or lower_seconds <= 0 or higher_seconds % lower_seconds:
        raise ValueError("higher_seconds must be a positive multiple of lower_seconds")
    lower_iter = iter(iter_ohlcv_csv(lower_path))
    pending = next(lower_iter, None)
    groups: list[list[tuple[str, str, float]] | None] = []
    stats = {"matched_bars": 0, "unmatched_bars": 0, "lower_rows": 0}
    for higher in higher_candles:
        start = _parse_time(higher.time)
        end = start + timedelta(seconds=higher_seconds)
        max_high = None
        min_low = None
        high_time = low_time = None
        rows = 0
        while pending is not None and _parse_time(pending.time) < end:
            lower_time = _parse_time(pending.time)
            if lower_time >= start:
                rows += 1
                stats["lower_rows"] += 1
                if max_high is None or pending.high > max_high:
                    max_high, high_time = pending.high, pending.time
                if min_low is None or pending.low < min_low:
                    min_low, low_time = pending.low, pending.time
            pending = next(lower_iter, None)
        expected_rows = higher_seconds // lower_seconds
        if (rows == expected_rows and max_high is not None and min_low is not None
                and abs(max_high - higher.high) <= tolerance
                and abs(min_low - higher.low) <= tolerance):
            events = [("H", high_time, max_high), ("L", low_time, min_low)]
            events.sort(key=lambda item: item[1])
            groups.append(events)
            stats["matched_bars"] += 1
        else:
            groups.append(None)
            stats["unmatched_bars"] += 1
    return groups, stats
