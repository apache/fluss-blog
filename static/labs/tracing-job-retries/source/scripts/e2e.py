"""Real-process E2E supervisor; assertions exist before worker implementation."""

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import queue
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
GST = timezone(timedelta(hours=4))
BASELINE_TYPES = ["STARTED", "COMPUTE_STARTED", "COMPUTE_FINISHED",
                  "ACTION_REQUESTED", "ACTION_CONFIRMED", "COMPLETED"]


def timestamp():
    return datetime.now(GST).isoformat()


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def http_call(base, method, path, body=None):
    data = None if body is None else json.dumps(body, sort_keys=True).encode()
    request = urllib.request.Request(base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def collect_lines(stream, path, messages):
    with path.open("w") as output:
        for line in iter(stream.readline, ""):
            output.write(timestamp() + " " + line)
            output.flush()
            if line.startswith("{"):
                messages.put(json.loads(line))
    messages.put({"kind": "STREAM_CLOSED"})


class Run:
    def __init__(self, args):
        self.args = args
        self.directory = args.evidence.resolve()
        self.directory.mkdir(parents=True, exist_ok=False)
        self.assertions = []
        self.commands = []
        self.serial = 0
        self.base = "http://127.0.0.1:" + str(args.service_port)
        self.ledger = self.directory / "ledger.sqlite"
        self.service = None
        self.active = []
        self.case_status = {}

    def check(self, name, expected, observed):
        item = {"name": name, "expected": expected, "observed": observed,
                "passed": expected == observed, "at_gst": timestamp()}
        self.assertions.append(item)
        save_json(self.directory / "assertions.json", self.assertions)
        if not item["passed"]:
            raise AssertionError(name + ": " + repr(item))

    def spawn(self, name, argv):
        self.serial += 1
        prefix = self.directory / (str(self.serial).zfill(3) + "-" + name)
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, bufsize=1, stdin=subprocess.DEVNULL)
        messages = queue.Queue()
        threads = [threading.Thread(target=collect_lines,
                   args=(proc.stdout, prefix.with_suffix(".stdout.log"), messages)),
                   threading.Thread(target=collect_lines,
                   args=(proc.stderr, prefix.with_suffix(".stderr.log"), queue.Queue()))]
        for thread in threads:
            thread.start()
        record = {"name": name, "argv": argv, "pid": proc.pid,
                  "started_gst": timestamp(), "prefix": str(prefix)}
        handle = (proc, messages, threads, record)
        self.active.append(handle)
        return handle

    def finish(self, handle):
        proc, messages, threads, record = handle
        timed_out = False
        try:
            code = proc.wait(timeout=self.args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            code = proc.wait(timeout=10)
        collector_alive = []
        for thread in threads:
            thread.join(timeout=10)
            collector_alive.append(thread.is_alive())
        record.update(exit_code=code, ended_gst=timestamp(), timed_out=timed_out,
                      collectors_finished=not any(collector_alive))
        self.commands.append(record)
        save_json(self.directory / "commands.json", self.commands)
        self.active.remove(handle)
        if timed_out:
            raise TimeoutError("Process timed out: " + record["name"])
        if any(collector_alive):
            raise TimeoutError("Output collector did not finish: " + record["name"])
        return code

    def java_argv(self, command, job=None, attempt=None, barrier="NONE"):
        argv = [self.args.java, "--add-opens=java.base/java.nio=ALL-UNNAMED", "-jar",
                str(self.args.jar.resolve()), command,
                "--bootstrap", self.args.bootstrap, "--service", self.base,
                "--timeout-seconds", str(self.args.timeout)]
        if job is not None:
            argv.extend(["--job", job])
        if attempt is not None:
            argv.extend(["--attempt", str(attempt), "--barrier", barrier])
        return argv

    def command(self, name, argv, expected=0):
        handle = self.spawn(name, argv)
        code = self.finish(handle)
        self.check(name + " exit", expected, code)
        return drain(handle[1])

    def java(self, command, job=None, attempt=None, expected=0, extra=None):
        argv = self.java_argv(command, job, attempt)
        if extra is not None:
            argv.extend(extra)
        messages = self.command(command + "-" + str(self.serial), argv, expected)
        if expected != 0:
            return messages
        results = [m for m in messages if m.get("kind") == "RESULT"]
        self.check(command + " single result", 1, len(results))
        return results[0]

    def inspect(self, job, suffix):
        result = self.java("inspect", job)
        save_json(self.directory / (suffix + "-fluss.json"), result)
        return result

    def ledger_snapshot(self, job, suffix):
        with closing(sqlite3.connect("file:" + str(self.ledger) + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            computations = rows(db, "SELECT * FROM computations WHERE job_id=? ORDER BY id", job)
            effects = rows(db, "SELECT * FROM effects WHERE action_id=? ORDER BY action_id", action(job))
            audit = rows(db, "SELECT * FROM http_audit WHERE job_id=? ORDER BY id", job)
        result = {"computations": computations, "effects": effects, "audit": audit}
        save_json(self.directory / (suffix + "-ledger.json"), result)
        return result

    def start_service(self):
        self.service = self.spawn("service", [sys.executable, str(ROOT / "scripts" / "service.py"),
                                  "--ledger", str(self.ledger), "--port", str(self.args.service_port)])
        message = wait_kind(self.service, "SERVICE_READY", self.args.timeout)
        self.check("service localhost", "127.0.0.1", message["host"])
        status, body = http_call(self.base, "GET", "/health")
        self.check("service health", (200, "fixture-atomic-action-id-payload-v1"),
                   (status, body["contract"]))

    def kill_at(self, job, barrier):
        handle = self.spawn("worker-" + barrier, self.java_argv("worker", job, 1, barrier))
        message = wait_kind(handle, "BARRIER", self.args.timeout)
        self.check(barrier + " barrier", barrier, message["barrier"])
        self.check(barrier + " worker pid", handle[0].pid, message["pid"])
        self.check(barrier + " alive before kill", None, handle[0].poll())
        os.kill(handle[0].pid, signal.SIGKILL)
        code = self.finish(handle)
        self.check(barrier + " SIGKILL exit", -signal.SIGKILL, code)
        save_json(self.directory / (barrier + "-" + job.split("/")[-2] + "-barrier.json"), message)
        return handle[0].pid

    def completed(self, job, name, compute_count):
        log = self.inspect(job, name)
        ledger = self.ledger_snapshot(job, name)
        self.check(name + " reduced state", "COMPLETED", log["state"])
        self.check(name + " effect count", 1, len(ledger["effects"]))
        self.check(name + " compute count", compute_count, len(ledger["computations"]))
        return log, ledger

    def baseline(self):
        job = self.job("baseline")
        self.java("worker", job, 1)
        log, ledger = self.completed(job, "baseline", 1)
        self.check("baseline ordered types", BASELINE_TYPES, types(log))
        self.check("baseline HTTP POST count", 1, posts(ledger))
        return job, ledger["effects"][0]

    def repeat_compute(self):
        job = self.job("repeat-compute")
        killed_pid = self.kill_at(job, "A")
        before = self.inspect(job, "repeat-compute-before")
        ledger = self.ledger_snapshot(job, "repeat-compute-before")
        self.check("A no completion append", ["STARTED", "COMPUTE_STARTED"], types(before))
        self.check("A independent computed once", 1, len(ledger["computations"]))
        recovered = self.java("recover", job, 2)
        self.check("A fresh PID", True, recovered["pid"] != killed_pid)
        log, ledger = self.completed(job, "repeat-compute-after", 2)
        self.check("A both attempts", [1, 2], sorted({r["attempt"] for r in log["logical"]}))
        self.check("A one action POST", 1, posts(ledger))

    def action_window(self, name, barrier, before_effects):
        job = self.job(name)
        killed_pid = self.kill_at(job, barrier)
        log = self.inspect(job, name + "-before")
        ledger = self.ledger_snapshot(job, name + "-before")
        self.check(name + " unresolved log", "ACTION_REQUESTED", log["state"])
        self.check(name + " before effects", before_effects, len(ledger["effects"]))
        self.check(name + " before POSTs", before_effects, posts(ledger))
        recovered = self.java("recover", job, 2)
        self.check(name + " fresh PID", True, recovered["pid"] != killed_pid)
        after, ledger = self.completed(job, name + "-after", 1)
        self.check(name + " no second POST", 1, posts(ledger))
        self.check(name + " receipt lookup", True, gets(ledger) >= 1)
        lookups = [r for r in ledger["audit"] if r["method"] == "GET"]
        self.check(name + " receipt status", 404 if before_effects == 0 else 200, lookups[0]["status"])
        self.check(name + " attempts retained", [1, 2], sorted({r["attempt"] for r in after["logical"]}))
        if before_effects == 1:
            original = json.loads(self.ledger_snapshot(job, name + "-receipt-proof")["effects"][0]["receipt_json"])
            confirmed = [r["detail"] for r in after["logical"] if r["event_type"] == "ACTION_CONFIRMED"]
            self.check(name + " recorded original receipt", original, json.loads(confirmed[0]))
        self.check(name + " reconciled event", True, "RECONCILED" in types(after))
        if name == "before-http":
            self.frozen_payload()
            self.frozen_rejections()
        return self.normalized(log, name)

    def frozen_payload(self):
        job = self.job("frozen-payload")
        title = 'Frozen "priority" \\ follow-up / ticket-1042'
        seeded = self.java("frozen-intent", job, extra=["--title", title])
        before = self.inspect(job, "frozen-payload-before")
        intent = before["logical"][-1]
        persisted = intent["detail"].encode("utf-8")
        self.check("frozen positive unresolved state", "ACTION_REQUESTED", before["state"])
        self.check("frozen positive non-default title", title, json.loads(intent["detail"])["title"])
        self.check("frozen positive differs from default", True, title != immutable_payload(job)["title"])
        self.check("frozen positive exact digest", hashlib.sha256(persisted).hexdigest(), intent["payload_digest"])
        ledger = self.ledger_snapshot(job, "frozen-payload-before")
        self.check("frozen positive no prior computation", 0, len(ledger["computations"]))
        self.check("frozen positive no prior effect", 0, len(ledger["effects"]))
        recovered = self.java("recover", job, 2)
        self.check("frozen positive fresh JVM", True, recovered["pid"] != seeded["pid"])
        after, ledger = self.completed(job, "frozen-payload-after", 0)
        requests = [r for r in ledger["audit"] if r["method"] == "POST" and r["path"] == "/followups"]
        self.check("frozen positive one POST", 1, len(requests))
        raw_body = bytes.fromhex(requests[0]["request_body_hex"])
        self.check("frozen positive raw HTTP payload bytes", persisted.hex(), wire_payload(raw_body).hex())
        self.check("frozen positive independent stored bytes", persisted.hex(),
                   ledger["effects"][0]["payload_json"].encode("utf-8").hex())
        receipt = json.loads(ledger["effects"][0]["receipt_json"])
        self.check("frozen positive receipt action", intent["action_id"], receipt["action_id"])
        self.check("frozen positive receipt digest", intent["payload_digest"], receipt["payload_digest"])
        digests = {e["payload_digest"] for e in after["logical"] if e["attempt"] == 2}
        self.check("frozen positive recovered digest propagation", [intent["payload_digest"]], sorted(digests))

    def frozen_rejections(self):
        expected = {"missing": "Missing persisted canonical payload", "noncanonical": "Payload is not canonical",
                    "tampered": "Persisted payload digest mismatch", "digest": "Persisted payload digest mismatch",
                    "binding": "Persisted payload job mismatch"}
        for fault in ["missing", "noncanonical", "tampered", "digest", "binding"]:
            job = self.job("invalid-intent-" + fault)
            self.java("invalid-intent", job, extra=["--fault", fault])
            before = self.ledger_snapshot(job, "invalid-intent-" + fault + "-before")
            messages = self.java("recover", job, 2, expected=1)
            self.rejection(messages, expected[fault], fault)
            after = self.ledger_snapshot(job, "invalid-intent-" + fault + "-after")
            self.check(fault + " no inference on invalid intent", 0, len(after["computations"]))
            self.check(fault + " no action POST", 0, posts(after))
            self.check(fault + " no effect", before["effects"], after["effects"])

    def normalized(self, log, name):
        for record in log["raw"]:
            event = record["event"]
            payload = immutable_payload(event["job_id"])
            self.check(name + " actual payload digest " + event["event_id"],
                       payload_digest(payload), event["payload_digest"])
            if event["event_type"] == "ACTION_REQUESTED":
                self.check(name + " immutable intent detail", payload, json.loads(event["detail"]))
        return normalize(log)

    def unknown(self):
        job = self.job("unknown")
        self.kill_at(job, "B2")
        before = self.ledger_snapshot(job, "unknown-before")
        self.check("unknown committed first", 1, len(before["effects"]))
        self.control(job, False)
        self.java("recover", job, 2)
        held = self.inspect(job, "unknown-held")
        ledger = self.ledger_snapshot(job, "unknown-held")
        self.check("unknown HOLD state", "HOLD_UNKNOWN", held["state"])
        self.check("unknown no blind POST", 1, posts(ledger))
        self.check("unknown held effect count", 1, len(ledger["effects"]))
        self.check("unknown held compute count", 1, len(ledger["computations"]))
        self.check("unknown lookup HTTP 503", True,
                   any(r["status"] == 503 for r in ledger["audit"] if r["method"] == "GET"))
        self.control(job, True)
        self.java("recover", job, 3)
        log, ledger = self.completed(job, "unknown-after", 1)
        self.check("unknown preserved receipt", before["effects"], ledger["effects"])
        self.check("unknown still one POST", 1, posts(ledger))
        self.receipt_rejections()

    def receipt_rejections(self):
        expected = {"wrong-action": "Receipt key mismatch", "wrong-digest": "Receipt immutable digest mismatch"}
        for fault in ["wrong-action", "wrong-digest"]:
            job = self.job("invalid-receipt-" + fault)
            self.kill_at(job, "B2")
            status, body = http_call(self.base, "POST", "/control", {"action_id": action(job),
                                     "lookup_available": True, "receipt_fault": fault})
            self.check(fault + " receipt fault configured", 200, status)
            messages = self.java("recover", job, 2, expected=1)
            self.rejection(messages, expected[fault], fault)
            ledger = self.ledger_snapshot(job, fault + "-rejected")
            log = self.inspect(job, fault + "-rejected")
            self.check(fault + " effect remains one", 1, len(ledger["effects"]))
            self.check(fault + " computation remains one", 1, len(ledger["computations"]))
            self.check(fault + " no extra POST", 1, posts(ledger))
            self.check(fault + " no successful reconciliation", False, "RECONCILED" in types(log))
            self.check(fault + " no completion", False, "COMPLETED" in types(log))

    def rejection(self, messages, expected, name):
        failures = [m for m in messages if m.get("kind") == "FAILURE"]
        self.check(name + " failure reported", 1, len(failures))
        self.check(name + " rejection reason", True, expected in failures[0]["error"])

    def control(self, job, available):
        status, body = http_call(self.base, "POST", "/control",
                                 {"action_id": action(job), "lookup_available": available})
        self.check("control status", 200, status)
        self.check("control applied", available, body["lookup_available"])

    def conflicting_action(self, job, effect):
        body = {"action_id": action(job), "payload_digest": effect["payload_digest"],
                "payload": json.loads(effect["payload_json"])}
        status, receipt = http_call(self.base, "POST", "/followups", body)
        self.check("exact duplicate status", 200, status)
        self.check("exact duplicate receipt", json.loads(effect["receipt_json"]), receipt)
        messages = self.java("conflict-action", job, expected=1)
        failures = [m for m in messages if m.get("kind") == "FAILURE"]
        self.check("conflicting worker failure", 1, len(failures))
        self.check("conflicting HTTP409", True, "HTTP 409" in failures[0]["error"])
        ledger = self.ledger_snapshot(job, "conflicting-action")
        self.check("conflicting effect remains one", 1, len(ledger["effects"]))
        self.check("conflict recorded independently", 409, ledger["audit"][-1]["status"])
        self.check("conflict changed digest", True,
                   ledger["audit"][-1]["payload_digest"] != effect["payload_digest"])

    def duplicate_event(self):
        job = self.job("duplicate-event")
        self.java("duplicate-event", job)
        log = self.inspect(job, "duplicate-event")
        self.check("duplicate raw count", 2, log["raw_count"])
        self.check("duplicate logical count", 1, log["logical_count"])
        self.check("duplicate distinct offsets", 2, len({r["offset"] for r in log["raw"]}))
        self.check("duplicate identical fields", log["raw"][0]["event"], log["raw"][1]["event"])
        self.java("conflict-event", job)
        messages = self.java("inspect", job, expected=1)
        failures = [m for m in messages if m.get("kind") == "FAILURE"]
        self.check("event conflict fails", 1, len(failures))
        self.check("event identity rejection", True, "event identity conflict" in failures[0]["error"])
        raw = self.java("inspect", job, extra=["--raw-only", "true"])
        save_json(self.directory / "duplicate-conflict-raw.json", raw)
        self.check("conflict all raw retained", 3, raw["raw_count"])

    def job(self, case):
        return self.args.run_id + "/" + case + "/ticket-1042"

    def metadata(self):
        files = sorted(p for p in ROOT.rglob("*") if p.is_file() and "target" not in p.parts)
        hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        save_json(self.directory / "source-hashes.json", hashes)
        self.command("java-version", [self.args.java, "-version"])
        self.command("maven-version", [self.args.maven, "--version"])
        save_json(self.directory / "versions.json", {"fluss_client": "1.0.0", "java_target": 17,
                  "python": sys.version, "sqlite": sqlite3.sqlite_version,
                  "cluster_evidence": str(self.args.cluster_evidence.resolve())})
        (self.directory / "cluster-runtime.json").write_bytes(self.args.cluster_evidence.read_bytes())

    def execute(self):
        self.metadata()
        self.start_service()
        self.java("init")
        job, effect = self.case("baseline", self.baseline)
        self.case("repeat-compute", self.repeat_compute)
        left = self.case("before-http", lambda: self.action_window("before-http", "B1", 0))
        right = self.case("after-commit", lambda: self.action_window("after-commit", "B2", 1))
        self.check("twin action prefixes", left, right)
        save_json(self.directory / "twin-normalization.json", {"before_http": left, "after_commit": right})
        self.case("unknown", self.unknown)
        self.case("conflicting-action", lambda: self.conflicting_action(job, effect))
        self.case("duplicate-event", self.duplicate_event)

    def case(self, name, operation):
        self.case_status[name] = {"started_gst": timestamp(), "status": "RUNNING"}
        save_json(self.directory / "case-status.json", self.case_status)
        try:
            result = operation()
        except Exception as failure:
            self.case_status[name].update(status="FAILED", ended_gst=timestamp(), error=str(failure))
            save_json(self.directory / "case-status.json", self.case_status)
            raise
        self.case_status[name].update(status="PASSED", ended_gst=timestamp())
        save_json(self.directory / "case-status.json", self.case_status)
        return result

    def close(self):
        errors = []
        for handle in list(self.active):
            proc = handle[0]
            if proc.poll() is None:
                proc.terminate()
            try:
                self.finish(handle)
            except Exception as failure:
                errors.append(str(failure))
        return errors


def rows(db, sql, key):
    return [dict(r) for r in db.execute(sql, (key,))]


def action(job):
    return job + "/create-followup/v1"


def drain(messages):
    values = []
    while not messages.empty():
        values.append(messages.get_nowait())
    return values


def wait_kind(handle, kind, timeout):
    proc, messages, threads, record = handle
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        message = messages.get(timeout=max(0.01, deadline - time.monotonic()))
        if message.get("kind") == kind:
            return message
        if message.get("kind") == "STREAM_CLOSED":
            raise RuntimeError(record["name"] + " closed stdout before " + kind)
    raise TimeoutError(record["name"] + " missing " + kind)


def types(log):
    return [r["event_type"] for r in log["logical"]]


def posts(ledger):
    return sum(r["method"] == "POST" and r["path"] == "/followups" for r in ledger["audit"])


def gets(ledger):
    return sum(r["method"] == "GET" and r["path"].startswith("/followups/") for r in ledger["audit"])


def normalize(log):
    normalized = []
    for position, record in enumerate(log["raw"]):
        event = dict(record["event"])
        event["job_id"] = "JOB"
        event["event_id"] = "JOB/" + str(event["attempt"]) + "/" + str(event["step"])
        event["action_id"] = "JOB/create-followup/v1"
        event["emitted_at_ms"] = "DISPLAY_TIMESTAMP"
        event["payload_digest"] = payload_digest(immutable_payload("JOB"))
        if event["event_type"] == "ACTION_REQUESTED":
            event["detail"] = json.dumps(immutable_payload("JOB"), sort_keys=True, separators=(",", ":"))
        normalized.append({"bucket": record["bucket"], "within_job_record": position, "event": event})
    return normalized


def immutable_payload(job):
    return {"classification": "needs-followup", "job_id": job,
            "ticket_id": "ticket-1042", "title": "Follow up synthetic ticket-1042"}


def payload_digest(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def wire_payload(raw_body):
    marker = b'"payload":'
    if raw_body.count(marker) != 1:
        raise ValueError("Expected one raw payload member in the worker envelope")
    start = raw_body.index(marker) + len(marker)
    text = raw_body.decode("utf-8")
    value, end = json.JSONDecoder().raw_decode(text, start)
    if not isinstance(value, dict):
        raise ValueError("Worker payload must be an object")
    return text[start:end].encode("utf-8")


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify"])
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--cluster-evidence", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--jar", type=Path, default=ROOT / "target" / "fluss-retry-lab.jar")
    parser.add_argument("--bootstrap", default="localhost:9123")
    parser.add_argument("--service-port", type=int, default=18080)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--java", default="java")
    parser.add_argument("--maven", default="mvn")
    return parser.parse_args()


def main():
    args = arguments()
    run = Run(args)
    status = "FAILED"
    error = None
    started = timestamp()
    try:
        run.execute()
        status = "PASSED"
    except Exception as failure:
        error = str(failure)
        raise
    finally:
        cleanup_errors = run.close()
        if cleanup_errors:
            status = "FAILED"
        save_json(run.directory / "manifest.json", {"status": status, "error": error,
                  "cleanup_errors": cleanup_errors, "started_gst": started, "ended_gst": timestamp(),
                  "run_id": args.run_id, "specified_cases": 7, "case_status": run.case_status,
                  "assertion_count": len(run.assertions), "cases_started": len(run.case_status),
                  "cluster_external_and_left_running": True})
        if cleanup_errors and error is None:
            raise RuntimeError("Cleanup failed: " + repr(cleanup_errors))


if __name__ == "__main__":
    main()
