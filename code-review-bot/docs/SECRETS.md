# Secrets and Vault integration

**Status:** Planning design for [issue 0001](../../.scratch/0001-code-review-bot.md). Not implemented yet.

## Decision

**Vault KV v2 is the source of truth. External Secrets Operator (ESO) syncs the values into a Kubernetes Secret. The bot consumes that Secret as files (`LLM_API_KEY_FILE`, `GITHUB_TOKEN_FILE`) and never talks to Vault itself.**

This reuses the pattern already proven in `C:\Work\Projects\AI\agents-infra\k8s-cluster`:

- ESO chart `2.12.0`.
- `ClusterSecretStore/vault-local` → Vault `http://host.docker.internal:8200`, KV v2 at mount `secret`.
- The store authenticates with the scoped token in `external-secrets/vault-token`, not the Vault root token.
- `ExternalSecret/database/agents-db-credentials` derives a Kubernetes Secret from Vault and owns it, so deleting the derived Secret recreates it and a source change propagates without a manual fetch.

The bot adds one Vault path and one `ExternalSecret`; it does **not** add a Vault SDK, a Vault sidecar, or a Vault token to the bot pod.

```
Vault KV v2
  secret/agents-infra/<profile>/code-review-bot
        │  (ESO controller reads with its scoped token)
        ▼
ExternalSecret/code-review-bot-secrets  (namespace: code-review)
        │  creates/owns
        ▼
Kubernetes Secret/code-review-bot-secrets
        │  mounted read-only at /run/secrets
        ▼
Job pod  ──  LLM_API_KEY_FILE=/run/secrets/llm_api_key
        └──  GITHUB_TOKEN_FILE=/run/secrets/github_token
```

## Secret inventory

Only two values are secrets. Everything else belongs in a ConfigMap or Job environment.

| Value        | Vault key      | Kubernetes Secret key | Bot input                                     |
|--------------|----------------|-----------------------|-----------------------------------------------|
| LLM API key  | `llm_api_key`  | `llm_api_key`         | `LLM_API_KEY_FILE=/run/secrets/llm_api_key`   |
| GitHub token | `github_token` | `github_token`        | `GITHUB_TOKEN_FILE=/run/secrets/github_token` |

Non-secret configuration (ConfigMap, not Vault): `LLM_BASE_URL`, `LLM_MODEL_SENIOR`, `LLM_MODEL_PRINCIPAL`, `LLM_MODEL_SECURITY`, `GITHUB_API_URL`, `FAIL_ON`, `SECURITY_PASS`, `MAX_*`, timeouts.

If the GitHub token is later replaced by a GitHub App, add `github_app_id` (non-secret) plus `github_app_private_key` (secret) to the same path; the `*_FILE` contract stays the same. The token must allow **Pull requests read/write** (review comments) and **Issues read/write** (sticky summary + `AI Reviewed` label).

## Vault path layout

Local/development, under the prefix the existing seed policy already covers:

```
secret/agents-infra/<profile>/code-review-bot
  llm_api_key    = ...
  github_token   = ...
```

Production, a dedicated prefix per environment:

```
secret/code-review/<env>/bot
  llm_api_key    = ...
  github_token   = ...
```

The profile in the local path matches the existing convention (`local` is the default). Do not put secrets under a repository-specific path: the GitHub token and LLM key are per-environment, not per-PR or per-repo.

## Local: reuse the existing store

The existing policy `agents-infra-<profile>-read` grants read on `secret/data/agents-infra/<profile>/*` and read/list on the metadata path. The bot path is inside that prefix, so the existing `ClusterSecretStore/vault-local` and token can read it — **no new store is required for local development**.

Create the namespace and ExternalSecret:

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

If a dedicated local store is preferred, create a second `ClusterSecretStore` named `vault-code-review` with its own token secret in the `external-secrets` namespace and a policy scoped only to the bot path. That is more isolation, but it is optional for local.

## Seeding local secrets

Do not pass secret values as command-line arguments (they can appear in the process list). Build a mode-`0600` JSON payload and hand the file to the Vault CLI:

```bash
#!/bin/sh
set -eu

: "${LLM_API_KEY:?set LLM_API_KEY in the environment}"
: "${GITHUB_TOKEN:?set GITHUB_TOKEN in the environment}"

VAULT_ADDR=${VAULT_ADDR:-http://127.0.0.1:8200}
VAULT_PATH=${VAULT_PATH:-secret/agents-infra/local/code-review-bot}
export VAULT_ADDR

payload=$(mktemp)
trap 'rm -f "$payload"' EXIT
umask 077
jq -n --arg llm "$LLM_API_KEY" --arg gh "$GITHUB_TOKEN" \
  '{llm_api_key:$llm,github_token:$gh}' > "$payload"

vault kv put "$VAULT_PATH" @"$payload"
rm -f "$payload"
echo "seeded $VAULT_PATH"
```

