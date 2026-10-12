"""Capture actual native runtime versions and verified distribution identity before an authorized run."""

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def verify_checksum(archive, checksum):
    matches = re.findall(r"\b[0-9a-fA-F]{128}\b", checksum.read_text())
    if len(matches) != 1:
        raise ValueError("Expected exactly one SHA512 in Apache checksum file")
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha512").hexdigest()
    if actual != matches[0].lower():
        raise ValueError("Distribution SHA512 mismatch")
    return actual


def capture(directory, name, argv):
    result = subprocess.run(argv, text=True, capture_output=True, timeout=60)
    (directory / (name + ".stdout.log")).write_text(result.stdout)
    (directory / (name + ".stderr.log")).write_text(result.stderr)
    if result.returncode != 0:
        raise RuntimeError(name + " exited " + str(result.returncode))
    return {"argv": argv, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def configured_data(cluster):
    text = (cluster / "conf" / "server.yaml").read_text()
    matches = re.findall(r"(?m)^data\.dir:\s*([^\n]+)$", text)
    if len(matches) != 1:
        raise ValueError("Set one explicit lab-owned data.dir in conf/server.yaml")
    data = Path(matches[0].strip().strip("'\""))
    if not data.is_absolute():
        raise ValueError("Use an absolute lab-owned data.dir")
    return str(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--checksum", type=Path, required=True)
    parser.add_argument("--cluster", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=False)
    checksum = verify_checksum(args.archive, args.checksum)
    java = capture(args.evidence, "java-version", ["java", "-version"])
    maven = capture(args.evidence, "maven-version", ["mvn", "--version"])
    if 'version "17.' not in java["stderr"]:
        raise ValueError("This lab targets an actual Java 17 runtime")
    value = {"captured_gst": datetime.now(timezone(timedelta(hours=4))).isoformat(),
             "distribution": "Apache Fluss 1.0.0", "archive": str(args.archive.resolve()),
             "archive_bytes": args.archive.stat().st_size, "archive_sha512": checksum,
             "checksum_file": str(args.checksum.resolve()), "java": java, "maven": maven,
             "python": sys.version, "cluster_path": str(args.cluster.resolve()),
             "data_dir": configured_data(args.cluster), "table_log_ttl": "0ms",
             "startup_command": "./bin/local-cluster.sh start",
             "startup_executed_by_this_capture": False}
    (args.evidence / "cluster-runtime.json").write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
