# Code Review Bot — Delivery and Operations

**Status:** Planning reference for [issue 0001](../../.scratch/0001-code-review-bot.md). Covers GitHub publishing, containers, secrets, testing, milestones and risks.

## Delivery

### GitHub integration

Intake:

- Parse `PR_URL` (`https://github.com/owner/repo/pull/123`, GHES equivalent, or `owner/repo#123`).
- `GET /repos/{owner}/{repo}/pulls/{number}` for title/body/state/base/head/commits **and labels**.
- Reject closed/merged PRs with a clean exit before the label check; do not add or remove labels.
- If `AI Reviewed` is in the labels and `FORCE=false`, log and exit 0 before clone/LLM/comment. If `FORCE=true`, remove the label before continuing. Ensure the label exists (create only if missing) before spending tokens.
- `GET /repos/{owner}/{repo}/pulls/{number}/files` for the file list (paginated; cap at `MAX_FILES`).
- `GET /repos/{owner}/{repo}/issues/{number}/comments` for the existing sticky summary.
- Linked spec: `Closes|Fixes|Resolves #N` in the PR body and commit messages; fetch the issue title/body. If none, the Spec axis uses the PR description; if that is empty, Spec reports "no spec available" and skips.
- If the PR changes no Java/Python source after exclusions, post a one-line "nothing to review" summary, add `AI Reviewed`, and exit 0 without any LLM call.

Workspace:

- `git init`, add `origin` **without** an embedded token.
- `GIT_ASKPASS` script in `/tmp` returns `x-access-token` / `$CRB_GIT_TOKEN`; `GIT_TERMINAL_PROMPT=0`; `core.symlinks=false`; no submodule recursion.
- Fetch `refs/pull/N/head` from the base repo (works for fork PRs) and the base branch; compute `git merge-base`. If a shallow fetch hides the merge-base, deepen within a bounded number of commits; if it still cannot be found, fail with a clear message rather than reviewing the wrong range.
- Checkout head detached. Refuse symlinks, submodules, files > 2 MB, and paths outside the repo.
- Quarantine `opencode.json`, `opencode.jsonc`, `.opencode/`, `.claude/`, `.agents/`, `AGENTS.md`, and `CLAUDE.md` before the graph/agent stages; the bot's generated config is the only one loaded.
- Diff `git diff --unified=40 <merge-base>...HEAD -- <selected paths>`; use the GitHub file list for metadata and the git diff for anchors.
- Exclude lockfiles, generated/vendor/build output, minified files, binaries, and `.env` from the **LLM context**; include build manifests and migrations as context. Scan the full diff for likely secrets first; if one is found, emit a critical finding with the value redacted and never send the value to the model. Rank remaining files by graph risk, then source-before-test, then path.

Publishing:

- **Only the Principal's final findings are posted.** Senior and security candidates that were rejected remain in `/out/triage.json`; they never become PR comments.
- **Summary**: one issue comment with marker `<!-- code-review-bot:summary:v4 head=<sha> run=<id> verdict=... -->`; create or `PATCH` in place. The visible body is a short human prose lead plus `Blocking` / `Worth fixing` / `Minor` groups, with tokens, issue counts, suggestions, effort and label in a compact `<sub>` footer.
- **Inline**: `POST /repos/{owner}/{repo}/pulls/{number}/reviews` with `commit_id=head`, `event=COMMENT`, a short body, and `comments[]` (`path`, `line`, `side=RIGHT`, optional `start_line`/`start_side=RIGHT`, `body`). Never `APPROVE` or `REQUEST_CHANGES` in v1; the gate is an exit code/check, not a bot approval.
- **Suggestion blocks**: when a finding has a validated `suggestion_code`, render a GitHub ```` ```suggestion ```` block in the comment body. A single-line suggestion uses the same `line`; a multi-line suggestion sends `start_line` + `line` + `side=RIGHT` + `start_side=RIGHT`. If the range or replacement fails validation, drop the block, post the prose comment, and record `suggestion_dropped`.
- **Anchor validation**: a finding is inline only if the path is in the diff and the line is an added/context line on the right side. Otherwise demote to summary with a `(not in diff)` note.
- **Noise enforcement**: enforce `MAX_FINDINGS`, `MAX_INLINE`, `ALLOW_NITS`, `MAX_MINOR_INLINE`, and `MAX_SUGGESTIONS` after the Principal's triage; a schema-valid report that exceeds the budget is re-capped deterministically, not posted as-is.
- **Voice enforcement**: lint `comment_body` for word count, headings/bold scaffolding, emojis, AI tells, visible metadata, and repeated openings. One style repair; then deterministically strip the offending formatting and record `style.lint=fallback`. Style never blocks a valid finding.
- **Idempotency**: each inline comment carries `<!-- crb:f:<fingerprint> severity=... -->`; on re-run, skip existing fingerprints; update the summary. A second run on the same head SHA with `FORCE=false` performs no writes and exits 0.
- **Comment body**: the Principal's `comment_body` — 1–3 short paragraphs, problem and consequence first, then the fix, optional question. No headings, bold-label scaffolding, emojis, visible confidence/model/run/token metadata, or AI tells. Keep code identifiers in backticks; sanitize HTML/images, neutralize `@mentions` outside code spans, and strip external links. Cap at 8 KB.
- **Label**: after the summary and inline review are posted successfully, add `AI Reviewed` (`POST /issues/{number}/labels`). Retry 5xx/429; a failure to apply the label is exit 3, not a silent success. Never add the label before the review is published.
- **Retries**: 429/5xx with exponential backoff and `Retry-After`/`X-RateLimit-Reset`; 403 is a hard auth/scope error with a clear message. Cap at 5 attempts; do not duplicate a review on ambiguous timeout — query existing comments by fingerprint first.
- **Old reviews**: leave prior inline reviews in place (GitHub marks them outdated as the branch moves). Minimizing previous bot reviews via GraphQL is a Phase 2 optimization; the sticky summary always links the latest run.

Summary shape:

```markdown
## Review

