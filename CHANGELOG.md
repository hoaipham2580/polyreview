# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Planned
- Add MiMo to the cross-model comparison once tokens are available.
- Extend benchmark dataset to 50+ samples incl. Defects4J / CVEfixes.
- GitHub PR auto-comment integration.

## [0.3.0]

### Added
- Disk-backed response cache (`CachedChatClient`). Repeat reviews of the same
  diff hit cache and avoid re-spending tokens. Cache key includes model +
  base URL so swapping models never returns stale data.
- `--mock` flag for offline / zero-cost end-to-end demos.
- Property-based test suite covering parser totality and dedup idempotence.
- **Minimal in-house benchmark** (`polyreview.bench`): 10 hand-written
  samples, pattern-matching mock client, single-agent baseline, and a
  runner that emits `BENCHMARK_RESULTS.md`.
- **Real-LLM mode for the benchmark** (`--client openai`): same dataset,
  any OpenAI-compatible endpoint. Each run persists a JSON sidecar under
  `bench/runs/`; the Markdown is rebuilt from all sidecars so the
  comparison table accretes as more models are tried.
- **Auto-retry with exponential back-off + rate limiting** in
  `OpenAIChatClient`, configurable via `POLYREVIEW_LLM_CONCURRENCY` and
  `POLYREVIEW_LLM_MIN_INTERVAL`. Required for shared / free-tier
  aggregator endpoints that enforce 1 RPS.
- **Robust JSON parser for agent outputs**: tolerates `MEDIUM` /
  `Critical` / `Warning` severity aliases, prose-wrapped JSON,
  back-to-back arrays, code fences, and string line numbers like `L42`.
- First three real-LLM runs: DeepSeek-V4-flash (90% recall, 47%
  precision, 1.9 findings/sample), GPT-5.4-nano (100% recall, 22%
  precision, 4.6 findings/sample), Baseline-Single (50% recall).
  Headline conclusion: multi-agent orchestration is robust to the model
  swap; the precision penalty is mostly evaluator-side, not model-side.

### Changed
- Synthesizer now produces a single one-line verdict instead of per-agent prose.
- Default `max_tokens` lowered from 2048 → 1024 per agent.

## [0.2.0]

### Added
- `--git HEAD~1..HEAD` mode for reviewing recent commits directly.
- JSON reporter for CI integrations.

### Changed
- Switched HTTP client from `requests` to `httpx` (async).

## [0.1.0]

### Added
- Initial scaffold: 4 specialist agents + 1 synthesizer.
- OpenAI-compatible chat client.
- Markdown reporter.
