#!/usr/bin/env python3
"""Run QoS test cases in the discrete-event simulator and produce reports.

Examples
  python3 run_simulation.py --scenario all            # every test case + sweep + ablation
  python3 run_simulation.py --scenario tc6            # one test case
  python3 run_simulation.py --scenario tc2 --pcap results/tc2_eps.pcap --pcap-scheduler eps
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qos import scenarios, report, pcapio


def print_table(res):
    print("\n" + "=" * 100)
    print(res["title"])
    print(res["desc"])
    print("-" * 100)
    print("%-16s %-12s %7s %8s %9s %9s %9s %9s  %s" % ("scheduler", "class", "sent", "loss%", "avg ms", "p99 ms", "jit ms", "kbps", "SLA"))
    for s, run in res["runs"].items():
        for c in report.CLASS_ORDER:
            m, v = run["summary"][c], run["sla"][c]
            sla = "  -" if c == "best_effort" else ("PASS" if v["pass"] else "FAIL")
            print("%-16s %-12s %7d %8.2f %9.1f %9.1f %9.1f %9.0f  %s" % (
                report.LABELS.get(s, s) if c == "emergency" else "", c, m["sent"], m["loss_pct"],
                m["delay_avg_ms"], m["delay_p99_ms"], m["jitter_ms"], m["throughput_kbps"], sla))
        if "recovery_ms" in run:
            print("%-16s recovery time (emergency delay back < 100 ms): %.0f ms" % ("", run["recovery_ms"]))
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="all", help="tc1..tc9, sweep, ablation, or all (default)")
    ap.add_argument("--schedulers", default=",".join(scenarios.SCHED_ORDER), help="comma list: fifo,pq,wfq,drr,eps")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--duration", type=float, default=None, help="override scenario duration (s)")
    ap.add_argument("--out", default="results", help="output directory")
    ap.add_argument("--pcap", help="write a Wireshark pcap for the (single) selected scenario")
    ap.add_argument("--pcap-scheduler", default="eps")
    ap.add_argument("--pcap-limit", type=int, default=20000)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    scheds = a.schedulers.split(",")
    os.makedirs(a.out, exist_ok=True)
    sel = a.scenario.lower()
    ids = list(scenarios.SCENARIOS) if sel == "all" else ([sel] if sel in scenarios.SCENARIOS else [])
    if not ids and sel not in ("sweep", "ablation"):
        sys.exit("unknown scenario %r" % sel)

    results, sweep, ablation = {}, None, None
    t0 = time.time()
    for sid in ids:
        res = scenarios.run_scenario(sid, scheds, a.seed, a.duration, keep_packets=bool(a.pcap))
        if a.pcap and sid == ids[0]:
            pk = res["runs"][a.pcap_scheduler].get("_packets")
            n = pcapio.write_pcap(a.pcap, pk, a.pcap_limit)
            print("wrote %s (%d packets, scheduler=%s)" % (a.pcap, n, a.pcap_scheduler))
        for r in res["runs"].values():
            r.pop("_packets", None)
        results[sid] = res
        if not a.quiet:
            print_table(res)
    if sel in ("all", "sweep"):
        sweep = scenarios.run_load_sweep(scheds, a.seed)
        print("\nTC10 load sweep (emergency p99 ms / voice p99 ms) at bulk loads", sweep["loads_kbps"])
        for s, r in sweep["runs"].items():
            print("  %-6s emergency %s" % (s, r["emergency_p99_ms"]))
            print("  %-6s voice     %s" % ("", r["voice_p99_ms"]))
    if sel in ("all", "ablation", "tc7"):
        ablation = scenarios.classifier_ablation(a.seed)
        print("\nClassifier ablation (noisy markings, EPS scheduler):")
        print("  %-10s %10s %10s %14s %14s" % ("mode", "accuracy%", "cache-hit%", "emerg p99 ms", "emerg loss%"))
        for m, v in ablation.items():
            print("  %-10s %10.2f %10.2f %14.1f %14.2f" % (m, v["accuracy_pct"], v["cache_hit_ratio_pct"], v["emergency_p99_ms"], v["emergency_loss_pct"]))

    tag = sel
    with open(os.path.join(a.out, "results_%s.json" % tag), "w") as f:
        json.dump({"scenarios": results, "sweep": sweep, "ablation": ablation}, f, indent=1)
    if results:
        with open(os.path.join(a.out, "summary_%s.csv" % tag), "w") as f:
            f.write(report.to_csv(results))
        with open(os.path.join(a.out, "summary_%s.md" % tag), "w") as f:
            f.write("# Simulation results\n\n" + "\n".join(report.scenario_table_md(r) for r in results.values()))
    with open(os.path.join(a.out, "report_%s.html" % tag), "w") as f:
        f.write(report.build_html(results, sweep, ablation))
    print("\nReports written to %s/ (report_%s.html, summary_%s.csv/.md, results_%s.json) in %.1fs" % (a.out, tag, tag, tag, time.time() - t0))


if __name__ == "__main__":
    main()