The order lookup is the main problem: any authenticated customer can read another customer's order by changing the ID. The retry path itself looks solid.

**Blocking**
- `OrderController.java:64` — ownership check missing

**Worth fixing**
- `UserService.java:87` — `Optional.get()` throws for unknown emails

Not ready to merge until the ownership check is fixed; the rest can follow up.

<sub>16 found → 5 accepted / 9 rejected / 1 downgraded / 1 added · 7 posted · 5 suggestions · 105,400 tokens (senior 32,400 / security 22,900 / principal 50,100) · effort medium/high/high · `AI Reviewed` added</sub>
```

The hidden marker carries the machine verdict and run metadata; the visible text stays conversational. No "ship_with_fixes" label in the prose.

Token scopes (fine-grained): Metadata read, Contents read, Pull requests read/write (review comments + PR metadata), Issues read/write (sticky summary, labels, linked issue read). For classic PATs: `repo` (private) or `public_repo`. Document that a GitHub App token is the preferred long-term replacement (Q8).

### AI Reviewed label and skip

The label is the bot's manual "this PR has had its AI review" gate. Default name: **`AI Reviewed`** (exact, case-sensitive); colour `0E8A16`; description `Reviewed by code-review-bot`.

Intake order:

1. Fetch the PR, including labels, before any clone or LLM call.
2. If `AI Reviewed` is present and `FORCE=false`: log `skip: AI Reviewed`, exit 0. No workspace, no graph, no LLM token spend, no comment.
3. If `FORCE=true`: remove the label (`DELETE /issues/{number}/labels/{name}`) before continuing. A failed forced run therefore leaves no false label and remains retryable.
4. Ensure the label exists: `GET /labels/{name}`; on 404 create it with `POST /labels`. Failure here is exit 3 **before** spending tokens. Never overwrite an existing label's colour/description.
5. Run the review and publish the summary and inline review.
6. Add the label (`POST /issues/{number}/labels`). The label is applied only after the summary and review succeed. If the label call fails after retries, append a short warning to the sticky summary (`Label not applied; rerun or add it manually`), write the artifact with `label.applied=false`, and exit 3. The review may exist, but the gate is incomplete.

Ordering rules:

- **Summary + inline first, label last.** Never label a PR whose review was not posted.
- **Dry run** applies no label.
- **Security pass failure** applies no label (exit 8).
- **Gate failure after publish** applies the label, then exits 6: the review is complete, the merge gate is a separate outcome.
- **No reviewable files** posts the one-line summary, applies the label, exits 0 (Q24).
- **New commits after the label** are skipped by design. Remove the label to request another review, or run with `FORCE=true` for a deliberate re-review. This is the trade-off for a simple, visible gate; Q24.
- **Label disabled** (`AI_REVIEWED_LABEL=""`): no skip, no label, no label API calls.

API surface:

| Operation | Endpoint | Permission |
|---|---|---|
| Read labels | `GET /repos/{owner}/{repo}/pulls/{number}` (labels array) | Pull requests read |
| Ensure label | `GET/POST /repos/{owner}/{repo}/labels` | Issues write |
| Add label | `POST /repos/{owner}/{repo}/issues/{number}/labels` | Issues write |
| Remove on `FORCE` | `DELETE /repos/{owner}/{repo}/issues/{number}/labels/{name}` | Issues write |

The label is a workflow marker, not a security control. It does not replace idempotency fingerprints; both are used. A human can always remove it to re-open the review path.

### Container and Kubernetes

Image:

- Multi-stage: fetch the pinned OpenCode binary from the official `ghcr.io/anomalyco/opencode` image (docs example: `2.0.0`) or the versioned CLI tarball in a build stage; runtime is `python:3.12-slim` pinned by digest.
- Runtime packages: `git`, `ca-certificates`, `ripgrep`, `tini`; Python deps locked (`httpx`, `pydantic`, `unidiff`, `tenacity`, `code-review-graph` pinned).
- No JDK, Node, Maven, Gradle, or build toolchain. The graph parses source; it does not compile.
- Non-root UID/GID `10001`; `ENTRYPOINT ["tini","--","crb"]`; no writable layer required.
- Target < 600 MB; multi-arch `linux/amd64` + `linux/arm64`; OCI labels; SBOM; optional cosign signature.
- Auto-update disabled in OpenCode config; no runtime `pip install`/`npm install`.

One-shot contract:

- One PR per container; exit when done; no listener, no cron, no shared state.
- All writes go to `/tmp` (tmpfs), `/workspace` (emptyDir), `/cache` (optional PVC), `/out` (emptyDir/artifact).
- The container is idempotent: a retried Job must not duplicate comments.

Kubernetes Job (recommended for standalone):

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: crb-pr-42
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 1500
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: Never
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        fsGroup: 10001
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: reviewer
          image: ghcr.io/acme/code-review-bot:0.1.0@sha256:<digest>
          env:
            - { name: PR_URL, value: "https://github.com/acme/service/pull/42" }
            - { name: LLM_BASE_URL, value: "https://llm.example/v1" }
            - { name: LLM_MODEL_SENIOR, value: "acme/reviewer-fast" }
            - { name: LLM_MODEL_PRINCIPAL, value: "acme/reviewer-strong" }
            - { name: LLM_MODEL_SECURITY, value: "acme/reviewer-security" }
            - { name: LLM_API_KEY_FILE, value: "/run/secrets/llm_api_key" }
            - { name: GITHUB_TOKEN_FILE, value: "/run/secrets/github_token" }
          resources:
            requests: { cpu: "500m", memory: "1Gi" }
            limits:   { cpu: "2",     memory: "3Gi" }
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          volumeMounts:
            - { name: tmp, mountPath: /tmp }
            - { name: workspace, mountPath: /workspace }
            - { name: out, mountPath: /out }
            - { name: secrets, mountPath: /run/secrets, readOnly: true }
      volumes:
        - { name: tmp, emptyDir: { medium: Memory, sizeLimit: 256Mi } }
        - { name: workspace, emptyDir: { sizeLimit: 2Gi } }
        - { name: out, emptyDir: { sizeLimit: 128Mi } }
        - { name: secrets, secret: { secretName: code-review-bot-secrets, defaultMode: 0440 } }
```

