# Benchmark Plan

> 此文档描述 PolyReview 计划做的评测,而不是已经完成的评测。如果你愿意一起跑,欢迎在 issues 里留言。

## 我们想回答的问题

1. **Q1 — 准确率**:多 Agent 编排相比单 Agent("一个 Agent 做完所有审查")在代码审查任务上是否有可量化的优势?优势体现在哪种问题类型上?
2. **Q2 — 成本**:为了换取这点优势,token 消耗增加多少倍是可以接受的?
3. **Q3 — 模型差异**:同一 Agent 编排下,小米 MiMo / GPT-4o-mini / Claude Haiku / DeepSeek V3 的表现有多大差异?

## 数据集设计

候选数据来源(尚未抓取):

- **Defects4J** 的部分 Java bug fix commit(已知漏洞,有 ground truth)
- **CVEfixes** 中的 Python / JavaScript 安全漏洞修复
- 一个手工标注的 30~50 PR 的小集合(从 awesome-python 列表里挑活跃项目)

每条样本格式:

```json
{
  "diff": "<unified diff>",
  "labels": [
    {"file": "x.py", "line": 42, "category": "security", "severity": "HIGH"}
  ],
  "source_url": "https://github.com/..."
}
```

## 评测指标

- **Recall@k**:模型给出的 top-k 个 finding 里,命中 ground-truth label 的比例
- **Precision@k**:top-k 里有多少是真问题
- **Cost ratio**:多 Agent 总 token 数 / 单 Agent token 数
- **Latency**:端到端 wall-clock 时间(开了并发的情况下)

## 实验组

| 编号 | 配置 |
|---|---|
| Baseline-Single | 一个 Agent 用合并 prompt,所有维度一次给完 |
| PolyReview-4 | Security / Performance / Style / Logic 四路并行 + Synthesizer |
| PolyReview-2 | 仅 Security + Logic(消融实验) |

每组在 4 个模型上各跑一次:`MiMo`、`GPT-4o-mini` / `GPT-5.4-nano`、`Claude Haiku`、`DeepSeek V4`。具体模型名以各厂商官方文档为准——本仓库的 OpenAI 兼容客户端通过环境变量传入,不写死。

## 如何复现(脚本计划中)

```bash
# 拉取数据集(尚未实现)
python -m polyreview.bench fetch --source defects4j --limit 50

# 跑评测(已实现 — 把 <model> 换成你聚合服务的真实模型名)
python -m polyreview.bench.runner --client openai --model <model> --label <label>

# 出报告 — runner 已自动重建 BENCHMARK_RESULTS.md;每跑一次新模型就追加一行
```

## 当前状态

- [x] 评测设计与指标定义
- [x] 数据格式定义
- [x] 第一版 in-house 数据集(10 样本合成集,`src/polyreview/bench/data/samples.jsonl`)
- [x] Baseline-Single 实现(`smart_mock.py` 中的 baseline rule set)
- [x] 评测 runner(`python -m polyreview.bench.runner`)
- [x] **三轮真实 LLM 评测** — 见 [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md):
      PolyReview-4 + GPT-5.4-nano(100% recall, 22% precision, 4.6 findings/sample);
      PolyReview-4 + DeepSeek-V4-flash(90% recall, 47% precision, 1.9 findings/sample);
      Baseline-Single(50% recall, 100% precision)
- [x] 自动重试 + 速率限制(适配第三方聚合 API)
- [x] 按模型隔离的响应缓存
- [ ] 接入 MiMo,把 MiMo 行加进对比表(等 token 额度到位)
- [ ] 扩展数据集到 50+ 样本,引入 Defects4J / CVEfixes 真实样本

后续真实模型评测在拿到更多 token 额度后启动,数据与脚本会同步开源。
