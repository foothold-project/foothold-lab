# -*- coding: utf-8 -*-
"""break-the-guard: run_dump.py · validate_dump.py 의 일부러 틀린 사본마다 test_run_dump.py 의 지정 시험이 FAIL 해야 한다 (v2).

분류: A/평가 · CE12-v1 이식 진단 1 · 실행기 · 검증기 시험의 시험
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 19:03 · v2 23:40 (ASTRA 17d §2.5 · §2.6 · §2.7 · §4 반례)
근거: lead 지시 20:06 · 23:30 · _eval/mutate_isaac_slot.py 와 같은 방식 (읽기만)
요지: 사본은 ce12 안 _mut_*.py 로 만들고 (실행기가 자기 위치로 _eval 을 찾는다) 끝나면 지운다. 원본은 건드리지 않는다.
      변이마다 지정 시험만 돌린다 (그 시험들이 FAIL 해야 CAUGHT). 바꿀 문자열은 원본에 정확히 한 번 나와야 한다.
      한 변이가 여러 곳을 바꿀 때는 (찾을 것, 바꿀 것) 짝의 목록을 쓴다.
상태: 시험 파일
판정: 종료 코드 1 · 지정 시험 모두 FAIL · 시험 실행기의 Traceback 없음 이면 CAUGHT. 모두 CAUGHT 면 「ALL CAUGHT」.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = {"run": open(os.path.join(HERE, "run_dump.py"), encoding="utf-8").read(),
       "val": open(os.path.join(HERE, "validate_dump.py"), encoding="utf-8").read()}

ALLOW_LIST = ('        if name not in allowed:\n'
              '            return None, f"허용 목록에 없는 옵션 {name!r} (축약 · 다른 이름 거절 · 허용: {sorted(allowed)})"\n')
M = [
    # ---------------------------------------------------------------- 실행기 (ASTRA 17d §2.5 · §2.6)
    ("run", "MR01 slot 에 --usd_root · --attempt 를 안 줌", '"--usd_root", P["usd"], "--attempt", attempt,\n', '\n', ["RT1", "RT7"]),
    ("run", "MR02 이미 있는 출력을 거절하지 않음",
     'taken = [P[k] for k in ("out", "log", "slot", "guard") if os.path.exists(P[k])]', 'taken = []', ["RT4"]),
    ("run", "MR03 허용 목록을 끔 (축약 · 장치 옵션이 기록기로 넘어감 · v1 의 등호형 탈출과 같은 종류)",
     [(ALLOW_LIST, ""), ('        kind = allowed[name]\n', '        kind = allowed.get(name, "free")\n'),
      ('    if kind.startswith("choice:"):', '    if kind == "free":\n        return True\n    if kind.startswith("choice:"):')], None, ["RT6"]),
    ("run", "MR04 같은 옵션 두 번을 허용 (뒤의 값이 이김)", '        if name in out:\n            return None, f"{name} 가 두 번 나온다"\n', '', ["RT6"]),
    ("run", "MR05 --allow_cfg_diff 를 정식 자료에 허용",
     [('FORBIDDEN_WHY = {"--allow_cfg_diff": "정식 자료에서 금지 (설정 차이 관문을 끈다)", ', 'FORBIDDEN_WHY = {'),
      ('COMMON = {"--cells": "cells",', 'COMMON = {"--allow_cfg_diff": "flag", "--cells": "cells",')], None, ["RT6"]),
    ("run", "MR06 등호형 이름을 그대로 이름으로 봄 (값 형식 검사 우회)",
     [('        name, eq, val = t.partition("=")\n', '        name, eq, val = t.partition("=")\n        if eq:\n            out[name] = val\n            i += 1\n            continue\n')],
     None, ["RT6"]),
    ("run", "MR07 자식이 끝난 뒤 출력 위치를 안 봄 (validate 에만 맡김)", '    prob = output_problem(a)\n', '    prob = ""\n', ["RT10"]),
    ("run", "MR08 v2 의 변환 예상을 1 로", 'EXPECT = {"cts": 1, "v2": 0}', 'EXPECT = {"cts": 1, "v2": 1}', ["RT2", "RT8", "RT9"]),
    ("run", "MR09 관문 v3 에 예상 0 기능이 없어도 v2 를 띄움", '    if EXPECT[a.which] == 0 and not ((cap', '    if False and not ((cap', ["RT3"]),
    ("run", "MR10 slot 에 --expect_conversions 를 안 넘김 (기본 1 로 돈다)", '    if cap["slot_expect_flag"]:\n', '    if False:\n', ["RT2", "RT8"]),
    ("run", "MR11 scan_dirs 에서 out_ce12/native 를 뺌",
     'for d in ("out_ce12/native", "out_branch", "out_uncr", "out_rand"))', 'for d in ("out_branch", "out_uncr", "out_rand"))', ["RT1"]),
    ("run", "MR12 tag 검사 없음 (경로가 들어감)", 'if not TAG_RE.match(a.tag):', 'if False:', ["RT6"]),
    ("run", "MR13 attempt 이름에 tag 가 없음",
     'attempt = f"{a.tag}-{time.strftime(\'%Y%m%d-%H%M%S\')}-{os.getpid()}"', 'attempt = f"{time.strftime(\'%Y%m%d-%H%M%S\')}-{os.getpid()}"', ["RT1"]),
    ("run", "MR14 CUDA_VISIBLE_DEVICES 를 --gpu 로 안 정함", 'CUDA_VISIBLE_DEVICES=str(a.gpu), ', 'CUDA_VISIBLE_DEVICES="0", ', ["RT1"]),
    ("run", "MR15 cells · envs_per_cell · steps 를 명시하지 않음 (요청이 기록기 기본값에 숨음)",
     '    args = ["--cells", req["cells"], "--envs_per_cell", str(req["envs_per_cell"]), "--steps", str(req["steps"])]\n', '    args = []\n', ["RT1"]),
    ("run", "MR16 강제 reset · 명령 전환 범위 검사 없음",
     '    why = CL.fixture_problem(req["steps"]', '    why = "" and CL.fixture_problem(req["steps"]', ["RT6"]),
]
# ---------------------------------------------------------------- 검증기 수집 검사: 하나씩 늘 통과로
for cid in ("R1", "R2", "R3", "R4", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10", "S11", "G1", "L1", "L2", "N1", "N2", "M1", "M2"):
    M.append(("val", f"MV-{cid} 수집 검사 {cid} 를 끔", f'add("{cid}", ', f'add("{cid}", True or ', [f"VT-cts-{cid}", f"VT-v2-{cid}"]))
# ---------------------------------------------------------------- 검증기 승인 검사 (ASTRA 17d §2.7 · §4)
for cid, want in (("a1", ["VA-cts-A1", "VA-v2-A1b"]), ("a2", ["VA-cts-A2", "VA-v2-A2b", "VA-cts-A2c"]), ("a3", ["VA-cts-A3", "VA-v2-A3b"]),
                  ("a4", ["VA-cts-A4", "VA-cts-A4b", "VA-v2-A4b", "VA-cts-A4c"]), ("a5", ["VA-cts-A5", "VA-v2-A5"]), ("a6", ["VA0", "VA-cts-A6"]),
                  ("a7", ["VA-pending"]), ("a8", ["VA-pending"])):
    M.append(("val", f"MV-{cid.upper()} 승인 검사 {cid.upper()} 를 늘 통과로", f"    def {cid}():\n", f"    def {cid}():\n        return PASS, \"\"\n", want))
M += [
    ("val", "MV-A5b teacher 입력 변경 action 차 (기록기 자체 검사) 를 안 봄",
     '        if chk != 0.0:\n            return f"기록기 자체 검사', '        if False:\n            return f"기록기 자체 검사', ["VA-cts-A5", "VA-teacher"]),
    ("val", "MV-A6a 비교 뒤 npz 가 바뀐 것을 안 봄", 'or inp.get("npz_sha256") != sha(F["npz"]):', 'or False:', ["VA-cts-A6", "VA-v2-A6"]),
    ("val", "MV-A6b 재계산 없는 보고서를 받음", 'if rep.get("recompute_action") is not True or not all(', 'if False and not all(', ["VA-cts-A6c", "VA-v2-A6c"]),
    ("val", "MV-A6c 보고서의 체크포인트를 안 봄",
     'if not same_path(rep.get("checkpoint", ""), a.checkpoint) or rep.get("checkpoint_sha256") != sha(a.checkpoint):', 'if False:',
     ["VA-cts-A6d", "VA-v2-A6d"]),
    ("val", "MV-A6d 보고서를 만든 코드 해시를 안 봄", '        if code != now:\n', '        if False:\n', ["VA-cts-A6e", "VA-v2-A6e"]),
    ("val", "MV-A6e 비교 뒤 meta 가 바뀐 것을 안 봄", 'if inp.get("meta_sha256") != sha(F["meta"]) or ', 'if False and ', ["VA-cts-A6f", "VA-v2-A6f"]),
    ("val", "MV-A7b reset 경로 0 을 보류가 아니라 통과로",
     'return (PASS, "") if cov["reset_events"] > 0 else (PEND,', 'return (PASS, "") if True else (PEND,', ["VA-pending"]),
    ("val", "MV-P 보류인데 승인 stamp 을 씀", '    if any(x[1] == PEND for x in RA):\n', '    if False:\n', ["VA-pending"]),
    ("val", "MV-CK 승인 뒤 바뀐 파일을 안 봄",
     '        changed = [k for k, (p, h) in st["files"].items() if not os.path.isfile(p) or sha(p) != h]\n', '        changed = []\n', ["VA0"]),
]


def main():
    res = []
    only = set(sys.argv[1:])
    for k, (target, name, a, b, want) in enumerate(M):
        if only and name.split()[0] not in only:
            continue
        src = SRC[target]
        pairs = a if isinstance(a, list) else [(a, b)]
        for x, _y in pairs:
            assert src.count(x) == 1, f"{name}: 바꿀 문자열이 {src.count(x)} 번 나온다: {x[:60]!r}"
        for x, y in pairs:
            src = src.replace(x, y)
        p = os.path.join(HERE, f"_mut_{target}_{k:02d}.py")
        with open(p, "w", encoding="utf-8") as f:
            f.write(src)
        try:
            env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1")
            env["CE12_RUN_DUMP" if target == "run" else "CE12_VALIDATE"] = p
            r = subprocess.run([sys.executable, "-B", os.path.join(HERE, "test_run_dump.py")] + want, capture_output=True, text=True,
                               env=env, encoding="utf-8", errors="replace", timeout=1800)
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
