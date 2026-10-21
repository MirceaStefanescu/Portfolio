"""Manual Sonar baseline: generate reports without changing application files."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ORG = "mirceastefanescu"
PREFIX = "mirceastefanescu_portfolio_"

ROOTS = {
    "infrastructure": "Automated Infrastructure & Deployment Platform",
    "cloud-commerce": "Cloud-Native E-Commerce Platform",
    "devsecops": "DevSecOps Pipeline with SBOM & SLSA",
    "event-commerce": "Event-Driven E-Commerce Platform",
    "fullstack-commerce":
        "Full Stack E-commerce Application with Angular and Spring Boot",
    "gitops": "GitOps Platform - Argo CD & Helm",
    "habit-tracker": "Habit Tracker & Routine Coach SaaS",
    "finops": "Kubernetes FinOps & Cost Optimization",
    "llmops": "LLMOps Evaluation Harness",
    "observability": "Observability - New Relic & Prometheus",
    "predictive": "Predictive Analytics Pipeline on Kubernetes",
    "prompt-safety": "Prompt Quality & Safety",
    "chat": "Real-Time Chat & Collaboration Platform",
    "rag": "Secure RAG Service & Knowledge API",
    "secrets": "Secure Secrets Management & Observability Toolkit",
    "cicd": "CI/CD Pipeline Automation",
    "shared": ".github,scripts,tests,policies,portfolio-launcher.sh,README.md",
}

JAVA = {
    "event-order":
        (ROOTS["event-commerce"] + "/services/order-service", "25"),
    "event-inventory":
        (ROOTS["event-commerce"] + "/services/inventory-service", "25"),
    "fullstack-backend": (ROOTS["fullstack-commerce"] + "/backend", "26"),
    "chat-backend": (ROOTS["chat"] + "/backend", "25"),
    "rag-api": (ROOTS["rag"] + "/api", "25"),
    "predictive-api": (ROOTS["predictive"] + "/api", "25"),
    "predictive-flink": (ROOTS["predictive"] + "/flink", "11"),
}

# kind, directory relative to project, test glob or Python source directory
UNITS = {
    "infrastructure": [("node", "portal", "")],
    "cloud-commerce": [
        ("python", "services/" + service, "app")
        for service in (
            "product-service", "order-service", "payment-service", "gateway"
        )
    ],
    "fullstack-commerce": [("angular", "frontend", "")],
    "habit-tracker": [
        ("node", "backend", "test/*.test.js"),
        ("node", "frontend", "test/*.test.js"),
    ],
    "llmops": [("python", ".", "src")],
    "prompt-safety": [("python", ".", "src")],
    "chat": [("angular", "frontend", "")],
    "secrets": [("node", "app", "test/*.test.js")],
    "cicd": [("node", ".", "tests/**/*.test.js")],
}

GENERATED = [
    "**/.devtools/**", "**/node_modules/**", "**/.venv/**",
    "**/target/**", "**/dist/**", "**/.terraform/**",
    "**/.angular/**", "**/coverage/**", "**/.coverage*",
    "**/coverage.xml", "**/.scannerwork/**", "analysis-reports/**",
]
TESTS = [
    "**/tests/**", "**/test/**", "**/*.test.js", "**/*.test.cjs",
    "**/*.spec.ts", "**/test_*.py", "**/test-*.py", "**/test-*.sh",
]
MODULES = [directory + "/**" for directory, _ in JAVA.values()]
MAVEN = ["mvn", "--batch-mode", "--no-transfer-progress", "--strict-checksums"]


def run(command, cwd=ROOT, env=None):
    subprocess.run(command, cwd=cwd, env=env, check=True)


def output(name, value):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write(f"{name}={value}\n")


def resolve_source(name, unit, bases=()):
    if name.startswith("file:"):
        parsed = urlparse(name)
        if parsed.netloc not in ("", "localhost"):
            raise ValueError("Non-local coverage source URI")
        name = unquote(parsed.path)
    path = Path(name)
    candidates = [path] if path.is_absolute() else [
        base / path for base in (ROOT, unit, *bases)
    ]
    matches = {
        candidate.resolve()
        for candidate in candidates
        if candidate.is_file() and candidate.resolve().is_relative_to(ROOT)
    }
    if len(matches) != 1:
        raise ValueError(f"Missing or ambiguous coverage source: {name}")
    return next(iter(matches)).relative_to(ROOT).as_posix()


def normalize_lcov(source, destination, unit):
    lines = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.startswith("SF:"):
            line = "SF:" + resolve_source(line[3:], unit)
        lines.append(line)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def normalize_python(source, destination, unit):
    tree = ET.parse(source)
    bases = []
    for element in tree.findall("./sources/source"):
        if element.text:
            path = Path(element.text)
            bases.append(path if path.is_absolute() else unit / path)
    for element in tree.findall(".//class"):
        element.set(
            "filename",
            resolve_source(element.attrib["filename"], unit, bases),
        )
    sources = tree.getroot().find("sources")
    if sources is None:
        sources = ET.SubElement(tree.getroot(), "sources")
    sources.clear()
    ET.SubElement(sources, "source").text = "."
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_unit(project_id, index, specification, destination):
    kind, relative, detail = specification
    unit = (ROOT / ROOTS[project_id] / relative).resolve()
    report_dir = destination / str(index)
    report_dir.mkdir(parents=True)
    normalized = []

    if kind == "python":
        environment = (
            Path(os.environ["RUNNER_TEMP"])
            / "portfolio-coverage" / f"{project_id}-{index}"
        )
        run([sys.executable, "-m", "venv", str(environment)])
        python = str(environment / "bin/python")
        install = [
            python, "-m", "pip", "install",
            "--disable-pip-version-check", "coverage==7.16.2",
        ]
        for name in ("requirements.txt", "requirements-dev.txt"):
            if (unit / name).is_file():
                install.extend(["-r", name])
        run(install, unit)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join([str(unit / "src"), str(unit)])
        run([
            python, "-m", "coverage", "run", "--branch",
            "--source=" + detail, "-m", "pytest", "-q",
        ], unit, env)
        run([
            python, "-m", "coverage", "xml", "-o", "coverage.xml"
        ], unit, env)
        source = unit / "coverage.xml"
        shutil.copyfile(source, report_dir / "raw-coverage.xml")
        target = report_dir / "coverage.xml"
        normalize_python(source, target, unit)
        normalized.append(("pythonxml", target))
    else:
        tracked = [unit / "package.json", unit / "package-lock.json"]
        before = {str(path): digest(path) for path in tracked}
        run(["npm", "ci"], unit)
        if kind == "angular":
            run([
                "npm", "install", "--no-save", "--package-lock=false",
                "--ignore-scripts", "@vitest/coverage-v8@5.0.5",
            ], unit)
            run(["npm", "ls", "vitest", "@vitest/coverage-v8", "--depth=0"], unit)
            run([
                "npm", "test", "--", "--watch=false", "--coverage",
                "--coverage-reporters=lcov",
                "--coverage-reporters=text-summary",
                "--coverage-include=src/**/*.ts",
                "--coverage-exclude=src/**/*.spec.ts",
                "--coverage-exclude=src/**/*.d.ts",
            ], unit)
        else:
            (unit / "coverage").mkdir(exist_ok=True)
            run(["npm", "run", "pretest", "--if-present"], unit)
            command = [
                "node", "--test", "--experimental-test-coverage",
                "--test-reporter=spec",
                "--test-reporter-destination=stdout",
                "--test-reporter=lcov",
                "--test-reporter-destination=coverage/lcov.info",
            ]
            if detail:
                command.append(detail)
            run(command, unit)
            run(["npm", "run", "posttest", "--if-present"], unit)
        if before != {str(path): digest(path) for path in tracked}:
            raise RuntimeError("Package manifest or lockfile changed")
        reports = sorted((unit / "coverage").rglob("lcov.info"))
        if not reports:
            raise RuntimeError(f"No LCOV report generated for {unit.name}")
        for number, source in enumerate(reports):
            shutil.copyfile(source, report_dir / f"raw-{number}.lcov")
            target = report_dir / f"{number}.lcov"
            normalize_lcov(source, target, unit)
            normalized.append(("lcov", target))

    return normalized


def properties(project_id, reports):
    values = {
        "sonar.organization": ORG,
        "sonar.projectKey": PREFIX + project_id,
        "sonar.projectVersion": "baseline-1",
        "sonar.projectBaseDir": str(ROOT),
        "sonar.sourceEncoding": "UTF-8",
        "sonar.scm.revision": os.environ["GITHUB_SHA"],
        "sonar.sources": ROOTS[project_id],
        "sonar.tests": ROOTS[project_id],
        "sonar.test.inclusions": ",".join(TESTS),
        "sonar.exclusions": ",".join(GENERATED + TESTS + MODULES),
        "sonar.test.exclusions": ",".join(GENERATED + MODULES),
        "sonar.python.version": "3.15",
        "sonar.qualitygate.wait": "true",
        "sonar.qualitygate.timeout": "300",
    }
    for kind, setting in (
        ("lcov", "sonar.javascript.lcov.reportPaths"),
        ("pythonxml", "sonar.python.coverage.reportPaths"),
    ):
        paths = [
            path.relative_to(ROOT).as_posix()
            for report_kind, path in reports if report_kind == kind
        ]
        if paths:
            values[setting] = ",".join(paths)
    path = Path(os.environ["RUNNER_TEMP"]) / f"sonar-{project_id}.properties"
    path.write_text(
        "".join(f"{key}={value}\n" for key, value in values.items()),
        encoding="utf-8",
    )
    output("properties", str(path))


def generate_reports(project_id):
    destination = ROOT / "analysis-reports" / project_id
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {
        "project_key": PREFIX + project_id,
        "sha": os.environ["GITHUB_SHA"],
        "observed_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "scope": JAVA[project_id][0] if project_id in JAVA else ROOTS[project_id],
        "state": "started",
        "coverage_reports": [],
        "sonar_result": "not_recorded_here",
    }
    manifest_path = destination / "scope.json"

    def save():
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    save()
    reports = []
    if project_id in JAVA:
        directory, jdk = JAVA[project_id]
        unit = ROOT / directory
        run(MAVEN + [
            "org.jacoco:jacoco-maven-plugin:0.8.15:prepare-agent",
            "verify",
            "org.jacoco:jacoco-maven-plugin:0.8.15:report",
        ], unit)
        target = destination / "jacoco.xml"
        shutil.copyfile(unit / "target/site/jacoco/jacoco.xml", target)
        reports.append(("jacoco", target))
        manifest["jdk"] = jdk
    else:
        for index, specification in enumerate(UNITS.get(project_id, [])):
            reports.extend(
                generate_unit(project_id, index, specification, destination)
            )
        properties(project_id, reports)
    manifest["state"] = "reports_generated" if reports else "static_scope_only"
    manifest["coverage_reports"] = [
        {
            "kind": kind,
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": digest(path),
        }
        for kind, path in reports
    ]
    save()


def sonar_java(project_id):
    if not os.environ.get("SONAR_TOKEN"):
        raise RuntimeError("SONAR_TOKEN is not configured")
    directory, _ = JAVA[project_id]
    run(MAVEN + [
        "org.sonarsource.scanner.maven:sonar-maven-plugin:5.8.0.7211:sonar",
        "-Dsonar.organization=" + ORG,
        "-Dsonar.projectKey=" + PREFIX + project_id,
        "-Dsonar.projectVersion=baseline-1",
        "-Dsonar.sourceEncoding=UTF-8",
        "-Dsonar.sources=.",
        "-Dsonar.tests=src/test",
        "-Dsonar.exclusions=" + ",".join(["src/test/**"] + GENERATED),
        "-Dsonar.test.exclusions=" + ",".join(GENERATED),
        "-Dsonar.coverage.jacoco.xmlReportPaths=target/site/jacoco/jacoco.xml",
        "-Dsonar.java.jdkHome=" + os.environ["JAVA_HOME"],
        "-Dsonar.scm.revision=" + os.environ["GITHUB_SHA"],
        "-Dsonar.qualitygate.wait=true",
        "-Dsonar.qualitygate.timeout=300",
    ], ROOT / directory)


def main():
    mode = sys.argv[1]
    if mode == "plan":
        entries = [
            {
                "id": project_id,
                "jdk": "",
                "node": any(
                    unit[0] in ("node", "angular")
                    for unit in UNITS.get(project_id, [])
                ),
            }
            for project_id in ROOTS
        ]
        entries.extend(
            {"id": project_id, "jdk": jdk, "node": False}
            for project_id, (_, jdk) in JAVA.items()
        )
        print(json.dumps({"include": entries}, separators=(",", ":")))
        return

    project_id = sys.argv[2]
    if project_id not in ROOTS and project_id not in JAVA:
        raise ValueError("Unknown analysis scope")
    if mode == "reports":
        generate_reports(project_id)
    elif mode == "sonar-java" and project_id in JAVA:
        sonar_java(project_id)
    else:
        raise ValueError("Unsupported operation")


if __name__ == "__main__":
    main()
