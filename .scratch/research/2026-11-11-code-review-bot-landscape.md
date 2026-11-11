# AI Code Review Bot — Landscape Research

**Date:** 2026-11-11
**Revision:** 2 — added tiered-review/noise-control and deeper security prior art.
**Purpose:** Choose the runtime, code-graph layer, and review skills for `code-review-bot`, using the most-starred open AI-skill repositories as the primary signal.
**Status:** Research complete; decisions proposed in [issue 0001](../0001-code-review-bot.md).

> **Method.** Star counts and licences were read from the GitHub REST API on 2026-11-11. Commit SHAs were pinned with `git ls-remote`. Capabilities were read from each project's primary README or official docs, not from secondary listicles. Stars are a popularity proxy, not a quality guarantee; every selected dependency is pinned to a commit and still needs its own evaluation.

---

## 1. The most-starred AI skill repositories

| Repository | Stars | Licence | Pinned commit | What it is |
|---|---:|---|---|---|
| [mattpocock/skills](https://github.com/mattpocock/skills) | 321,447 | MIT | `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d` | Small, composable engineering skills; includes the two-axis `code-review` skill |
| [obra/superpowers](https://github.com/obra/superpowers) | 315,986 | MIT | `22f0b463e7a5e579904dd6211a520321035526f7` | Agentic skills framework; code-review request/receipt and verification discipline |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | 301,011 | MIT | `d2ef2680594f9a17526a6e1a2e18b3d242c5d17b` | Large harness/skill collection; Java/Python reviewers, security review, verification loop |
| [anthropics/skills](https://github.com/anthropics/skills) | 192,779 | Per-skill (`LICENSE.txt`) | `2c5958ecac7cee2b583967a2c4981d0f4a75c579` | Reference implementation of the Agent Skills format |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 115,511 | MIT | `301b02b12bff98e4688e6984af6556802322bbde` | Production-grade review/quality skills; five-axis reviewer and severity taxonomy |
| [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) | 69,790 | MIT | `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` | Security-audit skill with attack-class references and a machine-readable report schema |

### What each one contributes

**mattpocock/skills — the review spine.** The [`code-review`](https://github.com/mattpocock/skills/blob/main/skills/engineering/code-review/SKILL.md) skill reviews a diff along two independent axes:

- **Standards** — does the change follow the repo's documented conventions, plus a fixed Fowler smell baseline?
- **Spec** — does it faithfully implement the originating issue/spec?

The axes run in parallel sub-agents so one does not contaminate the other, and the final report is **not reranked across axes** — a change can pass one and fail the other. The smell baseline is explicitly judgement-call language ("possible Feature Envy"), and a documented repo standard always overrides it. This is the methodology the bot should preserve; only the delivery mechanism changes (GitHub review instead of a terminal report).

**obra/superpowers — evidence discipline.** [`verification-before-completion`](https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md) states the iron law: *no completion claims without fresh verification evidence*. [`requesting-code-review`](https://github.com/obra/superpowers/blob/main/skills/requesting-code-review/SKILL.md) requires a reviewer with precisely crafted context, never the author's session history. For the bot, this becomes a **separate verifier pass**: every candidate finding must be re-checked against the changed code, its callers/guards/tests, and the graph before it is posted. A finding that cannot be evidenced is dropped, not softened.

**addyosmani/agent-skills — output quality.** [`code-review-and-quality`](https://github.com/addyosmani/agent-skills/blob/main/skills/code-review-and-quality/SKILL.md) adds the five axes (correctness, readability/simplicity, architecture, security, performance), the severity vocabulary (`Critical`, required/no prefix, `Optional`/`Consider`, `Nit`, `FYI`), and the rule to **drop a finding if callers, guards, or tests rule it out**. It also treats "zero findings" as a valid, honest result and requires a verification story. That directly attacks the false-positive problem that makes review bots noisy.

**cloudflare/security-audit-skill — security depth.** The skill organises security review by attack class (web/auth, injection, data isolation, supply chain, resource exhaustion, secrets) and ships [`report-schema.json`](https://github.com/cloudflare/security-audit-skill/blob/main/skills/security-audit/report-schema.json) plus validators. The bot does not need the full audit workflow, but the attack-class checklist and the idea of a validated, machine-readable finding are directly reusable.

**anthropics/skills — portability.** The repository is the reference for the `SKILL.md` format (`name`, `description`, optional supporting files) that OpenCode also consumes. Its value is format compatibility, not review content. Note that licences are per-skill, so any copied text must be checked individually.

**affaan-m/ECC — evaluated, not vendored.** It has useful Java/Python reviewer agents and a `security-review`/`verification-loop` pair, but it is a broad harness with overlapping review coverage. Vendoring it would add surface area and licence review without improving the core review loop. It remains a reference for language-specific checklists.

**alibaba/open-code-review — the quality bar, not a dependency.** 49,823 stars, Apache-2.0, pinned at `db5db6bec62ee45c02171a12e043b8239223aa07`. It is a hybrid of deterministic engineering (file selection, bundling, rule matching, comment positioning, reflection) and an LLM agent. Its public benchmark (AACR-Bench: 50 repositories, 200 PRs, 10 languages, 1,505 annotated issues) reports higher precision/F1 than a general-purpose agent at roughly 1/9 the tokens, with deliberately lower recall. Two lessons for this project:

1. **Positioning and reflection are separate, testable modules.** A finding that cannot be anchored to a changed line should not become an inline comment.
2. **Precision-first is the right default for a PR bot.** A missed minor issue is cheaper than a stream of false alarms.

It is not the runtime because the brief requires OpenCode + a graph + a single sidecar, and running a second review agent would duplicate the LLM loop.

---

## 2. Code-graph options

| Project | Stars | Licence | Pinned commit | Fit |
|---|---:|---|---|---|
| [tirth8205/code-review-graph](https://github.com/tirth8205/code-review-graph) | 32,713 | MIT | `29d8bd94312a02dc85b2f4e3e6c97ebe7e768fb8` | **Selected.** Tree-sitter graph, Java + Python, MCP server, SQLite only, no external service |
| [oraios/serena](https://github.com/oraios/serena) | 31,290 | Custom ("Serena Licensing Overview") | `6e5c3776d4e67befaab7c290bc29b0279c98d1ed` | Excellent LSP-based semantic retrieval, but needs per-language language servers; heavier than a single sidecar |
| [vitali87/code-graph-rag](https://github.com/vitali87/code-graph-rag) | 5,348 | MIT | `ff3e90865ef922da86bf922f87f1b5907f9e511b` | Multi-language graph/RAG, but requires Memgraph (an external database) — fails the single-container constraint |

### Why `code-review-graph`

- **Most-starred dedicated code graph for review.** It is built for the exact use case: a structural map of the repository that serves compact review context over MCP.
- **Java and Python are first-class.** Python is core; Java has Spring-aware extraction (dependency-injection call resolution, request endpoints, WebFlux routes, scheduled triggers, application events, Temporal edges) and does not require compiling the project.
- **Single-process storage.** One SQLite file under `.code-review-graph/`; no Neo4j/Memgraph, no vector service, no cloud dependency.
- **MCP native.** `code-review-graph serve` exposes 30 tools; `serve --http` uses Streamable HTTP on port 5555. OpenCode is an explicitly supported platform (`install --platform opencode`).
- **Incremental and bounded.** Reparse only changed files; a cold build of ~3,000 files is documented at roughly 40 seconds, and a two-file incremental update at roughly 2.5 seconds on the hook path.
- **Measured context reduction.** The project reports ~63× median per-question token reduction (range ~35×–358×) versus feeding the whole corpus. Treat these as vendor benchmarks, not independent results — but the direction is what matters for cost and latency.

Limits to design around:

- Impact "recall 1.0" in its benchmark is **circular** (the ground truth comes from the same graph edges), so the bot must not treat graph impact as proof of coverage.
- Graph context can cost more than a plain file read for trivial single-file changes; use it for multi-file/impact questions, not every lookup.
- Entry-point/flow detection is strongest for Python and PHP; JavaScript/Go need work. Java is source-level, not build-aware.
- A cold build of a very large monorepo can exceed the review budget; the bot needs a cap and a graceful fallback to diff + targeted reads.

---

## 3. Prior-art review engines

| Project | Stars | Licence | What it establishes | Why it is not the runtime |
|---|---:|---|---|---|
| [alibaba/open-code-review](https://github.com/alibaba/open-code-review) | 49,823 | Apache-2.0 | Deterministic + agent hybrid; line-level comments; precision-first benchmark | Second LLM agent; requirement is OpenCode + skills + graph |
| [qodo-ai/pr-agent](https://github.com/qodo-ai/pr-agent) | 15,917 | MIT | Mature PR orchestration, multi-SCM, review commands | Its own prompting/runtime; would bypass OpenCode and the vendored skills |
| [semgrep/semgrep](https://github.com/semgrep/semgrep) | 17,604 | LGPL-2.1 | Fast deterministic SAST for Java/Python | Optional later layer; rule licensing/network and image size need review |
| [github/codeql](https://github.com/github/codeql) | 10,340 | See repo | Deep semantic security analysis | Build/DB requirements are too heavy for a one-shot sidecar |
| [anthropics/claude-code-security-review](https://github.com/anthropics/claude-code-security-review) | 6,841 | See repo | Security-focused PR Action | Security-only; tied to a GitHub Action and Claude Code, not OpenCode |

The takeaway is architectural: **deterministic steps for the things that must not drift (file selection, diff anchoring, posting, idempotency) and an LLM agent for judgement (what is wrong, why, and how to fix it).** That is also the strongest lesson from Open Code Review's production experience.

### 3.1 Tiered review and noise-control prior art

No single project implements the exact requested chain — **Senior Engineer review → Principal/Staff Engineer audit-and-triage → optional security specialist** on top of OpenCode, a code graph, and a single-use sidecar. The closest pieces are worth reusing:

| Project | Stars | Licence | Pinned commit | Relevant contribution |
|---|---:|---|---|---|
| [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) | 26,482 | MIT | `ed74d115b7fb7026a22a4f816a8e3250f425e3b4` | 161+ agent personas. [`surgeon-reviewer`](https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/04-quality-security/surgeon-reviewer.md) is a zero-noise reviewer with `WILL BREAK` / `WILL COST` / `WILL ROT` tiers and a ship/no-ship verdict; [`ponder-auditor`](https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/04-quality-security/ponder-auditor.md) is a multi-pass auditor with Skeptic (delete false positives), Dreamer (add missed), Builder (make actionable), and Empath (re-rank). Also ships `architect-reviewer`, `security-auditor`, `code-reviewer`. |
| [wshobson/agents](https://github.com/wshobson/agents) | 42,409 | MIT | `9c61ab243def98f72da12abd41cfcf5bcd91af9d` | 202 agents, 185 skills, 94 plugins; first-class **OpenCode** installation and permission translation; code-review, security-scanning, and developer-essentials plugins. The closest multi-harness component library. |
| [contains-studio/agents](https://github.com/contains-studio/agents) | 12,422 | No licence field | `a5a480c324cac64b9c569bca0b2f297d517240cb` | Engineering personas including reviewers. Evaluated but **not vendored**: no declared licence. |
| [ramziddin/solid-skills](https://github.com/ramziddin/solid-skills) | 632 | MIT | `94978c9cb06da1cb643ee4fe8a83bc8bac97c0a8` | SOLID, TDD, clean code, architecture, and code-smell references. Strong content, but some rules (class/variable counts, mandatory value objects) are too dogmatic for a review bot; adapt with restraint. |
| [principal-review-and-refactor](https://github.com/worxbend/nerd-fonts-installer/blob/main/.agents/skills/principal-review-and-refactor/SKILL.md) | — | MIT (skill frontmatter) | — | Principal-engineer persona with bounded fan-out, impact × confidence ÷ risk ranking, and an explicit **"leave it alone"** list to prevent over-engineering. Best idea source for the Principal pass. |
| [LucianFord/agent-pack](https://github.com/LucianFord/agent-pack) / [Quinnod345/ponder](https://github.com/Quinnod345/ponder) | — | MIT (credited) | — | Original sources credited by VoltAgent for `surgeon-reviewer` and `ponder-auditor`; concepts, not dependencies. |
| [OWASP ASVS 5.0](https://asvs.dev/v5.0.0/) · [OWASP Top 10:2025](https://top10.owasp.org/2025/) · [CWE Top 25](https://cwe.mitre.org/top25/) | — | OWASP/CWE terms | — | Security verification requirements, web risk taxonomy, and weakness classes. Reference standards for the deep-security skill; do not copy text without checking the licence. |

**Interpretation.** The persona libraries provide the *style* of review we want: high-signal findings, explicit severity tiers, adversarial false-positive retraction, and a principal who can say "leave it alone". They do **not** provide the orchestration: GitHub PR intake, diff anchoring, code-graph context, two-model routing, triage ledger, idempotent publishing, or the one-shot sidecar. Full engines such as Open Code Review and PR-Agent provide orchestration but own the prompting/runtime and would bypass OpenCode and the vendored skills.

So the bot is a **composition**: adapt the strongest personas and checklists, but keep the two-pass control plane and the safety boundary in our orchestrator. That also avoids inheriting 200+ agents or an unmaintainable fork.

---

## 4. OpenCode runtime facts

Source: [OpenCode docs](https://opencode.ai/docs/) and the [anomalyco/opencode repository](https://github.com/anomalyco/opencode) (226,021 stars, MIT, pinned at `7bac5bad02f68b95fc5c2c022252c0635ea61abe`).

- **Headless execution:** `opencode run "..."` is explicitly designed for scripts and CI. It supports `--format json` (newline-delimited JSON), `--model provider/model`, `--agent <id>`, `--session`, `--continue`, `--file`, `--archived`, and `--standalone` (private server, recommended in CI).
- **Skills:** `.opencode/skills/<id>/SKILL.md`, with YAML `name`/`description`; also reads `.claude/skills` and `.agents/skills`. Skills can be disabled from model auto-invocation with `metadata.opencode/autoinvoke: false`.
- **Agents:** `.opencode/agents/<id>.md` with frontmatter (`description`, `mode`, `model`, `permissions`, `steps`). A read-only reviewer is a supported first-class pattern.
- **Permissions (v2):** ordered `{action, resource, effect}` rules; actions include `read`, `edit`, `glob`, `grep`, `shell`, `subagent`, `skill`, `webfetch`, `websearch`, and MCP tool names. The base default allows everything, so the bot must explicitly deny edits, shell, web, and subagents rather than rely on prompts.
- **MCP:** local stdio servers and remote Streamable HTTP servers are configured under `mcp.servers`; `codemode: false` exposes native tools directly.
- **Providers:** custom OpenAI-compatible providers are configured with `package`, `settings.baseURL`, `env`, and `models`. This is enough to accept a user-supplied endpoint, key, and model without a code change.
- **Container:** official images are published as `ghcr.io/anomalyco/opencode:<version>` (docs example: `2.0.0`).
- **No built-in PR publishing:** the runtime reviews; the bot's orchestrator must fetch the PR, validate anchors, and post the GitHub review.

This split is deliberate: OpenCode is the reasoning runtime; the Python orchestrator owns trust boundaries, GitHub I/O, schema validation, and idempotency.

---

## 5. GitHub and Kubernetes constraints

- **GitHub PR reviews.** Inline comments are created through the pull-request review API with `commit_id`, `path`, `line`, `side: "RIGHT"`, and `body`; the line must be part of the diff. Findings outside the diff must go to the summary, not an inline comment. Source: [GitHub REST — pull request reviews](https://docs.github.com/en/rest/pulls/reviews), [pull request comments](https://docs.github.com/en/rest/pulls/comments).
- **Least-privilege token.** A fine-grained PAT needs Metadata: read, Contents: read, Pull requests: read/write, and Issues: read/write (the sticky summary is an issue comment; linked specs are read). A GitHub App installation token is the better long-term shape, but the brief specifies a token.
- **Kubernetes sidecars are long-running by definition.** Native sidecars are init containers with `restartPolicy: Always`; a one-shot reviewer that exits would be restarted in a normal pod. A single-use review belongs in a **Job** (standalone) or an **initContainer** (when a later container consumes its output). Source: [Kubernetes sidecar containers](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/).

That last point is a real design correction to the phrase "single used sidecar": the deployment can look like a sidecar, but the lifecycle primitive must be one-shot.

---

## 6. Selected stack

| Layer | Choice | Why |
|---|---|---|
| Agent runtime | OpenCode 2.x, pinned | Required; headless JSON, skills, agents, MCP, custom providers |
| Orchestrator | Python 3.12 | GitHub/diff/schema ecosystem; `code-review-graph` is Python; no Node runtime needed |
| Code graph | `code-review-graph`, pinned | Most-starred dedicated graph; Java/Python; MCP; SQLite; no external DB |
| Review 1 — Senior | Senior persona + mattpocock two axes + addyosmani five axes + SOLID/language skills | Broad, high-recall candidate generation; no final filtering |
| Review 2 — Principal | Principal persona + `surgeon-reviewer`/`ponder-auditor` ideas + triage policy | Independent audit, adds only material issues, rejects low-value comments, final verdict |
| Noise control | `surgeon-reviewer` zero-noise test + principal "leave it alone" list + explicit noise budget | Prevents a technically-true but unimportant comment from overworking the author |
| Security specialist | cloudflare audit + OWASP ASVS 5.0 / Top 10:2025 / CWE Top 25 + language-specific AppSec | Deep, evidence-based security on sensitive diffs; conditional third pass |
| Verification | obra `verification-before-completion` + addyo "drop if ruled out" | Evidence before posting; precision over recall |
| Output taxonomy | addyosmani `code-review-and-quality` + surgeon tiers | Severity labels, five axes, zero-findings-is-valid |
| Skill format | anthropics/skills | Portable `SKILL.md` contract that OpenCode consumes |
| Packaging | Docker + Kubernetes Job / initContainer | Single-use, non-root, read-only, no external state |

---

## 7. Caveats and open research

- **Star counts are a snapshot and a proxy.** They move daily and can be gamed. The selection above is defensible on fit as well as stars; each dependency still needs a pinned-commit review and a licence check.
- **The selected skill repositories are MIT**, which permits adaptation with attribution. `anthropics/skills` is per-skill licensed, so only its format is used unless a specific file's licence is checked. Serena's licence is custom and was a factor in not selecting it. Semgrep's LGPL and rule licensing need review before it becomes a bundled dependency.
- **OpenCode v2 is young and moving.** Pin the binary, disable auto-update, and keep contract tests around `opencode run --format json`, agent frontmatter, and MCP config so an upgrade fails loudly.
- **Graph accuracy is Java/Python source-level.** Spring wiring and Python imports are approximated; dynamic dispatch, reflection, and generated code are blind spots. The bot should present graph facts as context, not as proof.
- **Quality is model-dependent.** The eval harness, not the prompt alone, decides whether a model is acceptable. A model that cannot produce a stable JSON object or call MCP tools reliably must be rejected regardless of benchmark scores.
- **Two passes can share blind spots.** Using the same model for Senior and Principal reduces independence. Prefer a different (usually stronger) model for the Principal, and measure whether the Principal adds or rejects anything the Senior missed.
- **Noise control can over-correct.** A Principal that rejects too much is as harmful as one that rubber-stamps. Track false rejections of true critical/security findings separately, and give security findings an explicit veto.

---

## 8. Sources

- [mattpocock/skills](https://github.com/mattpocock/skills) — `code-review` skill and repository README.
- [obra/superpowers](https://github.com/obra/superpowers) — `requesting-code-review`, `verification-before-completion`.
- [affaan-m/ECC](https://github.com/affaan-m/ECC) — Java/Python reviewer agents, `security-review`, `verification-loop`.
- [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) — `surgeon-reviewer`, `ponder-auditor`, `architect-reviewer`, `security-auditor`, `code-reviewer`.
- [wshobson/agents](https://github.com/wshobson/agents) — multi-harness agents/skills, native OpenCode installation, code review and security plugins.
- [contains-studio/agents](https://github.com/contains-studio/agents) — evaluated; no declared licence.
- [ramziddin/solid-skills](https://github.com/ramziddin/solid-skills) — SOLID/TDD/clean-code skill.
- [principal-review-and-refactor](https://github.com/worxbend/nerd-fonts-installer/blob/main/.agents/skills/principal-review-and-refactor/SKILL.md) — principal persona and "leave it alone" discipline.
- [OWASP ASVS 5.0](https://asvs.dev/v5.0.0/), [OWASP Top 10:2025](https://top10.owasp.org/2025/), [CWE Top 25](https://cwe.mitre.org/top25/) — security standards referenced by the deep-security skill.
- [anthropics/skills](https://github.com/anthropics/skills) — Agent Skills format.
- [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) — `code-review-and-quality`, `security-and-hardening`.
- [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) — attack classes, report schema, validators.
- [alibaba/open-code-review](https://github.com/alibaba/open-code-review) — hybrid architecture and AACR-Bench.
- [tirth8205/code-review-graph](https://github.com/tirth8205/code-review-graph) — graph architecture, MCP tools, benchmarks, limitations.
- [oraios/serena](https://github.com/oraios/serena) — LSP-based alternative.
- [vitali87/code-graph-rag](https://github.com/vitali87/code-graph-rag) — Memgraph-based alternative.
- [qodo-ai/pr-agent](https://github.com/qodo-ai/pr-agent) — prior-art PR orchestration.
- [semgrep/semgrep](https://github.com/semgrep/semgrep) — deterministic SAST option.
- [OpenCode docs](https://opencode.ai/docs/) — [CLI/run](https://opencode.ai/docs/cli/commands/), [skills](https://opencode.ai/docs/skills/), [agents](https://opencode.ai/docs/agents/), [permissions](https://opencode.ai/docs/permissions/), [MCP](https://opencode.ai/docs/mcp-servers/), [providers](https://opencode.ai/docs/providers/), [config](https://opencode.ai/docs/config/).
- [GitHub REST — pull request reviews](https://docs.github.com/en/rest/pulls/reviews) and [review comments](https://docs.github.com/en/rest/pulls/comments).
- [Kubernetes sidecar containers](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/).

All star counts, licences, and commit SHAs were captured on **2026-11-11**.
