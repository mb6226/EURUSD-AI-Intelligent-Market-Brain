"""Canonical paths for shared EURUSD BID datasets across the full available history."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHARED_DATA_DIR = PROJECT_ROOT / "data"
FULL_HISTORY_DIR = SHARED_DATA_DIR / "full-history"
TIMEFRAMES_DIR = SHARED_DATA_DIR / "timeframes"

# Validated combined M1 history: 2003-05-04 through 2026-11-20 (UTC, BID).
EURUSD_M1_BID_UTC = FULL_HISTORY_DIR / "eurusd-m1-bid-2003-05-04-2026-11-20.csv"

# Resampled from the combined M1 source; partial market-session buckets are retained.
EURUSD_TIMEFRAMES = {
    "M1": EURUSD_M1_BID_UTC,
    "M5": TIMEFRAMES_DIR / "eurusd-5min-bid-2003-05-04-2026-11-20.csv",
    "M15": TIMEFRAMES_DIR / "eurusd-15min-bid-2003-05-04-2026-11-20.csv",
    "H1": TIMEFRAMES_DIR / "eurusd-1h-bid-2003-05-04-2026-11-20.csv",
    "H4": TIMEFRAMES_DIR / "eurusd-4h-bid-2003-05-04-2026-11-20.csv",
    "D1": TIMEFRAMES_DIR / "eurusd-daily-bid-2003-05-04-2026-11-20.csv",
    "W1": TIMEFRAMES_DIR / "eurusd-weekly-bid-2003-05-04-2026-11-20.csv",
    "MN1": TIMEFRAMES_DIR / "eurusd-monthly-bid-2003-05-04-2026-11-20.csv",
}


def require_dataset(path: str | Path = EURUSD_M1_BID_UTC) -> Path:
    """Return an existing dataset path or raise a helpful error."""
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    if not resolved.is_file():
        raise FileNotFoundError(f"Shared dataset not found: {resolved}")
    return resolved
