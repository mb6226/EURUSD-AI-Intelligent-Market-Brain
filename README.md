# EURUSD Elliott Intelligence

A single research system for EURUSD Elliott Wave structure analysis, historical measurement, multi-timeframe reasoning, expert-reviewed learning, and leakage-safe evaluation.

## Canonical data

The project expects the user's local data directory to contain the validated EURUSD BID history in UTC:

- M1 source: `data/full-history/eurusd-m1-bid-2003-05-04-2026-11-20.csv`
- Resampled M5, M15, H1, H4, D1, W1 and MN1 files: `data/timeframes/`
- Canonical paths are defined only in `src/eurusd_ai/data_catalog.py`.

The market-data files are intentionally not committed to GitHub. Git tracks only `data/.gitkeep`; local price data stays on the user's machine. The data catalog fails clearly when a required file is absent. It must never silently substitute a shorter or stale dataset.

## Current capabilities

The existing research baseline includes:
- confirmed directional-change pivots with separate extreme time and confirmation time;
- impulse and ABC candidate generation with explicit hard-rule checks;
- transparent heuristic rankings and competing hypotheses;
- alternative causal ATR-reversal pivots and raw wave-length / retracement measurements;
- chart review, human-label dataset preparation, research-reference collection and OCR extraction workflows;
- multi-timeframe reasoning, walk-forward evaluation, parameter diagnostics and daily forecast pipeline components.

These capabilities are at different maturity levels. A script existing in the repository does not mean its output is validated. Read `docs/PROJECT_CONTRACT.md` and `Modules/Elliott_Waves/README.md` before interpreting results.

## Install (Windows PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -e ".[dev,ml]"
```

## First checks

```powershell
py -3 -m pytest -q
py -3 scripts\run_elliott_stage1.py
```

Stage-1 reports are research diagnostics, not trading signals. Scores are heuristic rankings, not calibrated probabilities. Do not use an AI-generated count as its own training truth.

## Development rules

1. One integrated codebase and one canonical data catalog; avoid duplicate data loaders and disconnected scripts.
2. Preserve the full 2003–2026 local dataset. Never delete or overwrite `data/` during code updates.
3. A pivot is usable only from its confirmation time onward. Extreme time and knowledge time are distinct.
4. If OHLC data cannot establish whether a high or low happened first inside the same candle, record ambiguity or resolve it with finer data; never guess.
5. Keep multiple plausible counts and explicit invalidation conditions.
6. Measure observed wave retracements and extensions from actual price legs. Do not force fixed Fibonacci ratios as labels.
7. Train only on independently reviewed labels; separate training, validation and untouched chronological test periods.
8. Publish no accuracy, probability or profitability claim without a reproducible out-of-sample test.

## Documentation

- `docs/PROJECT_CONTRACT.md` — data, causality, Elliott and evaluation invariants.
- `docs/IMPLEMENTATION_ROADMAP.md` — ordered build plan and acceptance gates.
- `Modules/Elliott_Waves/README.md` — detailed module capabilities and known limitations.
