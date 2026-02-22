"""OpenClaw backend — invokes OpenClaw CLI with workspace access to the vault."""

from __future__ import annotations

import asyncio
import os

from ..config import OpenClawBackendConfig
from ..utils import get_logger
from . import BackendResult, BaseBackend

log = get_logger(__name__)


class OpenClawBackend(BaseBackend):
    def __init__(self, config: OpenClawBackendConfig, env_overrides: dict[str, str] | None = None) -> None:
        self.config = config
        self.env_overrides = env_overrides or {}

    async def process(
        self,
        prompt: str,
        vault_path: str,
    ) -> BackendResult:
        cmd = [self.config.command, "agent", *self.config.args,
               "--agent", "alfred",
               "--message", prompt, "--local", "--json"]

        cwd = self.config.workspace_mount or vault_path

        log.info(
            "openclaw.dispatching",
            command=self.config.command,
            cwd=cwd,
            timeout=self.config.timeout,
        )

        try:
            env = {**os.environ, **self.env_overrides}
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
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
        return BackendResult(success=True, summary=raw.strip())
