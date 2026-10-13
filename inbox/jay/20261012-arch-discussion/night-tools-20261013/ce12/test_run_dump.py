# -*- coding: utf-8 -*-
"""run_dump.py v2 (실행기) · validate_dump.py v2 (수집 · 승인) · compare_native 입력 해시 시험 (CPU · Isaac · GPU 없이).

분류: A/평가 · CE12-v1 이식 진단 1 · 실행기 · 검증기 시험
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 19:03 · v2 20:10 · 23:46 v3 사본 (ASTRA 17d §2.5 · §2.6 · §2.7 · §4 반례 반영)
근거: VERIFY-astra-17d.md §2.5 · §2.6 · §2.7 · §4 · §8 반례 절차 · _eval/test_isaac_slot_v3.py · test_usd_isolate_v3.py 의 가짜 자식 방식 (읽기만)
요지: RT 는 실행기를 끝까지 돌린다. 관문은 실제 isaac_slot_v3.py · usd_isolate_run_v3.py 를 시험 시작 때 사본으로 떠서 쓴다 (23:30 지시 ·
      원본이 바뀌는 중이어도 한 판으로 돈다). cts 는 예상 1, v2 는 예상 0 (뜻밖의 변환은 변환기 진입 즉시 막혀야 한다).
      가짜는 guard 와 기록기 (가짜 isaaclab 변환기 포함) 뿐이다.
      VT 는 수집 검사에 결함을 하나씩 넣어 그 검사 하나만 걸리는지, VA 는 승인 검사 (서명 · 요청 · 명령 시간열 · 금지 override ·
      student 경로 · 비교 보고서 해시 · reset · 전환) 를 실제 E1 · v2 체크포인트를 CPU 로 써서 같은 방식으로 본다.
상태: 시험 파일. 모든 쓰기는 임시 폴더 (CE12_EVAL_ROOT) 에만. 실제 _eval/slot · out_* 를 건드리지 않는다. 체크포인트는 읽기만.

실행: C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B test_run_dump.py [RT|VT|VA|시험이름 ...]
      CE12_RUN_DUMP · CE12_VALIDATE · CE12_COMPARE_SRC 로 변이 사본을 시험시킨다 (mutate_run_dump.py).
      각 실행은 사본으로 쓴 v3 두 파일의 sha256 을 맨 끝 줄에 찍는다 (어느 판으로 시험했는지).
"""
import os
import sys

sys.dont_write_bytecode = True
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import contextlib  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

torch.set_num_threads(2)
HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
RUN = os.environ.get("CE12_RUN_DUMP", os.path.join(HERE, "run_dump.py"))
VAL = os.environ.get("CE12_VALIDATE", os.path.join(HERE, "validate_dump.py"))
TMP = tempfile.mkdtemp(prefix="ce12_run_").replace("\\", "/")
ROOT = f"{TMP}/eval"
NATIVE = f"{ROOT}/out_ce12/native"
os.environ["CE12_EVAL_ROOT"] = ROOT
import adapters as A  # noqa: E402
import cells as CL  # noqa: E402

E1 = A.CTS_E1_RUN
CK = {"cts": f"{E1}/model_20000.pt", "v2": A.V2_CHECKPOINT}
REAL_SLOT = f"{EVAL}/isaac_slot_v3.py".replace("\\", "/")
REAL_ISO = f"{EVAL}/usd_isolate_run_v3.py".replace("\\", "/")
ART = ["RR_calf_joint", "FL_thigh_joint", "RL_hip_joint", "FR_calf_joint", "FL_hip_joint", "RR_hip_joint",
       "RL_calf_joint", "FR_thigh_joint", "RR_thigh_joint", "FL_calf_joint", "FR_hip_joint", "RL_thigh_joint"]
V2_ORDER = ["FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint", "FL_thigh_joint", "FR_thigh_joint",
            "RL_thigh_joint", "RR_thigh_joint", "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint"]
REQ = {"cells": "stand,fwd03,yawL05", "envs_per_cell": 1, "steps": 6, "reset_envs": "1", "reset_step": 3, "switch_env": 0,
       "switch_step": 4, "switch_cell": "fwd05"}
REQ_ARGS = ["--cells", "stand,fwd03,yawL05", "--envs_per_cell", "1", "--steps", "6", "--reset_envs", "1", "--reset_step", "3",
            "--switch_env", "0", "--switch_step", "4", "--switch_cell", "fwd05"]
