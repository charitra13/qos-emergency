"""Multi-stage traffic classifier: QEP header -> DSCP -> port -> flow cache -> default.

The flow cache remembers the class of a flow once any of its packets was identified
by an explicit marking, so later packets whose markings were stripped/corrupted
are still classified correctly (like a router's flow table)."""
from .protocol import TC, CLASS_OF_DSCP, CLASS_OF_PORT


class Classifier:
    MODES = ("full", "stateless", "dscp", "dscp+port", "header")

    def __init__(self, mode="full", cache_size=65536):
        if mode not in self.MODES:
            raise ValueError("mode must be one of %s" % (self.MODES,))
        self.mode = mode
        self.use_header = mode in ("full", "stateless", "header")
        self.use_dscp = mode in ("full", "stateless", "dscp", "dscp+port")
        self.use_port = mode in ("full", "stateless", "dscp+port")
        self.use_cache = mode == "full"
        self.cache = {}
        self.cache_size = cache_size
        self.stats = {"header": 0, "dscp": 0, "port": 0, "cache": 0, "default": 0}

    def _remember(self, flow, cls):
        if self.use_cache and flow is not None and len(self.cache) < self.cache_size:
            self.cache[flow] = cls

    def classify(self, dscp=None, dport=None, hdr_cls=None, flow=None):
        if self.use_header and hdr_cls is not None:
            self.stats["header"] += 1
            cls = TC(hdr_cls)
            self._remember(flow, cls)
            return cls, "header"
        # DSCP 0 is ambiguous (best effort OR marking stripped) -> keep looking
        if self.use_dscp and dscp in CLASS_OF_DSCP:
            self.stats["dscp"] += 1
            cls = CLASS_OF_DSCP[dscp]
            self._remember(flow, cls)
            return cls, "dscp"
        if self.use_port and dport in CLASS_OF_PORT:
            self.stats["port"] += 1
            cls = CLASS_OF_PORT[dport]
            self._remember(flow, cls)
            return cls, "port"
        if self.use_cache and flow in self.cache:
            self.stats["cache"] += 1
            return self.cache[flow], "cache"
        self.stats["default"] += 1
        return TC.BEST_EFFORT, "default"

    def cache_hit_ratio(self):
        tot = sum(self.stats.values())
        return self.stats["cache"] / tot if tot else 0.0
