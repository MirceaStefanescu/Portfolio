#!/usr/bin/env python3
"""Demonstrate KMS-backed auto-unseal and guarded replication using local Vault.

Three new file-backed Vault instances are removed after testing. Root/recovery
credentials stay in memory; output contains only status, versions and digests.
This is an application-level KV replication demo, not Vault Enterprise DR.
"""
import hashlib
import datetime as dt
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid


class VaultError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__("Vault returned HTTP " + str(status))


def api(port, path, body=None, token=None, method=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Vault-Token"] = token
    request = urllib.request.Request(f"http://127.0.0.1:{port}/v1/{path}",
        data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raise VaultError(error.code) from None


def wait(check, description, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            result = check()
            if result:
                return result
        except (OSError, VaultError):
            pass
        time.sleep(1)
    raise RuntimeError("Timed out: " + description)


def replicate(source, source_token, target, target_token, expected_version):
    document = api(source, "secret/data/app", token=source_token)["data"]
    result = api(target, "secret/data/app", {"data": document["data"], "options": {"cas": expected_version}}, target_token)
    copied = api(target, "secret/data/app", token=target_token)["data"]
    if copied["data"] != document["data"]:
        raise RuntimeError("Replication readback differs")
    return {"source_version": document["metadata"]["version"], "target_version": result["data"]["version"],
            "sha256": hashlib.sha256(json.dumps(document["data"], sort_keys=True).encode()).hexdigest()}


def read_available(regions):
    for region, port, token in regions:
        try:
            return region, api(port, "secret/data/app", token=token)["data"]["data"]
        except (OSError, VaultError):
            continue
    raise RuntimeError("No region can serve the secret")


def main():
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker is required")
    project = "portfolio-kms-demo-" + uuid.uuid4().hex[:8]
    environment = os.environ.copy()
    environment["DEMO_KMS_TOKEN"] = "bootstrap-not-yet-issued"
    with tempfile.TemporaryDirectory(prefix=project + "-") as directory:
        root = Path(directory)
        common = 'disable_mlock = true\nui = true\nstorage "file" { path = "/vault/file" }\nlistener "tcp" { address = "0.0.0.0:8200"\n tls_disable = true }\n'
        (root / "kms.hcl").write_text(common + 'api_addr = "http://kms:8200"\n')
        for region in ("east", "west"):
            (root / (region + ".hcl")).write_text(common + f'api_addr = "http://{region}:8200"\n' +
                'seal "transit" {\n address = "http://kms:8200"\n key_name = "region-seal"\n mount_path = "transit/"\n}\n')
        config = {"services": {}, "volumes": {}}
        for name in ("kms", "east", "west"):
            config["volumes"][name + "-data"] = {}
            service = {"image": "hashicorp/vault:2.1.2", "command": ["server", "-config=/etc/demo/server.hcl"],
                       "ports": [{"target": 8200, "published": "0", "host_ip": "127.0.0.1"}],
                       "volumes": [{"type": "bind", "source": str(root / (name + ".hcl")), "target": "/etc/demo/server.hcl", "read_only": True},
                                   {"type": "volume", "source": name + "-data", "target": "/vault/file"}]}
            if name != "kms":
                # Vault's API client otherwise waits 60 seconds per KMS request.
                # Bound this local demonstration's outage handling explicitly.
                service["environment"] = {"VAULT_TOKEN": "${DEMO_KMS_TOKEN}", "VAULT_CLIENT_TIMEOUT": "3s"}
            config["services"][name] = service
        compose = root / "compose.json"
        compose.write_text(json.dumps(config))
        command = [docker, "compose", "-p", project, "-f", str(compose)]
        def run(arguments):
            result = subprocess.run(command + arguments, env=environment, text=True, capture_output=True, timeout=90)
            if result.returncode:
                raise RuntimeError("Compose operation failed: " + arguments[0])
            return result.stdout + (result.stderr if arguments[0] == "logs" else "")
        def port(name):
            return int(run(["port", name, "8200"]).strip().rsplit(":", 1)[1])
        try:
            print("Starting isolated KMS/region demo: " + project, flush=True)
            run(["up", "-d", "kms"])
            kms = port("kms")
            wait(lambda: api(kms, "sys/seal-status"), "KMS starts")
            bootstrap = api(kms, "sys/init", {"secret_shares": 1, "secret_threshold": 1})
            api(kms, "sys/unseal", {"key": bootstrap["keys_base64"][0]})
            kms_root = bootstrap["root_token"]
            api(kms, "sys/mounts/transit", {"type": "transit"}, kms_root)
            api(kms, "transit/keys/region-seal", {"type": "aes256-gcm96"}, kms_root)
            policy = 'path "transit/encrypt/region-seal" { capabilities = ["update"] }\npath "transit/decrypt/region-seal" { capabilities = ["update"] }'
            api(kms, "sys/policies/acl/region-seal", {"policy": policy}, kms_root, "PUT")
            environment["DEMO_KMS_TOKEN"] = api(kms, "auth/token/create-orphan", {"policies": ["region-seal"], "period": "1h"}, kms_root)["auth"]["client_token"]
            run(["up", "-d", "east", "west"])
            ports, tokens = {}, {}
            for region in ("east", "west"):
                ports[region] = port(region)
                wait(lambda region=region: api(ports[region], "sys/seal-status"), region + " starts")
                initialized = api(ports[region], "sys/init", {"recovery_shares": 1, "recovery_threshold": 1})
                tokens[region] = initialized["root_token"]
                wait(lambda region=region: not api(ports[region], "sys/seal-status")["sealed"], region + " auto-unsealed")
                api(ports[region], "sys/mounts/secret", {"type": "kv", "options": {"version": "2"}}, tokens[region])
            first = {"db_password": secrets.token_urlsafe(24), "rotated_at": "synthetic-v1"}
            api(ports["east"], "secret/data/app", {"data": first, "options": {"cas": 0}}, tokens["east"])
            one = replicate(ports["east"], tokens["east"], ports["west"], tokens["west"], 0)
            second = {"db_password": secrets.token_urlsafe(24), "rotated_at": "synthetic-v2"}
            api(ports["east"], "secret/data/app", {"data": second, "options": {"cas": 1}}, tokens["east"])
            try:
                replicate(ports["east"], tokens["east"], ports["west"], tokens["west"], 0)
                raise AssertionError("Stale replica version must be rejected")
            except VaultError as error:
                assert error.status == 400
            assert api(ports["west"], "secret/data/app", token=tokens["west"])["data"]["data"] == first
            two = replicate(ports["east"], tokens["east"], ports["west"], tokens["west"], 1)
            api(kms, "transit/keys/region-seal/rotate", {}, kms_root)
            assert api(kms, "transit/keys/region-seal", token=kms_root)["data"]["latest_version"] == 2
            run(["restart", "east"])
            ports["east"] = port("east")
            wait(lambda: not api(ports["east"], "sys/seal-status")["sealed"], "Auto-unseal after restart and KMS key rotation")
            assert api(ports["east"], "secret/data/app", token=tokens["east"])["data"]["data"] == second
            run(["stop", "east"])
            region, data = read_available([(name, ports[name], tokens[name]) for name in ("east", "west")])
            assert region == "west" and data == second
            run(["stop", "west", "kms"])
            outage_start = dt.datetime.now(dt.timezone.utc).isoformat()
            run(["start", "west"])
            def unavailable_without_kms():
                state = json.loads(run(["ps", "-a", "--format", "json", "west"]))
                log = run(["logs", "--no-color", "--since", outage_start, "west"]).lower()
                seal_error = "seal" in log and any(text in log for text in ("connection refused", "no such host", "lookup kms", "timeout", "context deadline exceeded"))
                if state["State"] == "exited" and seal_error:
                    return {"process": "exited", "kms_connection_failure": True}
                try:
                    if api(port("west"), "sys/seal-status")["sealed"]:
                        return {"sealed": True}
                except (OSError, RuntimeError):
                    # Vault can remain alive retrying seal initialization without
                    # opening its listener. Require its KMS failure log as evidence.
                    return {"process": state["State"], "kms_connection_failure": True} if seal_error else False
                return False
            try:
                blocked = wait(unavailable_without_kms, "Region fails closed without its KMS", 30)
            except RuntimeError:
                print("KMS failure diagnostic: " + run(["logs", "--no-color", "--tail", "12", "west"]), flush=True)
                raise
            run(["start", "kms"])
            kms = port("kms")
            wait(lambda: api(kms, "sys/seal-status"), "KMS restart")
            api(kms, "sys/unseal", {"key": bootstrap["keys_base64"][0]})
            run(["start", "west"])
            ports["west"] = port("west")
            wait(lambda: not api(ports["west"], "sys/seal-status")["sealed"], "Region recovers after KMS")
            assert api(ports["west"], "secret/data/app", token=tokens["west"])["data"]["data"] == second
            print(json.dumps({"status": "PASS", "auto_unseal": "PASS", "kms_key_rotation": "PASS",
                "persistent_restart": "PASS", "replication": [one, two], "compare_and_set_conflict": "PASS",
                "failover_region": region, "kms_outage_recovery": "PASS", "kms_outage_evidence": blocked,
                "scope": "Local Transit KMS and application KV replication; no cloud account or Enterprise DR"}, indent=2), flush=True)
        finally:
            run(["down", "--volumes", "--remove-orphans"])
            remaining = subprocess.check_output([docker, "ps", "-aq", "--filter", "label=com.docker.compose.project=" + project], text=True).strip()
            assert not remaining, "Demo cleanup left containers"
            print("Own KMS/region containers and volumes removed.", flush=True)


if __name__ == "__main__":
    main()
