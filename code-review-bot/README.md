# code-review-bot

**Status: implemented MVP, `In Progress`.** The orchestration, fake-mode E2E, Docker image, real OpenCode invocation, and Kubernetes smoke test work. The live GitHub/Vault pilot and the 30-PR evaluation are still outstanding.

AI-accelerated review for Java and Python pull requests. One container reviews one PR, runs **Senior → (Security) → Principal**, publishes a small set of line-anchored GitHub comments with optional `suggestion` blocks, posts a token/count summary, and adds `AI Reviewed`.

- **Issue:** [0001 — AI-Accelerated Java/Python Code Review Bot](../.scratch/0001-code-review-bot.md)
- **Detailed plan:** [PLAN.md](./docs/PLAN.md)
- **Delivery/secrets:** [DELIVERY.md](./docs/DELIVERY.md), [SECRETS.md](./docs/SECRETS.md)
- **Comment voice:** [COMMENT_STYLE.md](./docs/COMMENT_STYLE.md)
- **Kubernetes:** [deploy/k8s](./deploy/k8s)

## What works

1. Takes `PR_URL`, `LLM_BASE_URL`, `LLM_MODEL_*`, `LLM_API_KEY_FILE`, and `GITHUB_TOKEN_FILE`.
2. Skips before clone/LLM when the exact `AI Reviewed` label is present; `FORCE=true` removes it and re-runs.
3. Checks out the PR head and merge base; builds a `code-review-graph` brief (Java/Python, SQLite, no external DB).
4. Selects effort from changed volume (`small`/`medium`/`large`), escalating Security and Principal for sensitive diffs.
5. **Senior:** high-recall candidate findings with quoted evidence and impact.
6. **Security:** conditional deep pass with CWE/ASVS refs and fail-closed behavior.
7. **Principal:** audits candidates, rejects noise into a triage ledger, adds at most `MAX_ADDED` material findings, and writes the final human-style comment.
8. Validates every inline anchor and suggestion range against the right side of the diff; invalid suggestions become prose or summary-only.
9. Posts a sticky summary plus one review with inline comments, optional applyable suggestions, hidden `crb:` markers, and the label last.
10. Writes `review.json`, `summary.md`, and `triage.json`; dry-run writes without posting.

The agents are read-only: no edit, shell, web, or subagents. The GitHub token stays in the orchestrator. The OpenCode process receives the LLM key through `OPENCODE_CONFIG_CONTENT` in its environment, not a workspace file. The pod never holds a Vault token.

## Runtime versions

| Component | Version | Notes |
|---|---|---|
| Python | 3.12 in the image; 3.13 on the dev host | `requires-python >=3.11` |
| OpenCode | **1.17.3** | v1 config: `agent`/`permission`/`provider`; `--variant`, `--dir`, `--pure` |
| code-review-graph | **2.4.0** | Python package + CLI, SQLite |
| GitHub API | REST 2022-11-28 | GitHub.com and GHES base URL |

The earlier planning docs assumed OpenCode 2.x; the implementation and [PLAN.md](./docs/PLAN.md) now target the installed v1.17.3 surface.

## Inputs

| Input | Required | Form |
|---|---|---|
| PR | Yes | `PR_URL`, or `GITHUB_REPOSITORY` + `PR_NUMBER` |
| LLM endpoint | Yes | `LLM_BASE_URL` (OpenAI-compatible) |
| LLM key | Yes | `LLM_API_KEY_FILE` (or `LLM_API_KEY`) |
| Models | Yes | `LLM_MODEL`, or `LLM_MODEL_SENIOR` / `_PRINCIPAL` / `_SECURITY` |
| GitHub token | Yes | `GITHUB_TOKEN_FILE` (or `GITHUB_TOKEN`) |
| GitHub clone URL | No | `GITHUB_SERVER_URL` (GHES) or `GITHUB_CLONE_URL` (local tests) |
| Label | No | `AI_REVIEWED_LABEL`, default `AI Reviewed`; empty disables |
| Force/dry run | No | `FORCE`, `DRY_RUN` |
| Graph | No | `GRAPH_MODE=auto|required|off`; `GRAPH_MCP=off` (v1 default) |
| Effort | No | `REASONING_EFFORT=auto|low|medium|high`; `EFFORT_MODE=variant|prompt` |
| Gate | No | `FAIL_ON=none|critical|major` |

