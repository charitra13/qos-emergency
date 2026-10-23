# Simulation results

### TC1 - Normal load (~70 %)

Baseline: link is not congested. Every scheduler should meet all SLAs.

| Scheduler | Class | Sent | Loss % | Delay avg ms | p99 ms | Jitter ms | Thr kbps | SLA |
|---|---|---:|---:|---:|---:|---:|---:|:--:|
| FIFO | emergency | 3200 | 0.00 | 9.8 | 42.4 | 5.4 | 220 | PASS |
| FIFO | voice | 20000 | 0.00 | 11.1 | 50.4 | 4.5 | 1696 | PASS |
| FIFO | video | 7097 | 0.00 | 13.0 | 55.2 | 2.2 | 3554 | PASS |
| FIFO | best_effort | 4284 | 0.00 | 15.8 | 51.3 | 1.7 | 2024 | - |
| Strict PQ | emergency | 3200 | 0.00 | 5.4 | 6.3 | 0.3 | 220 | PASS |
| Strict PQ | voice | 20000 | 0.00 | 5.6 | 6.5 | 0.4 | 1696 | PASS |
| Strict PQ | video | 7097 | 0.00 | 9.5 | 30.7 | 1.7 | 3554 | PASS |
| Strict PQ | best_effort | 4284 | 2.38 | 24.5 | 104.4 | 3.4 | 1971 | - |
| WFQ | emergency | 3200 | 0.00 | 5.5 | 6.3 | 0.4 | 220 | PASS |
| WFQ | voice | 20000 | 0.00 | 5.6 | 6.9 | 0.4 | 1696 | PASS |
| WFQ | video | 7097 | 0.10 | 11.1 | 44.2 | 2.1 | 3551 | PASS |
| WFQ | best_effort | 4284 | 1.42 | 22.3 | 88.6 | 3.2 | 1993 | - |
| DRR | emergency | 3200 | 0.00 | 6.0 | 9.4 | 1.0 | 220 | PASS |
| DRR | voice | 20000 | 0.00 | 6.1 | 8.9 | 1.0 | 1696 | PASS |
| DRR | video | 7097 | 0.13 | 11.0 | 43.6 | 2.1 | 3550 | PASS |
| DRR | best_effort | 4284 | 1.40 | 22.0 | 89.0 | 3.2 | 1993 | - |
| EPS (proposed) | emergency | 3200 | 0.00 | 5.4 | 6.3 | 0.3 | 220 | PASS |
| EPS (proposed) | voice | 20000 | 0.00 | 5.6 | 6.5 | 0.4 | 1696 | PASS |
| EPS (proposed) | video | 7097 | 0.00 | 12.0 | 52.6 | 2.3 | 3554 | PASS |
| EPS (proposed) | best_effort | 4284 | 0.05 | 22.6 | 90.9 | 3.1 | 2023 | - |

### TC2 - Heavy congestion (~170 % offered load)

Bulk traffic overloads the 10 Mbps bottleneck. FIFO must fail emergency/voice SLAs.

