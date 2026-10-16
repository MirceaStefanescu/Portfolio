#!/usr/bin/env python3
"""Binding checks on verified-envelope fixtures; real signatures need pipeline.sh."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("release_policy", Path(__file__).with_name("release-policy.py"))
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class Bindings(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.image = "localhost:5000/demo@sha256:" + "a" * 64
        self.record = {"builder": "https://portfolio.example/builders/isolated-static/v1",
            "invocation": "test", "workerImage": "demo@sha256:" + "b" * 64,
            "runtimeImage": "runtime@sha256:" + "c" * 64,
            "source": {name: hashlib.sha256((gate.ROOT / "app" / name).read_bytes()).hexdigest()
                       for name in ("index.html", "Dockerfile")},
            "builderScriptSha256": hashlib.sha256((gate.ROOT / "builder/build.sh").read_bytes()).hexdigest(),
            "network": "none", "readOnlyRoot": True, "signingKeysMounted": False,
            "noNewPrivileges": True, "started": "2026-01-01T00:00:00Z", "finished": "2026-01-01T00:00:01Z"}
        self.sbom = {"components": [{"type": "operating-system", "name": "aggregate"},
            {"type": "library", "name": "example", "licenses": [{"license": {"id": "MIT"}}]}]}
        self.write("image-digest.txt", self.image)
        self.write("build-record.json", self.record)
        self.write("sbom.cdx.json", self.sbom)
        self.statement = {"predicateType": "https://slsa.dev/provenance/v1",
            "predicate": gate.predicate(self.record, self.image, self.sbom_hash()),
            "subject": [{"name": "localhost:5000/demo", "digest": {"sha256": "a" * 64}}]}
        self.envelope()

    def write(self, name, value):
        (self.root / name).write_text(value if isinstance(value, str) else json.dumps(value))

    def sbom_hash(self):
        return hashlib.sha256((self.root / "sbom.cdx.json").read_bytes()).hexdigest()

    def envelope(self, array=False, repeat=False):
        value = {"payload": base64.b64encode(json.dumps(self.statement).encode()).decode()}
        self.write("cosign-attestation-verify.json", [value] if array else value)
        if repeat:
            with (self.root / "cosign-attestation-verify.json").open("a") as output:
                output.write("\n" + json.dumps(value))

    def test_valid_package_licenses_exclude_distribution_aggregate(self):
        self.assertEqual(gate.gate_input(self.root)["components"], [{"name": "example", "licenses": ["MIT"]}])

    def test_cosign_array_and_stream(self):
        self.envelope(array=True)
        self.assertTrue(gate.gate_input(self.root)["bindingsVerified"])
        self.envelope(repeat=True)
        self.assertTrue(gate.gate_input(self.root)["bindingsVerified"])

    def test_changed_source(self):
        self.record["source"]["index.html"] = "0" * 64
        self.write("build-record.json", self.record)
        with self.assertRaisesRegex(ValueError, "Source identity"):
            gate.gate_input(self.root)

    def test_changed_builder(self):
        self.record["builderScriptSha256"] = "0" * 64
        self.write("build-record.json", self.record)
        with self.assertRaisesRegex(ValueError, "Builder identity"):
            gate.gate_input(self.root)

    def test_missing_sources(self):
        self.record["source"] = {}
        self.write("build-record.json", self.record)
        with self.assertRaisesRegex(ValueError, "Complete source"):
            gate.gate_input(self.root)

    def test_other_image(self):
        self.statement["subject"][0]["digest"]["sha256"] = "b" * 64
        self.envelope()
        with self.assertRaisesRegex(ValueError, "does not bind"):
            gate.gate_input(self.root)

    def test_other_valid_json_sbom(self):
        changed = copy.deepcopy(self.sbom)
        changed["components"][1]["name"] = "substituted"
        self.write("sbom.cdx.json", changed)
        with self.assertRaisesRegex(ValueError, "does not bind"):
            gate.gate_input(self.root)

    def test_unattested_build(self):
        self.statement["predicate"]["runDetails"]["metadata"]["invocationId"] = "other-build"
        self.envelope()
        with self.assertRaisesRegex(ValueError, "does not bind"):
            gate.gate_input(self.root)

    def test_networked_build(self):
        self.record["network"] = "bridge"
        self.write("build-record.json", self.record)
        with self.assertRaisesRegex(ValueError, "isolation contract"):
            gate.gate_input(self.root)


if __name__ == "__main__":
    unittest.main()
