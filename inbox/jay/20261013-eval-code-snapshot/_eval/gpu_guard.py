# Run one command while sampling GPU memory every 200 ms; stop the command (and its process tree) if the free
# memory of the watched GPU drops below the floor. The sampler lives in this process, so it ends with the run.
# Usage: python gpu_guard.py --gpu 1 --min_free_mib 4096 --log out/x.log --summary out/x.guard.json -- <command ...>
# Exit code: the command's exit code, or 99 when the guard stopped it.
import argparse
import json
import subprocess
import sys
import time

import psutil
import pynvml

ap = argparse.ArgumentParser()
ap.add_argument("--gpu", type=int, default=1, help="nvidia-smi / NVML index (PCI bus order)")
ap.add_argument("--min_free_mib", type=int, default=4096)
ap.add_argument("--interval", type=float, default=0.2)
ap.add_argument("--log", required=True)
ap.add_argument("--summary", required=True)
ap.add_argument("cmd", nargs=argparse.REMAINDER)
a = ap.parse_args()
cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
pynvml.nvmlInit()
h = pynvml.nvmlDeviceGetHandleByIndex(a.gpu)
uuid = pynvml.nvmlDeviceGetUUID(h)
uuid = uuid.decode() if isinstance(uuid, bytes) else uuid
t0 = time.time()
logf = open(a.log, "w", encoding="utf-8")
p = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
min_free, max_used, n, stopped, stop_info = 10 ** 9, 0, 0, False, None
while p.poll() is None:
    m = pynvml.nvmlDeviceGetMemoryInfo(h)
    free, used = m.free // 2 ** 20, m.used // 2 ** 20
    n += 1
    min_free, max_used = min(min_free, free), max(max_used, used)
    if free < a.min_free_mib:
        stopped = True
        stop_info = {"t_s": round(time.time() - t0, 2), "free_mib": int(free), "used_mib": int(used)}
        try:
            parent = psutil.Process(p.pid)
            for c in parent.children(recursive=True):
                c.kill()
            parent.kill()
        except psutil.NoSuchProcess:
            pass
        break
    time.sleep(a.interval)
rc = p.wait()
logf.close()
s = {"cmd": cmd, "gpu_index": a.gpu, "gpu_uuid": uuid, "min_free_floor_mib": a.min_free_mib, "samples": n, "interval_s": a.interval,
     "min_free_mib": int(min_free), "max_used_mib": int(max_used), "stopped_by_guard": stopped, "stop": stop_info,
     "exit_code": rc, "wall_s": round(time.time() - t0, 1)}
json.dump(s, open(a.summary, "w"), indent=1)
pynvml.nvmlShutdown()
print(f"GUARD rc={rc} stopped={stopped} min_free={min_free} MiB max_used={max_used} MiB samples={n} wall={s['wall_s']}s")
sys.exit(99 if stopped else rc)