| Scheduler | Class | Sent | Loss % | Delay avg ms | p99 ms | Jitter ms | Thr kbps | SLA |
|---|---|---:|---:|---:|---:|---:|---:|:--:|
| FIFO | emergency | 3200 | 2.91 | 100.2 | 105.5 | 4.1 | 214 | FAIL |
| FIFO | voice | 20000 | 3.19 | 100.3 | 105.4 | 4.0 | 1642 | FAIL |
| FIFO | video | 7097 | 29.82 | 99.8 | 105.8 | 2.2 | 2494 | FAIL |
| FIFO | best_effort | 23201 | 42.63 | 101.3 | 106.0 | 1.3 | 5697 | - |
| Strict PQ | emergency | 3200 | 0.00 | 5.6 | 6.3 | 0.4 | 220 | PASS |
| Strict PQ | voice | 20000 | 0.00 | 5.8 | 6.5 | 0.4 | 1696 | PASS |
| Strict PQ | video | 7097 | 0.00 | 9.9 | 31.0 | 1.7 | 3554 | PASS |
| Strict PQ | best_effort | 23201 | 53.79 | 64.3 | 134.7 | 2.9 | 4543 | - |
| WFQ | emergency | 3200 | 0.00 | 5.6 | 6.5 | 0.4 | 220 | PASS |
| WFQ | voice | 20000 | 0.00 | 5.8 | 7.2 | 0.4 | 1696 | PASS |
| WFQ | video | 7097 | 0.20 | 14.0 | 51.7 | 2.8 | 3547 | PASS |
| WFQ | best_effort | 23201 | 53.42 | 64.3 | 113.0 | 2.6 | 4551 | - |
| DRR | emergency | 3200 | 0.00 | 6.7 | 9.8 | 1.1 | 220 | PASS |
| DRR | voice | 20000 | 0.00 | 6.8 | 9.4 | 1.3 | 1696 | PASS |
| DRR | video | 7097 | 0.21 | 13.9 | 51.4 | 2.7 | 3547 | PASS |
| DRR | best_effort | 23201 | 53.35 | 64.2 | 112.7 | 2.6 | 4551 | - |
| EPS (proposed) | emergency | 3200 | 0.00 | 5.6 | 6.3 | 0.4 | 220 | PASS |
| EPS (proposed) | voice | 20000 | 0.00 | 5.8 | 6.5 | 0.4 | 1696 | PASS |
| EPS (proposed) | video | 7097 | 0.00 | 16.8 | 62.9 | 3.2 | 3554 | PASS |
| EPS (proposed) | best_effort | 23201 | 53.11 | 108.5 | 159.0 | 2.5 | 4554 | - |

### TC3 - Disaster surge: emergency burst during congestion

20 emergency sources raise 60 pps each for 6 s while bulk traffic saturates the link.

| Scheduler | Class | Sent | Loss % | Delay avg ms | p99 ms | Jitter ms | Thr kbps | SLA |
|---|---|---:|---:|---:|---:|---:|---:|:--:|
| FIFO | emergency | 9200 | 2.54 | 101.2 | 105.4 | 3.3 | 617 | FAIL |
| FIFO | voice | 20000 | 2.67 | 99.2 | 105.3 | 4.3 | 1651 | FAIL |
| FIFO | video | 7097 | 23.83 | 98.7 | 105.7 | 2.3 | 2707 | FAIL |
| FIFO | best_effort | 18613 | 37.60 | 100.0 | 105.9 | 1.4 | 5072 | - |
| Strict PQ | emergency | 9200 | 0.00 | 5.6 | 6.3 | 0.4 | 633 | PASS |
| Strict PQ | voice | 20000 | 0.00 | 5.8 | 6.8 | 0.4 | 1696 | PASS |
| Strict PQ | video | 7097 | 0.01 | 10.7 | 35.6 | 1.9 | 3554 | PASS |
| Strict PQ | best_effort | 18613 | 49.04 | 67.8 | 176.7 | 3.3 | 4122 | - |
| WFQ | emergency | 9200 | 0.00 | 5.8 | 7.3 | 0.5 | 633 | PASS |
| WFQ | voice | 20000 | 0.00 | 5.9 | 7.4 | 0.5 | 1696 | PASS |
| WFQ | video | 7097 | 0.31 | 15.7 | 60.9 | 3.1 | 3543 | PASS |
| WFQ | best_effort | 18613 | 48.47 | 67.9 | 138.8 | 2.9 | 4134 | - |
| DRR | emergency | 9200 | 0.00 | 7.1 | 10.1 | 1.3 | 633 | PASS |
| DRR | voice | 20000 | 0.00 | 7.0 | 10.3 | 1.4 | 1696 | PASS |
| DRR | video | 7097 | 0.32 | 15.5 | 61.1 | 2.9 | 3543 | PASS |
| DRR | best_effort | 18613 | 48.18 | 68.0 | 138.4 | 2.9 | 4134 | - |
| EPS (proposed) | emergency | 9200 | 0.00 | 5.6 | 6.3 | 0.4 | 633 | PASS |
| EPS (proposed) | voice | 20000 | 0.00 | 5.8 | 6.9 | 0.4 | 1696 | PASS |
| EPS (proposed) | video | 7097 | 0.00 | 20.6 | 78.8 | 3.5 | 3554 | PASS |
| EPS (proposed) | best_effort | 18613 | 48.26 | 116.6 | 195.6 | 2.9 | 4141 | - |

### TC4 - Failure: 2 s link outage and recovery

Link goes down 8-10 s with an emergency event in progress. Measures loss and recovery time.

