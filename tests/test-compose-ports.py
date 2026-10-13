"""Validate Compose syntax and the loopback-only contract for local demos."""
import json
import os
import secrets
import sys
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = subprocess.check_output(
    ["git", "ls-files", "-z", "*docker-compose*.yml"], cwd=root
).decode().strip("\0").split("\0")
assert files and all(files), "No Compose manifests found"
environment = os.environ.copy()
environment["JWT_SECRET"] = secrets.token_urlsafe(32)
environment["DEV_API_KEY"] = secrets.token_urlsafe(32)
ports_checked = 0
for name in files:
    result = subprocess.run(
        ["docker", "compose", "-f", str(root / name), "config",
         "--no-env-resolution", "--format", "json"],
        check=False, capture_output=True, text=True, env=environment,
    )
    if result.returncode:
        sys.exit(f"{name}: {result.stderr.strip()}")
    configuration = json.loads(result.stdout)
    for service, value in configuration["services"].items():
        for port in value.get("ports", []):
            assert port.get("host_ip") == "127.0.0.1", (
                f"{name}: {service} publishes {port.get('target')} beyond loopback"
            )
            ports_checked += 1
print(f"Validated {len(files)} Compose manifests and {ports_checked} loopback ports")
