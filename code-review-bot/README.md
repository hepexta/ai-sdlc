# code-review-bot

**Status: Planning (`Draft`) — no implementation yet.**

AI-accelerated code review for Java and Python pull requests, built on OpenCode, a code graph, and the most-starred open agent skills. It runs as one container per PR (Docker, Kubernetes Job, or single-use init/sidecar container) and publishes a small, evidence-backed set of line-anchored GitHub review comments in a natural senior-reviewer voice — not a wall of suggestions or a generated report.

- **Issue:** [0001 — AI-Accelerated Java/Python Code Review Bot](../.scratch/0001-code-review-bot.md)
- **Research:** [Landscape dossier](../.scratch/research/2026-11-11-code-review-bot-landscape.md)
- **Secrets:** [Vault/ESO design](./docs/SECRETS.md)
- **Comment voice:** [COMMENT_STYLE.md](./docs/COMMENT_STYLE.md)
- **Tracker conventions:** [.scratch/README.md](../.scratch/README.md)

## What it will do

1. Take an LLM endpoint, LLM API key, model(s), GitHub token, and PR reference. In Kubernetes, the two secrets arrive as files from a Vault-backed `ExternalSecret`, not as environment values.
2. Fetch the PR and labels. If it carries `AI Reviewed`, skip without cloning or calling an LLM; `FORCE=true` removes the label and re-reviews.
3. Check out the head commit, compute the merge base, and build a code graph with `code-review-graph`; expose the graph to OpenCode over MCP.
4. Select **reasoning effort** (low / medium / high) from the PR's changed lines/files, escalating Security and Principal for sensitive diffs.
5. **Review 1 — Senior Engineer:** broad, skill-based review across Standards, Spec, SOLID, language idioms, and security baseline; emits candidate findings.
6. **Specialist check — Security:** conditionally runs on auth/crypto/SQL/deserialization/dependency-sensitive diffs, using OWASP ASVS 5.0, Top 10:2025, and CWE Top 25.
7. **Review 2 — Principal/Staff Engineer:** independently audits the candidates, adds only material issues, rejects low-value comments, enforces SOLID/best practices with restraint, and produces the final verdict plus optional `suggestion_code` for exact local fixes.
8. Write the review in a natural senior-reviewer voice: short prose, problem and consequence first, no headings/badges/emojis/AI tells/visible model metadata; then publish the summary (prose lead + compact metrics footer), line-anchored comments with optional applyable suggestion blocks, and add `AI Reviewed`.
9. Optionally fail a gate on `critical` / `major`.

The agents never edit code, run shell commands, browse the web, or receive the GitHub token. Only the Principal's curated findings are posted; rejected candidates stay in the run artifact. The bot pod does not hold a Vault token; ESO delivers the secrets and the pod mounts the derived Kubernetes Secret read-only. A suggestion is a proposal, never an automatic commit. The bot account remains visible; "human-like" means natural tone, not impersonation.

## Planned repository layout

```
code-review-bot/
├── README.md
├── pyproject.toml / uv.lock
├── Dockerfile
├── src/code_review_bot/        # orchestrator: config, GitHub, labels, git, graph, effort, context, agent, findings, summary, publish
├── agent/                      # vendored OpenCode agents + skills (pinned, attributed)
│   ├── agents/
│   ├── skills/
│   └── opencode.jsonc.tmpl
├── deploy/
│   ├── docker-compose.yml
│   ├── vault/                  # seed policy/script for the bot's Vault path
│   └── k8s/                    # Job, initContainer pod, ExternalSecret, NetworkPolicy
├── tests/                      # unit, contract, integration, e2e
├── eval/                       # seeded PR corpus, ground truth, results
└── docs/                       # architecture, ADRs, security, privacy, runbook
    ├── SECRETS.md              # Vault/ESO design and rotation runbook
    └── COMMENT_STYLE.md        # human-like comment voice, examples, lint targets
```

## Non-goals (v1)

Auto-fixing code, a webhook/daemon service, GitLab/Bitbucket, languages beyond Java/Python, compiling or testing the PR, replacing a full SAST platform, and putting a Vault SDK/token inside the bot pod.

## Next step

Resolve the P0 open questions in the issue, move it to `In Progress`, and create the tracer-bullet tickets `01`–`09`. Seed the local Vault path and verify the `ExternalSecret` before the first Kubernetes pilot. Until then, this folder intentionally contains documentation only.
