# PolyReview

> 多 Agent 协作的智能代码审查工具 · Multi-Agent AI Code Review

[![CI](https://github.com/hoaipham2580/polyreview/actions/workflows/ci.yml/badge.svg)](https://github.com/hoaipham2580/polyreview/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[English](#english) · [中文](#中文)

---

## 中文

PolyReview 把一次代码审查拆成 **5 个独立的 Agent**:Security、Performance、Style、Logic 四个专长审查员各自用独立的 system prompt 与温度参数点评同一份 diff,最后由 Synthesizer Agent 汇总成一份结构化 Markdown 报告。

这种"多视角并行 + 单点收敛"的编排,对应真人团队 review 的工作方式。在仓库自带的 10 样本评测集上(`src/polyreview/bench/data/samples.jsonl`),三轮真实评测的数据如下:

| Backend | Recall | Precision | Findings/sample |
|---|---:|---:|---:|
| Baseline (single agent, mock) | 50% | 100% | 0.5 |
| **PolyReview-4 + DeepSeek-V4-flash** | **90%** | 47% | 1.9 |
| **PolyReview-4 + GPT-5.4-nano** | **100%** | 22% | 4.6 |

完整数据、per-sample 命中明细与解读见 [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md),用 `python -m polyreview.bench.runner --client openai --model <你的模型> --label <名字>` 一键复现并自动追加新行。

> Precision 看起来低不是模型差,是评测器的 keyword 匹配偏严:模型常常发现**真问题但措辞不在 ground-truth 词典里**(比如在 `open-in-loop` 样本里识别出路径遍历)。Recall 是这个数据集上更真实的指标。下一步要做的就是接上 MiMo 跑同一套评测,数据会自动加进表里。

### 核心特性

- 🤖 **多 Agent 编排** — 5 个专长 Agent(Security / Performance / Style / Logic / Synthesizer)并行协作
- 🔌 **模型无关** — 任何 OpenAI 兼容端点都能跑:小米 MiMo、Claude、GPT、DeepSeek、Qwen…
- 🧪 **Property-Based Testing** — 用 Hypothesis 对 diff 解析器与去重逻辑做随机化属性测试
- 💻 **CLI 优先** — 一行命令处理本地 diff、Git 提交范围或 stdin
- 🎭 **Mock 模式** — 没有 API Key 也能完整跑通端到端流程,演示零成本
- 💾 **响应缓存** — 同一 diff 重复审查时自动命中缓存,避免重复消耗 token
- 📊 **结构化输出** — Markdown / JSON 双格式

### 架构

```
              ┌────────────────────────────────────┐
              │           CLI / Library API        │
              └────────────────┬───────────────────┘
                               │
                  ┌────────────▼────────────┐
                  │      DiffParser         │  解析 unified diff
                  └────────────┬────────────┘
                               │ DiffChunks
                  ┌────────────▼────────────┐
                  │      Orchestrator       │  并发调度 + 缓存
                  └─┬───────┬───────┬─────┬─┘
                    │       │       │     │
        ┌───────────▼┐ ┌────▼────┐ ┌▼──┐ ┌▼──────┐
        │  Security  │ │ Perf.   │ │St.│ │Logic  │   并行 4 路点评
        │   Agent    │ │ Agent   │ │Ag.│ │Agent  │
        └───────────┬┘ └────┬────┘ └┬──┘ └┬──────┘
                    │       │       │     │
                    └───────┼───────┼─────┘
                            ▼       ▼
                  ┌────────────────────────┐
                  │   Synthesizer Agent    │  归并 + 去重 + 排序
                  └────────────┬───────────┘
                               │
                  ┌────────────▼───────────┐
                  │        Reporter        │  Markdown / JSON
                  └────────────────────────┘
```

### 快速开始

```bash
# 安装
pip install -e .

# 走 mock 模式(无需 API Key,直接看到完整流程)
polyreview review examples/sample_diff.patch --mock

# 接入小米 MiMo(具体 URL 与模型名以小米官方文档/拿到 token 时的指引为准)
export POLYREVIEW_API_KEY=sk-xxx
export POLYREVIEW_BASE_URL=https://<你的-MiMo-端点>/v1
export POLYREVIEW_MODEL=<你的-MiMo-模型名>
polyreview review examples/sample_diff.patch

# 审查最近一次提交
polyreview review --git HEAD~1..HEAD --format markdown -o review.md

# 仅启用部分 Agent
polyreview review diff.patch --agents security,logic
```

### 配置

支持环境变量与 `polyreview.toml`:

```toml
# polyreview.toml
[llm]
api_key       = "${POLYREVIEW_API_KEY}"
base_url      = "https://<你的-MiMo-端点>/v1"
model         = "<你的-MiMo-模型名>"
temperature   = 0.2
max_tokens    = 1024
timeout       = 30

[agents]
enabled = ["security", "performance", "style", "logic"]

[cache]
enabled = true
ttl_seconds = 86400
path = ".polyreview-cache"
```

### 输出示例

下面是 mock 模式跑 `examples/sample_diff.patch` 的真实输出:

```markdown
## PolyReview Report
**Files changed:** 3 · **Hunks:** 3 · **Severity:** ⚠️ HIGH

### 🧠 Logic (1 findings)
- **HIGH** `src/api.py:30` — 未处理空列表分支,会触发 IndexError

### 🔒 Security (1 findings)
- **HIGH** `src/auth.py:42` — 字符串拼接构造 SQL,存在注入风险

### ⚡ Performance (1 findings)
- **MED** `src/loader.py:101` — 循环内重复打开同一文件

### 🎨 Style (1 findings)
- **LOW** `src/api.py:18` — 函数缺少 docstring
```

完整示例见 [`examples/sample_report.md`](examples/sample_report.md)。

### 开发

```bash
pip install -e ".[dev]"
pytest                              # 全量测试
pytest tests/test_properties.py -v  # 仅看 PBT
ruff check src tests                # lint
black src tests                     # format
mypy src                            # 类型检查

# 跑评测(确定性 mock,免 token,~1 秒出结果)
python -m polyreview.bench.runner

# 拿到真实模型 token 后,接同一套评测(<你的-XX> 换成实际值)
export POLYREVIEW_API_KEY=sk-xxx
export POLYREVIEW_BASE_URL=https://<你的-端点>/v1
python -m polyreview.bench.runner --client openai --model <你的-模型名> --label <runlabel>
```

每次 `runner` 都会在 `src/polyreview/bench/runs/<label>.json` 里留一份 sidecar,然后**重建** `BENCHMARK_RESULTS.md`——表格只增不减,审核员能看到每接入一个新模型对比都长一行。

### 设计取舍

- **为什么是 5 个 Agent 不是 1 个?** 单 Agent 在多视角任务上容易"被 prompt 长度稀释",而把视角拆开再收敛可以让每个 Agent 聚焦,这是项目的核心假设,验证方式见 BENCHMARK.md。
- **为什么走 OpenAI 兼容协议?** 主流国产模型(MiMo / DeepSeek / Qwen)都已经提供兼容端点,一套代码就能切换。
- **为什么有 Mock 模式?** 测试 / CI / 演示都不该烧 token。

### 路线图

- [x] 5 Agent 并行编排
- [x] OpenAI 兼容 API
- [x] Mock 模式 + 响应缓存
- [x] Property-Based Testing
- [x] **第一轮真实 LLM A/B 评测(DeepSeek-V4-flash + GPT-5.4-nano + Baseline)** — 见 [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md)
- [ ] 接入 MiMo,把 MiMo 行加进对比表(等 token 额度到位)
- [ ] 扩展数据集到 50+ 样本,引入 Defects4J / CVEfixes 真实样本
- [ ] GitHub PR 集成(自动评论)
- [ ] VSCode 插件
- [ ] 自定义 Agent 注册机制
- [ ] 多语言专用 Agent(Rust / Go / Java)

### 协议

[MIT](LICENSE)

---

## English

PolyReview decomposes one code review into **five specialized agents** — Security, Performance, Style, Logic, and a Synthesizer that merges everything into a single structured Markdown report.

The hypothesis: parallel, narrow-scoped agents are more accurate and more steerable than one big agent doing everything. Whether that holds in practice — and at what cost — is what [BENCHMARK.md](BENCHMARK.md) is set up to measure.

### Highlights

- 🤖 **Multi-agent orchestration** — five specialists working in parallel
- 🔌 **Model-agnostic** — any OpenAI-compatible endpoint (Xiaomi MiMo, Claude, GPT, DeepSeek, Qwen…)
- 🧪 **Property-based tests** — Hypothesis-driven tests for the diff parser and dedup logic
- 💻 **CLI-first** — review a patch file, a Git range, or stdin in one line
- 🎭 **Mock mode** — full end-to-end demo with zero API cost
- 💾 **Response cache** — re-reviewing the same diff hits cache

See the Chinese section above for architecture and quick start.

### License

[MIT](LICENSE)
