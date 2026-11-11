# 0001 — AI-Accelerated Java/Python Code Review Bot

**Status:** In Progress
**Labels:** In Progress
**Type:** Feature
**Project:** code-review-bot
**Created:** 2026-11-11
**Updated:** 2026-11-11
**Owner:** unassigned

## Description

**Problem:** Java and Python PR review is slow and inconsistent. A single-pass AI reviewer either misses architecture/security problems or floods the author with technically-true but low-value comments. Both waste the time the bot should save.

**Outcome:** A single-use container that reviews a GitHub PR with **two distinct reviews**:

1. **Senior Engineer** — broad, high-recall candidate generation across Standards, Spec, SOLID, language idioms, and security baseline.
2. **Principal/Staff Engineer** — fresh-context audit that rejects low-value comments, adds only material issues, and sets the final verdict.

A **Security Specialist** runs between them on sensitive diffs. Only the Principal's curated findings are posted, with optional GitHub suggestions, a compact token/count summary, and the `AI Reviewed` label. Reasoning effort is selected from the PR's changed volume. Comments read like a senior reviewer, not a report.

**In scope:**

- Java/Python PR review on GitHub.com and GitHub Enterprise Server.
- Senior → (Security) → Principal pipeline with triage ledger and noise budget.
- Standards, Spec, SOLID/design, best practices, correctness, tests, performance, security.
- Conditional deep security: OWASP ASVS 5.0, Top 10:2025, CWE Top 25.
- Code graph via `code-review-graph`; OpenCode headless runtime; pinned skills.
- Line comments with optional applyable suggestions; human-style voice.
- Summary with token burn, issue counts, effort, label state.
- `AI Reviewed` skip gate; automatic low/medium/high effort.
- Docker/K8s one-shot sidecar; Vault/ESO secrets; idempotent re-runs.

**Out of scope:**

- Auto-fixing, pushing commits, or opening PRs.
- GitHub App, webhook service, or long-running daemon.
- GitLab/Bitbucket/Azure DevOps/Gerrit.
- Languages other than Java/Python.
- Compiling, running tests, or replacing a full SAST platform.
- Hosting an LLM or a UI/dashboard.
- Impersonating a human or hiding the bot identity.

**Success looks like:**

1. Senior → (Security) → Principal runs end to end and posts a curated review.
2. Every inline comment is line-anchored; unanchorable findings go to summary; zero invalid anchors.
3. Eval (30 PRs / 90 defects): Senior candidate recall ≥ 0.75, final precision ≥ 0.80, final recall ≥ 0.55, critical recall ≥ 0.95.
4. Security recall ≥ 0.80, zero critical security false negatives.
5. Principal rejects 30–60% of candidates with zero false rejections of true critical/security findings; median ≤ 4 inline comments, ≤ 1 inline per 100 changed lines, zero inline nits.
6. p95 ≤ 15 min two-pass; ≤ 20 min with security.
7. Comments pass the human-voice lint and ≥ 80% of a blind sample read as human-written.
8. A labeled PR is skipped with zero LLM calls; a successful review adds `AI Reviewed`.
9. Secrets come from Vault via ESO; the pod has no Vault token; no secret value is in Git or manifests.
10. Done is justified by tests, eval for all passes, and a real pilot PR.

## User Prompt

> new issue intend. I need AI accelerated code review bot for java/python based on the best (most stars) Ai skills. It should be running in docker/kubernetes as a single used sidecar. It should be running with opencode. It shoule use Code Graph. It should have input parameters as LLM endpoint, LLM API keys, github token for a PR.
> Follow C:\Work\Projects\AI\mattpocock-skills for planning Use C:\Work\Projects\AI\ai-sdlc\.scratch for issues tracking. Labels
> Draft, In Progress, In Review, Done. Generate C:\Work\Projects\AI\ai-sdlc\.scratch\README.md file and C:\Work\Projects\AI\ai-sdlc\.scratch\TEMPLATE.md file: Description, User Prompt, Context, Plan, Open Questions, Notes
> Use C:\Work\Projects\AI\ai-sdlc as parent folder for code-review-bot.

