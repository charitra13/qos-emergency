# QoS-Aware Emergency Traffic Prioritization

[![Project Demo](https://img.youtube.com/vi/r4yKdgUciPI/maxresdefault.jpg)](https://www.youtube.com/watch?v=r4yKdgUciPI)


A QoS-aware network traffic management system that classifies voice, video, emergency and ordinary traffic, then prioritizes packets during network congestion using multiple scheduling algorithms.

The project implements a custom protocol (QEP), a multi-stage traffic classifier, five scheduling algorithms (FIFO, Strict Priority, WFQ, DRR and the proposed hybrid EPS), a discrete-event simulator with 10 test scenarios, a live UDP demonstration with a software QoS router, Mininet/`tc` emulation, an interactive web dashboard and Wireshark verification tooling.

**Zero external Python dependencies.** Everything runs on the Python 3.8+ standard library. Mininet, tshark and Wireshark are optional.

## Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Problem Statement and Objectives](#2-problem-statement-and-objectives)
- [3. Architecture and Network Topology](#3-architecture-and-network-topology)
- [4. Custom Protocol: QEP](#4-custom-protocol-qep)
- [5. Multi-Stage Traffic Classifier](#5-multi-stage-traffic-classifier)
- [6. Packet Scheduling Algorithms](#6-packet-scheduling-algorithms)
- [7. Implementation Overview](#7-implementation-overview)
- [8. Test Scenarios and Results](#8-test-scenarios-and-results)
- [9. Wireshark and Packet-Level Verification](#9-wireshark-and-packet-level-verification)
- [10. Design Iterations and Improvements](#10-design-iterations-and-improvements)
- [11. Limitations and Future Work](#11-limitations-and-future-work)
- [12. Installation and Execution](#12-installation-and-execution)

---

## 1. Project Overview

QoS-Aware Emergency Traffic Prioritization is a network traffic management project designed to ensure that critical communications receive preferential treatment during periods of congestion.

It combines traffic classification, packet scheduling, traffic policing, queue management and performance monitoring to evaluate how different Quality of Service (QoS) strategies behave under realistic network conditions.

### Key Features

- **Custom QEP Protocol:** A 24-byte packet header carrying traffic class, flow ID, sequence number, timestamp and checksum.
- **Multi-Stage Classifier:** Identifies traffic using QEP headers, DSCP markings, UDP ports and flow caching.
- **Five Scheduling Algorithms:** FIFO, Strict Priority, Weighted Fair Queueing, Deficit Round Robin and the proposed Emergency Priority Scheduler.
- **EPS Hybrid Scheduler:** Combines strict priority, weighted fair queueing, token-bucket policing and shared-buffer push-out.
- **Discrete-Event Simulator:** Models congestion, link outages, degradation, malicious traffic, packet loss and other network conditions.
- **Live UDP Demonstration:** Sends real UDP packets through a software QoS router using actual network sockets.
- **Mininet Emulation:** Provides an optional Linux-based network emulation using `tc`.
- **Interactive Web Dashboard:** Separate Simulation and Live Demo views with class metrics, SLA results, router counters and emergency-delay charts.
- **Wireshark Verification:** Custom QEP dissector and packet capture tooling for protocol-level inspection.
- **Automated Testing:** 31 unit and scenario tests.

### Quick Start

```bash
# Run automated tests
python3 -m unittest -v tests.test_qos

# Run all simulation scenarios
python3 run_simulation.py --scenario all

# Run the live UDP demonstration
python3 live/run_live_demo.py

# Start the web dashboard
python3 dashboard/server.py
```

Open the dashboard at:

http://localhost:8080

See `instructions.txt` for detailed setup and execution instructions.

---

## 2. Problem Statement and Objectives

During emergencies and disasters, critical network traffic such as alarms, sensor telemetry and emergency dispatch communications shares network infrastructure with ordinary data traffic.

A conventional FIFO queue treats every packet equally. When the network bottleneck becomes saturated, emergency packets may experience excessive delays or packet loss because they are queued behind bulk data.

This project investigates how intelligent traffic classification and packet scheduling can improve network performance for critical traffic.

### Objectives

| # | Objective | Measurement |
|---|---|---|
| O1 | Classify packets into emergency, voice, video and best-effort traffic, even with missing or incorrect markings | Classification accuracy, flow-cache hit ratio (TC7) |
| O2 | Maintain emergency and voice delay, jitter and loss within SLA during congestion | p99 delay, jitter and packet loss (TC2, TC3) |
| O3 | Survive link failures and recover quickly | Emergency packet loss and recovery time (TC4, TC5) |
| O4 | Prevent abuse by flows falsely claiming emergency priority | Performance under spoofed traffic (TC6) |
| O5 | Prevent starvation of lower-priority traffic | Best-effort throughput and video loss (TC8) |
| O6 | Quantify performance trade-offs between scheduling algorithms | Load sweep (TC10) |

### SLA Targets

The following Service Level Agreement (SLA) thresholds are used to determine PASS/FAIL results.

| Traffic Class | p99 Delay | Jitter | Packet Loss |
|---|---:|---:|---:|
| Emergency | ≤ 50 ms | — | ≤ 0.1% |
| Voice | ≤ 150 ms | ≤ 30 ms | ≤ 1% |
| Video | ≤ 300 ms | — | ≤ 2% |

Delay is measured as one-way delay, including queueing, serialization and 5 ms propagation.

---

## 3. Architecture and Network Topology

The simulation, live demonstration and Mininet environment model the same logical network architecture.

![Network Architecture](docs/architecture.svg)

### Logical Network Topology

```text
h_voice  (10.0.1.1, EF)  ----\
h_video  (10.0.1.2, AF41) ---+--- s1 --- r1 --- 10 Mbit/s bottleneck --- s2 --- h_srv (10.0.2.2)
h_emerg  (10.0.1.3, CS6)  ---+             (Classifier + Scheduler)      |
h_bulk   (10.0.1.4, BE)   ---/                                          |
                                                                   5 ms propagation
```

### Network Components

| Component | Responsibility |
|---|---|
| h_voice | Generates voice traffic |
| h_video | Generates video traffic |
| h_emerg | Generates emergency traffic |
| h_bulk | Generates ordinary best-effort traffic |
| s1 | Connects traffic-generating hosts |
| r1 | Performs traffic classification, policing and packet scheduling |
| s2 | Connects the bottleneck to the destination |
| h_srv | Receives forwarded traffic |

**Important design decision:** Only the router egress port is congested. This ensures that the scheduler is the primary variable changing between experiments, allowing a controlled comparison of scheduling algorithms.

---

## 4. Custom Protocol: QEP

The project implements a custom packet protocol called **QEP (QoS Emergency Protocol)**.

Each datagram follows this structure:

```text
IPv4 (DSCP) | UDP | 24-byte QEP Header | Payload
```

### QEP Header Structure

```text
0               1               2               3
+---------------+---------------+---------------+---------------+
|       Magic 0x5145 'QE'       | Ver(4)|Class(4)|   Flags (8)   |
+---------------+---------------+---------------+---------------+
|           Flow ID             |   DSCP (8)    |  Reserved (8) |
+---------------+---------------+---------------+---------------+
|                       Sequence number (32)                    |
+---------------------------------------------------------------+
|                  Timestamp, ns since epoch (64)               |
+---------------+---------------+---------------+---------------+
|        Payload length         |     Header checksum (16)      |
+---------------+---------------+---------------+---------------+
```

### Header Fields

| Field | Description |
|---|---|
| Magic | Protocol identifier `0x5145` (`QE`) |
| Version | Protocol version |
| Class | Traffic class: 0 emergency, 1 voice, 2 video, 3 best effort |
| Flags | Packet control flags |
| Flow ID | Identifies the originating traffic flow |
| DSCP | Differentiated Services Code Point marking |
| Reserved | Reserved for future protocol extensions |
| Sequence Number | Tracks packet ordering and loss |
| Timestamp | Sender timestamp in nanoseconds since epoch |
| Payload Length | Length of the packet payload |
| Header Checksum | RFC 1071 Internet checksum over the header, with the checksum field zeroed during calculation |

### QEP Flags

| Flag | Value | Description |
|---|---|---|
| ALERT | `0x01` | First packet of an emergency event |
| RETX | `0x02` | Retransmission indicator |
| LAST | `0x04` | Last packet in a transmission |
| PREEMPT_REQUEST | `0x08` | Requests priority preemption |

### Traffic Classes and Markings

| Class | DSCP | UDP Port | Typical Source |
|---|---:|---:|---|
| Emergency | 48 (CS6) | 5911 | Alarms and sensor events |
| Voice | 46 (EF) | 5004 | G.711-like voice packets |
| Video | 34 (AF41) | 5006 | Video streams |
| Best Effort | 0 (BE) | 5201 / 80 / 443 / 8080 | Bulk and ordinary data |

### Traffic Generation Profiles

| Traffic | Packet Characteristics |
|---|---|
| Emergency | 172 bytes, 5–60 packets/sec per source |
| Voice | 212 bytes every 20 ms, approximately 85 kbit/s per call |
| Video | 30 FPS, I-frame bursts at 4× frequency, 1252-byte packets |
| Best Effort | Bursty TCP-like traffic, 200–1500 bytes |

**Implementation:** `qos/protocol.py`

**Wireshark dissector:** `docs/qep_dissector.lua`

---

## 5. Multi-Stage Traffic Classifier

Implementation: `qos/classifier.py`

The classifier uses a staged, cheapest-trustworthy-first approach to identify incoming packets.

### Classification Pipeline

```text
             Incoming Packet
                    |
                    v
              QEP Header?
               /      \
             Yes       No
              |         |
              v         v
          QEP Class   DSCP Marking?
                       /       \
                     Yes        No
                      |          |
                      v          v
                 DSCP Class   UDP Port?
                              /      \
                            Yes       No
                             |         |
                             v         v
                         Port Class  Flow Cache?
                                     /       \
                                   Hit       Miss
                                    |          |
                                    v          v
                               Cached Class  Best Effort
```

The actual classification order is:

1. QEP header
2. DSCP marking
3. UDP port
4. Flow cache
5. Default to best effort

### Flow Cache

The flow cache remembers the classification of a flow once a packet has been successfully identified.

Subsequent packets belonging to the same flow can retain their classification even when DSCP markings are stripped or corrupted.

DSCP value 0 is treated as unknown because a stripped marking is indistinguishable from ordinary best-effort traffic.

This mechanism improves classification accuracy from 99.72% to 100% in TC7.

---

## 6. Packet Scheduling Algorithms

Implementation: `qos/schedulers.py`

The project evaluates five scheduling algorithms.

| Algorithm | Description | Main Weakness |
|---|---|---|
| FIFO | Single tail-drop queue; all packets are treated equally | No prioritization |
| Strict Priority (PQ) | Separate per-class queues; higher-priority packets are served first | Can starve lower classes and trusts markings |
| WFQ | Self-Clocked Fair Queueing with weights 40/30/20/10 | Emergency receives only its allocated share under attack |
| DRR | Deficit Round Robin using the same weights | Coarser delay due to quantum rounds |
| EPS | Proposed hybrid scheduler combining priority, weighted sharing and policing | Requires call admission control for voice oversubscription |

### Proposed Hybrid Scheduler: EPS

The **Emergency Priority Scheduler (EPS)** combines strict priority for critical traffic with weighted sharing for lower-priority traffic.

Its design consists of five mechanisms.

**1. Tier 1 – Emergency**

Emergency packets receive the highest scheduling priority.

**2. Tier 2 – Voice**

Voice traffic receives the second-highest priority, ensuring low latency for real-time communication.

**3. Tier 3 – Video and Best Effort**

Video and best-effort traffic share the remaining bandwidth through WFQ with a 6:4 weight ratio.

This prevents lower-priority traffic from being completely starved.

**4. Token-Bucket Policing**

Emergency and voice traffic must conform to both:

- A per-flow token bucket.
- An aggregate class token bucket.

The aggregate limits are:

| Class | Maximum Aggregate Rate |
|---|---:|
| Emergency | 20% of link capacity |
| Voice | 35% of link capacity |

Packets exceeding their permitted profile are re-marked as best effort rather than dropped.

Per-flow policing prevents a single spoofed flow from consuming the aggregate reservation and demoting genuine emergency traffic.

**5. Shared Buffer with Push-Out**

EPS uses a shared buffer with packet push-out.

When the buffer is full, an arriving higher-priority packet can evict tail packets belonging to lower-priority classes.

Additionally, video and best-effort queues have individual capacity limits to reduce bufferbloat.

---

## 7. Implementation Overview

The project is organized into modular components shared across the simulation, live demo and Mininet environments.

| Path | Purpose |
|---|---|
| `qos/protocol.py` | QEP protocol and packet header |
| `qos/classifier.py` | Multi-stage traffic classifier |
| `qos/schedulers.py` | FIFO, PQ, WFQ, DRR and EPS |
| `qos/packet.py` | Packet representation |
| `qos/traffic.py` | Traffic generation models |
| `qos/simulator.py` | Discrete-event bottleneck simulator |
| `qos/metrics.py` | Performance metrics and SLA evaluation |
| `qos/scenarios.py` | Test scenario catalogue |
| `qos/report.py` | Markdown, CSV and HTML+SVG reports |
| `qos/pcapio.py` | PCAP packet writer and reader |
| `run_simulation.py` | Simulation CLI |
| `live/` | UDP sender, software QoS router, receiver and analyzer |
| `mininet/mn_qos_topo.py` | Mininet topology and `tc` configuration |
| `dashboard/` | Standard-library web dashboard |
| `tools/pcap_verify.py` | Packet-level verification |
| `docs/qep_dissector.lua` | Wireshark QEP dissector |
| `tests/test_qos.py` | Automated test suite |

### Performance Metrics

The simulator measures:

- One-way delay: average, p50, p95, p99 and maximum.
- Jitter: mean absolute delay variation between consecutive packets of each flow.
- Packet loss: queue drops, push-out drops and link loss.
- Throughput.
- SLA verdicts.
- Recovery time after link failures.
- Classification accuracy.
- Flow-cache hit ratio.

---

## 8. Test Scenarios and Results

The project includes 10 test scenarios to evaluate scheduler behaviour under different network conditions.

### Simulation Configuration

| Parameter | Value |
|---|---|
| Bottleneck capacity | 10 Mbit/s |
| Simulation duration | 20 seconds |
| Random seed | 1 |
| Voice traffic | 20 calls (1.7 Mbit/s) |
| Video traffic | 3 streams (3 Mbit/s) |
| Emergency traffic | 10 sources |
| Additional traffic | Bulk best-effort traffic |

**P/F** indicates the SLA verdict for Emergency / Voice / Video.

### TC1 – Normal Network Conditions (~70% Load)

Emergency p99 delay in milliseconds.

| Scheduler | Emergency p99 | SLA (EM/VO/VI) |
|---|---:|---|
| FIFO | 42.4 ms | P/P/P |
| Strict PQ | 6.3 ms | P/P/P |
| WFQ | 6.3 ms | P/P/P |
| DRR | 9.4 ms | P/P/P |
| **EPS** | **6.3 ms** | **P/P/P** |

### TC2 – Network Congestion (~170% Load)

| Scheduler | Emergency p99 | Emergency Loss | SLA |
|---|---:|---:|---|
| FIFO | 105.5 ms | 2.91% | F/F/F |
| Strict PQ | 6.3 ms | 0% | P/P/P |
| WFQ | 6.5 ms | 0% | P/P/P |
| DRR | 9.8 ms | 0% | P/P/P |
| **EPS** | **6.3 ms** | **0%** | **P/P/P** |

### TC3 – Disaster Surge During Congestion

| Scheduler | Emergency p99 | Emergency Loss | Emergency SLA |
|---|---:|---:|---|
| FIFO | 105.4 ms | 2.54% | F |
| Strict PQ | 6.3 ms | 0% | P |
| WFQ | 7.3 ms | 0% | P |
| DRR | 10.1 ms | 0% | P |
| **EPS** | **6.3 ms** | **0%** | **P** |

### TC4 – 2-Second Link Outage

| Scheduler | Emergency Loss | Recovery Time |
|---|---:|---:|
| FIFO | 19.9% | 7163 ms |
| Strict PQ | 16.4% | 0.9 ms |
| WFQ | 16.4% | 0 ms |
| DRR | 16.4% | 0 ms |
| **EPS** | **0.0%** | **0 ms** |

### TC5 – Network Capacity Degradation to 35%

| Scheduler | Emergency p99 | Voice p99 | SLA (EM/VO) |
|---|---:|---:|---|
| FIFO | 291.6 ms | 291.5 ms | F/F |
| Strict PQ | 8.2 ms | 9.6 ms | P/P |
| WFQ | 10.2 ms | 181.8 ms | P/F |
| DRR | 27.4 ms | 180.5 ms | P/F |
| **EPS** | **8.4 ms** | **9.7 ms** | **P/P** |

### TC6 – Spoofed Emergency Traffic Flood (8 Mbit/s)

| Scheduler | Emergency Loss | Video Loss | Result |
|---|---:|---:|---|
| FIFO | 1.53% | 24.8% | F |
| Strict PQ | 0.69% | 50.2% | F |
| WFQ | 2.28% | 28.0% | F |
| DRR | 4.72% | 27.7% | F |
| **EPS** | **0.00%** | **0.00%** | **P/P/P** |

### TC7 – Noisy Traffic Markings

Classification accuracy and emergency SLA.

| Scheduler / Classifier Mode | Classification Accuracy | Emergency SLA |
|---|---:|---|
| FIFO | — | F |
| Strict PQ | — | P |
| WFQ | — | P |
| DRR | — | P |
| **EPS (Full Classifier)** | **100.00%** | **P** |

### TC8 – Voice Oversubscription (90 Calls)

| Scheduler | Best-Effort Throughput | Video Loss |
|---|---:|---:|
| FIFO | 885 kbit/s | 56% |
| Strict PQ | 15 kbit/s | 39% |
| WFQ | 1643 kbit/s | 8.1% |
| DRR | 1643 kbit/s | 8.1% |
| **EPS** | **149 kbit/s** | **0.07%** |

### TC9 – Random Link Loss (2%)

| Scheduler | Emergency p99 | Emergency Loss |
|---|---:|---:|
| FIFO | 104 ms | 2.5% |
| Strict PQ | 6.3 ms | 2.0% |
| WFQ | 6.4 ms | 1.9% |
| DRR | 9.7 ms | 1.5% |
| **EPS** | **6.3 ms** | **2.1%** |

### TC10 – Load Sweep

Emergency p99 delay as bulk traffic increases from 1 to 15 Mbit/s.

| Scheduler | Emergency p99 Behaviour |
|---|---|
| FIFO | 36 → 57 → 105 → 105 ... ms |
| Strict PQ | Approximately 6.3 ms |
| WFQ | Approximately 7 ms |
| DRR | Approximately 10 ms |
| **EPS** | **Approximately 6.3 ms** |

### Classifier Ablation Study (TC7)

TC7 evaluates classification accuracy under noisy markings:

- 25% DSCP markings stripped.
- 10% incorrect UDP port markings.
- QEP headers available on 80% of packets.

| Classifier Configuration | Accuracy | Emergency Loss | Emergency p99 |
|---|---:|---:|---:|
| DSCP only | 85.86% | 1.23% | 117 ms |
| DSCP + Port | 98.46% | 0.23% | 117 ms |
| Header only | 88.25% | 1.41% | 118 ms |
| Header + DSCP + Port (Stateless) | 99.72% | 0.00% | 6.3 ms |
| **Full Classifier + Flow Cache** | **100.00%** | **0.00%** | **6.3 ms** |

32.7% of packets were served from the flow cache.

### Live UDP Demonstration

The live demo uses real UDP sockets and a software QoS router.

| Parameter | Value |
|---|---|
| Router capacity | 1 Mbit/s |
| Offered load | Approximately 190% |
| Duration | 8 seconds |
| Traffic | Real UDP packets |

#### Live Scheduler Comparison

| Scheduler | Emergency p99 | Emergency Loss | Voice p99 | SLA (EM/VO/VI) |
|---|---:|---:|---:|---|
| FIFO | 200.7 ms | 3.3% | 202.2 ms | F/F/F |
| Strict PQ | 12.0 ms | 0% | 14.7 ms | P/P/P |
| WFQ | 13.8 ms | 0% | 13.7 ms | P/P/P |
| DRR | 38.3 ms | 0% | 36.4 ms | P/P/P |
| **EPS** | **11.9 ms** | **0%** | **15.1 ms** | **P/P/P** |

#### Live Demo with a 900 kbit/s Spoofed Flood

| Scheduler | Emergency p99 | Emergency Loss | Voice p99 |
|---|---:|---:|---:|
| FIFO | 203 ms | 30.3% | 202 ms |
| Strict PQ | 112 ms | 0.62% | 112 ms |
| **EPS** | **13.6 ms** | **0%** | **19.6 ms** |

Live measurements may vary slightly due to operating-system scheduling, but the overall performance ordering is stable.

### Important Experimental Observations

- **TC1:** At approximately 70% utilization, FIFO already meets the SLA. QoS becomes important under congestion.
- **TC2/TC3:** All QoS schedulers protect low-rate emergency and voice traffic during congestion.
- **TC4:** Packets arriving during an outage can remain delayed for up to the outage duration. EPS achieves zero emergency packet loss through push-out buffer management.
- **TC5:** Video must degrade because the available bandwidth cannot satisfy all traffic demands. EPS and PQ protect emergency and voice traffic.
- **TC6:** Strict PQ and WFQ/DRR cannot adequately protect against spoofed emergency traffic. EPS uses per-flow policing.
- **TC8:** Strict PQ starves lower-priority traffic. EPS preserves video service but voice oversubscription remains a limitation.
- **TC9:** Random packet loss affects all classes. Scheduling alone cannot eliminate physical link loss; FEC or retransmission is required.

---

## 9. Wireshark and Packet-Level Verification

The project includes packet capture and verification tooling to validate that the scheduling behaviour observed in the simulator is reflected in actual packet output.

### Generate a PCAP File

Run:

```bash
python3 run_simulation.py --scenario tc2 --pcap results/tc2_eps.pcap --pcap-scheduler eps
```

This generates a packet capture containing packets as they leave the bottleneck.

The capture includes:

- Ethernet headers.
- IPv4 headers.
- UDP headers.
- QEP headers.
- Actual DSCP markings.
- Valid IP checksums.

### Open in Wireshark

```bash
wireshark -X lua_script:docs/qep_dissector.lua results/tc2_eps.pcap
```

### Useful Wireshark Display Filters

| Filter | Description |
|---|---|
| `qep.cls == 0` | Emergency packets |
| `ip.dsfield.dscp == 48` | CS6-marked packets |
| `qep.flags.alert == 1` | Emergency alert packets |
| `qep && frame.time_delta_displayed > 0.05` | QEP packets with displayed time delta above 50 ms |

### Automated PCAP Verification

```bash
python3 tools/pcap_verify.py results/tc2_eps.pcap
```

The verification tool checks:

- QEP header checksums.
- DSCP and traffic-class consistency.
- Packet-level delay.
- Scheduling priority.
- Traffic-class performance.

### Example Packet-Level Results

**EPS vs FIFO under congestion**

| Class | EPS Packets | Mean Delay | p99 Delay |
|---|---:|---:|---:|
| Emergency | 2143 | 0.58 ms | 1.31 ms |
| Voice | 9437 | 0.76 ms | 1.57 ms |
| Video | 3372 | 12.55 ms | 59.38 ms |
| Best Effort | 1294 | 106.21 ms | 156.85 ms |

| Class | FIFO Packets | Mean Delay | p99 Delay |
|---|---:|---:|---:|
| Emergency | 2081 | 95.65 ms | 100.55 ms |
| Voice | 9142 | 95.77 ms | 100.42 ms |
| Video | 2348 | 94.90 ms | 100.80 ms |
| Best Effort | 1662 | 96.48 ms | 100.98 ms |

**Verification Verdicts:**

- EPS: `PRIORITY HONOURED`
- FIFO: `NO PRIORITY EFFECT (FIFO-like)`

The QEP timestamp represents arrival time at the bottleneck, allowing capture time minus QEP timestamp to estimate queueing and serialization delay.

For live or Mininet captures, capture on the loopback or `r1-eth2` interface:

```bash
python3 tools/pcap_verify.py capture.pcap
```

Use classic PCAP format when exporting captures from Wireshark.

---

## 10. Design Iterations and Improvements

The implementation evolved through several iterations based on experimental results.

### 1. Aggregate-Only Policing

**Initial problem:** The first EPS implementation used only an aggregate emergency token bucket.

During TC6, spoofed traffic consumed the available tokens, causing genuine emergency packets to be demoted. Emergency p99 delay increased to 307 ms.

**Improvement:** Added both per-flow and aggregate token-bucket policing.

### 2. Stateless Classification

**Initial problem:** The stateless classifier misclassified approximately 0.3–0.5% of packets under noisy markings.

Emergency packet loss reached 0.12% in TC7.

**Improvement:** Introduced a flow cache to preserve previously established classifications.

### 3. Shared Buffer Management

**Initial problem:** Video traffic could fill the entire 125 kB shared buffer during network degradation, causing excessive queueing delay.

Video p99 delay reached 885 ms.

**Improvement:** Introduced individual queue capacity limits for video and best-effort traffic.

### 4. Live Demo Rate Scaling

**Initial problem:** The initial 10 Mbit/s per-flow traffic profile was too generous for the 1 Mbit/s live router.

**Improvement:** Scaled traffic profiles and policing limits according to the actual link capacity.

---

## 11. Limitations and Future Work

Although the project demonstrates significant improvements in emergency traffic prioritization, several limitations remain.

### Current Limitations

1. **Unauthenticated Emergency Markings:** QEP markings are not cryptographically authenticated. A malicious host can claim emergency priority. Future implementations should introduce HMAC-based authentication or ingress allow-lists.

2. **Single Bottleneck Architecture:** The experiments focus on a single congested egress link rather than a multi-hop network.

3. **UDP-Style Traffic Models:** TCP congestion-control feedback is not fully modelled.

4. **No ECN/AQM:** Active Queue Management techniques such as CoDel and RED are not included.

5. **Call Admission Control:** EPS requires call admission control to prevent excessive voice traffic from exceeding the reserved 35% aggregate capacity.

6. **Physical Packet Preemption:** The scheduler does not support preemption of in-flight Ethernet frames or link fragmentation.

7. **Mininet Approximation:** The Mininet implementation uses Linux `tc` TBF, PRIO and HTB configurations. It approximates EPS using HTB and does not implement the full per-flow policing and push-out mechanisms.

   The Mininet script (`mininet/mn_qos_topo.py`) requires Linux and root privileges and was not executed in the authoring environment.

### Future Enhancements

- Cryptographic authentication of emergency traffic.
- HMAC-based QEP authentication tokens.
- Multi-hop network topology support.
- Dynamic bandwidth allocation.
- Voice call admission control.
- ECN and Active Queue Management.
- Forward Error Correction and retransmission.
- Enhanced Mininet implementation of EPS.
- Adaptive scheduling based on real-time traffic conditions.

---

## 12. Installation and Execution

### Requirements

- Python 3.8 or later.
- No external Python packages required.
- Linux and root privileges for Mininet emulation.
- Wireshark and tshark for packet inspection (optional).

### Run Automated Tests

```bash
python3 -m unittest -v tests.test_qos
```

Expected: 31 automated tests.

### Run All Simulation Scenarios

```bash
python3 run_simulation.py --scenario all
```

Generated reports:

```text
results/
    summary_all.md
    report_all.html
```

### Run the Live UDP Demonstration

```bash
python3 live/run_live_demo.py
```

This launches real UDP traffic through the software QoS router and evaluates the scheduling algorithms.

### Launch the Web Dashboard

```bash
python3 dashboard/server.py
```

Open:

http://localhost:8080

The dashboard contains two separate views:

**Simulation View**
- Scenario selection.
- Scheduler comparison.
- Traffic-class performance.
- Delay and jitter metrics.
- SLA results.
- Simulation charts.

**Live Demo View**
- Real UDP traffic monitoring.
- Software router counters.
- Traffic-class metrics.
- SLA results.
- Emergency-delay charts.
- Live-run logs.

The dashboard server prints timestamped request, simulation and live-run logs to the terminal.

### Optional: Mininet Emulation

```bash
sudo python3 mininet/mn_qos_topo.py
```

Requires a Linux environment with Mininet and the Linux traffic-control (`tc`) utilities installed.

---

## Project Summary

QoS-Aware Emergency Traffic Prioritization demonstrates how intelligent packet classification, traffic policing and hybrid scheduling can improve the reliability of critical network communications during congestion.

The proposed **Emergency Priority Scheduler (EPS)** combines strict priority for emergency and voice traffic with weighted fair sharing for video and best-effort traffic. Its per-flow policing and push-out buffer management address important weaknesses found in conventional scheduling approaches.

Through discrete-event simulation, real UDP traffic, network emulation and packet-level verification, the project evaluates both the performance benefits and limitations of different QoS scheduling strategies.

**The central objective is simple: ensure that the packets that matter most are delivered first, without unnecessarily sacrificing the rest of the network.**
