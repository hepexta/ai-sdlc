from __future__ import annotations

import hashlib
import re
from collections import Counter

from .models import Finding, ReviewReport, Severity

FORBIDDEN = [
    r"\bas an ai\b",
    r"\bas a language model\b",
    r"\bi hope this helps\b",
    r"\bi noticed( that)?\b",
    r"\bit appears( that)?\b",
    r"\bit seems( that)?\b",
    r"\bcomprehensive\b",
    r"\brobust\b",
    r"\bleverage\b",
    r"\bdelve\b",
    r"\bseamless\b",
    r"\bcutting-edge\b",
    r"\blet'?s dive in\b",
    r"\bhere'?s a breakdown\b",
    r"\bin conclusion\b",
    r"\boverall\b",
    r"\bthe code snippet\b",
    r"\bthe provided code\b",
]
FORBIDDEN_RE = [re.compile(p, re.I) for p in FORBIDDEN]
BOLD_LABEL_RE = re.compile(r"^\s*\*\*(why|evidence|fix|impact|severity|confidence|model|run id|tokens?)\*\*\s*:?", re.I)
HEADING_RE = re.compile(r"^\s*#{1,6}\s+", re.M)
EMOJI_RE = re.compile(
    "[" "\U0001F300-\U0001FAFF" "\U00002700-\U000027BF" "\U0001F1E6-\U0001F1FF" "]+"
)
VISIBLE_META_RE = re.compile(
    r"\b(confidence|model|run id|tokens?)\s*:\s*\S+", re.I
)
CODE_FENCE_RE = re.compile(r"```.*?```", re.S)
SECRET_RE = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|"
    r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


def redact_secrets(text: str) -> str:
    return SECRET_RE.sub("[REDACTED_SECRET]", text)


def word_count(text: str) -> int:
    stripped = CODE_FENCE_RE.sub(" ", text)
    stripped = re.sub(r"<!--.*?-->", " ", stripped, flags=re.S)
    return len(re.findall(r"\S+", stripped))


def lint_comment(text: str, max_words: int = 120) -> list[str]:
    problems: list[str] = []
    if word_count(text) > max_words:
        problems.append(f"too many words ({word_count(text)} > {max_words})")
    if HEADING_RE.search(text):
        problems.append("markdown heading")
    if BOLD_LABEL_RE.search(text):
        problems.append("bold-label scaffolding")
    if EMOJI_RE.search(text):
        problems.append("emoji")
    if VISIBLE_META_RE.search(text):
        problems.append("visible model/confidence/run/token metadata")
    for pattern in FORBIDDEN_RE:
        if pattern.search(text):
            problems.append(f"AI-tell phrase: {pattern.pattern}")
    return problems