`vault kv put ... @file` reads the whole JSON object from the file, so neither value appears in `ps`. `jq` is already commonly present in the developer environment; if not, write the JSON with a small Python one-liner or use `vault kv put` with stdin.

Local Vault is in-memory (see `agents-infra/k8s-cluster/README.md`): after the Vault container restarts, run this seed again. ESO recreates the derived Kubernetes Secret once the source path exists again.

## Local Docker (outside Kubernetes)

Read each value into a mode-`0600` file and mount the directory read-only:

```bash
umask 077
mkdir -p /tmp/crb-secrets
vault kv get -field=llm_api_key secret/agents-infra/local/code-review-bot > /tmp/crb-secrets/llm_api_key
vault kv get -field=github_token secret/agents-infra/local/code-review-bot > /tmp/crb-secrets/github_token

docker run --rm \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=256m \
  --tmpfs /workspace:rw,noexec,nosuid,size=2g \
  --tmpfs /out:rw,noexec,nosuid,size=128m \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  -v /tmp/crb-secrets:/run/secrets:ro \
  -e LLM_BASE_URL="https://llm.example/v1" \
  -e LLM_MODEL_SENIOR="acme/reviewer-fast" \
  -e LLM_MODEL_PRINCIPAL="acme/reviewer-strong" \
  -e LLM_MODEL_SECURITY="acme/reviewer-security" \
  -e LLM_API_KEY_FILE=/run/secrets/llm_api_key \
  -e GITHUB_TOKEN_FILE=/run/secrets/github_token \
  -e PR_URL="https://github.com/acme/service/pull/42" \
  ghcr.io/acme/code-review-bot:0.1.0
```

Delete `/tmp/crb-secrets` after the run. Never use `docker run -e LLM_API_KEY=...` or an `--env-file` that is committed.

## CI

**Recommended: CI creates a Kubernetes Job; ESO injects the secrets in-cluster.** The CI runner needs only permission to create/suspend Jobs in the `code-review` namespace, not the LLM or GitHub credentials:

```bash
kubectl --context "$CONTEXT" -n code-review create job \
  --from=cronjob/code-review-bot-template "crb-pr-$PR_NUMBER"
```

The Job's pod references `secretName: code-review-bot-secrets`; kubelet mounts it; the bot reads the files. The runner never sees a secret value.

**If CI must run Docker outside the cluster**, use Vault OIDC (for example, GitHub Actions OIDC with a Vault JWT role) to obtain a short-lived token, fetch the two values into memory/temp files, and pass them to the container as `*_FILE`. Do not store long-lived LLM/GitHub credentials in GitHub Actions secrets when Vault is the source of truth. If the CI runner cannot reach Vault at all, GitHub Secrets is a fallback, but it creates a second source of truth and must be documented.

## Production (AKS)

Two supported shapes, both preserving the bot's `*_FILE` contract:

1. **Vault Kubernetes auth + ESO (matches the existing platform).**
   Add a dedicated `ClusterSecretStore/vault-code-review` with `auth.kubernetes`:

   ```yaml
   apiVersion: external-secrets.io/v1
   kind: ClusterSecretStore
   metadata:
     name: vault-code-review
   spec:
     provider:
       vault:
         server: https://vault.example
         path: secret
         version: v2
         auth:
           kubernetes:
             mountPath: kubernetes
             role: code-review-bot
             serviceAccountRef:
               name: external-secrets
               namespace: external-secrets
   ```

   The Vault role binds the ESO service account and a read-only policy scoped to `secret/data/code-review/<env>/*`. No static token is stored in Kubernetes. The `ExternalSecret` uses `secretStoreRef: {name: vault-code-review, kind: ClusterSecretStore}` and the same two `remoteRef` keys under `code-review/<env>/bot`.

The ESO service account name depends on the release; confirm it rather than assuming:

```bash
kubectl -n external-secrets get serviceaccount
```

```bash
vault policy write code-review-bot-read - <<'EOF'
path "secret/data/code-review/prod/*" {
  capabilities = ["read"]
}
path "secret/metadata/code-review/prod/*" {
  capabilities = ["read", "list"]
}
EOF

vault write auth/kubernetes/role/code-review-bot \
  bound_service_account_names=external-secrets \
  bound_service_account_namespaces=external-secrets \
  policies=code-review-bot-read \
  ttl=1h
```

Adjust the policy prefix to the environment (`prod`, `staging`, …) and the service account name to the ESO release. The bot pod never authenticates to Vault; only the ESO controller does.

2. **Azure Key Vault + Workload Identity (if the managed cluster standardizes on Key Vault).**
   Use the Secrets Store CSI Driver or ESO's Azure Key Vault provider with workload identity. The bot still reads `/run/secrets/llm_api_key` and `/run/secrets/github_token`; only the delivery controller changes. This matches the "same shape fronts a cloud secret manager with workload identity" note in the cluster README.

