-- Wireshark Lua dissector for the QEP (QoS Emergency Protocol) header.
-- Install: copy to ~/.local/lib/wireshark/plugins/ (Linux) or  %APPDATA%\Wireshark\plugins\ (Windows)
-- or run:  wireshark -X lua_script:docs/qep_dissector.lua capture.pcap
-- Useful display filters:  qep   |  qep.cls == 0   |  qep.flags.alert == 1  |  ip.dsfield.dscp == 48
local qep = Proto("qep", "QoS Emergency Protocol")
local classes = { [0] = "Emergency", [1] = "Voice", [2] = "Video", [3] = "Best effort" }

local f_magic = ProtoField.uint16("qep.magic", "Magic", base.HEX)
local f_ver   = ProtoField.uint8("qep.version", "Version", base.DEC, nil, 0xF0)
local f_cls   = ProtoField.uint8("qep.cls", "Class", base.DEC, classes, 0x0F)
local f_flags = ProtoField.uint8("qep.flags", "Flags", base.HEX)
local f_alert = ProtoField.bool("qep.flags.alert", "ALERT", 8, nil, 0x01)
local f_retx  = ProtoField.bool("qep.flags.retx", "RETX", 8, nil, 0x02)
local f_last  = ProtoField.bool("qep.flags.last", "LAST", 8, nil, 0x04)
local f_pre   = ProtoField.bool("qep.flags.preempt", "PREEMPT", 8, nil, 0x08)
local f_flow  = ProtoField.uint16("qep.flow", "Flow ID", base.DEC)
local f_dscp  = ProtoField.uint8("qep.dscp", "DSCP", base.DEC)
local f_rsv   = ProtoField.uint8("qep.rsv", "Reserved", base.HEX)
local f_seq   = ProtoField.uint32("qep.seq", "Sequence", base.DEC)
local f_ts    = ProtoField.uint64("qep.ts_ns", "Timestamp (ns)", base.DEC)
local f_plen  = ProtoField.uint16("qep.payload_len", "Payload length", base.DEC)
local f_csum  = ProtoField.uint16("qep.checksum", "Header checksum", base.HEX)
qep.fields = { f_magic, f_ver, f_cls, f_flags, f_alert, f_retx, f_last, f_pre,
               f_flow, f_dscp, f_rsv, f_seq, f_ts, f_plen, f_csum }

function qep.dissector(buf, pinfo, tree)
  if buf:len() < 24 or buf(0, 2):uint() ~= 0x5145 then return 0 end
  pinfo.cols.protocol = "QEP"
  local t = tree:add(qep, buf(0, 24))
  t:add(f_magic, buf(0, 2))
  t:add(f_ver, buf(2, 1))
  t:add(f_cls, buf(2, 1))
  local ft = t:add(f_flags, buf(3, 1))
  ft:add(f_alert, buf(3, 1)); ft:add(f_retx, buf(3, 1)); ft:add(f_last, buf(3, 1)); ft:add(f_pre, buf(3, 1))
  t:add(f_flow, buf(4, 2)); t:add(f_dscp, buf(6, 1)); t:add(f_rsv, buf(7, 1))
  t:add(f_seq, buf(8, 4)); t:add(f_ts, buf(12, 8))
  t:add(f_plen, buf(20, 2)); t:add(f_csum, buf(22, 2))
  pinfo.cols.info = string.format("QEP %s flow=%d seq=%d",
                    classes[buf(2, 1):uint() % 16] or "?", buf(4, 2):uint(), buf(8, 4):uint())
  return 24
end

local udp_table = DissectorTable.get("udp.port")
for _, p in ipairs({ 5004, 5006, 5911, 5201, 6004, 6006, 6911, 6201 }) do udp_table:add(p, qep) end
-- heuristic fallback for any other UDP port
local function heur(buf, pinfo, tree)
  if buf:len() >= 24 and buf(0, 2):uint() == 0x5145 then qep.dissector(buf, pinfo, tree); return true end
  return false
end
qep:register_heuristic("udp", heur)
