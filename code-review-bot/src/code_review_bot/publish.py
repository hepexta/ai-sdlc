from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .config import Config
from .github import GitHubClient, GitHubError
from .models import ReviewReport
from .style import fingerprint, render_comment, render_summary

log = logging.getLogger(__name__)
SUMMARY_MARKER = "code-review-bot:summary:v4"


@dataclass
class PublishResult:
    summary_url: str = ""
    review_id: int | None = None
    inline_count: int = 0
    label_applied: bool = False
    warning: str = ""


def _marker_value(body: str, key: str) -> str | None:
    import re

    match = re.search(rf"<!--\s*code-review-bot:summary:v4[^>]*\b{key}=([^\s>]+)", body)
    return match.group(1) if match else None


def _find_sticky(comments: list[dict[str, Any]]) -> dict[str, Any] | None:
    for comment in comments:
        if SUMMARY_MARKER in (comment.get("body") or ""):
            return comment
    return None


def _existing_fingerprints(comments: list[dict[str, Any]]) -> set[str]:
    import re

    found: set[str] = set()
    for comment in comments:
        for match in re.finditer(r"crb:f:([a-f0-9]{8,64})", comment.get("body") or ""):
            found.add(match.group(1))
    return found


class Publisher:
    def __init__(self, cfg: Config, gh: GitHubClient, report: ReviewReport, view):
        self.cfg = cfg
        self.gh = gh
        self.report = report
        self.view = view

    def publish(self, *, label_ensured: bool = False) -> PublishResult:
        if self.cfg.dry_run:
            return self._write_dry_run()
        result = PublishResult()
        comments = self.gh.list_issue_comments(self.report.pr.number)
        sticky = _find_sticky(comments)
        summary_id = sticky.get("id") if sticky else None
        summary_body = render_summary(
            self.report,
            marker_head=self.report.pr.head_sha,
            run_id=self.report.run_id,
            label_applied=False,
            label_name=self.cfg.label,
            max_words=self.cfg.max_summary_words,
        )
        if sticky:
            updated = self.gh.update_issue_comment(sticky["id"], summary_body)
            result.summary_url = updated.get("html_url", "")
        else:
            created = self.gh.create_issue_comment(self.report.pr.number, summary_body)
            summary_id = created.get("id")
            result.summary_url = created.get("html_url", "")

        existing = _existing_fingerprints(self.gh.list_review_comments(self.report.pr.number))
        comments_payload: list[dict[str, Any]] = []
        for finding in self.report.findings:
            if not finding.anchorable:
                continue
            fp = fingerprint(finding)
            if fp in existing:
                continue
            body = render_comment(
                finding,
                max_words=self.cfg.max_comment_words,
                style=self.cfg.comment_style,
            )
            item: dict[str, Any] = {
                "path": finding.path,
                "line": finding.line,
                "side": "RIGHT",
                "body": body,
            }
            if finding.start_line and finding.start_line < finding.line:
                item["start_line"] = finding.start_line
                item["start_side"] = "RIGHT"
            comments_payload.append(item)
            if len(comments_payload) >= self.cfg.max_inline:
                break

        if comments_payload:
            review = self.gh.create_review(
                self.report.pr.number,
                commit_id=self.report.pr.head_sha,
                body=self.report.summary.headline or "Review notes are inline.",
                comments=comments_payload,
            )
            result.review_id = review.get("id")
            result.inline_count = len(comments_payload)

        if self.cfg.label:
            try:
                self.gh.add_labels(self.report.pr.number, [self.cfg.label])
                result.label_applied = True
                self.report.summary.label["applied"] = True
                summary_body = render_summary(
                    self.report,
                    marker_head=self.report.pr.head_sha,
                    run_id=self.report.run_id,
                    label_applied=True,
                    label_name=self.cfg.label,
                    max_words=self.cfg.max_summary_words,
                )
                if summary_id:
                    self.gh.update_issue_comment(summary_id, summary_body)
                else:
                    created = self.gh.create_issue_comment(self.report.pr.number, summary_body)
                    result.summary_url = created.get("html_url", result.summary_url)
            except GitHubError as exc:
                result.warning = f"label not applied: {exc}"
                warning_body = summary_body.rstrip() + (
                    f"\n\n> `{self.cfg.label}` could not be applied; rerun the review or add it manually.\n"
                )
                try:
                    if summary_id:
                        self.gh.update_issue_comment(summary_id, warning_body)
                    else:
                        self.gh.create_issue_comment(self.report.pr.number, warning_body)
                except GitHubError:
                    pass
                raise
        return result

    def _write_dry_run(self) -> PublishResult:
        out = self.cfg.output_dir
        out.mkdir(parents=True, exist_ok=True)
        (out / "review.json").write_text(
            self.report.model_dump_json(indent=2), encoding="utf-8"
        )
        summary = render_summary(
            self.report,
            marker_head=self.report.pr.head_sha,
            run_id=self.report.run_id,
            label_applied=False,
            label_name=self.cfg.label,
            max_words=self.cfg.max_summary_words,
        )
        (out / "summary.md").write_text(summary, encoding="utf-8")
        (out / "triage.json").write_text(
            self.report.triage.model_dump_json(indent=2), encoding="utf-8"
        )
        return PublishResult(summary_url=str(out / "summary.md"), inline_count=0, label_applied=False)
