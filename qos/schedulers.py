"""
Packet schedulers for a single congested egress port.

Common interface
    enqueue(pkt, now) -> list[Packet]   packets dropped by this call (may be [])
    dequeue(now)      -> Packet | None
Dropped packets get pkt.status set by the scheduler.

fifo : single tail-drop queue (no QoS) - baseline
pq   : strict priority, per-class buffers (can starve low classes)
wfq  : Self-Clocked Fair Queueing (a practical WFQ), per-class buffers
drr  : Deficit Round Robin, per-class buffers
eps  : Emergency Priority Scheduler (proposed hybrid, LLQ-style):
         tier 1 strict emergency  (token-bucket policed)
         tier 2 strict voice      (token-bucket policed)
         tier 3 WFQ video : best-effort
       out-of-profile packets are re-marked to best effort (anti-abuse),
       shared buffer with push-out so high classes never lose to bulk traffic.
"""
from collections import deque
from .protocol import TC, CLASSES

EM, VO, VI, BE = TC.EMERGENCY, TC.VOICE, TC.VIDEO, TC.BEST_EFFORT

DEFAULT_WEIGHTS = {EM: 40, VO: 30, VI: 20, BE: 10}
DEFAULT_LIMIT_FRAC = {EM: .15, VO: .25, VI: .30, BE: .30}


class Scheduler:
    name = "base"
    label = "base"

    def __init__(self, link_bps, buffer_bytes, **kw):
        self.link_bps = link_bps
        self.buffer = buffer_bytes
        self.q = {c: deque() for c in CLASSES}
        self.qb = {c: 0 for c in CLASSES}
        self.n = 0
        self.bytes = 0

    def __len__(self):
        return self.n

    def _push(self, pkt, c):
        self.q[c].append(pkt)
        self.qb[c] += pkt.size
        self.n += 1
        self.bytes += pkt.size

    def _pop(self, c):
        p = self.q[c].popleft()
        self.qb[c] -= p.size
        self.n -= 1
        self.bytes -= p.size
        return p

    def _pop_tail(self, c):
        p = self.q[c].pop()
        self.qb[c] -= p.size
        self.n -= 1
        self.bytes -= p.size
        return p

    @staticmethod
    def _drop(pkt, status="drop_queue"):
        pkt.status = status
        return [pkt]

    def _class_limits(self, frac=None):
        frac = frac or DEFAULT_LIMIT_FRAC
        return {c: int(self.buffer * frac[c]) for c in CLASSES}


class FIFO(Scheduler):
    name, label = "fifo", "FIFO (no QoS)"

    def enqueue(self, pkt, now):
        pkt.qcls = pkt.cls
        if self.bytes + pkt.size > self.buffer:
            return self._drop(pkt)
        self._push(pkt, BE)          # single logical queue
        return []

    def dequeue(self, now):
        return self._pop(BE) if self.q[BE] else None


class StrictPriority(Scheduler):
    name, label = "pq", "Strict Priority"

    def __init__(self, link_bps, buffer_bytes, **kw):
        super().__init__(link_bps, buffer_bytes)
        self.limit = self._class_limits(kw.get("limit_frac"))

    def enqueue(self, pkt, now):
        c = pkt.qcls = pkt.cls
        if self.qb[c] + pkt.size > self.limit[c]:
            return self._drop(pkt)
        self._push(pkt, c)
        return []

    def dequeue(self, now):
        for c in CLASSES:
            if self.q[c]:
                return self._pop(c)
        return None


class WFQ(Scheduler):
    """Self-Clocked Fair Queueing: finish tag = max(V, last_finish) + size/weight."""
    name, label = "wfq", "WFQ"

    def __init__(self, link_bps, buffer_bytes, **kw):
        super().__init__(link_bps, buffer_bytes)
        self.w = dict(kw.get("weights") or DEFAULT_WEIGHTS)
        self.limit = self._class_limits(kw.get("limit_frac"))
        self.vtime = 0.0
        self.last_fin = {c: 0.0 for c in CLASSES}

    def enqueue(self, pkt, now):
        c = pkt.qcls = pkt.cls
        if self.qb[c] + pkt.size > self.limit[c]:
            return self._drop(pkt)
        start = max(self.vtime, self.last_fin[c])
        pkt._fin = start + pkt.size / self.w[c]
        self.last_fin[c] = pkt._fin
        self._push(pkt, c)
        return []

    def dequeue(self, now):
        best = None
        for c in CLASSES:
            if self.q[c] and (best is None or self.q[c][0]._fin < self.q[best][0]._fin):
                best = c
        if best is None:
            return None
        p = self._pop(best)
        self.vtime = p._fin
        return p


