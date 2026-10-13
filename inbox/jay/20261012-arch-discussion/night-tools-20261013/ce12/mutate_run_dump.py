# -*- coding: utf-8 -*-
"""break-the-guard: run_dump.py · validate_dump.py 의 일부러 틀린 사본마다 test_run_dump.py 의 지정 시험이 FAIL 해야 한다.

분류: A/평가 · CE12-v1 이식 진단 1 · 실행기 · 검증기 시험의 시험
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 19:03
근거: lead 지시 10/13 19:03 · _eval/mutate_isaac_slot.py 와 같은 방식 (읽기만)
요지: 사본은 ce12 안 _mut_*.py 로 만들고 (실행기가 자기 위치로 _eval 을 찾는다) 끝나면 지운다. 원본은 건드리지 않는다.
      변이가 실행기 것이면 RT 묶음만, 검증기 것이면 VT 묶음만 돌린다 (지정 시험은 늘 그 묶음 안에 있다).
상태: 시험 파일
판정: 종료 코드 1 · 지정 시험 모두 FAIL · Traceback 없음 이면 CAUGHT. 모두 CAUGHT 면 「ALL CAUGHT」.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = {"run": open(os.path.join(HERE, "run_dump.py"), encoding="utf-8").read(),
       "val": open(os.path.join(HERE, "validate_dump.py"), encoding="utf-8").read()}

M = [
    ("run", "MR01 slot 에 --usd_root · --attempt 를 안 줌 (보고서 1 판의 결함)",
     '"--usd_root", P["usd"], "--attempt", attempt,\n', '\n', ["RT1", "RT7"]),
    ("run", "MR02 이미 있는 출력을 거절하지 않음",
     'taken = [P[k] for k in ("out", "log", "slot", "guard") if os.path.exists(P[k])]', 'taken = []', ["RT3", "RT4"]),
    ("run", "MR03 v2 변환 흔적 (assigned.jsonl · 로그) 무시",
     'elif rc == 0 and (iso["assigned_lines"] or iso["log_usd_folders"]):', 'elif False:', ["RT9"]),
    ("run", "MR04 v2 격리 상태 없음을 무시",
     'if rc == 0 and (iso["isolate_state"] is None or not iso["patched_by"]):', 'if False:', ["RT10"]),
    ("run", "MR05 멈춤 파일 · 마감을 실행기에서 안 봄",
     'why = ("stop file" if a.stop_file and os.path.exists(a.stop_file) else', 'why = ("" if True else', ["RT5"]),
    ("run", "MR06 scan_dirs 에서 out_ce12/native 를 뺌",
     'for d in ("out_ce12/native", "out_branch", "out_uncr", "out_rand"))', 'for d in ("out_branch", "out_uncr", "out_rand"))', ["RT1"]),
    ("run", "MR07 v2 에 FOOTHOLD_USD_ROOT 를 안 넘김",
     'return guard + dump, {"FOOTHOLD_USD_ROOT": P["usd"]}', 'return guard + dump, {}', ["RT2", "RT8"]),
    ("run", "MR08 tag 검사 없음 (경로가 들어감)",
     'if not TAG_RE.match(a.tag):', 'if False:', ["RT6"]),
    ("run", "MR09 attempt 이름에 tag 가 없음",
     'attempt = f"{a.tag}-{time.strftime(\'%Y%m%d-%H%M%S\')}-{os.getpid()}"', 'attempt = f"{time.strftime(\'%Y%m%d-%H%M%S\')}-{os.getpid()}"',
     ["RT1"]),
    ("run", "MR10 CUDA_VISIBLE_DEVICES 를 --gpu 로 안 정함",
     'CUDA_VISIBLE_DEVICES=str(a.gpu), ', 'CUDA_VISIBLE_DEVICES="0", ', ["RT1"]),
    ("run", "MR11 v2 에도 isaac_slot 을 씀 (USD 폴더 0 개로 95)",
     '    if a.which == "cts":\n        dump = [PY_CTS,', '    if True:\n        dump = [PY_CTS,', ["RT2", "RT8"]),
    ("val", "MV-R1 run.json attempt 대조 없음", 'add("R1", run is not None and run.get("attempt") == a.attempt and', 'add("R1", run is not None and', ["VT-cts-R1"]),
    ("val", "MV-R2 바꿔치기 허용", 'add("R2", run is not None and (not run.get("overrides") or a.allow_overrides)', 'add("R2", True', ["VT-cts-R2"]),
    ("val", "MV-S1 slot attempt 안 봄", 'add("S1", s.get("attempt") == a.attempt,', 'add("S1", True,', ["VT-cts-S1"]),
    ("val", "MV-S2 slot_rc 안 봄", 'add("S2", s.get("slot_rc") == 0,', 'add("S2", True,', ["VT-cts-S2"]),
    ("val", "MV-S3 child_rc 안 봄", 'add("S3", s.get("child_rc") == 0,', 'add("S3", True,', ["VT-cts-S3"]),
    ("val", "MV-S4 해제 상태 안 봄", 'add("S4", s.get("state_at_release") == "scene_built",', 'add("S4", True,', ["VT-cts-S4"]),
    ("val", "MV-S5 USD 폴더 수를 1 개 이상으로", 'len(s["usd_final"]) == 1,', 'len(s["usd_final"]) >= 1,', ["VT-cts-S5"]),
    ("val", "MV-S6 루트 밖 USD 안 봄", 'add("S6", "usd_outside_root" in s and not s["usd_outside_root"],', 'add("S6", True,', ["VT-cts-S6"]),
    ("val", "MV-S7 충돌 안 봄", 'add("S7", "conflicts" in s and not s["conflicts"],', 'add("S7", True,', ["VT-cts-S7"]),
    ("val", "MV-S8 명령에서 usd_isolate_run 안 봄",
     '    if not any(x.endswith("/usd_isolate_run.py") or x == "usd_isolate_run.py" for x in c):\n        return "usd_isolate_run.py 없음"\n',
     '', ["VT-cts-S8", "VT-v2-V5"]),
    ("val", "MV-G1 guard 정지 안 봄", 'add("G1", g.get("exit_code") == 0 and g.get("stopped_by_guard") is False,', 'add("G1", True,', ["VT-cts-G1"]),
    ("val", "MV-L1 Traceback 안 봄", 'add("L1", log is not None and TRACE not in log,', 'add("L1", log is not None,', ["VT-cts-L1"]),
    ("val", "MV-L2 done 줄을 tag 접두어로만 봄", 'f"[CE12-DUMP] done {tag} N " in log', 'f"[CE12-DUMP] done {tag}" in log', ["VT-cts-L2"]),
    ("val", "MV-N1 유한값 안 봄", '        if not np.isfinite(v).all():\n', '        if False:\n', ["VT-cts-N1"]),
    ("val", "MV-N1b 모양 안 봄", '        if tuple(d[k].shape) != s:\n', '        if False:\n', ["VT-v2-N1"]),
    ("val", "MV-M1 체크포인트 sha256 안 봄", '        and meta.get("checkpoint_sha256") == sha(a.checkpoint)\n', '        and True\n', ["VT-cts-M1"]),
    ("val", "MV-M2 예전 결과를 받음 (시각 안 봄)", 'and t0 is not None and ts is not None and ts >= t0 - 1', 'and True', ["VT-cts-M2"]),
    ("val", "MV-V1 v2 실행 종료 코드 안 봄", 'add("V1", run is not None and run.get("rc") == 0 and run.get("child_rc") == 0,', 'add("V1", True,', ["VT-v2-V1"]),
    ("val", "MV-V2 격리 상태 안 봄", 'add("V2", st is not None and bool(st.get("patched_by")),', 'add("V2", True,', ["VT-v2-V2"]),
    ("val", "MV-V3 assigned.jsonl 안 봄", 'add("V3", n_asg == 0,', 'add("V3", True,', ["VT-v2-V3"]),
    ("val", "MV-V4 로그의 변환 폴더 안 봄", 'add("V4", log is not None and not found,', 'add("V4", True,', ["VT-v2-V4"]),
    ("val", "MV-ST stamp 를 실패에도 씀", '    if bad:\n        print(f"INVALID', '    if bad and False:\n        print(f"INVALID', ["VT-stamp"]),
]


def main():
    res = []
    for k, (target, name, a, b, want) in enumerate(M):
        src = SRC[target]
        assert src.count(a) == 1, f"{name}: 바꿀 문자열이 {src.count(a)} 번 나온다"
        p = os.path.join(HERE, f"_mut_{target}_{k:02d}.py")
        with open(p, "w", encoding="utf-8") as f:
            f.write(src.replace(a, b))
        try:
            env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1")
            env["CE12_RUN_DUMP" if target == "run" else "CE12_VALIDATE"] = p
            group = "RT" if target == "run" else "VT"
            r = subprocess.run([sys.executable, "-B", os.path.join(HERE, "test_run_dump.py"), group], capture_output=True, text=True,
                               env=env, encoding="utf-8", errors="replace", timeout=1200)
        finally:
            os.remove(p)
        failed = [ln.split()[1].rstrip(":") for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
        crashed = "Traceback (most recent call last)" in r.stderr
        caught = r.returncode == 1 and all(w in failed for w in want) and not crashed
        res.append(f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}"
                   f"{' · CRASH ' + r.stderr[-300:] if crashed else ''}")
        print(res[-1], flush=True)
    n_ok = sum(x.startswith("CAUGHT") for x in res)
    print(f"{n_ok}/{len(res)} CAUGHT")
    print("ALL CAUGHT" if n_ok == len(res) else "SOME MISSED")
    return 0 if n_ok == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
