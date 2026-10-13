# -*- coding: utf-8 -*-
"""run_dump.py (실행기) · validate_dump.py (검증기) 시험 (CPU · Isaac · GPU 없이).

분류: A/평가 · CE12-v1 이식 진단 1 · 실행기 · 검증기 시험
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 19:03
근거: lead 지시 10/13 19:03 · _eval/test_isaac_slot.py · test_usd_isolate.py 의 가짜 자식 방식 (읽기만)
요지: RT 는 실제 isaac_slot.py · usd_isolate_run.py 에 가짜 gpu_guard · 가짜 기록기 (가짜 isaaclab 변환기 포함) 를 물려 실행기를 끝까지 돌린다.
      VT 는 올바른 가짜 기록을 만든 뒤 결함을 하나씩 넣어 그 검사 하나만 걸리는지 본다.
상태: 시험 파일. 모든 파일은 임시 폴더 (CE12_EVAL_ROOT) 에만 쓴다. 실제 _eval/slot 의 잠금 · 기록 · out_* 를 건드리지 않는다.

실행: C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe test_run_dump.py [RT|VT|시험이름 ...]
      CE12_RUN_DUMP · CE12_VALIDATE 로 변이 사본을 시험시킬 수 있다 (mutate_run_dump.py).
"""
import os
import sys

sys.dont_write_bytecode = True
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
RUN = os.environ.get("CE12_RUN_DUMP", os.path.join(HERE, "run_dump.py"))
VAL = os.environ.get("CE12_VALIDATE", os.path.join(HERE, "validate_dump.py"))
TMP = tempfile.mkdtemp(prefix="ce12_run_").replace("\\", "/")
ROOT = f"{TMP}/eval"
NATIVE = f"{ROOT}/out_ce12/native"
os.environ["CE12_EVAL_ROOT"] = ROOT
TESTS = []

CONV = '''
import os, random
from datetime import datetime
class AssetConverterBase:
    def __init__(self, cfg):
        if cfg.usd_dir is None:
            self._usd_dir = f"{os.environ['FAKE_TMP']}/IsaacLab/usd_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randrange(10000)}"
        else:
            self._usd_dir = cfg.usd_dir
        os.makedirs(self._usd_dir, exist_ok=True)
'''
GUARD = '''
import argparse, json, os, subprocess, sys
ap = argparse.ArgumentParser()
ap.add_argument("--gpu", type=int, default=1); ap.add_argument("--min_free_mib", type=int, default=4096)
ap.add_argument("--interval", type=float, default=0.2); ap.add_argument("--log", required=True); ap.add_argument("--summary", required=True)
ap.add_argument("cmd", nargs=argparse.REMAINDER)
a = ap.parse_args()
cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
logf = open(a.log, "w", encoding="utf-8")
rc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT).wait()
logf.close()
json.dump({"cmd": cmd, "gpu_index": a.gpu, "min_free_floor_mib": a.min_free_mib, "exit_code": rc, "stopped_by_guard": False,
           "fake": True, "cvd": os.environ.get("CUDA_VISIBLE_DEVICES")}, open(a.summary, "w"))
sys.exit(rc)
'''
DUMP = '''
import argparse, hashlib, json, os, shutil, sys, time
ap = argparse.ArgumentParser()
ap.add_argument("--headless", action="store_true"); ap.add_argument("--checkpoint", required=True)
ap.add_argument("--tag", required=True); ap.add_argument("--outdir", required=True)
a, rest = ap.parse_known_args()
which = "cts" if os.path.basename(__file__) == "dump_native_cts.py" else "v2"
mode = os.environ.get("FAKE_MODE", "ok")
print("[fake dump] start", which, rest, flush=True)
if mode != "noimport":
    from isaaclab.sim.converters.asset_converter_base import AssetConverterBase
    if which == "cts" or mode == "convert":
        class Cfg:
            usd_dir = None
            asset_path = "go2.urdf"
        c = AssetConverterBase(Cfg())
        print("[INFO]: USD written to " + c._usd_dir + "/go2.usd", flush=True)
print("[INFO]: Time taken for scene creation: 0.5 s", flush=True)
time.sleep(0.3)
if mode == "traceback":
    print("Traceback (most recent call last):", flush=True)
    sys.exit(1)
out = os.path.join(a.outdir, a.tag)
os.makedirs(out)
shutil.copy(os.environ["FAKE_NPZ_" + which.upper()], os.path.join(out, "native.npz"))
h = hashlib.sha256(open(a.checkpoint, "rb").read()).hexdigest()
json.dump({"model": "cts_student" if which == "cts" else "v2", "args": {"tag": a.tag}, "checkpoint": os.path.abspath(a.checkpoint),
           "checkpoint_sha256": h, "t_start": time.strftime("%Y-%m-%d %H:%M:%S")}, open(os.path.join(out, "meta.json"), "w"))
json.dump({"fake": True}, open(os.path.join(out, "signature.json"), "w"))
print("[CE12-DUMP] done " + a.tag + " N 3 T 4 out " + out, flush=True)
'''


