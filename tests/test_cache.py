"""Regression tests for CachedChatClient.

Background: an earlier version keyed the cache on (agent, system, user)
only, which meant switching the underlying model would silently return
stale data captured for a previous model. We caught it when two
consecutive runner passes against different models produced byte-identical
output. These tests pin down the fix.
"""

from __future__ import annotations

from dataclasses import dataclass

from polyreview.config import LLMConfig
from polyreview.llm import CachedChatClient, OpenAIChatClient


@dataclass
class RecordingClient:
    """Stand-in inner client that returns a tagged response and counts calls."""

    tag: str
    config: LLMConfig | None = None
    calls: int = 0

    async def complete(self, system: str, user: str, *, agent: str) -> str:
        self.calls += 1
        return f"<{self.tag}>"


async def test_same_client_same_prompt_hits_cache(tmp_path) -> None:
    inner = RecordingClient(tag="A")
    cache = CachedChatClient(inner, tmp_path)
    a = await cache.complete("sys", "user", agent="security")
    b = await cache.complete("sys", "user", agent="security")
    assert a == b == "<A>"
    assert inner.calls == 1, "second call should hit cache"


async def test_different_models_do_not_share_cache(tmp_path) -> None:
    """The bug: changing model used to silently reuse old cached output."""
    inner_a = RecordingClient(
        tag="A",
        config=LLMConfig(model="model-a", base_url="https://x.example/v1"),
    )
    inner_b = RecordingClient(
        tag="B",
        config=LLMConfig(model="model-b", base_url="https://x.example/v1"),
    )
    cache_a = CachedChatClient(inner_a, tmp_path)
    cache_b = CachedChatClient(inner_b, tmp_path)

    out_a = await cache_a.complete("sys", "user", agent="security")
    out_b = await cache_b.complete("sys", "user", agent="security")

    assert out_a == "<A>"
    assert out_b == "<B>", "different model must not be served from another model's cache"
    assert inner_a.calls == 1
    assert inner_b.calls == 1


async def test_different_base_urls_do_not_share_cache(tmp_path) -> None:
    inner_a = RecordingClient(
        tag="A",
        config=LLMConfig(model="same-name", base_url="https://providerA.example/v1"),
    )
    inner_b = RecordingClient(
        tag="B",
        config=LLMConfig(model="same-name", base_url="https://providerB.example/v1"),
    )
    cache_a = CachedChatClient(inner_a, tmp_path)
    cache_b = CachedChatClient(inner_b, tmp_path)

    await cache_a.complete("sys", "user", agent="security")
    out_b = await cache_b.complete("sys", "user", agent="security")
    assert out_b == "<B>", "same model name on a different base URL is a different identity"


async def test_disabled_cache_never_persists(tmp_path) -> None:
    inner = RecordingClient(tag="A")
    cache = CachedChatClient(inner, tmp_path, enabled=False)
    await cache.complete("sys", "user", agent="security")
    await cache.complete("sys", "user", agent="security")
    assert inner.calls == 2


def test_real_openai_client_carries_config_for_cache_key() -> None:
    """Sanity check: the production OpenAIChatClient exposes .config so the
    cache wrapper can read .model + .base_url from it."""
    cfg = LLMConfig(model="gpt-test", base_url="https://example/v1")
    cli = OpenAIChatClient(cfg)
    assert cli.config.model == "gpt-test"
    assert cli.config.base_url == "https://example/v1"


def test_cache_filename_is_just_a_hash(tmp_path) -> None:
    """No raw model name or URL should leak into the on-disk filename
    (would risk path-injection on weird model strings like 'a/b')."""
    inner = RecordingClient(
        tag="A",
        config=LLMConfig(model="vendor/with/slashes", base_url="https://x/v1"),
    )
    cache = CachedChatClient(inner, tmp_path)
    import asyncio

    asyncio.run(cache.complete("s", "u", agent="security"))
    # exactly one cache file, name is sha256 hex
    files = list(tmp_path.glob("*.txt"))
    assert len(files) == 1
    assert len(files[0].stem) == 64
    int(files[0].stem, 16)  # raises if not hex


# Allow pytest to await the async tests above without explicit decorators
# (we already have asyncio_mode=auto in pyproject.toml).
