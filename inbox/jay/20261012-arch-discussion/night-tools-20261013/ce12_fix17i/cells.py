# -*- coding: utf-8 -*-
"""CE12 기록 칸 표 · 기록 중 reset · 명령 전환 구간 규칙 (순수 Python · torch 없음 · Kit 전에 import 해도 된다).

분류: A/평가 · CE12-v1 이식 진단 1 · 공용 표
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 20:10
근거: ASTRA 17d §2.7 (요청한 cell · T · N · 명령 시간열을 승인에 연결) · §4 (일부 환경 reset · 명령 전환 구간) · q_eval_cmdr.py ALL_CELLS
요지: dump_native_cts.py · dump_native_v2.py · run_dump.py · validate_dump.py 가 같은 표와 같은 규칙을 쓴다 (한 곳에만 적는다).
상태: 시험은 test_run_dump.py

시각 약속 (기록기와 같다): 지표 k 의 관측은 action[k] 직전. step k 안에서 일어난 reset 은 reset_after_step[k] 에 남고 관측 k+1 이 reset 뒤 첫 관측.
  강제 reset (--reset_envs i,j --reset_step K): 그 env 들이 env.step(K-1) 안에서 time-out 으로 reset 된다. 관측 K 가 reset 뒤 첫 관측.
  명령 전환 (--switch_env E --switch_step K --switch_cell C): env E 의 관측 K 부터 끝까지 명령이 C 의 명령이다 (그 전은 자기 칸 명령).
  K 는 1..T-1 (17f 4.4 · K=T 면 바뀐 명령으로 계산한 action 이 없다).
"""
CE12_CELLS = {
    "stand": ("stand", (0.0, 0.0, 0.0)), "fwd01": ("lin", (0.1, 0.0, 0.0)), "fwd03": ("lin", (0.3, 0.0, 0.0)),
    "fwd05": ("lin", (0.5, 0.0, 0.0)), "back03": ("lin", (-0.3, 0.0, 0.0)), "left03": ("lin", (0.0, 0.3, 0.0)),
    "right03": ("lin", (0.0, -0.3, 0.0)), "yawL05": ("yaw", (0.0, 0.0, 0.5)), "yawR05": ("yaw", (0.0, 0.0, -0.5)),
}
DEFAULT_CELLS = "stand,fwd03,yawL05"
DEFAULT_ENVS_PER_CELL = 4
DEFAULT_STEPS = 60
MAX_STEPS = 1450  # 29 s · CTS 기록기의 episode 30 s 안


def parse_cells(s):
    names = [x for x in str(s).split(",")]
    if not names or any(n not in CE12_CELLS for n in names) or len(set(names)) != len(names):
        raise ValueError(f"칸 목록 {s!r} (있는 칸 {list(CE12_CELLS)} · 겹침 없이)")
    return names


def parse_env_list(s):
    if s in ("", None):
        return []
    out = [int(x) for x in str(s).split(",")]
    if len(set(out)) != len(out):
        raise ValueError(f"env 목록이 겹친다 {s!r}")
    return out


def fixture_problem(T, N, reset_envs, reset_step, switch_env, switch_step, switch_cell):
    """강제 reset · 명령 전환 인자가 기록 범위 안인지. 문제 없으면 ''."""
    if reset_envs or reset_step:
        if not reset_envs or not reset_step:
            return "--reset_envs 와 --reset_step 은 같이 준다"
        if not 1 <= reset_step <= T - 1:
            return f"--reset_step {reset_step} 는 1..{T - 1}"
        if any(not 0 <= e < N for e in reset_envs):
            return f"--reset_envs {reset_envs} 는 0..{N - 1}"
        if len(reset_envs) >= N:
            return "--reset_envs 는 일부 env 만 (전부 reset 하면 「일부만」 경로를 못 본다)"
    if switch_env >= 0 or switch_step or switch_cell:
        if switch_env < 0 or not switch_step or not switch_cell:
            return "--switch_env · --switch_step · --switch_cell 은 같이 준다"
        if not 0 <= switch_env < N:
            return f"--switch_env {switch_env} 는 0..{N - 1}"
        if not 1 <= switch_step <= T - 1:  # ASTRA 17f 4.4: 마지막 관측 T 의 전환은 그 명령으로 계산한 action 이 0 개
            return f"--switch_step {switch_step} 는 1..{T - 1} (전환 뒤 action 이 하나 이상 있어야 한다)"
        if switch_cell not in CE12_CELLS:
            return f"--switch_cell {switch_cell!r} 모름"
    return ""


def expected_commands(cell_names, envs_per_cell, T, switch=None):
    """(T+1) x N x 3 의 기대 명령 (list). switch = (env, step, cell) 또는 None."""
    N = len(cell_names) * envs_per_cell
    base = [CE12_CELLS[cell_names[e // envs_per_cell]][1] for e in range(N)]
    out = []
    for k in range(T + 1):
        row = [list(base[e]) for e in range(N)]
        if switch is not None and k >= switch[1]:
            row[switch[0]] = list(CE12_CELLS[switch[2]][1])
        out.append(row)
    return out
