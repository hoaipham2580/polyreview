"""Lock in the synthetic-benchmark numbers so they don't silently regress."""

from __future__ import annotations

import asyncio

from polyreview.bench.runner import (
    load_samples,
    run_baseline,
    run_polyreview,
)
from polyreview.bench.smart_mock import SmartMockClient


def test_loads_ten_synthetic_samples() -> None:
    samples = load_samples()
    assert len(samples) == 10
    assert {s.id for s in samples} >= {"s01-sql-injection", "s10-unbounded-recursion"}


def test_polyreview_outperforms_baseline_on_synthetic_set() -> None:
    samples = load_samples()
    poly = asyncio.run(run_polyreview(samples, SmartMockClient(), "test", "mock", "n/a"))
    base = run_baseline(samples, "test")

    # Property the design is meant to satisfy:
    assert poly.recall >= base.recall, (
        "Multi-agent recall regressed below single-agent baseline. "
        "Either specialist coverage shrank or dedup is collapsing too aggressively."
    )

    # Concrete numbers from our calibrated synthetic set. If you change the
    # rule sets or dataset, update these and BENCHMARK_RESULTS.md together.
    assert base.recall == 0.50
    assert poly.recall == 1.00
    assert base.precision == 1.0
    assert poly.precision == 1.0
