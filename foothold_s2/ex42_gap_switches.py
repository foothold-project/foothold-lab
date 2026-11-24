"""EX-42 틈 · 평균대 열 처방 후보 셋의 스위치 (전부 환경 변수 · 기본 꺼짐 · 꺼져 있으면 영수증도 옛 것과 같다). Isaac 없이 읽힌다.

  EX42_EDGE_EXTRA_KINDS      발 가장자리 항 (foot_edge) 의 마스크를 더 넓은 열까지 (예: B/gap,B/beam,C/gap). 마스크는 메시 윗면에서 시작할 때 만든다
                             (메시 파일 · 메시 sha · 계획 sha 는 안 바뀐다). 가중치는 계획 행의 foot_edge_weight 그대로 (0 이면 오류).
  EX42_TRACK_LIN_MIN_KINDS   그 열 env 의 선속도 추종만 START 원문 식 exp(-|min(v, cmd) - cmd|^2 / std^2) (과속 무벌점). 나머지 열은 지금 식 (정확 추종).
  EX42_FALL_PLANE_KINDS      그 열 env 의 발 빠짐 종료를 출발 발판 평면 기준으로 (발 z < 타일 원점 z - 0.25). 나머지 열은 지금 식 (가장 가까운 스캔 점 기준).
  EX42_TRACK_LIN_STD_KINDS   family/kind=std 목록에 있는 열만 선속도 추종 std 를 고정한다. 그 밖의 열은 실시간 term std 를 따른다.

값은 family/kind 목록 (A/gaps,B/gap,C/gap 처럼). 열 표에 없는 이름 · 중복 · 모양이 틀린 값은 오류 (조용히 꺼지지 않게).
"""
from __future__ import annotations

import os
import re
import math
from typing import Any

ENV_EDGE = "EX42_EDGE_EXTRA_KINDS"
ENV_MIN = "EX42_TRACK_LIN_MIN_KINDS"
ENV_PLANE = "EX42_FALL_PLANE_KINDS"
ENV_STD = "EX42_TRACK_LIN_STD_KINDS"
PLANE_MARGIN_M = 0.25                       # go2_params.TERMINATION["foot_below_ground_m"] 와 같은 값 (START 원문 221 행의 여유)
_NAME = re.compile(r"[A-F]/[a-z_0-9]+")


def parse_kinds(name: str, table: list[dict[str, Any]], environ=None) -> tuple[str, ...]:
    """환경 변수 `name` 의 family/kind 목록. 안 정했으면 빈 튜플. 열 표 (family, kind 행) 에 없는 이름 · 중복 · 모양 오류는 ValueError."""
    raw = (environ if environ is not None else os.environ).get(name, "")
    kinds = tuple(k.strip() for k in raw.split(",") if k.strip())
    if not kinds:
        return ()
    bad = [k for k in kinds if _NAME.fullmatch(k) is None]
    if bad or len(set(kinds)) != len(kinds):
        raise ValueError("%s invalid (comma list of family/kind such as A/gaps,B/gap,C/gap, no duplicates): %r" % (name, raw))
    have = {"%s/%s" % (r["family"], r["kind"]) for r in table}
    if set(kinds) - have:
        raise ValueError("%s names kinds not in the column table: %s" % (name, sorted(set(kinds) - have)))
    return kinds


def columns_of(kinds: tuple[str, ...], table: list[dict[str, Any]]) -> tuple[int, ...]:
    """열 표에서 `kinds` 에 해당하는 열 번호 (오름차순)."""
    want = set(kinds)
    return tuple(c for c, r in enumerate(table) if "%s/%s" % (r["family"], r["kind"]) in want)


def read_std_kinds(table: list[dict[str, Any]], environ=None) -> dict[str, float]:
    """Optional family/kind=std overrides. An explicitly empty or invalid value is an error."""
    env = environ if environ is not None else os.environ
    if ENV_STD not in env:
        return {}
    raw = env[ENV_STD]
    parts = [part.strip() for part in raw.split(",")]
    have = {"%s/%s" % (r["family"], r["kind"]) for r in table}
    values: dict[str, float] = {}
    for part in parts:
        name, sep, text = part.partition("=")
        if sep != "=" or _NAME.fullmatch(name) is None or name not in have or name in values:
            raise ValueError(f"{ENV_STD} invalid or unknown kind: {part!r}")
        try:
            value = float(text)
        except ValueError as exc:
            raise ValueError(f"{ENV_STD} invalid std: {part!r}") from exc
        if not math.isfinite(value) or not 0 < value <= 1:
            raise ValueError(f"{ENV_STD} std must be in (0, 1]: {part!r}")
        values[name] = value
    return values


def std_columns_of(values: dict[str, float], table: list[dict[str, Any]]) -> dict[int, float]:
    return {col: values[name] for col, row in enumerate(table)
            if (name := "%s/%s" % (row["family"], row["kind"])) in values}