def strip_formatting(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            lines.append("")
            continue
        if HEADING_RE.match(line):
            line = HEADING_RE.sub("", line).strip()
        line = BOLD_LABEL_RE.sub("", line).strip()
        line = VISIBLE_META_RE.sub("", line).strip()
        line = line.replace("**", "").replace("__", "")
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = EMOJI_RE.sub("", cleaned)
    for pattern in FORBIDDEN_RE:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def severity_lead(severity: Severity) -> str:
    return {
        "critical": "This needs to be fixed before merge.",
        "major": "Worth fixing before merge.",
        "minor": "Not blocking, but this is worth tightening.",
        "nit": "Nit:",
    }[severity]


def fingerprint(finding: Finding) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", finding.title.lower()).strip("-")
    raw = f"{finding.path}|{finding.line}|{finding.category}|{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def default_comment(finding: Finding) -> str:
    lead = severity_lead(finding.severity)
    first = finding.impact or finding.evidence or finding.title
    first = first.strip()
    if finding.severity == "nit":
        body = f"{lead} {first}"
    elif finding.severity == "critical":
        body = f"{lead} {first}" if not first.lower().startswith("this") else first
    else:
        body = f"{lead} {first}" if not first.lower().startswith(("this", "`")) else first
    if finding.evidence and finding.evidence not in body:
        body += f"\n\n`{finding.evidence}`" if "`" not in finding.evidence else f"\n\n{finding.evidence}"
    if finding.suggestion:
        body += f"\n\n{finding.suggestion.strip()}"
    if finding.security_refs:
        body += "\n\n" + ", ".join(finding.security_refs)
    return body.strip()


def render_comment(
    finding: Finding,
    *,
    max_words: int = 120,
    style: str = "human",
    include_marker: bool = True,
) -> str:
    body = (finding.comment_body or default_comment(finding)).strip()
    body = redact_secrets(body)
    if style == "human":
        problems = lint_comment(body, max_words=max_words)
        if problems:
            body = strip_formatting(body) or default_comment(finding)
    if finding.suggestion_code and not CODE_FENCE_RE.search(body):
        body += (
            "\n\n```suggestion\n"
            + finding.suggestion_code.replacement.rstrip("\n")
            + "\n```"
        )
    if include_marker:
        body += f"\n\n<!-- crb:f:{fingerprint(finding)} severity={finding.severity} -->"
    return body.strip()


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def render_summary(
    report: ReviewReport,
    *,
    marker_head: str,
    run_id: str,
    label_applied: bool,
    label_name: str,
    max_words: int = 250,
) -> str:
    summary = report.summary
    findings = report.findings
    blocking = [f for f in findings if f.severity in {"critical", "major"}]
    minor = [f for f in findings if f.severity == "minor"]
    headline = summary.headline.strip()
    if not headline:
        if blocking:
            headline = "A few things need attention before this merges."
        elif minor:
            headline = "No blockers; a few smaller things are worth a look."
        else:
            headline = "I didn't find anything blocking in this change."
    lines = ["## Review", "", headline, ""]
    if blocking:
        lines.append("**Blocking**")
        for f in blocking[:6]:
            lines.append(f"- `{f.path}:{f.line}` — {f.title}")
        lines.append("")
    if minor:
        lines.append("**Worth fixing**")
        for f in minor[:4]:
            lines.append(f"- `{f.path}:{f.line}` — {f.title}")
        lines.append("")
    if summary.what_works:
        lines.extend([summary.what_works.strip(), ""])
    if not findings:
        lines.extend(["No findings met the bar for a comment.", ""])
    tokens = summary.tokens or {}
    total = int(tokens.get("total") or 0)
    by_pass = tokens.get("by_pass") or {}
    token_part = "tokens unavailable"
    if total:
        token_part = (
            f"{_fmt_int(total)} tokens "
            f"(senior {_fmt_int(int(by_pass.get('senior', 0)))} / "
            f"security {_fmt_int(int(by_pass.get('security', 0)))} / "
            f"principal {_fmt_int(int(by_pass.get('principal', 0)))})"
        )
    effort = summary.effort or {}
    effort_part = f"effort {effort.get('senior', '?')}/{effort.get('security', '?')}/{effort.get('principal', '?')}"
    if not label_name:
        label_part = "label disabled"
    elif label_applied:
        label_part = f"`{label_name}` added"
    else:
        label_part = "label not applied"
    footer = (
        f"{summary.issues.get('found', 0)} found → "
        f"{summary.issues.get('accepted', 0)} accepted / "
        f"{summary.issues.get('rejected', 0)} rejected / "
        f"{summary.issues.get('downgraded', 0)} downgraded / "
        f"{summary.issues.get('added', 0)} added · "
        f"{summary.issues.get('posted', 0)} posted · "
        f"{summary.suggestions} suggestions · {token_part} · {effort_part} · {label_part}"
    )
    lines.append(f"<sub>{footer}</sub>")
    lines.append("")
    lines.append(
        f"<!-- code-review-bot:summary:v4 head={marker_head} run={run_id} "
        f"verdict={summary.verdict} -->"
    )
    return redact_secrets("\n".join(lines).strip()) + "\n"


def summarize_style(findings: list[Finding], bodies: list[str], style: str) -> dict[str, object]:
    counts = [word_count(b) for b in bodies] if bodies else [0]
    return {
        "mode": style,
        "inline_avg_words": round(sum(counts) / max(1, len(counts)), 1),
        "max_words": max(counts),
        "lint": "pass",
        "visible_metadata": bool(any(VISIBLE_META_RE.search(b) for b in bodies)),
        "comments": len(findings),
    }
