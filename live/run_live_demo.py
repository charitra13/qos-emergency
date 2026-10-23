#!/usr/bin/env python3
"""One-command live demo on loopback: senders -> software QoS router (1 Mbit/s bottleneck) -> receiver.

  python3 live/run_live_demo.py                       # compare fifo, pq, wfq, eps (about 45 s)
  python3 live/run_live_demo.py --scenario spoof      # add a falsely-marked emergency flood
  python3 live/run_live_demo.py --schedulers fifo,eps --duration 8
Capture with Wireshark on the loopback interface, filter:  udp.port in {5004 5006 5911 5201}
"""
import argparse
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from live.qos_router import QoSRouter, INGRESS_OFFSET
from live.receiver import Receiver
from live.traffic_sender import run_sender
from live.analyze import merge
from qos import metrics, report
from qos.protocol import TC

LINK_BPS = 1_000_000


def one_run(sched, duration, scenario, verbose=True):
    rx = Receiver("127.0.0.1").start()
    # EPS profiles scaled to the 1 Mbit/s link: emergency class 35 % of the link, 40 kbit/s per source
    # (a genuine sensor needs ~30 kbit/s during an event; a spoofing flow is capped at 40 kbit/s)
    kw = dict(em_rate_frac=0.35, em_flow=(40e3, 3000)) if sched == "eps" else {}
    router = QoSRouter(sched, LINK_BPS, 25000, "127.0.0.1", "127.0.0.1", **kw).start()
    time.sleep(0.3)
    ev = [(duration * 0.35, duration * 0.35, 20)]
    jobs = [("voice", dict(flows=2)), ("video", dict(flows=1, kbps=150)),
            ("emergency", dict(flows=5, events=ev)), ("best_effort", dict(flows=1, kbps=1500))]
    if scenario == "spoof":
        jobs.append(("spoof", dict(flows=1, kbps=900)))
    results, threads = {}, []
    start = time.perf_counter() + 0.5

    def work(name, kw):
        results[name] = run_sender(name, "127.0.0.1", duration, port_offset=INGRESS_OFFSET,
                                   start_at=start, **kw)
    for n, kw in jobs:
        t = threading.Thread(target=work, args=(n, kw))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    time.sleep(2.5)                      # let the router queue drain
    router.stop()
    rx.stop()
    sent = [r for v in results.values() for r in v]
    pk = merge(sent, rx.records)
    summ = metrics.summarize(pk, duration)
    base = min((p.t_arrive for p in pk), default=0.0)
    buckets = {}
    for packet in pk:
        if packet.true_cls == TC.EMERGENCY and packet.delivered:
            bucket = int((packet.t_arrive - base) / 0.25)
            buckets.setdefault(bucket, []).append((packet.t_recv - packet.t_arrive) * 1000.0)
    timeline = [[round(bucket * 0.25, 3), round(sum(values) / len(values), 3)]
                for bucket, values in sorted(buckets.items())]
    return summ, metrics.sla_check(summ), router.report(), timeline


def run_demo(schedulers, duration, scenario):
    """Run real UDP traffic through the software router and return dashboard data."""
    runs = {}
    for sched in schedulers:
        summary, sla, router, timeline = one_run(sched, duration, scenario, verbose=False)
        runs[sched] = {"summary": summary, "sla": sla, "router": router,
                       "timeline": {"emergency": timeline}}
    return {
        "title": "Live demo - %s" % ("spoofed flood" if scenario == "spoof" else "congestion"),
        "desc": "Real UDP sockets through a software QoS router with a 1 Mbit/s rate-limited link. Results vary slightly with OS scheduling.",
        "source": "live",
        "runs": runs,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--schedulers", default="fifo,pq,wfq,eps")
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--scenario", choices=["congestion", "spoof"], default="congestion")
    a = ap.parse_args()
    print("Live demo: 1 Mbit/s bottleneck, offered load ~190 %% (voice 2 calls, video 150k, emergency 5 sources + event, bulk 1.5M%s)"
          % (", spoofed emergency flood 900k" if a.scenario == "spoof" else ""))
    print("%-6s %-12s %6s %8s %9s %9s %9s %8s  %s" % ("sched", "class", "sent", "loss%", "avg ms", "p99 ms", "jit ms", "kbps", "SLA"))
    for s in a.schedulers.split(","):
        summ, sla, _rc, _timeline = one_run(s, a.duration, a.scenario)
        for i, c in enumerate(report.CLASS_ORDER):
            m = summ[c]
            print("%-6s %-12s %6d %8.2f %9.1f %9.1f %9.1f %8.0f  %s" % (
                s if i == 0 else "", c, m["sent"], m["loss_pct"], m["delay_avg_ms"], m["delay_p99_ms"],
                m["jitter_ms"], m["throughput_kbps"], "-" if c == "best_effort" else ("PASS" if sla[c]["pass"] else "FAIL")))
        print()


if __name__ == "__main__":
    main()
