"""Automated test suite: unit tests (protocol, classifier, schedulers, link) and
scenario tests TC1-TC10 with pass/fail assertions.   Run:  python3 -m unittest -v tests.test_qos"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from qos import protocol as P, scenarios, simulator
from qos.classifier import Classifier
from qos.packet import Packet
from qos.schedulers import make_scheduler, EPS
from qos.protocol import TC

EM, VO, VI, BE = TC.EMERGENCY, TC.VOICE, TC.VIDEO, TC.BEST_EFFORT


def mk(cls, size=1000, t=0.0, flow=1, seq=0):
    p = Packet(flow, seq, cls, size, t)
    p.cls = cls
    return p


# ----------------------------------------------------------------- protocol
class TestProtocol(unittest.TestCase):
    def test_header_size_is_24(self):
        self.assertEqual(P.HDR_LEN, 24)

    def test_roundtrip(self):
        h = P.pack_header(TC.EMERGENCY, 321, 99, 123456789012, 100, P.FLAG_ALERT)
        d = P.unpack_header(h)
        self.assertEqual((d["cls"], d["flow"], d["seq"], d["ts_ns"], d["flags"], d["dscp"]),
                         (TC.EMERGENCY, 321, 99, 123456789012, P.FLAG_ALERT, 48))

    def test_checksum_detects_corruption(self):
        h = bytearray(P.pack_header(TC.VOICE, 1, 1, 1, 1))
        h[9] ^= 0xFF
        with self.assertRaises(P.ProtocolError):
            P.unpack_header(bytes(h))

    def test_bad_magic_and_short(self):
        with self.assertRaises(P.ProtocolError):
            P.unpack_header(b"\x00" * 24)
        with self.assertRaises(P.ProtocolError):
            P.unpack_header(b"\x51\x45")

    def test_build_packet_total_size(self):
        pkt = P.build_packet(TC.VIDEO, 5, 6, 7, 1252)
        self.assertEqual(len(pkt) + P.IP_UDP_OVERHEAD, 1252)
        hdr, payload = P.parse_packet(pkt)
        self.assertEqual(len(payload), hdr["payload_len"])


# --------------------------------------------------------------- classifier
class TestClassifier(unittest.TestCase):
    def test_header_has_precedence(self):
        self.assertEqual(Classifier("full").classify(dscp=0, dport=5201, hdr_cls=0)[0], EM)

    def test_dscp_then_port_then_default(self):
        c = Classifier("full")
        self.assertEqual(c.classify(dscp=46, dport=1)[0:2], (VO, "dscp"))
        self.assertEqual(c.classify(dscp=0, dport=5006)[0:2], (VI, "port"))
        self.assertEqual(c.classify(dscp=0, dport=80)[0:2], (BE, "default"))

    def test_flow_cache(self):
        c = Classifier("full")
        c.classify(dscp=48, dport=5911, hdr_cls=0, flow=7)
        self.assertEqual(c.classify(dscp=0, dport=12345, flow=7), (EM, "cache"))
        s = Classifier("stateless")
        s.classify(dscp=48, flow=7)
        self.assertEqual(s.classify(dscp=0, dport=12345, flow=7)[0], BE)

    def test_ablation_accuracy_ordering(self):
        ab = scenarios.classifier_ablation(duration=6.0)
        self.assertGreater(ab["full"]["accuracy_pct"], 99.9)
        self.assertGreater(ab["full"]["accuracy_pct"], ab["dscp+port"]["accuracy_pct"])
        self.assertGreater(ab["dscp+port"]["accuracy_pct"], ab["dscp"]["accuracy_pct"])
        self.assertLess(ab["full"]["emergency_p99_ms"], 20)


# --------------------------------------------------------------- schedulers
class TestSchedulers(unittest.TestCase):
    LINK, BUF = 10e6, 100000

    def test_strict_priority_order(self):
        s = make_scheduler("pq", self.LINK, self.BUF)
        for c in (BE, VI, VO, EM):
            s.enqueue(mk(c, 200), 0)
        self.assertEqual([s.dequeue(0).cls for _ in range(4)], [EM, VO, VI, BE])

    def test_fifo_tail_drop(self):
        s = make_scheduler("fifo", self.LINK, 3000)
        drops = [len(s.enqueue(mk(EM, 1000), 0)) for _ in range(4)]
        self.assertEqual(drops, [0, 0, 0, 1])

    def _share(self, name, w):
        s = make_scheduler(name, self.LINK, 10 ** 9, weights=w, limit_frac={c: 1.0 for c in P.CLASSES})
        for i in range(3000):
            for c in (EM, BE):
                s.enqueue(mk(c, 1000), 0)
        served = {EM: 0, BE: 0}
        for _ in range(2000):
            served[s.dequeue(0).cls] += 1
        return served[EM] / served[BE]

    def test_wfq_weighted_share(self):
        r = self._share("wfq", {EM: 40, VO: 30, VI: 20, BE: 10})
        self.assertAlmostEqual(r, 4.0, delta=0.3)

    def test_drr_weighted_share(self):
        r = self._share("drr", {EM: 40, VO: 30, VI: 20, BE: 10})
        self.assertAlmostEqual(r, 4.0, delta=0.5)

    def test_eps_serves_emergency_first_then_voice(self):
        s = EPS(self.LINK, self.BUF)
        for c in (BE, VI, VO, EM):
            s.enqueue(mk(c, 200), 0.0)
        self.assertEqual([s.dequeue(0).cls for _ in range(4)][:2], [EM, VO])

    def test_eps_demotes_out_of_profile_emergency(self):
        s = EPS(self.LINK, 10 ** 7)
        demoted = 0
        for i in range(200):                      # 200 x 1000B at t=0 from ONE flow
            p = mk(EM, 1000, 0.0, flow=9, seq=i)
            s.enqueue(p, 0.0)
            demoted += p.demoted
        self.assertGreater(demoted, 150)          # per-flow burst is only 5000 B
        self.assertEqual(s.demotions, demoted)

    def test_eps_pushout_protects_emergency(self):
        s = EPS(self.LINK, 5000, be_cap_frac=1.0)
        for i in range(5):
            s.enqueue(mk(BE, 1000, 0.0), 0.0)
        p = mk(EM, 1000, 0.0, flow=2)
        drops = s.enqueue(p, 0.0)
        self.assertEqual([d.cls for d in drops], [BE])
        self.assertEqual(drops[0].status, "drop_pushout")
        self.assertIs(s.dequeue(0), p)

    def test_eps_never_pushes_out_higher_class(self):
        s = EPS(self.LINK, 2000)
        s.enqueue(mk(EM, 1000, flow=1), 0.0)
        s.enqueue(mk(EM, 1000, flow=2), 0.0)
        be = mk(BE, 1000)
        self.assertEqual(s.enqueue(be, 0.0), [be])
        self.assertEqual(be.status, "drop_queue")


# --------------------------------------------------------------------- link
class TestLink(unittest.TestCase):
    def test_plain_tx_time(self):
        l = simulator.Link(8e6, 0.0)
        self.assertAlmostEqual(l.finish_time(1.0, 8000), 1.001)

    def test_outage_pauses_transmission(self):
        l = simulator.Link(8e6, 0.0, profile=[(1.0, 2.0, 0.0)])
        self.assertAlmostEqual(l.finish_time(0.9995, 8000), 2.0005, places=6)

    def test_degradation_slows_transmission(self):
        l = simulator.Link(8e6, 0.0, profile=[(0.0, 10.0, 0.5)])
        self.assertAlmostEqual(l.finish_time(0.0, 8000), 0.002)


# ---------------------------------------------------------------- scenarios
_CACHE = {}


def R(sid):
    if sid not in _CACHE:
        _CACHE[sid] = scenarios.run_scenario(sid)["runs"]
    return _CACHE[sid]


def passes(run, cls):
    return run["sla"][cls]["pass"]


class TestScenarios(unittest.TestCase):
    def test_determinism(self):
        a = scenarios.run_scenario("tc2", ["eps"], seed=3, duration=5)["runs"]["eps"]["summary"]
        b = scenarios.run_scenario("tc2", ["eps"], seed=3, duration=5)["runs"]["eps"]["summary"]
        self.assertEqual(a, b)

    def test_tc1_normal_everyone_meets_sla(self):
        for s, run in R("tc1").items():
            for c in ("emergency", "voice", "video"):
                self.assertTrue(passes(run, c), "%s %s %s" % (s, c, run["sla"][c]))

    def test_tc2_congestion_fifo_fails_qos_schedulers_pass(self):
        r = R("tc2")
        self.assertFalse(passes(r["fifo"], "emergency"))
        self.assertFalse(passes(r["fifo"], "voice"))
        for s in ("pq", "wfq", "drr", "eps"):
            self.assertTrue(passes(r[s], "emergency") and passes(r[s], "voice"), s)
        self.assertGreater(r["fifo"]["summary"]["emergency"]["delay_p99_ms"],
                           10 * r["eps"]["summary"]["emergency"]["delay_p99_ms"])

    def test_tc3_surge(self):
        r = R("tc3")
        self.assertFalse(passes(r["fifo"], "emergency"))
        self.assertTrue(passes(r["eps"], "emergency"))
        self.assertEqual(r["eps"]["summary"]["emergency"]["loss_pct"], 0.0)

    def test_tc4_outage_eps_loses_no_emergency_and_recovers(self):
        r = R("tc4")
        self.assertEqual(r["eps"]["summary"]["emergency"]["loss_pct"], 0.0)
        self.assertGreater(r["fifo"]["summary"]["emergency"]["loss_pct"], 5.0)
        self.assertLess(r["eps"]["recovery_ms"], 200.0)
        self.assertGreater(r["fifo"]["recovery_ms"], r["eps"]["recovery_ms"])

    def test_tc5_degradation_priority_classes_survive(self):
        r = R("tc5")
        self.assertTrue(passes(r["eps"], "emergency") and passes(r["eps"], "voice"))
        self.assertFalse(passes(r["fifo"], "emergency"))
        self.assertLess(r["eps"]["recovery_ms"], 200.0)

    def test_tc6_spoofed_flood_eps_resists_pq_does_not(self):
        r = R("tc6")
        self.assertTrue(passes(r["eps"], "emergency") and passes(r["eps"], "voice"))
        self.assertFalse(passes(r["pq"], "emergency"))
        self.assertGreater(r["pq"]["summary"]["video"]["loss_pct"], 30.0)
        self.assertLess(r["eps"]["summary"]["video"]["loss_pct"], 1.0)
        self.assertGreater(r["eps"]["demotions"], 1000)

    def test_tc7_noisy_markings(self):
        r = R("tc7")
        self.assertTrue(passes(r["eps"], "emergency") and passes(r["eps"], "voice"))
        self.assertGreater(r["eps"]["classification_accuracy_pct"], 99.9)
        self.assertFalse(passes(r["fifo"], "emergency"))

    def test_tc8_starvation(self):
        r = R("tc8")
        self.assertLess(r["pq"]["summary"]["best_effort"]["throughput_kbps"], 100)
        self.assertGreater(r["eps"]["summary"]["best_effort"]["throughput_kbps"], 100)
        self.assertGreater(r["pq"]["summary"]["video"]["loss_pct"], 20)
        self.assertLess(r["eps"]["summary"]["video"]["loss_pct"], 1.0)
        self.assertTrue(passes(r["eps"], "emergency"))

    def test_tc9_lossy_link_delay_unaffected(self):
        e = R("tc9")["eps"]["summary"]
        for c in ("emergency", "voice", "video"):
            self.assertTrue(1.0 < e[c]["loss_pct"] < 3.5, (c, e[c]["loss_pct"]))
        self.assertLess(e["emergency"]["delay_p99_ms"], 10.0)

    def test_tc10_load_sweep(self):
        sw = scenarios.run_load_sweep(["fifo", "eps"], duration=6.0)
        self.assertTrue(all(v < 10.0 for v in sw["runs"]["eps"]["emergency_p99_ms"]))
        self.assertGreater(sw["runs"]["fifo"]["emergency_p99_ms"][-1], 100.0)
        self.assertLess(sw["runs"]["fifo"]["emergency_p99_ms"][0], 50.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
