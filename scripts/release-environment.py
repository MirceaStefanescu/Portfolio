#!/usr/bin/env python3
"""Create isolated previews or verified Argo canaries using the shared Helm chart."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "GitOps Platform - Argo CD & Helm/charts/platform-service"
OWNER = "portfolio.example/release-id"


def run(command, *, data=None, timeout=180):
    result = subprocess.run(command, input=data, text=True, encoding="utf-8",
                            capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{Path(command[0]).name} failed: {result.stderr.strip()}")
    return result.stdout


def checked_id(value):
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?", value):
        raise ValueError("id must be a DNS label of 1 to 40 characters")
    return value


def owned(namespace, identity):
    if namespace.get("metadata", {}).get("labels", {}).get(OWNER) != identity:
        raise ValueError("Refusing to adopt or delete a namespace owned by another workflow")
    return namespace["metadata"]["uid"]


def values(args):
    if not args.image_repository or not args.image_tag:
        raise ValueError("--image-repository and --image-tag are required")
    if args.image_tag == "latest" or not re.fullmatch(r"[\w][\w.-]{0,127}", args.image_tag):
        raise ValueError("Use a versioned image tag")
    if not 1 <= args.port <= 65535 or not args.health_path.startswith("/"):
        raise ValueError("Invalid service port or health path")
    if args.env_secret and (len(args.env_secret) > 253 or not re.fullmatch(
            r"[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?", args.env_secret)):
        raise ValueError("--env-secret must name an existing Kubernetes Secret, not contain credentials")
    env = []
    for item in args.env:
        name, separator, value = item.partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError("--env requires NAME=value; use --env-secret for credentials")
        env.append({"name": name, "value": value})
    return {
        "fullnameOverride": "app", "environment": args.mode,
        "image": {"repository": args.image_repository, "tag": args.image_tag},
        "service": {"port": args.port}, "replicaCount": args.replicas,
        "healthPath": args.health_path, "extraEnv": env, "envFromSecret": args.env_secret,
        "rollout": {"enabled": args.mode == "canary", "strategy": "canary",
                    "analysis": {"enabled": True, "path": args.analysis_path or args.health_path,
                                 "expectedStatus": args.expected_status}},
    }


def wait_canary(kubectl, namespace, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        obj = json.loads(run(kubectl + ["-n", namespace, "get", "rollout", "app", "-o", "json"]))
        status = obj.get("status", {})
        # A status from the preceding generation cannot accept the current image.
        if status.get("observedGeneration") == str(obj["metadata"]["generation"]) or (
                status.get("observedGeneration") == obj["metadata"]["generation"]):
            if status.get("phase") == "Healthy":
                return
            if status.get("phase") == "Degraded":
                raise RuntimeError("Canary rejected: " + (status.get("message") or "analysis or readiness failed"))
        time.sleep(2)
    raise TimeoutError("Canary did not complete within the requested deadline")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["deploy", "remove"])
    parser.add_argument("--mode", choices=["preview", "canary"], required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--context", required=True, help="Explicit Kubernetes context; never uses a default")
    parser.add_argument("--image-repository")
    parser.add_argument("--image-tag")
    parser.add_argument("--port", type=int, default=9898)
    parser.add_argument("--health-path", default="/healthz")
    parser.add_argument("--analysis-path", help="Candidate JSON health measurement; defaults to readiness path")
    parser.add_argument("--expected-status", default="OK", help="Exact JSON status value returned by health endpoint")
    parser.add_argument("--replicas", type=int, default=2)
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--env-secret", default="", help="Name of an existing Kubernetes Secret; never its contents")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--events", type=Path, help="Optional local deployment JSONL ledger")
    parser.add_argument("--revision", default="")
    parser.add_argument("--committed-at", help="UTC/RFC3339 commit timestamp for measured lead time")
    args = parser.parse_args()
    try:
        identity = checked_id(args.id)
        if not 1 <= args.replicas <= 20 or not 10 <= args.timeout <= 600:
            raise ValueError("replicas must be 1..20 and timeout 10..600 seconds")
        configuration = values(args) if args.operation == "deploy" else None
    except ValueError as error:
        parser.error(str(error))
    namespace = args.mode + "-" + identity
    kubectl = [shutil.which("kubectl") or "kubectl", "--context", args.context]
    helm = [shutil.which("helm") or "helm", "--kube-context", args.context]
    current_text = run(kubectl + ["get", "namespace", namespace, "--ignore-not-found", "-o", "json"])
    current = json.loads(current_text) if current_text.strip() else None
    if current:
        owned(current, identity)
    if args.operation == "remove":
        if not current:
            print(json.dumps({"namespace": namespace, "status": "already absent"}))
            return
        # Kubernetes enforces UID and resourceVersion to prevent deleting a replacement.
        deletion = {"apiVersion": "v1", "kind": "DeleteOptions", "preconditions": {
            "uid": current["metadata"]["uid"], "resourceVersion": current["metadata"]["resourceVersion"]}}
        with tempfile.TemporaryDirectory(prefix="portfolio-release-") as tmp:
            request = Path(tmp) / "delete.json"
            request.write_text(json.dumps(deletion), encoding="utf-8")
            run(kubectl + ["delete", "--raw", "/api/v1/namespaces/" + namespace, "-f", str(request)])
        run(kubectl + ["wait", "--for=delete", "namespace/" + namespace, "--timeout=120s"])
        print(json.dumps({"namespace": namespace, "status": "removed"}))
        return
    if args.mode == "canary":
        run(kubectl + ["get", "crd", "rollouts.argoproj.io", "analysistemplates.argoproj.io"])
    started = datetime.now(timezone.utc).isoformat()
    result = "failed"
    try:
        # Keep configuration and rendered environment values in process pipes.
        # Neither credentials nor sensitive configuration belong in temporary files.
        payload = json.dumps(configuration)
        rendered = run(helm + ["template", "app", str(CHART), "-n", namespace, "-f", "-"], data=payload)
        run([shutil.which("conftest") or "conftest", "test", "-", "--parser", "yaml",
             "--all-namespaces", "--policy", str(ROOT / "policies")], data=rendered)
        if not current:
            document = {"apiVersion": "v1", "kind": "Namespace", "metadata": {
                "name": namespace, "labels": {OWNER: identity}}}
            # Create, never apply/adopt on a conflicting concurrent namespace.
            run(kubectl + ["create", "-f", "-"], data=json.dumps(document))
        # Services' selectors are reconciled by Argo. Helm 4's default SSA
        # conflicts with that legitimate controller ownership on every update.
        # Client-side merge retains controller-added selector fields; no force.
        helm4 = run(helm + ["version", "--short"]).startswith("v4.")
        apply_mode = ["--server-side=false"] if helm4 else []
        # Argo's status.phase is checked below, including observedGeneration.
        # Helm 4's generic watcher cannot infer readiness for a Rollout CR.
        wait_mode = "--wait=legacy" if helm4 else "--wait"
        run(helm + ["upgrade", "--install", "app", str(CHART), "-n", namespace,
                    "-f", "-", wait_mode, "--timeout", str(args.timeout) + "s"] + apply_mode,
            data=payload, timeout=args.timeout + 20)
        if args.mode == "canary":
            wait_canary(kubectl, namespace, args.timeout)
        else:
            run(kubectl + ["-n", namespace, "rollout", "status", "deployment/app",
                           "--timeout=" + str(args.timeout) + "s"], timeout=args.timeout + 10)
        result = "success"
        print(json.dumps({"namespace": namespace, "service": "app",
                          "mode": args.mode, "status": "PASS"}))
    finally:
        if args.events:
            entry = {"kind": "deployment", "id": str(uuid.uuid4()), "service": identity,
                     "environment": args.mode, "revision": args.revision, "status": result,
                     "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
                     "committed_at": args.committed_at}
            with args.events.open("a", encoding="utf-8") as output:
                output.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    main()
