from __future__ import annotations

import fnmatch
import json
import logging
import re
import time
import uuid
from pathlib import Path

from .brief import (
    build_principal_brief,
    build_security_brief,
    build_senior_brief,
    write_brief,
)
from .config import Config, ConfigError
from .diff import context_files, reviewable_source_files, source_change_counts
from .effort import choose_effort
from .github import GitHubClient, GitHubError, PullRequest
from .gitops import WorkspaceError, prepare_workspace
from .graph import GraphRequiredError, build_graph
from .models import (
    Finding,
    PassInfo,
    PassUsage,
    PRInfo,
    PrincipalOutput,
    ReviewReport,
    Summary,
    Triage,
)
from .opencode_runner import AgentError, AgentSpec, OpenCodeRunner, parse_json_object
from .publish import Publisher
from .style import render_comment, render_summary, summarize_style
from .triage import (
    CriticalSuppressed,
    assign_ids,
    build_summary,
    finalize,
    gate_failed,
    parse_candidates,
)

log = logging.getLogger(__name__)

SENSITIVE_PATH = re.compile(
    r"(auth|security|token|password|secret|jwt|crypto|cipher|sql|migration|upload|"
    r"deserial|objectinputstream|pickle|yaml|xml|actuator|cors|csrf|dockerfile|"
    r"k8s|helm|terraform)",
    re.I,
)
SENSITIVE_CONTENT = re.compile(
    r"(SecurityFilterChain|PreAuthorize|WebSecurity|PasswordEncoder|SecretKey|Cipher|"
    r"MessageDigest|ObjectInputStream|DocumentBuilder|pickle\.load|yaml\.load|"
    r"subprocess|shell=True|eval\(|exec\(|SELECT .*\+|execute\(|requests\.(get|post)|"
    r"Path\(|FileInputStream|Runtime\.getRuntime)",
    re.I,
)
SECRET_PATTERNS = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|"
    r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)",
)


class ReviewFailure(RuntimeError):
    def __init__(self, message: str, exit_code: int):
        super().__init__(message)
        self.exit_code = exit_code


def _security_sensitive(cfg: Config, view, workspace: Path) -> bool:
    if cfg.security_pass == "off":
        return False
    if cfg.security_pass == "always":
        return True
    selected = reviewable_source_files(view, cfg.max_files)
    for file in selected:
        if SENSITIVE_PATH.search(file.path):
            return True
        if any(fnmatch.fnmatch(file.path, pattern) for pattern in cfg.security_globs):
            return True
    diff_text = "\n".join(f.patch_text for f in selected)
    return bool(SENSITIVE_CONTENT.search(diff_text))


def _redact_secrets(text: str) -> str:
    return SECRET_PATTERNS.sub("[REDACTED_SECRET]", text)


def _agent_spec(name: str, role: str, cfg: Config, plan) -> AgentSpec:
    return AgentSpec(
        name=name,
        role=role,
        model=cfg.models[role],
        effort=plan.for_role(role),
        prompt="",
    )


def _run_json(runner: OpenCodeRunner, spec: AgentSpec, brief: Path, cfg: Config) -> tuple[dict, PassInfo]:
    result = runner.run(spec, brief)
    try:
        raw = parse_json_object(result.text)
    except Exception as exc:
        repair = brief.with_name(brief.stem + "-repair.md")
        repair.write_text(
            brief.read_text(encoding="utf-8")
            + "\n\n## Repair\nYour previous output was not valid JSON. Return exactly one JSON object. "
            + f"Parser error: {exc}\nPrevious output:\n```\n{result.text[:4000]}\n```\n",
            encoding="utf-8",
        )
        result = runner.run(spec, repair)
        try:
            raw = parse_json_object(result.text)
        except Exception as exc2:
            raise ReviewFailure(f"{spec.name} returned invalid JSON after repair: {exc2}", 5) from exc2
    info = PassInfo(
        enabled=True,
        model=result.model,
        effort=result.effort,
        duration_ms=result.duration_ms,
        usage=result.usage,
    )
    if result.usage.source == "unavailable" and cfg.token_accounting in {"auto", "estimate"}:
        try:
            input_tokens = max(1, len(brief.read_text(encoding="utf-8")) // 4)
        except OSError:
            input_tokens = 1
        output_tokens = max(1, len(result.text) // 4)
        info.usage = PassUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated=True,
            source="estimated",
        )
    return raw, info


def _usage_dict(info: PassInfo) -> dict:
    usage = info.usage
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens or usage.input_tokens + usage.output_tokens,
        "estimated": usage.estimated,
        "source": usage.source,
    }


