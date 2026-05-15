"""Minimal in-house benchmark for PolyReview.

The dataset under ``data/samples.jsonl`` is **synthetic** — small hand-written
diffs that reproduce well-known anti-patterns. They are not from Defects4J or
CVEfixes; that's an explicit non-goal of this minimal harness. The point is
to give us a small, public-domain, deterministic ground truth so we can
measure pipeline behaviour end-to-end.
"""
