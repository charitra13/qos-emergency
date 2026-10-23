#!/usr/bin/env python3
"""Software QoS router: UDP ingress -> classifier -> scheduler -> rate-limited egress.

It emulates a congested bottleneck link of `rate_bps` using real sockets. Packets arrive on
ingress ports (egress port + 1000), are classified (QEP header / DSCP / port / flow cache),
queued by the chosen scheduler (fifo|pq|wfq|drr|eps - the same classes used by the simulator)
and forwarded to the receiver at the configured rate, re-marked with the class DSCP.
"""
import argparse
import os
import select
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from qos.classifier import Classifier
from qos.packet import Packet
from qos.protocol import (TC, PORT_OF, CLASS_OF_PORT, DSCP_OF, IP_UDP_OVERHEAD, CLASSES,
                          CLASS_NAMES, unpack_header, ProtocolError)
from qos.schedulers import make_scheduler

INGRESS_OFFSET = 1000
IP_RECVTOS = getattr(socket, "IP_RECVTOS", 13)


class QoSRouter:
    def __init__(self, scheduler="eps", rate_bps=1_000_000, buffer_bytes=25000,
                 listen_ip="127.0.0.1", out_ip="127.0.0.1", classifier="full", **sched_kw):
        self.sched = make_scheduler(scheduler, rate_bps, buffer_bytes, **sched_kw)
        self.rate = rate_bps
        self.clf = Classifier(classifier)
        self.out_ip = out_ip
        self.lock = threading.Lock()
        self.stop_evt = threading.Event()
        self.counters = {c: {"in": 0, "out": 0, "dropped": 0} for c in CLASSES}
        self.in_socks = {}
        for port in PORT_OF.values():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
            s.bind((listen_ip, port + INGRESS_OFFSET))
            s.setblocking(False)
            try:
                s.setsockopt(socket.IPPROTO_IP, IP_RECVTOS, 1)
                self._tos_ok = True
            except OSError:
                self._tos_ok = False
            self.in_socks[s] = port
        self.out_socks = {}
        for c in CLASSES:
            o = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                o.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, DSCP_OF[c] << 2)
            except OSError:
                pass
            self.out_socks[c] = o
        self.threads = [threading.Thread(target=self._ingress, daemon=True),
                        threading.Thread(target=self._egress, daemon=True)]

    # ------------------------------------------------------------- ingress
    def _recv(self, s):
        dscp = None
        if self._tos_ok and hasattr(s, "recvmsg"):
            try:
                data, anc, _fl, _ad = s.recvmsg(4096, 64)
                for lvl, typ, val in anc:
                    if lvl == socket.IPPROTO_IP and typ in (1, IP_RECVTOS) and val:
                        dscp = val[0] >> 2
                return data, dscp
            except (BlockingIOError, InterruptedError):
                raise
            except OSError:
                self._tos_ok = False
        data, _a = s.recvfrom(4096)
        return data, dscp

    def _ingress(self):
        socks = list(self.in_socks)
        while not self.stop_evt.is_set():
            r, _, _ = select.select(socks, [], [], 0.05)
            for s in r:
                while True:
                    try:
                        data, dscp = self._recv(s)
                    except (BlockingIOError, InterruptedError):
                        break
                    now = time.perf_counter()
                    port = self.in_socks[s]
                    hdr_cls, flow, seq = None, port, 0
                    try:
                        h = unpack_header(data)
                        hdr_cls, flow, seq = h["cls"], h["flow"], h["seq"]
                    except ProtocolError:
                        pass
                    pkt = Packet(flow, seq, CLASS_OF_PORT.get(port, TC.BEST_EFFORT),
                                 len(data) + IP_UDP_OVERHEAD, now)
                    pkt.cls, _why = self.clf.classify(dscp, port, hdr_cls, flow)
                    pkt.payload, pkt.dport = data, port
                    with self.lock:
                        self.counters[pkt.cls]["in"] += 1
                        for d in self.sched.enqueue(pkt, now):
                            self.counters[d.cls]["dropped"] += 1

    # -------------------------------------------------------------- egress
    def _egress(self):
        next_free = time.perf_counter()
        while not self.stop_evt.is_set():
            now = time.perf_counter()
            if now < next_free:
                time.sleep(min(next_free - now, 0.001))
                continue
            with self.lock:
                pkt = self.sched.dequeue(now)
            if pkt is None:
                time.sleep(0.0003)
                next_free = max(next_free, now - 0.002)   # idle link accrues no credit
                continue
            self.out_socks[pkt.cls].sendto(pkt.payload, (self.out_ip, pkt.dport))
            self.counters[pkt.cls]["out"] += 1
            next_free = max(next_free, now - 0.005) + pkt.size * 8.0 / self.rate

    def start(self):
        for t in self.threads:
            t.start()
        return self

    def stop(self):
        self.stop_evt.set()
        for t in self.threads:
            t.join(timeout=1)
        for s in list(self.in_socks) + list(self.out_socks.values()):
            s.close()

    def report(self):
        return {CLASS_NAMES[c]: v for c, v in self.counters.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scheduler", default="eps", choices=["fifo", "pq", "wfq", "drr", "eps"])
    ap.add_argument("--rate-kbps", type=float, default=1000)
    ap.add_argument("--buffer", type=int, default=25000)
    ap.add_argument("--listen", default="0.0.0.0")
    ap.add_argument("--out", default="127.0.0.1", help="receiver IP")
    ap.add_argument("--duration", type=float, default=0, help="0 = run until Ctrl-C")
    a = ap.parse_args()
    r = QoSRouter(a.scheduler, a.rate_kbps * 1000, a.buffer, a.listen, a.out).start()
    print("QoS router up: scheduler=%s rate=%.0f kbit/s ingress ports=%s" %
          (a.scheduler, a.rate_kbps, [p + INGRESS_OFFSET for p in PORT_OF.values()]))
    try:
        time.sleep(a.duration) if a.duration else threading.Event().wait()
    except KeyboardInterrupt:
        pass
    r.stop()
    print(r.report())


if __name__ == "__main__":
    main()
