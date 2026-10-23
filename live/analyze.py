#!/usr/bin/env python3
"""Merge sender logs and a receiver log into per-class metrics (same metrics as the simulator).

  python3 live/analyze.py --sent /tmp/sent_*.json --recv /tmp/recv.json
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from qos import metrics
from qos.packet import Packet
from qos.protocol import TC, CLASS_NAMES


def merge(sent, recv):
    """sent: list of dicts; recv: dict (flow,seq)->t_ns. Returns list[Packet]."""
    out = []
    for r in sent:
        p = Packet(r["flow"], r["seq"], TC(r["cls"]), r["size"], r["t_ns"] / 1e9)
        t = recv.get((r["flow"], r["seq"]))
        if t is None:
            p.status = "lost"
        else:
            p.status, p.t_recv = "delivered", t / 1e9
        out.append(p)
    return out


def true_class_fix(pkts):
    """Spoofed flood packets are logged with their true class (best effort) by the sender."""
    return pkts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sent", nargs="+", required=True, help="sender logs (globs allowed)")
    ap.add_argument("--recv", required=True)
    ap.add_argument("--duration", type=float, default=None)
    a = ap.parse_args()
    sent = []
    for pat in a.sent:
        for fn in glob.glob(pat):
            sent += json.load(open(fn))
    recv = {(f, s): t for f, s, t in json.load(open(a.recv))}
    pk = merge(sent, recv)
    dur = a.duration or (max(p.t_arrive for p in pk) - min(p.t_arrive for p in pk))
    s = metrics.summarize(pk, dur)
    sla = metrics.sla_check(s)
    print("%-12s %7s %8s %9s %9s %9s %9s  %s" % ("class", "sent", "loss%", "avg ms", "p99 ms", "jit ms", "kbps", "SLA"))
    for c, m in s.items():
        print("%-12s %7d %8.2f %9.1f %9.1f %9.1f %9.0f  %s" % (c, m["sent"], m["loss_pct"], m["delay_avg_ms"],
              m["delay_p99_ms"], m["jitter_ms"], m["throughput_kbps"],
              "-" if c == "best_effort" else ("PASS" if sla[c]["pass"] else "FAIL")))


if __name__ == "__main__":
    main()
