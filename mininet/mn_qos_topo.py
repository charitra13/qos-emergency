#!/usr/bin/env python3
"""Mininet emulation of the QoS topology using Linux tc on the bottleneck interface.

        h_voice  (10.0.1.1) --\
        h_video  (10.0.1.2) ---+-- s1 -- r1 (Linux router) == 10 Mbit/s bottleneck == s2 -- h_srv (10.0.2.2)
        h_emerg  (10.0.1.3) ---+
        h_bulk   (10.0.1.4) --/

Hosts run live/traffic_sender.py (sets DSCP on the IP header, QEP header in payload);
h_srv runs live/receiver.py. The router queueing discipline on r1-eth2 is switched between:
   fifo : tbf (rate limit) + FIFO
   prio : tbf + 4-band strict priority classified on DSCP         (~ Strict PQ)
   htb  : htb with per-class rate/ceil/prio + DSCP filters         (~ EPS: policed strict tiers + sharing)

Run (root required):   sudo python3 mininet/mn_qos_topo.py --modes fifo,prio,htb --duration 20
Verify: tshark / Wireshark on r1-eth2 (the file results/mn_<mode>_r1-eth2.pcap is written when tcpdump exists).
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)

try:
    from mininet.net import Mininet
    from mininet.node import Node, Switch
    from mininet.link import TCLink
    from mininet.log import setLogLevel
    from mininet.cli import CLI
except ImportError:
    print("Mininet is not installed. Install with: sudo apt install mininet openvswitch-switch")
    sys.exit(1)

BOTTLENECK = "r1-eth2"
RATE = "10mbit"


class LinuxBridge(Switch):
    """Plain kernel bridge: Docker Desktop has no openvswitch module, and Mininet 2.3.0 lacks its own."""
    def start(self, controllers):
        self.cmd("ip link add name %s type bridge stp_state 0" % self.name)
        for i in self.intfList():
            if i.name != "lo":
                self.cmd("ip link set %s master %s" % (i.name, self.name))
        self.cmd("ip link set %s up" % self.name)

    def stop(self, deleteIntfs=True):
        self.cmd("ip link del %s" % self.name)
        super().stop(deleteIntfs)

    def connected(self):
        return True


class LinuxRouter(Node):
    def config(self, **params):
        super().config(**params)
        self.cmd("sysctl -w net.ipv4.ip_forward=1")

    def terminate(self):
        self.cmd("sysctl -w net.ipv4.ip_forward=0")
        super().terminate()


def build():
    # LinuxBridge instead of OVS: works in Docker Desktop, where the openvswitch kernel module is missing
    net = Mininet(controller=None, switch=LinuxBridge, link=TCLink, autoSetMacs=True)
    r1 = net.addHost("r1", cls=LinuxRouter, ip="10.0.1.254/24")
    s1, s2 = net.addSwitch("s1"), net.addSwitch("s2")
    hosts = {}
    for name, ip in (("h_voice", "10.0.1.1"), ("h_video", "10.0.1.2"), ("h_emerg", "10.0.1.3"), ("h_bulk", "10.0.1.4")):
        hosts[name] = net.addHost(name, ip=ip + "/24", defaultRoute="via 10.0.1.254")
        net.addLink(hosts[name], s1)
    srv = net.addHost("h_srv", ip="10.0.2.2/24", defaultRoute="via 10.0.2.254")
    net.addLink(s1, r1, intfName2="r1-eth1", params2={"ip": "10.0.1.254/24"})
    net.addLink(s2, r1, intfName2="r1-eth2", params2={"ip": "10.0.2.254/24"})
    net.addLink(srv, s2)
    return net, r1, hosts, srv


def tc_setup(r1, mode, buffer_bytes=125000):
    d = BOTTLENECK
    r1.cmd("tc qdisc del dev %s root 2>/dev/null" % d)
    r1.cmd("ethtool -K %s tso off gso off gro off 2>/dev/null" % d)
    if mode == "fifo":
        r1.cmd("tc qdisc add dev %s root tbf rate %s burst 16k limit %d" % (d, RATE, buffer_bytes))
    elif mode == "prio":
        r1.cmd("tc qdisc add dev %s root handle 1: tbf rate %s burst 16k limit %d" % (d, RATE, buffer_bytes))
        r1.cmd("tc qdisc add dev %s parent 1:1 handle 10: prio bands 4 priomap 3 3 3 3 3 3 3 3 3 3 3 3 3 3 3 3" % d)
        for tos, band in (("0xc0", 1), ("0xb8", 2), ("0x88", 3)):
            r1.cmd("tc filter add dev %s parent 10: protocol ip prio 1 u32 match ip tos %s 0xfc flowid 10:%d" % (d, tos, band))
    elif mode == "htb":
        r1.cmd("tc qdisc add dev %s root handle 1: htb default 40" % d)
        r1.cmd("tc class add dev %s parent 1: classid 1:1 htb rate %s ceil %s" % (d, RATE, RATE))
        # (classid, rate, ceil, prio)  emergency 2M capped, voice 3.5M capped, video 3M may borrow, bulk 1.5M may borrow
        for cid, rate, ceil, prio in ((10, "2mbit", "2mbit", 0), (20, "3500kbit", "3500kbit", 1),
                                      (30, "3mbit", RATE, 2), (40, "1500kbit", RATE, 3)):
            r1.cmd("tc class add dev %s parent 1:1 classid 1:%d htb rate %s ceil %s prio %d" % (d, cid, rate, ceil, prio))
            r1.cmd("tc qdisc add dev %s parent 1:%d handle %d: pfifo limit 80" % (d, cid, cid))
        for tos, cid in (("0xc0", 10), ("0xb8", 20), ("0x88", 30)):
            r1.cmd("tc filter add dev %s parent 1: protocol ip prio 1 u32 match ip tos %s 0xfc flowid 1:%d" % (d, tos, cid))
    else:
        raise ValueError(mode)


def run_mode(net, r1, hosts, srv, mode, duration, bulk_kbps, outdir):
    tc_setup(r1, mode)
    tag = "/tmp/qos_%s_" % mode
    for f in os.listdir("/tmp"):
        if f.startswith("qos_%s_" % mode):
            os.remove(os.path.join("/tmp", f))
    cap = r1.popen("tcpdump -i %s -w %s/mn_%s_%s.pcap udp 2>/dev/null" % (BOTTLENECK, outdir, mode, BOTTLENECK), shell=True)
    py = sys.executable
    srv_p = srv.popen("%s %s/live/receiver.py --duration %d --log %srecv.json" % (py, ROOT, duration + 6, tag), shell=True)
    time.sleep(1)
    ev = "--event %.1f,%.1f,40" % (duration * 0.3, duration * 0.3)
    cmds = {
        "h_voice": "--cls voice --flows 20",
        "h_video": "--cls video --flows 3 --kbps 3000",
        "h_emerg": "--cls emergency --flows 10 %s" % ev,
        "h_bulk": "--cls best_effort --flows 1 --kbps %d" % bulk_kbps,
    }
    procs = []
    for h, args in cmds.items():
        cls = args.split()[1]
        procs.append(hosts[h].popen("%s %s/live/traffic_sender.py %s --dest 10.0.2.2 --duration %d --log %ssent_%s.json" %
                                    (py, ROOT, args, duration, tag, cls), shell=True))
    for p in procs:
        p.wait()
    srv_p.wait()
    cap.terminate()
    os.system("%s %s/live/analyze.py --sent %ssent_*.json --recv %srecv.json --duration %d" % (py, ROOT, tag, tag, duration))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modes", default="fifo,prio,htb")
    ap.add_argument("--duration", type=int, default=20)
    ap.add_argument("--bulk-kbps", type=int, default=12000, help="bulk offered load (default overloads link)")
    ap.add_argument("--cli", action="store_true", help="open Mininet CLI afterwards")
    ap.add_argument("--out", default=os.path.join(ROOT, "results"))
    a = ap.parse_args()
    if os.geteuid() != 0:
        sys.exit("Run with sudo (Mininet needs root).")
    os.makedirs(a.out, exist_ok=True)
    setLogLevel("warning")
    net, r1, hosts, srv = build()
    net.start()
    print("connectivity:", "ok" if net.ping([hosts["h_voice"], srv], timeout=2) == 0 else "FAILED")
    for m in a.modes.split(","):
        print("\n=== qdisc mode: %s  (bulk=%d kbit/s on a 10 Mbit/s bottleneck) ===" % (m, a.bulk_kbps))
        run_mode(net, r1, hosts, srv, m, a.duration, a.bulk_kbps, a.out)
    if a.cli:
        CLI(net)
    net.stop()


if __name__ == "__main__":
    main()
