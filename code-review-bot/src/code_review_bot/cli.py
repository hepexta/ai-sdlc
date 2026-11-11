from __future__ import annotations

import argparse
import json
import logging
import sys

from . import __version__
from .config import Config, ConfigError
from .review import run_review


def _setup_logging(level: str, fmt: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
        if fmt != "json"
        else '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pr", help="PR URL or owner/repo#number")
    parser.add_argument("--dry-run", action="store_true", default=None, help="render and write artifacts, post nothing")
    parser.add_argument("--force", action="store_true", default=None, help="override the AI Reviewed skip")
    parser.add_argument("--output", help="artifact directory")
    parser.add_argument("--workspace", help="existing git checkout (testing)")
    parser.add_argument("--base-rev", help="base revision for --workspace")
    parser.add_argument("--head-rev", help="head revision for --workspace")
    parser.add_argument("--fake-opencode", action="store_true", default=None, help="use fake agent responses")
    parser.add_argument("--fake-dir", help="directory with <agent>.json fake responses")
    parser.add_argument("--effort", choices=["auto", "low", "medium", "high"], help="manual effort override")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crb", description="AI-assisted Java/Python PR reviewer")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser("review", help="review one pull request")
    _common(review)

    validate = sub.add_parser("validate-config", help="validate and print redacted configuration")
    _common(validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = Config.from_env(
            pr_override=args.pr,
            dry_run=args.dry_run,
            force=args.force,
            output=args.output,
            log_level=args.log_level,
            workspace=args.workspace,
            base_rev=args.base_rev,
            head_rev=args.head_rev,
            fake_opencode=args.fake_opencode,
            fake_dir=args.fake_dir,
            effort=args.effort,
        )
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    _setup_logging(cfg.log_level, cfg.log_format)
    if args.command == "validate-config":
        print(json.dumps(cfg.redacted(), indent=2))
        return 0
    return run_review(cfg)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
