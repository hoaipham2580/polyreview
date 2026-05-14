"""Specialized review agents and the synthesizer."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from polyreview.diff import DiffChunk
from polyreview.llm import ChatClient
from polyreview.models import Finding, Severity

_BASE_PROMPT = """\
你是一名严谨的代码审查员,审查角度: {focus}。
请只针对给定 diff 给出确实存在的问题。
返回严格的 JSON 数组,每项包含字段:severity(LOW/MED/HIGH)、file、line(int)、message、suggestion。
最多返回 {max_items} 条。无问题就返回 []。"""


_AGENT_FOCUSES = {
    "security": ("安全(注入、鉴权缺失、敏感数据暴露、密码学误用)", 4),
    "performance": ("性能(算法复杂度、不必要 IO、循环热点、内存分配)", 4),
    "style": ("代码风格与可读性(命名、结构、文档)", 3),
    "logic": ("功能正确性与边界情况(空值、越界、并发、异常处理)", 4),
}


@dataclass
class ReviewerAgent:
    name: str
    client: ChatClient

    def system_prompt(self) -> str:
        focus, max_items = _AGENT_FOCUSES[self.name]
        return _BASE_PROMPT.format(focus=focus, max_items=max_items)

    async def review(self, chunks: list[DiffChunk]) -> list[Finding]:
        if not chunks:
            return []
        diff_text = "\n\n".join(c.render() for c in chunks)
        raw = await self.client.complete(self.system_prompt(), diff_text, agent=self.name)
        return _parse_findings(raw, agent=self.name)


@dataclass
class Synthesizer:
    client: ChatClient

    async def summarize(self, findings: list[Finding]) -> str:
        if not findings:
            return "未发现问题。"
        sketch = "\n".join(
            f"- [{f.severity.value}] {f.agent} {f.file}:{f.line} {f.message}" for f in findings
        )
        return await self.client.complete(
            "你是评审组长,基于多名 Agent 的发现,用 1-2 句话给出总体结论与优先级。",
            sketch,
            agent="synthesizer",
        )


_SEVERITY_ALIASES = {
    "LOW": Severity.LOW,
    "L": Severity.LOW,
    "INFO": Severity.LOW,
    "MINOR": Severity.LOW,
    "MED": Severity.MED,
    "MEDIUM": Severity.MED,
    "M": Severity.MED,
    "MODERATE": Severity.MED,
    "WARNING": Severity.MED,
    "WARN": Severity.MED,
    "HIGH": Severity.HIGH,
    "H": Severity.HIGH,
    "CRITICAL": Severity.HIGH,
    "ERROR": Severity.HIGH,
    "SEVERE": Severity.HIGH,
}


def _coerce_severity(raw: object) -> Severity:
    s = str(raw or "").strip().upper()
    return _SEVERITY_ALIASES.get(s, Severity.LOW)


# Greedy JSON-array finder. Real LLMs occasionally wrap their JSON in prose
# ("Here are my findings: [...]"), or emit multiple back-to-back arrays
# (e.g. "[]\n\n[ {...} ]"). This regex hands us every top-level array and
# we union them.
_ARRAY_RE = re.compile(r"\[(?:[^\[\]]|\[[^\[\]]*\])*\]", re.DOTALL)


def _parse_findings(raw: str, *, agent: str) -> list[Finding]:
    """Parse LLM JSON output, tolerating common formatting noise.

    Strategies, in order:
      1. Strip a single ```json fence``` if present, then `json.loads`.
      2. Find every ``[...]`` substring in the response and try each.
      3. Give up — the response was prose-only.
    """
    if not raw or not raw.strip():
        return []
    text = raw.strip()

    # Strategy 1: code fence + direct parse.
    if text.startswith("```"):
        # Drop the opening fence line.
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        # Drop trailing fence.
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        text = text.strip()

    items: list[dict] = []
    try:
        loaded = json.loads(text)
        if isinstance(loaded, list):
            items = [x for x in loaded if isinstance(x, dict)]
        elif isinstance(loaded, dict):
            items = [loaded]
    except json.JSONDecodeError:
        # Strategy 2: extract every JSON array we can see.
        for m in _ARRAY_RE.finditer(text):
            try:
                arr = json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
            if isinstance(arr, list):
                items.extend(x for x in arr if isinstance(x, dict))

    out: list[Finding] = []
    for item in items:
        try:
            sev = _coerce_severity(item.get("severity"))
            line_raw = item.get("line", 0)
            if isinstance(line_raw, str):
                lm = re.search(r"\d+", line_raw)
                line = int(lm.group(0)) if lm else 0
            else:
                try:
                    line = int(line_raw or 0)
                except (TypeError, ValueError):
                    line = 0
            message = str(item.get("message", "")).strip()
            if not message:
                continue  # Pydantic would reject min_length=1 anyway
            file_name = str(item.get("file") or "<unknown>").strip() or "<unknown>"
            out.append(
                Finding(
                    agent=agent,
                    severity=sev,
                    file=file_name,
                    line=line,
                    message=message[:2000],
                    suggestion=item.get("suggestion"),
                )
            )
        except (ValueError, TypeError):
            continue
    return out
