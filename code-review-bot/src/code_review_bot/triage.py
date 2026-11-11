from __future__ import annotations

from collections import Counter

from .config import Config
from .diff import DiffView, anchor_finding, validate_suggestion
from .models import (
    Finding,
    PrincipalOutput,
    Summary,
    Triage,
    TriageRejection,
)

SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2, "nit": 3}
INLINE_SEVERITIES = {"critical", "major"}


class CriticalSuppressed(RuntimeError):
    """A proven critical candidate was dropped without acceptable evidence."""


def assign_ids(findings: list[Finding], prefix: str) -> list[Finding]:
    out: list[Finding] = []
    for index, finding in enumerate(findings, start=1):
        data = finding.model_dump()
        if not data.get("id"):
            data["id"] = f"{prefix}-{index:03d}"
        out.append(Finding.model_validate(data))
    return out


def parse_candidates(raw: dict, origin: str) -> list[Finding]:
    items = raw.get("findings", [])
    findings: list[Finding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        data = dict(item)
        data.setdefault("origin", origin)
        data.setdefault("status", "accepted")
        data.setdefault("anchorable", True)
        data.setdefault("id", "")
        findings.append(Finding.model_validate(data))
    return findings


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[str] = set()
    out: list[Finding] = []
    for finding in findings:
        key = f"{finding.path}:{finding.line}:{finding.category}:{finding.title.lower()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(finding)
    return out


def _reason_summary(rejections: list[TriageRejection]) -> dict[str, int]:
    counts = Counter(rejection.reason for rejection in rejections)
    return dict(sorted(counts.items()))


def finalize(
    cfg: Config,
    view: DiffView,
    principal: PrincipalOutput,
    senior: list[Finding],
    security: list[Finding],
) -> tuple[list[Finding], Triage, int]:
    candidates = _dedupe([*senior, *security])
    candidate_ids = {finding.id for finding in candidates}
    findings = _dedupe(list(principal.findings))
    added = [f for f in findings if f.origin == "principal"]
    if len(added) > cfg.max_added:
        keep = {f.id for f in sorted(added, key=lambda f: (SEVERITY_ORDER[f.severity], -f.confidence))[: cfg.max_added]}
        findings = [f for f in findings if f.origin != "principal" or f.id in keep]
    dropped_suggestions = 0

    cleaned: list[Finding] = []
    suggestions = 0
    for finding in findings:
        data = finding.model_dump()
        data["anchorable"] = anchor_finding(view, finding.path, finding.line)
        if data.get("suggestion_code"):
            valid, _ = validate_suggestion(
                view,
                finding.path,
                data["suggestion_code"].get("start_line") if isinstance(data["suggestion_code"], dict) else None,
                finding.line,
                data["suggestion_code"].get("replacement") if isinstance(data["suggestion_code"], dict) else "",
            )
            if not valid:
                data["suggestion_code"] = None
                dropped_suggestions += 1
            elif suggestions >= cfg.max_suggestions:
                data["suggestion_code"] = None
                dropped_suggestions += 1
            else:
                suggestions += 1
        cleaned.append(Finding.model_validate(data))

    cleaned.sort(key=lambda f: (SEVERITY_ORDER[f.severity], -f.confidence))
    limited: list[Finding] = []
    inline_total = 0
    inline_minor = 0
    for finding in cleaned:
        if finding.severity == "nit" and not cfg.allow_nits:
            continue
        if len(limited) >= cfg.max_findings:
            break
        if finding.anchorable and finding.severity != "nit":
            if finding.severity == "minor" and inline_minor >= cfg.max_minor_inline:
                data = finding.model_dump()
                data["anchorable"] = False
                finding = Finding.model_validate(data)
            elif inline_total >= cfg.max_inline:
                data = finding.model_dump()
                data["anchorable"] = False
                finding = Finding.model_validate(data)
            else:
                inline_total += 1
                if finding.severity == "minor":
                    inline_minor += 1
        limited.append(finding)

    triage = principal.triage
    if triage is None:
        rejected = [
            TriageRejection(
                candidate_id=f.id,
                origin=f.origin,
                reason="low_impact",
                title=f.title,
                path=f.path,
                line=f.line,
            )
            for f in candidates
            if f.id not in {item.id for item in limited}
        ]
        triage = Triage(
            candidate_count=len(candidates),
            posted_count=len(limited),
            rejection_rate=len(rejected) / max(1, len(candidates)),
            reasons=_reason_summary(rejected),
            rejected=rejected,
            leave_alone=list(principal.leave_alone),
        )
    else:
        data = triage.model_dump()
        data["candidate_count"] = len(candidates)
        data["posted_count"] = len(limited)
        data["rejection_rate"] = len(data.get("rejected", [])) / max(1, len(candidates))
        triage = Triage.model_validate(data)

    # Drop candidates whose IDs are unknown to the Principal ledger only for metrics; never crash.
    for rejection in triage.rejected:
        if rejection.candidate_id and candidate_ids and rejection.candidate_id not in candidate_ids:
            continue

    rejected_by_id = {rejection.candidate_id: rejection for rejection in triage.rejected}
    allowed_critical_rejections = {"duplicate", "already_addressed", "pre_existing"}
    for candidate in candidates:
        if candidate.severity != "critical":
            continue
        accepted = any(
            f.severity == "critical"
            and f.path == candidate.path
            and (f.line == candidate.line or f.category == candidate.category)
            for f in limited
        )
        if accepted:
            continue
        rejection = rejected_by_id.get(candidate.id)
        if rejection and rejection.reason in allowed_critical_rejections:
            continue
        raise CriticalSuppressed(
            f"critical candidate {candidate.id} ({candidate.path}:{candidate.line}) "
            "was not accepted and has no acceptable rejection evidence"
        )

    return limited, triage, dropped_suggestions


def build_summary(
    cfg: Config,
    findings: list[Finding],
    triage: Triage,
    *,
    pass_usage: dict[str, dict],
    effort: dict,
    label_name: str,
    label_applied: bool,
    graph_status: str,
    security_status: str,
    files_changed: int,
    files_reviewed: int,
    skipped: list[str],
    suggestion_dropped: int = 0,
    headline: str = "",
    what_works: str = "",
    verdict: str = "ship_with_fixes",
) -> Summary:
    counts = Counter(f.severity for f in findings)
    total_tokens = sum(int(v.get("total_tokens", 0)) for v in pass_usage.values())
    input_tokens = sum(int(v.get("input_tokens", 0)) for v in pass_usage.values())
    output_tokens = sum(int(v.get("output_tokens", 0)) for v in pass_usage.values())
    estimated = any(bool(v.get("estimated")) for v in pass_usage.values())
    sources = {v.get("source") for v in pass_usage.values() if v.get("source")}
    source = "provider" if sources == {"provider"} else "estimated" if estimated else "unavailable"
    issues = {
        "found": triage.candidate_count,
        "accepted": sum(1 for f in findings if f.status == "accepted"),
        "rejected": len(triage.rejected),
        "downgraded": sum(1 for f in findings if f.status == "downgraded"),
        "added": sum(1 for f in findings if f.status == "added" or f.origin == "principal"),
        "posted": len(findings),
    }
    by_pass = {role: int(v.get("total_tokens", 0)) for role, v in pass_usage.items()}
    return Summary(
        verdict=verdict,  # type: ignore[arg-type]
        headline=headline,
        counts={s: counts.get(s, 0) for s in ("critical", "major", "minor", "nit")},
        issues=issues,
        tokens={
            "total": total_tokens,
            "input": input_tokens,
            "output": output_tokens,
            "estimated": estimated,
            "source": source,
            "by_pass": by_pass,
        },
        suggestions=sum(1 for f in findings if f.suggestion_code),
        suggestion_dropped=suggestion_dropped,
        effort=effort,
        label={"name": label_name, "applied": label_applied},
        style={},
        noise={
            "inline": sum(1 for f in findings if f.anchorable),
            "per_100_changed_lines": round(
                sum(1 for f in findings if f.anchorable) / max(1, effort.get("changed_lines", 0)) * 100, 2
            ),
            "nits": sum(1 for f in findings if f.severity == "nit"),
        },
        coverage={
            "files_changed": files_changed,
            "files_reviewed": files_reviewed,
            "graph": graph_status,
            "security_pass": security_status,
            "skipped": skipped,
        },
        what_works=what_works,
    )


def gate_failed(cfg: Config, findings: list[Finding]) -> bool:
    if cfg.fail_on == "none":
        return False
    threshold = {"critical": 0, "major": 1}[cfg.fail_on]
    return any(SEVERITY_ORDER[f.severity] <= threshold for f in findings if f.severity != "nit")
