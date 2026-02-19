"""Entry point — asyncio.run + signal handling."""

from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

from .config import load_config
from .daemon import Daemon
from .utils import setup_logging


def main() -> None:
    config_path = Path(__file__).resolve().parent.parent.parent / "config.yaml"
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])

    cfg = load_config(config_path)
    setup_logging(level=cfg.logging.level, log_file=cfg.logging.file)

    daemon = Daemon(cfg)

    loop = asyncio.new_event_loop()

    def _shutdown(sig: signal.Signals) -> None:
        daemon.request_shutdown()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _shutdown, sig)
    else:
        # On Windows, use signal.signal for SIGINT (Ctrl+C)
        signal.signal(signal.SIGINT, lambda s, f: _shutdown(s))

    try:
        loop.run_until_complete(daemon.run())
    except KeyboardInterrupt:
        daemon.request_shutdown()
        loop.run_until_complete(daemon.shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
