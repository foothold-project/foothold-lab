"""창 2 자동 기동 판정 장치 (SONNET-X25). 창 1 두 판이 끝나기를 기다렸다가 고정 칸 평가 세 열을 돌리고, window2_criteria 의 기준으로 판정해 통과하면 창 2 를 순서대로 띄운다.

    python -m foothold_s2.window2_gate --ex30-run <창 1 EX-30 실행 폴더> --ex30-log <EX-30 rsl_rl 폴더> --ex31-run <...> --ex31-log <...> --out <판정 폴더>

실행 폴더 = run_ex3031_window1.sh 의 출력(train.log · rc.txt), rsl_rl 폴더 = model_1750.pt 가 있는 곳. 판정 json(window2_decision.json)에는 기준 파일 SHA · 숫자 · 사유가 남는다.
통과: EX-30 창 2 -> (DONE 확인) -> EX-31 창 2, GPU0 순차. 실패: 아무것도 띄우지 않고 판정 json 과 사유만 남긴다. 판정 폴더에 ABORT 파일을 만들면 다음 단계 시작 전에 멈춘다.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from foothold_s2 import ex3031_window1_contract as w1
from foothold_s2 import ex3031_window2_contract as w2
from foothold_s2 import window2_criteria as C
from foothold_s2.eval import compare_map_modes as cmp

ROOT = Path(__file__).resolve().parents[1]
BASH = "C:/Program Files/Git/bin/bash.exe"
DEVICE = "cuda:0"


def count_bad(text: str) -> dict:
    return {p: len(re.findall(re.escape(p), text, flags=re.IGNORECASE)) for p in C.BAD_LOG_PATTERNS}


def read_text(path) -> str:
    p = Path(path)

    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def check_window1_run(run_dir, log_dir) -> list[str]:
    """창 1 한 판이 정상 완료인지: rc=0 · DONE 줄 · Traceback/OOM 0 · 산출물 · 마지막 저장. 문제 목록(비어 있으면 정상)."""
    problems = []
    rc, log = read_text(Path(run_dir) / "rc.txt"), read_text(Path(run_dir) / "train.log")

    if "rc=0" not in rc:
        problems.append(f"rc.txt 가 rc=0 이 아니다: {rc.strip()!r}")
    if "DONE 줄 없음" in rc or "EX3031_W1_DONE" not in log:
        problems.append("EX3031_W1_DONE 이 없다")
    bad = {k: v for k, v in count_bad(log).items() if v}

    if bad:
        problems.append(f"train.log 에 {bad}")
    missing = w1.check_outputs(log_dir)

    if missing:
        problems.append(f"창 1 산출물 빠짐 {missing}")

    return problems


def check_eval_run(d) -> list[str]:
    problems = []
    rc, log = read_text(Path(d) / "rc.txt"), read_text(Path(d) / "run.log")

    if "rc=0" not in rc or "DONE 줄 없음" in rc:
        problems.append(f"{d}: rc.txt {rc.strip()!r}")
    if log.count("MAPMODE_DONE") != 1:
        problems.append(f"{d}: MAPMODE_DONE {log.count('MAPMODE_DONE')} 번")
    bad = {k: v for k, v in count_bad(log).items() if v}

    if bad:
        problems.append(f"{d}: run.log 에 {bad}")
    if not (Path(d) / "map_modes.json").is_file():
        problems.append(f"{d}: map_modes.json 없음")

    return problems


def _cell(res, mode, cmd):
    return res["modes"][mode][cmd]


def judge(parent: dict, children: dict) -> dict:
    """parent = 부모 B1500 의 map_modes.json, children = {"EX-30": json, "EX-31": json}. 반환: {"passed", "reasons", "rows"}."""
    reasons, rows = [], []
    results = {"parent": parent, **children}

    shas = {name: (r.get("fixed_terrain") or {}).get("assignment_sha256") for name, r in results.items()}
    if any(v is None for v in shas.values()) or len(set(shas.values())) != 1:                 # 세 평가 모두 고정 칸 기록이 있고 배열 SHA 가 같아야 한다(없거나 다르면 멈춘다)
        return {"passed": False, "reasons": [f"고정 지형 칸 기록이 없거나 배열 SHA 가 다르다: {shas}"], "rows": []}
    try:
        cmp.check_same_conditions(results)
    except ValueError as err:                                     # 조건이 다르면 비교 자체를 하지 않는다
        return {"passed": False, "reasons": [f"조건 불일치: {err}"], "rows": []}
    if parent.get("checkpoint_iter") != C.PARENT_ITER:
        reasons.append(f"부모 회차 {parent.get('checkpoint_iter')} != {C.PARENT_ITER}")
    for exp, res in children.items():
        if res.get("checkpoint_iter") != C.CHILD_ITER:
            reasons.append(f"{exp} 회차 {res.get('checkpoint_iter')} != {C.CHILD_ITER}")
    for cmd in C.COMMANDS:
        base = _cell(parent, C.PARENT_MODE, cmd)
        base_vx, base_alive = base[C.VX_KEY], base[C.ALIVE_KEY] / parent["envs"]

        if not base_vx > 0:
            reasons.append(f"부모 {cmd} 전진 {base_vx} <= 0 이라 비율 기준이 뜻이 없다")
        for exp, res in children.items():
            cell = _cell(res, C.CHILD_MODE, cmd)
            vx, alive = cell[C.VX_KEY], cell[C.ALIVE_KEY] / res["envs"]
            vx_ok = bool(base_vx > 0 and vx >= C.VX_RATIO_MIN * base_vx)
            alive_ok = bool(alive >= base_alive - C.ALIVE_DROP_MAX)
            rows.append({"exp": exp, "cmd": cmd, "vx": vx, "parent_vx": base_vx, "vx_ratio": (vx / base_vx) if base_vx > 0 else None, "vx_ok": vx_ok,
                         "alive": alive, "parent_alive": base_alive, "alive_ok": alive_ok})
            if not vx_ok:
                reasons.append(f"{exp} {cmd} 전진 {vx:.3f} < {C.VX_RATIO_MIN} x 부모 {base_vx:.3f}")
            if not alive_ok:
                reasons.append(f"{exp} {cmd} 생존 {alive:.3f} < 부모 {base_alive:.3f} - {C.ALIVE_DROP_MAX}")

    return {"passed": not reasons, "reasons": reasons, "rows": rows}


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(out, name, data):
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def default_run(cmd, **kw):
    """숨김 창으로 실행하고 끝날 때까지 기다린다(Windows)."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    return subprocess.run(cmd, stdin=subprocess.DEVNULL, creationflags=flags, **kw).returncode


