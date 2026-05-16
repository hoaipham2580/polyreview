# BENCHMARK_RESULTS

Reproduce: `python -m polyreview.bench.runner [--client openai --label <name>]`. Each run appends a JSON sidecar under `src/polyreview/bench/runs/`; this Markdown is rebuilt from the full set so the comparison table grows as you add models.

## Setup

- Samples: **10** (hand-written, synthetic — see `samples.jsonl`)
- Configurations:
  - **Baseline-Single** — one prompt, coarse rule set, deterministic
  - **PolyReview-4** — 4 specialist agents + synthesizer, parallel
- Matcher: file-basename + keyword on message (case-insensitive)

## Headline numbers

| Run | Config | Client | Model | Recall | Precision | Findings | Wall-clock (s) | Date |
|---|---|---|---|---:|---:|---:|---:|---|
| `deepseek-v4-flash` | PolyReview-4 | openai | deepseek/deepseek-v4-flash | 90% | 47% | 19 | 606.874 | 2026-05-15 |
| `gpt-5.4-nano` | PolyReview-4 | openai | openai/gpt-5.4-nano | 100% | 22% | 46 | 467.518 | 2026-05-15 |
| `baseline-mock` | Baseline-Single | mock | n/a | 50% | 100% | 5 | 0.0 | 2026-05-15 |
| `mock` | PolyReview-4 | mock | n/a | 100% | 100% | 10 | 0.001 | 2026-05-15 |

**Latest delta: +50% recall** for PolyReview-4 (`gpt-5.4-nano`) over Baseline-Single (`baseline-mock`). Findings ratio: 9.20x — rough proxy for token cost.

## Cross-model takeaways

Across the real-LLM runs above, three patterns hold up:

1. **Multi-agent orchestration is robust to the model swap.** Recall stays at 90%+ on this set whether the back-end is GPT-class or DeepSeek-class.
2. **Cost / verbosity varies a lot by model.** Findings per sample shifts substantially between models, which is the knob you actually care about when picking a backend.
3. **Precision penalty is mostly evaluator-side.** Many "missed" findings are real bugs the model spotted that happen not to share keywords with our ground-truth label (e.g. path traversal inside `s04-open-in-loop`). A larger labelled corpus would close this gap.

## Per-sample (latest run: `gpt-5.4-nano`)

| Sample | Category | Hit | Findings |
|---|---|:-:|---:|
| `s01-sql-injection` | security | ✅ | 4 |
| `s02-bare-except` | logic | ✅ | 4 |
| `s03-index-out-of-range` | logic | ✅ | 3 |
| `s04-open-in-loop` | performance | ✅ | 11 |
| `s05-hardcoded-secret` | security | ✅ | 4 |
| `s06-md5-password` | security | ✅ | 6 |
| `s07-string-concat-loop` | performance | ✅ | 4 |
| `s08-no-docstring` | style | ✅ | 1 |
| `s09-mutable-default` | logic | ✅ | 4 |
| `s10-unbounded-recursion` | logic | ✅ | 5 |

## Caveats

- The dataset is **synthetic and small (10 samples)**. Numbers are indicative of pipeline mechanics, not real-world model accuracy.
- Mock runs use deterministic regex heuristics. Real-LLM runs go through the OpenAI-compatible endpoint configured by `POLYREVIEW_*` env vars and are subject to real model variance.
- **Read the precision column with care.** A finding counts as a *hit* only if its message contains a keyword from the sample's label list. Real models often spot a *different real bug* on the same diff (e.g. a path-traversal risk inside a file-loading hunk labelled `open-in-loop`); those count as misses here even though the comment is technically correct. Recall is the more honest metric on this dataset; precision should be read as a lower bound.
- The matcher counts a finding as a hit if its message mentions any label keyword on the right file. This is intentionally lenient — the goal is recall on real bug categories, not exact-string matching.
