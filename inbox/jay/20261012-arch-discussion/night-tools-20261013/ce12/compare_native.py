# -*- coding: utf-8 -*-
"""CE12-v1 이식 진단 1 · native 기록과 adapter 출력을 칸마다 대조한다 (CPU · Isaac 없이 · GPU 를 가린다).

분류: A/평가 · CE12-v1 이식 진단 1 대조기
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 18:19
근거: DESIGN-astra-12-common-eval.md 2.2 · 5.1 (순서 7) · 5.2 · adapters.py · dump_native_cts.py · dump_native_v2.py
요지: 같은 원시 상태 · 같은 raw action 순서를 adapter 에 다시 넣어 native 관측 · joint target 과 비교하고 첫 불일치를
      step · env · term · 이력 칸 · 관절 이름 (또는 광선 번호) 으로 보고한다. 판정 · 점수는 내지 않는다.
상태: 가짜 기록 (test_adapters.py T21) 으로만 시험. 실제 native 기록에는 아직 안 돌렸다 (기록이 없다)

사용 (CPU):
  PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
  "$PY" ce12/compare_native.py --dump out_ce12/native/<tag>/native.npz [--recompute_action] [--report <json>]
  meta 는 같은 폴더의 meta.json 을 읽는다 (--meta 로 바꿀 수 있다).
종료 코드: 0 모두 통과 · 1 불일치 · 2 기록이 형식에 안 맞음

허용 오차 (기록을 보기 전에 정했다)
  OBS_ATOL    = 1e-6  관측 칸. 계약 5.2 「같은 FP32 계산은 최대 절대차 1e-6 목표」. 관측은 뺄셈 · 곱셈 · clamp · where
                      뿐이라 GPU 와 CPU 가 같은 IEEE 결과를 내야 한다 (기대 0). 1e-6 은 그 이상 어긋난 칸을 모두 잡는다.
  TARGET_ATOL = 1e-6  joint target 칸 (raw * scale + offset 뒤 clip). 같은 근거.
  STATE_ATOL  = 1e-6  기억한 last action · 기본 자세 · 광선 지역 좌표.
  ACTION_ATOL = 1e-4  --recompute_action 일 때만. 체크포인트를 CPU 에서 다시 돌린 action 과 GPU native action.
                      행렬곱 합산 순서가 달라 비트 동일을 기대하지 않는다. 이 값은 측정이 아니라 사전 설정이다 (근거 미확인).
  이름 · 배치 · 차원 · 이력 길이는 정확히 같아야 한다 (수치 오차로 넘어갈 수 없다).
"""
import os

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OBS_ATOL = 1e-6
TARGET_ATOL = 1e-6
STATE_ATOL = 1e-6
ACTION_ATOL = 1e-4


def _import_adapters():
    sp = importlib.util.spec_from_file_location("ce12_adapters", os.path.join(HERE, "adapters.py"))
    m = importlib.util.module_from_spec(sp)
    sys.modules["ce12_adapters"] = m
    sp.loader.exec_module(m)
    return m


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class _Check:
    """한 비교 항목의 누적: 최대 절대차 · 넘은 칸 수 · 첫 위치 (step 오름차순)."""

    def __init__(self, name, atol):
        self.name, self.atol = name, atol
        self.max_abs, self.n_bad, self.n = 0.0, 0, 0
        self.first = None
        self.extra = {}

    def add(self, step, got, want, locate=None):
        got = np.asarray(got, dtype=np.float64)
        want = np.asarray(want, dtype=np.float64)
        if got.shape != want.shape:
            self.n_bad += 1
            if self.first is None:
                self.first = {"step": int(step), "shape": [list(got.shape), list(want.shape)]}
            return
        both_nan = np.isnan(got) & np.isnan(want)
        d = np.where(both_nan, 0.0, np.abs(got - want))
        d = np.where(np.isnan(d), np.inf, d)
        self.n += d.size
        if d.size:
            self.max_abs = max(self.max_abs, float(d.max()))
        bad = d > self.atol
        nb = int(bad.sum())
        self.n_bad += nb
        if nb and self.first is None:
            pos = np.argwhere(bad)[0]
            env = int(pos[0])
            idx = int(pos[1]) if len(pos) > 1 else None
            self.first = {"step": int(step), "env": env, "index": idx,
                          "adapter": float(got[tuple(pos)]), "native": float(want[tuple(pos)])}
            if locate is not None and idx is not None:
                self.first["where"] = locate(idx)

    def flag(self, ok, detail):
        if not ok:
            self.n_bad += 1
            if self.first is None:
                self.first = {"step": None, "detail": detail}
        self.extra["detail"] = detail

    def result(self):
        return dict({"name": self.name, "atol": self.atol, "ok": self.n_bad == 0, "max_abs": self.max_abs,
                     "n_bad": self.n_bad, "n_compared": self.n, "first": self.first}, **self.extra)