def orchestrate(opts, run=default_run, sleep=time.sleep, now=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"), poll_s=30.0) -> dict:
    out = Path(opts.out)
    runs = {"EX-30": (Path(opts.ex30_run), Path(opts.ex30_log)), "EX-31": (Path(opts.ex31_run), Path(opts.ex31_log))}
    decision = {"criteria_file_sha256": C.criteria_sha256(), "criteria": {k: getattr(C, k) for k in ("COMMANDS", "PARENT_MODE", "CHILD_MODE", "VX_KEY", "ALIVE_KEY", "VX_RATIO_MIN", "ALIVE_DROP_MAX", "BAD_LOG_PATTERNS")},
                "started": now(), "runs": {k: [str(a), str(b)] for k, (a, b) in runs.items()}, "launched": []}

    def finish(passed, reasons, **extra):
        decision.update({"passed": passed, "reasons": reasons, "finished": now(), **extra})
        _write(out, "window2_decision.json", decision)

        return decision

    waited = 0.0
    while not all((r / "rc.txt").is_file() for r, _ in runs.values()):                         # 두 판이 모두 끝나기를 기다린다(rc.txt 가 생김)
        if (out / "ABORT").exists():
            return finish(False, ["ABORT 파일로 멈춤(창 1 대기 중)"])
        if opts.wait_limit_s is not None and waited >= opts.wait_limit_s:
            return finish(False, [f"창 1 이 {opts.wait_limit_s} 초 안에 끝나지 않았다"])
        sleep(poll_s)
        waited += poll_s
    problems = {exp: check_window1_run(r, lg) for exp, (r, lg) in runs.items()}
    decision["window1_problems"] = problems

    if any(problems.values()):
        return finish(False, [f"창 1 {exp}: {p}" for exp, ps in problems.items() for p in ps])
    eval_out = out / "eval"
    parent_dir, dirs = eval_out / "parent_b1500", {"EX-30": eval_out / "ex30_1750", "EX-31": eval_out / "ex31_1750"}

    if (out / "ABORT").exists():
        return finish(False, ["ABORT 파일로 멈춤(평가 전)"])
    rc = run([BASH, str(ROOT / "foothold_s2/run_eval_window1.sh"), DEVICE, str(runs["EX-30"][1]), str(runs["EX-31"][1]), str(eval_out)], cwd=str(ROOT))
    decision["eval_rc"] = rc
    eval_problems = [p for d in (parent_dir, *dirs.values()) for p in check_eval_run(d)]
    decision["eval_problems"] = eval_problems

    if eval_problems:
        return finish(False, [f"평가: {p}" for p in eval_problems])
    verdict = judge(_load(parent_dir / "map_modes.json"), {exp: _load(d / "map_modes.json") for exp, d in dirs.items()})
    decision["judge"] = verdict

    if not verdict["passed"]:
        return finish(False, verdict["reasons"])
    for exp in ("EX-30", "EX-31"):                                                             # 순서 고정: EX-30 끝(DONE 확인) -> EX-31
        if (out / "ABORT").exists():
            return finish(False, [f"ABORT 파일로 멈춤({exp} 창 2 시작 전)"])
        w2_out = out / f"window2_{exp.lower()}_{now()}"
        ckpt = runs[exp][1] / w2.CHILD_CKPT_NAME
        decision["launched"].append({"exp": exp, "out": str(w2_out), "ckpt": str(ckpt), "at": now()})
        _write(out, "window2_decision.json", {**decision, "passed": True, "state": f"{exp} 창 2 실행 중"})
        run([BASH, str(ROOT / "foothold_s2/run_ex3031_window2.sh"), exp, DEVICE, str(ckpt), str(w2_out)], cwd=str(ROOT))
        rc_txt, log = read_text(w2_out / "rc.txt"), read_text(w2_out / "train.log")
        bad = {k: v for k, v in count_bad(log).items() if v}
        w2_problems = ([] if "rc=0" in rc_txt and "DONE 줄 없음" not in rc_txt and "EX3031_W2_DONE" in log else [f"{exp} 창 2 가 DONE 으로 끝나지 않았다: {rc_txt.strip()!r}"]) + ([f"train.log 에 {bad}"] if bad else [])
        decision["launched"][-1]["problems"] = w2_problems

        if w2_problems:
            return finish(False, [f"{exp} 창 2 실패, 다음 판은 띄우지 않았다: {w2_problems}"], passed_judge=True)

    return finish(True, [], passed_judge=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    for name in ("ex30-run", "ex30-log", "ex31-run", "ex31-log", "out"):
        ap.add_argument(f"--{name}", required=True)
    ap.add_argument("--wait-limit-s", type=float, default=None)
    opts = ap.parse_args(argv)
    result = orchestrate(opts)
    print("WINDOW2_GATE " + json.dumps({k: result.get(k) for k in ("passed", "reasons")}, ensure_ascii=False), flush=True)

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
