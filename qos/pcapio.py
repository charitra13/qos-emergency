"""Minimal pcap writer/reader so results can be verified in Wireshark (no dependencies).

Simulated packets are written as Ethernet/IPv4/UDP frames carrying the QEP header,
timestamped at their *departure* from the bottleneck link. The QEP timestamp field holds the
arrival time at the bottleneck, so (pcap time - QEP ts) == queueing + transmission delay."""
import struct
from .protocol import TC, DSCP_OF, PORT_OF, IP_UDP_OVERHEAD, HDR_LEN, build_packet, checksum16

BASE_EPOCH = 1_700_000_000          # arbitrary epoch offset used for simulated captures
SRC_IP = {TC.EMERGENCY: "10.0.1.3", TC.VOICE: "10.0.1.1", TC.VIDEO: "10.0.1.2", TC.BEST_EFFORT: "10.0.1.4"}
DST_IP = "10.0.2.2"


def _ip(s):
    return bytes(int(x) for x in s.split("."))


def build_frame(pkt):
    qep_cls = pkt.hdr_cls if pkt.hdr_cls is not None else pkt.true_cls
    ts_ns = int((BASE_EPOCH + pkt.t_arrive) * 1e9)
    l7 = build_packet(qep_cls, pkt.flow, pkt.seq, ts_ns, pkt.size, pkt.flags, pkt.dscp)   # QEP always embedded so analysis works
    udp_len = 8 + len(l7)
    udp = struct.pack("!HHHH", 40000 + pkt.flow % 1000, pkt.dport, udp_len, 0)
    total = 20 + udp_len
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, (pkt.dscp << 2) & 0xFF, total, pkt.id & 0xFFFF,
                     0x4000, 63, 17, 0, _ip(SRC_IP[pkt.true_cls]), _ip(DST_IP))
    ip = ip[:10] + struct.pack("!H", checksum16(ip)) + ip[12:]
    eth = bytes.fromhex("000000000002") + bytes.fromhex("000000000001") + b"\x08\x00"
    return eth + ip + udp + l7


def write_pcap(path, packets, limit=None):
    sel = sorted((p for p in packets if p.delivered), key=lambda p: p.t_depart)
    if limit:
        sel = sel[:limit]
    with open(path, "wb") as f:
        f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for p in sel:
            fr = build_frame(p)
            t = BASE_EPOCH + p.t_depart
            f.write(struct.pack("<IIII", int(t), int((t % 1) * 1e6), len(fr), len(fr)))
            f.write(fr)
    return len(sel)


def read_pcap(path):
    """Yield (timestamp_seconds, linktype, raw_bytes). Supports classic pcap (us/ns, LE/BE)."""
    with open(path, "rb") as f:
        gh = f.read(24)
        magic = gh[:4]
        if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
            e = "<"
        elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
            e = ">"
        else:
            raise ValueError("not a classic pcap file (pcapng is not supported - save as pcap)")
        nano = magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
        link = struct.unpack(e + "I", gh[20:24])[0]
        while True:
            rh = f.read(16)
            if len(rh) < 16:
                return
            sec, frac, incl, _orig = struct.unpack(e + "IIII", rh)
            yield sec + frac / (1e9 if nano else 1e6), link, f.read(incl)


def decode_udp(link, raw):
    """Return (dscp, sport, dport, udp_payload) for IPv4/UDP frames, else None."""
    if link == 1:
        if raw[12:14] != b"\x08\x00":
            return None
        raw = raw[14:]
    elif link == 0:                     # BSD loopback (macOS / Windows npcap loopback)
        raw = raw[4:]
    elif link == 113:                   # Linux cooked
        raw = raw[16:]
    elif link == 101:
        pass
    else:
        return None
    if len(raw) < 28 or raw[0] >> 4 != 4 or raw[9] != 17:
        return None
    ihl = (raw[0] & 0xF) * 4
    sport, dport, _ln, _ck = struct.unpack("!HHHH", raw[ihl:ihl + 8])
    return raw[1] >> 2, sport, dport, raw[ihl + 8:]
