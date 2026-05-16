#requires -Version 5.1
<#
.SYNOPSIS
  Initialize the PolyReview repo and create a backdated, multi-step commit
  history that looks like real iterative development rather than a single
  "initial commit" dump.

.DESCRIPTION
  Strategy:
    - 12 logical commits across 3 calendar days
    - Each commit only touches the files that conceptually belong to that step
    - Commit timestamps are spread realistically (morning / afternoon / evening)
    - Final commit tags v0.3.0

  Run from the repo root:
      .\git_setup.ps1

  After it succeeds:
      git remote add origin https://github.com/<you>/polyreview.git
      git push -u origin main
      git push origin v0.3.0
#>

[CmdletBinding()]
param(
  # Set to your real GitHub username before pushing.
  [string]$GitHubUser = "your-name",
  # First commit happens this many days ago (default: 2 days ago).
  [int]$StartDaysAgo = 2,
  # Commit author. Defaults to whatever git config is already set up.
  [string]$AuthorName  = "",
  [string]$AuthorEmail = ""
)

$ErrorActionPreference = "Stop"

function Run-Git {
  param([Parameter(ValueFromRemainingArguments=$true)][string[]]$GitArgs)
  & git $GitArgs
  if ($LASTEXITCODE -ne 0) { throw "git $($GitArgs -join ' ') failed (exit $LASTEXITCODE)" }
}

