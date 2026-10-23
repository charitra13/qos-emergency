#!/usr/bin/env python3
"""Packet-level verification of a capture (simulated or live) without needing Wireshark.

For every UDP packet carrying a QEP header it checks:
  * header checksum / magic / version
  * IP DSCP matches the class declared in the QEP header
  * per-class count, mean/p99 (capture time - QEP timestamp), priority ordering
Use --ports to restrict to the receiver-side ports (final leg of a live capture)."""
import argparse
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from qos.pcapio import read_pcap, decode_udp
from qos.protocol import unpack_header, ProtocolError, DSCP_OF, CLASS_NAMES, PORT_OF, TC
from qos.metrics import percentile


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pcap")
    ap.add_argument("--ports", default=",".join(str(p) for p in PORT_OF.values()),
                    help="comma list of UDP destination ports to analyse")
    ap.add_argument("--by-flow", action="store_true", help="also print the 12 busiest flows")
    a = ap.parse_args()
    ports = {int(x) for x in a.ports.split(",")}
    stats, flows, bad_csum, dscp_mismatch, total = {}, {}, 0, 0, 0
    for ts, link, raw in read_pcap(a.pcap):
        d = decode_udp(link, raw)
        if not d or d[2] not in ports:
            continue
        dscp, _sp, _dp, payload = d
        total += 1
        try:
            h = unpack_header(payload)
        except ProtocolError:
            bad_csum += 1
            continue
        if dscp != 0 and dscp != DSCP_OF[h["cls"]]:
            dscp_mismatch += 1          # e.g. spoofed or re-marked packet
        delay = (ts - h["ts_ns"] / 1e9) * 1000.0
        stats.setdefault(h["cls"], []).append(delay)
        flows.setdefault((h["flow"], h["cls"]), []).append(delay)
    print("QEP packets analysed: %d   header errors: %d   DSCP/class mismatches: %d" %
          (total, bad_csum, dscp_mismatch))
    print("%-12s %8s %12s %12s %12s" % ("class", "packets", "mean ms", "p99 ms", "max ms"))
    for c in sorted(stats):
        v = sorted(stats[c])
        print("%-12s %8d %12.2f %12.2f %12.2f" % (CLASS_NAMES[c], len(v), sum(v) / len(v),
                                                   percentile(v, 99), v[-1]))
    if a.by_flow:
        print("\n%-8s %-12s %8s %12s %12s" % ("flow", "qep class", "packets", "mean ms", "p99 ms"))
        for (fl, c), v in sorted(flows.items(), key=lambda kv: -len(kv[1]))[:12]:
            v = sorted(v)
            print("%-8d %-12s %8d %12.2f %12.2f" % (fl, CLASS_NAMES[c], len(v), sum(v) / len(v), percentile(v, 99)))
    if TC.EMERGENCY in stats and TC.BEST_EFFORT in stats:
        e = sum(stats[TC.EMERGENCY]) / len(stats[TC.EMERGENCY])
        b = sum(stats[TC.BEST_EFFORT]) / len(stats[TC.BEST_EFFORT])
        print("\nVERDICT: emergency mean delay %.2f ms vs best-effort %.2f ms -> %s" %
              (e, b, "PRIORITY HONOURED" if e < 0.5 * b else "NO PRIORITY EFFECT (FIFO-like behaviour)"))


if __name__ == "__main__":
    main()
