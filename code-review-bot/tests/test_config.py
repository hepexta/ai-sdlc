from __future__ import annotations

from pathlib import Path

import pytest

from code_review_bot.config import Config, ConfigError, parse_pr_reference


def test_parse_pr_reference() -> None:
    assert parse_pr_reference("https://github.com/acme/service/pull/42", None, None).number == 42
    assert parse_pr_reference("acme/service#7", None, None).slug == "acme/service"
    assert parse_pr_reference(None, "acme/service", "9").number == 9
    with pytest.raises(ConfigError):
        parse_pr_reference("https://example.test/acme/service", None, None)


def test_models_fallback_and_secret_file(tmp_path: Path) -> None:
    secret = tmp_path / "secret"
    secret.write_text("value\n", encoding="utf-8")
    cfg = Config.from_env(
        {
            "PR_URL": "https://github.com/acme/service/pull/1",
            "LLM_BASE_URL": "https://llm.example/v1",
            "LLM_API_KEY_FILE": str(secret),
            "GITHUB_TOKEN_FILE": str(secret),
            "LLM_MODEL": "fallback",
        }
    )
    assert cfg.models == {"senior": "fallback", "principal": "fallback", "security": "fallback"}
    assert cfg.llm_api_key == "value"


def test_missing_model_and_bad_effort(tmp_path: Path) -> None:
    secret = tmp_path / "secret"
    secret.write_text("value", encoding="utf-8")
    base = {
        "PR_URL": "https://github.com/acme/service/pull/1",
        "LLM_BASE_URL": "https://llm.example/v1",
        "LLM_API_KEY_FILE": str(secret),
        "GITHUB_TOKEN_FILE": str(secret),
    }
    with pytest.raises(ConfigError):
        Config.from_env(base)
    with pytest.raises(ConfigError):
        Config.from_env({**base, "LLM_MODEL": "m", "REASONING_EFFORT": "turbo"})
    with pytest.raises(ConfigError):
        Config.from_env({**base, "LLM_MODEL": "m", "MAX_COMMENT_WORDS": "500"})
