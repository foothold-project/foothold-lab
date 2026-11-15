"""CPU copy of real q result. Slot, log, USD and traceback checks use fixtures."""
import builtins
import copy
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
import time
from types import SimpleNamespace

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from s1043_manifest import sha256

SOURCE = Path(r"C:/isaac/ext/go2_rl_robotlab/_eval/out/cq_test_8d384fcb_g0t141025p134176_ka_orig")
SOURCE_SHA = "4c4bed8364cf6cc1c873585dc895ec1fee99ab1bc699cf71bed9c19a834bb093"


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label, flush=True)
    if not condition:
        raise AssertionError(label)


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    driver = Path(os.environ.get("S1043_DRIVER_OVERRIDE", HERE / "cmdr_eval_driver_s1043.py"))
    old = sys.argv
    try:
        sys.argv = [str(driver), "--manifest", str(HERE / "manifest_s1043.json"),
                    "--expect_self_sha", sha256(driver), "--cpu_plan"]
        g = runpy.run_path(str(driver), run_name="fingerprint_17t_cpu_probe")["diagnostic_record"].__globals__
    finally:
        sys.argv = old
    fixture = ROOT / "fixture_17t_fingerprint" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    data = fixture / "data"
    data.mkdir(parents=True, exist_ok=False)
    tag = SOURCE.name
    shutil.copytree(SOURCE, data / tag)
    meta_path = data / tag / "meta.json"
    check("original meta copy SHA256", sha256(meta_path) == SOURCE_SHA)
    guard_source = SOURCE.parent / f"{tag}.guard.json"
    shutil.copy2(guard_source, data / f"{tag}.guard.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    g["OUT"] = str(data)
    g["GPU"] = "0"
    g["GPU_UUID"] = meta["devices"]["torch_cuda0_uuid"]
    g["log_done"] = lambda *a: ""
    g["usd_check"] = lambda *a: ""
    g["py_traceback"] = lambda *a: False
    slot = {"slot_rc": 0, "registry": g["CONTRACT"]["paths"]["registry"],
            "lock": g["CONTRACT"]["paths"]["convert_lock"],
            "expect_conversions": g["CONTRACT"]["device"]["expect_conversions"],
            "usd_root": g["CONTRACT"]["paths"]["work"]}
    def open_file(path, *args, **kwargs):
        if str(path).endswith(".slot.json"):
            stream = io.StringIO(json.dumps(slot))
            stream.name = str(path)
            return stream
        return builtins.open(path, *args, **kwargs)
    g["open"] = open_file
    original_load = json.load
    def load(stream, *args, **kwargs):
        result = original_load(stream, *args, **kwargs)
        if str(getattr(stream, "name", "")).endswith("meta.json"):
            result = copy.deepcopy(result)
            result["args"]["outdir"] = str(data)
        return result
    g["json"] = SimpleNamespace(load=load, loads=json.loads)
    ck = meta["checkpoint_sha256"]
    def validated():
        return g["validate"](tag, ck, 20000, "flat", ["stop03"], 100, True, 1000,
                             False, need_iter=False, small=True)
    item = {"evaluator": "q_eval.py", "small": True}
    def recorded(key):
        return g["diagnostic_record"](key, item, tag, 0, 1, validated())
    check("copied original validate", validated() == "")
    good = recorded("orig")
    check("original fingerprint valid", good["status"] == "valid" and good["fingerprint"] and
          good["fingerprint"]["env_origins"] and good["fingerprint"]["layout"])
    evidence = data / tag / "env_origins.npy"
    parked = data / tag / "env_origins.held.npy"
    evidence.rename(parked)
    try:
        check("validate unaffected by missing fingerprint file", validated() == "")
        missing = recorded("orig")
        check("missing fingerprint held", missing["status"] == "held" and
              "required fingerprint" in missing["why"] and missing["fingerprint"] is None)
        repeat = recorded("orig_repeat")
        check("repeat missing fingerprint held", repeat["status"] == "held" and
              repeat["why"] and repeat["fingerprint"] is None)
    finally:
        parked.rename(evidence)
    check("restored fingerprint valid", recorded("orig")["status"] == "valid")


if __name__ == "__main__":
    main()
