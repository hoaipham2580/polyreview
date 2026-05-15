"""Command-line entry point."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

from polyreview.config import Config
from polyreview.orchestrator import Orchestrator
from polyreview.reporter import to_json, to_markdown

console = Console()


@click.group()
@click.version_option(package_name="polyreview")
def main() -> None:
    """PolyReview — multi-agent AI code review."""


@main.command()
@click.argument("source", required=False)
@click.option("--git", "git_range", help="Git revision range, e.g. HEAD~1..HEAD")
@click.option("--mock", is_flag=True, help="Use deterministic offline mock LLM")
@click.option(
    "--agents",
    default=None,
    help="Comma-separated subset, e.g. security,logic",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["markdown", "json"]),
    default="markdown",
    show_default=True,
)
@click.option("-o", "--output", type=click.Path(dir_okay=False), default=None)
@click.option(
    "-c",
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to polyreview.toml",
)
def review(
    source: str | None,
    git_range: str | None,
    mock: bool,
    agents: str | None,
    fmt: str,
    output: str | None,
    config_path: str | None,
) -> None:
    """Run a review against a diff file, a Git range, or stdin."""
    cfg = Config.load(config_path or _find_default_config())
    if agents:
        cfg.enabled_agents = [a.strip() for a in agents.split(",") if a.strip()]

    diff_text = _resolve_diff(source, git_range)
    if not diff_text.strip():
        console.print("[yellow]No diff to review.[/yellow]")
        sys.exit(0)

    orch = Orchestrator.from_config(cfg, mock=mock)
    report = asyncio.run(orch.review_diff(diff_text))

    rendered = to_markdown(report) if fmt == "markdown" else to_json(report)
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
        console.print(f"[green]Report written to {output}[/green]")
    else:
        console.print(rendered)


def _find_default_config() -> str | None:
    p = Path("polyreview.toml")
    return str(p) if p.exists() else None


def _resolve_diff(source: str | None, git_range: str | None) -> str:
    if git_range:
        return _run_git_diff(git_range)
    if source and source != "-":
        return Path(source).read_text(encoding="utf-8")
    return sys.stdin.read()


def _run_git_diff(rev_range: str) -> str:
    out = subprocess.run(
        ["git", "diff", rev_range],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout


if __name__ == "__main__":  # pragma: no cover
    main()
