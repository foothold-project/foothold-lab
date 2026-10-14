"""CPU probe of original q metadata. It reads the source result without writes.

Slot, log_done, usd_check, and py_traceback are virtualized. Passing this test
does not establish that the original log, USD, or traceback gates pass.
"""
import copy
import builtins
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import types

HERE = Path(__file__).parent
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
        ns = runpy.run_path(str(driver), run_name="original_cpu_probe")
    finally:
        sys.argv = old
    g = ns["validate"].__globals__
    tag = SOURCE.name
    # The copy preserves the exact evidence bytes. The validator reads the
    # original path in read-only mode so its recorded outdir still matches.
    with tempfile.TemporaryDirectory(dir=HERE.parent, prefix="17s_meta_copy_") as tmp:
        copy_path = Path(tmp) / "meta.json"
        copy_path.write_bytes((SOURCE / "meta.json").read_bytes())
        check("original meta copy SHA256", sha256(copy_path) == SOURCE_SHA)
    meta = json.loads((SOURCE / "meta.json").read_text(encoding="utf-8"))
    check("original lacks loaded_iter", "loaded_iter" not in meta)
    g["OUT"] = str(SOURCE.parent)
    g["GPU"] = "0"
    g["GPU_UUID"] = meta["devices"]["torch_cuda0_uuid"]
    g["log_done"] = lambda *a: ""
    g["usd_check"] = lambda *a: ""
    g["py_traceback"] = lambda *a: False
    original_load = json.load
    mutation = {"loaded_iter": None, "checkpoint_sha256": None}
    slot = {"slot_rc": 0, "registry": g["CONTRACT"]["paths"]["registry"],
            "lock": g["CONTRACT"]["paths"]["convert_lock"],
            "expect_conversions": g["CONTRACT"]["device"]["expect_conversions"],
            "usd_root": g["CONTRACT"]["paths"]["work"]}
    def read_file(path, *args, **kwargs):
        if str(path).endswith(".slot.json"):
            stream = io.StringIO(json.dumps(slot))
            stream.name = str(path)
            return stream
        return builtins.open(path, *args, **kwargs)
    g["open"] = read_file
    def load(stream, *args, **kwargs):
        if str(getattr(stream, "name", "")).endswith(".slot.json"):
            return slot
        result = original_load(stream, *args, **kwargs)
        if str(getattr(stream, "name", "")).endswith("meta.json"):
            result = copy.deepcopy(result)
            for key, value in mutation.items():
                if value is not None:
                    result[key] = value
        return result
    g["json"] = types.SimpleNamespace(load=load)
    ck = meta["checkpoint_sha256"]
    def validate(need_iter):
        return g["validate"](tag, ck, 20000, "flat", ["stop03"], 100, True, 1000,
                             False, need_iter=need_iter, small=True)
    first = validate(False)
    print("original validation reason", repr(first))
    check("original q meta accepted", first == "")
    mutation["loaded_iter"] = 20000
    check("original with explicit 20000 accepted", validate(False) == "")
    mutation["loaded_iter"] = 19999
    check("original wrong explicit iteration rejected", "loaded_iter" in validate(False))
    mutation["loaded_iter"] = None
    mutation["checkpoint_sha256"] = "0" * 64
    check("checkpoint SHA mutation rejected", validate(False) == "checkpoint sha256")
    mutation["checkpoint_sha256"] = None
    check("cmdr missing iteration rejected", "loaded_iter" in validate(True))


if __name__ == "__main__":
    main()
