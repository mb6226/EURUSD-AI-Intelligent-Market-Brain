"""Independent causal and rule-integrity audit for the full-history EURUSD H1 Elliott engine.

This is a diagnostic audit, not an expert-label accuracy test or trading backtest.
It deliberately keeps rule-engine weak labels separate from Elliott ground truth.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from eurusd_ai.data_catalog import EURUSD_TIMEFRAMES, PROJECT_ROOT, require_dataset
from eurusd_ai.market_data import load_ohlcv_csv
from Modules.Elliott_Waves.Detection.detector import detect_pivots
from Modules.Elliott_Waves.Detection.engine import ElliottEngine

PIP = 0.0001
TF = "H1"
PIVOT_THRESHOLD_PIPS = 5.0
OUTPUT = PROJECT_ROOT / "Modules" / "Elliott_Waves" / "Evaluation" / "h1_quality_audit"


def epoch(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def pivot_signature(p):
    return (p.index, p.time, p.price, p.kind, p.confirmed,
            p.confirmation_index, p.confirmation_time)


def audit_candles(candles):
    times = [epoch(c.time) for c in candles]
    duplicate_times = sum(times[i] == times[i - 1] for i in range(1, len(times)))
    non_monotonic = sum(times[i] <= times[i - 1] for i in range(1, len(times)))
    invalid_ohlc = sum(
        c.high < max(c.open, c.close, c.low) or
        c.low > min(c.open, c.close, c.high)
        for c in candles
    )
    gaps = [
        round((times[i] - times[i - 1]) / 3600, 3)
        for i in range(1, len(times))
        if times[i] - times[i - 1] > 3600
    ]
    return {
        "candles": len(candles),
        "first_candle_utc": candles[0].time,
        "last_candle_utc": candles[-1].time,
        "duplicate_timestamps": duplicate_times,
        "non_monotonic_timestamps": non_monotonic,
        "invalid_ohlc_rows": invalid_ohlc,
        "gaps_over_one_hour": len(gaps),
        "largest_gap_hours": max(gaps) if gaps else 0,
    }


def audit_prefix_invariance(candles, full_pivots):
    """A pivot confirmed by cutoff must be identical when only that prefix is supplied."""
    checks = []
    for fraction in (0.25, 0.50, 0.75):
        cutoff = max(1, int(len(candles) * fraction) - 1)
        prefix = candles[:cutoff + 1]
        expected = [p for p in full_pivots
                    if p.confirmation_index is not None and p.confirmation_index <= cutoff]
        actual = detect_pivots(
            prefix, min_leg_pips=PIVOT_THRESHOLD_PIPS,
            include_provisional=False,
        )
        expected_sig = [pivot_signature(p) for p in expected]
        actual_sig = [pivot_signature(p) for p in actual]
        checks.append({
            "cutoff_fraction": fraction,
            "cutoff_index": cutoff,
            "expected_confirmed_pivots": len(expected),
            "prefix_detected_pivots": len(actual),
            "exact_match": expected_sig == actual_sig,
        })
    return checks


def audit_pivots(pivots, candles):
    candle_count = len(candles)
    bad_index = sum(p.index < 0 or p.index >= candle_count for p in pivots)
    bad_confirmation = sum(
        p.confirmation_index is None or
        p.confirmation_index < p.index or
        p.confirmation_index >= candle_count or
        not p.confirmation_time
        for p in pivots
    )
    non_alternating = sum(
        pivots[i].kind == pivots[i - 1].kind
        for i in range(1, len(pivots))
    )
    non_increasing_extremes = sum(
        pivots[i].index <= pivots[i - 1].index
        for i in range(1, len(pivots))
    )
    confirmation_order_errors = sum(
        pivots[i].confirmation_index <= pivots[i - 1].confirmation_index
        for i in range(1, len(pivots))
        if pivots[i].confirmation_index is not None
        and pivots[i - 1].confirmation_index is not None
    )
    extreme_time_mismatches = sum(
        p.time != candles[p.index].time
        for p in pivots if 0 <= p.index < candle_count
    )
    confirmation_time_mismatches = sum(
        p.confirmation_time != candles[p.confirmation_index].time
        for p in pivots
        if p.confirmation_index is not None and 0 <= p.confirmation_index < candle_count
    )
    return {
        "pivot_count": len(pivots),
        "bad_extreme_indices": bad_index,
        "bad_confirmation_metadata": bad_confirmation,
        "non_alternating_pivots": non_alternating,
        "non_increasing_extreme_indices": non_increasing_extremes,
        "confirmation_order_errors": confirmation_order_errors,
        "extreme_time_mismatches": extreme_time_mismatches,
        "confirmation_time_mismatches": confirmation_time_mismatches,
        "provisional_pivots": sum(not p.confirmed for p in pivots),
    }


def audit_candidates(candidates):
    counts = Counter(c.pattern for c in candidates)
    hard_valid = Counter(c.pattern for c in candidates if c.hard_valid)
    impulse_rule_errors = 0
    correction_soft_warnings = 0
    correction_hard_valid = 0
    availability_errors = 0
    pivot_order_errors = 0
    impulse_count = 0

    for c in candidates:
        ps = c.pivots
        if any(ps[i].index >= ps[i + 1].index for i in range(len(ps) - 1)):
            pivot_order_errors += 1
        if any(not p.confirmed or not p.confirmation_time for p in ps):
            availability_errors += 1

        if c.pattern == "impulse":
            impulse_count += 1
            d = [ps[i + 1].price - ps[i].price for i in range(5)]
            direction = 1 if d[0] > 0 else -1
            w1, w2, w3, _, w5 = map(abs, d)
            eps = PIP * 0.05
            up = direction > 0
            wave2_invalid = ((ps[2].price - ps[0].price) * direction <= 0
                             or w2 >= w1 - eps)
            wave3_invalid = ((ps[3].price - ps[1].price) * direction <= 0
                             or w3 + eps < min(w1, w5))
            overlap = ((ps[4].price <= ps[1].price + eps) if up
                       else (ps[4].price >= ps[1].price - eps))
            expected_valid = not (wave2_invalid or wave3_invalid or overlap)
            if c.hard_valid != expected_valid:
                impulse_rule_errors += 1
        elif c.pattern in ("zigzag", "flat_candidate", "abc"):
            correction_hard_valid += int(c.hard_valid)
            a = abs(ps[1].price - ps[0].price)
            b = abs(ps[2].price - ps[1].price)
            cc = abs(ps[3].price - ps[2].price)
            b_ratio = b / a if a > 0 else float("inf")
            c_ratio = cc / a if a > 0 else 0.0
            if c.pattern == "flat_candidate":
                atypical = not (0.85 <= b_ratio <= 1.15) or c_ratio < 0.50
            else:
                atypical = a <= 0 or b_ratio >= 1.0 or c_ratio < 0.50
            if atypical:
                correction_soft_warnings += 1

    return {
        "candidate_count": len(candidates),
        "pattern_counts": dict(counts),
        "hard_valid_counts_by_pattern": dict(hard_valid),
        "impulse_candidates_checked": impulse_count,
        "impulse_hard_valid_rule_mismatches": impulse_rule_errors,
        "correction_candidates_marked_hard_valid": correction_hard_valid,
        "correction_candidates_outside_basic_zigzag_morphology": correction_soft_warnings,
        "candidate_pivot_order_errors": pivot_order_errors,
        "candidate_confirmation_metadata_errors": availability_errors,
    }


def main():
    source = require_dataset(EURUSD_TIMEFRAMES[TF])
    print(f"Loading full-history {TF} from {source}...", flush=True)
    candles = load_ohlcv_csv(source)

    print("Auditing candle integrity...", flush=True)
    candle_report = audit_candles(candles)

    print("Running confirmed-pivot detector...", flush=True)
    pivots = detect_pivots(
        candles, min_leg_pips=PIVOT_THRESHOLD_PIPS,
        include_provisional=False,
    )

    print("Checking causal prefix invariance...", flush=True)
    prefix_checks = audit_prefix_invariance(candles, pivots)

    print("Auditing pivot metadata...", flush=True)
    pivot_report = audit_pivots(pivots, candles)

    print("Running Elliott structure engine...", flush=True)
    candidates = ElliottEngine(min_score=25.0).analyze_pivots(pivots)
    candidate_report = audit_candidates(candidates)

    hard_failures = []
    for key in ("duplicate_timestamps", "non_monotonic_timestamps", "invalid_ohlc_rows"):
        if candle_report[key]:
            hard_failures.append(key)
    for key in ("bad_extreme_indices", "bad_confirmation_metadata",
                "non_alternating_pivots", "non_increasing_extreme_indices",
                "confirmation_order_errors", "extreme_time_mismatches",
                "confirmation_time_mismatches"):
        if pivot_report[key]:
            hard_failures.append(key)
    if any(not x["exact_match"] for x in prefix_checks):
        hard_failures.append("causal_prefix_invariance")
    for key in ("impulse_hard_valid_rule_mismatches",
                "candidate_pivot_order_errors",
                "candidate_confirmation_metadata_errors"):
        if candidate_report[key]:
            hard_failures.append(key)

    report = {
        "audit": "elliott_h1_full_history_quality_audit_v1",
        "source_file": source.name,
        "timeframe": TF,
        "pivot_threshold_pips": PIVOT_THRESHOLD_PIPS,
        "candle_integrity": candle_report,
        "pivot_integrity": pivot_report,
        "causal_prefix_invariance": prefix_checks,
        "candidate_integrity": candidate_report,
        "hard_failures": hard_failures,
        "status": "PASS" if not hard_failures else "FAIL",
        "limitations": [
            "This audit does not establish expert Elliott correctness.",
            "Correction hard_valid currently represents basic alternating geometry; morphology warnings are reported separately.",
            "A causal prefix check is a detector invariance check, not proof that every downstream consumer uses availability timestamps correctly.",
            "No predictive edge or trading profitability is tested.",
        ],
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT / "h1_quality_audit.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = [
        "# Elliott H1 Full-History Quality Audit", "",
        f"**Status:** {report['status']}", "",
        "## Candle integrity", "",
        f"- Candles: {candle_report['candles']:,}",
        f"- Range: {candle_report['first_candle_utc']} → {candle_report['last_candle_utc']}",
        f"- Duplicate timestamps: {candle_report['duplicate_timestamps']}",
        f"- Non-monotonic timestamps: {candle_report['non_monotonic_timestamps']}",
        f"- Invalid OHLC rows: {candle_report['invalid_ohlc_rows']}",
        f"- Gaps over one hour: {candle_report['gaps_over_one_hour']}",
        "", "## Pivot integrity", "",
        f"- Confirmed pivots: {pivot_report['pivot_count']:,}",
        f"- Bad confirmation metadata: {pivot_report['bad_confirmation_metadata']}",
        f"- Non-alternating pivots: {pivot_report['non_alternating_pivots']}",
        f"- Confirmation-order errors: {pivot_report['confirmation_order_errors']}",
        "", "## Causal prefix invariance", "",
        "| Prefix | Expected pivots | Prefix pivots | Exact match |",
        "|---:|---:|---:|---|",
    ]
    for x in prefix_checks:
        md.append(f"| {x['cutoff_fraction']:.0%} | {x['expected_confirmed_pivots']} | {x['prefix_detected_pivots']} | {x['exact_match']} |")
    md += [
        "", "## Candidate integrity", "",
        f"- Candidates: {candidate_report['candidate_count']:,}",
        f"- Pattern counts: {candidate_report['pattern_counts']}",
        f"- Impulse rule mismatches: {candidate_report['impulse_hard_valid_rule_mismatches']}",
        f"- Correction candidates outside basic zigzag morphology: {candidate_report['correction_candidates_outside_basic_zigzag_morphology']}",
        f"- Candidate pivot-order errors: {candidate_report['candidate_pivot_order_errors']}",
        "", "## Interpretation", "",
        "A PASS means the implemented data, pivot, causality-invariance and impulse-rule checks passed. It does not mean the wave labels are expert-verified or predictive.",
        "Correction candidates are separately flagged because the current engine marks alternating ABC geometry hard-valid even when its basic zigzag morphology ratios are atypical.",
        "", "## Limitations", "",
    ]
    md.extend(f"- {x}" for x in report["limitations"])
    (OUTPUT / "h1_quality_audit.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("\n===== H1 QUALITY AUDIT =====")
    print(json.dumps(report, indent=2))
    print(f"JSON_REPORT={json_path}")
    print(f"MARKDOWN_REPORT={OUTPUT / 'h1_quality_audit.md'}")
    print(f"ELLIOTT_H1_QUALITY_AUDIT={report['status']}", flush=True)


if __name__ == "__main__":
    main()
