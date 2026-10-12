"""Synthetic deterministic inference and follow-up fixture with a durable SQLite ledger."""

import argparse
from contextlib import closing
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import unquote

CONTRACT = "fixture-atomic-action-id-payload-v1"
DDL = """
CREATE TABLE IF NOT EXISTS effects (
 action_id TEXT PRIMARY KEY, payload_digest TEXT NOT NULL,
 payload_json TEXT NOT NULL, receipt_json TEXT NOT NULL, committed_at_ms INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS computations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, attempt INTEGER NOT NULL,
 ticket_id TEXT NOT NULL, classification TEXT NOT NULL, invoked_at_ms INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS lookup_modes (
 action_id TEXT PRIMARY KEY, available INTEGER NOT NULL, receipt_fault TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS http_audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, method TEXT NOT NULL, path TEXT NOT NULL,
 job_id TEXT NOT NULL, action_id TEXT NOT NULL, payload_digest TEXT NOT NULL,
 request_json TEXT NOT NULL, status INTEGER NOT NULL, response_json TEXT NOT NULL,
 at_ms INTEGER NOT NULL, request_body_hex TEXT NOT NULL);
"""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def now_ms():
    return time.time_ns() // 1_000_000


def open_ledger(path):
    db = sqlite3.connect(path, timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("PRAGMA busy_timeout=10000")
    db.row_factory = sqlite3.Row
    return db


def initialize(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(open_ledger(path)) as db:
        db.executescript(DDL)


def job_from_action(action_id):
    suffix = "/create-followup/v1"
    if not isinstance(action_id, str):
        raise ValueError("Action identity must be a string")
    if not action_id.endswith(suffix):
        raise ValueError("Invalid synthetic action identity")
    return action_id[:-len(suffix)]


def validate_payload(payload):
    expected = {"classification", "job_id", "ticket_id", "title"}
    if set(payload) != expected:
        raise ValueError("Unexpected immutable payload fields")
    validate_ascii_fields(payload)
    if payload["ticket_id"] != "ticket-1042":
        raise ValueError("Only synthetic ticket-1042 is supported")
    if not re.fullmatch(r"[A-Za-z0-9_./-]+/ticket-1042", payload["job_id"]):
        raise ValueError("Invalid synthetic job_id")
    if payload["classification"] != "needs-followup":
        raise ValueError("Unexpected deterministic classification")


def validate_ascii_fields(payload):
    for value in payload.values():
        if not isinstance(value, str) or not value.isascii():
            raise ValueError("Payload fields must be ASCII strings")


def create_effect(db, body):
    payload = body["payload"]
    validate_payload(payload)
    action_id = body["action_id"]
    if job_from_action(action_id) != payload["job_id"]:
        raise ValueError("Action and immutable payload identify different jobs")
    if body["payload_digest"] != digest(payload):
        raise ValueError("Immutable payload digest mismatch")
    existing = db.execute("SELECT * FROM effects WHERE action_id=?", (action_id,)).fetchone()
    if existing is not None:
        return duplicate_receipt(existing, body)
    committed = now_ms()
    receipt = {"action_id": action_id, "payload_digest": body["payload_digest"],
               "receipt_id": "followup-" + hashlib.sha256(action_id.encode()).hexdigest()[:24],
               "committed_at_ms": committed, "contract": CONTRACT}
    db.execute("INSERT INTO effects VALUES (?, ?, ?, ?, ?)",
               (action_id, body["payload_digest"], canonical(payload), canonical(receipt), committed))
    return 201, receipt


def duplicate_receipt(existing, body):
    if existing["payload_digest"] != body["payload_digest"]:
        return 409, {"error": "action identity payload conflict", "contract": CONTRACT}
    if existing["payload_json"] != canonical(body["payload"]):
        return 409, {"error": "action identity immutable payload conflict", "contract": CONTRACT}
    return 200, json.loads(existing["receipt_json"])


def lookup_receipt(db, action_id):
    job_from_action(action_id)
    mode = db.execute("SELECT available,receipt_fault FROM lookup_modes WHERE action_id=?", (action_id,)).fetchone()
    if mode is not None and mode["available"] == 0:
        return 503, {"error": "receipt lookup deliberately unavailable", "contract": CONTRACT}
    row = db.execute("SELECT receipt_json FROM effects WHERE action_id=?", (action_id,)).fetchone()
    if row is None:
        return 404, {"action_id": action_id, "absent": True, "contract": CONTRACT}
    receipt = json.loads(row["receipt_json"])
    if mode is not None:
        receipt = corrupt_receipt(receipt, mode["receipt_fault"])
    return 200, receipt


def corrupt_receipt(receipt, fault):
    if fault == "wrong-action":
        receipt["action_id"] = "wrong-receipt/ticket-1042/create-followup/v1"
    if fault == "wrong-digest":
        receipt["payload_digest"] = "0" * 64
    return receipt


def compute(db, body):
    if body["ticket_id"] != "ticket-1042":
        raise ValueError("Only synthetic ticket-1042 is supported")
    if not isinstance(body["attempt"], int) or body["attempt"] < 1:
        raise ValueError("Invalid attempt")
    invoked = now_ms()
    cursor = db.execute("INSERT INTO computations(job_id,attempt,ticket_id,classification,invoked_at_ms) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (body["job_id"], body["attempt"], body["ticket_id"], "needs-followup", invoked))
    return 200, {"classification": "needs-followup", "invocation_id": cursor.lastrowid,
                 "stand_in": "deterministic synthetic classifier", "invoked_at_ms": invoked}


def control(db, body):
    action_id = body["action_id"]
    job_from_action(action_id)
    available = body["lookup_available"]
    if not isinstance(available, bool):
        raise ValueError("lookup_available must be boolean")
    fault = body.get("receipt_fault", "")
    if fault not in ["", "wrong-action", "wrong-digest"]:
        raise ValueError("Unknown receipt fault")
    db.execute("INSERT INTO lookup_modes VALUES (?, ?, ?) ON CONFLICT(action_id) "
               "DO UPDATE SET available=excluded.available,receipt_fault=excluded.receipt_fault",
               (action_id, int(available), fault))
    return 200, {"action_id": action_id, "lookup_available": available}


def dispatch(db, method, path, body):
    if method == "GET" and path == "/health":
        return 200, {"contract": CONTRACT, "inference": "deterministic stand-in"}
    if method == "GET" and path.startswith("/followups/"):
        return lookup_receipt(db, unquote(path[len("/followups/"):]))
    handlers = {"/followups": create_effect, "/compute": compute, "/control": control}
    if method == "POST" and path in handlers:
        return handlers[path](db, body)
    return 404, {"error": "Unknown fixture endpoint"}


def audit_identity(path, body):
    if body is None:
        return "", "", ""
    action_id = str(body.get("action_id", ""))
    if path.startswith("/followups/"):
        action_id = unquote(path[len("/followups/"):])
    job = str(body.get("job_id", ""))
    if action_id.endswith("/create-followup/v1"):
        job = job_from_action(action_id)
    return job, action_id, str(body.get("payload_digest", ""))


def transact(path, method, route, raw_body):
    with closing(open_ledger(path)) as db:
        db.execute("BEGIN IMMEDIATE")
        body = None
        try:
            body = decode_body(method, raw_body)
            status, response = dispatch(db, method, route, body)
        except (ValueError, KeyError, TypeError) as error:
            status, response = 400, {"error": str(error)}
        job, action_id, payload_digest = audit_identity(route, body)
        db.execute("INSERT INTO http_audit(method,path,job_id,action_id,payload_digest,"
                   "request_json,status,response_json,at_ms,request_body_hex) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (method, route, job, action_id, payload_digest, canonical(body), status,
                    canonical(response), now_ms(), raw_body.hex()))
        db.commit()
    return status, response


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.respond("GET", b"")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 65536:
            self.send_error(400, "Expected a bounded JSON request")
            return
        raw_body = self.rfile.read(length)
        self.respond("POST", raw_body)

    def respond(self, method, raw_body):
        status, response = transact(self.server.ledger, method, self.path, raw_body)
        data = canonical(response).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()


def decode_body(method, raw_body):
    if method == "GET":
        return {}
    value = json.loads(raw_body, object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise ValueError("Fixture request must be a JSON object")
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    initialize(args.ledger)
    with HTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.ledger = args.ledger
        print(canonical({"kind": "SERVICE_READY", "host": "127.0.0.1", "port": args.port,
                         "ledger": str(args.ledger.resolve()), "contract": CONTRACT}), flush=True)
        server.serve_forever(poll_interval=0.2)


if __name__ == "__main__":
    main()
