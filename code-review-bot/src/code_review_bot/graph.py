from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Config

log = logging.getLogger(__name__)


class GraphRequiredError(RuntimeError):
    pass


@dataclass
class GraphResult:
    status: str
    brief: str = ""
    error: str = ""
    command: str = "code-review-graph"


def _run(args: list[str], cwd: Path, timeout: int) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)


def build_graph(cfg: Config, workspace: Path, base_sha: str) -> GraphResult:
    if cfg.graph_mode == "off":
        return GraphResult(status="off", error="GRAPH_MODE=off")
    binary = shutil.which("code-review-graph")
    if not binary:
        message = "code-review-graph is not installed"
        if cfg.graph_mode == "required":
            raise GraphRequiredError(message)
        log.warning("graph unavailable: %s", message)
        return GraphResult(status="unavailable", error=message)

    if cfg.graph_mcp == "on":
        log.warning("GRAPH_MCP=on is not implemented in v1; using the graph brief only")

    try:
        code, out, err = _run([binary, "build"], workspace, cfg.graph_timeout)
        if code != 0:
            message = (err or out or f"exit {code}")[:800]
            if cfg.graph_mode == "required":
                raise GraphRequiredError(message)
            return GraphResult(status="unavailable", error=message)
        brief = ""
        code, out, err = _run(
            [binary, "detect-changes", "--brief", "--base", base_sha],
            workspace,
            cfg.graph_timeout,
        )
        if code == 0:
            brief = (out or "").strip()[:8000]
        else:
            log.warning("graph brief failed: %s", (err or out)[:400])
        return GraphResult(status="built" if brief else "partial", brief=brief, error="")
    except GraphRequiredError:
        raise
    except Exception as exc:  # noqa: BLE001
        if cfg.graph_mode == "required":
            raise GraphRequiredError(str(exc)) from exc
        return GraphResult(status="unavailable", error=str(exc))
