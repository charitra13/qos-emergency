#!/usr/bin/env python3
"""Real-time UDP traffic generator (one traffic class) that emits QEP packets.

Reuses qos.traffic generators for the timing/size pattern and sets the IP TOS/DSCP byte.
CLI example (used by the Mininet script):
  python3 live/traffic_sender.py --cls voice --dest 10.0.2.2 --duration 20 --flows 20 --log /tmp/sent_voice.json
"""
import argparse
import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from qos import traffic
from qos.protocol import TC, NAME_TO_CLASS, PORT_OF, DSCP_OF, build_packet


def sender_cfg(cls_name, duration, flows, kbps, events):
    cfg = dict(duration=duration, be_random_ports=False, noise={})
    if cls_name == "voice":
        cfg["voice_calls"] = flows
    elif cls_name == "video":
        cfg.update(video_streams=flows, video_kbps=kbps)
    elif cls_name == "emergency":
        cfg.update(emerg_sources=flows, emerg_hb_pps=5, emerg_events=events)
    elif cls_name == "best_effort":
        cfg["be_kbps"] = kbps
    elif cls_name == "spoof":
        cfg["spoof_kbps"] = kbps
    return cfg


def run_sender(cls_name, dest_ip, duration, flows=1, kbps=0, events=(), port_offset=0,
               seed=1, start_at=None, use_tos=True):
    """Send for `duration` seconds. Returns list of sent records."""
    cfg = sender_cfg(cls_name, duration, flows, kbps, list(events))
    pkts = traffic.generate(cfg, seed, only={cls_name})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
    dscp = DSCP_OF[TC.EMERGENCY] if cls_name == "spoof" else DSCP_OF[NAME_TO_CLASS[cls_name]]
    if use_tos:
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, dscp << 2)
        except OSError:
            pass
    dport = PORT_OF[TC.EMERGENCY] if cls_name == "spoof" else PORT_OF[NAME_TO_CLASS[cls_name]]
    sent = []
    t0 = start_at if start_at else time.perf_counter()
    while time.perf_counter() < t0 - 0.0005:
        time.sleep(0.0005)
    for p in pkts:
        target = t0 + p.t_arrive
        while True:
            rem = target - time.perf_counter()
            if rem <= 0:
                break
            time.sleep(min(rem, 0.002) if rem > 0.0015 else 0)
        qcls = p.hdr_cls if p.hdr_cls is not None else p.true_cls
        ts = time.time_ns()
        data = build_packet(qcls, p.flow, p.seq, ts, p.size, p.flags, p.dscp)
        sock.sendto(data, (dest_ip, dport + port_offset))
        sent.append({"flow": p.flow, "seq": p.seq, "cls": int(p.true_cls), "size": p.size, "t_ns": ts})
    sock.close()
    return sent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cls", required=True, choices=["voice", "video", "emergency", "best_effort", "spoof"])
    ap.add_argument("--dest", required=True)
    ap.add_argument("--duration", type=float, default=10)
    ap.add_argument("--flows", type=int, default=1, help="calls / streams / sources")
    ap.add_argument("--kbps", type=float, default=0, help="video/best_effort/spoof rate")
    ap.add_argument("--event", action="append", default=[], help="emergency event t0,dur,pps (repeatable)")
    ap.add_argument("--port-offset", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--log", help="write JSON log of sent packets")
    a = ap.parse_args()
    events = [tuple(float(x) for x in e.split(",")) for e in a.event]
    sent = run_sender(a.cls, a.dest, a.duration, a.flows, a.kbps, events, a.port_offset, a.seed)
    print("sent %d %s packets" % (len(sent), a.cls))
    if a.log:
        json.dump(sent, open(a.log, "w"))


if __name__ == "__main__":
    main()