class DRR(Scheduler):
    name, label = "drr", "DRR"

    def __init__(self, link_bps, buffer_bytes, **kw):
        super().__init__(link_bps, buffer_bytes)
        w = dict(kw.get("weights") or DEFAULT_WEIGHTS)
        mn = min(w.values())
        self.quantum = {c: 1500.0 * w[c] / mn for c in CLASSES}
        self.limit = self._class_limits(kw.get("limit_frac"))
        self.deficit = {c: 0.0 for c in CLASSES}
        self.fresh = {c: False for c in CLASSES}
        self.ptr = 0

    def enqueue(self, pkt, now):
        c = pkt.qcls = pkt.cls
        if self.qb[c] + pkt.size > self.limit[c]:
            return self._drop(pkt)
        self._push(pkt, c)
        return []

    def _advance(self):
        self.ptr = (self.ptr + 1) % len(CLASSES)

    def dequeue(self, now):
        if not self.n:
            return None
        while True:
            c = CLASSES[self.ptr]
            q = self.q[c]
            if not q:
                self.deficit[c] = 0.0
                self.fresh[c] = False
                self._advance()
                continue
            if not self.fresh[c]:
                self.deficit[c] += self.quantum[c]
                self.fresh[c] = True
            if q[0].size <= self.deficit[c]:
                p = self._pop(c)
                self.deficit[c] -= p.size
                if not q:
                    self.deficit[c] = 0.0
                    self.fresh[c] = False
                    self._advance()
                return p
            self.fresh[c] = False
            self._advance()


class TokenBucket:
    def __init__(self, rate_bps, burst_bytes):
        self.rate = rate_bps / 8.0
        self.burst = float(burst_bytes)
        self.tokens = float(burst_bytes)
        self.last = 0.0

    def conform(self, size, now):
        self.tokens = min(self.burst, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= size:
            self.tokens -= size
            return True
        return False


class EPS(Scheduler):
    """Emergency Priority Scheduler.

    Admission to the strict tiers requires conforming to BOTH a per-flow token bucket
    (stops one spoofed/misbehaving source from consuming the reservation) AND an
    aggregate token bucket (caps the whole class). Out-of-profile packets are
    re-marked to best effort instead of being dropped."""
    name, label = "eps", "EPS (proposed hybrid)"

    def __init__(self, link_bps, buffer_bytes, **kw):
        super().__init__(link_bps, buffer_bytes)
        self.tb = {
            EM: TokenBucket(link_bps * kw.get("em_rate_frac", 0.20), kw.get("em_burst", 10000)),
            VO: TokenBucket(link_bps * kw.get("voice_rate_frac", 0.35), kw.get("voice_burst", 15000)),
        }
        # per-flow profile: (rate bps, burst bytes); None disables per-flow policing
        self.flow_prof = {EM: kw.get("em_flow", (150e3, 5000)),
                          VO: kw.get("voice_flow", (128e3, 3000))}
        self.flow_tb = {EM: {}, VO: {}}
        self.w = {VI: kw.get("video_weight", 6), BE: kw.get("be_weight", 4)}
        self.cap = {EM: buffer_bytes, VO: int(buffer_bytes * 0.5),
                    VI: int(buffer_bytes * kw.get("video_cap_frac", 0.4)),
                    BE: int(buffer_bytes * kw.get("be_cap_frac", 0.5))}
        self.vtime = 0.0
        self.last_fin = {VI: 0.0, BE: 0.0}
        self.demotions = 0

    def _police(self, pkt, c, now):
        prof = self.flow_prof.get(c)
        if prof:
            tb = self.flow_tb[c].get(pkt.flow)
            if tb is None:
                tb = self.flow_tb[c][pkt.flow] = TokenBucket(prof[0], prof[1])
                tb.last = now
            if not tb.conform(pkt.size, now):
                return False
        return self.tb[c].conform(pkt.size, now)

    def enqueue(self, pkt, now):
        c = pkt.cls
        if c in self.tb and not self._police(pkt, c, now):
            c = BE                       # out-of-profile -> re-mark to best effort
            pkt.demoted = True
            self.demotions += 1
        pkt.qcls = c
        if self.qb[c] + pkt.size > self.cap[c]:
            return self._drop(pkt)
        drops = []
        if self.bytes + pkt.size > self.buffer:
            need = self.bytes + pkt.size - self.buffer
            if sum(self.qb[v] for v in CLASSES if v > c) < need:
                return self._drop(pkt)
            for v in reversed(CLASSES):  # push out lowest-priority tail first
                if v <= c:
                    break
                while need > 0 and self.q[v]:
                    vp = self._pop_tail(v)
                    need -= vp.size
                    vp.status = "drop_pushout"
                    drops.append(vp)
        if c in (VI, BE):
            pkt._fin = max(self.vtime, self.last_fin[c]) + pkt.size / self.w[c]
            self.last_fin[c] = pkt._fin
        self._push(pkt, c)
        return drops

    def dequeue(self, now):
        if self.q[EM]:
            return self._pop(EM)
        if self.q[VO]:
            return self._pop(VO)
        cand = [c for c in (VI, BE) if self.q[c]]
        if not cand:
            return None
        best = min(cand, key=lambda c: self.q[c][0]._fin)
        p = self._pop(best)
        self.vtime = p._fin
        return p


SCHEDULERS = {"fifo": FIFO, "pq": StrictPriority, "wfq": WFQ, "drr": DRR, "eps": EPS}


def make_scheduler(name, link_bps, buffer_bytes, **kw):
    try:
        return SCHEDULERS[name](link_bps, buffer_bytes, **kw)
    except KeyError:
        raise ValueError("unknown scheduler %r (choose from %s)" % (name, sorted(SCHEDULERS)))