def compare(npz_path, meta_path=None, A=None, recompute_action=False, checkpoint=None, agent_yaml=None):
    A = A or _import_adapters()
    d = dict(np.load(npz_path, allow_pickle=False))
    meta_path = meta_path or os.path.join(os.path.dirname(npz_path), "meta.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}
    model = str(meta.get("model") or (d["model"].item() if "model" in d else ""))
    rep = {"tool": "compare_native.py", "contract": A.CONTRACT, "npz": npz_path.replace("\\", "/"), "npz_sha256": _sha(npz_path),
           "meta": meta_path.replace("\\", "/") if os.path.exists(meta_path) else None, "model": model,
           "tolerances": {"obs": OBS_ATOL, "target": TARGET_ATOL, "state": STATE_ATOL, "action": ACTION_ATOL},
           "adapters_sha256": _sha(A.__file__), "t": time.strftime("%Y-%m-%d %H:%M:%S")}
    if model not in ("cts_student", "v2"):
        return dict(rep, status="invalid", reason=f"모르는 model {model!r}")
    missing = A.check_dump_keys(d, model)
    if missing:
        return dict(rep, status="invalid", reason=f"빠진 열쇠 {missing}")
    T, N = d["raw_action"].shape[0], d["raw_action"].shape[1]
    art = [str(x) for x in d["art_joint_names"]]
    obs_names = [str(x) for x in d["obs_joint_names"]]
    act_names = [str(x) for x in d["action_joint_names"]]
    try:
        if model == "cts_student":
            ad = A.CTSStudentAdapter.from_source(N)
            groups = ["policy", "single_obs"]
        else:
            ad = A.V2Adapter.from_env_yaml(obs_names, N, act_names)
            groups = ["policy"]
    except (KeyError, ValueError) as e:
        return dict(rep, status="invalid", reason=f"adapter 를 못 지음: {type(e).__name__}: {e}")
    checks = []
    c = _Check("names.obs_vs_action_joint_names", 0)
    c.flag(obs_names == act_names, {"obs": obs_names, "action": act_names})
    checks.append(c)
    c = _Check("names.adapter_obs_joint_names", 0)
    c.flag(ad.obs_joint_names == obs_names, {"adapter": ad.obs_joint_names, "native": obs_names})
    checks.append(c)
    c = _Check("names.adapter_action_joint_names", 0)
    c.flag(ad.action_joint_names == act_names, {"adapter": ad.action_joint_names, "native": act_names})
    checks.append(c)
    c = _Check("names.articulation_has_all", 0)
    c.flag(set(obs_names) <= set(art), {"articulation": art})
    checks.append(c)
    lay = meta.get("obs_layout")
    for g in groups:
        c = _Check(f"layout.{g}", 0)
        want = [(n, b - a) for n, a, b, H, dd in ad.layout(g)]
        if lay and g in lay:
            got = [(n, int(np.prod(x))) for n, x in zip(lay[g]["names"], lay[g]["dims"])]
            c.flag(got == want, {"native": got, "adapter": want})
        else:
            c.flag(False, "meta.json 에 obs_layout 이 없다 (배치를 확인하지 못함)")
        c2 = _Check(f"shape.obs_{g}", 0)
        c2.flag(d["obs_" + g].shape[-1] == sum(x[1] for x in want), {"native_dim": int(d["obs_" + g].shape[-1])})
        checks += [c, c2]
    c = _Check("default_joint_pos", STATE_ATOL)
    dq0 = A.take_by_names(torch.as_tensor(d["default_joint_pos"]), art, ad.obs_joint_names).numpy()
    c.add(0, np.tile(ad._q0.numpy(), (N, 1)), dq0)
    checks.append(c)
    c = _Check("default_joint_vel", STATE_ATOL)
    c.add(0, np.tile(ad._dq0.numpy(), (N, 1)), A.take_by_names(torch.as_tensor(d["default_joint_vel"]), art, ad.obs_joint_names).numpy())
    checks.append(c)
    if model == "v2":
        c = _Check("rays.local_xy_vs_grid", STATE_ATOL)
        g = A.grid_pattern_local(ad.height["size"], ad.height["resolution"], ad.height["ordering"]).numpy()
        c.add(0, g[None], d["ray_starts_local"][None, :, :2])
        c.extra["ray_start_z_offset"] = sorted(set(np.round(d["ray_starts_local"][:, 2], 6).tolist()))
        checks.append(c)

    def loc(g):
        return lambda i: ad.locate(g, i)

    c_obs = {g: _Check(f"obs.{g}", OBS_ATOL) for g in groups}
    c_peek = _Check("self.debug_read_does_not_advance", 0)
    c_last = _Check("state.last_action_memory", STATE_ATOL)
    c_tgt = _Check("joint_target", TARGET_ATOL)
    c_off = _Check("info.offset_minus_default (motor offset DR 크기 · 판정 아님)", float("inf"))
    off_max = 0.0
    obs_seq = []
    for k in range(T + 1):
        st = A.state_from_dump(d, k)
        c_last.add(k, ad._last_raw.numpy(), d["last_action"][k],
                   locate=lambda i: {"joint": ad.action_joint_names[i]})
        o = ad.observe(st)
        p = ad.observe(st, update_history=False)
        for g in groups:
            c_peek.add(k, p[g].numpy(), o[g].numpy())
            c_obs[g].add(k, o[g].numpy(), d["obs_" + g][k], locate=loc(g))
        obs_seq.append({g: o[g].clone() for g in groups})
        if k < T:
            raw = torch.as_tensor(d["raw_action"][k])
            tgt = ad.decode_action(raw, offset=torch.as_tensor(d["action_offset"][k]))
            c_tgt.add(k, tgt.numpy(), d["joint_target"][k], locate=lambda i: {"joint": ad.action_joint_names[i]})
            t_def = ad.decode_action(raw, remember=False)
            off_max = max(off_max, float((tgt - t_def).abs().max()))
            ids = np.nonzero(d["reset_after_step"][k])[0]
            if len(ids):
                ad.reset(torch.as_tensor(ids))
    c_off.extra["max_abs_target_change_m"] = off_max
    checks += [c_obs[g] for g in groups] + [c_peek, c_last, c_tgt, c_off]
    if model == "cts_student":
        # native 자체 일관성 (q_eval_cmdr.py:600-601 과 같은 검사): 최신 명령 칸 = 명령 항
        c = _Check("native.latest_command_slot_equals_command", STATE_ATOL)
        a, b = ad.history_slice("policy", ad._cmd_term(), -1)
        for k in range(T + 1):
            c.add(k, d["obs_policy"][k][:, a:b], d["command"][k])
        c.extra["slice"] = [a, b]
        checks.append(c)
    if recompute_action:
        checks += _recompute(A, ad, d, meta, model, obs_seq, groups, checkpoint, agent_yaml)
    res = [x.result() for x in checks]
    fails = [r for r in res if not r["ok"]]
    first = None
    for r in fails:
        f = r["first"] or {}
        key = (f.get("step") if f.get("step") is not None else -1)
        if first is None or key < first[0]:
            first = (key, dict(f, check=r["name"]))
    rep.update(status="pass" if not fails else "mismatch", checks=res, first_failure=None if first is None else first[1],
               T=int(T), N=int(N), reset_events=int(d["reset_after_step"].sum()),
               cells=[str(x) for x in d["cell_names"]])
    return rep


def _recompute(A, ad, d, meta, model, obs_seq, groups, checkpoint, agent_yaml):
    from tensordict import TensorDict
    import contextlib
    import io
    ck = checkpoint or meta.get("checkpoint")
    out = []
    c_ad = _Check("action.recompute_from_adapter_obs", ACTION_ATOL)
    c_nat = _Check("action.recompute_from_native_obs", ACTION_ATOL)
    if not ck or not os.path.exists(ck):
        c_ad.flag(False, f"체크포인트가 없다: {ck}")
        return [c_ad]
    with contextlib.redirect_stdout(io.StringIO()):
        if model == "cts_student":
            m, info = A.load_cts_policy_cpu(ck, agent_yaml or meta.get("agent_yaml"))
        else:
            m, info = A.load_v2_policy_cpu(ck, agent_yaml or A.V2_AGENT_YAML)
    c_ad.extra["policy"] = info
    T = d["raw_action"].shape[0]
    for k in range(T):
        a1 = ad.infer(m, obs_seq[k])
        c_ad.add(k, a1.numpy(), d["raw_action"][k])
        nat = {g: torch.as_tensor(d["obs_" + g][k]) for g in groups}
        a2 = ad.infer(m, nat)
        c_nat.add(k, a2.numpy(), d["raw_action"][k])
    return [c_ad, c_nat]


def _print(rep):
    print(f"[CE12-COMPARE] {rep['model']} {rep['npz']} T={rep.get('T')} N={rep.get('N')} resets={rep.get('reset_events')}")
    if rep["status"] == "invalid":
        print("[CE12-COMPARE] INVALID", rep.get("reason"))
        return
    for r in rep["checks"]:
        s = "PASS" if r["ok"] else "FAIL"
        line = f"{s} {r['name']} max_abs={r['max_abs']:.3g} n_bad={r['n_bad']}"
        if not r["ok"] and r["first"]:
            line += " first=" + json.dumps(r["first"], ensure_ascii=False)[:500]
        print(line)
    print("[CE12-COMPARE] ALL PASS" if rep["status"] == "pass" else
          "[CE12-COMPARE] MISMATCH first=" + json.dumps(rep["first_failure"], ensure_ascii=False)[:500])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--meta", default=None)
    ap.add_argument("--report", default=None, help="기본: npz 옆 compare_report_<시각>.json (덮어쓰지 않는다)")
    ap.add_argument("--recompute_action", action="store_true")
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--agent_yaml", default=None)
    a = ap.parse_args(argv)
    torch.set_num_threads(2)
    rep = compare(a.dump, a.meta, recompute_action=a.recompute_action, checkpoint=a.checkpoint, agent_yaml=a.agent_yaml)
    out = a.report or os.path.join(os.path.dirname(a.dump), f"compare_report_{time.strftime('%Y%m%d-%H%M%S')}.json")
    if os.path.exists(out):
        print("STOP: 보고 파일이 이미 있다", out)
        return 2
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    _print(rep)
    print("[CE12-COMPARE] report", out)
    return {"pass": 0, "mismatch": 1}.get(rep["status"], 2)


if __name__ == "__main__":
    sys.exit(main())