| Scheduler | Class | Sent | Loss % | Delay avg ms | p99 ms | Jitter ms | Thr kbps | SLA |
|---|---|---:|---:|---:|---:|---:|---:|:--:|
| FIFO | emergency | 3000 | 19.90 | 59.2 | 2069.5 | 28.0 | 165 | FAIL |
| FIFO | voice | 20000 | 9.98 | 42.2 | 103.1 | 11.1 | 1527 | FAIL |
| FIFO | video | 7097 | 10.82 | 45.3 | 103.9 | 4.8 | 3170 | FAIL |
| FIFO | best_effort | 8200 | 10.83 | 49.0 | 104.2 | 2.2 | 3435 | - |
| Strict PQ | emergency | 3000 | 16.40 | 84.8 | 1915.6 | 16.2 | 173 | FAIL |
| Strict PQ | voice | 20000 | 9.36 | 21.5 | 6.7 | 4.8 | 1537 | FAIL |
| Strict PQ | video | 7097 | 10.22 | 19.4 | 33.5 | 3.6 | 3191 | FAIL |
| Strict PQ | best_effort | 8200 | 19.38 | 45.8 | 121.7 | 4.0 | 3075 | - |
| WFQ | emergency | 3000 | 16.37 | 85.3 | 1918.9 | 16.2 | 173 | FAIL |
| WFQ | voice | 20000 | 9.27 | 21.8 | 50.2 | 4.8 | 1539 | FAIL |
| WFQ | video | 7097 | 10.27 | 22.6 | 56.9 | 4.4 | 3189 | FAIL |
| WFQ | best_effort | 8200 | 18.51 | 44.6 | 104.4 | 3.9 | 3111 | - |
| DRR | emergency | 3000 | 16.40 | 87.0 | 1933.5 | 16.9 | 173 | FAIL |
| DRR | voice | 20000 | 9.30 | 22.6 | 44.5 | 5.6 | 1538 | FAIL |
| DRR | video | 7097 | 10.27 | 22.1 | 55.9 | 4.4 | 3189 | FAIL |
| DRR | best_effort | 8200 | 18.48 | 43.5 | 104.6 | 3.9 | 3114 | - |
| EPS (proposed) | emergency | 3000 | 0.00 | 213.9 | 1909.3 | 13.5 | 206 | FAIL |
| EPS (proposed) | voice | 20000 | 9.49 | 17.6 | 44.4 | 5.0 | 1535 | FAIL |
| EPS (proposed) | video | 7097 | 10.48 | 15.1 | 64.7 | 3.0 | 3182 | FAIL |
| EPS (proposed) | best_effort | 8200 | 15.24 | 46.5 | 135.5 | 3.8 | 3252 | - |

Recovery time (ms until emergency delay < 100 ms after failure ends): FIFO=7163, Strict PQ=1, WFQ=0, DRR=0, EPS (proposed)=0

### TC5 - Failure: capacity degradation to 35 % (6-14 s)

E.g. microwave link fade / backup link. Priority classes must survive, video degrades.

