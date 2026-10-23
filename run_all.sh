#!/bin/sh
# Full reproduction: unit + scenario tests, all simulations, reports, pcaps, live demo.
set -e
cd "$(dirname "$0")"
python3 -m unittest tests.test_qos
python3 run_simulation.py --scenario all
python3 run_simulation.py --scenario tc2 --quiet --pcap results/tc2_eps.pcap  --pcap-scheduler eps
python3 run_simulation.py --scenario tc2 --quiet --pcap results/tc2_fifo.pcap --pcap-scheduler fifo
python3 tools/pcap_verify.py results/tc2_eps.pcap  | tee results/pcap_verify_tc2_eps.txt
python3 tools/pcap_verify.py results/tc2_fifo.pcap | tee results/pcap_verify_tc2_fifo.txt
python3 live/run_live_demo.py --duration 8
echo "Open results/report_all.html in a browser."
