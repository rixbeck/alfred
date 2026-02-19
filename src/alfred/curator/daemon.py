"""Main daemon loop — orchestrates the full inbox processing pipeline.

Architecture: agent-writes-directly. The agent (Claude Code, Zo, OpenClaw) has
full vault access and creates/modifies files directly. Curator orchestrates:
detect inbox → snapshot vault → invoke agent → diff vault → mark processed → track state.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from .backends import BaseBackend
from .backends.cli import ClaudeBackend
from .backends.http import ZoBackend
from .backends.openclaw import OpenClawBackend
from .config import CuratorConfig
from .context import build_vault_context
from .state import StateManager
from .utils import get_logger
from .watcher import InboxWatcher
from .writer import diff_vault, mark_processed, snapshot_vault

log = get_logger(__name__)


def _load_skill(base_dir: Path) -> str:
    """Load SKILL.md and all reference templates into a single text block."""
    skill_path = base_dir / "skills" / "vault-curator" / "SKILL.md"
    if not skill_path.exists():
        log.warning("daemon.skill_not_found", path=str(skill_path))
        return ""

    parts: list[str] = [skill_path.read_text(encoding="utf-8")]

    # Inline all reference templates so the agent has the full schema
    refs_dir = base_dir / "skills" / "vault-curator" / "references"
    if refs_dir.is_dir():
        for ref_file in sorted(refs_dir.glob("*.md")):
            content = ref_file.read_text(encoding="utf-8")
            parts.append(f"\n---\n### Reference Template: {ref_file.name}\n```\n{content}\n```")

    return "\n".join(parts)


def _create_backend(config: CuratorConfig) -> BaseBackend:
    """Instantiate the configured backend."""
    backend_name = config.agent.backend
    if backend_name == "claude":
        return ClaudeBackend(config.agent.claude)
    elif backend_name == "zo":
        return ZoBackend(config.agent.zo)
    elif backend_name == "openclaw":
        return OpenClawBackend(config.agent.openclaw)
    else:
        raise ValueError(f"Unknown backend: {backend_name}")


async def _process_file(
    inbox_file: Path,
    backend: BaseBackend,
    skill_text: str,
    config: CuratorConfig,
    state_mgr: StateManager,
) -> None:
    """Process a single inbox file through the full pipeline."""
    filename = inbox_file.name
    log.info("daemon.processing", file=filename)

    # Read inbox content
    try:
        inbox_content = inbox_file.read_text(encoding="utf-8")
    except Exception as e:
        log.error("daemon.read_failed", file=filename, error=str(e))
        return

    # Build vault context
    vault_context = build_vault_context(
        config.vault.vault_path,
        ignore_dirs=config.vault.ignore_dirs,
    )
    context_text = vault_context.to_prompt_text()

    # Snapshot vault before agent runs
    before = snapshot_vault(config.vault.vault_path, ignore_dirs=config.vault.ignore_dirs)

    # Invoke agent — it writes files directly
    result = await backend.process(
        inbox_content=inbox_content,
        skill_text=skill_text,
        vault_context=context_text,
        inbox_filename=filename,
        vault_path=str(config.vault.vault_path),
    )

    # Snapshot vault after agent runs and diff
    after = snapshot_vault(config.vault.vault_path, ignore_dirs=config.vault.ignore_dirs)
    files_created, files_modified = diff_vault(before, after)

    if not result.success:
        log.error("daemon.agent_failed", file=filename, summary=result.summary[:500])

    if not files_created and not files_modified:
        log.warning("daemon.no_changes", file=filename)

    # Mark processed and move
    mark_processed(inbox_file, config.vault.processed_path)

    # Update state
    state_mgr.state.mark_processed(
        filename=filename,
        inbox_path=str(inbox_file),
        files_created=files_created,
        files_modified=files_modified,
        backend_used=config.agent.backend,
    )
    state_mgr.save()

    log.info(
        "daemon.completed",
        file=filename,
        success=result.success,
        created=len(files_created),
        modified=len(files_modified),
    )


async def run(config: CuratorConfig, base_dir: Path) -> None:
    """Main daemon entry point."""
    log.info("daemon.starting", backend=config.agent.backend)

    # Load skill text
    skill_text = _load_skill(base_dir)
    if not skill_text:
        log.warning("daemon.no_skill", msg="Running without SKILL.md — agent may not produce correct output")

    # Init backend
    backend = _create_backend(config)

    # Init state
    state_mgr = StateManager(config.state.path)
    state_mgr.load()

    # Init watcher
    watcher = InboxWatcher(
        inbox_path=config.vault.inbox_path,
        debounce_seconds=config.watcher.debounce_seconds,
    )

    # Startup scan for unprocessed files
    unprocessed = watcher.full_scan(
        state_processed=set(state_mgr.state.processed.keys()),
    )
    for inbox_file in unprocessed:
        await _process_file(inbox_file, backend, skill_text, config, state_mgr)

    # Start watching
    watcher.start()
    log.info("daemon.watching", inbox=str(config.vault.inbox_path))

    try:
        while True:
            await asyncio.sleep(config.watcher.poll_interval)
            ready = watcher.collect_ready()
            for inbox_file in ready:
                # Skip if already processed (race condition guard)
                if state_mgr.state.is_processed(inbox_file.name):
                    continue
                if not inbox_file.exists():
                    continue
                await _process_file(inbox_file, backend, skill_text, config, state_mgr)
    finally:
        watcher.stop()
        log.info("daemon.stopped")
