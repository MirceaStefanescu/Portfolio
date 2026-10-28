#!/usr/bin/env python3
"""Three local Qdrant peers: replication, node outage, recovery and snapshot restore."""
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])
    return result.stdout.strip()


def request(base, path, data=None, method=None):
    req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)["result"]


def wait(check, description):
    end = time.monotonic() + 90
    while time.monotonic() < end:
        try:
            if check():
                return
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(1)
    raise RuntimeError("Timed out: " + description)


def main():
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker Compose v2 is required")
    directory = pathlib.Path(tempfile.mkdtemp(prefix="portfolio-qdrant-"))
    project = "portfolio-qdrant-" + uuid.uuid4().hex[:8]
    services = {}
    for number in range(1, 4):
        name = "peer" + str(number)
        services[name] = {"image": "qdrant/qdrant:v1.19.2", "ports": ["127.0.0.1::6333"],
                          "environment": {"QDRANT__CLUSTER__ENABLED": "true", "QDRANT__TELEMETRY_DISABLED": "true"},
                          "command": ["./qdrant", "--uri", f"http://{name}:6335"] +
                                     (["--bootstrap", "http://peer1:6335"] if number > 1 else []),
                          "volumes": [name + ":/qdrant/storage"]}
    services["restored"] = {"image": "qdrant/qdrant:v1.19.2", "ports": ["127.0.0.1::6333"],
                            "environment": {"QDRANT__TELEMETRY_DISABLED": "true"},
                            "volumes": ["restored:/qdrant/storage"]}
    compose = directory / "compose.json"
    compose.write_text(json.dumps({"services": services, "volumes": {name: {} for name in services}}))
    command = [docker, "compose", "-p", project, "-f", str(compose)]
    def url(name):
        return "http://127.0.0.1:" + run(command + ["port", name, "6333"]).rsplit(":", 1)[1]
    try:
        run(command + ["up", "-d", "peer1"])
        one = url("peer1")
        wait(lambda: request(one, "/cluster")["status"] == "enabled", "first peer")
        run(command + ["up", "-d", "peer2", "peer3", "restored"])
        two, three, restored = url("peer2"), url("peer3"), url("restored")
        wait(lambda: len(request(one, "/cluster")["peers"]) == 3, "three-peer consensus")
        request(one, "/collections/demo", {"vectors": {"size": 4, "distance": "Dot"},
                "shard_number": 1, "replication_factor": 3, "write_consistency_factor": 2}, "PUT")
        for address in [one, two, three]:
            wait(lambda: request(address, "/collections/demo")["status"] == "green", "replicated collection")
            shards = request(address, "/collections/demo/cluster")["local_shards"]
            if len(shards) != 1 or shards[0]["state"] != "Active":
                raise RuntimeError("Expected one active local shard: " + repr(shards))
        points = [{"id": i, "vector": [float(i), 1.0, 0.0, 0.0],
                   "payload": {"text": "Synthetic knowledge " + str(i)}} for i in range(1, 21)]
        request(one, "/collections/demo/points?wait=true", {"points": points}, "PUT")
        def records(address):
            return request(address, "/collections/demo/points/scroll", {"limit": 100, "with_vector": True})["points"]
        expected = points
        for address in [one, two, three]:
            wait(lambda: records(address) == expected, "replicated points and vectors")
        run(command + ["stop", "peer1"])
        if records(two) != expected or records(three) != expected:
            raise RuntimeError("Surviving peers did not retain the expected points and vectors")
        extra = {"id": 21, "vector": [21.0, 1.0, 0.0, 0.0], "payload": {"text": "Written during outage"}}
        request(two, "/collections/demo/points?wait=true", {"points": [extra]}, "PUT")
        expected = points + [extra]
        for address in [two, three]:
            wait(lambda: records(address) == expected, "outage write replicated to surviving peers")
        run(command + ["start", "peer1"])
        one = url("peer1")
        wait(lambda: records(one) == expected, "restarted peer catches up")
        snapshot = request(two, "/collections/demo/snapshots", {}, "POST")
        with urllib.request.urlopen(two + "/collections/demo/snapshots/" + snapshot["name"], timeout=30) as response:
            blob = response.read()
        snapshot_hash = hashlib.sha256(blob).hexdigest()
        (directory / "demo.snapshot").write_bytes(blob)
        boundary = "portfolio" + uuid.uuid4().hex
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="snapshot"; filename="demo.snapshot"\r\n'
                'Content-Type: application/octet-stream\r\n\r\n').encode() + blob + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(restored + "/collections/demo/snapshots/upload?priority=snapshot", data=body,
                                     headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError("Snapshot upload did not complete: " + str(response.status))
        if records(restored) != expected:
            raise RuntimeError("Restored points and vectors differ from the expected data")
        result = {"status": "PASS", "peers": 3, "replicationFactor": 3, "nodeOutageReadWrite": True,
                  "restartedPeerCatchup": True, "restoredPointsAndVectors": len(expected), "snapshotSha256": snapshot_hash,
                  "scope": "Synthetic local failure domains and isolated snapshot restore; no cloud availability claim"}
    finally:
        run(command + ["down", "--volumes", "--remove-orphans"])
    (directory / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
