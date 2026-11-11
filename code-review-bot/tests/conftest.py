from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


def _git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.test",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.test",
        }
    )
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def make_fixture_repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.test")
    java = repo / "src/main/java/com/acme"
    java.mkdir(parents=True)
    (java / "OrderController.java").write_text(
        "package com.acme;\n"
        "\n"
        "public class OrderController {\n"
        "  private final OrderRepository orderRepository;\n"
        "\n"
        "  public OrderController(OrderRepository orderRepository) {\n"
        "    this.orderRepository = orderRepository;\n"
        "  }\n"
        "\n"
        "  public Order get(String id) {\n"
        "    return orderRepository.findById(id);\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (java / "UserService.java").write_text(
        "package com.acme;\n"
        "\n"
        "public class UserService {\n"
        "  private final UserRepository repository;\n"
        "\n"
        "  public UserService(UserRepository repository) {\n"
        "    this.repository = repository;\n"
        "  }\n"
        "\n"
        "  public User find(String email) {\n"
        "    return repository.findByEmail(email).orElse(null);\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo / "AGENTS.md").write_text("Prefer clear ownership checks.\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    (java / "OrderController.java").write_text(
        "package com.acme;\n"
        "\n"
        "public class OrderController {\n"
        "  private final OrderRepository orderRepository;\n"
        "\n"
        "  public OrderController(OrderRepository orderRepository) {\n"
        "    this.orderRepository = orderRepository;\n"
        "  }\n"
        "\n"
        "  public Order get(String id, String callerId) {\n"
        "    return orderRepository.findById(id);\n"
        "  }\n"
        "\n"
        "  public String buildQuery(String id) {\n"
        "    return \"SELECT * FROM orders WHERE id = \" + id;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (java / "UserService.java").write_text(
        "package com.acme;\n"
        "\n"
        "public class UserService {\n"
        "  private final UserRepository repository;\n"
        "\n"
        "  public UserService(UserRepository repository) {\n"
        "    this.repository = repository;\n"
        "  }\n"
        "\n"
        "  public User find(String email) {\n"
        "    return repository.findByEmail(email).get();\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")
    return repo, base, head


def write_fake_responses(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    senior = {
        "findings": [
            {
                "axis": "standards",
                "dimension": "security",
                "severity": "critical",
                "category": "broken-access-control",
                "title": "Order lookup does not check ownership",
                "path": "src/main/java/com/acme/OrderController.java",
                "line": 11,
                "evidence": "orderRepository.findById(id)",
                "impact": "Any authenticated customer can read another customer's order.",
                "suggestion": "Load by id and customer id, or check ownership.",
                "confidence": 0.94,
                "security_refs": ["CWE-639"],
            },
            {
                "axis": "standards",
                "dimension": "correctness",
                "severity": "major",
                "category": "null-safety",
                "title": "Optional.get can throw for unknown emails",
                "path": "src/main/java/com/acme/UserService.java",
                "line": 11,
                "evidence": "repository.findByEmail(email).get()",
                "impact": "A normal user-not-found path throws instead of returning a 404.",
                "suggestion": "Use orElseThrow with a domain exception.",
                "confidence": 0.88,
            },
            {
                "axis": "standards",
                "dimension": "security",
                "severity": "minor",
                "category": "sql-injection",
                "title": "SQL string concatenation",
                "path": "src/main/java/com/acme/OrderController.java",
                "line": 15,
                "evidence": "\"SELECT * FROM orders WHERE id = \" + id",
                "impact": "A crafted id can alter the query.",
                "suggestion": "Use a parameterized query.",
                "confidence": 0.9,
                "security_refs": ["CWE-89"],
            },
        ]
    }
    security = {
        "findings": [
            {
                "axis": "standards",
                "dimension": "security",
                "severity": "critical",
                "category": "sql-injection",
                "title": "SQL string concatenation reaches the database",
                "path": "src/main/java/com/acme/OrderController.java",
                "line": 15,
                "evidence": "return \"SELECT * FROM orders WHERE id = \" + id;",
                "impact": "An attacker-controlled id can change the SQL statement.",
                "suggestion": "Bind the id as a parameter.",
                "confidence": 0.91,
                "security_refs": ["CWE-89", "ASVS-5.0:V5"],
            }
        ]
    }
    principal = {
        "verdict": "ship_with_fixes",
        "headline": "One access-control bug and one null-safety bug; the rest can wait.",
        "what_works": "The new query helper is small and easy to follow.",
        "findings": [
            {
                "id": "P-001",
                "origin": "senior",
                "status": "accepted",
                "axis": "standards",
                "dimension": "security",
                "severity": "critical",
                "category": "broken-access-control",
                "title": "Order lookup does not check ownership",
                "path": "src/main/java/com/acme/OrderController.java",
                "line": 11,
                "evidence": "orderRepository.findById(id)",
                "impact": "Any authenticated customer can read another customer's order by changing the id.",
                "suggestion": "Load by id and customer id, or check ownership before returning the DTO.",
                "suggestion_code": {
                    "replacement": "return orderRepository.findByIdAndCustomerId(id, callerId);",
                    "start_line": 11,
                    "line": 11,
                },
                "comment_body": "`findById` returns any customer's order, not just the caller's. Any authenticated user can read someone else's order by changing the ID.\n\nLoad it by id and customer id, or check ownership before returning the DTO.",
                "confidence": 0.94,
                "security_refs": ["CWE-639"],
                "triage_reason": "accepted",
            },
            {
                "id": "P-002",
                "origin": "senior",
                "status": "accepted",
                "axis": "standards",
                "dimension": "correctness",
                "severity": "major",
                "category": "null-safety",
                "title": "Optional.get can throw for unknown emails",
                "path": "src/main/java/com/acme/UserService.java",
                "line": 11,
                "evidence": "repository.findByEmail(email).get()",
                "impact": "A normal user-not-found path throws instead of returning a 404.",
                "suggestion": "Use orElseThrow with a domain exception.",
                "suggestion_code": {
                    "replacement": "return repository.findByEmail(email).orElseThrow(() -> new UserNotFound(email));",
                    "start_line": 11,
                    "line": 11,
                },
                "comment_body": "`findByEmail` returns an empty Optional for unknown addresses, so this `get()` throws on a normal not-found path.\n\nUse `orElseThrow` and map it to a 404. Worth a test for the unknown-email case.",
                "confidence": 0.88,
                "triage_reason": "accepted",
            },
        ],
        "triage": {
            "candidate_count": 4,
            "posted_count": 2,
            "reasons": {"nit": 1, "duplicate": 1},
            "rejected": [
                {
                    "candidate_id": "S-003",
                    "origin": "senior",
                    "reason": "nit",
                    "title": "SQL string concatenation",
                    "path": "src/main/java/com/acme/OrderController.java",
                    "line": 15,
                },
                {
                    "candidate_id": "SEC-001",
                    "origin": "security",
                    "reason": "duplicate",
                    "title": "SQL string concatenation reaches the database",
                    "path": "src/main/java/com/acme/OrderController.java",
                    "line": 15,
                },
            ],
            "leave_alone": ["A broader repository split is out of scope."],
        },
    }
    (directory / "senior-reviewer.json").write_text(json.dumps(senior), encoding="utf-8")
    (directory / "security-reviewer.json").write_text(json.dumps(security), encoding="utf-8")
    (directory / "principal-reviewer.json").write_text(json.dumps(principal), encoding="utf-8")


@pytest.fixture()
def fixture_repo(tmp_path: Path) -> tuple[Path, str, str]:
    return make_fixture_repo(tmp_path)
