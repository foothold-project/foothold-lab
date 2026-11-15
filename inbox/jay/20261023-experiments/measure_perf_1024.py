"""Run the explicitly listed short checks sequentially and record GPU samples.

This helper never changes training settings or kills a process. Configurations
are separate frozen JSON files consumed by run_process_1024.py.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    output = Path(spec["output"])
    output.mkdir(parents=True, exist_ok=False)
    state = {"state": "starting", "checks": []}

    def save():
        state["heartbeat_at"] = datetime.now(timezone.utc).isoformat()
        temporary = output / "status.tmp"
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temporary.replace(output / "status.json")

    for config in spec["configs"]:
        entry = {"config": config, "started_at": datetime.now(timezone.utc).isoformat()}
        state["checks"].append(entry)
        state["state"] = "running"
        with (output / (Path(config).stem + ".log")).open("wb") as log:
            child = subprocess.Popen([spec["python"], "-B", spec["supervisor"], config],
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            entry["supervisor_pid"] = child.pid
            save()
            with (output / (Path(config).stem + "_gpu.jsonl")).open("w", encoding="utf-8") as samples:
                while child.poll() is None:
                    sample = {"at": datetime.now(timezone.utc).isoformat()}
                    try:
                        result = subprocess.run([
                            "nvidia-smi", "--query-gpu=pci.bus_id,memory.used,memory.free,utilization.gpu",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
                        sample.update(returncode=result.returncode, rows=result.stdout.splitlines())
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        sample["error"] = type(exc).__name__
                    samples.write(json.dumps(sample) + "\n")
                    samples.flush()
                    save()
                    time.sleep(1)
            entry.update(returncode=child.returncode, ended_at=datetime.now(timezone.utc).isoformat())
        if child.returncode:
            state["state"] = "failed"
            save()
            return child.returncode
    state["state"] = "completed"
    save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
