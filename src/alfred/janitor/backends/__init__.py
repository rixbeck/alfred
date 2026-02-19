"""Backend base class and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..issues import Issue
from ..utils import get_logger

log = get_logger(__name__)


@dataclass
class BackendResult:
    """Result from agent fix invocation."""
    success: bool = False
    summary: str = ""
    files_changed: list[str] = field(default_factory=list)


def build_sweep_prompt(
    skill_text: str,
    issue_report: str,
    affected_records: str,
    vault_path: str,
) -> str:
    """Assemble the full prompt sent to any backend for fix mode."""
    return f"""{skill_text}

---

## Vault Location

The vault is at: `{vault_path}`

All file paths are relative to this root. When modifying files, use absolute paths
(e.g. `{vault_path}/person/John Smith.md`).

---

## Issue Report

The following issues were detected by the structural scanner. Fix what you can,
flag what requires human judgment.

{issue_report}

---

## Affected Records

{affected_records}

---

Fix the issues listed above. For each file:
1. Read the file
2. Apply the appropriate fix
3. If the fix requires human judgment, add a `janitor_note` frontmatter field instead

When done, output a structured summary:
- FIXED: count
- FLAGGED: count (janitor_note added)
- SKIPPED: count (no action needed)
- DELETED: count (garbage removed)

Then list each action taken, one per line:
ACTION | file_path | issue_code | detail"""


def build_issue_report(issues: list[Issue]) -> str:
    """Format issues into a readable report for the agent."""
    if not issues:
        return "No issues found."

    lines: list[str] = []
    # Group by file
    by_file: dict[str, list[Issue]] = {}
    for issue in issues:
        by_file.setdefault(issue.file, []).append(issue)

    for filepath in sorted(by_file.keys()):
        file_issues = by_file[filepath]
        lines.append(f"### {filepath}")
        for issue in file_issues:
            lines.append(
                f"- **{issue.code.value}** [{issue.severity.value}] {issue.message}"
            )
            if issue.detail:
                lines.append(f"  Detail: {issue.detail}")
            if issue.suggested_fix:
                lines.append(f"  Suggested fix: {issue.suggested_fix}")
        lines.append("")

    return "\n".join(lines)


class BaseBackend(ABC):
    """Abstract base for all agent backends."""

    @abstractmethod
    async def process(
        self,
        skill_text: str,
        issue_report: str,
        affected_records: str,
        vault_path: str,
    ) -> BackendResult:
        """Send issue report to the agent and return fix summary."""
        ...