def apply_std_cfg(env_cfg, columns: dict[int, float], track_func, *, min_columns: tuple[int, ...] = ()) -> None:
    if not columns:
        return
    term = env_cfg.rewards.track_lin_vel
    term.func = track_func
    term.params = {**term.params, "std_columns": list(columns), "std_values": [columns[c] for c in columns],
                   **({"min_columns": list(min_columns)} if min_columns else {})}


def read_switches(table: list[dict[str, Any]], environ=None) -> dict[str, Any]:
    """{edge_kinds, min_kinds, plane_kinds (각 family/kind 튜플), edge_columns, min_columns, plane_columns}. 셋 다 꺼져 있으면 모두 빈 값."""
    edge, mn, plane = (parse_kinds(n, table, environ) for n in (ENV_EDGE, ENV_MIN, ENV_PLANE))
    return {"edge_kinds": edge, "min_kinds": mn, "plane_kinds": plane,
            "edge_columns": columns_of(edge, table), "min_columns": columns_of(mn, table), "plane_columns": columns_of(plane, table)}


def any_on(sw: dict[str, Any]) -> bool:
    return bool(sw["edge_kinds"] or sw["min_kinds"] or sw["plane_kinds"])


def receipt(sw: dict[str, Any]) -> dict[str, Any]:
    """env 영수증에 붙이는 칸 (켠 것만). 셋 다 꺼져 있으면 빈 dict (옛 영수증과 같다)."""
    out: dict[str, Any] = {}
    if sw["edge_kinds"]:
        out["edge_extra_kinds"] = list(sw["edge_kinds"])
    if sw["min_kinds"]:
        out["track_lin_min_kinds"] = list(sw["min_kinds"])
    if sw["plane_kinds"]:
        out["fall_plane_kinds"] = list(sw["plane_kinds"])
    return {"gap_switches": out} if out else {}


def apply_cfg(env_cfg, sw: dict[str, Any], track_func=None) -> None:
    """env cfg (gym.make 전) 에 켠 처방을 건다: 선속도 추종 항의 함수 · 열 번호, 발 빠짐 종료의 열 번호. 가장자리 마스크는 시작 뒤 attach_edge_tables 가 붙인다."""
    if sw["min_kinds"]:
        if track_func is None:
            raise ValueError("track_func is required when %s is set" % ENV_MIN)
        env_cfg.rewards.track_lin_vel.func = track_func
        env_cfg.rewards.track_lin_vel.params["min_columns"] = list(sw["min_columns"])
    if sw["plane_kinds"]:
        env_cfg.terminations.foot_below_ground.params["plane_columns"] = list(sw["plane_columns"])


# ---- 순수 torch 식 (Isaac 없이 시험) ------------------------------------------------------------------------------------------------------

def track_lin_mixed(vel_xy, cmd_xy, std: float, min_env):
    """(N,) 선속도 추종. min_env (N,) bool 인 env 는 원문 식 exp(-|min(v, cmd) - cmd|^2 / std^2), 나머지는 정확 추종 exp(-|cmd - v|^2 / std^2)."""
    import torch
    exact = torch.exp(-torch.sum((cmd_xy - vel_xy) ** 2, dim=-1) / std ** 2)
    low = torch.exp(-torch.sum((torch.minimum(vel_xy, cmd_xy) - cmd_xy) ** 2, dim=-1) / std ** 2)
    return torch.where(min_env, low, exact)


def track_lin_std_mixed(vel_xy, cmd_xy, std: float, types, n_columns: int,
                        std_columns: tuple[int, ...], std_values: tuple[float, ...], min_columns: tuple[int, ...] = ()):
    """The same tracking expression with a fixed std on named columns and the live term std elsewhere."""
    import torch
    if len(std_columns) != len(std_values):
        raise ValueError("std columns and values differ in length")
    per_column = torch.full((n_columns,), float(std), dtype=vel_xy.dtype, device=vel_xy.device)
    if std_columns:
        per_column[list(std_columns)] = torch.as_tensor(std_values, dtype=vel_xy.dtype, device=vel_xy.device)
    env_std = per_column[types.long()]
    error = cmd_xy - vel_xy
    if min_columns:
        on = column_env_mask(types, min_columns, n_columns)
        error = torch.where(on[:, None], cmd_xy - torch.minimum(vel_xy, cmd_xy), error)
    return torch.exp(-torch.sum(error ** 2, dim=-1) / env_std ** 2)


def column_env_mask(types, columns: tuple[int, ...], n_columns: int):
    """(N,) bool: env 의 지형 열이 `columns` 안에 있다."""
    import torch
    lut = torch.zeros(n_columns, dtype=torch.bool, device=types.device)
    if columns:
        lut[list(columns)] = True
    return lut[types.long()]


def feet_below_plane(feet_z, plane_z, margin: float = PLANE_MARGIN_M):
    """(N,) bool: 어느 발이든 출발 발판 평면 (타일 원점 z) 보다 margin 아래 (START 원문 식)."""
    return (feet_z < plane_z[:, None] - margin).any(dim=1)
