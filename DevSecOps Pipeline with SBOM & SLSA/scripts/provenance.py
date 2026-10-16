#!/usr/bin/env python3
"""Create SLSA v1 predicate from the controller's actual, isolated build record."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def predicate(record, image, sbom_sha256):
    if not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image):
        raise ValueError("The pushed image must be identified by digest")
    if record["network"] != "none" or not record["readOnlyRoot"] or record["signingKeysMounted"]:
        raise ValueError("The build did not meet its isolation contract")
    if set(record["source"]) != {"index.html", "Dockerfile"} or not re.fullmatch("[0-9a-f]{64}", sbom_sha256):
        raise ValueError("Complete source and SBOM identity are required")
    return {"buildDefinition": {
        "buildType": "https://portfolio.example/build-types/static-site/v1",
        "externalParameters": {"source": "app", "image": image},
        "internalParameters": {"network": record["network"], "readOnlyRoot": record["readOnlyRoot"],
                               "signingKeysMounted": record["signingKeysMounted"], "noNewPrivileges": record["noNewPrivileges"]},
        "resolvedDependencies": [{"uri": "app/" + name, "digest": {"sha256": digest}} for name, digest in record["source"].items()]
            + [{"uri": record["workerImage"], "digest": {"sha256": record["workerImage"].split("@sha256:")[1]}},
               {"uri": record["runtimeImage"], "digest": {"sha256": record["runtimeImage"].split("@sha256:")[1]}},
               {"uri": "builder/build.sh", "digest": {"sha256": record["builderScriptSha256"]}}]},
        "runDetails": {"builder": {"id": record["builder"]},
                       "byproducts": [{"uri": "artifacts/sbom.cdx.json", "digest": {"sha256": sbom_sha256}}],
                       "metadata": {"invocationId": record["invocation"], "startedOn": record["started"], "finishedOn": record["finished"]}}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("image")
    args = parser.parse_args()
    value = predicate(json.loads((args.artifacts / "build-record.json").read_text()), args.image,
                      hashlib.sha256((args.artifacts / "sbom.cdx.json").read_bytes()).hexdigest())
    (args.artifacts / "provenance.json").write_text(json.dumps(value, indent=2) + "\n")