**Follow-up (revision 2):**

> I would have code reviewer to do a review twice: once by Senior engineer Skill based bot, and then by principle staf engineer to double check after and maybe add more, reject not important comments to avoid overworking. solid principles, best practices, etc, maybe there is something already in github for the same. also we need to have very good security skills

**Follow-up (revision 4):**

> code reviewer bot should generate comments for a line with suggestion (if available) use github_token to submit comments and generate code review summary: how many tokens the review burn, how many issues fount, accepted/rejected. after the review the bot should add Label: "AI Reviewed"
> When the label is there, the bot skip the review. Also we need automatic selection of reasoning effort (low, medium, high, depending on volume PR has changed)

**Follow-up (revision 5):**

> Bot comment shoul be looking "human like"

**Interpretation:**

- **Review twice** = two different jobs, not the same prompt twice. Security is a conditional specialist, not a third general review.
- **Reject not important comments** is a triage ledger and noise budget, not a prompt hint.
- **SOLID/best practices** are flagged only with a concrete change-amplification/testability/dependency cost.
- **Existing GitHub work** was researched; the bot composes the best personas, not a full engine (see Context).
- **Security** gets a deep skill and a specialist pass with a critical-finding veto.
- **Human-like** means natural senior-reviewer prose, not impersonation; the bot account stays visible.
- **Fount** = found.

### User Inputs

Secrets are file paths or references, never values in the issue, manifests, or CLI arguments.

| Input | Required | Form | Purpose |
|---|---|---|---|
| PR reference | Yes | `PR_URL` or `GITHUB_REPOSITORY` + `PR_NUMBER` | PR to review |
| LLM endpoint | Yes | `LLM_BASE_URL` | OpenAI-compatible chat endpoint |
| LLM API key | Yes | `LLM_API_KEY_FILE` (or `LLM_API_KEY`) | LLM auth; file form in K8s |
| LLM model(s) | Yes | `LLM_MODEL`, or `LLM_MODEL_SENIOR` / `_PRINCIPAL` / `_SECURITY` | Role models; `LLM_MODEL` is fallback |
| GitHub token | Yes | `GITHUB_TOKEN_FILE` (or `GITHUB_TOKEN`) | PR read, comments, summary, label |
| GitHub API URL | No | `GITHUB_API_URL` | GitHub Enterprise Server |
| AI Reviewed label | No | `AI_REVIEWED_LABEL` | Skip/post-review label; empty disables |
| Reasoning effort | No | `REASONING_EFFORT=auto` (or low/medium/high) | Manual override; auto by volume |
| Preview/force | No | `DRY_RUN`, `FORCE` | No writes; override label skip |

```yaml
env:
  - { name: PR_URL, value: "https://github.com/acme/service/pull/42" }
  - { name: LLM_BASE_URL, value: "https://llm.example/v1" }
  - { name: LLM_MODEL_SENIOR, value: "acme/reviewer-fast" }
  - { name: LLM_MODEL_PRINCIPAL, value: "acme/reviewer-strong" }
  - { name: LLM_API_KEY_FILE, value: "/run/secrets/llm_api_key" }
  - { name: GITHUB_TOKEN_FILE, value: "/run/secrets/github_token" }
```

