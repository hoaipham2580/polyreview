"""Render ``ReviewReport`` to Markdown / JSON / terminal."""

from __future__ import annotations

import json

from polyreview.models import ReviewReport, Severity

_SEV_BADGE = {Severity.HIGH: "⚠️ HIGH", Severity.MED: "🟠 MED", Severity.LOW: "🟢 LOW"}
_AGENT_TITLE = {
    "security": "🔒 Security",
    "performance": "⚡ Performance",
    "style": "🎨 Style",
    "logic": "🧠 Logic",
}


def to_markdown(report: ReviewReport) -> str:
    lines: list[str] = []
    lines.append("## PolyReview Report")
    lines.append(
        f"**Files changed:** {report.files_changed} · "
        f"**Hunks:** {report.hunks} · "
        f"**Severity:** {_SEV_BADGE[report.overall_severity]}"
    )
    lines.append("")
    if report.summary:
        lines.append(f"> {report.summary}")
        lines.append("")

    if not report.findings:
        lines.append("_No findings — looks good._")
        return "\n".join(lines)

    seen_agents = []
    for f in report.findings:
        if f.agent not in seen_agents:
            seen_agents.append(f.agent)

    for agent in seen_agents:
        items = report.by_agent(agent)
        title = _AGENT_TITLE.get(agent, agent.title())
        lines.append(f"### {title} ({len(items)} findings)")
        for f in items:
            sev = f.severity.value.ljust(4)
            lines.append(f"- **{sev}** `{f.file}:{f.line}` — {f.message}")
            if f.suggestion:
                lines.append(f"  - 建议: {f.suggestion}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_json(report: ReviewReport) -> str:
    return json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
