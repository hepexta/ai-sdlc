from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse


class ConfigError(ValueError):
    """Invalid or incomplete configuration."""


@dataclass(frozen=True)
class PRReference:
    owner: str
    repo: str
    number: int

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"


def parse_pr_reference(value: str | None, repository: str | None, number: str | None) -> PRReference:
    if value:
        raw = value.strip()
        shortcut = re.fullmatch(r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)#(\d+)", raw)
        if shortcut:
            return PRReference(shortcut.group(1), shortcut.group(2), int(shortcut.group(3)))
        parsed = urlparse(raw)
        match = re.fullmatch(r"/([^/]+)/([^/]+)/pull/(\d+)/?", parsed.path)
        if parsed.scheme in {"http", "https"} and match:
            return PRReference(match.group(1), match.group(2), int(match.group(3)))
        raise ConfigError(
            "PR_URL must look like https://github.com/owner/repo/pull/123 or owner/repo#123"
        )
    if not repository or not number:
        raise ConfigError("set PR_URL, or both GITHUB_REPOSITORY and PR_NUMBER")
    match = re.fullmatch(r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", repository.strip())
    if not match or not str(number).isdigit():
        raise ConfigError("GITHUB_REPOSITORY must be owner/repo and PR_NUMBER must be an integer")
    return PRReference(match.group(1), match.group(2), int(number))


def _read_secret(env: Mapping[str, str], name: str) -> str:
    direct = (env.get(name) or "").strip()
    file_value = env.get(f"{name}_FILE")
    if direct and file_value:
        raise ConfigError(f"set either {name} or {name}_FILE, not both")
    if direct:
        return direct
    if not file_value:
        raise ConfigError(f"{name} or {name}_FILE is required")
    path = Path(file_value).expanduser()
    try:
        st = path.resolve(strict=True).stat()
    except OSError as exc:
        raise ConfigError(f"cannot read {name}_FILE at {path}: {exc}") from exc
    if not stat.S_ISREG(st.st_mode):
        raise ConfigError(f"{name}_FILE must resolve to a regular file: {path}")
    if os.name != "nt" and st.st_mode & stat.S_IWOTH:
        raise ConfigError(f"{name}_FILE must not be world-writable: {path}")
    try:
        value = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {name}_FILE at {path}: {exc}") from exc
    return value[:-1] if value.endswith("\n") else value


def _bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = (env.get(name) or "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be a boolean, got {raw!r}")


def _int(env: Mapping[str, str], name: str, default: int, minimum: int = 0) -> int:
    raw = (env.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}")
    return value


def _choice(env: Mapping[str, str], name: str, default: str, choices: set[str]) -> str:
    raw = (env.get(name) or "").strip().lower() or default
    if raw not in choices:
        raise ConfigError(f"{name} must be one of {sorted(choices)}, got {raw!r}")
    return raw


@dataclass(frozen=True)
class Config:
    pr: PRReference
    github_api_url: str
    github_token: str
    github_clone_url: str
    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    models: Mapping[str, str]
    label: str
    label_color: str
    label_description: str
    fail_on: str
    max_candidates: int
    max_findings: int
    max_inline: int
    max_files: int
    max_diff_bytes: int
    max_added: int
    allow_nits: bool
    max_minor_inline: int
    max_suggestions: int
    enable_suggestions: bool
    comment_style: str
    max_comment_words: int
    max_summary_words: int
    security_pass: str
    security_globs: tuple[str, ...]
    graph_mode: str
    graph_mcp: str
    graph_cache_dir: str
    graph_timeout: int
    agent_timeout: int
    review_timeout: int
    effort: str
    effort_mode: str
    low_max_lines: int
    medium_max_lines: int
    low_max_files: int
    medium_max_files: int
    token_accounting: str
    dry_run: bool
    force: bool
    output_dir: Path
    workspace: Path | None
    base_rev: str | None
    head_rev: str | None
    opencode_bin: str
    fake_opencode: bool
    fake_dir: Path | None
    log_level: str
    log_format: str

    @property
    def provider_id(self) -> str:
        return self.llm_provider

    def model_ref(self, role: str) -> str:
        model = self.models[role]
        if self.llm_provider == "opencode":
            return model
        return f"review-llm/{model}"

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        pr_override: str | None = None,
        dry_run: bool | None = None,
        force: bool | None = None,
        output: str | None = None,
        log_level: str | None = None,
        workspace: str | None = None,
        base_rev: str | None = None,
        head_rev: str | None = None,
        fake_opencode: bool | None = None,
        fake_dir: str | None = None,
        effort: str | None = None,
    ) -> "Config":
        e = dict(os.environ if env is None else env)
        dry_run_value = _bool(e, "DRY_RUN") if dry_run is None else dry_run
        provider = _choice(
            e, "LLM_PROVIDER", "openai-compatible", {"openai-compatible", "opencode"}
        )
        pr = parse_pr_reference(
            pr_override or e.get("PR_URL"),
            e.get("GITHUB_REPOSITORY"),
            e.get("PR_NUMBER"),
        )
        base_url = (e.get("LLM_BASE_URL") or "").strip()
        if provider == "opencode":
            base_url = ""
        else:
            if not base_url:
                raise ConfigError("LLM_BASE_URL is required")
            if not base_url.startswith(("https://", "http://")):
                raise ConfigError("LLM_BASE_URL must be an http(s) URL")
            allow_insecure = _bool(e, "ALLOW_INSECURE_LLM")
            if base_url.startswith("http://") and not allow_insecure:
                raise ConfigError("use https for LLM_BASE_URL, or set ALLOW_INSECURE_LLM=true for local tests")

        fallback = (e.get("LLM_MODEL") or "").strip()
        if provider == "opencode" and not fallback:
            fallback = "opencode/deepseek-v4.1-flash-free"
        models = {
            "senior": (e.get("LLM_MODEL_SENIOR") or fallback).strip(),
            "principal": (e.get("LLM_MODEL_PRINCIPAL") or fallback).strip(),
            "security": (e.get("LLM_MODEL_SECURITY") or e.get("LLM_MODEL_PRINCIPAL") or fallback).strip(),
        }
        missing = [role for role, model in models.items() if not model]
        if missing:
            raise ConfigError(
                "set LLM_MODEL or all role models; missing: " + ", ".join(missing)
            )
        if provider == "opencode":
            bad = [role for role, model in models.items() if "/" not in model]
            if bad:
                raise ConfigError(
                    "LLM_PROVIDER=opencode requires full provider/model IDs; bad: " + ", ".join(bad)
                )
        effort_mode = _choice(e, "EFFORT_MODE", "variant", {"variant", "prompt"})
        if effort_mode == "variant":
            bad = [role for role, model in models.items() if "#" in model]
            if bad:
                raise ConfigError("role model IDs must not contain '#' in variant mode: " + ", ".join(bad))

        comment_style = _choice(e, "COMMENT_STYLE", "human", {"human", "structured"})
        max_words = _int(e, "MAX_COMMENT_WORDS", 120, 20)
        if comment_style == "human" and not 60 <= max_words <= 160:
            raise ConfigError("MAX_COMMENT_WORDS must be between 60 and 160 in human mode")
        max_summary_words = _int(e, "MAX_SUMMARY_WORDS", 250, 50)
        if not 150 <= max_summary_words <= 400:
            raise ConfigError("MAX_SUMMARY_WORDS must be between 150 and 400")

        low_lines = _int(e, "EFFORT_LOW_MAX_LINES", 150, 1)
        medium_lines = _int(e, "EFFORT_MEDIUM_MAX_LINES", 600, low_lines + 1)
        low_files = _int(e, "EFFORT_LOW_MAX_FILES", 5, 1)
        medium_files = _int(e, "EFFORT_MEDIUM_MAX_FILES", 20, low_files + 1)

        max_inline = _int(e, "MAX_INLINE", 10, 0)
        max_suggestions = _int(e, "MAX_SUGGESTIONS", min(10, max_inline), 0)
        if max_suggestions > max_inline:
            raise ConfigError("MAX_SUGGESTIONS cannot exceed MAX_INLINE")

        label = (e.get("AI_REVIEWED_LABEL", "AI Reviewed") or "").strip()
        if label and (len(label) > 50 or "\n" in label):
            raise ConfigError("AI_REVIEWED_LABEL must be <= 50 characters and one line")

        api_key = "" if provider == "opencode" else _read_secret(e, "LLM_API_KEY")
        try:
            github_token = _read_secret(e, "GITHUB_TOKEN")
        except ConfigError:
            if dry_run_value and _bool(e, "ALLOW_ANONYMOUS_GITHUB"):
                github_token = ""
            else:
                raise

        effort = (effort or e.get("REASONING_EFFORT") or "auto").strip().lower()
        if effort not in {"auto", "low", "medium", "high"}:
            raise ConfigError("REASONING_EFFORT must be auto, low, medium, or high")

        server_url = (e.get("GITHUB_SERVER_URL") or "https://github.com").rstrip("/")
        clone_url = (e.get("GITHUB_CLONE_URL") or f"{server_url}/{pr.owner}/{pr.repo}.git").strip()

        return cls(
            pr=pr,
            github_api_url=(e.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/"),
            github_token=github_token,
            github_clone_url=clone_url,
            llm_provider=provider,
            llm_base_url=base_url.rstrip("/"),
            llm_api_key=api_key,
            models=models,
            label=label,
            label_color=(e.get("AI_REVIEWED_LABEL_COLOR") or "0E8A16").strip(),
            label_description=(e.get("AI_REVIEWED_LABEL_DESCRIPTION") or "Reviewed by code-review-bot").strip(),
            fail_on=_choice(e, "FAIL_ON", "none", {"none", "critical", "major"}),
            max_candidates=_int(e, "MAX_CANDIDATES", 30, 1),
            max_findings=_int(e, "MAX_FINDINGS", 15, 0),
            max_inline=max_inline,
            max_files=_int(e, "MAX_FILES", 100, 1),
            max_diff_bytes=_int(e, "MAX_DIFF_BYTES", 1_500_000, 1000),
            max_added=_int(e, "MAX_ADDED", 5, 0),
            allow_nits=_bool(e, "ALLOW_NITS"),
            max_minor_inline=_int(e, "MAX_MINOR_INLINE", 1, 0),
            max_suggestions=max_suggestions,
            enable_suggestions=_bool(e, "ENABLE_SUGGESTIONS", True),
            comment_style=comment_style,
            max_comment_words=max_words,
            max_summary_words=max_summary_words,
            security_pass=_choice(e, "SECURITY_PASS", "auto", {"auto", "always", "off"}),
            security_globs=tuple(
                p.strip() for p in (e.get("SECURITY_SENSITIVE_GLOBS") or "").split(",") if p.strip()
            ),
            graph_mode=_choice(e, "GRAPH_MODE", "auto", {"auto", "required", "off"}),
            graph_mcp=_choice(e, "GRAPH_MCP", "off", {"on", "off"}),
            graph_cache_dir=(e.get("GRAPH_CACHE_DIR") or "/cache/code-review-graph").strip(),
            graph_timeout=_int(e, "GRAPH_TIMEOUT_SECONDS", 240, 10),
            agent_timeout=_int(e, "AGENT_TIMEOUT_SECONDS", 300, 10),
            review_timeout=_int(e, "REVIEW_TIMEOUT_SECONDS", 1500, 30),
            effort=effort,
            effort_mode=effort_mode,
            low_max_lines=low_lines,
            medium_max_lines=medium_lines,
            low_max_files=low_files,
            medium_max_files=medium_files,
            token_accounting=_choice(e, "TOKEN_ACCOUNTING", "auto", {"auto", "provider", "estimate"}),
            dry_run=dry_run_value,
            force=_bool(e, "FORCE") if force is None else force,
            output_dir=Path(output or e.get("OUTPUT_DIR") or "out"),
            workspace=Path(workspace or e["CRB_WORKSPACE"]) if (workspace or e.get("CRB_WORKSPACE")) else None,
            base_rev=base_rev or e.get("CRB_BASE_REV"),
            head_rev=head_rev or e.get("CRB_HEAD_REV"),
            opencode_bin=(e.get("OPENCODE_BIN") or "opencode").strip(),
            fake_opencode=_bool(e, "CRB_FAKE_OPENCODE") if fake_opencode is None else fake_opencode,
            fake_dir=Path(fake_dir or e["CRB_FAKE_DIR"]) if (fake_dir or e.get("CRB_FAKE_DIR")) else None,
            log_level=(log_level or e.get("LOG_LEVEL") or "info").lower(),
            log_format=(e.get("LOG_FORMAT") or "text").lower(),
        )

    def redacted(self) -> dict[str, object]:
        return {
            "pr": self.pr.slug + "#" + str(self.pr.number),
            "github_api_url": self.github_api_url,
            "llm_provider": self.llm_provider,
            "llm_base_url": self.llm_base_url,
            "models": dict(self.models),
            "label": self.label,
            "fail_on": self.fail_on,
            "security_pass": self.security_pass,
            "graph_mode": self.graph_mode,
            "graph_mcp": self.graph_mcp,
            "effort": self.effort,
            "effort_mode": self.effort_mode,
            "comment_style": self.comment_style,
            "dry_run": self.dry_run,
            "force": self.force,
            "fake_opencode": self.fake_opencode,
        }
