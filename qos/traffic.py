"""Synthetic traffic generators for voice, video, emergency, bulk and spoofed flows."""
import random
from .packet import Packet
from .protocol import TC, DSCP_OF, PORT_OF, IP_UDP_OVERHEAD, HDR_LEN, FLAG_ALERT

OVER = IP_UDP_OVERHEAD + HDR_LEN            # 52 bytes of per-packet overhead
BE_PORTS = [80, 443, 5201, 8080]
BE_SIZES = [(1500, .70), (576, .20), (200, .10)]
BE_MEAN = sum(s * p for s, p in BE_SIZES)

FLOW_BASE = {"voice": 100, "video": 200, "emergency": 300, "best_effort": 400, "spoof": 500}


def _mark(pkt, rng, noise, cls_marked):
    """Set DSCP / port / QEP header according to the *claimed* class, with optional noise."""
    noise = noise or {}
    pkt.dscp = DSCP_OF[cls_marked]
    pkt.dport = PORT_OF[cls_marked]
    if rng.random() < noise.get("dscp_strip", 0.0):
        pkt.dscp = 0
    if rng.random() < noise.get("port_wrong", 0.0):
        pkt.dport = rng.randint(40000, 60000)
    pkt.hdr_cls = cls_marked if (cls_marked != TC.BEST_EFFORT and
                                 rng.random() < noise.get("hdr_prob", 1.0)) else None


def gen_voice(rng, calls, t0, t1, noise, payload=160, ptime=0.02):
    out = []
    for i in range(calls):
        t = t0 + rng.random() * ptime
        seq = 0
        while t < t1:
            p = Packet(FLOW_BASE["voice"] + i, seq, TC.VOICE, payload + OVER, t)
            _mark(p, rng, noise, TC.VOICE)
            out.append(p)
            seq += 1
            t += ptime
    return out


def gen_video(rng, streams, kbps_total, t0, t1, noise, fps=30, mtu_payload=1200):
    out = []
    if streams <= 0 or kbps_total <= 0:
        return out
    base = kbps_total / streams * 125.0 / fps / 1.1      # mean bytes / P-frame
    for i in range(streams):
        t = t0 + rng.random() / fps
        seq = fn = 0
        while t < t1:
            fsize = base * (4.0 if fn % fps == 0 else 1.0) * (0.8 + 0.4 * rng.random())
            k = max(1, int(fsize / mtu_payload + 0.999))
            for j in range(k):
                p = Packet(FLOW_BASE["video"] + i, seq, TC.VIDEO, mtu_payload + OVER, t + j * 1e-4)
                _mark(p, rng, noise, TC.VIDEO)
                out.append(p)
                seq += 1
            fn += 1
            t += 1.0 / fps
    return out


def gen_emergency(rng, sources, hb_pps, events, t0, t1, noise, payload=120):
    out = []
    for i in range(sources):
        flow = FLOW_BASE["emergency"] + i
        seq = 0
        t = t0 + rng.random() / max(hb_pps, 1e-9)
        times = []
        while hb_pps > 0 and t < t1:
            times.append((t, 0))
            t += 1.0 / hb_pps
        for (e0, dur, pps) in events:
            if pps <= 0:
                continue
            te = e0 + rng.random() / pps
            first = True
            while te < min(e0 + dur, t1):
                times.append((te, FLAG_ALERT if first else 0))
                first = False
                te += 1.0 / pps
        for (tt, fl) in sorted(times):
            p = Packet(flow, seq, TC.EMERGENCY, payload + OVER, tt)
            p.flags = fl
            _mark(p, rng, noise, TC.EMERGENCY)
            out.append(p)
            seq += 1
    return out


def gen_bulk(rng, kbps, t0, t1, flow, spoof=False, random_ports=True, mean_burst=6.0):
    """Bursty bulk data (TCP-like windows). spoof=True -> falsely marked as emergency."""
    out = []
    if kbps <= 0:
        return out
    pps = kbps * 125.0 / BE_MEAN
    burst_rate = pps / mean_burst
    t = t0 + rng.expovariate(burst_rate)
    seq = 0
    while t < t1:
        k = 1 + int(rng.expovariate(1.0 / (mean_burst - 1)))
        for j in range(k):
            r, acc, size = rng.random(), 0.0, BE_SIZES[-1][0]
            for s, pr in BE_SIZES:
                acc += pr
                if r <= acc:
                    size = s
                    break
            p = Packet(flow, seq, TC.BEST_EFFORT, size, t + j * 1e-4)
            if spoof:
                p.dscp, p.dport, p.hdr_cls = DSCP_OF[TC.EMERGENCY], PORT_OF[TC.EMERGENCY], TC.EMERGENCY
            else:
                p.dscp = 0
                p.dport = rng.choice(BE_PORTS) if random_ports else PORT_OF[TC.BEST_EFFORT]
                p.hdr_cls = None
            out.append(p)
            seq += 1
        t += rng.expovariate(burst_rate)
    return out


def generate(cfg, seed=1, only=None):
    """Build the packet list for a scenario config (sorted by arrival time)."""
    rng = random.Random(seed)
    d = cfg["duration"]
    noise = cfg.get("noise", {})
    want = lambda n: only is None or n in only
    pk = []
    if want("voice"):
        pk += gen_voice(rng, cfg.get("voice_calls", 0), 0.0, d, noise)
    if want("video"):
        pk += gen_video(rng, cfg.get("video_streams", 0), cfg.get("video_kbps", 0), 0.0, d, noise)
    if want("emergency"):
        pk += gen_emergency(rng, cfg.get("emerg_sources", 0), cfg.get("emerg_hb_pps", 0),
                            cfg.get("emerg_events", []), 0.0, d, noise)
    if want("best_effort"):
        pk += gen_bulk(rng, cfg.get("be_kbps", 0), 0.0, d, FLOW_BASE["best_effort"],
                       random_ports=cfg.get("be_random_ports", True))
    if want("spoof"):
        pk += gen_bulk(rng, cfg.get("spoof_kbps", 0), 0.0, d, FLOW_BASE["spoof"], spoof=True)
    pk.sort(key=lambda p: p.t_arrive)
    for i, p in enumerate(pk):
        p.id = i
    return pk