Full validation/defaults: [Input contract](../code-review-bot/docs/PLAN.md#input-contract).

## Context

### Current state

- `ai-sdlc` is new: `.scratch/` tracker + this issue; `code-review-bot/` has docs only.
- No git remote, CI, registry, or cluster is configured yet.
- Dev host is Windows; runtime target is Linux containers.
- Existing Vault/ESO platform is under `agents-infra/k8s-cluster`: ESO `2.12.0`, `ClusterSecretStore/vault-local`, scoped token, `ExternalSecret` pattern.

### Constraints

- One container, one PR, one run; no daemon/queue.
- BYO OpenAI-compatible LLM; tool calling + ≥64k context.
- Senior and Principal always run; Security conditional.
- GitHub token only; least-privilege PAT/installation token.
- Read-only agents: no edits, shell, web, or subagents.
- Java/Python source only; no build/test execution.
- 2 CPU / 3 GiB / 25-minute hard deadline.
- Vault KV v2 is source of truth; ESO delivers a Kubernetes Secret; bot reads `*_FILE`.
- `AI Reviewed` is a manual gate; failed publish must not leave a false label.
- Suggestions only for exact, local, complete replacements.
- Comments ≤ 120 words target, 160 hard cap; no report scaffolding/AI tells/visible model metadata.
- MIT/Apache vendored skills; runtime deps OSI-compatible.

### Prior art

| Piece | Snapshot | Use |
|---|---|---|
| [OpenCode](https://github.com/anomalyco/opencode) | 226,021★, MIT, `7bac5ba` | Headless runtime; skills/agents |
| [code-review-graph](https://github.com/tirth8205/code-review-graph) | 32,713★, MIT, `29d8bd9` | Java/Python graph, optional MCP, SQLite |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 321,447★, MIT, `4ae2317` | Two-axis review spine |
| [obra/superpowers](https://github.com/obra/superpowers) | 315,986★, MIT, `22f0b46` | Verification-before-completion |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 115,511★, MIT, `301b02b` | Five axes, severity, drop-if-ruled-out |
| [cloudflare/security-audit](https://github.com/cloudflare/security-audit-skill) | 69,790★, MIT, `c1c8a8c` | Attack classes |
| [VoltAgent](https://github.com/VoltAgent/awesome-claude-code-subagents) | 26,482★, MIT, `ed74d11` | `surgeon-reviewer`, `ponder-auditor` personas |
| [wshobson/agents](https://github.com/wshobson/agents) | 42,409★, MIT, `9c61ab2` | OpenCode-compatible reference |
| [solid-skills](https://github.com/ramziddin/solid-skills) | 632★, MIT, `94978c9` | SOLID/TDD reference |
| [Open Code Review](https://github.com/alibaba/open-code-review) | 49,823★, Apache-2.0 | Benchmark/hybrid reference |

**Existing GitHub answer:** persona libraries and full engines exist, but none combines Senior → Principal triage + code graph + OpenCode + one-shot sidecar + GitHub publishing. The bot is a composition. Detail: [research §3.1](./research/2026-11-11-code-review-bot-landscape.md#31-tiered-review-and-noise-control-prior-art).

### Assumptions

- Endpoint supports OpenAI-compatible tool calls and per-role model IDs.
- GitHub token can read/write PRs and Issues (labels).
- ESO/Vault store exists; local uses `vault-local`.
- Models expose effort variants, or prompt-level effort fallback is acceptable.
- Token usage is provider-reported; otherwise estimate and mark it.

## Plan

### Architecture

```
GitHub PR → Orchestrator (Python, one-shot)
  ├─ labels/skip → workspace → code graph → shared brief
  ├─ Senior review (high recall)
  ├─ Security specialist (conditional)
  ├─ Principal review (audit + add + reject)
  └─ normalize → summary + inline comments + suggestions → AI Reviewed
```

**LLM vs MCP:** OpenCode's provider client calls `LLM_BASE_URL` directly over HTTPS — no local proxy and no MCP in the LLM path. MCP, if enabled, only exposes code-graph tools to the agent. It holds no credentials and needs no HTTP port.

### Runtime flow

1. Validate inputs; preflight distinct models.
2. Fetch PR + labels. If `AI Reviewed` and not `FORCE`, exit 0 before clone/LLM. If forced, remove label.
3. Check out head, merge-base, sanitize, size limits.
4. Build/update graph; capture compact brief; optional MCP only if `GRAPH_MCP=on`; degrade if allowed.
5. Build brief; select effort from volume; redact secrets.
6. Senior → candidates.
7. Security if triggered; failure on required pass = exit 8.
8. Principal → final findings, triage, suggestions.
9. Normalize anchors/suggestions/tokens/counts.
10. Publish summary + review; add label last; exit 0/6/8.

### Review passes

| Pass | Job | Output | Must not |
|---|---|---|---|
| Senior | Broad high-recall review; Standards/Spec/SOLID/language/security baseline | 8–30 candidates with evidence/impact/confidence | Filter importance, post, nits |
| Security | Attack paths and defense gaps on sensitive diffs; CWE/ASVS refs | 0–10 security findings, fail closed | Generic advice, style |
| Principal | Audit candidates, reject noise, add ≤ 5 material issues, verdict, suggestions | Final findings, triage ledger, "leave it alone" list | Rubber-stamp, scope creep, nits |

- Principal rejection reasons: `style`, `speculative`, `out_of_scope`, `pre_existing`, `already_addressed`, `duplicate`, `tooling`, `low_impact`, `unproven`, `tests_unchanged`, `nit`.
- Noise budget: ≤ 15 final, ≤ 10 inline, ≤ 1 inline minor, 0 inline nits; reject 30–60%.
- Critical veto: no proven `critical` (security or correctness) rejection without contrary evidence; escalate if unsure.
- Detail: [Review pipeline](../code-review-bot/docs/PLAN.md#review-passes).

### Comments, suggestions, voice

- Only Principal-final findings become inline comments; one issue per comment.
- Suggestion blocks only when exact/local/complete; validate `start_line`/`line` on the right side; invalid → prose only.
- Visible body: 1–3 short paragraphs, problem + consequence then fix; no headings, bold scaffolding, emojis, AI tells, or visible model/confidence/run metadata.
- Severity in natural phrasing plus a hidden marker; metrics only in summary footer.
- Bot account remains visible; no impersonation.
- Lint → one repair → deterministic strip; never block a valid finding.
- Detail: [Comment voice](../code-review-bot/docs/COMMENT_STYLE.md).

### Security

- Deep skill grounded in OWASP ASVS 5.0, Top 10:2025, CWE Top 25.
- Trigger on auth, crypto, secrets, SQL/ORM, deserialization, XML, upload/path, SSRF, subprocess/eval, dependencies, IaC, CORS/CSRF, Actuator.
- Evidence: source → sink → trust boundary → precondition → impact; cite CWE/ASVS.
- Critical only for realistic exploitability; no security nits.
- Principal may not suppress a proven critical security finding; required pass failure exits 8.
- Detail: [Review pipeline](../code-review-bot/docs/PLAN.md) (security section).

### Output and summary

- Artifact: `review.json`, `summary.md`, `triage.json`; optional per-pass context/NDJSON.
- Summary verdict: `ship` / `ship_with_fixes` / `do_not_ship` in hidden marker; visible prose is human.
- Summary footer: tokens total/per pass, found/accepted/rejected/downgraded/added/posted, suggestions, effort, label.
- Tokens: provider first; estimate marked; `unavailable` if impossible.
- Schema `4.0`; full contract: [Plan § Output](../code-review-bot/docs/PLAN.md#output-contract).

### AI Reviewed label

- Default exact label `AI Reviewed`; color `0E8A16`.
- Check labels before clone/LLM; skip if present.
- `FORCE` removes label first, re-adds only after success.
- Ensure label exists before LLM; add last, after summary + review; failure = exit 3 + summary warning.
- Dry run/security failure: no label. Gate failure after publish: label added, exit 6.
- New commits while labeled are skipped; remove label to re-review.
- Table/API details: [Delivery § label](../code-review-bot/docs/DELIVERY.md#ai-reviewed-label-and-skip).

### Reasoning effort

| Volume | Rule | Senior | Security | Principal |
|---|---|---|---|---|
| small | ≤150 lines and ≤5 files | low | medium | medium |
| medium | ≤600 lines and ≤20 files | medium | high | high |
| large | larger | high | high | high |

- Security-sensitive/high graph risk: Security + Principal high; Senior stays volume-based.
- `EFFORT_MODE=variant` uses `#low/#medium/#high`; `prompt` fallback; record applied effort.
- Detail: [Plan § effort](../code-review-bot/docs/PLAN.md#reasoning-effort).

### Platform

- **LLM path:** OpenCode calls `LLM_BASE_URL` directly; no local proxy and no MCP in LLM traffic.
- **Code graph:** `code-review-graph` build/update + compact graph brief required; optional local stdio MCP only when `GRAPH_MCP=on` (default `off` in v1); `GRAPH_MODE=auto|required|off`.
- **OpenCode:** generated config, read-only permissions, separate fresh sessions, JSON NDJSON; no `--auto`.
- **GitHub:** sticky summary v4, inline review `COMMENT`, hidden fingerprints, label last; token scopes Metadata/Contents read, PR read-write, Issues read-write.
- **Container:** non-root 10001, read-only rootfs, drop caps, 3 GiB / 1500 s, Job/initContainer; never a long-running sidecar.
- **Secrets:** Vault KV v2 `secret/agents-infra/<profile>/code-review-bot` → ESO `code-review-bot-secrets` → `/run/secrets/*`; no Vault token in pod.
- **Docs:** [Delivery](../code-review-bot/docs/DELIVERY.md), [Secrets](../code-review-bot/docs/SECRETS.md).

### Testing and evaluation

- Unit: config/model fallback, diff/anchors, schema, dedupe, noise, security trigger, effort classifier, suggestion ranges, label skip/force, token counts, style lint.
- Contract: pass JSON, triage, suggestions, `comment_body`, usage events, label API.
- E2E: Docker + fixture repo + fake GitHub/LLM; label skip/force, suggestions, summary, human voice.
- Eval: 30 PRs / 90 defects (Java, Python, architecture/SOLID, security, noise); metrics from success criteria.
- Voice: deterministic lint 100%; blind human sample ≥ 80% human-like.
- Acceptance detail: [Delivery § testing](../code-review-bot/docs/DELIVERY.md#testing-and-evaluation).

### Milestones

| # | Deliverable | Blocked by |
|---|---|---|
| 01 | Foundation: CLI/config/schema/fixtures/fakes | — |
| 02 | GitHub intake, workspace, diff anchors | 01 |
| 03 | Code graph + brief + optional MCP + fallback | 02 |
| 04 | Senior review + volume/effort | 03 |
| 05 | Security specialist + deep skill | 03 |
| 06 | Principal review + triage + suggestions | 04, 05 |
| 07 | Publishing: summary, label, idempotency, gate | 06 |
| 08 | Container/K8s + Vault/ESO + docs | 07 |
| 09 | Eval, hardening, release `v0.1.0` | 08 |

### Risks and rollout

Top risks: correlated model blind spots, Principal over/under-rejection, security false negatives, bad suggestions, stale `AI Reviewed` label, style drift, cost/latency, supply chain, graph gaps, Vault/ESO outage.

Rollout: seed Vault + verify ESO → local dry run → shadow 5 PRs → model comparison → pilot comment-only → opt-in `FAIL_ON=critical` → widen after two clean eval runs.

## Open Questions

Only blocking questions here; full 29-question list: [OPEN_QUESTIONS.md](../code-review-bot/docs/OPEN_QUESTIONS.md).

| ID | Question | Default |
|---|---|---|
| Q1 | Sidecar lifecycle: Job, initContainer, or multi-container Job pod? | Standalone Job; initContainer example; never long-running |
| Q2 | LLM protocol: OpenAI-compatible only or native Anthropic/Gemini/Azure? | OpenAI-compatible v1; adapter later |
| Q3 | Trigger: one-shot CI/Job or long-running watcher? | One-shot; no webhook |
| Q4 | Block merges or comment only? | Comment only; `FAIL_ON=critical` opt-in |
| Q5 | Is the noise budget right? | 15/10/1/0; median ≤4 inline; reject 30–60% |
| Q6 | Java depth: source-only or build-aware? | Source-only + Spring graph; revisit after eval |
| Q15 | Must Senior/Principal models differ? | Same endpoint/key; different stronger Principal recommended |
| Q16 | Security Specialist separate pass or Principal mode? | Separate conditional pass, feeds Principal |
| Q17 | Principal authority and critical veto? | Full over non-security; critical veto; escalate if unsure |
| Q21 | Vault tenancy: reuse `vault-local` or dedicated store? | Reuse local; production dedicated Kubernetes auth |
| Q24 | Label on new commit/docs-only? | New commits skipped until removed; docs-only gets label |
| Q28 | How human-like, and what stays visible? | Natural prose, bot visible, no impersonation, hidden metadata |

## Notes

### Research

Full cited dossier: [2026-11-11 landscape research](./research/2026-11-11-code-review-bot-landscape.md). Star counts are a 2026-11-11 snapshot; every dependency is pinned and must pass its eval.

### Decisions

- Two general reviews (Senior → Principal) + conditional Security.
- Principal has explicit reject authority, triage ledger, noise budget, critical veto.
- Comments are human-style; metrics only in summary footer; bot identity visible.
- Suggestions only for exact local fixes; author applies.
- `AI Reviewed` label is a manual gate; add last, skip by default, `FORCE` override.
- Effort auto-selected from volume; variant/prompt fallback recorded.
- Vault/ESO is the secret path; pod never holds a Vault token.
- LLM traffic goes directly from OpenCode to `LLM_BASE_URL`; MCP is only an optional graph-tool transport, not an LLM proxy. v1 uses the precomputed graph brief and leaves MCP off.
- Vendor and pin skills; no runtime skill fetch.
- One-shot Job/initContainer; no long-running sidecar.
- Comment-only by default; gate opt-in.
- Implemented against **OpenCode 1.17.3** (v1 `agent`/`permission`/`provider` config), not the 2.x config shape in the earlier planning draft. `GRAPH_MCP` stays off; the graph brief is the v1 path.

### Implementation (2026-11-11)

- Python 3.12 package, CLI, Dockerfile, K8s Job/ExternalSecret/NetworkPolicy in [`code-review-bot`](../code-review-bot).
- OpenCode 1.17.3 invoked with `--format json --variant --dir --pure`; provider key injected through `OPENCODE_CONFIG_CONTENT`, never written to the workspace.
- `code-review-graph` 2.4.0 pinned; graph brief required, MCP optional/off.
- 17 tests pass: unit, fake GitHub/OpenCode E2E, real OpenCode + fake LLM, Docker E2E, manifests.
- Local kind smoke (`scripts/k8s-smoke.ps1`) ran the image as a Job with read-only rootfs and a Secret-mounted config; passed.
- Still outstanding: live Vault/ESO verification, real GitHub pilot, 30-PR eval, blind voice sample.

### Changelog

- **2026-11-11 — revision 8.** Implementation started: Python pipeline, Docker image, OpenCode 1.17.3 v1 config, K8s Job/ExternalSecret/NetworkPolicy, fake and real E2E tests, kind smoke. Issue moved to `In Progress`.

- **2026-11-11 — revision 7.** Clarified that MCP is not in the LLM path: OpenCode calls the LLM endpoint directly, and the graph MCP is an optional `GRAPH_MCP=on` enhancement; v1 uses a precomputed graph brief with MCP off.
- **2026-11-11 — revision 6.** Split the detailed plan into [PLAN.md](../code-review-bot/docs/PLAN.md), [DELIVERY.md](../code-review-bot/docs/DELIVERY.md), and [OPEN_QUESTIONS.md](../code-review-bot/docs/OPEN_QUESTIONS.md); this issue is now the ≤500-line entry point. Added the issue-size rule to [AGENTS.md](../AGENTS.md).
- **2026-11-11 — revision 5.** Human-like comment voice, style lint, prose summary, schema 4.0.
- **2026-11-11 — revision 4.** Suggestions, token/count summary, `AI Reviewed`, auto effort.
- **2026-11-11 — revision 3.** Vault/ESO secrets.
- **2026-11-11 — revision 2.** Senior/Principal two-pass, SOLID, security specialist.
- **2026-11-11 — revision 1.** Initial issue and tracker.

### Next actions

1. Resolve/accept the remaining P0 questions: Q1–Q4, Q15–Q17.
2. Seed the Vault path and verify the `ExternalSecret` against a live cluster.
3. Run a real pilot PR, then the 30-PR eval and the 20-comment voice sample.
