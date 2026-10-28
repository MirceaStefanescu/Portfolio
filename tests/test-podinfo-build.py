"""Mocked regression tests for build-local-podinfo.py."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

_path = os.environ.get("PODINFO_CANDIDATE") or str(
    Path(__file__).resolve().parents[1] / "scripts" / "build-local-podinfo.py"
)
_spec = importlib.util.spec_from_file_location("podinfo_build", _path)
if _spec is None or _spec.loader is None:
    raise ImportError("Cannot load build-local-podinfo.py from " + _path)
podinfo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(podinfo)


class PodinfoBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "project"
        dockerfile = self.project / "scripts/local-podinfo/Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        dockerfile.write_bytes(b"FROM scratch\n")

    def case(self, name):
        root = self.base / name
        root.mkdir()
        return root, root / "work", root / "inputs/podinfo.tar"

    @staticmethod
    def archive(extra=()):
        out, prefix = io.BytesIO(), "podinfo-" + podinfo.REVISION
        files = {
            "go.mod": b"module example.test/podinfo\n",
            "go.sum": b"example.test/dependency v1.0.0 h1:fixture\n",
            "ui/index.html": b"<html>fixture</html>\n",
            "LICENSE": b"fixture license\n",
        }
        with tarfile.open(fileobj=out, mode="w") as tar:
            for name in ("", "ui"):
                item = tarfile.TarInfo(prefix + ("/" + name if name else ""))
                item.type = tarfile.DIRTYPE
                tar.addfile(item)
            for name, data in files.items():
                item = tarfile.TarInfo(prefix + "/" + name)
                item.size = len(data)
                tar.addfile(item, io.BytesIO(data))
            for item in extra:
                tar.addfile(item)
        return out.getvalue()

    def put_archive(self, path, extra=()):
        data = self.archive(extra)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data

    @staticmethod
    def seed(work, identity=True):
        source = work / ("podinfo-" + podinfo.REVISION)
        (source / "ui").mkdir(parents=True)
        files = {
            "go.mod": b"module example.test/podinfo\n",
            "go.sum": b"example.test/dependency v1.0.0 h1:fixture\n",
            "ui/index.html": b"<html>fixture</html>\n",
            "LICENSE": b"fixture license\n",
        }
        for name, data in files.items():
            (source / name).write_bytes(data)
        ca = b"fixture CA bundle\n"
        (work / "ca-certificates.crt").write_bytes(ca)
        if identity:
            record = {
                "revision": podinfo.REVISION, "archive_sha256": podinfo.ARCHIVE_SHA,
                "go.mod": hashlib.sha256((source / "go.mod").read_bytes()).hexdigest(),
                "go.sum": hashlib.sha256((source / "go.sum").read_bytes()).hexdigest(),
                "ca_sha256": hashlib.sha256((work / "ca-certificates.crt").read_bytes()).hexdigest(),
            }
            (work / "source-identity.json").write_text(
                json.dumps(record, indent=2), encoding="utf-8"
            )
        return source, files, ca

    @contextlib.contextmanager
    def mocked(self, args, *, version="go version go1.27.2 windows/amd64",
               check_effect=None, run_effect=None, responses=(), env=None):
        with contextlib.ExitStack() as stack:
            check = mock.Mock(return_value=version, side_effect=check_effect)
            run, urlopen = mock.Mock(side_effect=run_effect), mock.Mock(side_effect=list(responses))
            for target, name, value in (
                (podinfo.subprocess, "check_output", check),
                (podinfo.subprocess, "run", run), (podinfo, "urlopen", urlopen),
                (podinfo, "ROOT", self.project), (sys, "argv", ["build.py", *map(str, args)]),
            ):
                stack.enter_context(mock.patch.object(target, name, value))
            if env is not None:
                stack.enter_context(mock.patch.dict(os.environ, env))
            yield check, run, urlopen

    @staticmethod
    def fake_build(command, **_kwargs):
        if command[:2] == ["go", "build"]:
            Path(command[command.index("-o") + 1]).write_bytes(
                ("synthetic " + command[-1]).encode()
            )

    def test_phase_and_version_gates_precede_filesystem_work(self):
        _, work, archive = self.case("phase")
        with self.mocked(["--work-dir", work, "--archive", archive,
                          "--prepare-only", "--build-only"]) as (check, run, _):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                podinfo.main()
            check.assert_not_called()
            run.assert_not_called()
        self.assertFalse(work.exists())
        self.assertFalse(archive.parent.exists())
        for name, version, error in (
            ("wrong", "go version go1.0", None),
            ("failed", None, subprocess.CalledProcessError(1, ["go", "version"])),
            ("timeout", None, subprocess.TimeoutExpired(["go", "version"], 30)),
        ):
            with self.subTest(name=name):
                _, work, archive = self.case(name)
                options = {"version": version} if error is None else {"check_effect": error}
                with self.mocked(["--work-dir", work, "--archive", archive], **options) as (
                    check, run, _
                ):
                    if error is None:
                        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                            podinfo.main()
                    else:
                        with self.assertRaises(type(error)) as caught:
                            podinfo.main()
                        self.assertIs(caught.exception, error)
                    check.assert_called_once()
                    run.assert_not_called()
                self.assertFalse(work.exists())
                self.assertFalse(archive.parent.exists())

    def test_digest_and_download_copy_close_and_propagate(self):
        root, _, _ = self.case("download")
        sample = root / "abc"
        sample.write_bytes(b"abc")
        self.assertEqual(podinfo.digest(sample),
                         "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        response, target = io.BytesIO(b"exact response"), root / "downloaded"
        with mock.patch.object(podinfo, "urlopen", return_value=response) as urlopen:
            podinfo.download("https://example.invalid/file", target)
        self.assertEqual(target.read_bytes(), b"exact response")
        self.assertTrue(response.closed)
        urlopen.assert_called_once_with("https://example.invalid/file", timeout=60)
        with mock.patch.object(podinfo, "urlopen", side_effect=OSError("offline")):
            with self.assertRaisesRegex(OSError, "offline"):
                podinfo.download("https://example.invalid/file", root / "failed")
        self.assertFalse((root / "failed").exists())

    def test_archive_hash_mismatch_stops_before_extract_or_go(self):
        _, work, archive = self.case("hash")
        archive.parent.mkdir()
        archive.write_bytes(b"not accepted")
        with mock.patch.object(podinfo, "ARCHIVE_SHA", "wrong"):
            with self.mocked(["--work-dir", work, "--archive", archive]) as (_, run, _):
                with self.assertRaisesRegex(ValueError, "archive hash mismatch"):
                    podinfo.main()
                run.assert_not_called()
        self.assertFalse((work / ("podinfo-" + podinfo.REVISION)).exists())

    def test_links_and_devices_are_rejected_without_writes(self):
        for name, kind in (("link", tarfile.SYMTYPE), ("device", tarfile.CHRTYPE)):
            with self.subTest(name=name):
                root, work, archive = self.case(name)
                item = tarfile.TarInfo("podinfo-" + podinfo.REVISION + "/unsafe")
                item.type = kind
                if kind == tarfile.SYMTYPE:
                    item.linkname = "../../escaped"
                else:
                    item.devmajor, item.devminor = 1, 3
                data = self.put_archive(archive, (item,))
                with mock.patch.object(podinfo, "ARCHIVE_SHA", hashlib.sha256(data).hexdigest()):
                    with self.mocked(["--work-dir", work, "--archive", archive]) as (_, run, _):
                        with self.assertRaisesRegex(ValueError, "links or devices"):
                            podinfo.main()
                        run.assert_not_called()
                self.assertFalse((root / "escaped").exists())
                self.assertFalse((work / ("podinfo-" + podinfo.REVISION)).exists())

    def test_prepare_existing_archive_records_identity_without_building(self):
        _, work, archive = self.case("prepare")
        data = self.put_archive(archive)
        archive_hash = hashlib.sha256(data).hexdigest()
        ca, ca_hash = b"mock CA\n", hashlib.sha256(b"mock CA\n").hexdigest()
        responses = [io.BytesIO(ca), io.BytesIO((ca_hash + " ca.pem\n").encode())]
        with mock.patch.object(podinfo, "ARCHIVE_SHA", archive_hash):
            with self.mocked(["--work-dir", work, "--archive", archive, "--prepare-only"],
                             responses=responses) as (_, run, _):
                with contextlib.redirect_stdout(io.StringIO()):
                    podinfo.main()
                source = work / ("podinfo-" + podinfo.REVISION)
                self.assertEqual(json.loads((work / "source-identity.json").read_text()), {
                    "revision": podinfo.REVISION, "archive_sha256": archive_hash,
                    "go.mod": hashlib.sha256((source / "go.mod").read_bytes()).hexdigest(),
                    "go.sum": hashlib.sha256((source / "go.sum").read_bytes()).hexdigest(), "ca_sha256": ca_hash,
                })
                self.assertEqual((source / "ui/index.html").read_bytes(), b"<html>fixture</html>\n")
                self.assertEqual((source / "LICENSE").read_bytes(), b"fixture license\n")
                self.assertEqual((work / "ca-certificates.crt").read_bytes(), ca)
                self.assertEqual([c.args[0][1:] for c in run.call_args_list], [
                    ["mod", "edit", "-require=golang.org/x/net@v0.60.0"],
                    ["mod", "tidy"], ["mod", "verify"],
                ])

    def test_prepare_downloads_missing_archive_from_mocked_response(self):
        _, work, archive = self.case("download-archive")
        data, ca = self.archive(), b"download CA\n"
        ca_hash = hashlib.sha256(ca).hexdigest()
        responses = [io.BytesIO(data), io.BytesIO(ca),
                     io.BytesIO((ca_hash + " ca.pem\n").encode())]
        with mock.patch.object(podinfo, "ARCHIVE_SHA", hashlib.sha256(data).hexdigest()):
            with self.mocked(["--work-dir", work, "--archive", archive, "--prepare-only"],
                             responses=responses) as (_, run, _):
                with contextlib.redirect_stdout(io.StringIO()):
                    podinfo.main()
                self.assertEqual(archive.read_bytes(), data)
                self.assertTrue((work / "source-identity.json").exists())
                run.assert_called()

    def test_ca_mismatch_and_network_error_leave_no_identity(self):
        data = self.archive()
        cases = (
            ("checksum", [io.BytesIO(b"CA\n"), io.BytesIO(b"0" * 64 + b" ca.pem\n")], ValueError),
            ("network", [OSError("offline")], OSError),
        )
        expected = [["mod", "edit", "-require=golang.org/x/net@v0.60.0"],
                    ["mod", "tidy"], ["mod", "verify"]]
        for name, responses, error in cases:
            with self.subTest(name=name):
                _, work, archive = self.case("ca-" + name)
                archive.parent.mkdir(parents=True)
                archive.write_bytes(data)
                with mock.patch.object(podinfo, "ARCHIVE_SHA", hashlib.sha256(data).hexdigest()):
                    with self.mocked(["--work-dir", work, "--archive", archive, "--prepare-only"],
                                     responses=responses) as (_, run, _):
                        with self.assertRaises(error):
                            podinfo.main()
                        self.assertFalse((work / "source-identity.json").exists())
                        self.assertEqual([c.args[0][1:] for c in run.call_args_list], expected)
                        self.assertFalse(any(c.args[0][1:2] in (["test"], ["build"])
                                             for c in run.call_args_list))

    def test_build_only_rejects_missing_or_changed_admission_inputs(self):
        for name in ("missing", "go.mod", "go.sum", "ca-certificates.crt"):
            with self.subTest(name=name):
                _, work, _ = self.case("identity-" + name)
                source, _, _ = self.seed(work, identity=name != "missing")
                if name in ("go.mod", "go.sum"):
                    (source / name).write_bytes(b"changed\n")
                elif name == "ca-certificates.crt":
                    (work / name).write_bytes(b"changed\n")
                args = ["--work-dir", work, "--archive", work / "unused", "--build-only"]
                with self.mocked(args) as (_, run, _):
                    error = FileNotFoundError if name == "missing" else ValueError
                    with self.assertRaises(error):
                        podinfo.main()
                    run.assert_not_called()

    def test_valid_build_is_offline_and_populates_context(self):
        _, work, _ = self.case("valid")
        source, original, ca = self.seed(work)
        args = ["--work-dir", work, "--archive", work / "unused", "--build-only"]
        with self.mocked(args, run_effect=self.fake_build,
                         env={"GOOS": "darwin", "GOARCH": "arm64"}) as (_, run, _):
            podinfo.main()
            calls = run.call_args_list
            self.assertEqual([c.args[0] for c in calls[:-1]], [
                ["go", "mod", "verify"], ["go", "test", "-p", "4", "./pkg/..."],
                ["go", "build", "-p", "4", "-trimpath", "-ldflags=-s -w", "-o",
                 str(work / "container/podinfo"), "./cmd/podinfo"],
                ["go", "build", "-p", "4", "-trimpath", "-ldflags=-s -w", "-o",
                 str(work / "container/podcli"), "./cmd/podcli"],
            ])
            for c in calls[:-1]:
                env = c.kwargs["env"]
                self.assertTrue(c.kwargs["check"])
                self.assertEqual(c.kwargs["timeout"], 300)
                self.assertEqual((env["GOTOOLCHAIN"], env["CGO_ENABLED"]), ("local", "0"))
                self.assertEqual((env["GOPROXY"], env["GOSUMDB"]), ("off", "off"))
            for c in calls[:2]:
                self.assertNotIn("GOOS", c.kwargs["env"])
                self.assertNotIn("GOARCH", c.kwargs["env"])
            for c in calls[2:4]:
                self.assertEqual((c.kwargs["env"]["GOOS"], c.kwargs["env"]["GOARCH"]),
                                 ("linux", "amd64"))
            context = work / "container"
            self.assertEqual(calls[-1].args[0], [
                "docker", "build", "--network=none", "-t",
                "portfolio-podinfo:6.15.0-security1", str(context),
            ])
            self.assertEqual(calls[-1].kwargs["timeout"], 120)
            self.assertEqual({p.name for p in context.iterdir()},
                             {"podinfo", "podcli", "ui", "LICENSE", "ca-certificates.crt",
                              "Dockerfile", "tmp"})
            self.assertEqual((context / "ui/index.html").read_bytes(), original["ui/index.html"])
            self.assertEqual((context / "LICENSE").read_bytes(), original["LICENSE"])
            self.assertEqual((context / "ca-certificates.crt").read_bytes(), ca)
            self.assertEqual((context / "Dockerfile").read_bytes(),
                             (self.project / "scripts/local-podinfo/Dockerfile").read_bytes())
            self.assertTrue((context / "tmp").is_dir())
            self.assertEqual((context / "podinfo").read_bytes(), b"synthetic ./cmd/podinfo")
            self.assertEqual((context / "podcli").read_bytes(), b"synthetic ./cmd/podcli")

    def test_rerun_preserves_sources_and_kind_is_opt_in(self):
        _, work, _ = self.case("rerun")
        source, original, _ = self.seed(work)
        args = ["--work-dir", work, "--archive", work / "unused", "--build-only"]
        with self.mocked(args, run_effect=self.fake_build) as (_, run, _):
            podinfo.main()
            self.assertFalse(any(c.args[0][0] == "kind" for c in run.call_args_list))
            podinfo.main()
            docker = [c.args[0] for c in run.call_args_list if c.args[0][0] == "docker"]
            self.assertEqual(len(docker), 2)
            self.assertTrue(all(c[2] == "--network=none" for c in docker))
        with self.mocked(args + ["--kind", "cluster"], run_effect=self.fake_build) as (_, run, _):
            podinfo.main()
            self.assertEqual([c.args[0] for c in run.call_args_list if c.args[0][0] == "kind"], [
                ["kind", "load", "docker-image", "portfolio-podinfo:6.15.0-security1",
                 "--name", "cluster"]
            ])
        context = work / "container"
        self.assertEqual(len(list(context.iterdir())), 7)
        for name, content in original.items():
            self.assertEqual((source / name).read_bytes(), content)

    def test_go_and_docker_failures_block_later_stages_and_propagate(self):
        for stage in ("test", "build", "docker"):
            with self.subTest(stage=stage):
                _, work, _ = self.case("failure-" + stage)
                self.seed(work)
                error = subprocess.CalledProcessError(1, [stage])

                def fail(command, **_kwargs):
                    hit = command[0] == "docker" if stage == "docker" else command[:2] == ["go", stage]
                    if hit:
                        raise error
                    self.fake_build(command)

                args = ["--work-dir", work, "--archive", work / "unused",
                        "--build-only", "--kind", "cluster"]
                with self.mocked(args, run_effect=fail) as (_, run, _):
                    with self.assertRaises(subprocess.CalledProcessError) as caught:
                        podinfo.main()
                    self.assertIs(caught.exception, error)
                    commands = [c.args[0][0] for c in run.call_args_list]
                    self.assertNotIn("kind", commands)
                    if stage != "docker":
                        self.assertNotIn("docker", commands)


if __name__ == "__main__":
    unittest.main()
