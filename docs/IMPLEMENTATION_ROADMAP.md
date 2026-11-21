# Implementation Roadmap

This roadmap is ordered by dependency. A later phase cannot be called complete while an earlier acceptance gate fails.

## Phase 0 — Repository and data foundation
- Keep the full-history data catalog as the sole source of dataset paths.
- Preserve local `data/`; keep large data out of Git.
- Add continuous integration and deterministic tests.
- Validate all eight timeframes and their source provenance.

Acceptance: clean install, full test suite green, catalog points to the 2003-2026 files, no hidden shorter-history fallback.

## Phase 1 — Causal market-structure engine
- Audit directional-change and ATR pivot detectors.
- Explicitly handle same-candle high/low ambiguity; use M1 to resolve higher-timeframe ordering only when the M1 evidence is conclusive.
- Store extreme time separately from confirmation time.
- Test prefix invariance and no-lookahead behavior.

Acceptance: every emitted confirmed pivot is causally available; ambiguous sequences are represented, not guessed.

## Phase 2 — Elliott hypothesis engine
- Keep multiple impulse and correction candidates.
- Expand correction taxonomy (zigzag, flat, triangle and combinations) only with explicit rule sets and tests.
- Add diagonal patterns separately from standard impulses.
- Add degree/nesting hypotheses and parent-child constraints.
- Explain candidate scores by named components and explicit invalidation rules.

Acceptance: synthetic positive/negative fixtures for each pattern; hard-rule violations are never hidden by a high score.

## Phase 3 — Multi-timeframe reasoning
- Align M1/M5/M15/H1/H4/D1/W1/MN1 using close-time availability.
- Compare parent and child wave hypotheses across degrees.
- Preserve conflicts and alternative scenarios; abstain when evidence is insufficient.

Acceptance: no incomplete bar is used; every scenario has traceable source evidence and as-of time.

## Phase 4 — Expert-reviewed learning dataset
- Generate reproducible chart packets from historical windows.
- Store reviewer-confirmed labels and uncertainty with provenance.
- Exclude OCR-only and model-generated labels from ground truth.

Acceptance: auditable labels, reviewer agreement gates, no overlapping-window leakage.

## Phase 5 — Learning and calibration
- Train candidate rankers only on reviewed examples.
- Calibrate scores only on a separate chronological validation set.
- Compare against deterministic baselines and retain an abstain option.

Acceptance: documented sample gates, calibration and uncertainty metrics; no unsupported probability claims.

## Phase 6 — Walk-forward forecast evaluation
- Reconstruct what was knowable at each historical cutoff.
- Evaluate next-swing direction, magnitude, timing and scenario coverage.
- Keep all tuning inside each training fold.

Acceptance: reproducible outer-fold results and an untouched final holdout.

## Phase 7 — Daily research forecast
- Run the same validated library against the latest fully closed candles.
- Produce scenarios, invalidation levels, confidence calibration (only if earned), and abstention reasons.
- Keep automation separate from any broker execution.

Acceptance: freshness checks, deterministic report, failure-safe behavior and no stale-data forecast.