| Scheduler | Class | Sent | Loss % | Delay avg ms | p99 ms | Jitter ms | Thr kbps | SLA |
|---|---|---:|---:|---:|---:|---:|---:|:--:|
| FIFO | emergency | 3200 | 3.16 | 160.6 | 291.6 | 8.3 | 213 | FAIL |
| FIFO | voice | 20000 | 3.80 | 126.1 | 291.5 | 5.4 | 1632 | FAIL |
| FIFO | video | 7097 | 28.90 | 72.3 | 292.3 | 3.2 | 2527 | FAIL |
| FIFO | best_effort | 8286 | 30.44 | 73.1 | 292.4 | 1.8 | 2578 | - |
| Strict PQ | emergency | 3200 | 0.00 | 5.9 | 8.2 | 0.6 | 220 | PASS |
| Strict PQ | voice | 20000 | 0.00 | 6.3 | 9.6 | 0.7 | 1696 | PASS |
| Strict PQ | video | 7097 | 22.69 | 50.2 | 266.0 | 3.1 | 2748 | FAIL |
| Strict PQ | best_effort | 8286 | 46.85 | 99.0 | 134.0 | 7.0 | 2050 | - |
| WFQ | emergency | 3200 | 0.00 | 6.3 | 10.2 | 0.9 | 220 | PASS |
| WFQ | voice | 20000 | 1.27 | 60.8 | 181.8 | 1.2 | 1674 | FAIL |
| WFQ | video | 7097 | 28.15 | 56.5 | 314.2 | 3.5 | 2554 | FAIL |
| WFQ | best_effort | 8286 | 38.21 | 100.2 | 631.9 | 4.4 | 2298 | - |
| DRR | emergency | 3200 | 0.00 | 11.2 | 27.4 | 3.7 | 220 | PASS |
| DRR | voice | 20000 | 1.31 | 60.2 | 180.5 | 2.0 | 1674 | FAIL |
| DRR | video | 7097 | 28.15 | 56.4 | 312.8 | 3.5 | 2554 | FAIL |
| DRR | best_effort | 8286 | 38.23 | 99.6 | 632.1 | 4.5 | 2297 | - |
| EPS (proposed) | emergency | 3200 | 0.00 | 5.9 | 8.4 | 0.6 | 220 | PASS |
| EPS (proposed) | voice | 20000 | 0.00 | 6.4 | 9.7 | 0.7 | 1696 | PASS |
| EPS (proposed) | video | 7097 | 29.59 | 75.6 | 584.6 | 4.1 | 2502 | FAIL |
| EPS (proposed) | best_effort | 8286 | 34.53 | 146.1 | 1096.9 | 4.5 | 2456 | - |

Recovery time (ms until emergency delay < 100 ms after failure ends): FIFO=0, Strict PQ=0, WFQ=0, DRR=0, EPS (proposed)=0

### TC6 - Attack: bulk flow falsely marked as emergency (8 Mbps)

Spoofed DSCP-48 / QEP class-0 flood. Strict priority collapses; policed EPS must hold.

| Scheduler | Class | Sent | Loss % | Delay avg ms | p99 ms | Jitter ms | Thr kbps | SLA |
|---|---|---:|---:|---:|---:|---:|---:|:--:|
| FIFO | emergency | 3200 | 1.53 | 99.0 | 105.3 | 4.7 | 217 | FAIL |
| FIFO | voice | 20000 | 2.81 | 99.3 | 105.4 | 4.3 | 1648 | FAIL |
| FIFO | video | 7097 | 24.77 | 98.8 | 105.7 | 2.3 | 2674 | FAIL |
| FIFO | best_effort | 20389 | 38.30 | 100.3 | 105.9 | 1.5 | 5507 | - |
| Strict PQ | emergency | 3200 | 0.69 | 9.7 | 20.0 | 4.9 | 219 | FAIL |
| Strict PQ | voice | 20000 | 0.14 | 27.2 | 119.9 | 13.9 | 1694 | PASS |
| Strict PQ | video | 7097 | 50.19 | 141.4 | 578.0 | 18.9 | 1770 | FAIL |
| Strict PQ | best_effort | 20389 | 32.91 | 66.0 | 21.1 | 4.8 | 6349 | - |
| WFQ | emergency | 3200 | 2.28 | 25.0 | 36.7 | 8.7 | 215 | FAIL |
| WFQ | voice | 20000 | 0.00 | 6.3 | 8.6 | 0.7 | 1696 | PASS |
| WFQ | video | 7097 | 28.03 | 111.0 | 128.5 | 5.3 | 2558 | FAIL |
| WFQ | best_effort | 20389 | 38.45 | 59.5 | 249.5 | 4.5 | 5560 | - |
| DRR | emergency | 3200 | 4.72 | 24.9 | 38.7 | 8.7 | 210 | FAIL |
| DRR | voice | 20000 | 0.00 | 9.5 | 14.3 | 1.5 | 1696 | PASS |
| DRR | video | 7097 | 27.74 | 109.8 | 130.2 | 4.9 | 2568 | FAIL |
| DRR | best_effort | 20389 | 38.58 | 59.2 | 249.1 | 4.5 | 5555 | - |
| EPS (proposed) | emergency | 3200 | 0.00 | 5.6 | 6.3 | 0.4 | 220 | PASS |
| EPS (proposed) | voice | 20000 | 0.00 | 5.8 | 6.6 | 0.4 | 1696 | PASS |
| EPS (proposed) | video | 7097 | 0.00 | 17.4 | 64.7 | 3.3 | 3554 | PASS |
| EPS (proposed) | best_effort | 20389 | 47.45 | 97.2 | 161.6 | 24.8 | 4551 | - |

