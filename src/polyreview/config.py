"""Configuration loading."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


@dataclass
class LLMConfig:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 1024
    timeout: float = 30.0


@dataclass
class CacheConfig:
    enabled: bool = True
    ttl_seconds: int = 86400
    path: str = ".polyreview-cache"


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    enabled_agents: list[str] = field(
        default_factory=lambda: ["security", "performance", "style", "logic"]
    )

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        cfg = cls()
        cfg._apply_env()
        if path and Path(path).exists():
            cfg._apply_file(Path(path))
        return cfg

    def _apply_env(self) -> None:
        if v := os.environ.get("POLYREVIEW_API_KEY"):
            self.llm.api_key = v
        if v := os.environ.get("POLYREVIEW_BASE_URL"):
            self.llm.base_url = v
        if v := os.environ.get("POLYREVIEW_MODEL"):
            self.llm.model = v

    def _apply_file(self, p: Path) -> None:
        with p.open("rb") as fh:
            data = tomllib.load(fh)
        llm = data.get("llm", {})
        for k in ("api_key", "base_url", "model"):
            if k in llm and isinstance(llm[k], str):
                value = os.path.expandvars(llm[k])
                setattr(self.llm, k, value)
        for k in ("temperature", "max_tokens", "timeout"):
            if k in llm:
                setattr(self.llm, k, llm[k])
        cache = data.get("cache", {})
        for k in ("enabled", "ttl_seconds", "path"):
            if k in cache:
                setattr(self.cache, k, cache[k])
        agents = data.get("agents", {})
        if "enabled" in agents and isinstance(agents["enabled"], list):
            self.enabled_agents = list(agents["enabled"])
