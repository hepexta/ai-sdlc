from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["critical", "major", "minor", "nit"]
Axis = Literal["standards", "spec"]
Origin = Literal["senior", "security", "principal"]
Status = Literal["accepted", "added", "downgraded"]
RejectionReason = Literal[
    "style",
    "speculative",
    "out_of_scope",
    "pre_existing",
    "already_addressed",
    "duplicate",
    "tooling",
    "low_impact",
    "unproven",
    "tests_unchanged",
    "nit",
]

REJECTION_REASONS = {
    "style",
    "speculative",
    "out_of_scope",
    "pre_existing",
    "already_addressed",
    "duplicate",
    "tooling",
    "low_impact",
    "unproven",
    "tests_unchanged",
    "nit",
}


class SuggestionCode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    replacement: str
    start_line: int
    line: int


class Finding(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    origin: Origin = "principal"
    status: Status = "accepted"
    axis: Axis = "standards"
    dimension: str = "correctness"
    severity: Severity
    category: str
    title: str
    path: str
    line: int
    start_line: int | None = None
    anchorable: bool = True
    evidence: str = ""
    impact: str = ""
    suggestion: str = ""
    suggestion_code: SuggestionCode | None = None
    comment_body: str | None = None
    confidence: float = 0.8
    security_refs: list[str] = Field(default_factory=list)
    triage_reason: str | None = None


class CandidateOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    findings: list[Finding] = Field(default_factory=list)


class TriageRejection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    candidate_id: str
    origin: Origin = "senior"
    reason: RejectionReason
    title: str = ""
    path: str = ""
    line: int | None = None


class Triage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    candidate_count: int
    posted_count: int
    rejection_rate: float = 0.0
    reasons: dict[str, int] = Field(default_factory=dict)
    rejected: list[TriageRejection] = Field(default_factory=list)
    leave_alone: list[str] = Field(default_factory=list)


class PassUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated: bool = False
    source: Literal["provider", "estimated", "unavailable"] = "unavailable"
    cost_usd: float | None = None


class PassInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    model: str = ""
    effort: str = "medium"
    candidates: int = 0
    findings: int = 0
    accepted: int = 0
    rejected: int = 0
    downgraded: int = 0
    added: int = 0
    duration_ms: int = 0
    usage: PassUsage = Field(default_factory=PassUsage)


class Summary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    verdict: Literal["ship", "ship_with_fixes", "do_not_ship"] = "ship_with_fixes"
    headline: str = ""
    counts: dict[str, int] = Field(
        default_factory=lambda: {"critical": 0, "major": 0, "minor": 0, "nit": 0}
    )
    issues: dict[str, int] = Field(
        default_factory=lambda: {
            "found": 0,
            "accepted": 0,
            "rejected": 0,
            "downgraded": 0,
            "added": 0,
            "posted": 0,
        }
    )
    tokens: dict[str, object] = Field(default_factory=dict)
    suggestions: int = 0
    suggestion_dropped: int = 0
    effort: dict[str, object] = Field(default_factory=dict)
    label: dict[str, object] = Field(default_factory=lambda: {"name": "", "applied": False})
    style: dict[str, object] = Field(default_factory=dict)
    noise: dict[str, object] = Field(default_factory=dict)
    coverage: dict[str, object] = Field(default_factory=dict)
    what_works: str = ""


class PRInfo(BaseModel):
    repo: str
    number: int
    head_sha: str
    base_sha: str
    url: str


class PrincipalOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    findings: list[Finding] = Field(default_factory=list)
    triage: Triage | None = None
    leave_alone: list[str] = Field(default_factory=list)
    verdict: Literal["ship", "ship_with_fixes", "do_not_ship"] = "ship_with_fixes"
    headline: str = ""
    what_works: str = ""


class ReviewReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_version: str = "4.0"
    run_id: str
    pr: PRInfo
    passes: dict[str, PassInfo] = Field(default_factory=dict)
    summary: Summary
    triage: Triage
    findings: list[Finding] = Field(default_factory=list)
    gate: dict[str, object] = Field(default_factory=dict)
    usage: dict[str, object] = Field(default_factory=dict)
    timings_ms: dict[str, int] = Field(default_factory=dict)


class PassResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str
    usage: PassUsage = Field(default_factory=PassUsage)
    model: str = ""
    effort: str = "medium"
    duration_ms: int = 0