### TC7 - Noisy markings (DSCP stripped 25 %, wrong port 10 %, header on 80 %)

Classifier robustness under congestion; compare classifier ablation (accuracy).

| Scheduler | Class | Sent | Loss % | Delay avg ms | p99 ms | Jitter ms | Thr kbps | SLA |
|---|---|---:|---:|---:|---:|---:|---:|:--:|
| FIFO | emergency | 3200 | 4.25 | 100.9 | 105.5 | 3.7 | 211 | FAIL |
| FIFO | voice | 20000 | 2.89 | 100.3 | 105.4 | 3.8 | 1647 | FAIL |
| FIFO | video | 7126 | 27.81 | 99.6 | 105.7 | 2.1 | 2576 | FAIL |
| FIFO | best_effort | 23015 | 42.87 | 101.4 | 106.0 | 1.2 | 5614 | - |
| Strict PQ | emergency | 3200 | 0.00 | 5.5 | 6.3 | 0.3 | 220 | PASS |
| Strict PQ | voice | 20000 | 0.00 | 5.7 | 6.5 | 0.4 | 1696 | PASS |
| Strict PQ | video | 7126 | 0.00 | 9.8 | 31.0 | 1.8 | 3569 | PASS |
| Strict PQ | best_effort | 23015 | 53.53 | 64.5 | 129.0 | 2.8 | 4528 | - |
| WFQ | emergency | 3200 | 0.00 | 5.6 | 6.4 | 0.4 | 220 | PASS |
| WFQ | voice | 20000 | 0.00 | 5.8 | 7.0 | 0.4 | 1696 | PASS |
| WFQ | video | 7126 | 0.21 | 13.5 | 51.4 | 2.8 | 3561 | PASS |
| WFQ | best_effort | 23015 | 52.80 | 64.6 | 113.1 | 2.5 | 4535 | - |
| DRR | emergency | 3200 | 0.00 | 6.9 | 9.4 | 1.2 | 220 | PASS |
| DRR | voice | 20000 | 0.00 | 6.7 | 9.1 | 1.1 | 1696 | PASS |
| DRR | video | 7126 | 0.23 | 13.4 | 51.6 | 2.8 | 3561 | PASS |
| DRR | best_effort | 23015 | 52.93 | 64.5 | 113.5 | 2.5 | 4536 | - |
| EPS (proposed) | emergency | 3200 | 0.00 | 5.5 | 6.3 | 0.4 | 220 | PASS |
| EPS (proposed) | voice | 20000 | 0.00 | 5.7 | 6.5 | 0.4 | 1696 | PASS |
| EPS (proposed) | video | 7126 | 0.00 | 16.2 | 62.6 | 3.3 | 3569 | PASS |
| EPS (proposed) | best_effort | 23015 | 52.73 | 108.7 | 161.6 | 2.5 | 4537 | - |

### TC8 - Starvation test: voice over-subscription (90 calls)

Strict priority starves video/bulk completely; EPS bounds voice to its reservation.

