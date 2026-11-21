from pathlib import Path

from eurusd_ai.data_catalog import EURUSD_M1_BID_UTC, EURUSD_TIMEFRAMES, PROJECT_ROOT, require_dataset


def test_full_history_catalog_has_all_expected_timeframes():
    assert set(EURUSD_TIMEFRAMES) == {"M1", "M5", "M15", "H1", "H4", "D1", "W1", "MN1"}
    assert EURUSD_TIMEFRAMES["M1"] == EURUSD_M1_BID_UTC
    assert EURUSD_M1_BID_UTC == (
        PROJECT_ROOT / "data" / "full-history"
        / "eurusd-m1-bid-2003-05-04-2026-11-20.csv"
    )


def test_derived_timeframe_files_live_under_canonical_timeframes_directory():
    for timeframe, path in EURUSD_TIMEFRAMES.items():
        if timeframe != "M1":
            assert path.parent == PROJECT_ROOT / "data" / "timeframes"
            assert path.suffix == ".csv"


def test_require_dataset_resolves_absolute_and_project_relative_paths(tmp_path):
    data_file = tmp_path / "sample.csv"
    data_file.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    assert require_dataset(data_file) == data_file
    assert require_dataset(str(data_file)) == data_file
