"""Thin OpenAI-compatible chat client with mock support."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import httpx

from polyreview.config import LLMConfig


class ChatClient(Protocol):
    async def complete(self, system: str, user: str, *, agent: str) -> str: ...


# Concurrency cap that applies to ALL real-LLM requests across the whole
# process. Tunable via env var so users on shared / free aggregator keys
# don't have to edit code. 1 = strictly serial, which is the safest default
# for rate-limited free tiers.
_REAL_LLM_CONCURRENCY = int(os.environ.get("POLYREVIEW_LLM_CONCURRENCY", "1"))
_REAL_LLM_SEMAPHORE = asyncio.Semaphore(_REAL_LLM_CONCURRENCY)

# Inter-request delay (seconds). Some shared aggregators enforce a hard
# 1-RPS cap; an explicit small sleep is more reliable than backoff alone.
_REAL_LLM_MIN_INTERVAL = float(os.environ.get("POLYREVIEW_LLM_MIN_INTERVAL", "0.0"))


@dataclass
class OpenAIChatClient:
    config: LLMConfig
    max_retries: int = 5
    _last_call_at: list[float] = field(default_factory=lambda: [0.0])

    async def complete(self, system: str, user: str, *, agent: str) -> str:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        payload = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with _REAL_LLM_SEMAPHORE:
                    if _REAL_LLM_MIN_INTERVAL > 0:
                        now = asyncio.get_event_loop().time()
                        wait = _REAL_LLM_MIN_INTERVAL - (now - self._last_call_at[0])
                        if wait > 0:
                            await asyncio.sleep(wait)
                        self._last_call_at[0] = asyncio.get_event_loop().time()

                    async with httpx.AsyncClient(timeout=self.config.timeout) as cli:
                        r = await cli.post(url, headers=headers, json=payload)
                        if r.status_code == 429 or r.status_code >= 500:
                            # Honour Retry-After header if the server sent one.
                            retry_after = r.headers.get("retry-after")
                            if retry_after and retry_after.isdigit():
                                delay = float(retry_after)
                            else:
                                delay = min(2**attempt, 30) + random.uniform(0, 1)
                            print(
                                f"[polyreview] {r.status_code} from {self.config.model} "
                                f"agent={agent}, sleeping {delay:.1f}s "
                                f"(attempt {attempt + 1}/{self.max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                        r.raise_for_status()
                        data = r.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                last_exc = e
                # Non-retryable client errors (e.g. 400 bad model name).
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise
                continue
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                delay = min(2**attempt, 30) + random.uniform(0, 1)
                print(
                    f"[polyreview] network error: {e!r}; sleeping {delay:.1f}s "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                await asyncio.sleep(delay)
                continue

        raise RuntimeError(
            f"Exhausted {self.max_retries} retries for agent={agent}; last error: {last_exc!r}"
        )


class MockChatClient:
    """Deterministic, offline-friendly client for tests / demos."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    async def complete(self, system: str, user: str, *, agent: str) -> str:
        await asyncio.sleep(0)  # yield, simulate async
        templates = {
            "security": [
                {
                    "severity": "HIGH",
                    "file": "src/auth.py",
                    "line": 42,
                    "message": "字符串拼接构造 SQL,存在注入风险",
                    "suggestion": "改用参数化查询或 ORM。",
                }
            ],
            "performance": [
                {
                    "severity": "MED",
                    "file": "src/loader.py",
                    "line": 101,
                    "message": "循环内重复打开同一文件",
                    "suggestion": "把 open() 提到循环外,或使用流式读取。",
                }
            ],
            "style": [
                {
                    "severity": "LOW",
                    "file": "src/api.py",
                    "line": 18,
                    "message": "函数缺少 docstring",
                    "suggestion": "添加简短的 docstring 描述返回值。",
                }
            ],
            "logic": [
                {
                    "severity": "HIGH",
                    "file": "src/api.py",
                    "line": 30,
                    "message": "未处理空列表分支,会触发 IndexError",
                    "suggestion": "在访问前判断长度并返回明确错误。",
                }
            ],
            "synthesizer": [],
        }
        if agent == "synthesizer":
            return "整体风险偏高,优先修复 SQL 注入与索引越界,其余作为后续优化项。"
        return json.dumps(templates.get(agent, []), ensure_ascii=False)


class CachedChatClient:
    """Thin disk cache wrapper around any ``ChatClient``.

    The cache key includes the underlying client's identity (model + base URL
    when wrapping ``OpenAIChatClient``) so that switching models does NOT
    reuse responses captured for a previous model. Earlier versions hashed
    only the prompt, which silently returned stale cross-model data — this
    was caught when two consecutive runs against different models produced
    byte-identical outputs.
    """

    def __init__(self, inner: ChatClient, path: str | Path, *, enabled: bool = True) -> None:
        self.inner = inner
        self.dir = Path(path)
        self.enabled = enabled
        if enabled:
            self.dir.mkdir(parents=True, exist_ok=True)

    def _identity(self) -> str:
        # Walk past additional wrappers if any, to find the most identifying
        # client. For OpenAIChatClient we use model + base_url; otherwise
        # we fall back to the class name.
        target = self.inner
        cfg = getattr(target, "config", None)
        if cfg is not None and hasattr(cfg, "model") and hasattr(cfg, "base_url"):
            return f"{type(target).__name__}|{cfg.model}|{cfg.base_url}"
        return type(target).__name__

    async def complete(self, system: str, user: str, *, agent: str) -> str:
        if not self.enabled:
            return await self.inner.complete(system, user, agent=agent)
        key_text = f"{self._identity()}\n{agent}\n{system}\n{user}"
        key = hashlib.sha256(key_text.encode()).hexdigest()
        f = self.dir / f"{key}.txt"
        if f.exists():
            return f.read_text(encoding="utf-8")
        out = await self.inner.complete(system, user, agent=agent)
        f.write_text(out, encoding="utf-8")
        return out
