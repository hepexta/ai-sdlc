from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from .conftest import make_fixture_repo, write_fake_responses
from .fake_github import FakeGitHub
from .fake_llm import FakeLLM


def _docker_available() -> bool:
    return shutil.which("docker") is not None


@pytest.mark.skipif(not _docker_available(), reason="docker is not installed")
def test_docker_real_opencode_e2e(tmp_path: Path) -> None:
    repo, base, head = make_fixture_repo(tmp_path)
    fake_dir = tmp_path / "fake"
    write_fake_responses(fake_dir)
    texts = {
        "senior": (fake_dir / "senior-reviewer.json").read_text(encoding="utf-8"),
        "security": (fake_dir / "security-reviewer.json").read_text(encoding="utf-8"),
        "principal": (fake_dir / "principal-reviewer.json").read_text(encoding="utf-8"),
    }
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "llm_api_key").write_text("test-key", encoding="utf-8")
    (secrets / "github_token").write_text("test-token", encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()
    with FakeGitHub(host="0.0.0.0") as github, FakeLLM(
        "", texts=texts, host="0.0.0.0"
    ) as llm:
        cmd = [
            "docker",
            "run",
            "--rm",
            "--add-host=host.docker.internal:host-gateway",
            "-v",
            f"{repo}:/workspace/repo",
            "-v",
            f"{secrets}:/seed:ro",
            "-v",
            f"{output}:/out",
            "--tmpfs",
            "/run/secrets:rw,uid=10001,gid=10001,mode=700",
            "--entrypoint",
            "/bin/sh",
            "-e",
            "PR_URL=https://github.com/acme/service/pull/1",
            "-e",
            f"GITHUB_API_URL={github.container_url}",
            "-e",
            "GITHUB_TOKEN_FILE=/run/secrets/github_token",
            "-e",
            f"LLM_BASE_URL={llm.container_url}",
            "-e",
            "LLM_API_KEY_FILE=/run/secrets/llm_api_key",
            "-e",
            "LLM_MODEL_SENIOR=fast",
            "-e",
            "LLM_MODEL_PRINCIPAL=strong",
            "-e",
            "LLM_MODEL_SECURITY=strong",
            "-e",
            "ALLOW_INSECURE_LLM=true",
            "-e",
            "CRB_WORKSPACE=/workspace/repo",
            "-e",
            f"CRB_BASE_REV={base}",
            "-e",
            f"CRB_HEAD_REV={head}",
            "-e",
            "GRAPH_MODE=off",
            "-e",
            "OUTPUT_DIR=/out",
            "-e",
            "COMMENT_STYLE=human",
            "-e",
            "MAX_COMMENT_WORDS=120",
            "-e",
            "SECURITY_PASS=auto",
            "-e",
            "GIT_CONFIG_COUNT=1",
            "-e",
            "GIT_CONFIG_KEY_0=safe.directory",
            "-e",
            "GIT_CONFIG_VALUE_0=/workspace/repo",
            "code-review-bot:dev",
            "-c",
            "cp /seed/llm_api_key /run/secrets/llm_api_key && "
            "cp /seed/github_token /run/secrets/github_token && "
            "chmod 600 /run/secrets/llm_api_key /run/secrets/github_token && "
            "exec crb review",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=360)
        assert proc.returncode == 0, f"stdout={proc.stdout[-4000:]}\nstderr={proc.stderr[-4000:]}"
        assert github.reviews, "no review posted"
        assert len(github.reviews[0]["comments"]) == 2
        assert any(label["name"] == "AI Reviewed" for label in github.pull["labels"])
        assert (output / "review.json").exists()
        report = json.loads((output / "review.json").read_text(encoding="utf-8"))
        assert report["summary"]["label"]["applied"] is True
        assert report["summary"]["tokens"]["total"] > 0
