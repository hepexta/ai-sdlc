from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .diff import DiffView, parse_diff
from .github import PullRequest


class WorkspaceError(RuntimeError):
    pass


@dataclass
class Workspace:
    path: Path
    base_sha: str
    head_sha: str
    diff: DiffView
    temporary: bool = False
    standards_text: str = ""

    def cleanup(self) -> None:
        if self.temporary:
            shutil.rmtree(self.path, ignore_errors=True)

    def read_text(self, relative: str, limit: int = 200_000) -> str:
        path = (self.path / relative).resolve()
        if self.path.resolve() not in path.parents:
            return ""
        try:
            data = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return data[:limit]


def _run_git(args: list[str], cwd: Path, env: dict[str, str], timeout: int = 120) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise WorkspaceError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:500]}")
    return proc.stdout


def _snapshot_standards(path: Path) -> str:
    chunks: list[str] = []
    for name in ["AGENTS.md", "CLAUDE.md", "CONTEXT.md", "CONTRIBUTING.md", "CODING_STANDARDS.md"]:
        target = path / name
        if target.is_file():
            chunks.append(f"### {name}\n{target.read_text(encoding='utf-8', errors='replace')[:6000]}")
    text = "\n\n".join(chunks)
    if text:
        output = path / ".crb"
        output.mkdir(exist_ok=True)
        (output / "standards.md").write_text(text, encoding="utf-8")
    return text


def _quarantine(path: Path) -> None:
    quarantine = path / "quarantine"
    for relative in ["opencode.json", "opencode.jsonc", "AGENTS.md", "CLAUDE.md"]:
        target = path / relative
        if target.exists():
            quarantine.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(quarantine / relative))
    for relative in [".opencode", ".claude", ".agents"]:
        target = path / relative
        if target.exists():
            quarantine.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(quarantine / relative.replace(".", "")))
    for target in path.glob(".env*"):
        if target.name == ".env.example" or not target.is_file():
            continue
        quarantine.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(quarantine / target.name))


def prepare_workspace(cfg: Config, pr: PullRequest) -> Workspace:
    if cfg.workspace:
        path = cfg.workspace.resolve()
        if not (path / ".git").exists():
            raise WorkspaceError(f"workspace is not a git checkout: {path}")
        base = cfg.base_rev or "HEAD~1"
        head = cfg.head_rev or "HEAD"
        env = os.environ.copy()
        base_sha = _run_git(["rev-parse", base], path, env).strip()
        head_sha = _run_git(["rev-parse", head], path, env).strip()
        diff_text = _run_git(["diff", "--unified=40", f"{base}...{head}"], path, env)
        standards = _snapshot_standards(path)
        _quarantine(path)
        return Workspace(
            path=path,
            base_sha=base_sha,
            head_sha=head_sha,
            diff=parse_diff(diff_text),
            standards_text=standards,
        )

    path = Path(tempfile.mkdtemp(prefix="crb-workspace-"))
    try:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["CRB_GIT_TOKEN"] = cfg.github_token
        askpass = path / ".git-askpass"
        askpass.write_text(
            "#!/bin/sh\n"
            'case "$1" in\n'
            '  *Username*) echo "x-access-token" ;;\n'
            '  *Password*) echo "$CRB_GIT_TOKEN" ;;\n'
            "  *) echo \"\" ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        askpass.chmod(0o700)
        env["GIT_ASKPASS"] = str(askpass)
        _run_git(["init", "-q"], path, env)
        _run_git(
            ["remote", "add", "origin", cfg.github_clone_url],
            path,
            env,
        )
        _run_git(["config", "core.symlinks", "false"], path, env)
        _run_git(["config", "submodule.recurse", "false"], path, env)
        _run_git(
            ["fetch", "--depth=50", "origin", f"refs/pull/{cfg.pr.number}/head:refs/crb/head"],
            path,
            env,
        )
        _run_git(["checkout", "--detach", "refs/crb/head"], path, env)
        head_sha = _run_git(["rev-parse", "HEAD"], path, env).strip()
        base_branch = pr.base_ref or "main"
        base_ref = f"origin/{base_branch}"
        _run_git(
            ["fetch", "--depth=50", "origin", f"+refs/heads/{base_branch}:refs/remotes/{base_ref}"],
            path,
            env,
        )
        try:
            base_sha = _run_git(["merge-base", "HEAD", base_ref], path, env).strip()
        except WorkspaceError:
            _run_git(["fetch", "--deepen=200", "origin"], path, env)
            base_sha = _run_git(["merge-base", "HEAD", base_ref], path, env).strip()
        diff_text = _run_git(["diff", "--unified=40", f"{base_sha}...HEAD"], path, env)
        standards = _snapshot_standards(path)
        _quarantine(path)
        return Workspace(
            path=path,
            base_sha=base_sha,
            head_sha=head_sha,
            diff=parse_diff(diff_text),
            temporary=True,
            standards_text=standards,
        )
    except Exception:
        shutil.rmtree(path, ignore_errors=True)
        raise


def resolve_head(path: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(path), capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""
