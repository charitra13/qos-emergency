"""Test-case catalogue (TC1..TC10) and the runner that produces JSON-able results."""
import copy
from . import simulator, metrics
from .protocol import TC, CLASS_NAMES

SCHED_ORDER = ["fifo", "pq", "wfq", "drr", "eps"]

BASE = dict(
    duration=20.0, link_bps=10e6, prop_delay=0.005, buffer_bytes=125000,
    loss_prob=0.0, profile=[],
    voice_calls=20, video_streams=3, video_kbps=3000,
    emerg_sources=10, emerg_hb_pps=10, emerg_events=[(5.0, 3.0, 40)],
    be_kbps=2000, spoof_kbps=0, noise={}, classifier="full", sched_opts={},
)


def _cfg(**kw):
    c = copy.deepcopy(BASE)
    c.update(kw)
    return c


SCENARIOS = {
    "tc1": dict(title="TC1 - Normal load (~70 %)",
                desc="Baseline: link is not congested. Every scheduler should meet all SLAs.",
                cfg=_cfg()),
    "tc2": dict(title="TC2 - Heavy congestion (~170 % offered load)",
                desc="Bulk traffic overloads the 10 Mbps bottleneck. FIFO must fail emergency/voice SLAs.",
                cfg=_cfg(be_kbps=12000)),
    "tc3": dict(title="TC3 - Disaster surge: emergency burst during congestion",
                desc="20 emergency sources raise 60 pps each for 6 s while bulk traffic saturates the link.",
                cfg=_cfg(be_kbps=10000, emerg_sources=20, emerg_hb_pps=5, emerg_events=[(6.0, 6.0, 60)])),
    "tc4": dict(title="TC4 - Failure: 2 s link outage and recovery",
                desc="Link goes down 8-10 s with an emergency event in progress. Measures loss and recovery time.",
                cfg=_cfg(be_kbps=4000, emerg_events=[(7.0, 5.0, 20)], profile=[(8.0, 10.0, 0.0)]),
                failure=(10.0, "emergency", 100.0)),
    "tc5": dict(title="TC5 - Failure: capacity degradation to 35 % (6-14 s)",
                desc="E.g. microwave link fade / backup link. Priority classes must survive, video degrades.",
                cfg=_cfg(be_kbps=4000, profile=[(6.0, 14.0, 0.35)]),
                failure=(14.0, "emergency", 100.0)),
    "tc6": dict(title="TC6 - Attack: bulk flow falsely marked as emergency (8 Mbps)",
                desc="Spoofed DSCP-48 / QEP class-0 flood. Strict priority collapses; policed EPS must hold.",
                cfg=_cfg(be_kbps=2000, spoof_kbps=8000)),
    "tc7": dict(title="TC7 - Noisy markings (DSCP stripped 25 %, wrong port 10 %, header on 80 %)",
                desc="Classifier robustness under congestion; compare classifier ablation (accuracy).",
                cfg=_cfg(be_kbps=12000, noise=dict(dscp_strip=0.25, port_wrong=0.10, hdr_prob=0.80))),
    "tc8": dict(title="TC8 - Starvation test: voice over-subscription (90 calls)",
                desc="Strict priority starves video/bulk completely; EPS bounds voice to its reservation.",
                cfg=_cfg(voice_calls=90, be_kbps=4000)),
    "tc9": dict(title="TC9 - Lossy link (2 % random loss, moderate load)",
                desc="Isolates link loss from congestion loss; delay must be unaffected.",
                cfg=_cfg(be_kbps=4000, loss_prob=0.02)),
}

SWEEP_LOADS_KBPS = [1000, 3000, 5000, 7000, 9000, 11000, 13000, 15000]


def run_scenario(sid, schedulers=None, seed=1, duration=None, keep_packets=False):
    spec = SCENARIOS[sid]
    cfg = copy.deepcopy(spec["cfg"])
    if duration:
        cfg["duration"] = duration
    out = {"id": sid, "title": spec["title"], "desc": spec["desc"], "runs": {}}
    for s in (schedulers or SCHED_ORDER):
        r = simulator.run(cfg, s, seed)
        run = {"summary": r["summary"], "sla": r["sla"],
               "classification_accuracy_pct": r["classification_accuracy_pct"],
               "demotions": r["demotions"],
               "cache_hit_ratio_pct": r["cache_hit_ratio_pct"],
               "timeline": {n: metrics.delay_timeline(r["packets"], c)
                            for c, n in CLASS_NAMES.items() if c in (TC.EMERGENCY, TC.VOICE)}}
        if "failure" in spec:
            t_end, cname, thr = spec["failure"]
            cls = [c for c, n in CLASS_NAMES.items() if n == cname][0]
            run["recovery_ms"] = metrics.recovery_time_ms(r["packets"], cls, t_end, thr)
        if keep_packets:
            run["_packets"] = r["packets"]
        out["runs"][s] = run
    return out


def run_load_sweep(schedulers=None, seed=1, duration=10.0):
    res = {"loads_kbps": SWEEP_LOADS_KBPS, "runs": {}}
    for s in (schedulers or SCHED_ORDER):
        em, vo, thr = [], [], []
        for be in SWEEP_LOADS_KBPS:
            cfg = _cfg(duration=duration, be_kbps=be, emerg_events=[(3.0, 3.0, 40)])
            r = simulator.run(cfg, s, seed)
            em.append(r["summary"]["emergency"]["delay_p99_ms"])
            vo.append(r["summary"]["voice"]["delay_p99_ms"])
            thr.append(r["summary"]["best_effort"]["throughput_kbps"])
        res["runs"][s] = {"emergency_p99_ms": em, "voice_p99_ms": vo, "be_throughput_kbps": thr}
    return res


def classifier_ablation(seed=1, duration=10.0):
    """Classification accuracy (%) per classifier mode under noisy markings."""
    out = {}
    for mode in ("dscp", "dscp+port", "header", "stateless", "full"):
        cfg = _cfg(duration=duration, be_kbps=12000, classifier=mode,
                   noise=dict(dscp_strip=0.25, port_wrong=0.10, hdr_prob=0.80))
        r = simulator.run(cfg, "eps", seed)
        out[mode] = {"accuracy_pct": r["classification_accuracy_pct"],
                     "cache_hit_ratio_pct": r["cache_hit_ratio_pct"],
                     "emergency_p99_ms": r["summary"]["emergency"]["delay_p99_ms"],
                     "emergency_loss_pct": r["summary"]["emergency"]["loss_pct"]}
    return out
