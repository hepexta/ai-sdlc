from __future__ import annotations

import os
import subprocess
from pathlib import Path

from code_review_bot.config import Config
from code_review_bot.github import PullRequest
from code_review_bot.gitops import prepare_workspace

from .conftest import make_fixture_repo


def _git(cwd: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update({"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@e", "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@e"})
    return subprocess.run(["git", *args], cwd=str(cwd), env=env, capture_output=True, text=True, check=True).stdout.strip()


def test_prepare_workspace_clones_pull_ref(tmp_path: Path) -> None:
    repo, base, head = make_fixture_repo(tmp_path)
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "clone", "--bare", str(repo), str(bare)], check=True, capture_output=True)
    _git(bare, "update-ref", "refs/heads/master", base)
    _git(bare, "update-ref", "refs/pull/1/head", head)
    secret = tmp_path / "secret"
    secret.write_text("x", encoding="utf-8")
    cfg = Config.from_env(
        {
            "PR_URL": "https://github.com/acme/service/pull/1",
            "LLM_BASE_URL": "https://llm.example/v1",
            "LLM_API_KEY_FILE": str(secret),
            "GITHUB_TOKEN_FILE": str(secret),
            "LLM_MODEL": "m",
            "GITHUB_CLONE_URL": str(bare),
        }
    )
    pr = PullRequest(
        owner="acme",
        repo="service",
        number=1,
        title="t",
        body="",
        state="open",
        base_ref="master",
        base_sha=base,
        head_sha=head,
    )
    ws = prepare_workspace(cfg, pr)
    try:
        assert ws.head_sha == head
        assert "src/main/java/com/acme/OrderController.java" in ws.diff.files
        assert ws.temporary is True
    finally:
        ws.cleanup()
