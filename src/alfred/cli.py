"""Top-level argparse CLI dispatcher for Alfred."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


def _load_unified_config(config_path: str) -> dict[str, Any]:
    """Load and return raw unified config dict."""
    path = Path(config_path)
    if not path.exists():
        print(f"Config file not found: {path}")
        print("Run `alfred quickstart` to create one.")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_base_dir() -> Path:
    """Return the monorepo root (where skills/ and scaffold/ live)."""
    # Walk up from this file: src/alfred/cli.py -> src/alfred -> src -> alfred/
    return Path(__file__).resolve().parent.parent.parent


def _setup_logging_from_config(raw: dict[str, Any]) -> None:
    """Set up logging from the unified config's logging section."""
    log_cfg = raw.get("logging", {})
    level = log_cfg.get("level", "INFO")
    log_dir = log_cfg.get("dir", "./data")
    # Each tool sets up its own logging, but we set a base level
    from alfred.curator.utils import setup_logging
    setup_logging(level=level, log_file=f"{log_dir}/alfred.log")


# --- Subcommand handlers ---

def cmd_quickstart(args: argparse.Namespace) -> None:
    from alfred.quickstart import run_quickstart
    run_quickstart()


def cmd_up(args: argparse.Namespace) -> None:
    raw = _load_unified_config(args.config)
    _setup_logging_from_config(raw)
    from alfred.orchestrator import run_all
    run_all(raw, only=args.only, base_dir=_get_base_dir())


def cmd_status(args: argparse.Namespace) -> None:
    raw = _load_unified_config(args.config)

    print("=" * 60)
    print("ALFRED STATUS")
    print("=" * 60)

    # Curator status
    print("\n--- Curator ---")
    try:
        from alfred.curator.config import load_from_unified as curator_cfg
        cfg = curator_cfg(raw)
        from alfred.curator.state import StateManager
        sm = StateManager(cfg.state.path)
        sm.load()
        print(f"  Processed files: {len(sm.state.processed)}")
        print(f"  Last run: {sm.state.last_run or 'never'}")
    except Exception as e:
        print(f"  (unavailable: {e})")

    # Janitor status
    print("\n--- Janitor ---")
    try:
        from alfred.janitor.config import load_from_unified as janitor_cfg
        cfg = janitor_cfg(raw)
        from alfred.janitor.state import JanitorState
        st = JanitorState(cfg.state.path, cfg.state.max_sweep_history)
        st.load()
        files_with_issues = sum(1 for fs in st.files.values() if fs.open_issues)
        print(f"  Tracked files: {len(st.files)}")
        print(f"  Files with issues: {files_with_issues}")
        print(f"  Sweeps recorded: {len(st.sweeps)}")
    except Exception as e:
        print(f"  (unavailable: {e})")

    # Distiller status
    print("\n--- Distiller ---")
    try:
        from alfred.distiller.config import load_from_unified as distiller_cfg
        cfg = distiller_cfg(raw)
        from alfred.distiller.state import DistillerState
        st = DistillerState(cfg.state.path, cfg.state.max_run_history)
        st.load()
        total_learns = sum(len(fs.learn_records_created) for fs in st.files.values())
        print(f"  Tracked source files: {len(st.files)}")
        print(f"  Learn records created: {total_learns}")
        print(f"  Runs recorded: {len(st.runs)}")
    except Exception as e:
        print(f"  (unavailable: {e})")

    # Surveyor status
    print("\n--- Surveyor ---")
    try:
        from alfred.surveyor.config import load_from_unified as surveyor_cfg
        cfg = surveyor_cfg(raw)
        from alfred.surveyor.state import PipelineState
        st = PipelineState(cfg.state.path)
        st.load()
        print(f"  Tracked files: {len(st.files)}")
        print(f"  Clusters: {len(st.clusters)}")
        print(f"  Last run: {st.last_run or 'never'}")
    except Exception as e:
        print(f"  (unavailable: {e})")

    print()


def cmd_curator(args: argparse.Namespace) -> None:
    import asyncio
    raw = _load_unified_config(args.config)
    _setup_logging_from_config(raw)
    from alfred.curator.config import load_from_unified
    config = load_from_unified(raw)
    from alfred.curator.daemon import run
    try:
        asyncio.run(run(config, _get_base_dir()))
    except KeyboardInterrupt:
        print("\nStopped.")


