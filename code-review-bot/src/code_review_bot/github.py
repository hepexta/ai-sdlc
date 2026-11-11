from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx


class GitHubError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass
class PullRequest:
    owner: str
    repo: str
    number: int
    title: str
    body: str
    state: str
    base_ref: str
    base_sha: str
    head_sha: str
    labels: list[str] = field(default_factory=list)
    html_url: str = ""

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"


class GitHubClient:
    def __init__(self, base_url: str, token: str, owner: str, repo: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.owner = owner
        self.repo = repo
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "code-review-bot/0.1",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        last: Exception | None = None
        for attempt in range(5):
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                last = exc
                time.sleep(min(8, 2**attempt))
                continue
            if response.status_code in {429, 500, 502, 503, 504}:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else min(8, 2**attempt)
                time.sleep(delay)
                last = GitHubError(f"GitHub returned {response.status_code}", response.status_code)
                continue
            if response.status_code >= 400:
                detail = response.text[:500]
                raise GitHubError(
                    f"GitHub {method} {path} failed with {response.status_code}: {detail}",
                    response.status_code,
                )
            if response.status_code == 204 or not response.content:
                return None
            return response.json()
        raise GitHubError(f"GitHub request failed after retries: {last}")

    @property
    def repo_path(self) -> str:
        return f"/repos/{self.owner}/{self.repo}"

    def get_pull(self, number: int) -> PullRequest:
        data = self._request("GET", f"{self.repo_path}/pulls/{number}")
        return PullRequest(
            owner=self.owner,
            repo=self.repo,
            number=number,
            title=data.get("title", ""),
            body=data.get("body") or "",
            state=data.get("state", ""),
            base_ref=(data.get("base") or {}).get("ref", ""),
            base_sha=(data.get("base") or {}).get("sha", ""),
            head_sha=(data.get("head") or {}).get("sha", ""),
            labels=[label.get("name", "") for label in data.get("labels", [])],
            html_url=data.get("html_url", ""),
        )

    def list_files(self, number: int, max_files: int = 100) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        page = 1
        while len(out) < max_files:
            batch = self._request(
                "GET",
                f"{self.repo_path}/pulls/{number}/files",
                params={"per_page": min(100, max_files - len(out)), "page": page},
            )
            if not batch:
                break
            out.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return out[:max_files]

    def get_issue(self, number: int) -> dict[str, Any]:
        return self._request("GET", f"{self.repo_path}/issues/{number}")

    def list_issue_comments(self, number: int) -> list[dict[str, Any]]:
        return self._request(
            "GET", f"{self.repo_path}/issues/{number}/comments", params={"per_page": 100}
        ) or []

    def create_issue_comment(self, number: int, body: str) -> dict[str, Any]:
        return self._request("POST", f"{self.repo_path}/issues/{number}/comments", json={"body": body})

    def update_issue_comment(self, comment_id: int, body: str) -> dict[str, Any]:
        return self._request("PATCH", f"{self.repo_path}/issues/comments/{comment_id}", json={"body": body})

    def list_review_comments(self, number: int) -> list[dict[str, Any]]:
        return self._request(
            "GET", f"{self.repo_path}/pulls/{number}/comments", params={"per_page": 100}
        ) or []

    def create_review(
        self,
        number: int,
        *,
        commit_id: str,
        body: str,
        comments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"commit_id": commit_id, "event": "COMMENT", "body": body}
        if comments:
            payload["comments"] = comments
        return self._request("POST", f"{self.repo_path}/pulls/{number}/reviews", json=payload)

    def add_labels(self, number: int, labels: list[str]) -> Any:
        return self._request(
            "POST", f"{self.repo_path}/issues/{number}/labels", json={"labels": labels}
        )

    def remove_label(self, number: int, label: str) -> Any:
        return self._request(
            "DELETE", f"{self.repo_path}/issues/{number}/labels/{quote(label, safe='')}"
        )

    def get_label(self, label: str) -> dict[str, Any] | None:
        try:
            return self._request("GET", f"{self.repo_path}/labels/{quote(label, safe='')}")
        except GitHubError as exc:
            if exc.status == 404:
                return None
            raise

    def ensure_label(self, label: str, color: str, description: str) -> dict[str, Any]:
        existing = self.get_label(label)
        if existing:
            return existing
        try:
            return self._request(
                "POST",
                f"{self.repo_path}/labels",
                json={"name": label, "color": color, "description": description[:100]},
            )
        except GitHubError as exc:
            if exc.status == 422:
                existing = self.get_label(label)
                if existing:
                    return existing
            raise

    def linked_issue_number(self, pr: PullRequest) -> int | None:
        import re

        match = re.search(r"(?:closes|fixes|resolves)\s+#(\d+)", pr.body, re.I)
        if match:
            return int(match.group(1))
        return None
