"""Six code mutants: normal same-input pass, exact first FAIL want, then CAUGHT."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import test_s2_step3_contract as T
from s2_stage_gate import verdict as normal_stage
from s2_connect_check import check_arrays as normal_connection


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check(label, condition):
    if not condition:
        raise AssertionError(label)


def run_case(name, want, normal, mutant, output):
    normal()
    (output / f"{name}.normal.log").write_text("PASS " + want + "\n", encoding="utf-8")
    try:
        mutant()
    except AssertionError as ex:
        first = str(ex)
        (output / f"{name}.mutant.log").write_text("FAIL " + first + "\nAssertionError: " + first + "\n", encoding="utf-8")
    else:
        first = None
        (output / f"{name}.mutant.log").write_text("NOT_CAUGHT\n", encoding="utf-8")
    caught = first == want
    print(("CAUGHT" if caught else "NOT_CAUGHT"), name, "first", first, "want", want, flush=True)
    return {"name": name, "want": want, "first_failed": first, "normal_exit": 0,
            "mutant_exit": 1 if first else 0, "caught": caught}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=False)
    meta, arrays, criteria = T.fixture()
    cases = []
    for key, mutate_data, label in (
        ("grid_order_or_yaw", lambda x: x["ray_hits_w"].__setitem__((0, 0, 0, 0, 0), 9.), "grid order gate"),
        ("height_or_offset", lambda x: x["height"].__setitem__((0, 0, 0, 0), 1.), "height offset gate"),
    ):
        bad = copy.deepcopy(arrays)
        mutate_data(bad)
        source = (HERE / "s2_connect_check.py").read_text(encoding="utf-8")
        anchor = '    return {"verdict": "PASS" if not reasons else "HOLD"'
        assert source.count(anchor) == 1
        source = source.replace(anchor, f'    reasons = [x for x in reasons if x != "{key}"]\n' + anchor)
        path = a.out / f"mutant_{key}.py"
        path.write_text(source, encoding="utf-8")
        module = load_module(path, f"s2_connect_mutant_{key}")
        cases.append(run_case(key, label,
            lambda k=key, b=bad, w=label: check(w, k in normal_connection(meta, b, criteria)["reasons"]),
            lambda k=key, b=bad, w=label, m=module: check(w, k in m.check_arrays(meta, b, criteria)["reasons"]), a.out))
    source = (HERE / "s2_connect_diag.py").read_text(encoding="utf-8")
    anchor = "            last = provider.sample()"
    assert source.count(anchor) == 1
    mutant_source = source.replace(anchor, "            last = first")
    path = a.out / "mutant_capture.py"
    path.write_text(mutant_source, encoding="utf-8")
    capture_mutant = load_module(path, "s2_capture_mutant")
    from s2_connect_diag import capture as normal_capture
    from s2_env_config import EnvironmentSpec
    class Provider:
        def __init__(self, kind, spec, yaw):
            self.case, self.t = T.CASES.index(kind), 0
        def reset(self): self.t = 0
        def step_zero(self): self.t = 1
        def sample(self):
            row = {k: arrays[k][self.case, self.t].copy() for k in
                   ("pos_w", "ray_hits_w", "root_pos_w", "root_quat_w", "env_origin_w",
                    "height", "mask", "episode_ids", "frame_tokens")}
            row["reset_receipt"] = arrays["reset_receipt"][self.case].copy()
            return row
        def close(self): pass
    spec = EnvironmentSpec(11, 1, .1, .2, .1, .5, .01)
    def capture_matches(fn):
        got = fn(Provider, spec=spec, steps=4, reset_yaw_rad=1.57)
        return all(np.array_equal(got[k], arrays[k]) for k in arrays)
    cases.append(run_case("capture_time", "diagnostic capture two instants",
                          lambda: check("diagnostic capture two instants", capture_matches(normal_capture)),
                          lambda: check("diagnostic capture two instants", capture_matches(capture_mutant.capture)), a.out))
    with __import__("tempfile").TemporaryDirectory(prefix="s2_mutant_stage_") as tmp:
        root = Path(tmp)
        manifest, conn = T.stage_fixture(root, meta, arrays, criteria)
        connect = normal_stage(manifest, "connect", conn, now_epoch=100.)
        train = T.train_record(root, connect)
        for key, stage, bad_record, bad_manifest, previous, label in (
            ("approval_unbound", "smoke", copy.deepcopy(train), copy.deepcopy(manifest), connect, "approval binding gate"),
            ("artifact_hash", "smoke", copy.deepcopy(train), copy.deepcopy(manifest), connect, "artifact hash gate"),
            ("step_count", "smoke", copy.deepcopy(train), copy.deepcopy(manifest), connect, "optimizer step count gate"),
            ("connect_hold", "connect", copy.deepcopy(conn), copy.deepcopy(manifest), None, "connection verdict gate"),
        ):
            if key == "approval_unbound":
                bad_manifest["approval"]["status"] = "UNDECIDED"
            elif key == "artifact_hash":
                bad_record["artifacts"]["A_log"]["sha256"] = "0"*64
            elif key == "step_count":
                rp = root / "bad_step.json"
                x = T.train_result("A")
                x["optimizer_steps_actual"] = 7
                rp.write_text(json.dumps(x), encoding="utf-8")
                from s2_stage_gate import digest
                bad_record["artifacts"]["A_result"] = {"path": str(rp), "sha256": digest(rp)}
            elif key == "connect_hold":
                bad_meta = copy.deepcopy(meta)
                bad_meta["driver_version"] = None
                bad_root = root / "bad_connect"
                T.write_capture(bad_root, bad_meta, arrays)
                from s2_stage_gate import digest
                for artifact, file in (("connect_meta", "meta.json"), ("connect_npz", "capture.npz")):
                    p = bad_root / file
                    bad_record["artifacts"][artifact] = {"path": str(p), "sha256": digest(p)}
            source = (HERE / "s2_stage_gate.py").read_text(encoding="utf-8")
            anchor = "    reasons = sorted(reasons)"
            assert source.count(anchor) == 1
            source = source.replace(anchor, f'    reasons = [x for x in reasons if x != "{key}"]\n' + anchor)
            path = a.out / f"mutant_{key}.py"
            path.write_text(source, encoding="utf-8")
            module = load_module(path, f"s2_stage_mutant_{key}")
            cases.append(run_case(key, label,
                lambda k=key, s=stage, r=bad_record, m=bad_manifest, p=previous, w=label:
                    check(w, k in normal_stage(m, s, r, previous=p, now_epoch=100.)["reasons"]),
                lambda k=key, s=stage, r=bad_record, m=bad_manifest, p=previous, w=label, mod=module:
                    check(w, k in mod.verdict(m, s, r, previous=p, now_epoch=100.)["reasons"]), a.out))
    # STOP mutation uses the same CPU dry path, with a pre-existing STOP file.
    import test_s2_step3_entry as E
    from s2_train_entry import execute as normal_execute
    source = (HERE / "s2_train_entry.py").read_text(encoding="utf-8")
    anchor = "                if Path(a.stop_file).exists():"
    assert source.count(anchor) == 1
    mutant_source = source.replace(anchor, "                if False and Path(a.stop_file).exists():")
    path = a.out / "mutant_stop.py"
    path.write_text(mutant_source, encoding="utf-8")
    mod = types.ModuleType("s2_train_mutant_stop")
    mod.__file__ = str(HERE / "s2_train_entry.py")
    exec(compile(mutant_source, str(path), "exec"), mod.__dict__)
    with tempfile.TemporaryDirectory(prefix="s2_stop_mutant_") as tmp:
        root = Path(tmp)
        stop = root / "STOP"
        stop.write_text("stop", encoding="utf-8")
        def stops(fn, name):
            result = fn(E.args(root / name, stop=stop), cpu_dry=True)
            return result["status"] == "HOLD" and result["stop_reason"] == "STOP file"
        cases.append(run_case("stop_file", "STOP before update holds",
                              lambda: check("STOP before update holds", stops(normal_execute, "normal")),
                              lambda: check("STOP before update holds", stops(mod.execute, "mutant")), a.out))
    shell = (HERE / "night_s2_chain_draft.sh").read_text(encoding="utf-8")
    assert shell.count("exit 99") >= 1
    mutant_shell = shell.replace("exit 99\n", "# removed mandatory stop\n", 1)
    (a.out / "mutant_shell.sh").write_text(mutant_shell, encoding="utf-8")
    def inert(value):
        lines = value.splitlines()
        return any(line.strip() == "exit 99" for line in lines[:5])
    cases.append(run_case("inert_shell", "draft inert exit99",
                          lambda: check("draft inert exit99", inert(shell)),
                          lambda: check("draft inert exit99", inert(mutant_shell)), a.out))
    summary = {"code_mutants": len(cases), "caught": sum(x["caught"] for x in cases), "records": cases}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if summary["caught"] == summary["code_mutants"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
