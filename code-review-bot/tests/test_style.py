from __future__ import annotations

from code_review_bot.models import Finding, SuggestionCode
from code_review_bot.style import (
    fingerprint,
    lint_comment,
    render_comment,
    strip_formatting,
    word_count,
)


def _finding(**overrides) -> Finding:
    data = {
        "id": "P-1",
        "origin": "principal",
        "severity": "major",
        "category": "null-safety",
        "title": "Optional.get can throw",
        "path": "src/UserService.java",
        "line": 11,
        "evidence": "repository.findByEmail(email).get()",
        "impact": "A normal not-found path throws instead of returning a 404.",
        "suggestion": "Use orElseThrow and map it to a 404.",
        "comment_body": (
            "`findByEmail` returns an empty Optional for unknown addresses, so this `get()` "
            "throws on a normal not-found path.\n\nUse `orElseThrow` and map it to a 404."
        ),
    }
    data.update(overrides)
    return Finding.model_validate(data)


def test_human_comment_passes_and_has_marker() -> None:
    finding = _finding(
        suggestion_code=SuggestionCode(
            replacement="return repository.findByEmail(email).orElseThrow();",
            start_line=11,
            line=11,
        )
    )
    body = render_comment(finding, max_words=120)
    assert "```suggestion" in body
    assert "<!-- crb:f:" in body
    assert not lint_comment(body.split("<!--")[0], 120)


def test_ai_scaffolding_is_linted_and_stripped() -> None:
    bad = "## Summary\n\n**Why:** This is a comprehensive issue.\n\nLet's dive in."
    problems = lint_comment(bad, 120)
    assert "markdown heading" in problems
    assert any("AI-tell" in p for p in problems)
    cleaned = strip_formatting(bad)
    assert "##" not in cleaned
    assert "**" not in cleaned
    assert "comprehensive" not in cleaned.lower()


def test_word_count_ignores_code_and_markers() -> None:
    text = "one two\n\n```suggestion\nthree four five\n```\n<!-- crb:f:abc severity=major -->"
    assert word_count(text) == 2


def test_secret_is_redacted_from_comment() -> None:
    finding = _finding(
        comment_body="The token `ghp_abcdefghijklmnopqrstuvwxyz` is committed. Remove it."
    )
    body = render_comment(finding)
    assert "ghp_" not in body
    assert "[REDACTED_SECRET]" in body


def test_fingerprint_stable() -> None:
    assert fingerprint(_finding()) == fingerprint(_finding())
    assert fingerprint(_finding()) != fingerprint(_finding(line=12))
