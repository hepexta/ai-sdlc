param(
  [string]$Cluster = "crb-smoke",
  [string]$Image = "code-review-bot:dev",
  [switch]$Keep
)

$ErrorActionPreference = "Continue"
$Context = "kind-$Cluster"

$previous = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
$clusters = @(kind get clusters 2>$null)
$ErrorActionPreference = $previous
if (-not ($clusters -contains $Cluster)) {
  Write-Host "Creating kind cluster $Cluster ..."
  kind create cluster --name $Cluster --wait 180s
  if ($LASTEXITCODE -ne 0) { throw "kind create cluster failed" }
}

Write-Host "Loading $Image into $Cluster ..."
kind load docker-image $Image --name $Cluster
if ($LASTEXITCODE -ne 0) { throw "kind load docker-image failed" }

kubectl --context $Context apply -f (Join-Path $PSScriptRoot "..\deploy\k8s\namespace.yaml")
if ($LASTEXITCODE -ne 0) { throw "namespace apply failed" }
kubectl --context $Context -n code-review-bot create secret generic code-review-bot-secrets `
  --from-literal=llm_api_key=test-llm `
  --from-literal=github_token=test-gh `
  --dry-run=client -o yaml | kubectl --context $Context apply -f -
if ($LASTEXITCODE -ne 0) { throw "secret apply failed" }

$job = @'
apiVersion: batch/v1
kind: Job
metadata:
  name: code-review-bot-smoke
  namespace: code-review-bot
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 180
  template:
    metadata:
      labels:
        app.kubernetes.io/name: code-review-bot
    spec:
      restartPolicy: Never
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: smoke
          image: code-review-bot:dev
          imagePullPolicy: IfNotPresent
          args: ["validate-config"]
          env:
            - { name: PR_URL, value: "https://github.com/acme/service/pull/1" }
            - { name: LLM_BASE_URL, value: "https://llm.example/v1" }
            - { name: LLM_MODEL_SENIOR, value: "fast" }
            - { name: LLM_MODEL_PRINCIPAL, value: "strong" }
            - { name: LLM_API_KEY_FILE, value: "/run/secrets/llm_api_key" }
            - { name: GITHUB_TOKEN_FILE, value: "/run/secrets/github_token" }
            - { name: HOME, value: "/tmp" }
            - { name: TMPDIR, value: "/tmp" }
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits: { cpu: 500m, memory: 512Mi }
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - { name: secrets, mountPath: /run/secrets, readOnly: true }
            - { name: tmp, mountPath: /tmp }
      volumes:
        - name: secrets
          secret:
            secretName: code-review-bot-secrets
        - name: tmp
          emptyDir: {}
'@
$job | kubectl --context $Context apply -f -
if ($LASTEXITCODE -ne 0) { throw "job apply failed" }

kubectl --context $Context -n code-review-bot wait --for=condition=complete job/code-review-bot-smoke --timeout=180s
if ($LASTEXITCODE -ne 0) {
  kubectl --context $Context -n code-review-bot describe job/code-review-bot-smoke
  kubectl --context $Context -n code-review-bot logs job/code-review-bot-smoke
  throw "smoke Job did not complete"
}
$logs = kubectl --context $Context -n code-review-bot logs job/code-review-bot-smoke
$logs
$logText = $logs -join "`n"
if ($logText -notmatch '"pr"') {
  throw "validate-config output did not contain the expected configuration"
}

if (-not $Keep) {
  kubectl --context $Context -n code-review-bot delete job code-review-bot-smoke --ignore-not-found
  kubectl --context $Context -n code-review-bot delete secret code-review-bot-secrets --ignore-not-found
}
Write-Host "Kubernetes smoke test passed."
