from __future__ import annotations

import os
import sys
from pathlib import Path

from code_review_bot.config import Config
from code_review_bot.graph import build_graph

from .conftest import make_fixture_repo


def test_graph_build_and_brief(tmp_path: Path, monkeypatch) -> None:
    repo, base, _ = make_fixture_repo(tmp_path)
    scripts = str(Path(sys.executable).parent)
    monkeypatch.setenv("PATH", scripts + os.pathsep + os.environ.get("PATH", ""))
    secret = tmp_path / "secret"
    secret.write_text("x", encoding="utf-8")
    cfg = Config.from_env(
        {
            "PR_URL": "https://github.com/acme/service/pull/1",
            "LLM_BASE_URL": "https://llm.example/v1",
            "LLM_API_KEY_FILE": str(secret),
            "GITHUB_TOKEN_FILE": str(secret),
            "LLM_MODEL": "m",
            "GRAPH_MODE": "required",
        }
    )
    result = build_graph(cfg, repo, base)
    assert result.status in {"built", "partial"}
    assert result.brief
    assert "risk" in result.brief.lower() or "analyzed" in result.brief.lower()