Do not run both delivery paths for the same Secret. Pick one per environment.

## Kubernetes consumption

The Job never references Vault. It references the derived Secret:

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

`automountServiceAccountToken: false` stays set: the bot pod does not need a Kubernetes API token or a Vault token. The ESO controller, not the bot, authenticates to Vault.

## Rotation and recovery

| Event                               | Action                                                                                                               | Verification                                                                                                                        |
|-------------------------------------|----------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| LLM key or GitHub token rotated     | `vault kv put` the new value; wait for ESO refresh (`1m` local / `5m` prod); create the next Job                     | `kubectl -n code-review get externalsecret code-review-bot-secrets -o jsonpath='{.status.conditions}'`; next Job uses the new value |
| Derived Secret deleted              | Nothing; ESO recreates it                                                                                            | `kubectl -n code-review get secret code-review-bot-secrets`                                                                         |
| Vault container restarted (local)   | Re-run the seed script; ESO recovers once the path exists                                                            | ExternalSecret `Ready=True`                                                                                                         |
| Vault token expired/revoked (local) | Re-run `vault-seed.sh`; update `external-secrets/vault-token` as `addons-up.sh` does; ESO revalidates on its backoff | `kubectl -n external-secrets get secret vault-token`; ExternalSecret Ready                                                          |
| ESO unavailable                     | The last derived Secret remains mounted; a new Job can still run with the last synced values, but rotation is stale  | Alert on ExternalSecret `Ready=False`; fix ESO before relying on new values                                                         |
| Suspected exposure                  | Rotate in Vault first, then restart/delete affected Jobs; revoke the old GitHub token/LLM key                        | Vault audit log + GitHub token revocation                                                                                           |

A running Job keeps the Secret values it started with; because the workload is one-shot, the next Job is the reload boundary. If the bot ever becomes a long-running sidecar, use an explicit reload/restart strategy instead of assuming env/file updates propagate.

## Security rules

- **No secret values in Git**, Dockerfiles, ConfigMaps, Job `env` values, issue comments, or logs. Only paths and key names are committed.
- **Vault is the source of truth**; the Kubernetes Secret is a derived cache owned by the `ExternalSecret`. Do not create it manually or edit it.
- **The bot pod has no Vault token.** ESO's controller holds the Vault credential in the `external-secrets` namespace; the bot mounts only the derived Secret.
- **Least privilege at Vault.** The bot path policy is read-only; production uses a dedicated role/store. Do not reuse the root token.
- **Kubernetes Secret is not encryption.** Enable etcd encryption at rest in production and restrict `get/list` on Secrets in the `code-review` namespace. The bot's service account needs no Secret permissions because kubelet mounts the volume.
- **Files, not env, for secrets.** `LLM_API_KEY_FILE` / `GITHUB_TOKEN_FILE` avoid env leakage in process listings and crash dumps. Mount mode `0440` (or `0400` with matching ownership).
- **Rotate on a schedule** and after any suspected exposure; use fine-grained GitHub tokens and per-environment LLM keys.
- **Audit** Vault access and ESO sync status; alert on `Ready=False` and on repeated Vault auth failures.

## Verification commands

```bash
# ESO sees the source and derived the Secret
kubectl -n code-review get externalsecret code-review-bot-secrets
kubectl -n code-review get secret code-review-bot-secrets

# The keys exist; do not print the values
kubectl -n code-review get secret code-review-bot-secrets \
  -o go-template='{{range $k,$v := .data}}{{$k}} {{end}}{{"\n"}}'

# The Job mounted the files (inside the pod; print sizes, not contents)
kubectl -n code-review exec job/crb-pr-42 -- \
  sh -c 'wc -c /run/secrets/llm_api_key /run/secrets/github_token'

# Vault path exists (local admin token only for inspection)
VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=dev-token \
  vault kv get secret/agents-infra/local/code-review-bot
```

## Why not the alternatives

- **Direct Vault SDK in the bot:** puts a Vault token in the pod, adds another auth path, and makes the review container depend on Vault network reachability. ESO already solves delivery.
- **Manual `kubectl create secret`:** drifts from Vault, leaks into shell history/CI logs, and has no rotation or ownership.
- **Secrets in a committed `values.yaml`/`.env`:** unacceptable; even encrypted files add a key-management problem the platform already solved.
- **A Vault sidecar per Job:** more moving parts and another token; ESO is the existing cluster-wide pattern.
- **Long-lived static token in production:** use Vault Kubernetes auth or workload identity; the local static token is a development convenience only.

## Related

- [Issue 0001 — code review bot](../../.scratch/0001-code-review-bot.md)
- [Project README](../README.md)
- Existing platform: `agents-infra/k8s-cluster/scripts/vault-seed.sh`, `agents-infra/k8s-cluster/scripts/addons-up.sh`, `agents-infra/k8s-cluster/addons/external-secrets/`.
