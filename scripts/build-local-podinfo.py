#!/usr/bin/env python3
"""Rebuild pinned podinfo sources with patched Go/x/net and package without an OS base."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from urllib.request import urlopen

REVISION = "dd507173b7b75b2312a36cabe0de5f09c1ce69c8"
ARCHIVE_SHA = "bf5ac81b6be50ed19e7d400ffac1456c7ba0461a71a5db3fffcb88998f8af727"
ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, path):
    with urlopen(url, timeout=60) as response, path.open("wb") as output:
        shutil.copyfileobj(response, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True, help="Private build workspace")
    parser.add_argument("--archive", type=Path, required=True, help="Pinned source download location")
    parser.add_argument("--go", default="go")
    parser.add_argument("--kind")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only and args.build_only:
        parser.error("Choose one phase")
    env = dict(os.environ, GOTOOLCHAIN="local", CGO_ENABLED="0")
    version = subprocess.check_output([args.go, "version"], text=True, env=env, timeout=30)
    if " go1.27.2 " not in version:
        parser.error("This reproducible build is verified with Go 1.27.2")
    args.work_dir = args.work_dir.resolve()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    source = args.work_dir / ("podinfo-" + REVISION)
    admission = args.work_dir / "source-identity.json"
    def go(*command, offline=False, target=False):
        settings = env.copy()
        settings.pop("GOOS", None)
        settings.pop("GOARCH", None)
        if offline:
            settings.update(GOPROXY="off", GOSUMDB="off")
        if target:
            settings.update(GOOS="linux", GOARCH="amd64")
        subprocess.run([args.go, *command], cwd=source, env=settings, check=True, timeout=300)
    if not args.build_only:
        args.archive.parent.mkdir(parents=True, exist_ok=True)
        if not args.archive.exists():
            download("https://codeload.github.com/stefanprodan/podinfo/tar.gz/" + REVISION, args.archive)
        if digest(args.archive) != ARCHIVE_SHA:
            raise ValueError("Official source archive hash mismatch")
        if not source.exists():
            with tarfile.open(args.archive) as stream:
                members = stream.getmembers()
                if any(not (item.isfile() or item.isdir()) for item in members):
                    raise ValueError("Archive contains unexpected links or devices")
                stream.extractall(args.work_dir, members=members, filter="data")
        go("mod", "edit", "-require=golang.org/x/net@v0.60.0")
        go("mod", "tidy")
        go("mod", "verify")
        ca = args.work_dir / "ca-certificates.crt"
        download("https://curl.se/ca/cacert.pem", ca)
        with urlopen("https://curl.se/ca/cacert.pem.sha256", timeout=30) as response:
            expected = response.read().decode().split()[0]
        if digest(ca) != expected:
            raise ValueError("Public CA bundle checksum mismatch")
        identity = {"revision": REVISION, "archive_sha256": ARCHIVE_SHA,
                    "go.mod": digest(source / "go.mod"), "go.sum": digest(source / "go.sum"),
                    "ca_sha256": digest(ca)}
        admission.write_text(json.dumps(identity, indent=2), encoding="utf-8")
    if args.prepare_only:
        print("Prepared source/module identities. No project code has been executed.")
        return
    identity = json.loads(admission.read_text(encoding="utf-8"))
    for name in ("go.mod", "go.sum"):
        if digest(source / name) != identity[name]:
            raise ValueError("Prepared module identity changed")
    if digest(args.work_dir / "ca-certificates.crt") != identity["ca_sha256"]:
        raise ValueError("Prepared CA bundle changed")
    go("mod", "verify", offline=True)
    go("test", "-p", "4", "./pkg/...", offline=True)
    context = args.work_dir / "container"
    context.mkdir(exist_ok=True)
    for binary in ("podinfo", "podcli"):
        go("build", "-p", "4", "-trimpath", "-ldflags=-s -w", "-o", str(context / binary),
           "./cmd/" + binary, offline=True, target=True)
    shutil.copytree(source / "ui", context / "ui", dirs_exist_ok=True)
    shutil.copy2(source / "LICENSE", context / "LICENSE")
    shutil.copy2(args.work_dir / "ca-certificates.crt", context / "ca-certificates.crt")
    shutil.copy2(ROOT / "scripts/local-podinfo/Dockerfile", context / "Dockerfile")
    (context / "tmp").mkdir(exist_ok=True)
    image = "portfolio-podinfo:6.15.0-security1"
    subprocess.run(["docker", "build", "--network=none", "-t", image, str(context)],
                   check=True, timeout=120)
    if args.kind:
        subprocess.run(["kind", "load", "docker-image", image, "--name", args.kind],
                       check=True, timeout=120)


if __name__ == "__main__":
    main()
