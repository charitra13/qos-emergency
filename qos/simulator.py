"""Discrete-event simulation of one congested bottleneck link."""
import math
import random
from .classifier import Classifier
from .schedulers import make_scheduler
from . import traffic, metrics

INF = float("inf")


class Link:
    """Bottleneck link with propagation delay, random loss and a capacity profile.
    profile: list of (t0, t1, factor); factor 0 = outage, 0.3 = 30 % capacity."""

    def __init__(self, rate_bps, prop_delay, loss_prob=0.0, profile=None, seed=7):
        self.rate = rate_bps
        self.prop = prop_delay
        self.loss_prob = loss_prob
        self.profile = list(profile or [])
        self.rng = random.Random(seed)
        self.bounds = sorted({b for seg in self.profile for b in seg[:2]})

    def factor(self, t):
        f = 1.0
        for t0, t1, k in self.profile:
            if t0 <= t < t1:
                f = min(f, k)
        return f

    def _next_bound(self, t):
        for b in self.bounds:
            if b > t:
                return b
        return INF

    def finish_time(self, start, bits):
        t, rem = start, float(bits)
        while rem > 1e-9:
            f, nxt = self.factor(t), self._next_bound(t)
            if f <= 0:
                if nxt == INF:
                    return INF
                t = nxt
                continue
            r = self.rate * f
            cap = (nxt - t) * r
            if cap >= rem:
                return t + rem / r
            rem -= cap
            t = nxt
        return t

    def lost(self):
        return self.loss_prob > 0 and self.rng.random() < self.loss_prob


def run(cfg, sched_name, seed=1):
    pkts = traffic.generate(cfg, seed)
    clf = Classifier(cfg.get("classifier", "full"))
    correct = 0
    for p in pkts:
        p.cls, _ = clf.classify(p.dscp, p.dport, p.hdr_cls, p.flow)
        correct += (p.cls == p.true_cls)
    link = Link(cfg["link_bps"], cfg["prop_delay"], cfg.get("loss_prob", 0.0),
                cfg.get("profile"), seed + 1000)
    sched = make_scheduler(sched_name, cfg["link_bps"], cfg["buffer_bytes"], **cfg.get("sched_opts", {}))

    now, i, N = 0.0, 0, len(pkts)
    dead = False
    while True:
        while i < N and pkts[i].t_arrive <= now:
            sched.enqueue(pkts[i], pkts[i].t_arrive)
            i += 1
        p = sched.dequeue(now)
        if p is None:
            if i >= N:
                break
            now = pkts[i].t_arrive
            continue
        fin = link.finish_time(now, p.size * 8)
        if fin == INF:
            p.status = "drop_outage"
            dead = True
            break
        now = fin
        if link.lost():
            p.status = "drop_link"
        else:
            p.status = "delivered"
            p.t_depart = fin
            p.t_recv = fin + link.prop
    if dead:        # permanent outage: everything left is lost
        while True:
            q = sched.dequeue(now)
            if q is None:
                break
            q.status = "drop_outage"
        for q in pkts[i:]:
            q.status = "drop_outage"

    summary = metrics.summarize(pkts, cfg["duration"])
    return {
        "packets": pkts,
        "summary": summary,
        "sla": metrics.sla_check(summary),
        "classification_accuracy_pct": round(100.0 * correct / max(1, N), 3),
        "demotions": getattr(sched, "demotions", 0),
        "classifier_stats": dict(clf.stats),
        "cache_hit_ratio_pct": round(100.0 * clf.cache_hit_ratio(), 3),
    }
