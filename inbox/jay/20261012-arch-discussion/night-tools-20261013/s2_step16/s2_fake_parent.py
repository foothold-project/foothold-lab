"""CPU test parent. The test may terminate this process that it created itself."""
import argparse
import time
from pathlib import Path

from s2_chain_runner import launch_detached_cpu_fixture

ap = argparse.ArgumentParser()
for arg in ("manifest", "approval", "fixture_plan", "status", "log", "pid_file"):
    ap.add_argument("--" + arg.replace("_", "-"), type=Path, required=True)
a = ap.parse_args()
child = launch_detached_cpu_fixture(script=Path(__file__).with_name("s2_chain_runner.py"),
                                    manifest=a.manifest, approval=a.approval,
                                    fixture_plan=a.fixture_plan, status=a.status, log=a.log)
a.pid_file.write_text(str(child.pid), encoding="ascii")
time.sleep(30)
