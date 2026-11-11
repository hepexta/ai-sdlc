# Implementation notes

**Status:** MVP implemented on 2026-11-11. This file records what the code actually does where the planning docs are broader.

## Runtime

- Python 3.12 in the image; the host tests run on Python 3.13.
- OpenCode **1.17.3**, v1 config surface (`agent`, `permission`, `provider`, `mcp` by name).
- `code-review-graph` **2.4.0** (SQLite; no external database).
- GitHub REST API 2022-11-28; GitHub.com and GHES through `GITHUB_API_URL` / `GITHUB_SERVER_URL`.

## Module map

| Module | Responsibility |
|---|---|
| `config.py` | Env/file inputs, PR parsing, bounds, secret-file reads, GHES clone URL |
| `models.py` | Pydantic v2 pass/report/triage/summary schemas |
| `diff.py` | Parse unified diff, right-side anchor map, source selection, suggestion range validation |
| `gitops.py` | PR ref clone, merge base, diff, standards snapshot, quarantine of repo-supplied agent/secret files |
| `github.py` | PR/files/comments/reviews/labels API with retries |
| `graph.py` | `code-review-graph build` + `detect-changes --brief`; `auto`/`required`/`off` |
| `effort.py` | Volume class and Senior/Security/Principal effort map |
| `brief.py` | Context assembly for Senior/Security/Principal, including output schemas |
| `opencode_runner.py` | v1 config injection, checked-in skill copying, subprocess, NDJSON text/usage parsing, one repair |
| `triage.py` | Candidate merging, caps, suggestion validation, critical veto, gate |
| `style.py` | Human-comment lint/strip, suggestion block, secret redaction, summary |
| `publish.py` | Sticky summary, inline review, fingerprint dedupe, label last |
| `review.py` | End-to-end orchestration and exit codes |

## Pipeline

1. Load/validate config; read secrets from files.
2. `GET` PR; skip on `AI Reviewed` before clone/LLM; `FORCE` removes and continues.
3. Ensure label exists; prepare workspace (clone/fetch PR ref, merge base, diff, quarantine).
4. Build graph and brief; choose effort.
5. Senior pass → candidates.
6. Security pass if `SECURITY_PASS=always` or sensitive path/content (or skipped).
7. Principal pass → final findings + triage ledger.
8. Validate anchors and suggestions; enforce caps, nits, added-findings cap, critical veto.
9. Render human comments/summary; post sticky summary + review; add label last.
10. Write artifacts and apply `FAIL_ON` gate.

## Important behavior

- **No MCP in the LLM path.** OpenCode calls `LLM_BASE_URL` directly. `GRAPH_MCP=off` is the v1 default; the graph is a precomputed brief. `GRAPH_MCP=on` is optional.
- **Review skills are checked in.** `src/code_review_bot/skills/{mr-reviewer,mr-review-critic,security-reviewer}/SKILL.md` are copied to `.opencode/skill/` on every run; the three agent prompts name the matching skill.
- **Secrets never enter the workspace.** The provider key is in `OPENCODE_CONFIG_CONTENT` in the child environment; agent `edit`/`bash`/`webfetch`/`task` and `external_directory` are denied.
- **Repo instructions are quarantined.** `AGENTS.md`, `CLAUDE.md`, `opencode.json`, `.opencode/`, `.claude/`, `.agents/`, and `.env*` are moved aside before OpenCode starts. Their standards text is copied to `.crb/standards.md` for the brief only.
- **Suggestions** are emitted only when the range is on the right side of the diff and the replacement is non-empty/not fenced. Invalid suggestions are dropped and counted.
- **Noise caps** are deterministic too: `MAX_FINDINGS`, `MAX_INLINE`, `MAX_MINOR_INLINE`, `MAX_ADDED`, `MAX_SUGGESTIONS`, `ALLOW_NITS`. Do not rely on the Principal prompt alone.
- **Critical veto:** a Senior/Security `critical` candidate that is not represented in the final findings must have a `duplicate`, `already_addressed`, or `pre_existing` rejection; otherwise the run exits 8 and posts nothing.
- **Idempotency:** inline comments carry `<!-- crb:f:<hash> ... -->`; a re-run skips existing fingerprints. The summary is sticky by `code-review-bot:summary:v4`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success, or skipped because labeled/not open |
| 2 | Configuration error |
| 3 | GitHub, workspace, or label error |
| 4 | Agent process failure |
| 5 | Schema/JSON failure after one repair |
| 6 | `FAIL_ON` gate failed after posting |
| 7 | `GRAPH_MODE=required` and graph unavailable |
| 8 | Security pass failed, or critical candidate suppressed without acceptable evidence |

## Test evidence (2026-11-11)

- 28 pytest tests.
- Fake GitHub + fake OpenCode E2E: summary, two inline comments, suggestions, label, skip, forced re-review.
- Real OpenCode 1.17.3 + fake OpenAI-compatible LLM: config, agent, JSON event, token usage.
- Docker E2E: built image, real OpenCode in container, graph build, fake GitHub/LLM, secret files, label.
- kind smoke: image as a Job, non-root/read-only rootfs, Secret mount, `validate-config`.

## Gaps

- No live Vault/ESO or real GitHub pilot yet.
- No 30-PR eval or blind voice sample yet.
- No merge gate by default; `FAIL_ON` is opt-in.
- `GRAPH_MCP=on` is implemented as optional OpenCode config but is not exercised by the E2E suite.
- Token counts are provider-reported; if unavailable, they are estimated from brief/response character counts and marked `estimated`.
