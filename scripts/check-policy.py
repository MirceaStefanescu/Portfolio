#!/usr/bin/env python3
"""Run native Conftest gates on project manifests, Helm output and Terraform plans."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(command):
    subprocess.run(command, check=True, timeout=120)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--plan", type=Path, help="JSON from terraform show -json of the exact saved plan")
    args = parser.parse_args()
    project = args.project.resolve(strict=True)
    conftest = shutil.which("conftest")
    if not conftest:
        parser.error("Conftest 0.71.1 is required; install the official verified release")
    common = [conftest, "test", "--all-namespaces", "--policy", str(ROOT / "policies")]
    run([conftest, "verify", "--policy", str(ROOT / "policies")])
    files = []
    for folder in ("k8s", "kubernetes", "vault/policies", "terraform"):
        for suffix in ("*.yaml", "*.yml", "*.hcl", "*.tf"):
            files.extend(path for path in (project / folder).rglob(suffix)
                         if not any(part.startswith(".") for part in path.relative_to(project).parts))
    charts = [path.parent for folder in ("helm", "charts") for path in (project / folder).rglob("Chart.yaml")]
    with tempfile.TemporaryDirectory(prefix="portfolio-policy-") as temporary:
        # Mixed CRLF/LF from Windows chart templates can make the YAML parser
        # read only the first document. Normalize bytes, never remove documents.
        for index, path in enumerate(sorted(set(files))):
            normalized = Path(temporary) / f"source-{index}{path.suffix}"
            normalized.write_text(path.read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
            print(f"Checking {path.relative_to(project)}", flush=True)
            run(common + [str(normalized)])
        for index, chart in enumerate(charts):
            helm = shutil.which("helm")
            if not helm:
                parser.error("Helm is required to validate rendered manifests")
            rendered = Path(temporary) / f"chart-{index}.yaml"
            result = subprocess.run([helm, "template", "policy-check", str(chart)], capture_output=True,
                                    text=True, encoding="utf-8", check=True, timeout=120)
            rendered.write_text(result.stdout, encoding="utf-8", newline="\n")
            print(f"Checking rendered chart {chart.relative_to(project)}", flush=True)
            run(common + [str(rendered)])
    if args.plan:
        run(common + [str(args.plan.resolve(strict=True))])
    if not files and not charts and not args.plan:
        parser.error("No policy inputs found; nothing has been validated")


if __name__ == "__main__":
    main()