The Secret is created and owned by the `ExternalSecret`; **do not create it with `kubectl create secret`**. Its data keys are `llm_api_key` and `github_token`, and ESO refreshes it from Vault. See [Secrets and Vault integration](#secrets-and-vault-integration).

Single-use sidecar / initContainer:

- **Preferred when a later container needs the result:** a multi-container Job pod with `restartPolicy: Never`, or an `initContainer` that writes `/out/review.json` and `/out/summary.md` before the main container starts.
- **Do not** put this container in a long-running pod with `restartPolicy: Always`; it will be restarted after exit. Native sidecars are long-running by design.
- If an existing CI runner pod must own the lifecycle, the reviewer is an `initContainer`; the runner reads `/out` and publishes/uses the result.
- Provide `deploy/k8s/job.yaml` and `deploy/k8s/initcontainer-pod.yaml`; document the difference in the README.

Network and secrets:

- The derived `code-review-bot-secrets` Secret is mounted as files (`_FILE` inputs); do not pass secrets as `env` values. ESO owns the Secret and refreshes it from Vault.
- NetworkPolicy: default-deny egress; allow DNS, `api.github.com`/GHES, and the LLM host. Kubernetes NetworkPolicy is IP/CIDR-based; for FQDN egress use Cilium `toFQDNs` or an egress gateway. Block link-local/metadata (`169.254.169.254`) explicitly.
- No service-account token, no Docker socket, no hostPath, no privileged mode.

### Secrets and Vault integration

**Decision:** secrets do not live in the bot, the Git repository, a ConfigMap, or Job `env` values. **Vault KV v2 is the source of truth; External Secrets Operator (ESO) syncs the values into a derived Kubernetes Secret; the Job mounts that Secret as files.** The bot has no Vault token and makes no Vault API call. Full design, manifests and runbook: [SECRETS.md](SECRETS.md).

The existing platform already proves this pattern:

- `agents-infra/k8s-cluster` installs ESO `2.12.0`.
- `ClusterSecretStore/vault-local` points at Vault KV v2 (`path: secret`) over `http://host.docker.internal:8200` for the local cluster.
- The store authenticates with the scoped token in `external-secrets/vault-token`, not the administrative token.
- `ExternalSecret/database/agents-db-credentials` derives a Kubernetes Secret and owns it, so deletion is repaired and source changes propagate without a manual fetch.
- The seed policy `agents-infra-<profile>-read` already grants read on `secret/data/agents-infra/<profile>/*`, which covers a bot path under that prefix.

Secret inventory:

| Value | Vault key | Kubernetes Secret key | Bot input |
|---|---|---|---|
| LLM API key | `llm_api_key` | `llm_api_key` | `LLM_API_KEY_FILE=/run/secrets/llm_api_key` |
| GitHub token | `github_token` | `github_token` | `GITHUB_TOKEN_FILE=/run/secrets/github_token` |

Non-secret configuration stays in a ConfigMap: `LLM_BASE_URL`, the three model IDs, `GITHUB_API_URL`, `FAIL_ON`, `SECURITY_PASS`, limits and timeouts.

Paths:

```
local:       secret/agents-infra/<profile>/code-review-bot
production:  secret/code-review/<env>/bot
```

Local flow (reuse the existing `vault-local` store; no new controller):

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: code-review
---
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: code-review-bot-secrets
  namespace: code-review
spec:
  refreshInterval: 1m
  secretStoreRef:
    name: vault-local
    kind: ClusterSecretStore
  target:
    name: code-review-bot-secrets
    creationPolicy: Owner
  data:
    - secretKey: llm_api_key
      remoteRef:
        key: agents-infra/local/code-review-bot
        property: llm_api_key
    - secretKey: github_token
      remoteRef:
        key: agents-infra/local/code-review-bot
        property: github_token
```

The Job consumes the derived Secret by name; it never references Vault:

```yaml
          env:
            - { name: LLM_API_KEY_FILE, value: "/run/secrets/llm_api_key" }
            - { name: GITHUB_TOKEN_FILE, value: "/run/secrets/github_token" }
          volumeMounts:
            - { name: secrets, mountPath: /run/secrets, readOnly: true }
      volumes:
        - name: secrets
          secret:
            secretName: code-review-bot-secrets
            defaultMode: 0440
```

Seeding uses a mode-`0600` JSON payload rather than command-line arguments, so values do not appear in the process list:

```bash
umask 077
payload=$(mktemp)
trap 'rm -f "$payload"' EXIT
jq -n --arg llm "$LLM_API_KEY" --arg gh "$GITHUB_TOKEN" \
  '{llm_api_key:$llm,github_token:$gh}' > "$payload"
vault kv put secret/agents-infra/local/code-review-bot @"$payload"
```

Local Vault is in-memory: after the Vault container restarts, re-run the seed. ESO recreates the derived Secret once the path exists again.

Docker (outside Kubernetes) reads the two values into mode-`0600` files and mounts the directory read-only; no Vault token enters the container:

```bash
umask 077
mkdir -p /tmp/crb-secrets
vault kv get -field=llm_api_key secret/agents-infra/local/code-review-bot > /tmp/crb-secrets/llm_api_key
vault kv get -field=github_token secret/agents-infra/local/code-review-bot > /tmp/crb-secrets/github_token
# mount /tmp/crb-secrets at /run/secrets:ro; delete after the run
```

CI:

- **Recommended:** CI creates the Kubernetes Job; ESO injects the Secret in-cluster. The runner needs only Job-create RBAC, never the LLM key or GitHub token.
- **Outside the cluster:** use Vault OIDC (for example GitHub Actions OIDC) for a short-lived token, fetch into temp files, and pass `*_FILE`. Do not make GitHub Actions secrets a second permanent source of truth unless Vault is unreachable and that exception is documented.

Production (AKS):

- **Vault Kubernetes auth + ESO:** add a dedicated `ClusterSecretStore/vault-code-review` with `auth.kubernetes` (ESO service account + Vault role) and a read-only policy scoped to `secret/data/code-review/<env>/*`. No static token is stored in Kubernetes.
- **Azure Key Vault + Workload Identity:** use the Secrets Store CSI Driver or ESO's Azure provider. The bot still reads `/run/secrets/*`; only delivery changes.
- Pick one delivery path per environment; do not run both for the same Secret.

Rotation and recovery:

- Rotate the value in Vault; ESO refreshes (`1m` local, `5m` production); the next one-shot Job gets the new value. A running Job keeps the value it started with, which is acceptable for a one-shot workload.
- Delete the derived Secret: ESO recreates it.
- Vault restarts locally: re-seed; ESO recovers.
- ESO unavailable: the last derived Secret remains mounted, but rotation is stale; alert on `ExternalSecret Ready=False`.
- Suspected exposure: rotate in Vault first, then revoke the old GitHub token/LLM key and delete affected Jobs.

Security rules:

- The bot pod has **no Vault token** and no Kubernetes API token (`automountServiceAccountToken: false`). Only the ESO controller authenticates to Vault.
- The derived Kubernetes Secret is a cache, not the source of truth. Never create or edit it manually; never put values in Git, ConfigMaps, Job `env`, issue text, or logs.
- Kubernetes Secrets are base64, not encryption: enable etcd encryption at rest in production and restrict `get/list` on Secrets in the `code-review` namespace. The bot's service account needs no Secret permissions because kubelet mounts the volume.
- Mount files with `0440` (or `0400` with matching ownership); use `*_FILE`, not environment variables, for secret values.
- Vault policy is read-only and path-scoped; the local administrative token is never used by the cluster.

### Bot security and privacy

This section is about the bot's own security, not the security review of the PR.

| Threat                        | Vector                                                                                              | Control                                                                                                                                          | Verification                                                           |
|-------------------------------|-----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------|
| Prompt injection              | PR code/comments instruct a model to leak or misreport                                              | Untrusted-data system prompt; no shell/web/write/subagent tools; separate pass contexts; Principal audit; comment sanitization                   | Injection fixtures; tool-permission test                               |
| GitHub token theft            | Agent reads env/file or uses shell                                                                  | Token only in orchestrator; delivered by ESO as a mounted file; sanitized env for each OpenCode pass; askpass; no token in remote URL; redaction | Env-dump test; log scan                                                |
| Vault/ESO credential exposure | Bot pod or Job manifest gains a Vault token or a secret value                                       | Bot pod has no Vault token; ESO controller holds it; derived Secret mounted read-only; no secret in manifests or ConfigMaps                      | Pod env/volume inspection; manifest scan                               |
| Secret source drift           | Manual Secret or stale copy diverges from Vault                                                     | ESO owns the derived Secret; manual creation forbidden; refresh + rotation runbook                                                               | ExternalSecret `Ready=True`; rotation test                             |
| Secret committed in PR        | Diff contains a key; sending it to the LLM leaks it                                                 | Regex + entropy scan before the LLM call; replace with `[REDACTED_SECRET]`; emit a critical finding without the value                            | Seeded-secret fixture                                                  |
| Malicious repo                | Symlink escape, submodule, huge file, path traversal                                                | `core.symlinks=false`, no submodules, size caps, canonical path check, `external_directory` deny                                                 | Fixture with symlink/large file                                        |
| Repo-supplied agent config    | PR adds `.opencode/opencode.json`, `AGENTS.md`, or `CLAUDE.md` to alter instructions or permissions | Quarantine those paths before OpenCode starts; load only the bot's generated `.opencode/`; treat repo docs as data, never instructions           | Fixture with a malicious `AGENTS.md` / `.opencode`; assert ignored     |
| Cross-pass contamination      | Principal inherits Senior's framing and misses a bad candidate                                      | Fresh process, fresh session, separate brief; no shared transcript; different model recommended                                                  | Eval: Principal rejects a seeded false positive and adds a seeded miss |
| Principal over-rejection      | Noise budget suppresses a true critical/security issue                                              | Critical veto; false-rejection metric; escalation path; human review on uncertainty                                                              | Eval: zero false rejections of true critical/security                  |
| Arbitrary code execution      | Agent shell tool, build scripts, tests                                                              | Shell denied; no build/test execution; read-only rootfs                                                                                          | Permission config test; runtime probe                                  |
| Data exfiltration to LLM      | Full repo or unrelated files sent                                                                   | Diff + selected files + graph brief only; path exclusions; token budget; documented data boundary                                                | Context artifact inspection                                            |
| Comment injection             | Model output contains HTML/images/links/mentions                                                    | Escape HTML, strip images and external links, neutralize `@mentions` outside code spans, allow fenced code, cap size                             | Render test                                                            |
| Denial of service             | Huge PR, slow LLM, graph build, three passes                                                        | File/byte caps, per-pass timeouts, global deadline, memory limits, activeDeadlineSeconds                                                         | Load fixture                                                           |
| Supply chain                  | Compromised image/dependency/skill                                                                  | Pin digests/versions/commits; lockfile hashes; SBOM; Trivy; cosign; no runtime installs                                                          | CI scan; provenance check                                              |
| Over-broad token              | PAT with admin/org scopes                                                                           | Least-privilege scope check at startup; document required scopes; App migration path                                                             | Token introspection test                                               |

Privacy:

- Code and diff are sent to the configured LLM endpoint for each pass. The deployment documentation must state this plainly; the operator owns the endpoint's retention policy.
- Logs never include the diff, prompt, token, or API key at `info`; debug artifacts are opt-in and redacted.
- The bot does not persist repository contents beyond the pod's ephemeral volumes. `/cache` stores the graph (structural metadata, identifiers, and bounded docstring summaries), not full source files, and is optional.
- The triage artifact contains rejected finding titles and locations; treat it as internal review data, not public output.
- A `PRIVACY.md` and a short data-flow diagram ship with the image.

Process isolation:

- Scope child-process environments: `GITHUB_TOKEN` never leaves the orchestrator; git gets a dedicated `CRB_GIT_TOKEN`; each OpenCode pass gets the LLM variables plus `HOME`/`XDG_*`; the graph child (and optional MCP child when `GRAPH_MCP=on`) gets `CRG_*` and the workspace path.
- The agents' read permission is limited to the workspace; `external_directory` is denied, so `/proc`, the orchestrator's memory, and secret mounts are out of reach.
- The passes are separate processes with separate sessions; the Principal does not inherit the Senior's context or the Security Specialist's context.
- There is no separate verifier pass; the Principal is the verifier and the final gate.

Licensing:

- Vendored skills: MIT/Apache-2.0 only. Runtime dependencies: OSI-approved and distribution-compatible (MIT/BSD/Apache; `git` is GPL-2.0 as a separate binary). `THIRD_PARTY_NOTICES.md` lists each vendored skill, source URL, pinned commit, licence, and modifications.
- The bot's own licence is TBD (recommend Apache-2.0 for patent clarity; confirm before publishing).
- Do not copy `anthropics/skills` content without checking the per-skill `LICENSE.txt`. Do not copy OWASP/CWE text without checking its terms; reference the standard instead.
- `contains-studio/agents` has no declared licence and is not vendored.

### Observability and operations

- Structured JSON logs: `ts`, `level`, `run_id`, `event`, `pass`, `pr`, `duration_ms`, `counts`, `model`, `error_code`; never diff content or secrets.
- Artifacts: `review.json`, `summary.md`, `triage.json`, optional per-pass `context.md`/redacted NDJSON; emitted even on failure when possible.
- Metrics (opt-in OTLP): runs, Senior candidates, Principal rejection rate, final findings by severity, inline count, nit count, security pass trigger/rate, security escalations, tokens/cost per pass, latency by pass, gate failures.
- No health endpoint: the process is one-shot; the Job/exit code is the health signal. If a caller needs readiness, it should wait on the Job, not a port.
- Failure runbook:

| Symptom                        | Likely cause                                         | Action                                                     |
|--------------------------------|------------------------------------------------------|------------------------------------------------------------|
| Exit 2, "missing model"        | Incomplete model config                              | Set `LLM_MODEL` or all three role models                   |
| Exit 3, 401/403 from GitHub    | Bad/expired token or missing PR/issue write scope    | Rotate token; check fine-grained permissions               |
| Exit 4, provider 404           | Wrong base URL or model ID                           | Check `/models`; verify endpoint compatibility             |
| Exit 4, timeout                | Model slow / context too large                       | Raise timeout, reduce `MAX_FILES`, or use a faster model   |
| Exit 5, invalid JSON           | Model cannot follow schema                           | Try a stronger model; inspect redacted NDJSON; do not post |
| Exit 6                         | Gate failed                                          | Block merge or acknowledge                                 |
| Exit 8                         | Required security pass failed                        | Fix the security model/run; do not claim coverage          |
| Principal rejection rate < 30% | Senior too conservative or Principal rubber-stamping | Inspect triage ledger; tune Senior prompt/model            |
| Principal rejection rate > 60% | Senior too noisy or Principal over-rejecting         | Inspect false rejections; tune Senior candidate rules      |

### Testing and evaluation

Test at the highest seams: the `crb review` CLI (fake GitHub, fake OpenAI-compatible endpoint, fake `opencode` binary), each pass's JSON contract, the triage ledger, and the GitHub publish payload. Do not unit-test prompt prose; test the deterministic normalization and policy around the models.

| Layer | What | Tooling |
|---|---|---|
| Unit | Config/model fallback, URL parsing, diff hunk mapping, anchor validation, redaction, schema, dedupe, noise caps, rejection reasons, security trigger, gate, summary rendering, permission config, volume classifier, effort mapping/fallback, suggestion range validation, label skip/force, token aggregation, style linter, visible-metadata scrubber | `pytest`, `pytest-cov` |
| Contract | Senior/Security/Principal JSON fixtures, triage ledger, suggestion blocks, `comment_body` voice fixtures, token-usage events, label API calls, invalid/partial JSON, model-role/effort routing | `respx`/`pytest-httpserver`, recorded fixtures |
| Integration | Real `code-review-graph` on fixture repos; fake `opencode` binary; fake GitHub; fake OpenAI-compatible server | Docker Compose / pytest |
| End-to-end | Built image + fixture repo + fake GitHub + fake LLM; label skip/force, suggestion publishing, human-style comments, summary metrics; then real OpenCode + fake LLM | `docker run`, `pytest` |
| Quality eval | 30 PRs / 90 seeded defects across correctness, security, architecture/SOLID, and noise traps; real models | Eval harness, JSON results under `eval/results/` |
| Security | Prompt injection, secret leak, symlink escape, oversized file, token-in-env, comment injection, security-pass failure, principal veto | Fixtures + Trivy + custom assertions |

Fixture repositories:

- `fixtures/java-spring/` — a small Spring-style service with seeded defects: unchecked `Optional.get()`, self-invoked `@Transactional`, shared `SimpleDateFormat`, SQL string concatenation, unclosed stream, broken `equals`/`hashCode`, unsynchronized singleton mutation, missing test for a new branch, missing ownership check, exposed Actuator endpoint.
- `fixtures/python-fastapi/` — a small async service with seeded defects: mutable default argument, blocking `requests` in an async endpoint, SQL f-string, swallowed exception, path traversal, missing request timeout, meaningless pytest assertion, `yaml.load` without `SafeLoader`, missing auth dependency, JWT `alg: none`.
- **Architecture/SOLID fixtures:** a god class, a cyclic dependency, a leaky abstraction, a wrong abstraction, a dependency-inversion violation, and a speculative generality. Each has a "leave it alone" counterpart so the eval can check that the Principal does **not** over-flag.
- **Noise traps:** style-only diffs, naming preferences, hypothetical issues, pre-existing issues, already-handled guards, and tooling-catchable issues. These measure the Principal's rejection quality.
- **Publishing/label fixtures:** small/medium/large PRs for effort boundaries, a one-line local fix that produces a valid suggestion, a multi-line suggestion, an invalid suggestion that must fall back to prose, a pre-labeled PR that must skip, and a `FORCE` re-review fixture.
- **Voice fixtures:** bad structured comments (headings, `**Why:**`, confidence footer) that must be repaired or stripped; good human-style comments for comparison; comments with AI-tell phrases; comments over the word cap; a blind human sample of 20 posted comments.
- The Java and Python fixtures have 10 PR patches each; the architecture/SOLID and noise fixtures have 5 each, for 30 PRs total. Each PR has a base branch and ground truth (`eval/ground_truth/*.json`) listing expected findings, severity, path, line, and whether the finding is security-critical. Clean PRs measure false positives.

Eval metrics and gates:

- **Senior candidate recall** = seeded defects present in Senior candidates / all seeded defects ≥ 0.75.
- **Final precision** = correct posted findings / all posted findings ≥ 0.80.
- **Final recall** = seeded defects posted / all seeded defects ≥ 0.55; **critical recall** ≥ 0.95.
- **Security recall** ≥ 0.80 on seeded security defects; security precision ≥ 0.70; **zero critical security false negatives**.
- **Principal rejection rate** between 0.30 and 0.60; **zero false rejections** of true critical/security findings.
- **Noise:** median inline ≤ 4 per PR; ≤ 1 inline per 100 changed lines; 0 inline nits; ≤ 1 inline minor.
- **Anchor accuracy** = valid inline comments / all inline comments = 1.00 (hard gate).
- **Suggestion validity** = posted suggestion blocks whose ranges/replacements apply exactly / all posted suggestions = 1.00 (hard gate); suggestions that fail validation must be prose-only.
- **Summary accuracy**: token totals reconcile with per-pass usage; found/accepted/rejected/posted reconcile with the triage ledger; estimated usage is labelled `estimated`, never presented as measured.
- **Effort selection**: the volume class and per-role effort match the boundary fixtures; a missing variant is recorded as `prompt-fallback`, not as a failed run.
- **Label behaviour**: a labeled PR causes zero LLM calls; a successful run adds the label; a failed run leaves it absent; `FORCE` removes and re-adds it.
- **Voice**: 100% of posted inline comments pass the deterministic style lint (no headings, bold scaffolding, emojis, AI tells, visible model/confidence/run metadata; ≤ 120 words target). Blind human sample: average naturalness ≥ 4.0/5 and ≥ 80% "would a human reviewer write this?".
- **Latency** p95 ≤ 15 min for a two-pass review; ≤ 20 min with security.
- **Cost** recorded per pass; no hard dollar gate in v1, but a budget alert is recommended.
- Any prompt/model/skill change must rerun the eval and attach the delta to the PR.

Acceptance for the issue:

- [ ] `docker run` with the required inputs runs Senior → Principal and posts a curated review on a Java fixture PR and a Python fixture PR.
- [ ] The Security Specialist runs on seeded auth/SQL/deserialization diffs and is skipped on a non-sensitive docs-only PR.
- [ ] Inline comments are always anchored; unanchorable findings are in the summary; anchor accuracy is 1.00 on the eval.
- [ ] Final comments include applyable suggestion blocks where a safe local replacement exists; invalid suggestions are demoted to prose; the summary reports the suggestion count.
- [ ] The summary reports total/per-pass tokens, found/accepted/rejected/downgraded/added/posted, suggestions, effort, and label state; the counts reconcile with the artifact.
- [ ] A labeled PR is skipped with zero LLM calls; a successful review adds `AI Reviewed`; a run that fails before publishing leaves it absent; a gate failure after publishing still adds it; `FORCE=true` re-reviews and re-adds it only after success.
- [ ] Reasoning effort is selected from changed volume (low/medium/high), recorded per pass, and falls back to prompt mode when a variant is unavailable.
- [ ] Posted inline comments read like a senior reviewer: no headings, bold-label scaffolding, emojis, AI tells, or visible model/confidence/run metadata; ≤ 120 words target; blind human sample ≥ 80% "human-like".
- [ ] The summary has a short prose lead and a compact metrics footer; the machine verdict stays in the hidden marker.
- [ ] Only Principal-final findings are posted; the triage ledger records every rejection with a reason.
- [ ] Senior candidate recall, final precision/recall, critical recall, security recall, and rejection-rate targets are met and linked.
- [ ] Zero false rejections of true critical/security findings in the eval.
- [ ] Noise budget is enforced: ≤ 15 total, ≤ 10 inline, ≤ 1 inline minor, 0 inline nits.
- [ ] The graph is built and cited; `GRAPH_MODE=auto` degrades cleanly and says so.
- [ ] Skills are vendored, pinned, attributed; no runtime skill fetch.
- [ ] The agents cannot edit, shell, browse, or subagent; a permissions test proves it.
- [ ] Re-running the same head SHA creates no duplicate comments; `FORCE` still dedupes.
- [ ] `FAIL_ON=critical` returns exit 6; a required security failure returns exit 8; default `none` returns 0.
- [ ] The Job and initContainer manifests run under restricted Pod Security; the image is non-root/read-only.
- [ ] Unit/contract/integration/e2e tests pass; eval thresholds are met.
- [ ] Secret-leak scan of logs/artifacts is clean; image scan has no critical/high findings.
- [ ] Vault is the source of truth: ESO syncs `llm_api_key` and `github_token` into `code-review-bot-secrets`; the Job mounts them as files; the pod has no Vault token; no secret value appears in Git, ConfigMap, or Job manifest.
- [ ] Rotating a value in Vault propagates to the derived Secret and the next Job; Vault-restart recovery is documented and exercised locally.
- [ ] README, deployment guide, runbook, privacy note, and third-party notices are complete.

### Milestones and tickets

Each row is a vertical slice that is demoable or verifiable on its own. Detailed ticket files will be created under `.scratch/code-review-bot/issues/` when the issue moves to `In Progress`; this table is the index and the blocking graph.

| #  | Deliverable (end-to-end behaviour)                                                                                                                                                                      | Blocked by                        | Demo / verification                                                                                                                           |
|----|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| 01 | **Foundation:** package, CLI, config/model fallback/validation, JSON schema v2, fixture repos, fake GitHub/LLM harness, lint/test CI                                                                    | None                              | `crb validate-config` with good/bad env; unit suite green                                                                                     |
| 02 | **GitHub intake + workspace + diff anchors:** PR metadata/files/commits/linked issue, clone at head, merge-base, diff parser, sanitized checkout, dry-run JSON                                          | 01                                | Fixture PR dry-run produces correct metadata, diff, line map; token never logged                                                              |
| 03 | **Code graph:** pinned install, build/update, status, graph brief, optional MCP config, fallback                                                                                                         | 02                                | Java/Python fixture graph built; risk/callers/tests in context; graph failure degrades                                                        |
| 04 | **Senior review + effort:** senior agent + standards/spec/SOLID/language skills, volume classifier, low/medium/high effort with variant/prompt fallback, candidate JSON, schema/repair, no writes/shell | 03                                | Seeded defects found as candidates; small/medium/large fixtures select the expected effort; Senior recall measured; no final posting          |
| 05 | **Security specialist:** deep-security skill, sensitive-diff trigger, ASVS/Top10/CWE refs, security JSON, fail-closed                                                                                   | 03                                | Seeded SQLi/IDOR/JWT/deserialization findings; non-sensitive PR skips cleanly; failure exits 8                                                |
| 06 | **Principal review:** principal agent, audit/add/reject, noise budget, triage ledger, verdict, critical veto, suggestion_code, "leave it alone"                                                         | 04, 05                            | Principal rejects a noise trap, keeps a true critical, adds a missed material issue; valid/invalid suggestion ranges handled; ledger complete |
| 07 | **Publishing + summary + label:** token/issue summary, suggestion blocks, sticky summary, inline review, `AI Reviewed` skip/add/force, fingerprint dedupe, exit codes                                   | 06                                | E2E fixture PR gets curated summary + inline comments + suggestions + label; rerun skips; FORCE re-reviews; gate exits 6                      |
| 08 | **Container + Kubernetes + secrets:** Dockerfile, non-root/read-only, Compose, Job + initContainer manifests, NetworkPolicy, Vault/ESO ExternalSecret + seed script + rotation runbook, docs            | 07 (packaging can start after 02) | Image runs as UID 10001; Job succeeds on fixture; ExternalSecret `Ready=True`; pod has no Vault token; restricted-PSS checks pass             |
| 09 | **Eval + hardening + release:** 30-PR eval, Senior/Principal/security/noise metrics, security tests, SBOM/scan/sign, docs, `v0.1.0`                                                                     | 08                                | Eval thresholds met; scan clean; release notes and rollback verified                                                                          |

### Risks and rollback

| Risk                                            | Likelihood | Impact | Mitigation                                                                                                                                         |
|-------------------------------------------------|------------|--------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| Correlated blind spots (same model both passes) | High       | High   | Prefer different Senior/Principal models; record model identity; eval measures what Principal adds/rejects                                         |
| Principal over-rejects true issues              | Medium     | High   | Critical veto; false-rejection metric; escalation; human review on uncertainty                                                                     |
| Principal adds noise or scope creep             | Medium     | Medium | `MAX_ADDED=5`, critical/major only, noise budget, "leave it alone" list                                                                            |
| Senior floods the Principal                     | High       | Medium | Candidate cap, confidence floor, no style/nits, Senior prompt discipline                                                                           |
| Security false negatives                        | Medium     | High   | Dedicated specialist, ASVS/Top10/CWE coverage, seeded security eval, fail-closed on required pass                                                  |
| Two/three-pass cost and latency                 | High       | Medium | Model tiering (fast Senior, strong Principal), conditional security, caps, per-pass budgets                                                        |
| False positives erode trust                     | High       | High   | Principal audit, evidence rules, severity caps, precision-first eval, shadow mode                                                                  |
| A suggestion applies a wrong fix                | Medium     | High   | Exact/local/complete validation, conservative suggestion policy, prose fallback, author applies the commit, suggestion-validity eval               |
| Comments sound robotic or templated             | High       | Medium | `COMMENT_STYLE.md`, deterministic style lint, varied openings, blind human sample; repair then strip                                               |
| "Human-like" hides automation                   | Low        | High   | Bot account remains visible, no impersonation or invented experience, no false authorship claims; `AI Reviewed` label visible                      |
| Style repair damages technical meaning          | Low        | Medium | Repair only formatting/word choice; never alter code identifiers, evidence, or suggestion_code; deterministic strip fallback preserves the finding |
| Stale `AI Reviewed` label skips new commits     | Medium     | High   | Label is a deliberate manual gate; document removal and `FORCE=true`; Q24; visible summary explains the gate                                       |
| Label API fails after the review                | Low        | Medium | Label applied last, retries, exit 3; idempotency prevents duplicate comments on retry                                                              |
| Effort variant unsupported by the model         | Medium     | Medium | Prompt-mode fallback, `effort.applied` recorded, contract tests; never fail the review for effort                                                  |
| Token usage unavailable or misreported          | Medium     | Low    | Provider usage preferred; estimator fallback marked `estimated`/`unavailable`; reconcile totals before publishing                                  |
| Summary counts drift from the ledger            | Low        | High   | Schema reconciliation (`found = candidate_count`, `posted = posted_count`, token totals); exit 5 on mismatch                                       |
| Position drift / bad anchors                    | High       | High   | Diff-based line map, anchor validation, demote to summary, anchor-accuracy gate                                                                    |
| LLM output not valid JSON                       | Medium     | High   | Strict schema, one repair, model eval, reject models that cannot comply                                                                            |
| Graph cold start or partial parse               | Medium     | Medium | Warm cache option, 240 s cap, `auto` degradation, coverage note                                                                                    |
| Prompt injection                                | Medium     | High   | No shell/web/write; untrusted-data prompt; fresh pass contexts; Principal audit; sanitized comments                                                |
| Vault unavailable or ESO out of sync            | Medium     | High   | Last derived Secret remains mounted; alert on `ExternalSecret Ready=False`; re-seed local Vault after restart; runbook in `docs/SECRETS.md`        |
| Over-broad or expired Vault credential          | Medium     | High   | Read-only path-scoped policy; dedicated production store/role; periodic token or Kubernetes auth; alert on auth failures                           |
| Manual Secret drifts from Vault                 | Low        | High   | ESO owns `code-review-bot-secrets`; manual `kubectl create secret` forbidden; manifest scan in CI                                                  |
| Token/cost blow-up                              | Medium     | Medium | `MAX_FILES`, `MAX_DIFF_BYTES`, finding caps, token budget, per-pass cost in artifact                                                               |
| OpenCode API churn                              | Medium     | Medium | Pin binary, disable auto-update, contract tests, upgrade ADR                                                                                       |
| Java semantic blind spots                       | High       | Medium | Source-only disclaimer; graph facts as context; Phase 2 build/LSP option (Q6)                                                                      |
| GitHub rate limits                              | Low        | Medium | Backoff, conditional requests, one review per SHA, skip unchanged                                                                                  |
| Supply-chain compromise                         | Low        | High   | Pinned digests, lockfiles, SBOM, Trivy, cosign, no runtime installs                                                                                |
| Licence contamination                           | Low        | High   | Vendored skills MIT/Apache only; dependency licence review; `THIRD_PARTY_NOTICES.md`; legal review before release                                  |
| Existing-library churn/quality                  | Medium     | Medium | Adapt selected concepts, pin commits, no wholesale fork; eval before adoption                                                                      |

Rollback:

- Disable the CI workflow / suspend the Job; the bot has no persistent state to clean up beyond the optional graph cache.
- Pin the previous image digest; the deployment is immutable-image based, so rollback is a tag/digest change.
- Delete/rotate the LLM key and GitHub token if exposure is suspected; the agents never held the GitHub token, which limits blast radius.
- If bad comments were posted: delete the bot's review/comments by marker; the sticky summary is the single place to correct the record.
- If the Principal over-rejects in production, switch `ALLOW_NITS` back off (default), raise `MAX_FINDINGS`/`MAX_INLINE`, or temporarily bypass the Principal only with an explicit `PRINCIPAL_MODE=audit-only` run — do not silently post Senior candidates.

### Rollout

1. **Secrets first:** seed `secret/agents-infra/local/code-review-bot`, apply the `ExternalSecret`, and verify `Ready=True` plus both keys in `code-review-bot-secrets`; confirm the Job pod has no Vault token and no secret value appears in Git.
2. **Local dry-run** on the fixture repos; inspect Senior candidates, Security findings, Principal triage, and `review.json`; no GitHub writes.
3. **Shadow mode** on 5 real PRs in a test repo: post only the Principal's curated review, no gate; compare with human review; measure rejection rate and missed issues.
4. **Model comparison** on the eval corpus: same-model vs different-model Senior/Principal; pick the pair with the best final precision/recall and rejection quality.
5. **Pilot** on one team repo: comment-only, `FAIL_ON=none`, security pass `auto`; collect precision, noise, latency, and cost.
6. **Opt-in gate** on the pilot: `FAIL_ON=critical`; keep `major` non-blocking until precision is stable.
7. **Widen** only after two consecutive eval runs meet the thresholds and the pilot has no anchor/duplication incidents.
