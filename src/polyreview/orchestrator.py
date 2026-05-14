"""Concurrent multi-agent orchestrator."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from polyreview.agents import ReviewerAgent, Synthesizer
from polyreview.config import Config
from polyreview.diff import DiffChunk, DiffParser
from polyreview.llm import CachedChatClient, ChatClient, MockChatClient, OpenAIChatClient
from polyreview.models import Finding, ReviewReport


@dataclass
class Orchestrator:
    config: Config
    client: ChatClient

    @classmethod
    def from_config(cls, config: Config, *, mock: bool = False) -> Orchestrator:
        base: ChatClient = MockChatClient() if mock else OpenAIChatClient(config.llm)
        client = CachedChatClient(base, config.cache.path, enabled=config.cache.enabled)
        return cls(config=config, client=client)

    async def review_diff(self, diff_text: str, *, summarize: bool = True) -> ReviewReport:
        chunks = DiffParser().parse(diff_text)
        return await self.review_chunks(chunks, summarize=summarize)

    async def review_chunks(
        self, chunks: list[DiffChunk], *, summarize: bool = True
    ) -> ReviewReport:
        agents = [ReviewerAgent(name=n, client=self.client) for n in self.config.enabled_agents]
        results = await asyncio.gather(
            *(a.review(chunks) for a in agents),
            return_exceptions=False,
        )

        # Flatten + de-duplicate via Finding.key().
        seen: set[tuple[str, str, int, str]] = set()
        merged: list[Finding] = []
        for batch in results:
            for f in batch:
                k = f.key()
                if k in seen:
                    continue
                seen.add(k)
                merged.append(f)

        # Stable sort: severity desc, file asc, line asc.
        merged.sort(key=lambda f: (-f.severity.rank, f.file, f.line))

        if summarize:
            synth = Synthesizer(self.client)
            summary = await synth.summarize(merged)
        else:
            summary = ""

        files = sorted({c.file for c in chunks})
        return ReviewReport(
            findings=merged,
            files_changed=len(files),
            hunks=len(chunks),
            summary=summary,
        )
