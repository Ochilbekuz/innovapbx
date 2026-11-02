#!/bin/sh
set -e
python3 /sippcfg/register_only.py innova-smoke-ast 5060 5090 t1-101 TestSecret12345 3600
exec sipp -sf /sippcfg/uas_only.xml -i 0.0.0.0 -p 5090 -m 1 -trace_screen -trace_msg -timeout 30s innova-smoke-ast:5060
