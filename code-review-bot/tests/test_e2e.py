from __future__ import annotations

import json
from pathlib import Path

from code_review_bot.config import Config
from code_review_bot.review import run_review

from .conftest import make_fixture_repo, write_fake_responses
from .fake_github import FakeGitHub


def _env(tmp_path: Path, fake: FakeGitHub, repo: Path) -> dict[str, str]:
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "llm").write_text("test-llm-key", encoding="utf-8")
    (secrets / "gh").write_text("test-gh-token", encoding="utf-8")
    return {
        "PR_URL": "https://github.com/acme/service/pull/1",
        "GITHUB_API_URL": fake.url,
        "GITHUB_TOKEN_FILE": str(secrets / "gh"),
        "LLM_BASE_URL": "https://llm.example/v1",
        "LLM_API_KEY_FILE": str(secrets / "llm"),
        "LLM_MODEL_SENIOR": "fast",
        "LLM_MODEL_PRINCIPAL": "strong",
        "LLM_MODEL_SECURITY": "strong",
        "ALLOW_INSECURE_LLM": "true",
        "GRAPH_MODE": "off",
        "CRB_WORKSPACE": str(repo),
        "CRB_BASE_REV": "HEAD~1",
        "CRB_HEAD_REV": "HEAD",
        "CRB_FAKE_OPENCODE": "1",
        "CRB_FAKE_DIR": str(tmp_path / "fake"),
        "OUTPUT_DIR": str(tmp_path / "out"),
        "COMMENT_STYLE": "human",
        "MAX_COMMENT_WORDS": "120",
        "SECURITY_PASS": "auto",
    }


def test_fake_end_to_end_and_skip(tmp_path: Path) -> None:
    repo_path, base, head = make_fixture_repo(tmp_path)
    write_fake_responses(tmp_path / "fake")
    with FakeGitHub() as fake:
        env = _env(tmp_path, fake, repo_path)
        cfg = Config.from_env(env)
        assert run_review(cfg) == 0
        assert len(fake.reviews) == 1
        assert len(fake.reviews[0]["comments"]) == 2
        assert any("```suggestion" in c["body"] for c in fake.reviews[0]["comments"])
        assert any(label["name"] == "AI Reviewed" for label in fake.pull["labels"])
        assert len(fake.issue_comments) == 1
        summary = fake.issue_comments[0]["body"]
        assert "AI Reviewed" in summary
        assert "tokens" in summary
        assert "2 posted" in summary
        assert (tmp_path / "out" / "review.json").exists()

        # Same head + label: skip without new comments.
        assert run_review(Config.from_env(env)) == 0
        assert len(fake.reviews) == 1
        assert len(fake.issue_comments) == 1

        # Forced re-review: remove/re-add label, do not duplicate inline comments.
        forced = dict(env)
        forced["FORCE"] = "true"
        assert run_review(Config.from_env(forced)) == 0
        assert len(fake.reviews) == 1
        assert any(label["name"] == "AI Reviewed" for label in fake.pull["labels"])


def test_dry_run_writes_without_posting(tmp_path: Path) -> None:
    repo_path, base, head = make_fixture_repo(tmp_path)
    write_fake_responses(tmp_path / "fake")
    with FakeGitHub() as fake:
        env = _env(tmp_path, fake, repo_path)
        env["DRY_RUN"] = "true"
        assert run_review(Config.from_env(env)) == 0
        assert not fake.reviews
        assert not fake.issue_comments
        assert not fake.labels
        assert not fake.pull["labels"]
        assert (tmp_path / "out" / "review.json").exists()
        report = json.loads((tmp_path / "out" / "review.json").read_text(encoding="utf-8"))
        assert report["summary"]["issues"]["posted"] == 2