TESTS = []


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

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
json.dump({"cmd": cmd, "gpu_index": a.gpu, "exit_code": rc, "stopped_by_guard": False, "fake": True,
           "expect_env": os.environ.get("FOOTHOLD_EXPECT_CONVERSIONS")}, open(a.summary, "w"))
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
print("[fake dump] start", which, rest, "expect", os.environ.get("FOOTHOLD_EXPECT_CONVERSIONS"), flush=True)
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
src = os.environ["FAKE_BUNDLE_" + which.upper()]
out = os.path.join(a.outdir, a.tag + ("_elsewhere" if mode == "misplace" else ""))
os.makedirs(out)
shutil.copy(os.path.join(src, "native.npz"), os.path.join(out, "native.npz"))
shutil.copy(os.path.join(src, "signature.json"), os.path.join(out, "signature.json"))
m = json.load(open(os.path.join(src, "meta.json"), encoding="utf-8"))
m["args"]["tag"] = a.tag
m["args"]["outdir"] = os.path.abspath(a.outdir)
m["checkpoint"] = os.path.abspath(a.checkpoint)
m["checkpoint_sha256"] = hashlib.sha256(open(a.checkpoint, "rb").read()).hexdigest()
m["t_start"] = time.strftime("%Y-%m-%d %H:%M:%S")
json.dump(m, open(os.path.join(out, "meta.json"), "w", encoding="utf-8"))
print("[CE12-DUMP] done " + a.tag + " N 3 T 6 out " + out, flush=True)
'''
def test(tid, group):
    def deco(fn):
        TESTS.append((tid, group, fn))
        return fn
    return deco


# ------------------------------------------------------------------ 준비 (임시 폴더에만)
for d in ("isaaclab", "isaaclab/sim", "isaaclab/sim/converters"):
    os.makedirs(f"{TMP}/pkg/{d}", exist_ok=True)
    open(f"{TMP}/pkg/{d}/__init__.py", "w").close()
open(f"{TMP}/pkg/isaaclab/sim/converters/asset_converter_base.py", "w").write(CONV)
for d in ("fake", "v3copy", "stub"):
    os.makedirs(f"{TMP}/{d}")
open(f"{TMP}/fake/gpu_guard.py", "w").write(GUARD)
for n in ("dump_native_cts.py", "dump_native_v2.py"):
    open(f"{TMP}/fake/{n}", "w").write(DUMP)
# 실제 v3 관문 두 파일을 시험 시작 때 사본으로 떠서 쓴다 (원본을 다른 하위 작업이 고치는 중이어도 이 시험 한 번은 한 판으로 돈다).
shutil.copy(REAL_SLOT, f"{TMP}/v3copy/isaac_slot_v3.py")
shutil.copy(REAL_ISO, f"{TMP}/v3copy/usd_isolate_run_v3.py")
V3_SHA = {n: sha(f"{TMP}/v3copy/{n}") for n in ("isaac_slot_v3.py", "usd_isolate_run_v3.py")}
COPY_SLOT, COPY_ISO = f"{TMP}/v3copy/isaac_slot_v3.py", f"{TMP}/v3copy/usd_isolate_run_v3.py"
open(f"{TMP}/stub/isaac_slot_v3.py", "w").write("# stub without the expected-conversion feature\nimport sys\nsys.exit(0)\n")
open(f"{TMP}/stub/usd_isolate_run_v3.py", "w").write("# stub\nimport sys\nsys.exit(0)\n")


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


_POL = {}


def policy(which):
    if which not in _POL:
        with quiet():
            _POL[which] = (A.load_cts_policy_cpu(CK["cts"]) if which == "cts" else A.load_v2_policy_cpu())[0]
    return _POL[which]


def default_pose(n):
    leg, part = n.split("_")[0], n.split("_")[1]
    return (0.1 if leg[1] == "L" else -0.1) if part == "hip" else (0.8 if leg[0] == "F" else 1.0) if part == "thigh" else -1.5


def build_native(which, req, seed=0):
    """요청 (cells · E · T · 강제 reset · 명령 전환) 대로의 가짜 native 기록. raw action 은 실제 체크포인트의 CPU 닫힌 고리 출력."""
    rng = np.random.RandomState(seed)
    cells = CL.parse_cells(req["cells"])
    E, T = int(req["envs_per_cell"]), int(req["steps"])
    N = len(cells) * E
    sw = (int(req["switch_env"]), int(req["switch_step"]), req["switch_cell"]) if int(req.get("switch_env", -1)) >= 0 else None
    cmd = np.asarray(CL.expected_commands(cells, E, T, sw), np.float32)
    renv = CL.parse_env_list(req.get("reset_envs", ""))
    ad = A.CTSStudentAdapter.from_source(N) if which == "cts" else A.V2Adapter.from_env_yaml(V2_ORDER, N)
    m = policy(which)
    f32 = lambda *s, lo=-0.5, hi=0.5: rng.uniform(lo, hi, s).astype(np.float32)  # noqa: E731
    K = {k: f32(T + 1, N, s) for k, s in (("root_pos_w", 3), ("root_quat_w", 4), ("lin_vel_b", 3), ("ang_vel_b", 3), ("projected_gravity_b", 3))}
    K["command"] = cmd
    K["joint_pos"] = (np.array([default_pose(n) for n in ART], np.float32)[None, None] + f32(T + 1, N, 12, lo=-0.1, hi=0.1)).astype(np.float32)
    K["joint_vel"] = f32(T + 1, N, 12, lo=-2, hi=2)
    K["art_joint_names"] = np.array(ART)
    if which == "v2":
        K["height_sensor_pos_w"] = f32(T + 1, N, 3, lo=0.3, hi=0.4)
        K["ray_hits_w"] = f32(T + 1, N, 187, 3, lo=-0.2, hi=0.2)
        K["ray_starts_local"] = np.concatenate([A.grid_pattern_local().numpy(), np.full((187, 1), 20.0)], 1).astype(np.float32)
    K["last_action"] = np.zeros((T + 1, N, 12), np.float32)
    K["raw_action"] = np.zeros((T, N, 12), np.float32)
    K["action_offset"] = np.tile(np.array([ad.default_joint_pos[n] for n in ad.action_joint_names], np.float32), (T, N, 1))
    K["reset_after_step"] = np.zeros((T, N), bool)
    if renv:
        K["reset_after_step"][int(req["reset_step"]) - 1, renv] = True
    K["terminated"] = np.zeros((T, N), bool)
    K["time_out"] = K["reset_after_step"].copy()
    pol, sin, tgt = [], [], []
    for k in range(T + 1):
        st = A.state_from_dump(K, k)
        K["last_action"][k] = ad._last_raw.numpy()
        o = ad.observe(st)
        pol.append(o["policy"].numpy())
        if which == "cts":
            sin.append(o["single_obs"].numpy())
        if k < T:
            K["raw_action"][k] = ad.infer(m, o).numpy()
            tgt.append(ad.decode_action(torch.tensor(K["raw_action"][k]), offset=torch.tensor(K["action_offset"][k])).numpy())
            ids = np.nonzero(K["reset_after_step"][k])[0]
            if len(ids):
                ad.reset(torch.tensor(ids))
    K["obs_policy"] = np.stack(pol)
    if which == "cts":
        K["obs_single_obs"] = np.stack(sin)
        K["obs_critic"] = f32(T + 1, N, 275)
    K["joint_target"] = np.stack(tgt)
    K["obs_joint_names"] = np.array(ad.obs_joint_names)
    K["action_joint_names"] = np.array(ad.action_joint_names)
    K["default_joint_pos"] = np.tile(np.array([default_pose(n) for n in ART], np.float32), (N, 1))
    K["default_joint_vel"] = np.zeros((N, 12), np.float32)
    K["cell_index"] = np.arange(N) // E
    K["cell_names"] = np.array(cells)
    K["cell_cmd"] = np.asarray([CL.CE12_CELLS[c][1] for c in cells], np.float32)
    K["model"] = np.array("cts_student" if which == "cts" else "v2")
    return K, ad


def meta_of(which, tag, req):
    m = {"model": "cts_student" if which == "cts" else "v2", "checkpoint": CK[which], "checkpoint_sha256": sha(CK[which]),
         "t_start": time.strftime("%Y-%m-%d %H:%M:%S"),
         "args": {"tag": tag, "outdir": NATIVE, "allow_cfg_diff": False, "cells": req["cells"], "envs_per_cell": req["envs_per_cell"],
                  "steps": req["steps"]}}
    if which == "cts":
        m.update({"policy_class": "ActorCriticMoECTS", "checks": {"teacher_input_randomized_max_abs_action_change": 0.0},
                  "default_cfg_vs_train_yaml_counts": {"observations": 0, "actions": 0, "decimation": 0, "sim": 0},
                  "train_yaml": {"path": f"{E1}/params/env.yaml", "sha256": sha(f"{E1}/params/env.yaml")},
                  "agent_yaml": f"{E1}/params/agent.yaml"})
    else:
        t = [["base_lin_vel", "base_lin_vel"]]
        m.update({"policy_class": "ActorCritic", "env_yaml": A.V2_ENV_YAML,
                  "cfg_vs_env_yaml": {"terms_runtime": t, "terms_env_yaml": t, "action_runtime": {"scale": 0.25}, "action_env_yaml": {"scale": 0.25}}})
    return m


def write_bundle(which, d, tag="bundle", req=REQ, seed=0):
    os.makedirs(d, exist_ok=True)
    K, ad = build_native(which, req, seed)
    np.savez(f"{d}/native.npz", **K)
    m = meta_of(which, tag, req)
    groups = ["policy", "single_obs"] if which == "cts" else ["policy"]
    m["obs_layout"] = {g: {"names": [x[0] for x in ad.layout(g)], "dims": [[x[2] - x[1]] for x in ad.layout(g)]} for g in groups}
    json.dump(m, open(f"{d}/meta.json", "w", encoding="utf-8"))
    A.write_signature(ad, f"{d}/signature.json")
    return d


BUNDLE = {}


def env_run(mode="ok", slot="copy"):
    e = dict(os.environ, PYTHONPATH=f"{TMP}/pkg", FAKE_TMP=f"{TMP}/faketmp", PYTHONIOENCODING="utf-8", FAKE_MODE=mode,
             CE12_EVAL_ROOT=ROOT, CE12_GUARD=f"{TMP}/fake/gpu_guard.py", CE12_DUMP_DIR=f"{TMP}/fake", CE12_PY_CTS=sys.executable,
             CE12_PY_V2=sys.executable, FAKE_BUNDLE_CTS=BUNDLE.get("cts", ""), FAKE_BUNDLE_V2=BUNDLE.get("v2", ""))
    if slot in ("copy", "stub"):
        d = "v3copy" if slot == "copy" else slot
        e["CE12_SLOT"] = f"{TMP}/{d}/isaac_slot_v3.py"
        e["CE12_ISOLATE"] = f"{TMP}/{d}/usd_isolate_run_v3.py"
    else:  # live: 실제 원본 경로 (dry_run 에서만 · 띄우지 않는다)
        e.pop("CE12_SLOT", None)
        e.pop("CE12_ISOLATE", None)
    return e


def run_dump(args, mode="ok", slot="copy"):
    r = subprocess.run([sys.executable, "-B", RUN] + args, capture_output=True, text=True, env=env_run(mode, slot), encoding="utf-8",
                       errors="replace", timeout=300)
    m = re.search(r"\[CE12-RUN\] \S+ attempt (\S+)|attempt (\S+) rc", r.stdout)
    att = (m.group(1) or m.group(2)) if m else None
    return r.returncode, r.stdout + r.stderr, att


def dry(args, slot="copy"):
    i = args.index("--") if "--" in args else len(args)  # 실행기 인자는 -- 앞에 (뒤는 기록기 인자)
    rc, out, att = run_dump(args[:i] + ["--dry_run"] + args[i:], slot=slot)
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


def CMP():
    if "c" not in _V:
        sp = importlib.util.spec_from_file_location("ce12_compare_under_test", os.environ.get("CE12_COMPARE_SRC", os.path.join(HERE, "compare_native.py")))
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        _V["c"] = m
    return _V["c"]


class _A:
    def __init__(self, which, tag, attempt, allow=True, report=""):
        self.which, self.tag, self.attempt, self.checkpoint, self.allow_overrides = which, tag, attempt, CK[which], allow
        self.compare_report = report
        self.stamp = self.approve = self.check_approval = False


def collect_failed(which, tag, attempt, allow=True):
    R = V().collect(_A(which, tag, attempt, allow))
    return sorted(n for n, s, _d in R if s != "PASS"), [n for n, _s, _d in R]


def approve_status(which, tag, attempt, report=""):
    v = V()
    a = _A(which, tag, attempt, True, report)
    RA, cov = v.approve(a, v.files_of(which, tag, attempt))
    return {n: s for n, s, _d in RA}, {n: d for n, _s, d in RA}


def validate_cli(which, tag, attempt, extra=()):
    r = subprocess.run([sys.executable, "-B", VAL, "--which", which, "--tag", tag, "--checkpoint", CK[which], "--attempt", attempt] + list(extra),
                       capture_output=True, text=True, env=dict(os.environ, CE12_EVAL_ROOT=ROOT, PYTHONIOENCODING="utf-8"),
                       encoding="utf-8", errors="replace", timeout=600)
    return r.returncode, r.stdout + r.stderr


def compare_report(which, tag, recompute=True, name="cmp.json"):
    with quiet():
        rep = CMP().compare(f"{NATIVE}/{tag}/native.npz", recompute_action=recompute, checkpoint=CK[which] if recompute else None)
    p = f"{NATIVE}/{tag}/{name}"
    json.dump(rep, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return p, rep


# ================================================================== RT · 실행기
@test("RT1", "RT")
def rt1():
    rc, j, att = dry(["--which", "cts", "--checkpoint", CK["cts"], "--tag", "c1"], slot="live")
    assert rc == 0, (rc, j)
    assert att and re.fullmatch(r"c1-\d{8}-\d{6}-\d+", att), att
    assert not os.path.exists(f"{ROOT}/out_ce12"), "dry_run 이 무언가를 만들었다"
    c = j["cmd"]
    assert c[1] == REAL_SLOT, ("관문은 실제 isaac_slot_v3.py", c[1])
    kv = {c[i]: c[i + 1] for i in range(2, c.index("--")) if c[i].startswith("--")}
    assert kv["--attempt"] == att and kv["--usd_root"] == f"{NATIVE}/_attempts/{att}/usd", kv
    assert kv["--watch_log"] == f"{NATIVE}/c1.log" and kv["--record"] == f"{NATIVE}/c1.slot.json", kv
    assert kv["--lock"] == f"{ROOT}/slot/isaac_convert.lock" and kv["--registry"] == f"{ROOT}/slot/isaac_usd_registry.json", kv
    assert kv["--scan_dirs"].split(",") == [f"{ROOT}/out_ce12/native", f"{ROOT}/out_branch", f"{ROOT}/out_uncr", f"{ROOT}/out_rand"], kv
    assert kv["--stop_file"] == f"{ROOT}/out_ce12/STOP" and float(kv["--deadline"]) == 0.0, kv
    assert j["capabilities"]["slot"] == REAL_SLOT and j["capabilities"]["isolate"] == REAL_ISO
    if j["capabilities"]["slot_expect_flag"]:
        assert c[c.index("--expect_conversions") + 1] == "1" and c.index("--expect_conversions") < c.index("--"), "slot v3 의 예상 인자 1"
    else:
        assert "--expect_conversions" not in c, "slot 이 모르는 인자를 넘겼다"
    i_g = next(i for i, x in enumerate(c) if x.endswith("/gpu_guard.py"))
    g = {c[i]: c[i + 1] for i in range(i_g + 1, c.index("--", i_g)) if c[i].startswith("--")}
    assert g == {"--gpu": "1", "--min_free_mib": "4096", "--log": f"{NATIVE}/c1.log", "--summary": f"{NATIVE}/c1.guard.json"}, g
    rest = c[c.index("--", i_g) + 1:]
    assert rest[1] == REAL_ISO and rest[2].endswith("/dump_native_cts.py"), rest[:3]
    assert rest[rest.index("--tag") + 1] == "c1" and rest[rest.index("--outdir") + 1] == NATIVE, rest
    assert rest[rest.index("--steps") + 1] == "60" and rest[rest.index("--cells") + 1] == "stand,fwd03,yawL05", "요청을 늘 명시"
    es = j["env_set"]
    assert es["CUDA_VISIBLE_DEVICES"] == "1" and es["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID" and es["FOOTHOLD_EXPECT_CONVERSIONS"] == "1", es


@test("RT2", "RT")
def rt2():
    rc, j, att = dry(["--which", "v2", "--checkpoint", CK["v2"], "--tag", "v1", "--gpu", "0", "--min_free_mib", "2048"], slot="copy")
    assert rc == 0, (rc, j)
    c = j["cmd"]
    assert c[1] == COPY_SLOT, "v2 도 slot v3 을 거친다"
    assert c[c.index("--expect_conversions") + 1] == "0", "slot 이 아는 예상 인자 0"
    rest = c[c.index("--", c.index("--min_free_mib")) + 1:]
    assert rest[1].endswith("/usd_isolate_run_v3.py") and rest[2].endswith("/dump_native_v2.py"), rest[:3]
    assert j["env_set"]["FOOTHOLD_EXPECT_CONVERSIONS"] == "0" and j["env_set"]["CUDA_VISIBLE_DEVICES"] == "0", j["env_set"]
    assert "FOOTHOLD_USD_ROOT" not in j["env_set"], "USD 루트는 slot 이 넘긴다"


@test("RT3", "RT")
def rt3():
    rc, out, _ = run_dump(["--which", "v2", "--checkpoint", CK["v2"], "--tag", "v3stub"], slot="stub")
    assert rc == 2 and "변환 예상 0" in out, (rc, out[-300:])
    assert not os.path.exists(f"{NATIVE}/v3stub.log")


@test("RT4", "RT")
def rt4():
    os.makedirs(f"{NATIVE}/taken", exist_ok=True)
    try:
        rc, out, _ = run_dump(["--which", "cts", "--checkpoint", CK["cts"], "--tag", "taken"])
        assert rc == 2 and "STOP" in out, (rc, out[-300:])
    finally:
        shutil.rmtree(f"{NATIVE}/taken")
    for suf in (".log", ".slot.json", ".guard.json"):
        p = f"{NATIVE}/t4{suf}"
        open(p, "w").write("old")
        try:
            rc, out, _ = run_dump(["--which", "v2", "--checkpoint", CK["v2"], "--tag", "t4"], slot="copy")
            assert rc == 2 and "STOP" in out and open(p).read() == "old", (suf, rc)
        finally:
            os.remove(p)


@test("RT5", "RT")
def rt5():
    sf = f"{TMP}/STOP"
    open(sf, "w").close()
    try:
        rc, out, att = run_dump(["--which", "v2", "--checkpoint", CK["v2"], "--tag", "t5", "--stop_file", sf], slot="copy")
        assert rc == 98, (rc, out[-300:])
        rj = json.load(open(f"{NATIVE}/_attempts/{att}/run.json", encoding="utf-8"))
        assert rj["state"].startswith("not launched") and not os.path.exists(f"{NATIVE}/t5.log"), rj
    finally:
        os.remove(sf)
    rc, out, att = run_dump(["--which", "cts", "--checkpoint", CK["cts"], "--tag", "t5b", "--deadline", str(time.time() - 10)])
    assert rc == 98 and not os.path.exists(f"{NATIVE}/t5b.log"), (rc, out[-300:])


@test("RT6", "RT")
def rt6():
    """ASTRA 17d §2.5 반례: 등호형 · 축약 · 중복 · 금지 옵션 · 형식이 틀린 값은 띄우기 전에 거절 (종료 2 · 아무 데도 안 씀)."""
    esc = f"{TMP}/escaped"
    bad = [["--", f"--outdir={esc}"], ["--", "--outdir", esc], ["--", "--outd", esc], ["--", f"--tag=x"], ["--", f"--checkpoint={CK['v2']}"],
           ["--", "--allow_cfg_diff"], ["--", "--allow_cfg_diff=1"], ["--", "--device", "cuda:1"], ["--", "--steps", "5", "--steps", "6"],
           ["--", "--steps=5", "--steps", "6"], ["--", "--cells", "stand,bogus"], ["--", "--steps", "-3"], ["--", "--steps", "--outdir"],
           ["--", "--env_yaml", "x.yaml"], ["--", "stray"], ["--", "--seed"], ["--", "--switch_env", "0"], ["--", "--reset_envs", "0,1,2", "--reset_step", "2",
           "--cells", "stand", "--envs_per_cell", "3"], ["--", "--steps", "0"], ["--", "--headless"], ["--", "--dr_profile", "x"]]
    for extra in bad:
        rc, out, _ = run_dump(["--which", "v2", "--checkpoint", CK["v2"], "--tag", "esc"] + extra, slot="copy")
        assert rc == 2 and "STOP" in out, (extra, rc, out[-200:])
    assert not os.path.exists(esc) and not os.path.exists(f"{NATIVE}/esc") and not os.path.exists(f"{NATIVE}/esc.log")
    for args in (["--which", "cts", "--checkpoint", CK["cts"], "--tag", "../out/x"], ["--which", "cts", "--tag", "nockpt"],
                 ["--which", "cts", "--checkpoint", f"{TMP}/none.pt", "--tag", "miss"]):
        rc, out, _ = run_dump(args)
        assert rc == 2 and "STOP" in out, (args, rc)
    rc, j, _ = dry(["--which", "v2", "--checkpoint", CK["v2"], "--tag", "ok6", "--", "--steps=7", "--switch_env", "0", "--switch_step", "3",
                    "--switch_cell", "fwd05"], slot="copy")
    c = j["cmd"]
    assert rc == 0 and c[c.index("--steps") + 1] == "7" and c.count("--steps") == 1 and "--steps=7" not in c, "등호형 허용 옵션은 정규화"


@test("RT7", "RT")
def rt7():
    """수정 경로 그대로: 실제 isaac_slot_v3.py · usd_isolate_run_v3.py 의 사본 (cts · 예상 1) + 가짜 guard · 가짜 기록기."""
    rc, out, att = run_dump(["--which", "cts", "--checkpoint", CK["cts"], "--tag", "c7", "--"] + REQ_ARGS)
    assert rc == 0, (rc, out[-1500:])
    s = json.load(open(f"{NATIVE}/c7.slot.json", encoding="utf-8"))
    assert (s["slot_version"], s["attempt"], s["slot_rc"], s["child_rc"], s["state_at_release"], len(s["usd_final"]), s["usd_outside_root"],
            s["usd_unassigned"], s["conflicts"]) == ("v3", att, 0, 0, "scene_built", 1, [], [], {}), s
    assert s["isolate_state"]["patched_by"] == "loader" and s["isolate_state"]["version"] == "v3" and not s["isolate_state"]["blocked"], s["isolate_state"]
    assert (s["expect_conversions"], s["conversion_attempts"], s["expect_violation"], s["isolate_state"]["expect_conversions"]) == ("1", 1, False, "1"), s
    assert os.path.exists(f"{ROOT}/slot/isaac_usd_registry.json") and not os.path.exists(f"{TMP}/faketmp"), "registry 는 임시 · 공용 폴더 없음"
    g = json.load(open(f"{NATIVE}/c7.guard.json"))
    assert g["expect_env"] == "1", g
    rcv, o = validate_cli("cts", "c7", att, ["--allow_overrides", "--stamp"])
    assert rcv == 0 and "COLLECTED c7" in o, o[-1200:]
    st = json.load(open(f"{NATIVE}/c7/validate_stamp.json", encoding="utf-8"))
    assert {"npz", "meta", "signature", "log", "guard", "slot", "run"} == set(st["files"]), st["files"].keys()
    rcv, o = validate_cli("cts", "c7", att)
    assert rcv == 1 and "FAIL R2" in o and o.count("FAIL ") == 1, o[-800:]


@test("RT8", "RT")
def rt8():
    """v2 · 예상 0 · 변환 없음: 실제 slot v3 · isolate v3 사본 (--expect_conversions 0). 수집 통과."""
    rc, out, att = run_dump(["--which", "v2", "--checkpoint", CK["v2"], "--tag", "v8", "--"] + REQ_ARGS, slot="copy")
    assert rc == 0, (rc, out[-1500:])
    s = json.load(open(f"{NATIVE}/v8.slot.json", encoding="utf-8"))
    assert (s["expect_conversions"], s["usd_final"], s["assigned"], s["conversion_attempts"], s["expect_violation"], s["isolate_state"]["patched_by"],
            s["isolate_state"]["expect_conversions"]) == ("0", [], [], 0, False, "loader", "0"), s
    rcv, o = validate_cli("v2", "v8", att, ["--allow_overrides"])
    assert rcv == 0 and "COLLECTED v8" in o, o[-1200:]


@test("RT9", "RT")
def rt9():
    """ASTRA 17d §2.6: v2 에서 뜻밖의 변환은 변환기 진입 즉시 막혀야 한다 (폴더를 만들기 전 · 공용 경로에 아무것도 없음)."""
    rc, out, att = run_dump(["--which", "v2", "--checkpoint", CK["v2"], "--tag", "v9"], mode="convert", slot="copy")
    assert rc == 89, (rc, out[-800:])
    usd = f"{NATIVE}/_attempts/{att}/usd"
    st = json.load(open(f"{usd}/isolate_state.json", encoding="utf-8"))
    assert st["blocked"] and "FOOTHOLD_EXPECT_CONVERSIONS=0" in st["blocked"][0]["why"], st
    kinds = [json.loads(x)["kind"] for x in open(f"{usd}/assigned.jsonl", encoding="utf-8") if x.strip()]
    assert kinds == ["refused_unexpected_conversion"], kinds
    assert not os.path.exists(f"{usd}/IsaacLab") and not os.path.exists(f"{TMP}/faketmp"), "쓰기 시도 전에 막지 못했다"
    s = json.load(open(f"{NATIVE}/v9.slot.json", encoding="utf-8"))
    assert s["expect_violation"] is True and s["slot_rc"] == 89, s
    rcv, o = validate_cli("v2", "v9", att, ["--allow_overrides"])
    assert rcv == 1 and "FAIL S3" in o and "FAIL S9" in o and "FAIL S10" in o, o[-800:]


@test("RT10", "RT")
def rt10():
    """자식은 0 인데 결과가 다른 곳에 생김: 실행기가 직접 확인해 88."""
    rc, out, att = run_dump(["--which", "v2", "--checkpoint", CK["v2"], "--tag", "v10"], mode="misplace", slot="copy")
    assert rc == 88, (rc, out[-600:])
    rj = json.load(open(f"{NATIVE}/_attempts/{att}/run.json", encoding="utf-8"))
    assert "없음" in rj["output_problem"], rj["output_problem"]
    rcv, o = validate_cli("v2", "v10", att, ["--allow_overrides"])
    assert rcv == 1 and "FAIL R4" in o, o[-600:]


@test("RT11", "RT")
def rt11():
    rc, out, att = run_dump(["--which", "cts", "--checkpoint", CK["cts"], "--tag", "c11"], mode="traceback")
    assert rc == 1, (rc, out[-600:])
    rcv, o = validate_cli("cts", "c11", att, ["--allow_overrides"])
    assert rcv == 1 and "FAIL S3" in o and "FAIL L1" in o, o[-600:]


@test("RT12", "RT")
def rt12():
    """끝까지: 실제 slot v3 · isolate v3 로 수집 -> compare_native --recompute_action -> 승인 APPROVED -> 입력이 바뀌면 승인 무효."""
    rc, out, att = run_dump(["--which", "cts", "--checkpoint", CK["cts"], "--tag", "chain", "--"] + REQ_ARGS)
    assert rc == 0, (rc, out[-1200:])
    r = subprocess.run([sys.executable, "-B", os.path.join(HERE, "compare_native.py"), "--dump", f"{NATIVE}/chain/native.npz",
                        "--recompute_action", "--report", f"{NATIVE}/chain/cmp.json"], capture_output=True, text=True,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"), encoding="utf-8", errors="replace", timeout=600)
    assert r.returncode == 0, r.stdout[-1200:] + r.stderr[-800:]
    rcv, o = validate_cli("cts", "chain", att, ["--allow_overrides", "--approve", "--compare_report", f"{NATIVE}/chain/cmp.json"])
    assert rcv == 0 and "APPROVED chain" in o, o[-1500:]
    rcv, o = validate_cli("cts", "chain", att, ["--check_approval"])
    assert rcv == 0 and "STILL VALID" in o, o[-400:]
    m = json.load(open(f"{NATIVE}/chain/meta.json", encoding="utf-8"))
    m["note"] = "changed after approval"
    json.dump(m, open(f"{NATIVE}/chain/meta.json", "w", encoding="utf-8"))
    rcv, o = validate_cli("cts", "chain", att, ["--check_approval"])
    assert rcv == 1 and "APPROVAL INVALID" in o and "meta" in o, o[-400:]


# ================================================================== VT · 수집 검사 결함 하나씩
def make_valid(which, tag, req=REQ):
    att = f"{tag}-20261013-201000-1"
    ad = f"{NATIVE}/_attempts/{att}"
    usd = f"{ad}/usd"
    os.makedirs(usd, exist_ok=True)
    os.makedirs(f"{NATIVE}/{tag}", exist_ok=True)
    exp = 1 if which == "cts" else 0
    dump = f"{HERE}/dump_native_{which}.py".replace("\\", "/")
    dcmd = ["py", REAL_ISO, dump, "--headless", "--checkpoint", CK[which], "--tag", tag, "--outdir", NATIVE]
    cmd = ["py", REAL_SLOT, "--watch_log", "x", "--"] + ["py", "gpu_guard.py", "--"] + dcmd
    run = {"attempt": att, "which": which, "tag": tag, "checkpoint": CK[which], "overrides": {}, "rc": 0, "child_rc": 0, "output_problem": "",
           "cmd": cmd, "paths": {"usd": usd}, "t_request_epoch": time.time() - 5, "expect_conversions": exp,
           "env_set": {"FOOTHOLD_EXPECT_CONVERSIONS": str(exp)}, "request": dict(req)}
    json.dump(run, open(f"{ad}/run.json", "w"))
    folder = [f"{usd.lower()}/isaaclab/usd_20261013_201001_7"] if exp else []
    json.dump({"slot_version": "v3", "attempt": att, "slot_rc": 0, "child_rc": 0, "state_at_release": "scene_built" if exp else "exited",
               "usd_final": folder, "usd_outside_root": [], "usd_unassigned": [], "assigned": folder, "assigned_outside_root": [],
               "hint_without_assigned": False, "conflicts": {}, "registry_error": "", "cmd": cmd[4:], "expect_conversions": str(exp),
               "conversion_attempts": exp, "unexpected_refused": [], "launcher_blocked": [], "expect_violation": False,
               "isolate_state": {"patched_by": "loader", "version": "v3", "blocked": [], "expect_conversions": str(exp)}},
              open(f"{NATIVE}/{tag}.slot.json", "w"))
    json.dump({"exit_code": 0, "stopped_by_guard": False}, open(f"{NATIVE}/{tag}.guard.json", "w"))
    open(f"{NATIVE}/{tag}.log", "w").write(f"start\n[CE12-DUMP] done {tag} N 3 T 6 out x\n")
    src = BUNDLE[which] if req is REQ else write_bundle(which, f"{TMP}/bundles/{tag}", tag, req)
    for f in ("native.npz", "signature.json"):
        shutil.copy(f"{src}/{f}", f"{NATIVE}/{tag}/{f}")
    m = json.load(open(f"{src}/meta.json", encoding="utf-8"))
    m["args"]["tag"] = tag
    m["t_start"] = time.strftime("%Y-%m-%d %H:%M:%S")
    json.dump(m, open(f"{NATIVE}/{tag}/meta.json", "w", encoding="utf-8"))
    return att, ad, usd


def jedit(p, **kw):
    d = json.load(open(p, encoding="utf-8"))
    d.update(kw)
    json.dump(d, open(p, "w", encoding="utf-8"))


def jedit_in(p, key, **kw):
    d = json.load(open(p, encoding="utf-8"))
    d[key] = dict(d.get(key) or {}, **kw)
    json.dump(d, open(p, "w", encoding="utf-8"))


def npz_edit(p, key, fn):
    d = dict(np.load(p))
    d[key] = fn(d[key])
    np.savez(p, **d)


def _nan(a):
    a = a.copy()
    a[1, 0, 5] = float("nan")
    return a


SL = lambda t: f"{NATIVE}/{t}.slot.json"  # noqa: E731
COLLECT_DEFECTS = {
    "R1": lambda w, t, ad, u: jedit(f"{ad}/run.json", attempt="other"),
    "R2": lambda w, t, ad, u: jedit(f"{ad}/run.json", overrides={"CE12_GUARD": "x"}),
    "R3": lambda w, t, ad, u: jedit_in(f"{ad}/run.json", "env_set", FOOTHOLD_EXPECT_CONVERSIONS="7"),
    "R4": lambda w, t, ad, u: jedit(f"{ad}/run.json", output_problem="결과가 다른 곳"),
    "S1": lambda w, t, ad, u: jedit(SL(t), attempt="other"),
    "S2": lambda w, t, ad, u: jedit(SL(t), slot_rc=95),
    "S3": lambda w, t, ad, u: jedit(SL(t), child_rc=1),
    "S4": lambda w, t, ad, u: jedit(SL(t), state_at_release="convert_timeout"),
    "S5": lambda w, t, ad, u: jedit(SL(t), usd_final=["a", "b"]),
    "S6": lambda w, t, ad, u: jedit(SL(t), usd_outside_root=["c:/tmp/isaaclab/usd_20261013_190000_1"]),
    "S7": lambda w, t, ad, u: jedit(SL(t), conflicts={"x": ["C:/other.log"]}),
    "S8": lambda w, t, ad, u: jedit(SL(t), cmd=[x.replace("usd_isolate_run_v3.py", "usd_isolate_run.py") for x in json.load(open(SL(t)))["cmd"]]),
    "S9": lambda w, t, ad, u: jedit(SL(t), usd_unassigned=["c:/x/isaaclab/usd_20261013_190000_1"]),
    "S10": lambda w, t, ad, u: jedit(SL(t), isolate_state={"patched_by": "loader", "version": "v3", "blocked": [{"why": "x"}],
                                                          "expect_conversions": str(1 if w == "cts" else 0)}),
    "S11": lambda w, t, ad, u: jedit(SL(t), registry_error="registry is not JSON"),
    "G1": lambda w, t, ad, u: jedit(f"{NATIVE}/{t}.guard.json", exit_code=99, stopped_by_guard=True),
    "L1": lambda w, t, ad, u: open(f"{NATIVE}/{t}.log", "a").write("Traceback (most recent call last):\n"),
    "L2": lambda w, t, ad, u: open(f"{NATIVE}/{t}.log", "w").write(f"[CE12-DUMP] done {t}_old N 3 T 6\n"),
    "N1": lambda w, t, ad, u: npz_edit(f"{NATIVE}/{t}/native.npz", "obs_policy", _nan),
    "N2": lambda w, t, ad, u: os.remove(f"{NATIVE}/{t}/signature.json"),
    "M1": lambda w, t, ad, u: jedit(f"{NATIVE}/{t}/meta.json", checkpoint_sha256="0" * 64),
    "M2": lambda w, t, ad, u: jedit(f"{NATIVE}/{t}/meta.json", t_start="2026-10-01 00:00:00"),
}
EXTRA_COLLECT = {
    "S8b": ("S8", lambda w, t, ad, u: jedit(f"{ad}/run.json", cmd=[x.replace("isaac_slot_v3.py", "isaac_slot.py") for x in json.load(open(f"{ad}/run.json"))["cmd"]])),
    "S8c": ("S8", lambda w, t, ad, u: jedit(SL(t), cmd=json.load(open(SL(t)))["cmd"] + [f"--outdir={TMP}/escaped"])),
    "S8d": ("S8", lambda w, t, ad, u: jedit(SL(t), slot_version="v2")),
    "S9b": ("S9", lambda w, t, ad, u: jedit(SL(t), assigned=[] if w == "cts" else ["c:/r/isaaclab/usd_1"])),
    "R3b": ("R3", lambda w, t, ad, u: jedit(SL(t), expect_conversions="5")),
    "R3c": ("R3", lambda w, t, ad, u: jedit(SL(t), isolate_state={"patched_by": "loader", "version": "v3", "blocked": [], "expect_conversions": "any"})),
    "S9c": ("S9", lambda w, t, ad, u: jedit(SL(t), expect_violation=True)),
    "S9d": ("S9", lambda w, t, ad, u: jedit(SL(t), conversion_attempts=2)),
    "S9e": ("S9", lambda w, t, ad, u: jedit(SL(t), unexpected_refused=[{"n": 2}])),
    "S10b": ("S10", lambda w, t, ad, u: jedit(SL(t), launcher_blocked=[{"why": "x"}])),
    "N1b": ("N1", lambda w, t, ad, u: npz_edit(f"{NATIVE}/{t}/native.npz", "obs_policy", lambda a: a[..., :-1])),
}
ALL_COLLECT = sorted(COLLECT_DEFECTS)


@test("VT0", "VT")
def vt0():
    for which in ("cts", "v2"):
        att, _, _ = make_valid(which, f"base_{which}")
        bad, names = collect_failed(which, f"base_{which}", att)
        assert bad == [] and sorted(names) == ALL_COLLECT, (which, bad, sorted(names))
        bad, _ = collect_failed(which, f"base_{which}", att, allow=False)
        assert bad == [], ("overrides 가 비었으면 --allow_overrides 없이도 통과해야", bad)


def _vt(which, cid, want, fn):
    def run():
        tag = f"d_{which}_{cid}"
        att, ad, usd = make_valid(which, tag)
        fn(which, tag, ad, usd)
        bad, _ = collect_failed(which, tag, att, allow=False)
        assert bad == [want], f"{which} 결함 {cid}: 걸린 검사 {bad} (원하는 것 [{want}])"
    return run


for _w in ("cts", "v2"):
    for _c, _f in COLLECT_DEFECTS.items():
        test(f"VT-{_w}-{_c}", "VT")(_vt(_w, _c, _c, _f))
    for _c, (_want, _f) in EXTRA_COLLECT.items():
        test(f"VT-{_w}-{_c}", "VT")(_vt(_w, _c, _want, _f))


@test("VT-stamp", "VT")
def vt_stamp():
    att, _, _ = make_valid("v2", "stamp_v2")
    rc, o = validate_cli("v2", "stamp_v2", att)
    assert rc == 0 and not os.path.exists(f"{NATIVE}/stamp_v2/validate_stamp.json"), "--stamp 없이 stamp"
    os.remove(f"{NATIVE}/stamp_v2/signature.json")
    rc, o = validate_cli("v2", "stamp_v2", att, ["--stamp"])
    assert rc == 1 and not os.path.exists(f"{NATIVE}/stamp_v2/validate_stamp.json") and "FAIL N2" in o, "서명이 없는데 stamp (또는 조용히 뺌)"


# ================================================================== VA · 승인 검사
A_ALL = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"]


@test("VA0", "VA")
def va0():
    """완전한 기록 + 재계산 비교 보고서 = APPROVED · 보고서가 없으면 A6 만 보류 · stamp 은 그때 지금 파일과 맞는다."""
    for which in ("cts", "v2"):
        tag = f"ap_{which}"
        att, _, _ = make_valid(which, tag)
        st, why = approve_status(which, tag, att)
        assert st == dict({k: "PASS" for k in A_ALL}, A6="PENDING"), (which, st, why)
        p, rep = compare_report(which, tag)
        assert rep["status"] == "pass", [c for c in rep["checks"] if not c["ok"]][:2]
        st, why = approve_status(which, tag, att, p)
        assert st == {k: "PASS" for k in A_ALL}, (which, st, why)
        rc, o = validate_cli(which, tag, att, ["--approve", "--compare_report", p])
        assert rc == 0 and f"APPROVED {tag}" in o, o[-800:]
        st = json.load(open(f"{NATIVE}/{tag}/approval_stamp.json", encoding="utf-8"))
        need = {"npz", "meta", "signature", "compare_report", "checkpoint", "code_adapters.py", "code_compare_native.py", "code_cells.py"}
        assert need <= set(st["files"]), sorted(st["files"])
        rc, o = validate_cli(which, tag, att, ["--check_approval"])
        assert rc == 0 and "STILL VALID" in o, o[-400:]
        npz_edit(f"{NATIVE}/{tag}/native.npz", "joint_vel", lambda a: a * 1.0001)
        rc, o = validate_cli(which, tag, att, ["--check_approval"])
        assert rc == 1 and "APPROVAL INVALID" in o and "npz" in o, ("승인 뒤 npz 가 바뀌었는데 승인 유효", o[-400:])


def _va(which, cid, want, fn, report=False):
    def run():
        tag = f"a_{which}_{cid}"
        att, ad, usd = make_valid(which, tag)
        p = compare_report(which, tag)[0] if report else ""
        fn(which, tag, ad, usd, p)
        st, why = approve_status(which, tag, att, p)
        bad = sorted(k for k, s in st.items() if s == "FAIL")
        assert bad == [want], f"{which} 결함 {cid}: FAIL {bad} (원하는 것 [{want}]) · {why.get(want)} · {st}"
    return run


def _sig_rename(w, t, ad, u, p):
    s = json.load(open(f"{NATIVE}/{t}/signature.json", encoding="utf-8"))
    s["joint_names"]["observation"][0] = "XX_joint"
    json.dump(s, open(f"{NATIVE}/{t}/signature.json", "w", encoding="utf-8"))


def _rep_edit(**kw):
    def f(w, t, ad, u, p):
        d = json.load(open(p, encoding="utf-8"))
        for k, v in kw.items():
            if k == "code":
                d["inputs"]["code_sha256"]["adapters.py"] = "0" * 64
            else:
                d[k] = v
        json.dump(d, open(p, "w", encoding="utf-8"))
    return f


def _cmd_edit(w, t, ad, u, p):
    npz_edit(f"{NATIVE}/{t}/native.npz", "command", lambda a: a + np.where(np.arange(a.shape[0])[:, None, None] == 2, 0.1, 0.0).astype(np.float32))


APPROVE_DEFECTS = {
    "A1": ("A1", _sig_rename, False),
    "A1b": ("A1", lambda w, t, ad, u, p: jedit(f"{NATIVE}/{t}/signature.json", adapter_version="old"), False),
    "A2": ("A2", lambda w, t, ad, u, p: jedit_in(f"{ad}/run.json", "request", steps=60), False),
    "A2b": ("A2", lambda w, t, ad, u, p: jedit_in(f"{ad}/run.json", "request", cells="stand,fwd05,yawL05"), False),
    "A2c": ("A2", lambda w, t, ad, u, p: jedit_in(f"{ad}/run.json", "request", reset_envs="2"), False),
    "A3": ("A3", _cmd_edit, False),
    "A3b": ("A3", lambda w, t, ad, u, p: jedit_in(f"{ad}/run.json", "request", switch_cell="fwd03"), False),
    "A4": ("A4", lambda w, t, ad, u, p: jedit_in(f"{NATIVE}/{t}/meta.json", "args", allow_cfg_diff=True), False),
    "A4b": ("A4", lambda w, t, ad, u, p: (jedit(f"{NATIVE}/{t}/meta.json", default_cfg_vs_train_yaml_counts={"observations": 4, "actions": 0, "decimation": 0})
                                          if w == "cts" else jedit_in(f"{NATIVE}/{t}/meta.json", "cfg_vs_env_yaml", action_runtime={"scale": 0.5})), False),
    "A4c": ("A4", lambda w, t, ad, u, p: jedit_in(f"{NATIVE}/{t}/meta.json", "args", outdir=f"{TMP}/escaped"), False),
    "A5": ("A5", lambda w, t, ad, u, p: (jedit(f"{NATIVE}/{t}/meta.json", checks={"teacher_input_randomized_max_abs_action_change": 1.0})
                                         if w == "cts" else jedit(f"{NATIVE}/{t}/meta.json", policy_class="ActorCriticMoECTS")), False),
    "A6": ("A6", lambda w, t, ad, u, p: npz_edit(f"{NATIVE}/{t}/native.npz", "root_pos_w", lambda a: a + 1.0), True),
    "A6b": ("A6", _rep_edit(status="mismatch"), True),
    "A6c": ("A6", _rep_edit(recompute_action=False), True),
    "A6d": ("A6", _rep_edit(checkpoint_sha256="0" * 64), True),
    "A6e": ("A6", _rep_edit(code=True), True),
    "A6f": ("A6", lambda w, t, ad, u, p: jedit(f"{NATIVE}/{t}/meta.json", note="changed after compare"), True),
}


for _w in ("cts", "v2"):
    for _c, (_want, _f, _r) in APPROVE_DEFECTS.items():
        test(f"VA-{_w}-{_c}", "VA")(_va(_w, _c, _want, _f, _r))


@test("VA-pending", "VA")
def va_pending():
    """reset · 명령 전환이 없는 기본형 기록은 A7 · A8 보류 (그 경로 미확인) · 보고서 없음은 A6 보류 · 종료 3 · stamp 없음."""
    req = dict(REQ, reset_envs="", reset_step=0, switch_env=-1, switch_step=0, switch_cell="")
    att, _, _ = make_valid("cts", "pend", req)
    st, _ = approve_status("cts", "pend", att)
    assert st == dict({k: "PASS" for k in A_ALL}, A6="PENDING", A7="PENDING", A8="PENDING"), st
    rc, o = validate_cli("cts", "pend", att, ["--approve"])
    assert rc == 3 and "PENDING pend" in o and "미확인 경로" in o and not os.path.exists(f"{NATIVE}/pend/approval_stamp.json"), o[-600:]


@test("VA-teacher", "VA")
def va_teacher():
    """ASTRA 17d §2.7 반례 묶음: allow_cfg_diff · 관측 설정 차이 4 · teacher 입력 변경 action 차 1.0 · 틀린 steps/cells · signature 삭제."""
    att, ad, _ = make_valid("cts", "astra")
    p = f"{NATIVE}/astra/meta.json"
    m = json.load(open(p, encoding="utf-8"))
    m["args"]["allow_cfg_diff"] = True
    m["default_cfg_vs_train_yaml_counts"]["observations"] = 4
    m["checks"]["teacher_input_randomized_max_abs_action_change"] = 1.0
    json.dump(m, open(p, "w", encoding="utf-8"))
    jedit_in(f"{ad}/run.json", "request", steps=60, cells="stand,fwd05")
    os.remove(f"{NATIVE}/astra/signature.json")
    bad, _ = collect_failed("cts", "astra", att)
    assert bad == ["N2"], bad
    st, _ = approve_status("cts", "astra", att)
    assert {k for k, s in st.items() if s == "FAIL"} == {"A1", "A2", "A4", "A5"}, st
    rc, o = validate_cli("cts", "astra", att, ["--approve", "--stamp"])
    assert rc == 1 and "REJECTED astra" in o and not os.path.exists(f"{NATIVE}/astra/validate_stamp.json"), o[-600:]


def main():
    sel = set(sys.argv[1:])
    fails = 0
    try:
        for which in ("cts", "v2"):
            BUNDLE[which] = write_bundle(which, f"{TMP}/bundles/{which}")
        for tid, group, fn in TESTS:
            if sel and tid not in sel and group not in sel:
                continue
            try:
                fn()
                print(f"PASS {tid}", flush=True)
            except AssertionError as e:
                fails += 1
                print(f"FAIL {tid}: {str(e)[:600]}", flush=True)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"FAIL {tid}: {type(e).__name__}: {str(e)[:600]}", flush=True)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    n = len([t for t in TESTS if not sel or t[0] in sel or t[1] in sel])
    print(f"SUMMARY {n - fails}/{n} PASS · run_dump={RUN} · validate={VAL} · v3 사본 sha256 {V3_SHA}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
