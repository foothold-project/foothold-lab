"""Detached run receipt for the October 24 experiments; never kills a process."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone


def stamp():
    return datetime.now(timezone.utc).isoformat()


def main():
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    out = Path(config["output"])
    out.mkdir(parents=True, exist_ok=False)
    (out / "launch.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    state = {"started_at": stamp(), "supervisor_pid": os.getpid(), "state": "starting"}

    def save():
        state["heartbeat_at"] = stamp()
        tmp = out / "process.tmp"
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(tmp, out / "process.json")

    save()
    env = os.environ.copy()
    for key in config.get("unset_env", []):
        env.pop(key, None)
    env.update(config.get("env", {}))
    try:
        with (out / "run.log").open("wb") as stream:
            child = subprocess.Popen(config["argv"], cwd=config["cwd"], env=env,
                                     stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
            state.update(state="running", child_pid=child.pid)
            save()
            while child.poll() is None:
                time.sleep(5)
                save()
            state.update(state="exited", returncode=child.returncode, ended_at=stamp())
            save()
            return child.returncode
    except BaseException as exc:
        state.update(state="supervisor_error", error=repr(exc), ended_at=stamp())
        save()
        raise


if __name__ == "__main__":
    sys.exit(main())
