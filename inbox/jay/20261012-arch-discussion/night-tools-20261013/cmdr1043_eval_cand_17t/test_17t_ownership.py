"""Deterministic psutil-table ownership probes. No real process is signalled."""
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from s1043_manifest import sha256


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label, flush=True)
    if not condition:
        raise AssertionError(label)


class StopProbe(Exception):
    pass


def driver_globals():
    driver = Path(os.environ.get("S1043_DRIVER_OVERRIDE", HERE / "cmdr_eval_driver_s1043.py"))
    old = sys.argv
    try:
        sys.argv = [str(driver), "--manifest", str(HERE / "manifest_s1043.json"),
                    "--expect_self_sha", sha256(driver), "--cpu_plan"]
        return runpy.run_path(str(driver), run_name="ownership_17t_cpu_probe")["wait_child_tree"].__globals__
    finally:
        sys.argv = old


def probe(g, mode):
    class NoSuchProcess(Exception):
        pass
    class AccessDenied(Exception):
        pass

    state = SimpleNamespace(round=0, signals=[], alive={100: True, 110: True, 300: True})

    class FakeProcess:
        def __init__(self, pid):
            self.pid = pid
            if mode == "parent_missing" and state.round >= 2 and pid == 110:
                raise NoSuchProcess()
            if mode == "child_access_denied" and pid == 110:
                raise AccessDenied()
            if pid not in state.alive:
                raise NoSuchProcess()
        def create_time(self):
            if mode == "pid_reuse" and state.round >= 2 and self.pid == 110:
                return 9.0
            return {100: 1.0, 110: 2.0, 300: 10.0}[self.pid]
        def is_running(self):
            return state.alive[self.pid]
        def status(self):
            return "running" if state.alive[self.pid] else "zombie"
        def kill(self):
            state.signals.append(("kill", self.pid))
            state.alive[self.pid] = False
        def terminate(self):
            state.signals.append(("terminate", self.pid))
            state.alive[self.pid] = False

    def ppid_map():
        state.round += 1
        if mode in ("pid_reuse", "parent_missing") and state.round == 1:
            return {100: 0, 110: 100}
        if mode == "child_access_denied":
            return {100: 0, 110: 100}
        return {100: 0, 110: 100, 300: 110}

    class FakeRoot:
        pid = 100
        def poll(self):
            return None if state.alive[100] else 0
        def wait(self):
            return 0

    g["psutil"] = SimpleNamespace(Process=FakeProcess, _ppid_map=ppid_map,
                                  NoSuchProcess=NoSuchProcess, AccessDenied=AccessDenied,
                                  STATUS_ZOMBIE="zombie")
    g["LOG"].pop("stopped", None)
    g["TREE_ABORT"][0] = None
    observations = []
    def observer(known, live):
        observations.append((known, live, dict(g["TREE_UNKNOWN"][0])))
        if mode != "normal" and state.round >= 3:
            raise StopProbe()
    try:
        rc = g["wait_child_tree"](FakeRoot(), poll_s=0, observer=observer,
                                  stop_check=lambda: state.round >= (2 if mode != "normal" else 1),
                                  terminate_grace_s=0)
        returned = True
    except StopProbe:
        rc = None
        returned = False
    return state, observations, rc, returned


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    g = driver_globals()
    state, observations, rc, returned = probe(g, "pid_reuse")
    check("PID reuse child never signalled", 300 not in [pid for _, pid in state.signals])
    check("PID reuse child not registered", all(300 not in known for known, _, _ in observations))
    check("PID reuse holds lease as unowned_unknown", not returned and
          300 in g["TREE_UNKNOWN"][0] and g["LOG"].get("stopped") == "unowned_unknown")
    state, observations, rc, returned = probe(g, "normal")
    check("normal parent descendant registered", any(300 in known for known, _, _ in observations))
    check("normal tree cleanup retained", returned and rc == 125 and
          {100, 110, 300}.issubset({pid for _, pid in state.signals}))
    state, observations, rc, returned = probe(g, "child_access_denied")
    check("access denied child never signalled", 110 not in [pid for _, pid in state.signals])
    check("access denied holds lease", not returned and 110 in g["TREE_UNKNOWN"][0])
    state, observations, rc, returned = probe(g, "parent_missing")
    check("missing parent child never signalled", 300 not in [pid for _, pid in state.signals])
    check("missing parent holds lease", not returned and 300 in g["TREE_UNKNOWN"][0])


if __name__ == "__main__":
    main()
