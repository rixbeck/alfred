"""Backend base class and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..utils import get_logger

log = get_logger(__name__)


@dataclass
class BackendResult:
    """Result from a backend dispatch.

    The agent writes files directly — we just track success and what changed.
    """

    success: bool = False
    summary: str = ""
    files_changed: list[str] = field(default_factory=list)


def build_prompt(
    inbox_content: str,
    skill_text: str,
    vault_context: str,
    inbox_filename: str,
    vault_path: str,
) -> str:
    """Assemble the full prompt sent to any backend.

    The agent has direct filesystem access to the vault.
    """
    return f"""{skill_text}

---

## Vault Location

The vault is at: `{vault_path}`

All file paths are relative to this root. When creating files, use absolute paths
(e.g. `{vault_path}/person/John Smith.md`).

---

## Current Vault Context

{vault_context}

---

## Inbox File to Process

**Filename:** {inbox_filename}
**Full path:** `{vault_path}/inbox/{inbox_filename}`

```
{inbox_content}
```

---

Process this inbox file now. Read existing vault records as needed, then create/update the appropriate records directly in the vault. When done, output a brief summary of what you created or modified."""


class BaseBackend(ABC):
    """Abstract base for all agent backends."""

    @abstractmethod
    async def process(
        self,
        inbox_content: str,
        skill_text: str,
        vault_context: str,
        inbox_filename: str,
        vault_path: str,
    ) -> BackendResult:
        """Send inbox content to the agent and return result summary."""
        ...