Full defaults and bounds are in [PLAN.md](./docs/PLAN.md#input-contract). Secret values must not be put in the issue, Git, manifests, or command lines.

## Local development

```powershell
cd code-review-bot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"   # or pip install -e . pytest pyyaml
.\.venv\Scripts\python.exe -m pytest tests -q
```

The test suite includes:

- unit tests for config, diff anchors, suggestions, effort, style, triage, and manifests;
- a **fake GitHub + fake OpenCode** end-to-end test, including skip and forced re-review;
- a **real OpenCode 1.17.3** test against a fake OpenAI-compatible LLM;
- a **Docker** end-to-end test that runs the built image, real OpenCode inside the container, fake GitHub/LLM services on the host, secret files, summary, suggestions, and label;
- a **kind** smoke script that runs the image as a Job with a read-only root filesystem and a mounted Secret.

Useful commands:

```powershell
# Fake pipeline (no network)
.\.venv\Scripts\python.exe -m pytest tests/test_e2e.py -q

# Real OpenCode + fake LLM (needs opencode on PATH)
.\.venv\Scripts\python.exe -m pytest tests/test_opencode_real.py -q

# Build and run the Docker E2E
docker build -t code-review-bot:dev .
.\.venv\Scripts\python.exe -m pytest tests/test_docker_e2e.py -q

# Kubernetes smoke (creates/reuses kind cluster crb-smoke)
.\scripts\k8s-smoke.ps1
```

## Run against a real PR

```bash
export PR_URL="https://github.com/acme/service/pull/42"
export LLM_BASE_URL="https://llm.example/v1"
export LLM_API_KEY_FILE="/run/secrets/llm_api_key"
export GITHUB_TOKEN_FILE="/run/secrets/github_token"
export LLM_MODEL_SENIOR="reviewer-fast"
export LLM_MODEL_PRINCIPAL="reviewer-strong"

crb review
```

`crb validate-config` prints the redacted effective configuration without calling GitHub or the LLM.

Docker:

```bash
docker run --rm \
  -e PR_URL -e LLM_BASE_URL \
  -e LLM_MODEL_SENIOR -e LLM_MODEL_PRINCIPAL \
  -e LLM_API_KEY_FILE=/run/secrets/llm_api_key \
  -e GITHUB_TOKEN_FILE=/run/secrets/github_token \
  -v "$PWD/secrets:/run/secrets:ro" \
  code-review-bot:0.1.0
```

The image entrypoint is `tini -- crb`; pass `review` or `validate-config` as the container argument.

## Kubernetes

```bash
kubectl apply -k deploy/k8s
```

Edit `deploy/k8s/job.yaml` (PR URL, endpoint, models, image) and seed Vault at `secret/agents-infra/<profile>/code-review-bot` with `llm_api_key` and `github_token`. The `ExternalSecret` syncs them to `code-review-bot-secrets`; the Job mounts it read-only at `/run/secrets`.

The Job has `backoffLimit: 0`, `activeDeadlineSeconds: 1500`, a non-root UID `10001`, a read-only root filesystem, all capabilities dropped, no service-account token, and an egress policy limited to DNS and TCP 443. `kubectl apply -k` requires the ESO `ExternalSecret` CRD; the smoke script creates a plain Secret because it does not install ESO.

## Repository layout

```
code-review-bot/
├── Dockerfile
├── pyproject.toml
├── src/code_review_bot/
│   ├── config.py models.py diff.py gitops.py github.py
│   ├── graph.py effort.py brief.py opencode_runner.py
│   ├── triage.py style.py publish.py review.py cli.py
├── tests/                  # unit + fake E2E + real OpenCode + Docker + manifests
├── deploy/k8s/             # Job, ExternalSecret, NetworkPolicy
├── scripts/k8s-smoke.ps1
└── docs/                   # PLAN, DELIVERY, SECRETS, COMMENT_STYLE
```

## Current limitations

- `GRAPH_MCP=on` is optional and off by default; v1 uses the precomputed graph brief. MCP is **not** in the LLM path.
- The live Vault/ESO path has been designed and manifested, not tested against a running Vault in this session.
- The 30-PR evaluation and blind human-voice sample have not been run; the metrics in the issue remain targets, not results.
- The Kubernetes smoke test runs `validate-config`, not a full review. The full Docker E2E is the end-to-end evidence.
- `FAIL_ON` is off by default (`none`); comment-only is the safe rollout mode.
- The bot account and `AI Reviewed` label remain visible; "human-like" means natural tone, not impersonation.
