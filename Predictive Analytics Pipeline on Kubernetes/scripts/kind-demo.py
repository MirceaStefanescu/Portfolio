#!/usr/bin/env python3
"""Run the complete pipeline and reactive Kafka scaling in a new Kind namespace.

Requires Docker, kubectl, kind, Python 3.11+, and KEDA in an existing disposable
Kind cluster. Only the newly created namespace is removed unless --keep is set.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def run(command, data=None, timeout=300):
    result = subprocess.run(command, input=data, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(" ".join(command[:6]) + ": " + result.stderr[-2000:])
    return result.stdout


def wait(check, description, timeout=180):
    end = time.monotonic() + timeout
    error = None
    while time.monotonic() < end:
        try:
            result = check()
            if result:
                return result
        except (OSError, ValueError, RuntimeError) as ex:
            error = ex
        time.sleep(2)
    raise RuntimeError(description + ": " + str(error))


def http(port, path, body=None):
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        data = response.read()
        return json.loads(data) if data else None


def resource_list(stream):
    """kubectl emits adjacent JSON objects for multi-document YAML."""
    decoder = json.JSONDecoder()
    resources = []
    while stream.strip():
        document, end = decoder.raw_decode(stream.lstrip())
        stream = stream.lstrip()[end:]
        resources.extend(document["items"] if document.get("kind") == "List" else [document])
    return {"apiVersion": "v1", "kind": "List", "items": resources}


def cached_on_nodes(docker, image, platform, nodes):
    """Compare actual runtime configuration and every uncompressed layer digest.

    Docker index IDs and CRI manifest IDs differ after platform-only imports.
    Layer/config identity, rather than a tag or either unrelated ID, is required.
    """
    local = json.loads(run([docker, "image", "inspect", "--platform", platform, image]))[0]
    for node in nodes:
        try:
            cached = json.loads(run([docker, "exec", node["metadata"]["name"], "crictl", "inspecti", image]))["info"]["imageSpec"]
        except (RuntimeError, KeyError):
            return False
        if local["RootFS"]["Layers"] != cached["rootfs"]["diff_ids"] or local["Config"] != cached["config"]:
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--namespace", default="predictive-demo-" + uuid.uuid4().hex[:8])
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,45}", args.cluster) or not re.fullmatch(r"predictive-demo-[a-z0-9-]{1,35}", args.namespace):
        parser.error("Use a named Kind cluster and a predictive-demo- namespace")
    executables = {name: shutil.which(name) for name in ("docker", "kubectl", "kind")}
    if not all(executables.values()):
        parser.error("Docker, kubectl and kind must be on PATH")
    if args.cluster not in run([executables["kind"], "get", "clusters"]).splitlines():
        parser.error("The selected Kind cluster does not exist")
    kube = [executables["kubectl"], "--context", "kind-" + args.cluster]
    scoped = kube + ["-n", args.namespace]
    run(kube + ["get", "crd", "scaledobjects.keda.sh"])
    if run(kube + ["get", "namespace", args.namespace, "--ignore-not-found", "-o", "name"]).strip():
        parser.error("Namespace already exists; choose a new name")
    for component, image in (("api", "predictive-analytics-api:latest"), ("flink", "predictive-analytics-flink-job:latest")):
        print("Building " + image, flush=True)
        run([executables["docker"], "build", "-t", image, str(ROOT / component)], timeout=600)
    images = ["predictive-analytics-api:latest", "predictive-analytics-flink-job:latest",
              "confluentinc/cp-kafka:7.9.10", "confluentinc/cp-zookeeper:7.9.10",
              "confluentinc/cp-schema-registry:7.9.10", "postgres:15",
              "docker.elastic.co/elasticsearch/elasticsearch:7.17.9", "otel/opentelemetry-collector-contrib:0.162.0"]
    print("Loading verified local build images into " + args.cluster, flush=True)
    nodes = json.loads(run(kube + ["get", "nodes", "-o", "json"]))["items"]
    platforms = {node["status"]["nodeInfo"]["operatingSystem"] + "/" + node["status"]["nodeInfo"]["architecture"] for node in nodes}
    if len(platforms) != 1:
        raise RuntimeError("This local demo requires one node platform")
    platform = next(iter(platforms))
    missing = [image for image in images if not cached_on_nodes(executables["docker"], image, platform, nodes)]
    # Docker's containerd image store can retain multi-platform descriptors without
    # the other platforms' blobs. Export exactly the cluster platform for Kind.
    if missing:
        with tempfile.TemporaryDirectory(prefix="predictive-kind-images-") as directory:
            archive = str(Path(directory) / "images.tar")
            run([executables["docker"], "image", "save", "--platform", platform, "-o", archive, *missing], timeout=600)
            run([executables["kind"], "load", "image-archive", "--name", args.cluster, archive], timeout=600)
    print(f"Reused {len(images) - len(missing)} images with verified layers and runtime configuration", flush=True)
    marker = uuid.uuid4().hex
    run(kube + ["create", "-f", "-"], json.dumps({"apiVersion": "v1", "kind": "Namespace",
        "metadata": {"name": args.namespace, "labels": {"portfolio-demo-owner": marker}}}))
    identity = json.loads(run(kube + ["get", "namespace", args.namespace, "-o", "json"]))["metadata"]["uid"]
    forwards = []
    passed = False
    def apply(name):
        document = resource_list(run(kube + ["create", "--dry-run=client", "-f", str(ROOT / "k8s" / name), "-o", "json"]))
        for resource in document["items"]:
            resource["metadata"]["namespace"] = args.namespace
            if resource["kind"] == "ScaledObject":
                for trigger in resource["spec"]["triggers"]:
                    if trigger["type"] == "kafka":
                        trigger["metadata"]["bootstrapServers"] = f"kafka.{args.namespace}.svc.cluster.local:9092"
        run(kube + ["apply", "-f", "-"], json.dumps(document))
    def forward(service, target):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen(scoped + ["port-forward", "--address", "127.0.0.1", "svc/" + service, f"{port}:{target}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        forwards.append(process)
        return port
    try:
        for name in ("configmap.yaml", "secret.yaml", "postgres-init-configmap.yaml", "flink-checkpoints.yaml",
                     "zookeeper.yaml", "kafka.yaml", "postgres.yaml", "elasticsearch.yaml", "schema-registry.yaml",
                     "otel-collector.yaml", "api-service.yaml", "api-deployment.yaml"):
            apply(name)
        run(scoped + ["rollout", "status", "deployment/predictive-analytics-api", "--timeout=180s"], timeout=190)
        apply("kafka-init-job.yaml")
        run(scoped + ["wait", "--for=condition=complete", "job/kafka-init", "--timeout=90s"], timeout=100)
        api = forward("predictive-analytics-api", 8080)
        wait(lambda: http(api, "/api/health")["status"] == "ok", "API")
        # Build a finite known backlog before starting consumers. KEDA must act on real lag.
        base = int(time.time() // 30 * 30000)
        records = "\n".join(json.dumps({"eventType": "sensor.kubernetes", "value": 35.0,
                            "timestamp": base + n * 100}) for n in range(1000)) + "\n"
        run(scoped + ["exec", "-i", "deployment/kafka", "--", "kafka-console-producer", "--bootstrap-server",
                      "kafka:9092", "--topic", "events"], records)
        apply("flink-taskmanager.yaml")
        apply("keda-scaledobject.yaml")
        wait(lambda: json.loads(run(scoped + ["get", "deployment", "flink-taskmanager", "-o", "json"]))["spec"]["replicas"] >= 2,
             "KEDA scales TaskManagers for Kafka backlog")
        scaled = json.loads(run(scoped + ["get", "deployment", "flink-taskmanager", "-o", "json"]))["spec"]["replicas"]
        print("Kafka lag scaled TaskManagers to " + str(scaled), flush=True)
        apply("flink-jobmanager.yaml")
        run(scoped + ["rollout", "status", "deployment/flink-jobmanager", "--timeout=180s"], timeout=190)
        flink = forward("flink-jobmanager", 8081)
        job = wait(lambda: next((job for job in http(flink, "/jobs/overview")["jobs"] if job["state"] == "RUNNING"), None), "Running reactive Flink job")
        details = http(flink, "/jobs/" + job["jid"])
        parallelism = max(vertex["parallelism"] for vertex in details["vertices"])
        assert parallelism >= 2, details
        restored_before = http(flink, "/jobs/" + job["jid"] + "/checkpoints")["counts"]["restored"]
        wait(lambda: http(flink, "/jobs/" + job["jid"] + "/checkpoints")["counts"]["completed"] > 0, "Completed checkpoint")
        wait(lambda: json.loads(run(scoped + ["get", "deployment", "flink-taskmanager", "-o", "json"]))["spec"]["replicas"] == 1,
             "KEDA scales down after committed offsets", 180)
        def rescaled():
            details = http(flink, "/jobs/" + job["jid"])
            return details["state"] == "RUNNING" and all(vertex["parallelism"] == 1 and vertex["status"] == "RUNNING" for vertex in details["vertices"])
        wait(rescaled, "Reactive Flink resumes at parallelism one", 120)
        assert http(flink, "/jobs/" + job["jid"] + "/checkpoints")["counts"]["restored"] > restored_before
        # Event-time watermarks are rebuilt from new events after recovery. Close
        # every backlog window with a fresh event, then verify all 1,000 records
        # exactly once. An intermediate partial SQL batch is not a stable baseline.
        http(api, "/api/events", {"eventType": "sensor.kubernetes", "value": 35,
                                   "timestamp": dt.datetime.fromtimestamp((base + 180000) / 1000, dt.timezone.utc).isoformat()})
        rows = wait(lambda: (values if len(values := http(api, "/api/predictions?eventType=sensor.kubernetes&limit=20")) == 4 else None), "Four complete post-rescale windows")
        assert sorted(row["eventCount"] for row in rows) == [100, 300, 300, 300], rows
        assert len({(row["windowStart"], row["windowEnd"]) for row in rows}) == 4, rows
        assert all(row["predictionScore"] >= 3 and row["avgValue"] == 35 for row in rows), rows
        wait(lambda: "events.publish" in run(scoped + ["logs", "deployment/otel-collector"]), "OTLP after rescale")
        print(json.dumps({"status": "PASS", "namespace": args.namespace, "namespace_uid": identity,
            "keda_replicas": [1, scaled, 1], "flink_parallelism": [parallelism, 1],
            "checkpoint_restore": "PASS", "continued_predictions": "PASS", "traces": "PASS",
            "backlog_records_accounted_for": sum(row["eventCount"] for row in rows), "unique_windows": len(rows),
            "scope": "Single-node Kind; Kafka and ZooKeeper are ephemeral demo stores"}, indent=2), flush=True)
        passed = True
    finally:
        for process in forwards:
            process.terminate()
            process.wait(timeout=10)
        if not passed:
            print(run(scoped + ["get", "pods", "-o", "wide"]), flush=True)
            for deployment in ("flink-jobmanager", "flink-taskmanager", "predictive-analytics-api"):
                try: print(run(scoped + ["logs", "deployment/" + deployment, "--tail=35"]), flush=True)
                except RuntimeError: pass
        if not args.keep:
            current = json.loads(run(kube + ["get", "namespace", args.namespace, "-o", "json"]))
            if current["metadata"]["uid"] != identity or current["metadata"]["labels"].get("portfolio-demo-owner") != marker:
                raise RuntimeError("Namespace ownership changed; cleanup stopped")
            run(kube + ["delete", "namespace", args.namespace, "--wait=true", "--timeout=120s"], timeout=130)
        else:
            print("Retained namespace: " + args.namespace + "; use kubectl --context kind-" + args.cluster + " -n " + args.namespace + " port-forward svc/predictive-analytics-api 8082:8080")


if __name__ == "__main__":
    main()
