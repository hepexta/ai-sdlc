from __future__ import annotations

from code_review_bot.config import Config
from code_review_bot.effort import choose_effort, volume_class


def _config(tmp_path, **extra):
    secret = tmp_path / "secret"
    secret.write_text("x", encoding="utf-8")
    env = {
        "PR_URL": "https://github.com/acme/service/pull/1",
        "LLM_BASE_URL": "https://llm.example/v1",
        "LLM_API_KEY_FILE": str(secret),
        "GITHUB_TOKEN_FILE": str(secret),
        "LLM_MODEL": "model",
        **extra,
    }
    return Config.from_env(env)


def test_volume_thresholds(tmp_path) -> None:
    cfg = _config(tmp_path)
    assert volume_class(100, 3, cfg) == "small"
    assert volume_class(300, 10, cfg) == "medium"
    assert volume_class(900, 30, cfg) == "large"


def test_effort_escalates_security_and_principal(tmp_path) -> None:
    cfg = _config(tmp_path)
    plan = choose_effort(cfg, 100, 3)
    assert (plan.senior, plan.security, plan.principal) == ("low", "medium", "medium")
    sensitive = choose_effort(cfg, 100, 3, security_sensitive=True)
    assert sensitive.security == "high"
    assert sensitive.principal == "high"
    assert sensitive.senior == "low"


def test_manual_effort_overrides_volume(tmp_path) -> None:
    cfg = _config(tmp_path, REASONING_EFFORT="high")
    plan = choose_effort(cfg, 5, 1)
    assert (plan.senior, plan.security, plan.principal) == ("high", "high", "high")
    assert plan.applied == "manual"
