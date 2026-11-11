from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from code_review_bot.config import Config
from code_review_bot.effort import choose_effort
from code_review_bot.opencode_runner import AgentSpec, OpenCodeRunner, parse_json_object

from .conftest import make_fixture_repo
from .fake_llm import FakeLLM


@pytest.mark.skipif(shutil.which("opencode") is None, reason="opencode is not installed")
def test_real_opencode_v1_config_and_events(tmp_path: Path) -> None:
    repo, base, head = make_fixture_repo(tmp_path)
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "llm").write_text("test-key", encoding="utf-8")
    (secrets / "gh").write_text("test-token", encoding="utf-8")
    output = '{"findings": []}'
    with FakeLLM(output) as llm:
        env = {
            "PR_URL": "https://github.com/acme/service/pull/1",
            "GITHUB_TOKEN_FILE": str(secrets / "gh"),
            "LLM_BASE_URL": llm.url,
            "LLM_API_KEY_FILE": str(secrets / "llm"),
            "LLM_MODEL_SENIOR": "fast",
            "LLM_MODEL_PRINCIPAL": "strong",
            "ALLOW_INSECURE_LLM": "true",
            "CRB_WORKSPACE": str(repo),
            "CRB_BASE_REV": base,
            "CRB_HEAD_REV": head,
            "GRAPH_MODE": "off",
        }
        cfg = Config.from_env(env)
        plan = choose_effort(cfg, 10, 2)
        runner = OpenCodeRunner(cfg, repo, plan)
        runner.prepare()
        brief = repo / "BRIEF.md"
        brief.write_text("Review this PR. Return JSON.", encoding="utf-8")
        spec = AgentSpec(
            name="senior-reviewer",
            role="senior",
            model="fast",
            effort=plan.senior,
            prompt="",
        )
        result = runner.run(spec, brief)
        assert parse_json_object(result.text) == {"findings": []}
        assert result.usage.input_tokens == 100
        assert result.usage.output_tokens == 20
        assert llm.requests
