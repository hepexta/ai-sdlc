from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _docs(name: str):
    return [d for d in yaml.safe_load_all((ROOT / "deploy" / "k8s" / name).read_text(encoding="utf-8")) if d]


def test_job_security_and_secret_contract() -> None:
    job = _docs("job.yaml")[0]
    pod = job["spec"]["template"]["spec"]
    assert pod["automountServiceAccountToken"] is False
    assert pod["securityContext"]["runAsNonRoot"] is True
    container = pod["containers"][0]
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
    assert container["resources"]["limits"]["memory"] == "3Gi"
    assert not container["image"].endswith(":latest")
    env = {item["name"]: item.get("value") for item in container["env"]}
    assert env["LLM_API_KEY_FILE"] == "/run/secrets/llm_api_key"
    assert env["GITHUB_TOKEN_FILE"] == "/run/secrets/github_token"
    assert "VAULT_TOKEN" not in env
    assert "GITHUB_TOKEN" not in env
    mounts = {item["name"]: item for item in container["volumeMounts"]}
    assert mounts["secrets"]["readOnly"] is True
    secret_volume = next(v for v in pod["volumes"] if v["name"] == "secrets")
    assert secret_volume["secret"]["secretName"] == "code-review-bot-secrets"


def test_external_secret_and_network_policy() -> None:
    ext = _docs("externalsecret.yaml")[0]
    assert ext["spec"]["secretStoreRef"]["name"] == "vault-local"
    keys = {item["secretKey"] for item in ext["spec"]["data"]}
    assert keys == {"llm_api_key", "github_token"}
    net = _docs("networkpolicy.yaml")[0]
    assert net["spec"]["policyTypes"] == ["Ingress", "Egress"]
    assert net["spec"]["ingress"] == []


@pytest.mark.skipif(shutil.which("kubectl") is None, reason="kubectl is not installed")
def test_kustomize_builds() -> None:
    proc = subprocess.run(
        ["kubectl", "kustomize", str(ROOT / "deploy" / "k8s")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    docs = [d for d in yaml.safe_load_all(proc.stdout) if d]
    assert {d["kind"] for d in docs} == {
        "Namespace",
        "ServiceAccount",
        "ExternalSecret",
        "Job",
        "NetworkPolicy",
    }