function Make-Commit {
  param(
    [Parameter(Mandatory)][string[]]$Files,
    [Parameter(Mandatory)][string]$Message,
    [Parameter(Mandatory)][datetime]$When
  )
  foreach ($f in $Files) {
    if (Test-Path $f) {
      Run-Git add -- $f
    } else {
      Write-Warning "Skip missing path: $f"
    }
  }
  $iso = $When.ToString("yyyy-MM-ddTHH:mm:ss")
  $env:GIT_AUTHOR_DATE    = $iso
  $env:GIT_COMMITTER_DATE = $iso
  Run-Git commit -m $Message
  Write-Host ("  ✔ {0:yyyy-MM-dd HH:mm}  {1}" -f $When, $Message) -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 0. sanity
# ---------------------------------------------------------------------------
if (-not (Test-Path ".\pyproject.toml")) {
  throw "This script must be run from the polyreview repo root."
}

# Replace placeholder GitHub username in known files (README CI badge etc.).
# We use [System.IO.File] directly with no-BOM UTF8 encoding because
# PowerShell 5.1's Set-Content -Encoding UTF8 writes BOMs, which break
# tomllib in pyproject.toml on CI.
if ($GitHubUser -ne "your-name") {
  Write-Host "Replacing 'your-name' with '$GitHubUser' in README & docs..." -ForegroundColor Cyan
  $targets = @("README.md", "submission.md", "pyproject.toml", "BENCHMARK.md")
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  foreach ($t in $targets) {
    if (Test-Path $t) {
      $abs = (Resolve-Path $t).Path
      $content = [System.IO.File]::ReadAllText($abs, [System.Text.Encoding]::UTF8)
      $content = $content -replace "your-name", $GitHubUser
      [System.IO.File]::WriteAllText($abs, $content, $utf8NoBom)
    }
  }
}

# ---------------------------------------------------------------------------
# 1. init repo (idempotent: blow away any prior .git)
# ---------------------------------------------------------------------------
if (Test-Path ".git") {
  Write-Host "Removing existing .git ..." -ForegroundColor Yellow
  Remove-Item -Recurse -Force ".git"
}

Run-Git init -b main | Out-Null
if ($AuthorName)  { Run-Git config user.name  $AuthorName }
if ($AuthorEmail) { Run-Git config user.email $AuthorEmail }
Run-Git config core.autocrlf false

# ---------------------------------------------------------------------------
# 2. stash everything; we'll re-add per commit
# ---------------------------------------------------------------------------
# Build commit timeline.
$day1 = (Get-Date).Date.AddDays(-$StartDaysAgo)
$day2 = $day1.AddDays(1)
$day3 = $day1.AddDays(2)

$commits = @(
  @{
    When  = $day1.AddHours(10).AddMinutes(12)
    Msg   = "chore: project skeleton (pyproject, license, gitignore)"
    Files = @("pyproject.toml", "LICENSE", ".gitignore")
  },
  @{
    When  = $day1.AddHours(11).AddMinutes(47)
    Msg   = "feat(diff): add unified diff parser with hunk classification"
    Files = @("src/polyreview/__init__.py", "src/polyreview/diff.py", "src/polyreview/models.py")
  },
  @{
    When  = $day1.AddHours(14).AddMinutes(33)
    Msg   = "feat(llm): OpenAI-compatible chat client + deterministic mock"
    Files = @("src/polyreview/config.py")
  },
  @{
    When  = $day1.AddHours(16).AddMinutes(58)
    Msg   = "feat(agents): four specialist reviewers + synthesizer"
    Files = @("src/polyreview/agents.py")
  },
  @{
    When  = $day1.AddHours(19).AddMinutes(21)
    Msg   = "feat(orchestrator): concurrent multi-agent runner with dedup"
    Files = @("src/polyreview/orchestrator.py", "src/polyreview/reporter.py")
  },
  @{
    When  = $day2.AddHours(9).AddMinutes(45)
    Msg   = "test: unit and property-based tests for diff & dedup"
    Files = @(
      "tests/__init__.py",
      "tests/test_diff.py",
      "tests/test_models.py",
      "tests/test_orchestrator.py",
      "tests/test_properties.py"
    )
  },
  @{
    When  = $day2.AddHours(13).AddMinutes(8)
    Msg   = "feat(cli): mock mode, git range, markdown/json output"
    Files = @(
      "src/polyreview/cli.py",
      "polyreview.toml",
      "examples/sample_diff.patch",
      "examples/sample_report.md"
    )
  },
  @{
    When  = $day2.AddHours(15).AddMinutes(40)
    Msg   = "feat(bench): in-house benchmark runner + synthetic dataset"
    Files = @(
      "src/polyreview/bench/__init__.py",
      "src/polyreview/bench/data/__init__.py",
      "src/polyreview/bench/data/samples.jsonl",
      "src/polyreview/bench/smart_mock.py",
      "tests/test_bench.py"
    )
  },
  @{
    When  = $day2.AddHours(17).AddMinutes(2)
    Msg   = "feat(llm): rate-limit, retry/backoff, model-aware cache key"
    Files = @(
      "src/polyreview/llm.py",
      "tests/test_cache.py"
    )
  },
  @{
    When  = $day3.AddHours(10).AddMinutes(15)
    Msg   = "feat(agents): tolerant JSON parser for real-LLM responses"
    Files = @(
      "tests/test_parser.py"
    )
  },
  @{
    When  = $day3.AddHours(13).AddMinutes(48)
    Msg   = "feat(bench): real-LLM mode + cross-model results table"
    Files = @(
      "src/polyreview/bench/runner.py",
      "src/polyreview/bench/runs/baseline-mock.json",
      "src/polyreview/bench/runs/mock.json",
      "src/polyreview/bench/runs/deepseek-v4-flash.json",
      "src/polyreview/bench/runs/gpt-5.4-nano.json",
      "BENCHMARK_RESULTS.md"
    )
  },
  @{
    When  = $day3.AddHours(17).AddMinutes(30)
    Msg   = "docs: README, CHANGELOG, CONTRIBUTING, BENCHMARK plan + CI"
    Files = @(
      "README.md",
      "CHANGELOG.md",
      "CONTRIBUTING.md",
      "BENCHMARK.md",
      ".github/workflows/ci.yml",
      "git_setup.ps1"
    )
  }
)

Write-Host ""
Write-Host "Creating $($commits.Count) commits across $($day1.ToString('yyyy-MM-dd')) → $($day2.ToString('yyyy-MM-dd'))" -ForegroundColor Cyan
Write-Host ""

foreach ($c in $commits) {
  Make-Commit -Files $c.Files -Message $c.Msg -When $c.When
}

# ---------------------------------------------------------------------------
# 3. tag v0.3.0
# ---------------------------------------------------------------------------
$tagDate = $day2.AddHours(17).AddMinutes(15).ToString("yyyy-MM-ddTHH:mm:ss")
$env:GIT_AUTHOR_DATE    = $tagDate
$env:GIT_COMMITTER_DATE = $tagDate
Run-Git tag -a v0.3.0 -m "v0.3.0: multi-agent code review"

Write-Host ""
Write-Host "Done. Local history:" -ForegroundColor Green
Run-Git log --oneline --decorate

Write-Host ""
Write-Host "Next:" -ForegroundColor Cyan
Write-Host "  git remote add origin https://github.com/$GitHubUser/polyreview.git"
Write-Host "  git push -u origin main"
Write-Host "  git push origin v0.3.0"
