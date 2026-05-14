"""Pydantic models for findings and reports."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"

    @property
    def rank(self) -> int:
        return {"LOW": 0, "MED": 1, "HIGH": 2}[self.value]


class Finding(BaseModel):
    """A single review comment from an agent."""

    agent: str = Field(..., description="Name of the agent that produced this finding")
    severity: Severity
    file: str
    line: int = Field(ge=0)
    message: str = Field(min_length=1, max_length=2000)
    suggestion: str | None = None

    @field_validator("file")
    @classmethod
    def _file_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("file must not be empty")
        return v

    def key(self) -> tuple[str, str, int, str]:
        """Stable identity used for de-duplication."""
        return (self.agent, self.file, self.line, self.message.strip().lower())


class ReviewReport(BaseModel):
    """Final aggregated report produced by the Synthesizer."""

    findings: list[Finding] = Field(default_factory=list)
    files_changed: int = 0
    hunks: int = 0
    summary: str = ""

    @property
    def overall_severity(self) -> Severity:
        if not self.findings:
            return Severity.LOW
        return max(self.findings, key=lambda f: f.severity.rank).severity

    def by_agent(self, agent: str) -> list[Finding]:
        return [f for f in self.findings if f.agent == agent]
