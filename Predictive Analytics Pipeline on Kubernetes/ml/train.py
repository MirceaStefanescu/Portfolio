#!/usr/bin/env python3
"""Fit a univariate Gaussian baseline to synthetic 30-second window averages."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent
MODEL = ROOT.parent / "flink/src/main/resources/anomaly-model.json"


def train():
    raw = (ROOT / "training.csv").read_bytes()
    values = [float(row["window_average"]) for row in csv.DictReader(raw.decode().splitlines())]
    if len(values) < 2 or not all(math.isfinite(x) for x in values):
        raise ValueError("Training requires at least two finite window averages")
    stddev = statistics.pstdev(values)
    if stddev <= 0:
        raise ValueError("Training variance must be positive")
    model = {"version": "synthetic-window-gaussian-v1", "mean": statistics.fmean(values),
             "stddev": stddev, "threshold": 3.0, "training_count": len(values),
             "training_sha256": hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()}
    validation = list(csv.DictReader((ROOT / "validation.csv").read_text().splitlines()))
    confusion = {"true_positive": 0, "true_negative": 0, "false_positive": 0, "false_negative": 0}
    for row in validation:
        predicted = abs(float(row["window_average"]) - model["mean"]) / stddev >= model["threshold"]
        actual = bool(int(row["anomaly"]))
        confusion[("true_" if predicted == actual else "false_") + ("positive" if predicted else "negative")] += 1
    return model, {"samples": len(validation), **confusion, "scope": "Synthetic held-out windows only"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    model, report = train()
    if args.check:
        assert json.loads(MODEL.read_text()) == model, "Model differs from reproducible training"
        assert not report["false_positive"] and not report["false_negative"], report
    else:
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        MODEL.write_text(json.dumps(model, indent=2) + "\n")
    print(json.dumps({"model": model, "validation": report}, indent=2))