def cmd_janitor(args: argparse.Namespace) -> None:
    raw = _load_unified_config(args.config)
    _setup_logging_from_config(raw)
    from alfred.janitor.config import load_from_unified
    config = load_from_unified(raw)
    base_dir = _get_base_dir()

    from alfred.janitor import cli as jcli
    subcmd = args.janitor_cmd

    if subcmd == "scan":
        jcli.cmd_scan(config, base_dir)
    elif subcmd == "fix":
        jcli.cmd_fix(config, base_dir)
    elif subcmd == "watch":
        jcli.cmd_watch(config, base_dir)
    elif subcmd == "status":
        jcli.cmd_status(config)
    elif subcmd == "history":
        jcli.cmd_history(config, limit=args.limit)
    elif subcmd == "ignore":
        jcli.cmd_ignore(config, args.file, reason=args.reason)
    else:
        print(f"Unknown janitor subcommand: {subcmd}")
        sys.exit(1)


def cmd_distiller(args: argparse.Namespace) -> None:
    raw = _load_unified_config(args.config)
    _setup_logging_from_config(raw)
    from alfred.distiller.config import load_from_unified
    config = load_from_unified(raw)
    base_dir = _get_base_dir()

    from alfred.distiller import cli as dcli
    subcmd = args.distiller_cmd

    if subcmd == "scan":
        dcli.cmd_scan(config, base_dir, project=args.project)
    elif subcmd == "run":
        dcli.cmd_run(config, base_dir, project=args.project)
    elif subcmd == "watch":
        dcli.cmd_watch(config, base_dir)
    elif subcmd == "status":
        dcli.cmd_status(config)
    elif subcmd == "history":
        dcli.cmd_history(config, limit=args.limit)
    else:
        print(f"Unknown distiller subcommand: {subcmd}")
        sys.exit(1)


def cmd_surveyor(args: argparse.Namespace) -> None:
    raw = _load_unified_config(args.config)
    _setup_logging_from_config(raw)

    try:
        from alfred.surveyor.config import load_from_unified
    except ImportError:
        print("Surveyor dependencies not installed.")
        print("Install with: pip install -e '.[all]'")
        sys.exit(1)

    config = load_from_unified(raw)
    from alfred.surveyor.daemon import Daemon
    daemon = Daemon(config)
    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\nStopped.")


# --- Argument parser ---

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alfred",
        description="Alfred — unified vault operations suite",
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to config.yaml (default: config.yaml)",
    )
    sub = parser.add_subparsers(dest="command")

    # quickstart
    sub.add_parser("quickstart", help="Interactive setup wizard")

    # up
    up_parser = sub.add_parser("up", help="Start all daemons")
    up_parser.add_argument(
        "--only", type=str, default=None,
        help="Comma-separated list of tools to start (e.g. curator,janitor)",
    )

    # status
    sub.add_parser("status", help="Show status from all tools")

    # curator
    sub.add_parser("curator", help="Start curator daemon")

    # janitor
    jan = sub.add_parser("janitor", help="Vault janitor subcommands")
    jan_sub = jan.add_subparsers(dest="janitor_cmd")
    jan_sub.add_parser("scan", help="Run structural scan")
    jan_sub.add_parser("fix", help="Scan + agent fix")
    jan_sub.add_parser("watch", help="Daemon mode")
    jan_sub.add_parser("status", help="Show sweep status")
    jan_hist = jan_sub.add_parser("history", help="Show sweep history")
    jan_hist.add_argument("--limit", type=int, default=10)
    jan_ignore = jan_sub.add_parser("ignore", help="Ignore a file")
    jan_ignore.add_argument("file", help="Relative file path to ignore")
    jan_ignore.add_argument("--reason", default="", help="Reason for ignoring")

    # distiller
    dist = sub.add_parser("distiller", help="Vault distiller subcommands")
    dist_sub = dist.add_subparsers(dest="distiller_cmd")
    dist_scan = dist_sub.add_parser("scan", help="Scan for candidates")
    dist_scan.add_argument("--project", "-p", default=None, help="Filter by project name")
    dist_run = dist_sub.add_parser("run", help="Scan + extract")
    dist_run.add_argument("--project", "-p", default=None, help="Filter by project name")
    dist_sub.add_parser("watch", help="Daemon mode")
    dist_sub.add_parser("status", help="Show extraction status")
    dist_hist = dist_sub.add_parser("history", help="Show run history")
    dist_hist.add_argument("--limit", type=int, default=10)

    # surveyor
    sub.add_parser("surveyor", help="Start surveyor pipeline")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "quickstart": cmd_quickstart,
        "up": cmd_up,
        "status": cmd_status,
        "curator": cmd_curator,
        "janitor": cmd_janitor,
        "distiller": cmd_distiller,
        "surveyor": cmd_surveyor,
    }

    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)
