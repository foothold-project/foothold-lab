"""Read the two EX-35 reconstruction-error smoke receipts for the lab page."""

from __future__ import annotations

import html
import json
import math
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np


FIRST = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/map_err_x27m")
SECOND = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/map_err_x27m4")
MAIN = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/map_err_main_x27n")
VERIFIER = Path("C:/mai/wt/foothold-lab/verifier-27c-window/inbox/jay/20261027-experiments/VERIFY-verifier-496e0cfe-map-error.md")
RUNS = (("sparse50 L0", "smoke64_sparse50_pred"), ("default", "smoke64_default_pred"))


def _receipt(directory: Path, envs: int, code_prefix: str) -> dict:
    data = json.loads((directory / "map_modes.json").read_text(encoding="utf-8"))
    if data["envs"] != envs or data["checkpoint_iter"] != 2000:
        raise ValueError(f"map error smoke contract changed: {directory}")
    if not data["run_identity"]["code_head"].startswith(code_prefix):
        raise ValueError(f"map error code head changed: {directory}")
    if "fwd1.0" not in data["modes"]["eval_pred"]:
        raise ValueError(f"eval_pred/fwd1.0 missing: {directory}")
    return data


def group_inrange(data: dict, arrays: dict, *, require_tiles: bool) -> list[tuple[str, int, float]]:
    env = np.asarray(arrays["env"])
    value = np.asarray(arrays["map_err_inrange_mean_cm"], dtype=np.float64)
    steps = np.asarray(arrays["map_err_inrange_steps"])
    actual_kind = [str(kind) for kind in arrays["kind"]]
    count = int(data["envs"])
    if env.tolist() != list(range(count)) or any(len(v) != count for v in (value, steps, actual_kind)):
        raise ValueError("map error env alignment changed")
    if not np.isfinite(value).all() or not (steps > 0).all():
        raise ValueError("map error inrange value missing or nonfinite")
    tiles = data["fixed_terrain"].get("tiles")
    if require_tiles and (not isinstance(tiles, list) or len(tiles) != count):
        raise ValueError("sparse50 kind/env tile assignment missing")
    if tiles:
        tile_kind = {int(tile["env"]): str(tile["kind"]) for tile in tiles}
        if sorted(tile_kind) != list(range(count)) or any(tile_kind[i] != actual_kind[i] for i in range(count)):
            raise ValueError("map_modes tiles and NPZ kinds disagree")
        kinds = [tile_kind[i] for i in range(count)]
    else:
        # The default receipt has no JSON tiles; its NPZ carries kind and env.
        kinds = actual_kind
    groups: dict[str, list[float]] = defaultdict(list)
    for kind, number in zip(kinds, value, strict=True):
        groups[kind].append(float(number))
    summary = [(kind, len(numbers), sum(numbers) / len(numbers)) for kind, numbers in sorted(groups.items())]
    if sum(n for _, n, _ in summary) != count or any(not math.isfinite(mean) for _, _, mean in summary):
        raise ValueError("map error kind summary incomplete")
    return summary


def main_launch_evidence() -> tuple[str, str]:
    first_line = (MAIN / "main.log").read_text(encoding="utf-8").splitlines()[0]
    match = re.fullmatch(r"(2026-10-27 \d{2}:\d{2}:\d{2}) MAIN start head=(496e0cfe[0-9a-f]+)", first_line)
    if match is None:
        raise ValueError("X27n main launch record changed")
    files = list(MAIN.rglob("*.npz"))
    if not files:
        raise ValueError("X27n first NPZ not yet available")
    first = min(files, key=lambda path: path.stat().st_ctime)
    created = datetime.fromtimestamp(first.stat().st_ctime, ZoneInfo("Asia/Seoul"))
    launched = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Asia/Seoul"))
    if created < launched:
        raise ValueError("X27n first NPZ predates launch")
    if "막음 0" not in VERIFIER.read_text(encoding="utf-8"):
        raise ValueError("X27m4 verifier result changed")
    return launched.strftime("%H:%M:%S"), created.strftime("%H:%M:%S")


def render() -> str:
    for terrain in ("smoke8_sparse50", "smoke8_default"):
        directory = FIRST / terrain
        _receipt(directory, 8, "16112810")
        with np.load(directory / "env_arrays_eval_pred_fwd1.0.npz", allow_pickle=False) as arrays:
            if "map_err_inrange_mean_cm" in arrays or "map_err_valid_mean_cm" not in arrays:
                raise ValueError("first smoke metric identity changed")
    rows = []
    sources = []
    for label, name in RUNS:
        directory = SECOND / name
        data = _receipt(directory, 64, "496e0cfe")
        if data["terrain_set"] != name.split("_")[1]:
            raise ValueError("map error terrain set changed")
        with np.load(directory / "env_arrays_eval_pred_fwd1.0.npz", allow_pickle=False) as arrays:
            groups = group_inrange(data, arrays, require_tiles=label.startswith("sparse50"))
        for kind, count, mean in groups:
            rows.append(
                f"<tr><td>{html.escape(label)}</td><td>{html.escape(kind)}</td>"
                f"<td>{count}</td><td>{mean:.2f} cm</td></tr>"
            )
        sources.append(str(directory).replace("/", "\\"))
    source_text = " · ".join(html.escape(source) for source in sources)
    first_path = html.escape(str(FIRST).replace("/", "\\"))
    main_path = html.escape(str(MAIN).replace("/", "\\"))
    launched, first_npz = main_launch_evidence()
    return (
        "<p>복원 오차 축 1차 예행 16112810, 8 env 원자료는 옛 valid 지표만 있어 "
        "아래 inrange 수치와 합치지 않음. 2차 예행 496e0cfe, 64 env, "
        "sparse50 L0 · default, eval_pred · fwd1.0 · m2000. "
        "예행 · 판정 아님 · 해석 미완. "
        "reviewer 막음 0(REVIEW-496e0cfe.md) · verifier 막음 0(VERIFY-verifier-496e0cfe-map-error.md). "
        f"본 측정 X27n GPU0 {launched} 기동, 진행 중(첫 NPZ {first_npz} 생성). "
        f"결과 폴더 {main_path}. 본 측정 결과 수치는 진행 중이라 미기입. "
        "inrange는 정답 지도 -1.0 포화칸을 뺀 값이며 표는 env별 평균의 단순평균(유효 step 가중 아님).</p>"
        '<table><thead><tr><th>지형</th><th>종류</th><th>env</th><th>inrange 평균</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
        + f'<p class="t">근거 1차 {first_path} · 2차 {source_text}; '
        "2차 sparse50 종류는 map_modes.json tiles(kind·env), default 종류는 NPZ kind·env. "
        "각 폴더의 map_modes.json 및 env_arrays_eval_pred_fwd1.0.npz.</p>"
    )
