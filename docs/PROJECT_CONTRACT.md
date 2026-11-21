# EURUSD Elliott Intelligence — Project Contract

## Mission
Build one coherent EURUSD-only research system that discovers, measures, compares and evaluates Elliott Wave hypotheses on the user's historical BID OHLCV data. This is a research and decision-support project, not an autonomous trading system.

## Data contract
- Instrument: EURUSD only.
- Source: Dukascopy BID OHLCV, timestamps normalized to UTC.
- Canonical M1 history: 2003-05-04 through 2026-11-20.
- Derived timeframes: M5, M15, H1, H4, D1, W1 and MN1.
- CSV schema: timestamp, open, high, low, close, volume.
- `data/` is local-only except for the tracked empty `.gitkeep`. Never commit the user's large market data.
- Every derived dataset must retain source range, timeframe, resampling rule and validation metadata.
- No fallback to a shorter dataset when a canonical file is missing.

## Causality and candle ambiguity
- Every pivot has an extreme timestamp and a separate confirmation timestamp/index.
- A confirmed pivot may enter a forecast only after its confirmation candle has closed.
- A provisional terminal pivot is explicitly marked provisional and excluded from historical training labels.
- OHLC cannot reveal the order of a candle's high and low. If both extremes could determine pivot order, the engine must mark the sequence ambiguous or resolve it from lower-timeframe data. It must not invent intrabar order.
- Higher-timeframe bars are available only after their complete interval closes.
- All feature joins, labels and forecasts use point-in-time information. No future candle, future pivot confirmation, or future revision may leak into an earlier row.

## Elliott structure contract
- Return multiple competing counts, not a single forced count.
- Separate hard Elliott rule validity from soft morphology, ranking and confidence calibration.
- Support impulse and corrective families incrementally; do not label a pattern solely from one ratio.
- Track wave degree and nesting as explicit hypotheses with parent/child relationships, not as a chart-range heuristic.
- Measure leg sizes, retracements, extensions and durations from observed price data. Ratios are descriptive measurements; no fixed Fibonacci threshold is a ground-truth label.
- Every candidate includes source pivots, confirmation times, rule checks, score components, invalidation level/condition and unresolved ambiguity.

## Learning contract
- Self-generated counts are predictions, never ground truth.
- OCR and scraped research material are unverified evidence until a human confirms the chart and its labels.
- Training labels require provenance, reviewer identity, review timestamp, instrument/timeframe, and explicit uncertainty or abstention.
- Keep train/validation/test splits chronological and grouped to prevent overlapping chart windows leaking across splits.
- A model may rank or calibrate hypotheses only after minimum independent-review and class-coverage gates are met.

## Evaluation contract
- Use expanding or rolling walk-forward evaluation with strict as-of timestamps.
- Tune thresholds only inside training/validation windows; never on the outer test period.
- Report structural metrics separately from directional forecast metrics and trading metrics.
- Include coverage, abstention, calibration, confusion matrices, regime slices and uncertainty intervals where applicable.
- No accuracy, probability or profitability claim without reproducible independent holdout evidence.

## Engineering contract
- One canonical data catalog and one shared candle model.
- Pure, testable analysis functions; CLI and automation call the same library code.
- Deterministic runs with versioned configuration and machine-readable reports.
- Every phase adds tests and documentation; no disconnected duplicate engines.
- Python standard CSV handling is sufficient for data validation; pandas is not a required dependency.
