"""Backend base class and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..utils import get_logger

log = get_logger(__name__)


@dataclass
class BackendResult:
    """Result from agent extraction invocation."""
    success: bool = False
    summary: str = ""
    files_changed: list[str] = field(default_factory=list)


def build_extraction_prompt(
    skill_text: str,
    vault_path: str,
    project_name: str | None,
    project_description: str,
    existing_learns_formatted: str,
    source_records_formatted: str,
) -> str:
    """Assemble the full prompt sent to any backend for extraction."""
    project_section = f"**{project_name}** — {project_description}" if project_name else "Ungrouped records (no specific project)"

    return f"""{skill_text}

---

## Vault Location

The vault is at: `{vault_path}`

All file paths are relative to this root. When creating files, use absolute paths
(e.g. `{vault_path}/decision/Decision Title.md`).

---

## Project Context

{project_section}

---

## Existing Learning Records for This Project

(so you know what's already been extracted — DO NOT duplicate these)

{existing_learns_formatted}

---

## Source Records to Distill

{source_records_formatted}

---

Read these source records. Extract any latent:
- **Assumptions** — beliefs the team is operating on
- **Decisions** — choices made but not formally recorded
- **Constraints** — limits mentioned (regulatory, budget, timeline, technical)
- **Contradictions** — conflicting information between records
- **Synthesis** — patterns emerging across multiple records

For each learning found, create the appropriate record file in the vault.
Link back to source records via `based_on`, `cluster_sources`, `source`, etc.

When done, output a structured summary:
- CREATED: count by type (assumption: N, decision: N, etc.)

Then list each action taken, one per line:
CREATED | learn_type | file_path | detail"""


def format_existing_learns(learns: list) -> str:
    """Format existing learn records for dedup context."""
    if not learns:
        return "(No existing learning records for this project.)"

    lines: list[str] = []
    for rec in learns:
        lines.append(f"### {rec.rel_path}")
        lines.append(f"- Type: {rec.record_type}")
        lines.append(f"- Status: {rec.frontmatter.get('status', 'unknown')}")
        # Show first 200 chars of body for context
        body_preview = rec.body[:200].strip()
        if body_preview:
            lines.append(f"- Preview: {body_preview}")
        lines.append("")

    return "\n".join(lines)


def format_source_records(candidates: list) -> str:
    """Format source records for the agent prompt."""
    lines: list[str] = []
    for sc in candidates:
        rec = sc.record
        lines.append(f"### {rec.rel_path} (score: {sc.score:.2f})")
        lines.append(f"- Type: {rec.record_type}")
        lines.append(f"- Wikilinks: {', '.join(rec.wikilinks[:10])}")
        lines.append(f"```")
        lines.append(rec.body[:2000])  # cap body length in prompt
        lines.append(f"```")
        lines.append("")

    return "\n".join(lines)


class BaseBackend(ABC):
    """Abstract base for all agent backends."""

    @abstractmethod
    async def process(
        self,
        prompt: str,
        vault_path: str,
    ) -> BackendResult:
        """Send extraction prompt to the agent and return result."""
        ...
