#!/usr/bin/env python3
"""Enforce licenses and the verified SLSA predicate before artifact replication."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from provenance import predicate

ROOT = Path(__file__).resolve().parents[1]


def gate_input(artifacts):
    image = (artifacts / "image-digest.txt").read_text().strip()
    digest = image.split("@sha256:")[-1]
    if not re.fullmatch("[0-9a-f]{64}", digest):
        raise ValueError("Invalid image digest")
    record = json.loads((artifacts / "build-record.json").read_text())
    for name, value in record["source"].items():
        if name not in ("index.html", "Dockerfile") or hashlib.sha256((ROOT / "app" / name).read_bytes()).hexdigest() != value:
            raise ValueError("Source identity changed after build")
    if hashlib.sha256((ROOT / "builder/build.sh").read_bytes()).hexdigest() != record["builderScriptSha256"]:
        raise ValueError("Builder identity changed after build")
    expected = predicate(record, image, hashlib.sha256((artifacts / "sbom.cdx.json").read_bytes()).hexdigest())
    verified = (artifacts / "cosign-attestation-verify.json").read_text().strip()
    # Cosign emits either one JSON object or multiple newline-delimited envelopes.
    decoder = json.JSONDecoder()
    envelopes = []
    while verified:
        value, length = decoder.raw_decode(verified)
        envelopes.extend(value if isinstance(value, list) else [value])
        verified = verified[length:].lstrip()
    statements = [json.loads(base64.b64decode(item["payload"], validate=True)) for item in envelopes]
    selected = next((statement for statement in statements if statement.get("predicateType") == "https://slsa.dev/provenance/v1"
                     and statement.get("predicate") == expected
                     and any(subject.get("digest", {}).get("sha256") == digest for subject in statement.get("subject", []))), None)
    if not selected:
        raise ValueError("Verified attestation does not bind the selected build and image")
    sbom = json.loads((artifacts / "sbom.cdx.json").read_text())
    components = []
    for component in sbom.get("components", []):
        # The distribution is an aggregate, not one licensable package. Every
        # individual package remains subject to the mandatory license gate.
        if component.get("type") == "operating-system":
            continue
        licenses = []
        for license in component.get("licenses", []):
            expression = license.get("expression") or license.get("license", {}).get("id") or license.get("license", {}).get("name", "")
            licenses.extend(token for token in re.findall(r"[A-Za-z0-9.+-]+", expression) if token not in ("AND", "OR", "WITH"))
        components.append({"name": component.get("name", "unnamed"), "licenses": sorted(set(licenses))})
    return {"components": components, "provenance": selected["predicate"], "bindingsVerified": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    args = parser.parse_args()
    data = gate_input(args.artifacts)
    gate = args.artifacts / "release-policy-input.json"
    gate.write_text(json.dumps(data, indent=2) + "\n")
    result = subprocess.run([os.environ.get("CONFTEST", "conftest"), "test", str(gate),
                             "--policy", str(ROOT / "policy/release"), "--data", str(ROOT / "policy/release/data.json"),
                             "--output", "json"], text=True, capture_output=True, timeout=30)
    (args.artifacts / "release-policy-result.json").write_text(result.stdout)
    if result.returncode:
        raise SystemExit("Release policy rejected the artifacts: " + result.stdout + result.stderr)
    print("License/provenance release policy passed")


if __name__ == "__main__":
    main()
