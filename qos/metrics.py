"""Metrics: delay, jitter, loss, throughput, SLA verdicts, recovery time."""
import math
from .protocol import CLASSES, CLASS_NAMES

SLA = {
    "emergency": {"delay_p99_ms": 50.0, "loss_pct": 0.1},
    "voice": {"delay_p99_ms": 150.0, "jitter_ms": 30.0, "loss_pct": 1.0},
    "video": {"delay_p99_ms": 300.0, "loss_pct": 2.0},
    "best_effort": {},
}


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    k = min(len(sorted_vals) - 1, max(0, int(math.ceil(p / 100.0 * len(sorted_vals))) - 1))
    return sorted_vals[k]


def _jitter(pkts):
    """Mean |D(i-1,i)| of one-way delay between consecutive packets of the same flow (ms)."""
    flows = {}
    for p in pkts:
        if p.delivered:
            flows.setdefault(p.flow, []).append(p)
    tot, n = 0.0, 0
    for lst in flows.values():
        lst.sort(key=lambda p: p.seq)
        prev = None
        for p in lst:
            d = p.t_recv - p.t_arrive
            if prev is not None:
                tot += abs(d - prev)
                n += 1
            prev = d
    return 1000.0 * tot / n if n else 0.0


def summarize(pkts, duration):
    out = {}
    for c in CLASSES:
        name = CLASS_NAMES[c]
        sel = [p for p in pkts if p.true_cls == c]
        deliv = [p for p in sel if p.delivered]
        delays = sorted((p.t_recv - p.t_arrive) * 1000.0 for p in deliv)
        sent = len(sel)
        qd = sum(1 for p in sel if p.status in ("drop_queue", "drop_pushout"))
        ld = sum(1 for p in sel if p.status in ("drop_link", "drop_outage"))
        lost_other = sum(1 for p in sel if p.status in (None, "lost"))
        lost = sent - len(deliv)
        out[name] = {
            "sent": sent, "delivered": len(deliv), "lost": lost,
            "queue_drops": qd, "link_drops": ld + lost_other,
            "demoted": sum(1 for p in sel if p.demoted),
            "loss_pct": round(100.0 * lost / sent, 3) if sent else 0.0,
            "delay_avg_ms": round(sum(delays) / len(delays), 3) if delays else 0.0,
            "delay_p50_ms": round(percentile(delays, 50), 3),
            "delay_p95_ms": round(percentile(delays, 95), 3),
            "delay_p99_ms": round(percentile(delays, 99), 3),
            "delay_max_ms": round(delays[-1], 3) if delays else 0.0,
            "jitter_ms": round(_jitter(sel), 3),
            "offered_kbps": round(sum(p.size for p in sel) * 8 / duration / 1000.0, 1),
            "throughput_kbps": round(sum(p.size for p in deliv) * 8 / duration / 1000.0, 1),
        }
    return out


def sla_check(summary, sla=None):
    sla = sla or SLA
    res = {}
    for name, lim in sla.items():
        s = summary[name]
        viol = []
        if s["sent"] == 0:
            res[name] = {"pass": True, "violations": [], "n/a": True}
            continue
        for key, bound in lim.items():
            if s[key] > bound:
                viol.append("%s=%.2f > %.2f" % (key, s[key], bound))
        res[name] = {"pass": not viol, "violations": viol}
    return res


def delay_timeline(pkts, cls, bucket=0.25):
    acc = {}
    for p in pkts:
        if p.true_cls == cls and p.delivered:
            b = int(p.t_arrive / bucket)
            acc.setdefault(b, []).append((p.t_recv - p.t_arrive) * 1000.0)
    return [(round(b * bucket, 3), round(sum(v) / len(v), 3)) for b, v in sorted(acc.items())]


def recovery_time_ms(pkts, cls, t_end, thr_ms):
    """Time after t_end until the last packet of class that violated thr_ms (lost counts as violation)."""
    last = None
    for p in pkts:
        if p.true_cls != cls or p.t_arrive < t_end:
            continue
        bad = (not p.delivered) or (p.t_recv - p.t_arrive) * 1000.0 > thr_ms
        if bad and (last is None or p.t_arrive > last):
            last = p.t_arrive
    return 0.0 if last is None else round((last - t_end) * 1000.0, 1)
