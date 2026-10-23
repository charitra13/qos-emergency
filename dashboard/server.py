#!/usr/bin/env python3
"""Tiny dependency-free web dashboard (python stdlib http.server).

  python3 dashboard/server.py --port 8080      then open http://localhost:8080
Pick a test case, click Run: the simulator executes all schedulers and the page draws
delay / loss / throughput charts, SLA verdicts and the emergency-delay timeline. The Live demo
view runs the real UDP sender/router/receiver pipeline and reports its metrics in the same page."""
import argparse
import json
import logging
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from qos import scenarios
from live.run_live_demo import run_demo

logger = logging.getLogger("qos.dashboard")
_cache, _lock = {}, threading.Lock()
_live_lock = threading.Lock()
PAGE = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"), encoding="utf-8").read()


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if u.path == "/api/scenarios":
            return self._send(200, json.dumps({k: {"title": v["title"], "desc": v["desc"]} for k, v in scenarios.SCENARIOS.items()}), "application/json")
        if u.path == "/api/run":
            sid = q.get("scenario", ["tc2"])[0]
            if sid not in scenarios.SCENARIOS:
                logger.warning("Rejected unknown simulation scenario: %s", sid)
                return self._send(404, json.dumps({"error": "unknown scenario"}), "application/json")
            try:
                dur = float(q.get("duration", ["0"])[0]) or None
                if dur is not None and dur < 0:
                    raise ValueError
            except ValueError:
                logger.warning("Rejected simulation with invalid duration: %s", q.get("duration", [""])[0])
                return self._send(400, json.dumps({"error": "duration must be a positive number"}), "application/json")
            key = (sid, dur)
            try:
                with _lock:
                    if key not in _cache:
                        logger.info("Starting simulation: scenario=%s duration=%s", sid, dur or "default")
                        _cache[key] = scenarios.run_scenario(sid, duration=dur)
                        logger.info("Simulation complete: scenario=%s", sid)
                    else:
                        logger.info("Serving cached simulation: scenario=%s duration=%s", sid, dur or "default")
            except Exception:
                logger.exception("Simulation failed: scenario=%s duration=%s", sid, dur or "default")
                return self._send(500, json.dumps({"error": "simulation failed; check the server terminal"}), "application/json")
            return self._send(200, json.dumps(_cache[key]), "application/json")
        if u.path == "/api/live":
            schedulers = q.get("schedulers", ["fifo,pq,wfq,drr,eps"])[0].split(",")
            allowed = set(scenarios.SCHED_ORDER)
            if not schedulers or any(s not in allowed for s in schedulers):
                logger.warning("Rejected live run with unknown scheduler(s): %s", schedulers)
                return self._send(400, json.dumps({"error": "unknown scheduler"}), "application/json")
            schedulers = list(dict.fromkeys(schedulers))
            scenario = q.get("scenario", ["congestion"])[0]
            if scenario not in ("congestion", "spoof"):
                logger.warning("Rejected unknown live scenario: %s", scenario)
                return self._send(400, json.dumps({"error": "unknown live scenario"}), "application/json")
            try:
                duration = min(30.0, max(1.0, float(q.get("duration", ["6"])[0])))
            except ValueError:
                logger.warning("Rejected live run with invalid duration: %s", q.get("duration", [""])[0])
                return self._send(400, json.dumps({"error": "duration must be a number"}), "application/json")
            if not _live_lock.acquire(blocking=False):
                logger.warning("Rejected overlapping live run: scenario=%s", scenario)
                return self._send(409, json.dumps({"error": "a live run is already in progress"}), "application/json")
            try:
                started = time.monotonic()
                logger.info("Starting live demo: scenario=%s duration=%.1fs schedulers=%s",
                            scenario, duration, ",".join(schedulers))
                result = run_demo(schedulers, duration, scenario)
                logger.info("Live demo complete: scenario=%s schedulers=%s elapsed=%.1fs",
                            scenario, ",".join(schedulers), time.monotonic() - started)
                return self._send(200, json.dumps(result), "application/json")
            except Exception:
                logger.exception("Live demo failed: scenario=%s schedulers=%s", scenario, ",".join(schedulers))
                return self._send(500, json.dumps({"error": "live demo failed; check the server terminal"}), "application/json")
            finally:
                _live_lock.release()
        self._send(404, "not found", "text/plain")

    def log_message(self, *a):
        logger.info("%s - %s", self.client_address[0], a[0] % a[1:])


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        stream=sys.stdout)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), H)
    logger.info("Dashboard listening on http://%s:%d (Ctrl-C to stop)", a.host, a.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user")


if __name__ == "__main__":
    main()
