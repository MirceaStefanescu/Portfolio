#!/usr/bin/env python3
"""Readback, tamper rejection and HTTP smoke test after the local pipeline."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid


def run(command, expected=0):
    result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    if result.returncode != expected:
        raise RuntimeError(result.stderr[-1500:])
    return result.stdout + (result.stderr if len(command) > 1 and command[1] == "logs" else "")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--storage", type=Path, required=True)
    parser.add_argument("--backups", type=Path, required=True)
    parser.add_argument("--keys", type=Path, required=True)
    args = parser.parse_args()
    docker = shutil.which("docker")
    if not docker:
        parser.error("Docker is required")
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.artifacts.iterdir() if p.is_file()}
    if not files or not (args.artifacts / "release-policy-result.json").is_file():
        raise RuntimeError("Complete verified pipeline artifacts are required")
    backups = sorted(path for path in args.backups.iterdir() if path.is_dir())
    if not backups:
        raise RuntimeError("No backup exists")
    for destination in [args.storage / name for name in ("aws", "azure", "gcp")] + [backups[-1]]:
        actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.iterdir() if p.is_file()}
        if actual != files:
            raise RuntimeError("Replicated artifact identity differs: " + destination.name)
    with tempfile.TemporaryDirectory(prefix="portfolio-sbom-tamper-", dir=args.artifacts.resolve()) as directory:
        temp = Path(directory)
        sbom = json.loads((args.artifacts / "sbom.cdx.json").read_text())
        sbom["components"][0]["name"] += "-tampered"
        (temp / "sbom.cdx.json").write_text(json.dumps(sbom))
        shutil.copyfile(args.artifacts / "sbom.bundle.json", temp / "sbom.bundle.json")
        user = ["--user", f"{os.getuid()}:{os.getgid()}"] if hasattr(os, "getuid") else []
        rejected = subprocess.run([docker, "run", "--rm", *user, "--network=none",
            "-v", f"{args.keys.resolve()}:/keys:ro", "-v", f"{temp}:/artifacts:ro",
            os.environ.get("COSIGN_IMAGE", "gcr.io/projectsigstore/cosign:v3.1.3"), "verify-blob",
            "--insecure-ignore-tlog=true", "--key", "/keys/cosign.pub", "--bundle", "/artifacts/sbom.bundle.json",
            "/artifacts/sbom.cdx.json"], capture_output=True, text=True, timeout=60)
        if not rejected.returncode or not any(word in rejected.stderr.lower() for word in ("signature", "digest")):
            raise RuntimeError("Modified SBOM was not rejected cryptographically: " + rejected.stderr[-1000:])
    image = (args.artifacts / "image-digest.txt").read_text().strip()
    if not image.startswith(("localhost:", "127.0.0.1:")) or "@sha256:" not in image:
        raise RuntimeError("This verifier accepts only the local demo image digest")
    name = "portfolio-supply-http-" + uuid.uuid4().hex[:8]
    container = run([docker, "create", "--name", name, "--read-only", "--cap-drop=ALL",
        "--tmpfs", "/run", "--tmpfs", "/var/lib/nginx/tmp",
        "--security-opt=no-new-privileges", image]).strip()
    try:
        run([docker, "start", container])
        state = json.loads(run([docker, "inspect", container]))[0]["State"]
        if not state["Running"]:
            raise RuntimeError("Signed image failed to start: " + run([docker, "logs", container]))
        page = None
        # The agent and Docker daemon may have different loopback interfaces.
        # Read HTTP from this application's network namespace, without publishing
        # a host port or giving the probe any host mounts or credentials.
        client = [docker, "run", "--rm", "--network", "container:" + container,
            "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "python:3.15-slim", "python", "-c",
            "import base64,urllib.request; "
            "r=urllib.request.urlopen('http://127.0.0.1:8080',timeout=3); "
            "assert r.status==200; print(base64.b64encode(r.read()).decode())"]
        for _ in range(20):
            try:
                page = base64.b64decode(run(client).strip(), validate=True)
                break
            except (OSError, RuntimeError):
                time.sleep(0.5)
        expected = (Path(__file__).resolve().parents[1] / "app/index.html").read_bytes()
        if page != expected:
            raise RuntimeError("HTTP response does not match the signed build source")
    finally:
        run([docker, "stop", container])
        run([docker, "rm", container])
    print(json.dumps({"status": "PASS", "replicated_files_per_copy": len(files), "copies": 4,
        "sha256_readback": "PASS", "modified_sbom_rejected": "PASS", "signed_image_http": "PASS",
        "scope": "Local key and registry; filesystem cloud-storage demonstration"}, indent=2))


if __name__ == "__main__":
    main()
