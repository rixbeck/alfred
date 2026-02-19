"""OpenClaw backend — invokes OpenClaw CLI with workspace access to the vault."""

from __future__ import annotations

import asyncio

from ..config import OpenClawBackendConfig
from ..utils import get_logger
from . import BackendResult, BaseBackend, build_prompt

log = get_logger(__name__)


class OpenClawBackend(BaseBackend):
    def __init__(self, config: OpenClawBackendConfig) -> None:
        self.config = config

    async def process(
        self,
        inbox_content: str,
        skill_text: str,
        vault_context: str,
        inbox_filename: str,
        vault_path: str,
    ) -> BackendResult:
        prompt = build_prompt(inbox_content, skill_text, vault_context, inbox_filename, vault_path)

        cmd = [self.config.command, *self.config.args]

        # Mount the vault as workspace
        workspace = self.config.workspace_mount or vault_path
        cmd.extend(["--workspace", workspace])

        # Prompt as last argument
        cmd.append(prompt)

        log.info(
            "openclaw.dispatching",
            command=self.config.command,
            workspace=workspace,
            timeout=self.config.timeout,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout,
            )
        except asyncio.TimeoutError:
            log.error("openclaw.timeout", timeout=self.config.timeout)
            return BackendResult(success=False, summary="ERROR: timeout")
        except FileNotFoundError:
            log.error("openclaw.command_not_found", command=self.config.command)
            return BackendResult(
                success=False,
                summary=f"ERROR: command not found: {self.config.command}",
            )

        raw = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            log.warning(
                "openclaw.nonzero_exit", code=proc.returncode, stderr=err[:500]
            )
            return BackendResult(
                success=False,
                summary=f"Exit code {proc.returncode}: {err[:500]}",
            )

        log.info("openclaw.completed", summary_length=len(raw))
        return BackendResult(
            success=True,
            summary=raw.strip(),
        )
