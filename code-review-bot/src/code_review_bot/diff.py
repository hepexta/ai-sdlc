from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from unidiff import PatchSet

SOURCE_SUFFIXES = {".java", ".py"}
CONTEXT_FILES = {
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.py",
    "setup.cfg",
    "gradle.properties",
}
EXCLUDE_PARTS = {
    "node_modules",
    "vendor",
    "dist",
    "build",
    "target",
    ".venv",
    "venv",
    "__pycache__",
    "generated",
}
EXCLUDE_SUFFIXES = {
    ".lock",
    ".min.js",
    ".min.css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".jar",
    ".class",
}
SECRETISH = re.compile(r"(^|/)(\.env(\.|$)|.*\.(pem|key|p12|jks)$|id_rsa)", re.I)


@dataclass
class FileChange:
    path: str
    added: int = 0
    removed: int = 0
    is_source: bool = False
    patch_text: str = ""

    @property
    def changed_lines(self) -> int:
        return self.added + self.removed


@dataclass
class DiffView:
    patch: PatchSet
    text: str
    files: dict[str, FileChange] = field(default_factory=dict)
    anchors: dict[str, set[int]] = field(default_factory=dict)


def parse_diff(text: str) -> DiffView:
    patch = PatchSet(text)
    view = DiffView(patch=patch, text=text)
    for patched in patch:
        path = patched.path
        added = sum(1 for h in patched for line in h if line.is_added)
        removed = sum(1 for h in patched for line in h if line.is_removed)
        view.files[path] = FileChange(
            path=path,
            added=added,
            removed=removed,
            is_source=Path(path).suffix.lower() in SOURCE_SUFFIXES,
            patch_text=str(patched),
        )
        anchors: set[int] = set()
        for hunk in patched:
            for line in hunk:
                if (line.is_added or line.is_context) and line.target_line_no is not None:
                    anchors.add(int(line.target_line_no))
        view.anchors[path] = anchors
    return view


def is_excluded(path: str) -> bool:
    p = Path(path)
    if any(part in EXCLUDE_PARTS for part in p.parts):
        return True
    if p.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    if p.name.endswith((".lock", "-lock.json", "-lock.yaml")):
        return True
    if SECRETISH.search(path):
        return True
    return False


def reviewable_source_files(view: DiffView, max_files: int) -> list[FileChange]:
    selected = [
        f
        for f in view.files.values()
        if f.is_source and not is_excluded(f.path) and f.changed_lines > 0
    ]
    selected.sort(key=lambda f: (f.added + f.removed), reverse=True)
    return selected[:max_files]


def context_files(view: DiffView, max_files: int = 20) -> list[FileChange]:
    selected = [
        f
        for f in view.files.values()
        if Path(f.path).name in CONTEXT_FILES and not is_excluded(f.path)
    ]
    return selected[:max_files]


def source_change_counts(view: DiffView, max_files: int = 100) -> tuple[int, int]:
    files = reviewable_source_files(view, max_files)
    return sum(f.changed_lines for f in files), len(files)


def anchor_paths(view: DiffView) -> set[str]:
    return {p for p, lines in view.anchors.items() if lines}


def validate_suggestion(
    view: DiffView,
    path: str,
    start_line: int | None,
    line: int,
    replacement: str,
) -> tuple[bool, str]:
    if not replacement.strip():
        return False, "empty replacement"
    if "```" in replacement:
        return False, "replacement contains a code fence"
    if "\x00" in replacement:
        return False, "replacement contains a NUL byte"
    if path not in view.anchors:
        return False, "path is not in the diff"
    start = start_line or line
    if start > line:
        return False, "start_line must be <= line"
    if line not in view.anchors[path]:
        return False, "line is not on the right side of the diff"
    if any(n not in view.anchors[path] for n in range(start, line + 1)):
        return False, "suggestion range crosses an unanchored line"
    return True, ""


def anchor_finding(view: DiffView, path: str, line: int) -> bool:
    return path in view.anchors and line in view.anchors[path]


def compact_diff(view: DiffView, selected: list[FileChange], max_chars: int) -> str:
    chunks: list[str] = []
    used = 0
    for file in selected:
        text = file.patch_text
        if used + len(text) > max_chars:
            remaining = max_chars - used
            if remaining <= 200:
                break
            text = text[:remaining] + "\n... diff truncated ...\n"
        chunks.append(text)
        used += len(text)
        if used >= max_chars:
            break
    return "\n".join(chunks)
