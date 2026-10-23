"""Packet record shared by the simulator and the live router."""


class Packet:
    __slots__ = ("id", "flow", "seq", "true_cls", "cls", "qcls", "size",
                 "t_arrive", "t_depart", "t_recv", "status", "dscp", "dport",
                 "hdr_cls", "payload", "demoted", "flags", "_fin")

    def __init__(self, flow, seq, true_cls, size, t_arrive):
        self.id = 0
        self.flow = flow
        self.seq = seq
        self.true_cls = true_cls      # ground truth (for metrics only)
        self.cls = true_cls           # class assigned by the classifier
        self.qcls = None              # queue actually used (after policing)
        self.size = size              # IP-level bytes
        self.t_arrive = t_arrive
        self.t_depart = None
        self.t_recv = None
        self.status = None            # delivered | drop_queue | drop_pushout | drop_link | drop_outage | lost
        self.dscp = 0
        self.dport = 0
        self.hdr_cls = None
        self.payload = None
        self.demoted = False
        self.flags = 0
        self._fin = 0.0

    @property
    def delivered(self):
        return self.status == "delivered"
