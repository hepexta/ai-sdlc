from __future__ import annotations

from code_review_bot.config import Config
from code_review_bot.diff import parse_diff
from code_review_bot.models import Finding, PrincipalOutput, Triage, TriageRejection
from code_review_bot.triage import CriticalSuppressed, finalize, gate_failed

DIFF = """--- a/A.java
+++ b/A.java
@@ -1,2 +1,3 @@
 class A {
+  void x() {}
 }
"""


def _cfg(tmp_path, **extra):
    secret = tmp_path / "secret"
    secret.write_text("x", encoding="utf-8")
    return Config.from_env(
        {
            "PR_URL": "https://github.com/acme/service/pull/1",
            "LLM_BASE_URL": "https://llm.example/v1",
            "LLM_API_KEY_FILE": str(secret),
            "GITHUB_TOKEN_FILE": str(secret),
            "LLM_MODEL": "m",
            "MAX_ADDED": "1",
            "MAX_INLINE": "0",
            "MAX_SUGGESTIONS": "0",
            **extra,
        }
    )


def _finding(**overrides) -> Finding:
    data = {
        "id": "P-1",
        "origin": "senior",
        "status": "accepted",
        "axis": "standards",
        "dimension": "correctness",
        "severity": "major",
        "category": "bug",
        "title": "A bug",
        "path": "A.java",
        "line": 2,
        "evidence": "void x()",
        "impact": "It breaks.",
        "suggestion": "Fix it.",
        "confidence": 0.9,
    }
    data.update(overrides)
    return Finding.model_validate(data)


def test_caps_nits_added_and_inline(tmp_path) -> None:
    view = parse_diff(DIFF)
    principal = PrincipalOutput(
        findings=[
            _finding(id="P-1"),
            _finding(id="P-2", severity="nit", title="nit"),
            _finding(id="P-3", origin="principal", status="added", title="added one"),
            _finding(id="P-4", origin="principal", status="added", title="added two"),
        ],
        triage=None,
    )
    findings, triage, _ = finalize(_cfg(tmp_path), view, principal, [], [])
    assert [f.id for f in findings] == ["P-1", "P-3"]
    assert all(not f.anchorable for f in findings)
    assert triage.candidate_count == 0
    assert gate_failed(_cfg(tmp_path, FAIL_ON="major"), findings)
    assert not gate_failed(_cfg(tmp_path, FAIL_ON="critical"), findings)


def test_critical_candidate_cannot_be_suppressed_as_speculative(tmp_path) -> None:
    view = parse_diff(DIFF)
    candidate = _finding(id="S-1", origin="senior", severity="critical")
    principal = PrincipalOutput(
        findings=[],
        triage=Triage(
            candidate_count=1,
            posted_count=0,
            reasons={"speculative": 1},
            rejected=[
                TriageRejection(
                    candidate_id="S-1",
                    origin="senior",
                    reason="speculative",
                    title="A bug",
                    path="A.java",
                    line=2,
                )
            ],
        ),
    )
    try:
        finalize(_cfg(tmp_path), view, principal, [candidate], [])
    except CriticalSuppressed:
        pass
    else:
        raise AssertionError("critical suppression should fail closed")