def test(tid, group):
    def deco(fn):
        TESTS.append((tid, group, fn))
        return fn
    return deco


# ------------------------------------------------------------------ 준비 (임시 폴더에만)
os.makedirs(f"{TMP}/pkg/isaaclab/sim/converters")
for d in ("isaaclab", "isaaclab/sim", "isaaclab/sim/converters"):
    open(f"{TMP}/pkg/{d}/__init__.py", "w").close()
open(f"{TMP}/pkg/isaaclab/sim/converters/asset_converter_base.py", "w").write(CONV)
os.makedirs(f"{TMP}/fake")
open(f"{TMP}/fake/gpu_guard.py", "w").write(GUARD)
for n in ("dump_native_cts.py", "dump_native_v2.py"):
    open(f"{TMP}/fake/{n}", "w").write(DUMP)
CKPT = f"{TMP}/ckpt/model_1.pt"
os.makedirs(os.path.dirname(CKPT))
open(CKPT, "wb").write(os.urandom(4096))
NPZ = {}


def fake_npz():
    """test_adapters.make_fake_dump 로 형식이 맞는 npz 두 개 (cts · v2)."""
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    sp = importlib.util.spec_from_file_location("ce12_test_adapters", os.path.join(HERE, "test_adapters.py"))
    ta = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(ta)
    d = f"{TMP}/npz"
    os.makedirs(d, exist_ok=True)
    for which, model in (("cts", "cts_student"), ("v2", "v2")):
        p, _, _ = ta.make_fake_dump(model, d, T=4, N=3)
        NPZ[which] = p.replace("\\", "/")


def env_run(mode="ok"):
    return dict(os.environ, PYTHONPATH=f"{TMP}/pkg", FAKE_TMP=f"{TMP}/faketmp", PYTHONIOENCODING="utf-8", FAKE_MODE=mode,
                CE12_EVAL_ROOT=ROOT, CE12_GUARD=f"{TMP}/fake/gpu_guard.py", CE12_DUMP_DIR=f"{TMP}/fake",
                CE12_PY_CTS=sys.executable, CE12_PY_V2=sys.executable, FAKE_NPZ_CTS=NPZ["cts"], FAKE_NPZ_V2=NPZ["v2"])


def run_dump(args, mode="ok"):
    r = subprocess.run([sys.executable, RUN] + args, capture_output=True, text=True, env=env_run(mode), encoding="utf-8",
                       errors="replace", timeout=300)
    m = re.search(r"attempt (\S+)", r.stdout)
    return r.returncode, r.stdout + r.stderr, (m.group(1) if m else None)


def dry(args):
    rc, out, att = run_dump(args + ["--dry_run"])
    j = json.loads(out[out.index("{"):out.rindex("}") + 1]) if "{" in out else {}
    return rc, j, att


_V = {}


