"""
QEP - QoS Emergency Protocol (application-layer header carried in UDP payload)

 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+---------------------------------------------------------------+
|        Magic (0x5145 'QE')    | Ver(4) | Class(4) |  Flags(8) |
+---------------------------------------------------------------+
|           Flow ID             |   DSCP (8)   |  Reserved (8)  |
+---------------------------------------------------------------+
|                      Sequence number (32)                     |
+---------------------------------------------------------------+
|                    Timestamp, ns since epoch (64)             |
|                                                               |
+---------------------------------------------------------------+
|        Payload length         |   Header checksum (16)        |
+---------------------------------------------------------------+
Total: 24 bytes.  Class: 0 emergency, 1 voice, 2 video, 3 best effort.
Flags: 0x01 ALERT (first packet of an emergency event), 0x02 RETX,
       0x04 LAST, 0x08 PREEMPT_REQUEST.
Checksum: RFC 1071 Internet checksum over the 24-byte header (field = 0).
"""
import struct
from enum import IntEnum

MAGIC = 0x5145
VERSION = 1
HDR_FMT = "!HBBHBBIQHH"
HDR_LEN = struct.calcsize(HDR_FMT)      # 24
IP_UDP_OVERHEAD = 28                    # 20 (IPv4) + 8 (UDP)

FLAG_ALERT, FLAG_RETX, FLAG_LAST, FLAG_PREEMPT = 0x01, 0x02, 0x04, 0x08


class TC(IntEnum):
    """Traffic class. Numeric value == strict priority (0 is highest)."""
    EMERGENCY = 0
    VOICE = 1
    VIDEO = 2
    BEST_EFFORT = 3


CLASSES = [TC.EMERGENCY, TC.VOICE, TC.VIDEO, TC.BEST_EFFORT]
CLASS_NAMES = {TC.EMERGENCY: "emergency", TC.VOICE: "voice",
               TC.VIDEO: "video", TC.BEST_EFFORT: "best_effort"}
NAME_TO_CLASS = {v: k for k, v in CLASS_NAMES.items()}

# DiffServ code points used by this project
DSCP_OF = {TC.EMERGENCY: 48,      # CS6
           TC.VOICE: 46,          # EF
           TC.VIDEO: 34,          # AF41
           TC.BEST_EFFORT: 0}     # BE
CLASS_OF_DSCP = {48: TC.EMERGENCY, 46: TC.VOICE,
                 34: TC.VIDEO, 36: TC.VIDEO, 38: TC.VIDEO}

PORT_OF = {TC.EMERGENCY: 5911, TC.VOICE: 5004,
           TC.VIDEO: 5006, TC.BEST_EFFORT: 5201}
CLASS_OF_PORT = {v: k for k, v in PORT_OF.items()}


class ProtocolError(ValueError):
    pass


def checksum16(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    s = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF


def pack_header(cls, flow_id, seq, ts_ns, payload_len, flags=0, dscp=None):
    if dscp is None:
        dscp = DSCP_OF[TC(cls)]
    raw = struct.pack(HDR_FMT, MAGIC, (VERSION << 4) | int(cls), flags & 0xFF,
                      flow_id & 0xFFFF, dscp & 0xFF, 0, seq & 0xFFFFFFFF,
                      ts_ns, payload_len & 0xFFFF, 0)
    return raw[:-2] + struct.pack("!H", checksum16(raw))


def unpack_header(buf: bytes) -> dict:
    if len(buf) < HDR_LEN:
        raise ProtocolError("short header")
    magic, vc, flags, flow, dscp, _rsv, seq, ts, plen, csum = \
        struct.unpack(HDR_FMT, buf[:HDR_LEN])
    if magic != MAGIC:
        raise ProtocolError("bad magic")
    if vc >> 4 != VERSION:
        raise ProtocolError("unsupported version")
    if (vc & 0xF) > 3:
        raise ProtocolError("bad class")
    if checksum16(buf[:HDR_LEN - 2] + b"\x00\x00") != csum:
        raise ProtocolError("bad checksum")
    return dict(cls=TC(vc & 0xF), flags=flags, flow=flow, dscp=dscp,
                seq=seq, ts_ns=ts, payload_len=plen)


def build_packet(cls, flow_id, seq, ts_ns, total_size, flags=0, dscp=None):
    """Build a UDP payload so that IP packet length == total_size."""
    filler = max(0, total_size - IP_UDP_OVERHEAD - HDR_LEN)
    return pack_header(cls, flow_id, seq, ts_ns, filler, flags, dscp) + bytes(filler)


def parse_packet(buf: bytes):
    hdr = unpack_header(buf)
    return hdr, buf[HDR_LEN:]