| Scheduler | Class | Sent | Loss % | Delay avg ms | p99 ms | Jitter ms | Thr kbps | SLA |
|---|---|---:|---:|---:|---:|---:|---:|:--:|
| FIFO | emergency | 3200 | 0.56 | 103.6 | 105.0 | 1.0 | 219 | FAIL |
| FIFO | voice | 90000 | 3.28 | 103.2 | 105.1 | 1.4 | 7382 | FAIL |
| FIFO | video | 7105 | 56.06 | 102.5 | 105.5 | 1.1 | 1564 | FAIL |
| FIFO | best_effort | 7483 | 65.78 | 103.6 | 105.8 | 0.8 | 885 | - |
| Strict PQ | emergency | 3200 | 0.00 | 5.3 | 6.0 | 0.1 | 220 | PASS |
| Strict PQ | voice | 90000 | 0.00 | 6.0 | 6.8 | 0.4 | 7632 | PASS |
| Strict PQ | video | 7105 | 39.24 | 132.3 | 179.6 | 5.9 | 2162 | FAIL |
| Strict PQ | best_effort | 7483 | 99.55 | 19992.5 | 20024.4 | 4.0 | 15 | - |
| WFQ | emergency | 3200 | 0.00 | 5.6 | 7.0 | 0.4 | 220 | PASS |
| WFQ | voice | 90000 | 35.75 | 55.4 | 59.3 | 0.8 | 4904 | FAIL |
| WFQ | video | 7105 | 8.05 | 76.4 | 97.2 | 4.4 | 3272 | FAIL |
| WFQ | best_effort | 7483 | 48.78 | 165.3 | 195.8 | 7.2 | 1643 | - |
| DRR | emergency | 3200 | 0.00 | 8.8 | 12.9 | 2.8 | 220 | PASS |
| DRR | voice | 90000 | 35.75 | 55.0 | 59.3 | 1.4 | 4903 | FAIL |
| DRR | video | 7105 | 8.05 | 75.9 | 96.7 | 4.4 | 3272 | FAIL |
| DRR | best_effort | 7483 | 48.82 | 165.6 | 197.2 | 7.3 | 1643 | - |
| EPS (proposed) | emergency | 3200 | 0.00 | 5.4 | 6.1 | 0.2 | 220 | PASS |
| EPS (proposed) | voice | 90000 | 20.07 | 82.4 | 219.8 | 54.1 | 6100 | FAIL |
| EPS (proposed) | video | 7105 | 0.07 | 40.5 | 101.5 | 4.5 | 3556 | PASS |
| EPS (proposed) | best_effort | 7483 | 89.08 | 182.6 | 220.3 | 2.8 | 149 | - |

### TC9 - Lossy link (2 % random loss, moderate load)

Isolates link loss from congestion loss; delay must be unaffected.

| Scheduler | Class | Sent | Loss % | Delay avg ms | p99 ms | Jitter ms | Thr kbps | SLA |
|---|---|---:|---:|---:|---:|---:|---:|:--:|
| FIFO | emergency | 3200 | 2.50 | 50.9 | 104.2 | 10.4 | 215 | FAIL |
| FIFO | voice | 20000 | 2.24 | 32.9 | 103.3 | 6.8 | 1658 | FAIL |
| FIFO | video | 7097 | 3.47 | 33.6 | 103.5 | 3.0 | 3431 | FAIL |
| FIFO | best_effort | 8286 | 4.04 | 37.6 | 104.4 | 1.7 | 3739 | - |
| Strict PQ | emergency | 3200 | 1.97 | 5.5 | 6.3 | 0.4 | 216 | FAIL |
| Strict PQ | voice | 20000 | 2.06 | 5.7 | 6.5 | 0.4 | 1661 | FAIL |
| Strict PQ | video | 7097 | 2.33 | 9.8 | 30.9 | 1.7 | 3472 | FAIL |
| Strict PQ | best_effort | 8286 | 12.95 | 35.9 | 122.9 | 3.5 | 3352 | - |
| WFQ | emergency | 3200 | 1.94 | 5.6 | 6.4 | 0.4 | 216 | FAIL |
| WFQ | voice | 20000 | 2.18 | 5.7 | 7.1 | 0.4 | 1659 | FAIL |
| WFQ | video | 7097 | 2.28 | 13.1 | 50.7 | 2.6 | 3473 | FAIL |
| WFQ | best_effort | 8286 | 11.73 | 34.5 | 105.5 | 3.4 | 3402 | - |
| DRR | emergency | 3200 | 1.47 | 6.5 | 9.7 | 1.1 | 217 | FAIL |
| DRR | voice | 20000 | 2.32 | 6.5 | 9.4 | 1.2 | 1657 | FAIL |
| DRR | video | 7097 | 2.17 | 13.0 | 50.8 | 2.5 | 3477 | FAIL |
| DRR | best_effort | 8286 | 11.65 | 34.2 | 105.0 | 3.4 | 3408 | - |
| EPS (proposed) | emergency | 3200 | 2.09 | 5.5 | 6.3 | 0.4 | 216 | FAIL |
| EPS (proposed) | voice | 20000 | 2.09 | 5.7 | 6.5 | 0.4 | 1661 | FAIL |
| EPS (proposed) | video | 7097 | 2.21 | 15.3 | 61.6 | 3.0 | 3476 | FAIL |
| EPS (proposed) | best_effort | 8286 | 8.00 | 47.0 | 148.7 | 3.4 | 3569 | - |