def V():
    if "m" not in _V:
        sp = importlib.util.spec_from_file_location("ce12_validate_under_test", VAL)
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        _V["m"] = m
    return _V["m"]


class _A:
    def __init__(self, which, tag, attempt, allow=True):
        self.which, self.tag, self.attempt, self.checkpoint, self.allow_overrides = which, tag, attempt, CKPT, allow
        self.stamp = False


def failed(which, tag, attempt, allow=True):
    R, _ = V().check(_A(which, tag, attempt, allow))
    return sorted(n for n, ok, _d in R if not ok), [n for n, _o, _d in R]


def validate_cli(which, tag, attempt, extra=()):
    r = subprocess.run([sys.executable, VAL, "--which", which, "--tag", tag, "--checkpoint", CKPT, "--attempt", attempt] + list(extra),
                       capture_output=True, text=True, env=dict(os.environ, CE12_EVAL_ROOT=ROOT, PYTHONIOENCODING="utf-8"),
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout


# ================================================================== RT · 실행기
@test("RT1", "RT")
def rt1():
    rc, j, att = dry(["--which", "cts", "--checkpoint", CKPT, "--tag", "c1"])
    assert rc == 0, rc
    assert att and re.fullmatch(r"c1-\d{8}-\d{6}-\d+", att), att
    assert not os.path.exists(f"{ROOT}/out_ce12"), "dry_run 이 무언가를 만들었다"
    c = j["cmd"]
    i_slot = next(i for i, x in enumerate(c) if x.endswith("/isaac_slot.py"))
    assert os.path.normcase(c[i_slot]) == os.path.normcase(os.path.join(EVAL, "isaac_slot.py").replace("\\", "/")), c[i_slot]
    kv = {c[i]: c[i + 1] for i in range(i_slot + 1, c.index("--", i_slot)) if c[i].startswith("--")}
    assert kv["--attempt"] == att and kv["--usd_root"] == f"{NATIVE}/_attempts/{att}/usd", kv
    assert kv["--watch_log"] == f"{NATIVE}/c1.log" and kv["--record"] == f"{NATIVE}/c1.slot.json", kv
    assert kv["--lock"] == f"{ROOT}/slot/isaac_convert.lock" and kv["--registry"] == f"{ROOT}/slot/isaac_usd_registry.json", kv
    assert kv["--scan_dirs"].split(",") == [f"{ROOT}/out_ce12/native", f"{ROOT}/out_branch", f"{ROOT}/out_uncr", f"{ROOT}/out_rand"], kv
    assert kv["--stop_file"] == f"{ROOT}/out_ce12/STOP" and float(kv["--deadline"]) == 0.0, kv
    i_g = next(i for i, x in enumerate(c) if x.endswith("/gpu_guard.py"))
    g = {c[i]: c[i + 1] for i in range(i_g + 1, c.index("--", i_g)) if c[i].startswith("--")}
    assert g == {"--gpu": "1", "--min_free_mib": "4096", "--log": f"{NATIVE}/c1.log", "--summary": f"{NATIVE}/c1.guard.json"}, g
    rest = c[c.index("--", i_g) + 1:]
    assert rest[1].endswith("/usd_isolate_run.py") and rest[2].endswith("/dump_native_cts.py"), rest
    assert rest[rest.index("--tag") + 1] == "c1" and rest[rest.index("--outdir") + 1] == NATIVE, rest
    assert j["env_set"]["CUDA_VISIBLE_DEVICES"] == "1" and j["env_set"]["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID", j["env_set"]
    assert "FOOTHOLD_USD_ROOT" not in j["env_set"], "cts 는 isaac_slot 이 USD 루트를 넘긴다"


@test("RT2", "RT")
def rt2():
    rc, j, att = dry(["--which", "v2", "--checkpoint", CKPT, "--tag", "v1", "--gpu", "0", "--min_free_mib", "2048"])
    assert rc == 0, rc
    c = j["cmd"]
    assert not any(x.endswith("isaac_slot.py") for x in c), "v2 에 slot 이 있다"
    assert c[1].endswith("/gpu_guard.py"), c[:3]
    rest = c[c.index("--") + 1:]
    assert rest[1].endswith("/usd_isolate_run.py") and rest[2].endswith("/dump_native_v2.py"), rest
    assert j["env_set"]["FOOTHOLD_USD_ROOT"] == f"{NATIVE}/_attempts/{att}/usd", j["env_set"]
    assert j["env_set"]["CUDA_VISIBLE_DEVICES"] == "0" and c[c.index("--min_free_mib") + 1] == "2048"


@test("RT3", "RT")
def rt3():
    os.makedirs(f"{NATIVE}/taken")
    try:
        rc, out, _ = run_dump(["--which", "cts", "--checkpoint", CKPT, "--tag", "taken"])
        assert rc == 2 and "STOP" in out, (rc, out[-300:])
        assert not os.path.exists(f"{NATIVE}/_attempts") or not any(x.startswith("taken-") for x in os.listdir(f"{NATIVE}/_attempts"))
    finally:
        shutil.rmtree(f"{NATIVE}/taken")


@test("RT4", "RT")
def rt4():
    os.makedirs(NATIVE, exist_ok=True)
    for suf in (".log", ".slot.json", ".guard.json"):
        p = f"{NATIVE}/t4{suf}"
        open(p, "w").write("old")
        try:
            rc, out, _ = run_dump(["--which", "v2", "--checkpoint", CKPT, "--tag", "t4"])
            assert rc == 2 and "STOP" in out, (suf, rc)
            assert open(p).read() == "old", "옛 파일이 바뀌었다"
        finally:
            os.remove(p)


@test("RT5", "RT")
def rt5():
    sf = f"{TMP}/STOP"
    open(sf, "w").close()
    try:
        rc, out, att = run_dump(["--which", "v2", "--checkpoint", CKPT, "--tag", "t5", "--stop_file", sf])
        assert rc == 98, (rc, out[-300:])
        rj = json.load(open(f"{NATIVE}/_attempts/{att}/run.json", encoding="utf-8"))
        assert rj["state"].startswith("not launched") and not os.path.exists(f"{NATIVE}/t5") and not os.path.exists(f"{NATIVE}/t5.log"), rj
    finally:
        os.remove(sf)
    rc, out, att = run_dump(["--which", "cts", "--checkpoint", CKPT, "--tag", "t5b", "--deadline", str(time.time() - 10)])
    assert rc == 98 and not os.path.exists(f"{NATIVE}/t5b.log"), (rc, out[-300:])


@test("RT6", "RT")
def rt6():
    for args in (["--which", "cts", "--checkpoint", CKPT, "--tag", "../out/x"], ["--which", "cts", "--tag", "nockpt"],
                 ["--which", "cts", "--checkpoint", f"{TMP}/none.pt", "--tag", "miss"],
                 ["--which", "cts", "--checkpoint", CKPT, "--tag", "ex", "--", "--outdir", "C:/x"]):
        rc, out, _ = run_dump(args)
        assert rc == 2 and "STOP" in out, (args, rc, out[-200:])
    assert not os.path.exists(f"{ROOT}/out") and not os.path.exists(f"{NATIVE}/ex")


@test("RT7", "RT")
def rt7():
    rc, out, att = run_dump(["--which", "cts", "--checkpoint", CKPT, "--tag", "c7", "--", "--steps", "5"])
    assert rc == 0, (rc, out[-800:])
    s = json.load(open(f"{NATIVE}/c7.slot.json", encoding="utf-8"))
    assert (s["attempt"], s["slot_rc"], s["child_rc"], s["state_at_release"], len(s["usd_final"]), s["usd_outside_root"], s["conflicts"]) == \
        (att, 0, 0, "scene_built", 1, [], {}), s
    st = json.load(open(f"{NATIVE}/_attempts/{att}/usd/isolate_state.json", encoding="utf-8"))
    assert st["patched_by"] == "loader", st
    assert os.path.exists(f"{ROOT}/slot/isaac_usd_registry.json") and os.path.exists(f"{NATIVE}/c7/native.npz")
    assert "--steps" in s["cmd"] and not os.path.exists(f"{TMP}/faketmp"), "추가 인자 · 공용 폴더"
    rcv, o = validate_cli("cts", "c7", att, ["--allow_overrides", "--stamp"])
    assert rcv == 0 and "VALID c7" in o, o[-600:]
    stamp = json.load(open(f"{NATIVE}/c7/validate_stamp.json", encoding="utf-8"))
    assert stamp["attempt"] == att and {"npz", "meta", "log", "guard", "slot", "run"} <= set(stamp["sha256"]), stamp
    rcv, o = validate_cli("cts", "c7", att)
    assert rcv == 1 and "FAIL R2" in o and o.count("FAIL") == 1, o[-600:]


@test("RT8", "RT")
def rt8():
    rc, out, att = run_dump(["--which", "v2", "--checkpoint", CKPT, "--tag", "v8"])
    assert rc == 0, (rc, out[-800:])
    rj = json.load(open(f"{NATIVE}/_attempts/{att}/run.json", encoding="utf-8"))
    iso = rj["v2_isolation"]
    assert iso["patched_by"] == "loader" and iso["assigned_lines"] == 0 and iso["log_usd_folders"] == [], iso
    assert not os.path.exists(f"{NATIVE}/v8.slot.json")
    rcv, o = validate_cli("v2", "v8", att, ["--allow_overrides", "--stamp"])
    assert rcv == 0 and "VALID v8" in o, o[-600:]


@test("RT9", "RT")
def rt9():
    rc, out, att = run_dump(["--which", "v2", "--checkpoint", CKPT, "--tag", "v9"], mode="convert")
    assert rc == 93, (rc, out[-600:])
    rcv, o = validate_cli("v2", "v9", att, ["--allow_overrides"])
    assert rcv == 1 and "FAIL V3" in o and "FAIL V4" in o, o[-600:]


@test("RT10", "RT")
def rt10():
    rc, out, att = run_dump(["--which", "v2", "--checkpoint", CKPT, "--tag", "v10"], mode="noimport")
    assert rc == 92, (rc, out[-600:])
    rcv, o = validate_cli("v2", "v10", att, ["--allow_overrides"])
    assert rcv == 1 and "FAIL V2" in o, o[-600:]


@test("RT11", "RT")
def rt11():
    rc, out, att = run_dump(["--which", "cts", "--checkpoint", CKPT, "--tag", "c11"], mode="traceback")
    assert rc == 1, (rc, out[-600:])
    rcv, o = validate_cli("cts", "c11", att, ["--allow_overrides"])
    assert rcv == 1 and "FAIL S3" in o and "FAIL L1" in o, o[-600:]


# ================================================================== VT · 검증기 결함 하나씩
def make_valid(which, tag):
    att = f"{tag}-20261013-190000-1"
    ad = f"{NATIVE}/_attempts/{att}"
    usd = f"{ad}/usd"
    os.makedirs(usd, exist_ok=True)
    os.makedirs(f"{NATIVE}/{tag}", exist_ok=True)
    dump = f"dump_native_{which}.py"
    cmd = ["py", "gpu_guard.py", "--", "py", f"{EVAL}/usd_isolate_run.py", f"{HERE}/{dump}", "--headless", "--checkpoint", CKPT,
           "--tag", tag, "--outdir", NATIVE]
    run = {"attempt": att, "which": which, "tag": tag, "checkpoint": CKPT, "overrides": {}, "rc": 0, "child_rc": 0, "cmd": cmd,
           "paths": {"usd": usd}, "t_request_epoch": time.time() - 5}
    json.dump(run, open(f"{ad}/run.json", "w"))
    if which == "cts":
        json.dump({"attempt": att, "slot_rc": 0, "child_rc": 0, "state_at_release": "scene_built", "usd_final": ["20261013_190001_7"],
                   "usd_outside_root": [], "conflicts": {}, "cmd": ["py", "isaac_slot.py", "--"] + cmd},
                  open(f"{NATIVE}/{tag}.slot.json", "w"))
    else:
        json.dump({"patched_by": "loader"}, open(f"{usd}/isolate_state.json", "w"))
    json.dump({"exit_code": 0, "stopped_by_guard": False}, open(f"{NATIVE}/{tag}.guard.json", "w"))
    open(f"{NATIVE}/{tag}.log", "w").write(f"start\n[CE12-DUMP] done {tag} N 3 T 4 out x\n")
    shutil.copy(NPZ[which], f"{NATIVE}/{tag}/native.npz")
    json.dump({"model": "cts_student" if which == "cts" else "v2", "args": {"tag": tag}, "checkpoint": CKPT,
               "checkpoint_sha256": hashlib.sha256(open(CKPT, "rb").read()).hexdigest(), "t_start": time.strftime("%Y-%m-%d %H:%M:%S")},
              open(f"{NATIVE}/{tag}/meta.json", "w"))
    json.dump({}, open(f"{NATIVE}/{tag}/signature.json", "w"))
    return att, ad, usd


def jedit(p, **kw):
    d = json.load(open(p))
    d.update(kw)
    json.dump(d, open(p, "w"))


def npz_edit(p, key, fn):
    import numpy as np
    d = dict(np.load(p))
    d[key] = fn(d[key])
    np.savez(p, **d)


def defect_nan(a):
    a = a.copy()
    a[1, 0, 5] = float("nan")
    return a


CTS_ALL = ["G1", "L1", "L2", "M1", "M2", "N1", "R1", "R2", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
V2_ALL = ["G1", "L1", "L2", "M1", "M2", "N1", "R1", "R2", "V1", "V2", "V3", "V4", "V5"]
DEFECTS = {
    "cts": {
        "R1": lambda t, ad, u: jedit(f"{ad}/run.json", attempt="other"),
        "R2": lambda t, ad, u: jedit(f"{ad}/run.json", overrides={"CE12_GUARD": "x"}),
        "S1": lambda t, ad, u: jedit(f"{NATIVE}/{t}.slot.json", attempt="other"),
        "S2": lambda t, ad, u: jedit(f"{NATIVE}/{t}.slot.json", slot_rc=95),
        "S3": lambda t, ad, u: jedit(f"{NATIVE}/{t}.slot.json", child_rc=1),
        "S4": lambda t, ad, u: jedit(f"{NATIVE}/{t}.slot.json", state_at_release="exited"),
        "S5": lambda t, ad, u: jedit(f"{NATIVE}/{t}.slot.json", usd_final=["20261013_190001_7", "20261013_190002_8"]),
        "S6": lambda t, ad, u: jedit(f"{NATIVE}/{t}.slot.json", usd_outside_root=["20261013_190001_7"]),
        "S7": lambda t, ad, u: jedit(f"{NATIVE}/{t}.slot.json", conflicts={"20261013_190001_7": ["C:/other.log"]}),
        "S8": lambda t, ad, u: jedit(f"{NATIVE}/{t}.slot.json", cmd=["py", "isaac_slot.py", "--", "py", "gpu_guard.py", "--", "py",
                                                                     f"{HERE}/dump_native_cts.py", "--checkpoint", CKPT, "--tag", t]),
        "G1": lambda t, ad, u: jedit(f"{NATIVE}/{t}.guard.json", exit_code=99, stopped_by_guard=True),
        "L1": lambda t, ad, u: open(f"{NATIVE}/{t}.log", "a").write("Traceback (most recent call last):\n"),
        "L2": lambda t, ad, u: open(f"{NATIVE}/{t}.log", "w").write(f"[CE12-DUMP] done {t}_old N 3 T 4\n"),
        "N1": lambda t, ad, u: npz_edit(f"{NATIVE}/{t}/native.npz", "obs_policy", defect_nan),
        "M1": lambda t, ad, u: jedit(f"{NATIVE}/{t}/meta.json", checkpoint_sha256="0" * 64),
        "M2": lambda t, ad, u: jedit(f"{NATIVE}/{t}/meta.json", t_start="2026-10-01 00:00:00"),
    },
    "v2": {
        "V1": lambda t, ad, u: jedit(f"{ad}/run.json", rc=93),
        "V2": lambda t, ad, u: os.remove(f"{u}/isolate_state.json"),
        "V3": lambda t, ad, u: open(f"{u}/assigned.jsonl", "w").write('{"usd_dir": "x"}\n'),
        "V4": lambda t, ad, u: open(f"{NATIVE}/{t}.log", "a").write("Loading C:/tmp/IsaacLab/usd_20261013_190000_1/go2.usd\n"),
        "V5": lambda t, ad, u: jedit(f"{ad}/run.json", cmd=["py", f"{HERE}/dump_native_v2.py", "--checkpoint", CKPT, "--tag", t]),
        "N1": lambda t, ad, u: npz_edit(f"{NATIVE}/{t}/native.npz", "ray_starts_local", lambda a: a[:186]),
        "L2": lambda t, ad, u: open(f"{NATIVE}/{t}.log", "w").write("[CE12-DUMP] done other N 3\n"),
        "M2": lambda t, ad, u: jedit(f"{NATIVE}/{t}/meta.json", model="cts_student"),
    },
}


@test("VT0", "VT")
def vt0():
    for which, allc in (("cts", CTS_ALL), ("v2", V2_ALL)):
        att, _, _ = make_valid(which, f"base_{which}")
        bad, names = failed(which, f"base_{which}", att)
        assert bad == [] and sorted(names) == allc, (which, bad, sorted(names))
        bad, _ = failed(which, f"base_{which}", att, allow=False)
        assert bad == [], ("overrides 가 비었으면 --allow_overrides 없이도 통과해야", bad)


def _vt(which, cid):
    def fn():
        tag = f"d_{which}_{cid}"
        att, ad, usd = make_valid(which, tag)
        DEFECTS[which][cid](tag, ad, usd)
        bad, _ = failed(which, tag, att, allow=False)
        assert bad == [cid], f"{which} 결함 {cid}: 걸린 검사 {bad}"
    return fn


for _w in ("cts", "v2"):
    for _c in DEFECTS[_w]:
        test(f"VT-{_w}-{_c}", "VT")(_vt(_w, _c))


@test("VT-stamp", "VT")
def vt_stamp():
    att, _, _ = make_valid("v2", "stamp_v2")
    rc, o = validate_cli("v2", "stamp_v2", att)
    assert rc == 0 and not os.path.exists(f"{NATIVE}/stamp_v2/validate_stamp.json"), "--stamp 없이 stamp"
    open(f"{NATIVE}/stamp_v2.log", "a").write("Traceback (most recent call last):\n")
    rc, o = validate_cli("v2", "stamp_v2", att, ["--stamp"])
    assert rc == 1 and not os.path.exists(f"{NATIVE}/stamp_v2/validate_stamp.json"), "실패인데 stamp"


def main():
    sel = set(sys.argv[1:])
    fails = 0
    try:
        fake_npz()
        for tid, group, fn in TESTS:
            if sel and tid not in sel and group not in sel:
                continue
            try:
                fn()
                print(f"PASS {tid}", flush=True)
            except AssertionError as e:
                fails += 1
                print(f"FAIL {tid}: {str(e)[:500]}", flush=True)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"FAIL {tid}: {type(e).__name__}: {str(e)[:500]}", flush=True)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    n = len([t for t in TESTS if not sel or t[0] in sel or t[1] in sel])
    print(f"SUMMARY {n - fails}/{n} PASS · run_dump={RUN} · validate={VAL}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