def _write_artifacts(cfg: Config, report: ReviewReport) -> None:
    out = cfg.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "review.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (out / "triage.json").write_text(report.triage.model_dump_json(indent=2), encoding="utf-8")
    summary = render_summary(
        report,
        marker_head=report.pr.head_sha,
        run_id=report.run_id,
        label_applied=bool(report.summary.label.get("applied")),
        label_name=cfg.label,
        max_words=cfg.max_summary_words,
    )
    (out / "summary.md").write_text(summary, encoding="utf-8")


def _empty_review(cfg: Config, gh: GitHubClient, pr: PullRequest) -> int:
    if cfg.dry_run:
        log.info("nothing to review; dry run")
        return 0
    if cfg.label:
        body = (
            "## Review\n\nThis PR has no Java/Python changes to review. "
            f"The `{cfg.label}` label was added; remove it to request another review.\n\n"
            f"<!-- code-review-bot:summary:v4 head={pr.head_sha} run=empty verdict=ship -->\n"
        )
        gh.create_issue_comment(pr.number, body)
        gh.add_labels(pr.number, [cfg.label])
    log.info("nothing to review")
    return 0


def run_review(cfg: Config) -> int:
    started = time.time()
    run_id = str(uuid.uuid4())
    gh = GitHubClient(
        cfg.github_api_url,
        cfg.github_token,
        cfg.pr.owner,
        cfg.pr.repo,
    )
    workspace = None
    try:
        pr = gh.get_pull(cfg.pr.number)
        if pr.state != "open":
            log.info("PR is %s; skipping", pr.state)
            return 0
        if cfg.label and cfg.label in pr.labels:
            if not cfg.force:
                log.info("skip: %s", cfg.label)
                return 0
            if not cfg.dry_run:
                try:
                    gh.remove_label(pr.number, cfg.label)
                except GitHubError as exc:
                    if exc.status != 404:
                        raise
        if cfg.label and not cfg.dry_run:
            gh.ensure_label(cfg.label, cfg.label_color, cfg.label_description)

        workspace = prepare_workspace(cfg, pr)
        view = workspace.diff
        selected = reviewable_source_files(view, cfg.max_files)
        if not selected:
            return _empty_review(cfg, gh, pr)
        total_changed, source_files = source_change_counts(view, cfg.max_files)
        sensitive = _security_sensitive(cfg, view, workspace.path)
        plan = choose_effort(cfg, total_changed, source_files, sensitive)
        log.info("volume=%s effort=%s/%s/%s", plan.volume, plan.senior, plan.security, plan.principal)

        graph = build_graph(cfg, workspace.path, workspace.base_sha)
        linked_issue = ""
        issue_number = gh.linked_issue_number(pr)
        if issue_number:
            try:
                issue = gh.get_issue(issue_number)
                linked_issue = f"#{issue_number} {issue.get('title', '')}\n{issue.get('body') or ''}"
            except GitHubError:
                linked_issue = ""

        runner = OpenCodeRunner(cfg, workspace.path, plan)
        runner.prepare()
        senior_brief = build_senior_brief(
            cfg, pr, view, graph, plan, workspace.path, linked_issue
        )
        senior_path = write_brief(workspace.path / "SENIOR_BRIEF.md", _redact_secrets(senior_brief))
        senior_spec = _agent_spec("senior-reviewer", "senior", cfg, plan)
        senior_raw, senior_info = _run_json(runner, senior_spec, senior_path, cfg)
        senior = assign_ids(parse_candidates(senior_raw, "senior"), "S")[: cfg.max_candidates]
        senior_info.candidates = len(senior)

        security: list[Finding] = []
        security_info = PassInfo(enabled=False, effort=plan.security)
        if sensitive:
            security_brief = build_security_brief(cfg, pr, view, graph, plan)
            security_path = write_brief(workspace.path / "SECURITY_BRIEF.md", _redact_secrets(security_brief))
            security_spec = _agent_spec("security-reviewer", "security", cfg, plan)
            try:
                security_raw, security_info = _run_json(runner, security_spec, security_path, cfg)
            except Exception as exc:
                raise ReviewFailure(f"security pass failed: {exc}", 8) from exc
            security = assign_ids(parse_candidates(security_raw, "security"), "SEC")[:10]
            security_info.findings = len(security)
            security_info.enabled = True

        principal_brief = build_principal_brief(
            cfg, pr, view, graph, plan, senior, security, linked_issue
        )
        principal_path = write_brief(workspace.path / "PRINCIPAL_BRIEF.md", _redact_secrets(principal_brief))
        principal_spec = _agent_spec("principal-reviewer", "principal", cfg, plan)
        principal_raw, principal_info = _run_json(runner, principal_spec, principal_path, cfg)
        try:
            principal = PrincipalOutput.model_validate(principal_raw)
            findings, triage, dropped = finalize(cfg, view, principal, senior, security)
        except CriticalSuppressed as exc:
            raise ReviewFailure(str(exc), 8) from exc
        except Exception as exc:
            raise ReviewFailure(f"principal output invalid: {exc}", 5) from exc
        principal_info.accepted = sum(1 for f in findings if f.status == "accepted")
        principal_info.rejected = len(triage.rejected)
        principal_info.downgraded = sum(1 for f in findings if f.status == "downgraded")
        principal_info.added = sum(1 for f in findings if f.status == "added" or f.origin == "principal")
        principal_info.findings = len(findings)
        usage = {
            "senior": _usage_dict(senior_info),
            "security": _usage_dict(security_info) if security_info.enabled else {},
            "principal": _usage_dict(principal_info),
        }
        effort_dict = {
            "volume": plan.volume,
            "changed_lines": plan.changed_lines,
            "changed_files": plan.changed_files,
            "security_sensitive": plan.security_sensitive,
            "senior": plan.senior,
            "security": plan.security,
            "principal": plan.principal,
            "applied": plan.applied,
        }
        summary = build_summary(
            cfg,
            findings,
            triage,
            pass_usage=usage,
            effort=effort_dict,
            label_name=cfg.label,
            label_applied=False,
            graph_status=graph.status,
            security_status="run" if security_info.enabled else "skipped",
            files_changed=len(view.files),
            files_reviewed=len(selected),
            skipped=[p for p in view.files if p not in {f.path for f in selected}],
            suggestion_dropped=dropped,
            headline=principal.headline,
            what_works=principal.what_works,
            verdict=principal.verdict,
        )
        bodies = [
            render_comment(f, max_words=cfg.max_comment_words, style=cfg.comment_style)
            for f in findings
            if f.anchorable
        ]
        summary.style = summarize_style(findings, bodies, cfg.comment_style)
        report = ReviewReport(
            run_id=run_id,
            pr=PRInfo(
                repo=pr.slug,
                number=pr.number,
                head_sha=workspace.head_sha,
                base_sha=workspace.base_sha,
                url=pr.html_url,
            ),
            passes={
                "senior": senior_info,
                "security": security_info,
                "principal": principal_info,
            },
            summary=summary,
            triage=triage,
            findings=findings,
            gate={"fail_on": cfg.fail_on, "failed": gate_failed(cfg, findings)},
            usage={**usage, "total": {
                "input_tokens": sum(v.get("input_tokens", 0) for v in usage.values() if v),
                "output_tokens": sum(v.get("output_tokens", 0) for v in usage.values() if v),
                "total_tokens": sum(v.get("total_tokens", 0) for v in usage.values() if v),
                "estimated": any(v.get("estimated") for v in usage.values() if v),
            }},
            timings_ms={"total": int((time.time() - started) * 1000)},
        )
        if cfg.dry_run:
            Publisher(cfg, gh, report, view).publish()
        else:
            result = Publisher(cfg, gh, report, view).publish()
            report.summary.label["applied"] = result.label_applied
            _write_artifacts(cfg, report)
        return 6 if report.gate["failed"] else 0
    except ConfigError as exc:
        log.error("configuration error: %s", exc)
        return 2
    except GraphRequiredError as exc:
        log.error("graph required but unavailable: %s", exc)
        return 7
    except ReviewFailure as exc:
        log.error("%s", exc)
        return exc.exit_code
    except GitHubError as exc:
        log.error("github error: %s", exc)
        return 3
    except AgentError as exc:
        log.error("agent error: %s", exc)
        return 4
    except WorkspaceError as exc:
        log.error("workspace error: %s", exc)
        return 3
    except Exception as exc:  # noqa: BLE001
        log.exception("review failed: %s", exc)
        return 1
    finally:
        gh.close()
        if workspace:
            workspace.cleanup()
