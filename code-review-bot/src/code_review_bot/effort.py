from __future__ import annotations

from dataclasses import dataclass, replace

from .config import Config


@dataclass(frozen=True)
class EffortPlan:
    volume: str
    changed_lines: int
    changed_files: int
    security_sensitive: bool
    senior: str
    security: str
    principal: str
    applied: str

    def for_role(self, role: str) -> str:
        return {"senior": self.senior, "security": self.security, "principal": self.principal}[role]


def volume_class(changed_lines: int, changed_files: int, cfg: Config) -> str:
    if changed_lines <= cfg.low_max_lines and changed_files <= cfg.low_max_files:
        return "small"
    if changed_lines <= cfg.medium_max_lines and changed_files <= cfg.medium_max_files:
        return "medium"
    return "large"


def choose_effort(
    cfg: Config,
    changed_lines: int,
    changed_files: int,
    security_sensitive: bool = False,
) -> EffortPlan:
    volume = volume_class(changed_lines, changed_files, cfg)
    if cfg.effort in {"low", "medium", "high"}:
        return EffortPlan(
            volume=volume,
            changed_lines=changed_lines,
            changed_files=changed_files,
            security_sensitive=security_sensitive,
            senior=cfg.effort,
            security=cfg.effort,
            principal=cfg.effort,
            applied="manual",
        )

    if volume == "small":
        senior, security, principal = "low", "medium", "medium"
    elif volume == "medium":
        senior, security, principal = "medium", "high", "high"
    else:
        senior, security, principal = "high", "high", "high"

    if security_sensitive:
        security = "high"
        principal = "high"

    return EffortPlan(
        volume=volume,
        changed_lines=changed_lines,
        changed_files=changed_files,
        security_sensitive=security_sensitive,
        senior=senior,
        security=security,
        principal=principal,
        applied=cfg.effort_mode,
    )


def prompt_effort(plan: EffortPlan, role: str) -> str:
    return (
        f"Reasoning effort: {plan.for_role(role)}. "
        "Be thorough but do not invent issues; use the graph brief before reading widely."
    )


def with_applied(plan: EffortPlan, applied: str) -> EffortPlan:
    return replace(plan, applied=applied)
