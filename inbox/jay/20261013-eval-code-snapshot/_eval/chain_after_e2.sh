#!/usr/bin/env bash
# Waits for E2 training (pid 173044) to end, records the E2 checkpoints, then runs the evaluation list on GPU 0
# and the replay videos on GPU 1. Declared 2026-10-12 (no training; GPU 0 only after E2 has ended).
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
E2=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-11_12-39-32_e2_seed43_n8192
while tasklist //FI "PID eq 173044" 2>/dev/null | grep -q 173044; do sleep 30; done
echo "E2 PROCESS ENDED $(date +%H:%M:%S)"
tail -c 600 C:/isaac/ext/go2_rl_robotlab/_runs/e2_seed43_n8192.log > out/e2_log_tail.txt
"$PY" - <<'EOF'
import hashlib, json, os, glob
d = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-11_12-39-32_e2_seed43_n8192"
out = {"checkpoints": {}, "agent_yaml": open(os.path.join(d, "params", "agent.yaml"), encoding="utf-8").read()[:2000]}
for it in (5000, 10000, 15000, 19500, 20000, 20499):
    p = os.path.join(d, f"model_{it}.pt")
    if os.path.exists(p):
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        out["checkpoints"][it] = {"sha256": h, "bytes": os.path.getsize(p)}
    else:
        out["checkpoints"][it] = None
json.dump(out, open("out/e2_ckpt_check.json", "w"), indent=1)
print("E2 checkpoints:", {k: (v["sha256"][:12] if v else None) for k, v in out["checkpoints"].items()})
EOF
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
if [ ! -f "$E2/model_20499.pt" ]; then echo "STOP: model_20499.pt missing"; exit 3; fi
GPU=0 bash run_e2.sh e1fr || exit $?
GPU=0 bash run_e2.sh e2q || exit $?
GPU=0 bash run_e2.sh e2c || exit $?
GPU=0 bash run_e2.sh e2d1 || exit $?
GPU=0 bash run_e2.sh e2qd || exit $?
echo "CHAIN DONE $(date +%H:%M:%S)"
