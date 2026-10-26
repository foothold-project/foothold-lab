"""판정 입력 읽기와 회전 통계 (JUDGE-SPEC v0.2 J-T1 · J-T2). 순수 numpy, Kit 없음.

- `turn_stats`: 16 env 회전 진단 한 경우의 통계. env 마다 q_e = 명령 부호 x 살아 있는 표본 평균 wz, 안 넘어진(kept) env 만 같은 무게로 평균해 Q 를 낸다.
  절댓값 · pooled 평균 · alive_end 분모는 판정에 쓰지 않는다(옛 pooled 값은 `yaw_pooled_legacy` 로 대조용으로만 남긴다).
- `read_map64`: 64 env 고정 칸 평가 JSON 을 읽고 칸 SHA · env 수 · 스텝 수가 다르면 거절한다.
- `load_bundle`: 한 저장본의 평가 묶음(16 env 여섯 경우 + 64 env)을 판정 함수(`judge_gate`)가 받는 모양으로 만든다.

부호는 `turn_probe_plan.PROTOCOLS[경우]["cmd"][2]` 한 곳에서 읽는다. 문턱은 여기 두지 않는다(`judge_gate.THRESHOLDS`).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from foothold_s2.eval import turn_probe_plan as P

SPEC_VERSION = "JUDGE-SPEC v0.2"
HZ = 200.0
FEET = (4, 8, 14, 18)                               # 발 링크 번호(결과 JSON 의 link_names 에서 다시 뽑아 같은지 단언한다)
CONTACT_N = 1.0                                     # 네 발 동시 접촉의 접촉력 문턱
PROBE16_SHA12 = "7f49a1e935ea"                      # 16 env 진단의 고정 칸 해시 앞 12 자리
MAP64_SHA = "c3884d686592596ee6ac7b2cdfc94e0b1d3f6d84dbca66c52ad20a0400e2358f"
MAP64_ENVS, MAP64_STEPS = 64, 300
SIX_CASES = ("indep_left", "indep_right", "left_then_right", "right_then_left", "fwd_then_left", "fwd_then_right")
WALK_CASES = ("walk_turn_left", "walk_turn_right")
MAP64_CMDS = ("fwd0.5", "fwd1.0", "spin+1.2", "spin-1.2")
EVAL_MODES = ("eval_gt", "eval_pred", "probe_prop_only", "none")


class JudgeInputError(ValueError):
    """판정에 쓸 수 없는 입력(칸 SHA 불일치 · 모양 틀림). 이 입력으로는 판정하지 않는다."""


def sha256_file(path) -> str:
    h = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)

    return h.hexdigest()


def case_sign(case: str) -> int:
    """명령 wz 의 부호. 표는 turn_probe_plan.PROTOCOLS 한 곳에서만 읽는다."""
    wz = P.PROTOCOLS[case]["cmd"][2]

    if wz == 0:
        raise JudgeInputError("%s: 명령 wz 가 0 이라 회전 부호가 없다" % case)

    return 1 if wz > 0 else -1


def _arrays(src):
    if isinstance(src, (str, Path)):
        with np.load(src) as z:
            return {k: z[k] for k in z.files}

    return dict(src)


def turn_stats(src, case: str, feet=FEET) -> dict:
    """한 경우의 통계. `src` 는 arrays_<경우>.npz 경로 또는 {alive, kept, wz, force, (vx)} 사전.

    Q = mean_{e in kept}( 부호 x mean_t( wz[e,t] | alive[e,t] ) ), C = mean_{e in kept}( mean_t( 네 발 접촉 | alive ) ).
    kept 가 없으면 Q · C 는 NaN. 반환 필드: Q C kept n_env n_fallen n_ge06 n_lt012 n_neg qmin qmax mean_abs yaw_pooled_legacy alive_end q_all_envs_mean vx_integral_kept_mean nonfinite.
    """
    z = _arrays(src)
    sign = case_sign(case)
    alive = np.asarray(z["alive"], dtype=bool)

    if "kept" not in z:
        raise JudgeInputError("kept 배열이 없다(분모를 알 수 없다): 이 입력은 판정하지 않는다")

    kept_in = np.asarray(z["kept"], dtype=bool)
    wz = np.asarray(z["wz"], dtype=np.float64)
    force = np.asarray(z["force"], dtype=np.float64)
    n = alive.shape[0]

    if alive.shape != wz.shape or kept_in.shape != (n,):
        raise JudgeInputError("alive %s · wz %s · kept %s 모양이 맞지 않는다" % (alive.shape, wz.shape, kept_in.shape))

    cnt = alive.sum(axis=1)
    has = cnt > 0
    safe = np.maximum(cnt, 1)
    nonfinite = bool((~np.isfinite(wz[alive])).any() or (~np.isfinite(force[alive])).any())
    mean_wz = np.where(has, (np.where(alive, wz, 0.0)).sum(axis=1) / safe, np.nan)
    q = sign * mean_wz
    four = (force[..., list(feet)] > CONTACT_N).all(axis=-1)
    c_env = np.where(has, (four & alive).sum(axis=1) / safe, np.nan)
    kept = kept_in & has                                                              # 살아 있는 표본이 없는 env 는 kept 로 치지 않는다(NaN 이 평균에 들어가지 않게)
    nk = int(kept.sum())
    qk, ck = q[kept], c_env[kept]
    abs_env = np.where(has, (np.where(alive, np.abs(wz), 0.0)).sum(axis=1) / safe, np.nan)
    pooled = float(sign * wz[alive].mean()) if alive.any() else float("nan")
    vx_int = float("nan")

    if "vx" in z:
        vx = np.asarray(z["vx"], dtype=np.float64)
        vx_env = (np.where(alive, vx, 0.0)).sum(axis=1) / HZ
        vx_int = float(vx_env[kept].mean()) if nk else float("nan")

    return {
        "case": case, "sign": sign, "n_env": int(n), "kept": nk, "n_fallen": int(n - nk), "alive_end": int(alive[:, -1].sum()),
        "Q": float(qk.mean()) if nk else float("nan"), "C": float(ck.mean()) if nk else float("nan"),
        "n_ge06": int((qk >= 0.6).sum()), "n_lt012": int((qk < 0.12).sum()), "n_neg": int((qk < 0.0).sum()),
        "qmin": float(qk.min()) if nk else float("nan"), "qmax": float(qk.max()) if nk else float("nan"),
        "mean_abs": float(abs_env[kept].mean()) if nk else float("nan"),
        "yaw_pooled_legacy": pooled, "q_all_envs_mean": float(np.nanmean(q)) if has.any() else float("nan"),
        "vx_integral_kept_mean": vx_int, "nonfinite": nonfinite,
    }


def _read_json(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def feet_from_probe(probe: dict) -> tuple:
    """probe_result.json 의 static.link_names 에서 발 링크 번호를 다시 뽑는다. [4, 8, 14, 18] 과 다르면 거절한다."""
    names = probe["static"]["link_names"]
    idx = tuple(i for i, nm in enumerate(names) if P.classify_link(nm) == "foot")

    if idx != FEET:
        raise JudgeInputError("발 링크 번호 %s 가 %s 와 다르다" % (idx, FEET))

    return idx


def read_turn_dir(d, cases=SIX_CASES, strict_sha=True) -> dict:
    """<판>/arrays_<경우>.npz 들을 읽어 {경우: turn_stats} 로. 파일이 없는 경우는 목록에서 빠진다(호출자가 missing 으로 읽는다).

    probe_result.json 이 있으면 고정 칸 SHA 앞 12 자리(7f49a1e935ea)와 발 링크 번호를 단언한다.
    """
    d = Path(d)
    pj = d / "probe_result.json"

    if pj.exists():
        probe = _read_json(pj)
        sha = ((probe.get("fixed_terrain") or {}).get("assignment_sha256") or "")

        if strict_sha and not sha.startswith(PROBE16_SHA12):
            raise JudgeInputError("%s: 16 env 고정 칸 SHA %r 가 %s 와 다르다(칸이 다른 숫자를 섞지 않는다)" % (d, sha[:12], PROBE16_SHA12))

        feet = feet_from_probe(probe)
    else:
        feet = FEET

    out = {}

    for c in cases:
        f = d / ("arrays_%s.npz" % c)

        if f.exists():
            out[c] = turn_stats(f, c, feet)
            out[c]["source_sha256"] = sha256_file(f)

    return out


def read_map64(path, strict=True) -> dict:
    """64 env 평가 JSON -> {"modes": {모드: {명령: {...}}}, "sha256": 파일 해시, "checkpoint_sha256": ...}.

    칸 SHA(c3884d68...) · envs 64 · steps 300 이 다르면 JudgeInputError(평가 분포가 다른 숫자를 섞지 않는다).
    각 명령 칸: fwd_m(body_vx_integral_median_m) · yaw_follow · alive · stalled · tilt. 회전 두 명령(spin±)의 생존은 모드마다 `rot_alive_min` 으로 묶는다.
    """
    d = _read_json(path)
    sha = ((d.get("fixed_terrain") or {}).get("assignment_sha256"))

    if strict and (sha != MAP64_SHA or d.get("envs") != MAP64_ENVS or d.get("steps") != MAP64_STEPS):
        raise JudgeInputError("%s: 칸 SHA %r · envs %r · steps %r 가 기준(%s · 64 · 300)과 다르다" % (path, (sha or "")[:12], d.get("envs"), d.get("steps"), MAP64_SHA[:12]))

    modes = {}

    for mode, cmds in d["modes"].items():
        row = {}

        for cmd, v in cmds.items():
            row[cmd] = {"fwd_m": v["body_vx_integral_median_m"], "yaw_follow": v["yaw_follow_median"], "alive": int(v["alive_envs_at_end"]),
                        "stalled": v["stalled_fraction_2to4s"], "tilt": v["tilt_rad_mean_alive"], "gt_used": v.get("gt_used")}
        modes[mode] = row

    return {"modes": modes, "sha256": sha256_file(path), "checkpoint_sha256": d.get("checkpoint_sha256"), "map_input": d.get("map_input")}


def finite_everywhere(obj) -> bool:
    """사전 · 목록 안의 모든 수가 유한한가(NaN · inf 가 하나라도 있으면 거짓)."""
    if isinstance(obj, dict):
        return all(finite_everywhere(v) for v in obj.values())

    if isinstance(obj, (list, tuple)):
        return all(finite_everywhere(v) for v in obj)

    if isinstance(obj, float):
        return math.isfinite(obj)

    return True


def load_bundle(label, turn_dirs=None, map64_json=None, launch_rc_file=None, cases=SIX_CASES) -> dict:
    """한 저장본의 평가 묶음. 판정 함수가 받는 모양:

    {"label", "turn": {모드: {경우: 통계}}, "map64": {모드: {명령: {...}}} | None, "missing": 파일이 «없는» 것이 있는가, "missing_what": [...],
     "launch_failed": 기동 실패(rc 파일에 rc=1 이상 · 없음), "nonfinite": 비유한값이 있는가, "sources": {이름: sha256}}.

    파일이 없는 것은 missing 이다. 관측된 낙상(kept 작음)은 missing 이 아니다.
    """
    b = {"label": label, "turn": {}, "map64": None, "missing": False, "missing_what": [], "launch_failed": False, "nonfinite": False, "sources": {}}

    for mode, d in (turn_dirs or {}).items():
        dd = Path(d)
        stats = read_turn_dir(dd, cases) if dd.is_dir() else {}
        b["turn"][mode] = stats
        absent = [c for c in cases if c not in stats]

        if absent:
            b["missing"] = True
            b["missing_what"].append("turn16/%s: %s" % (mode, ",".join(absent)))

        for c, s in stats.items():
            b["nonfinite"] = b["nonfinite"] or s["nonfinite"]
            b["sources"]["turn16/%s/%s" % (mode, c)] = s["source_sha256"]

    if map64_json is not None:
        if Path(map64_json).exists():
            m = read_map64(map64_json)
            b["map64"] = m["modes"]
            b["sources"]["map64"] = m["sha256"]
            b["nonfinite"] = b["nonfinite"] or not finite_everywhere(m["modes"])
        else:
            b["missing"] = True
            b["missing_what"].append("map64")

    if launch_rc_file is not None:
        p = Path(launch_rc_file)
        txt = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        import re

        if "없음" in txt or re.search(r"rc=[1-9]", txt):
            b["launch_failed"] = True

    return b


def format_six_table(dirs, cases=SIX_CASES) -> str:
    """여섯 경우 표(마크다운). 칸: `Q / C (kept, alive_end)` 와 옛 pooled 값 `legacy`. `six_table.py` 가 이 함수를 부른다(pooled 는 legacy 열로만 남는다).

    kept 가 문턱(12) 미만이면 Q 옆에 `무효` 를 붙인다(평균은 적되 판정에는 안 쓴다). 분모 열 없이 Q 를 적지 않는다.
    """
    lines = ["| 판 | " + " | ".join(cases) + " |", "|---|" + "---|" * len(cases)]

    for d in dirs:
        d = Path(d)
        stats = read_turn_dir(d, cases)
        cells = []

        for c in cases:
            s = stats.get(c)

            if s is None:
                cells.append("-")
                continue

            tag = " 무효" if s["kept"] < 12 else ""
            cells.append("%+.3f / %.3f (kept %d, alive_end %d)%s legacy %+.3f" % (s["Q"], s["C"], s["kept"], s["alive_end"], tag, s["yaw_pooled_legacy"]))

        lines.append("| %s | %s |" % (d.name, " | ".join(cells)))

    return "\n".join(lines) + "\n"
