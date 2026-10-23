#!/usr/bin/env python3
"""UDP receiver: listens on all class ports, parses the QEP header, logs per-packet arrival.

CLI:  python3 live/receiver.py --bind 0.0.0.0 --duration 25 --log /tmp/recv.json
"""
import argparse
import json
import os
import select
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from qos.protocol import PORT_OF, unpack_header, ProtocolError


class Receiver:
    def __init__(self, bind="127.0.0.1", ports=None):
        self.socks = []
        for p in (ports or list(PORT_OF.values())):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
            s.bind((bind, p))
            s.setblocking(False)
            self.socks.append(s)
        self.records = {}          # (flow, seq) -> recv time ns
        self.bad = 0
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while not self._stop.is_set():
            r, _, _ = select.select(self.socks, [], [], 0.05)
            for s in r:
                while True:
                    try:
                        data, _a = s.recvfrom(4096)
                    except (BlockingIOError, InterruptedError):
                        break
                    now = time.time_ns()
                    try:
                        h = unpack_header(data)
                        self.records[(h["flow"], h["seq"])] = now
                    except ProtocolError:
                        self.bad += 1

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self._stop.set()
        self.thread.join(timeout=1)
        for s in self.socks:
            s.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--duration", type=float, default=30)
    ap.add_argument("--log", required=True)
    a = ap.parse_args()
    r = Receiver(a.bind).start()
    print("receiver listening on %s ports %s for %.0fs" % (a.bind, list(PORT_OF.values()), a.duration))
    time.sleep(a.duration)
    r.stop()
    json.dump([[f, s, t] for (f, s), t in r.records.items()], open(a.log, "w"))
    print("received %d packets (%d malformed)" % (len(r.records), r.bad))


if __name__ == "__main__":
    main()
