#!/usr/bin/env python3
"""Networkless static-site build; controller records evidence outside the worker."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASE = "cgr.dev/chainguard/nginx@sha256:bbed24ea6459404aeaf23edca30844092adee4d6059808cda5ebf9456a43d874"
WORKER = "cgr.dev/chainguard/busybox@sha256:f7d9063f22547e726221275158930e5033be3c6d8340c6867afb7d0d779fad8d"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command):
    result = subprocess.run(command, text=True, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr[-1500:])
    return result.stdout


def build(image, artifacts, app):
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker is required")
    if app.resolve() != (ROOT / "app").resolve():
        raise ValueError("The isolated example accepts only the bundled app")
    dockerfile = (app / "Dockerfile").read_text()
    if not dockerfile.startswith("FROM " + BASE + "\n") or re.search(r"(?im)^\s*(RUN|ADD|ARG|ONBUILD)\b", dockerfile):
        raise ValueError("Offline image assembly requires the pinned base and COPY-only Dockerfile")
    for path in [app, app / "index.html", app / "Dockerfile", ROOT / "builder/build.sh"]:
        if path.is_symlink() or not path.exists():
            raise ValueError("Build inputs must be regular, explicit local sources")
    # Resolve the pinned dependency before entering the networkless build phase.
    run([docker, "image", "inspect", BASE])
    run([docker, "image", "inspect", WORKER])
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    invocation = "portfolio-builder-" + uuid.uuid4().hex
    sources = {name: sha(app / name) for name in ("index.html", "Dockerfile")}
    artifacts.mkdir(parents=True, exist_ok=True)
    # A containerized CI agent and its Docker daemon share the workspace, but
    # generally have different /tmp directories. Keep bind sources in that
    # explicitly shared workspace and still remove the private build directory.
    with tempfile.TemporaryDirectory(prefix=invocation + "-", dir=artifacts.resolve()) as directory:
        work = Path(directory)
        source, output = work / "src", work / "out"
        source.mkdir(); output.mkdir()
        output.chmod(0o777)  # Only unsigned public build output, inside this private temporary directory.
        shutil.copyfile(app / "index.html", source / "index.html")
        user = str(os.getuid()) + ":" + str(os.getgid()) if os.name != "nt" and os.getuid() else "65532:65532"
        container = run([docker, "create", "--name", invocation, "--network", "none", "--read-only",
                         "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", user,
                         "--mount", f"type=bind,source={source},target=/src,readonly",
                         "--mount", f"type=bind,source={output},target=/out",
                         "--mount", f"type=bind,source={ROOT / 'builder'},target=/builder,readonly",
                         WORKER, "/bin/sh", "/builder/build.sh"]).strip()
        try:
            configuration = json.loads(run([docker, "inspect", container]))[0]
            host = configuration["HostConfig"]
            assert host["NetworkMode"] == "none" and host["ReadonlyRootfs"]
            assert "ALL" in host["CapDrop"] and any("no-new-privileges" in value for value in host["SecurityOpt"])
            assert not configuration["Config"].get("Env") or not any("COSIGN" in value for value in configuration["Config"]["Env"])
            run([docker, "start", "-a", container])
            assert json.loads(run([docker, "inspect", container]))[0]["State"]["ExitCode"] == 0
            if sha(output / "index.html") != sources["index.html"]:
                raise RuntimeError("Builder output differs from the selected static source")
            for name, digest in sources.items():
                if sha(app / name) != digest:
                    raise RuntimeError("Source changed while building")
            shutil.copyfile(app / "Dockerfile", output / "Dockerfile")
            run([docker, "build", "--network=none", "--pull=false", "--provenance=false", "-t", image, str(output)])
            record = {"builder": "https://portfolio.example/builders/isolated-static/v1", "invocation": invocation,
                      "workerImage": WORKER, "runtimeImage": BASE, "source": sources, "builderScriptSha256": sha(ROOT / "builder/build.sh"),
                      "network": "none", "readOnlyRoot": True, "capabilities": [], "signingKeysMounted": False,
                      "noNewPrivileges": True, "workerUser": user,
                      "imageId": json.loads(run([docker, "image", "inspect", image]))[0]["Id"],
                      "started": started, "finished": dt.datetime.now(dt.timezone.utc).isoformat()}
            artifacts.mkdir(parents=True, exist_ok=True)
            (artifacts / "build-record.json").write_text(json.dumps(record, indent=2) + "\n")
        finally:
            run([docker, "rm", container])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--app", type=Path, default=ROOT / "app")
    args = parser.parse_args()
    build(args.image, args.artifacts, args.app)
