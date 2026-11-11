# Kubernetes deployment

One `Job` per PR. The bot is not a long-running sidecar and must not be deployed as a Deployment.

## Prerequisites

- External Secrets Operator with a `ClusterSecretStore` named `vault-local`.
- Vault KV v2 path `secret/agents-infra/<profile>/code-review-bot` containing `llm_api_key` and `github_token`.
- An image pushed to a registry the cluster can pull; replace `ghcr.io/acme/code-review-bot:0.1.0`.
- A namespace where the Job is allowed to egress to GitHub and the LLM endpoint on TCP 443.

## Apply

```bash
kubectl apply -k deploy/k8s
```

Then edit `job.yaml` for the real PR URL, LLM endpoint, model IDs, and image. The `ExternalSecret` creates `code-review-bot-secrets`; the Job mounts it read-only at `/run/secrets`.

## Security contract

- Pod runs as UID/GID `10001`, non-root, read-only root filesystem, all capabilities dropped, `seccompProfile: RuntimeDefault`.
- No service-account token; no RBAC.
- `GITHUB_TOKEN` and `LLM_API_KEY` are never environment values; only `*_FILE` paths.
- No Vault token in the pod; ESO owns the sync.
- NetworkPolicy denies ingress and allows only DNS plus TCP 443 egress.
- The Job does not retry (`backoffLimit: 0`) because a repeated review could double-post; the label gate makes a manual retry safe.

## Local smoke test

From `code-review-bot/`:

```powershell
docker build -t code-review-bot:dev .
.\scripts\k8s-smoke.ps1
```

The script creates/reuses the kind cluster `crb-smoke`, loads the image, creates a plain test Secret, and runs the image as a Job with `validate-config`. It checks the effective config and cleans up the Job and Secret. It does not install ESO or exercise Vault; that is the production path.
