"""D94 · D125: W15 지도 모드 평가를 DR 켠 채 한 번 더 돌리는 모드 (planner 11/02 · lead 14:5x 의뢰 · lead 16:0x 검토 반영).

기본(``--dr-mode off``) 은 현행 그대로다. eval_map_modes 가 B env 의 시동 DR 이벤트 둘(physics_material · add_base_mass)
을 지우고 행동 지연을 0 으로 두며, 출력 map_modes.json 에 아무 키도 더하지 않는다(이 모듈은 아무것도 하지 않는다).
끔 출력은 ``source_sha256`` 키(평가기 자신의 파일 해시가 들어간다) 를 뺀 나머지가 이 변경 전과 같다.

``--dr-mode on`` 은 학습 시작 경로(train_start → ex41_startup.prepare_ex41_env_cfg → ex40_dr_runtime.install_runtime_events)
와 같은 설치 함수로 EX-40 런타임 DR 다섯(무게중심 · 이득 · 모터 세기 · 행동 지연 · 밀기) 을 env_cfg 에 설치하고, 시동 DR 둘은
지우지 않고 그대로 둔 뒤, 배율(``--dr-scale``, D125 승인값 1.0) 을 첫 reset 전에 ``env._ex40_dr_scale`` 로 고정해 돌린다.
학습과 같은 소비자(reset 이벤트 · 지연 행동 · ``interval_push``) 가 그 배율을 읽는다.

밀기만 일정이 다르다(lead 16:0x B1). 학습의 밀기는 Isaac interval 이벤트(``push_interval_s`` 10~15 s) 인데, W15 명령 하나는
``--steps 300`` × step_dt 0.02 s = 6.0 s 라 최소 간격 10 s 에 못 미치고, Isaac 은 env 가 reset 될 때마다 interval 타이머를 새로
뽑는다(``isaaclab/managers/event_manager.py:140~148`` · step 안에서 죽은 env 의 reset 도 같다). 그래서 interval 밀기는 평가 명령
안에서 한 번도 나지 않는다. 켠 모드는 그 interval 항을 설치 뒤 떼고, 롤아웃(명령 하나 · 시퀀스 하나) 마다 **명령 시작 2.0 s 에
한 번** 학습과 같은 ``interval_push`` 를 평가기가 직접 불러 env 전부를 민다(방향 · 크기는 표의 ±1.0 m/s × 배율 안에서 균등 추출,
난수는 (eval_seed, 롤아웃 이름) 으로 고정한 별도 시드로 뽑고 전역 난수 상태는 건드리지 않는다). 2.0 s 는 설계 원문에 없는 값이다
(설계 §5 :246 「DR 전체 범위 켠 채 … 밀기, 같은 시드」 는 시각을 적지 않았다 · lead 11/02 16:0x 요지 「명령 시작 2.0 s 예시」 채택 ·
가정): 평가기의 측정 창이 2~4 s(``sl = slice(int(2.0 / dt), int(4.0 / dt))``) 라 창의 멈춤 · 정지 지표가 밀린 뒤 행동을 재고, 끝
생존(alive_envs_at_end) 은 4 s 뒤 회복을 잰다.

영상용 기록(G18, lead 16:0x 요지 「영상에서 어디로 · 얼마나 밀리는지」): 밀기 이벤트마다 step · 시각 · 시드 · env 마다 밀기 직전
월드 위치 xy · yaw · 월드 Δv(x,y,z) · 크기 · 방향을 ``dr.readback[<롤아웃>].push_events`` 에 적는다(scripter 가 읽어 화살표를 그린다).
회복 지표 셋(쓰러짐 · 경로 이탈 · 회복 시간) 은 ``recovery_metrics`` 가 그 롤아웃의 step 배열로 센다. 정의는 함수 docstring 과
출력의 ``definition`` 에 적힌 가정값이다(설계 원문에 정의 없음 · 1 차는 기록).

출력 map_modes.json 에 ``dr`` 블록(배율 · 범위표 경로와 SHA · 설치 영수증 · 밀기 일정 · 명령마다 실측 readback) 을 적고, 점수
행(res.modes[mode][cmd] · sequences, MAPMODE 줄에 그대로 찍히는 행) 에는 ``dr_scale`` · 이벤트별 발화 수 ``dr_fired`` · 밀기 요약
``dr_push`` · 회복 지표 ``dr_recovery`` 를 더한다(lead 16:0x B2 · G18). 명령마다 reset 표본이 env 전부에 닿았는지 · 밀기가 정확히
한 번 env 전부에 닿았는지 · 표본이 배율만큼의 범위 안인지 · 지연 상한이 배율과 맞는지 확인해 어긋나면 RuntimeError 로 멈춘다
(「켠 줄 알았는데 꺼진 채」 방지). 표본은 롤아웃마다 비운다(B3): ``begin`` 이 reset 전에 비우고 ``collect`` 가 그 롤아웃의 것만 읽는다.

소비자 계약(lead 17:5x B2): 유지 판정 소비자(ex41_startup.maintenance_counts_from_map_modes · ex40_score._map_rows) 는 dr 블록 ·
dr_off 를 보지 않으므로, DR 켠 map_modes.json 이 들어가면 그 생존 수가 39 칸 유지 판정이 된다. ``require_dr_off_document`` 가 json 을
읽은 직후 「dr 키 없음 · dr_off == EXPECTED_DR_OFF · 점수 행에 dr_* 키 없음」 을 확인하고 어긋나면 RuntimeError 를 낸다. 소비자 파일은
runner · analyst 소유라 연결은 lead 가 전달하고, 이 모듈은 helper 와 깨뜨리는 시험만 둔다.

같은 시드 · 다른 잡음 실현(B5): 켠 판은 끔 판과 같은 ``--eval-seed`` 로 돌지만 DR 이 난수를 더 소비하므로 reset 자세 · 명령
잡음의 실현은 끔 판과 다르다. 「같은 시드」 는 재현 조건이지 「같은 궤적에서 DR 만 더한 것」 이 아니다.

칸 정의의 근거: WORKLIST D94(11/01 「DR 켠 평가 칸 하나」) · D125(11/02 「배율 1.0」) · CURRICULUM-GATES(「확대 대상은 COM ·
Kp/Kd · 모터 세기 · 행동 지연 · 밀기 다섯. 시동 마찰 · 질량은 보존」) · DESIGN-EX41-STAGE2 §5(「W15 fwd1.0 · side± 를 DR 전체
범위 켠 채(… 밀기, 같은 시드) 한 번 더 · 1 차는 기록」). 어느 명령 · 지형 · 모드를 돌릴지는 기존 인자(--commands · --modes ·
--fixed-level) 로 고르고, 이 모듈은 「켠다 · 얼마나 켰는지 적는다 · 실제로 켜졌는지 확인한다」 만 맡는다.

Kit 밖에서도 import 된다. 설치 함수 · readback · 밀기는 켠 모드에서만 늦게 import 한다.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml

from foothold_s2.curriculum.ex40_dr import validate_full_ranges

DEFAULT_TABLE = Path(__file__).resolve().parents[1] / "curriculum" / "ex41-fixed5000.yaml"
STARTUP_EVENTS = ("physics_material", "add_base_mass")           # B env 에 실제 있는 시동 DR(eval 의 EXPECTED_DR_OFF 와 같은 둘)
EXPECTED_DR_OFF = list(STARTUP_EVENTS)                          # 끔 판 map_modes.json 의 dr_off 기대값. eval_map_modes 의 리터럴 EXPECTED_DR_OFF 와 같아야 한다(시험이 ast 로 대조)
DR_ROW_KEYS = ("dr_scale", "dr_fired", "dr_push", "dr_recovery")  # 켠 모드가 점수 행에 더하는 키. 끔 판 소비자는 이 키가 있으면 거절한다
RUNTIME_RESET_TERMS = ("ex40_base_com", "ex40_actuator_gains", "ex40_motor_strength")
RUNTIME_INTERVAL_TERM = "ex40_push"                               # 학습의 interval 밀기. 켠 모드는 설치 뒤 떼고 가운데 step 밀기로 바꾼다
RESET_SAMPLE_KEYS = ("base_com_offset_m", "actuator_gains", "motor_strength_multiplier")
PUSH_SAMPLE_KEY = "push_velocity_delta"
PUSH_RECORD_DIMS = 6                                              # interval_push 가 적는 root 속도 차 성분 수(x y z roll pitch yaw)
PUSH_AT_S = 2.0                                                   # 롤아웃(명령) 시작 몇 초에 한 번 미는가(가정 · lead 16:0x 예시값 · 측정 창 2~4 s 시작)
RECOVERY_BAND_MPS = 0.1                                           # 회복 판정: 몸 좌표 속도가 밀기 전 평균의 이 반지름 안(가정)
RECOVERY_HOLD_S = 0.2                                             # 회복 판정: 그 안에 연속으로 머무는 시간(가정)
RECOVERY_PRE_S = 1.0                                              # 밀기 전 기준 속도 · 기준 경로를 재는 길이(가정)
RECOVERY_BAND_RADPS = 0.2                                         # 회복 판정: 몸 yaw 속도가 명령 wz 의 이 반지름 안(가정)
NEUTRAL = {"base_com_offset_m": 0.0, "actuator_gains": 1.0, "motor_strength_multiplier": 1.0, PUSH_SAMPLE_KEY: 0.0}
CELL_DEFINITION = ("D94 DR 켠 평가 칸(11/01) · D125 배율 1.0(11/02): 시동 DR 둘 보존 + 런타임 DR 다섯"
                   "(base_com · actuator_gains · motor_strength · delay_s · push_velocity) 을 배율만큼 켠 W15 지도 모드 평가. "
                   "밀기는 롤아웃마다 명령 시작 %.1f s 에 한 번, env 전부(interval 10~15 s 는 6 s 명령 안에서 안 남 · G18 영상 기록). "
                   "같은 평가 시드 · 다른 잡음 실현(DR 이 난수를 더 소비)" % PUSH_AT_S)
PUSH_REASON = ("학습 interval 밀기 push_interval_s 최소 10 s > W15 명령 300 step × 0.02 s = 6 s 이고, Isaac event_manager 는 env reset "
               "마다 interval 타이머를 다시 뽑는다(event_manager.py:140~148) → 명령 안에서 interval 밀기 0 회. 그래서 interval 항을 "
               "떼고 롤아웃마다 명령 시작 %.1f s 에 한 번, 같은 interval_push 로 env 전부를 민다(세기 범위 표 그대로 × 배율 · 난수는 "
               "(eval_seed, 롤아웃 이름) 시드로 고정). 시각 2.0 s 는 설계 원문(DESIGN §5 :246) 에 없고 lead 11/02 16:0x 예시값(가정); "
               "평가기 측정 창 2~4 s 의 시작과 같다" % PUSH_AT_S)
SEED_NOTE = "같은 --eval-seed · 다른 잡음 실현: DR 이 난수를 더 소비하므로 끔 판과 reset 자세 · 명령 잡음의 실현이 다르다"


def add_arguments(parser) -> None:
    parser.add_argument("--dr-mode", choices=("off", "on"), default="off",
                        help="off = 현행(시동 DR 둘 끔 · 지연 0 · 출력 그대로). on = D94 DR 켠 칸: 시동 DR 보존 + 런타임 DR 설치, 배율 --dr-scale")
    parser.add_argument("--dr-scale", type=float, default=1.0,
                        help="--dr-mode on 의 배율 [0, 1]. D125 승인값 1.0. 0 은 설치는 하되 범위를 명목값으로 접는다(켜짐 · 꺼짐 끝점 시험용)")
    parser.add_argument("--dr-table", default=str(DEFAULT_TABLE),
                        help="domain_randomization.full_ranges · push_interval_s 를 읽을 커리큘럼 표(기본 ex41-fixed5000.yaml; ex40.yaml 과 같은 범위)")


def validate_args(args) -> str | None:
    """Kit 기동 전에 거절할 사유를 돌려준다(없으면 None). 호출자가 parser.error 로 올린다."""
    if args.dr_mode == "off":
        return None
    if getattr(args, "axis_v2", False):
        return "--dr-mode on 은 W57 --axis-v2 와 같이 쓰지 않는다(W57 관문 칸은 DR 끔)"
    scale = args.dr_scale
    if not isinstance(scale, (int, float)) or isinstance(scale, bool) or not math.isfinite(scale) or not 0.0 <= scale <= 1.0:
        return "--dr-scale 은 [0, 1] 의 유한한 수(D125 승인값 1.0)"
    if not Path(args.dr_table).is_file():
        return "--dr-table 파일이 없다: %s" % args.dr_table
    return None


def load_table(path: str | Path) -> dict[str, Any]:
    """커리큘럼 표의 domain_randomization 에서 범위 · 밀기 간격 · 지연 상한을 읽고 검증한다."""
    p = Path(path)
    raw = p.read_bytes()
    doc = yaml.safe_load(raw.decode("utf-8"))
    dr = (doc or {}).get("domain_randomization")
    if not isinstance(dr, dict):
        raise ValueError("DR 켠 평가: %s 에 domain_randomization 이 없다" % p)
    ranges = validate_full_ranges(dr.get("full_ranges"))
    interval = dr.get("push_interval_s")
    if (not isinstance(interval, (list, tuple)) or len(interval) != 2
            or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in interval)
            or interval[0] <= 0 or interval[1] < interval[0]):
        raise ValueError("DR 켠 평가: push_interval_s 가 비었거나 순서가 틀렸다")
    return {"path": str(p), "sha256": hashlib.sha256(raw).hexdigest(), "full_ranges": ranges,
            "push_interval_s": (float(interval[0]), float(interval[1])),
            "delay_max_s": float(ranges["delay_s"][1])}


def require_dr_off_document(doc: Any, *, where: str = "map_modes.json") -> dict[str, Any]:
    """끔 판 소비자 계약(lead 17:5x B2): map_modes.json 을 읽은 직후 부른다. DR 켠 판의 문서는 RuntimeError.

    유지 판정 소비자(ex41_startup.maintenance_counts_from_map_modes · ex40_score._map_rows) 가 읽는 생존 수는 끔 판의 것이어야 한다.
    거절: dict 가 아님 · ``dr`` 키 있음 · ``dr_off`` 가 EXPECTED_DR_OFF(순서 무관) 와 다름 · 점수 행(modes · sequences) 에 DR_ROW_KEYS 가 있음.
    통과하면 같은 doc 을 돌려준다(소비자가 ``data = require_dr_off_document(json.loads(...))`` 로 끼울 수 있게).
    """
    if not isinstance(doc, dict):
        raise RuntimeError("%s: 문서가 dict 가 아니다: %s" % (where, type(doc).__name__))
    if "dr" in doc:
        raise RuntimeError("%s: DR 켠 평가 출력(dr 블록 · 배율 %r) 은 유지 판정에 쓸 수 없다" % (where, (doc.get("dr") or {}).get("scale") if isinstance(doc.get("dr"), dict) else None))
    dr_off = doc.get("dr_off")
    if not isinstance(dr_off, list) or sorted(str(x) for x in dr_off) != sorted(EXPECTED_DR_OFF):
        raise RuntimeError("%s: 꺼진 DR 목록 %r 이 기대 %r 와 다르다(끔 판이 아니거나 DR 이름이 바뀌었다)" % (where, dr_off, EXPECTED_DR_OFF))
    modes = doc.get("modes")
    if not isinstance(modes, dict):
        raise RuntimeError("%s: modes 가 없다" % where)
    rows = [(("modes", mode, name), row) for mode, cells in modes.items() if isinstance(cells, dict) for name, row in cells.items()]
    seqs = doc.get("sequences")
    if isinstance(seqs, dict):
        rows += [(("sequences", mode, name), row) for mode, cells in seqs.items() if isinstance(cells, dict) for name, row in cells.items()]
    elif isinstance(seqs, list):
        rows += [(("sequences", i), row) for i, row in enumerate(seqs)]
    for path, row in rows:
        if isinstance(row, dict) and any(k in row for k in DR_ROW_KEYS):
            raise RuntimeError("%s: 점수 행 %r 에 DR 켠 키 %r 가 있다" % (where, path, [k for k in DR_ROW_KEYS if k in row]))
    return doc


def push_schedule(total_steps: int, dt: float) -> dict[str, Any]:
    """롤아웃 길이 · 정책 dt 로 밀기 step 을 정한다: 시작 PUSH_AT_S 초에 한 번. 롤아웃이 그보다 짧으면 0 번(기록만)."""
    total = int(total_steps)
    if not (isinstance(dt, (int, float)) and math.isfinite(dt) and dt > 0):
        raise RuntimeError("DR 켠 평가: 정책 dt 가 양수가 아니다: %r" % (dt,))
    step = int(round(PUSH_AT_S / float(dt)))
    if total <= 0 or step >= total:
        return {"total_steps": total, "dt": float(dt), "push_step": None, "push_t_s": None, "expected_pushes": 0}
    return {"total_steps": total, "dt": float(dt), "push_step": step, "push_t_s": step * float(dt), "expected_pushes": 1}


def push_seed(eval_seed: int, key: str) -> int:
    """밀기 난수 시드: (평가 시드, 롤아웃 이름) 에서 고정으로 만든다. 같은 입력이면 같은 Δv."""
    digest = hashlib.sha256(("%d|%s" % (int(eval_seed), key)).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _default_installer(env_cfg, ranges, push_interval_s, *, delay_max_s):
    from foothold_s2.curriculum.ex40_dr_runtime import install_runtime_events

    return install_runtime_events(env_cfg, ranges, push_interval_s, delay_max_s=delay_max_s)


def _default_pusher(raw, target_range, seed: int) -> dict[str, Any]:
    """학습과 같은 interval_push 를 env 전부(env_ids None) 에 한 번 부르고 env 마다 Δv 를 돌려준다(G18 영상용).

    배율은 env._ex40_dr_scale 에서 읽힌다. 난수는 fork_rng 안에서 seed 로 심어 뽑고 전역 상태는 되돌린다.
    """
    import torch
    from isaaclab.managers import SceneEntityCfg

    from foothold_s2.curriculum.ex40_dr_runtime import interval_push

    cfg = SceneEntityCfg("robot")
    cfg.resolve(raw.scene)
    asset = raw.scene["robot"]
    pos = asset.data.root_pos_w[:, :2].detach().clone()
    q = asset.data.root_quat_w.detach()
    yaw = torch.atan2(2.0 * (q[:, 0] * q[:, 3] + q[:, 1] * q[:, 2]), 1.0 - 2.0 * (q[:, 2] ** 2 + q[:, 3] ** 2))
    before = asset.root_physx_view.get_root_velocities().clone()
    device = torch.device(asset.device)
    with torch.random.fork_rng(devices=[device.index] if device.type == "cuda" else []):
        torch.manual_seed(int(seed))
        interval_push(raw, None, cfg, target_range)
    after = asset.root_physx_view.get_root_velocities().clone()
    return _push_event_record(pos.cpu(), yaw.cpu(), (after - before).cpu())


def _push_event_record(pos_xy, yaw, dv) -> dict[str, Any]:
    """env 마다 밀기 직전 월드 위치 · yaw · 월드 Δv 를 JSON 가능한 꼴로."""
    import torch

    dv = torch.as_tensor(dv, dtype=torch.float64)
    norm = torch.hypot(dv[:, 0], dv[:, 1])
    return {"env_ids": list(range(int(dv.shape[0]))), "frame": "world",
            "pos_xy_w_m": torch.as_tensor(pos_xy, dtype=torch.float64).tolist(),
            "yaw_w_rad": torch.as_tensor(yaw, dtype=torch.float64).tolist(),
            "dv_xyz_w_mps": dv[:, :3].tolist(), "dv_rpy_w_radps": dv[:, 3:6].tolist(),
            "dv_xy_norm_mps": norm.tolist(), "dv_xy_dir_w_rad": torch.atan2(dv[:, 1], dv[:, 0]).tolist(),
            "dv_xy_norm_mps_median": float(norm.median()), "dv_xy_norm_mps_max": float(norm.max())}


def _first_hold(inside, hold: int):
    """inside (T, N) bool 에서 env 마다 연속 hold step 동안 참이 되는 첫 시작 index(없으면 −1)."""
    import numpy as np

    found = np.full(inside.shape[1], -1)
    run = np.zeros(inside.shape[1], dtype=int)
    for i in range(inside.shape[0]):
        run = np.where(inside[i], run + 1, 0)
        hit = (run >= hold) & (found < 0)
        found[hit] = i - hold + 1
    return found


def recovery_metrics(alive, dones, vx, vy, xy, dt: float, push_step: int | None, *, wz=None, tilt=None, cmd=None,
                     band_mps: float = RECOVERY_BAND_MPS, band_radps: float = RECOVERY_BAND_RADPS,
                     hold_s: float = RECOVERY_HOLD_S, pre_s: float = RECOVERY_PRE_S) -> dict[str, Any]:
    """밀기 칸 지표 넷(G18 · lead 16:30 정본 목록: 쓰러짐 · 최대 몸 기울기 · 경로 이탈 · 명령 속도 회복 시간 · 가정 정의 · 기록 전용).

    배열은 평가 루프의 것 그대로: alive · dones (T, N) bool, vx · vy · wz (T, N) 몸 좌표 속도, tilt (T, N) 몸 기울기 rad,
    xy (T, N, 2) 월드 위치, cmd = (vx, vy, wz) 명령. step k 의 값은 k 번째 env.step 뒤 상태. wz · tilt · cmd 가 없으면 그 지표는 None.

    모집단: 밀기 step 전에 한 번도 끝나지(dones) 않은 env. 밀기 전 기준은 [push_step − pre_s, push_step) 의 평균.
    쓰러짐: 밀기 step 이후 롤아웃 끝까지 dones 가 한 번이라도 참(처음 쓰러진 시각의 중앙값은 밀기 뒤 경과 초).
    최대 몸 기울기: 밀기 뒤 살아 있는 step 의 tilt 최대(env 별) 의 중앙값 · 최대, 비교용으로 밀기 전 평균 tilt.
    경로 이탈: 밀기 직전 위치에서 기준 월드 속도로 직진했을 때의 예측 위치와 실제 위치의 거리(살아 있는 step 만) 의 env 별 최대, 그 중앙값 · 최대.
    명령 속도 회복 시간: 밀기 뒤 몸 속도(vx, vy) 가 **명령** 에서 band_mps 안, wz 가 명령 wz 에서 band_radps 안에 hold_s 동안 연속으로 머문 첫 시각
    (밀기 뒤 경과 초). 못 머물면 미회복. 대안(밀기 전 평균 속도 기준) 도 같이 적는다.
    """
    import numpy as np

    alive = np.asarray(alive, dtype=bool)
    dones = np.asarray(dones, dtype=bool)
    vx, vy, xy = np.asarray(vx, dtype=float), np.asarray(vy, dtype=float), np.asarray(xy, dtype=float)
    wz = None if wz is None else np.asarray(wz, dtype=float)
    tilt = None if tilt is None else np.asarray(tilt, dtype=float)
    T, N = alive.shape
    definition = {"band_mps": band_mps, "band_radps": band_radps, "hold_s": hold_s, "pre_s": pre_s, "decision_use": "record_only",
                  "population": "envs never done before the push step",
                  "fell": "any done at or after the push step",
                  "tilt_max": "per-env max body tilt (rad) over alive steps after the push; median and max over the population",
                  "path_deviation": "max distance from straight-line extrapolation of the pre-push mean world velocity (alive steps only)",
                  "recovery_cmd": "first time after the push when body (vx, vy) stays within band_mps of the command and wz within band_radps for hold_s",
                  "recovery_pre": "alternative: same test against the pre-push mean body velocity instead of the command",
                  "path_deviation_note": ("straight-line extrapolation only: under a turning command (wz != 0) the commanded arc itself "
                                          "counts as deviation; compare path_deviation only between cells of the same command"),
                  "band_note": ("band_mps %.3g m/s is an assumption (evaluator stall threshold 0.05 m/s x 2); a command whose |(vx, vy)| "
                                "<= band_mps is inside the band while standing still, so recovery_cmd says little for stop and low-speed "
                                "commands; the test is against the command, not against the off-mode run" % band_mps)}
    shapes_ok = dones.shape == (T, N) and vx.shape == (T, N) and vy.shape == (T, N) and xy.shape == (T, N, 2)
    shapes_ok = shapes_ok and (wz is None or wz.shape == (T, N)) and (tilt is None or tilt.shape == (T, N))
    if not shapes_ok:
        raise RuntimeError("회복 지표: 배열 모양이 맞지 않는다 alive %r dones %r vx %r vy %r xy %r wz %r tilt %r"
                           % (alive.shape, dones.shape, vx.shape, vy.shape, xy.shape, None if wz is None else wz.shape, None if tilt is None else tilt.shape))
    if cmd is not None and (len(cmd) != 3 or any(not math.isfinite(float(c)) for c in cmd)):
        raise RuntimeError("회복 지표: 명령이 (vx, vy, wz) 가 아니다: %r" % (cmd,))
    definition["command_turns"] = None if cmd is None else bool(float(cmd[2]) != 0.0)                 # 참이면 경로 이탈에 명령 원호가 섞인다
    definition["command_speed_above_band"] = None if cmd is None else bool(math.hypot(float(cmd[0]), float(cmd[1])) > band_mps)
    if push_step is None or not 0 < push_step < T:
        return {"defined": False, "reason": "no push inside the rollout or push at step 0 (no pre-push baseline)", "push_step": push_step, "definition": definition}
    pre0 = max(0, push_step - int(round(pre_s / dt)))
    base = ~dones[:push_step].any(0)
    n_base = int(base.sum())
    post_alive = alive[push_step:]
    post_dones = dones[push_step:]
    fell = base & post_dones.any(0)
    first_fall = np.argmax(post_dones, axis=0)
    fall_t = (first_fall[fell] + 1) * dt
    v_pre_w = (xy[push_step - 1] - xy[pre0]) / max((push_step - 1 - pre0) * dt, dt)
    t_rel = (np.arange(push_step, T) - (push_step - 1)) * dt
    predicted = xy[push_step - 1][None] + v_pre_w[None] * t_rel[:, None, None]
    deviation = np.linalg.norm(xy[push_step:] - predicted, axis=2)
    dev_max = np.where(post_alive, deviation, 0.0).max(axis=0)
    vb_pre = np.stack([vx[pre0:push_step].mean(0), vy[pre0:push_step].mean(0)], axis=1)
    hold = max(1, int(round(hold_s / dt)))
    err_pre = np.hypot(vx[push_step:] - vb_pre[:, 0][None], vy[push_step:] - vb_pre[:, 1][None])
    rec_pre_at = _first_hold((err_pre <= band_mps) & post_alive, hold)
    rec_pre = base & (rec_pre_at >= 0)

    def med(values):
        return float(np.median(values)) if len(values) else None

    out = {"defined": True, "push_step": int(push_step), "push_t_s": push_step * dt, "definition": definition,
           "envs_in_population": n_base,
           "fell_envs": int(fell.sum()), "fell_fraction": (float(fell.sum()) / n_base) if n_base else None, "fall_time_s_median": med(fall_t),
           "tilt_max_rad_median": None, "tilt_max_rad_max": None, "tilt_pre_mean_rad": None,
           "path_deviation_m_median": med(dev_max[base]), "path_deviation_m_max": float(dev_max[base].max()) if n_base else None,
           "command": None if cmd is None else [float(c) for c in cmd],
           "recovered_envs": None, "recovered_fraction": None, "recovery_time_s_median": None,
           "recovered_vs_pre_envs": int(rec_pre.sum()), "recovered_vs_pre_fraction": (float(rec_pre.sum()) / n_base) if n_base else None,
           "recovery_vs_pre_time_s_median": med((rec_pre_at[rec_pre] + 1) * dt)}
    if tilt is not None:
        tilt_max = np.where(post_alive, tilt[push_step:], 0.0).max(axis=0)
        out.update({"tilt_max_rad_median": med(tilt_max[base]), "tilt_max_rad_max": float(tilt_max[base].max()) if n_base else None,
                    "tilt_pre_mean_rad": float(tilt[pre0:push_step][:, base].mean()) if n_base else None})
    if cmd is not None:
        err_cmd = np.hypot(vx[push_step:] - float(cmd[0]), vy[push_step:] - float(cmd[1]))
        inside = (err_cmd <= band_mps) & post_alive
        if wz is not None:
            inside &= np.abs(wz[push_step:] - float(cmd[2])) <= band_radps
        rec_at = _first_hold(inside, hold)
        rec = base & (rec_at >= 0)
        out.update({"recovered_envs": int(rec.sum()), "recovered_fraction": (float(rec.sum()) / n_base) if n_base else None,
                    "recovery_time_s_median": med((rec_at[rec] + 1) * dt), "recovery_uses_wz": wz is not None})
    return out


def sample_bounds(ranges: dict[str, Any], scale: float) -> dict[str, tuple[float, float]]:
    """배율만큼 접힌 표본 허용 범위(validate_runtime_summary 와 같은 셈)."""
    from foothold_s2.curriculum.ex40_dr_runtime import _scaled_interval

    def scaled(pair, neutral):
        return _scaled_interval(tuple(float(v) for v in pair), scale, neutral)

    return {
        "base_com_offset_m": (min(scaled(ranges["base_com"][axis], 0.0)[0] for axis in ("x", "y", "z")),
                              max(scaled(ranges["base_com"][axis], 0.0)[1] for axis in ("x", "y", "z"))),
        "actuator_gains": (min(scaled(ranges["actuator_gains"][key], 1.0)[0] for key in ("stiffness_scale", "damping_scale")),
                           max(scaled(ranges["actuator_gains"][key], 1.0)[1] for key in ("stiffness_scale", "damping_scale"))),
        "motor_strength_multiplier": scaled(ranges["motor_strength"], 1.0),
        PUSH_SAMPLE_KEY: (min(scaled(pair, 0.0)[0] for pair in ranges["push_velocity"].values()),
                          max(scaled(pair, 0.0)[1] for pair in ranges["push_velocity"].values())),
    }


def _within(row: dict[str, Any], key: str, bounds: tuple[float, float], scale: float) -> None:
    low, high = bounds
    if row["min"] < low - 1e-6 or row["max"] > high + 1e-6:
        raise RuntimeError("DR 표본이 배율 %.3f 의 범위 [%.4f, %.4f] 를 벗어났다: %s min %.4f max %.4f"
                           % (scale, low, high, key, row["min"], row["max"]))
    if scale == 0.0 and (abs(row["min"] - NEUTRAL[key]) > 1e-9 or abs(row["max"] - NEUTRAL[key]) > 1e-9):
        raise RuntimeError("배율 0 인데 표본이 명목값이 아니다: %s" % key)


def check_fired(summary: dict[str, Any], scale: float, ranges: dict[str, Any], delay_max_s: float, *,
                num_envs: int, pushes: int, expected_pushes: int = 1) -> dict[str, Any]:
    """한 롤아웃의 readback 이 「이벤트마다 env 전부에 · 배율만큼 실제로 켜졌다」 를 보인다. 아니면 RuntimeError.

    reset 이벤트 셋: 표본 수 > 0 이고 닿은 env 수(target_envs) ≥ num_envs(롤아웃 앞 reset 이 전부에 닿음).
    밀기: 이번 롤아웃에 정확히 expected_pushes 번 불렸고, 표본이 pushes × num_envs 개 env · × 6 성분이며 배율 범위 안.
    지연: reset 표본 수 ≥ num_envs, 허용 substep == floor(delay_max × 배율 / dt), 관측 ≤ 허용.
    """
    if type(num_envs) is not int or num_envs <= 0:
        raise RuntimeError("DR 켠 평가: env 수가 양의 정수가 아니다: %r" % (num_envs,))
    samples = summary.get("actual_samples")
    if not isinstance(samples, dict):
        raise RuntimeError("DR 켠 평가: actual_samples 가 없다")
    bounds = sample_bounds(ranges, scale)
    counts, fired = {}, {}
    for key, name in zip(RESET_SAMPLE_KEYS, ("base_com", "actuator_gains", "motor_strength")):
        row = samples.get(key)
        if not isinstance(row, dict) or type(row.get("count")) is not int or row["count"] <= 0:
            raise RuntimeError("DR 켠 평가인데 reset 이벤트 표본이 없다: %s" % key)
        if type(row.get("target_envs")) is not int or row["target_envs"] < num_envs:
            raise RuntimeError("reset 이벤트가 env 전부에 닿지 않았다: %s 닿은 env %r < %d" % (key, row.get("target_envs"), num_envs))
        _within(row, key, bounds[key], scale)
        counts[key] = row["count"]
        fired[name] = row["target_envs"]
    if pushes != expected_pushes:
        raise RuntimeError("밀기 횟수가 일정과 다르다: 불림 %r 기대 %d" % (pushes, expected_pushes))
    push = samples.get(PUSH_SAMPLE_KEY)
    if expected_pushes > 0:
        if (not isinstance(push, dict) or push.get("target_envs") != pushes * num_envs
                or push.get("count") != pushes * num_envs * PUSH_RECORD_DIMS):
            raise RuntimeError("밀기 표본이 env 전부 × 횟수와 다르다: %r (기대 env %d · 표본 %d)"
                               % (push, pushes * num_envs, pushes * num_envs * PUSH_RECORD_DIMS))
        _within(push, PUSH_SAMPLE_KEY, bounds[PUSH_SAMPLE_KEY], scale)
        if scale > 0.0 and max(abs(float(push["min"])), abs(float(push["max"]))) <= 1e-9:
            raise RuntimeError("배율 %.3f > 0 인데 밀기 표본이 전부 0 이다(밀기가 root 속도에 닿지 않았다): %r" % (scale, push))
        fired["push"] = push["target_envs"]
    else:
        if isinstance(push, dict) and push.get("count"):
            raise RuntimeError("밀기 일정이 0 번인데 밀기 표본이 있다: %r" % (push,))
        fired["push"] = 0
    fired["push_events"] = pushes
    delay = summary.get("delay_readback")
    if not isinstance(delay, dict):
        raise RuntimeError("DR 켠 평가: 지연 행동 readback 이 없다(DelayedJointPositionAction 미설치)")
    dt = float(delay.get("physics_dt_seconds", 0.0))
    if dt <= 0:
        raise RuntimeError("DR 켠 평가: physics dt 가 0 이하")
    expected_max = int(math.floor(delay_max_s * scale / dt + 1e-9))
    observed = delay.get("observed_max_substeps")
    if delay.get("max_allowed_substeps") != expected_max or (observed or 0) > expected_max:
        raise RuntimeError("지연 상한이 배율과 맞지 않는다: 허용 %r 관측 %r 기대 %d" % (delay.get("max_allowed_substeps"), observed, expected_max))
    reset_samples = delay.get("reset_sample_count")
    if type(reset_samples) is not int or reset_samples < num_envs:
        raise RuntimeError("지연 행동 reset 표본이 env 전부에 닿지 않았다: %r < %d" % (reset_samples, num_envs))
    fired["delay_reset_samples"] = reset_samples
    fired["delay_observed_max_substeps"] = observed
    return {"fired": fired, "reset_sample_counts": counts, "delay_max_substeps": expected_max, "delay_observed_max_substeps": observed}


class DRMode:
    """평가기 한 판의 DR 상태. off 는 전부 no-op 이라 현행 출력이 바뀌지 않는다.

    켠 모드의 호출 순서(롤아웃 = 명령 하나 또는 시퀀스 하나):
    from_args(Kit 전) → after_make(gym.make 뒤 · 첫 reset 전) → [begin(reset 전) → step(매 step, env.step 전) → collect(끝)] × 롤아웃
    """

    def __init__(self, mode: str, scale: float | None, table: dict[str, Any] | None = None, *, pusher=None, eval_seed: int = 0):
        self.mode = mode
        self.scale = scale
        self.table = table
        self.eval_seed = int(eval_seed)
        self.receipt = None
        self.startup_events_kept: list[str] = []
        self.readback = None
        self.pusher = pusher or _default_pusher
        self._record: dict[str, Any] | None = None
        self._rollout: dict[str, Any] | None = None

    @classmethod
    def from_args(cls, args, env_cfg, *, installer=None, pusher=None) -> "DRMode":
        if args.dr_mode == "off":
            return cls("off", None)
        error = validate_args(args)
        if error:
            raise RuntimeError(error)
        table = load_table(args.dr_table)
        self = cls("on", float(args.dr_scale), table, pusher=pusher, eval_seed=int(args.eval_seed))
        events = getattr(env_cfg, "events", None)
        kept = [name for name in STARTUP_EVENTS if getattr(events, name, None) is not None]
        if kept != list(STARTUP_EVENTS):
            raise RuntimeError("DR 켠 평가: B env 의 시동 DR %r 가운데 %r 만 있다(다른 env 이거나 이미 꺼짐)" % (STARTUP_EVENTS, kept))
        self.startup_events_kept = kept
        installer = installer or _default_installer
        self.receipt = installer(env_cfg, table["full_ranges"], table["push_interval_s"], delay_max_s=table["delay_max_s"])
        for name in RUNTIME_RESET_TERMS:
            if not callable(getattr(getattr(events, name, None), "func", None)):
                raise RuntimeError("DR 켠 평가: 런타임 reset 이벤트가 설치되지 않았다: %s" % name)
        if not callable(getattr(getattr(events, RUNTIME_INTERVAL_TERM, None), "func", None)):
            raise RuntimeError("DR 켠 평가: 런타임 interval 밀기가 설치되지 않았다: %s" % RUNTIME_INTERVAL_TERM)
        setattr(events, RUNTIME_INTERVAL_TERM, None)                                   # B1: 6 s 명령 안에서 안 나는 interval 밀기는 떼고 가운데 step 밀기로
        action = getattr(getattr(env_cfg, "actions", None), "joint_pos", None)
        if (getattr(action, "max_delay_s", None) != table["delay_max_s"]
                or getattr(action, "dr_scale_from_env", False) is not True):
            raise RuntimeError("DR 켠 평가: 지연 행동이 설치되지 않았다(max_delay_s %r · dr_scale_from_env %r)"
                               % (getattr(action, "max_delay_s", None), getattr(action, "dr_scale_from_env", None)))
        self._record = {"mode": "on", "scale": self.scale, "cell_definition": CELL_DEFINITION, "seed_note": SEED_NOTE,
                        "table": table["path"], "table_sha256": table["sha256"],
                        "full_ranges": table["full_ranges"], "push_interval_s": list(table["push_interval_s"]),
                        "delay_max_s": table["delay_max_s"], "startup_events_kept": kept,
                        "installed": self.receipt,
                        "push_schedule": {"mode": "fixed_time_in_rollout", "at_s": PUSH_AT_S, "pushes_per_rollout": 1,
                                          "seed": "sha256(eval_seed|rollout key)", "eval_seed": self.eval_seed,
                                          "removed_interval_term": RUNTIME_INTERVAL_TERM,
                                          "training_interval_s": list(table["push_interval_s"]), "reason": PUSH_REASON},
                        "recovery_definition": {"band_mps": RECOVERY_BAND_MPS, "band_radps": RECOVERY_BAND_RADPS, "hold_s": RECOVERY_HOLD_S, "pre_s": RECOVERY_PRE_S},
                        "decision_use": "record_only: 밀기 칸 지표는 기록 전용 · DR 유지 판정(ex41 maintenance) 에 쓰지 않는다(lead 16:30)",
                        "env_scale_before_first_reset": None, "push_cells": {}, "readback": {}}
        return self

    @property
    def record(self) -> dict[str, Any] | None:
        return self._record

    def after_make(self, raw) -> float | None:
        """gym.make 뒤 · RslRlVecEnvWrapper(첫 reset) 앞에서 배율을 env 에 심는다."""
        if self.mode == "off":
            return None
        from foothold_s2.curriculum.ex40_dr_runtime import RuntimeReadback

        readback = RuntimeReadback(raw, self.table["full_ranges"], self.table["delay_max_s"], self.table["sha256"])
        readback.scale = self.scale
        raw._ex40_dr_scale = self.scale
        if getattr(raw, "_ex40_dr_scale", None) != self.scale or readback.scale != self.scale:
            raise RuntimeError("DR 켠 평가: 배율을 env 에 심지 못했다")
        self.readback = readback
        self._record["env_scale_before_first_reset"] = self.scale
        return self.scale

    def _pinned(self, raw) -> None:
        if self.readback is None or getattr(raw, "_ex40_dr_scale", None) != self.scale:
            raise RuntimeError("DR 켠 평가: 롤아웃 중 배율이 바뀌었거나 readback 이 없다")

    def begin(self, raw, key: str, total_steps: int, num_envs: int, dt: float) -> dict[str, Any] | None:
        """롤아웃의 reset 전에 부른다: 지난 표본을 비우고(B3) 이 롤아웃의 밀기 step · 시드를 정한다."""
        if self.mode == "off":
            return None
        self._pinned(raw)
        if self._rollout is not None:
            raise RuntimeError("DR 켠 평가: 앞 롤아웃 %r 의 collect 없이 다음 롤아웃을 시작했다" % (self._rollout["key"],))
        raw._ex40_dr_samples = {}
        try:
            action = raw.action_manager.get_term("joint_pos")
        except (AttributeError, KeyError, ValueError):
            action = None
        if action is not None and hasattr(action, "_ex40_sample_counts"):
            action._ex40_sample_counts = None
        self._rollout = {"key": key, **push_schedule(total_steps, dt), "num_envs": int(num_envs),
                         "push_seed": push_seed(self.eval_seed, key), "pushed": 0, "events": []}
        return {k: v for k, v in self._rollout.items() if k != "events"}

    def step(self, raw, step_index: int) -> bool:
        """매 step, env.step 전에 부른다. 이 롤아웃의 밀기 step 이면 env 전부를 한 번 밀고 이벤트(시각 · env 별 Δv) 를 적는다."""
        if self.mode == "off":
            return False
        if self._rollout is None:
            raise RuntimeError("DR 켠 평가: begin 없이 step 이 불렸다")
        if step_index != self._rollout["push_step"]:
            return False
        self._pinned(raw)
        event = self.pusher(raw, self.table["full_ranges"]["push_velocity"], self._rollout["push_seed"])
        if not isinstance(event, dict) or len(event.get("env_ids", [])) != self._rollout["num_envs"]:
            raise RuntimeError("DR 켠 평가: 밀기 기록이 env 전부를 담지 않았다: %r" % (type(event),))
        if self.scale > 0.0 and not float(event.get("dv_xy_norm_mps_median", 0.0)) > 0.0:
            raise RuntimeError("DR 켠 평가: 배율 %.3f > 0 인데 밀기 Δv 크기 중앙값이 0 이다(env 절반 이상이 안 밀렸다): %r"
                               % (self.scale, event.get("dv_xy_norm_mps_median")))
        self._rollout["pushed"] += 1
        self._rollout["events"].append({"step": int(step_index), "t_s": step_index * self._rollout["dt"],
                                        "seed": self._rollout["push_seed"], "scale": self.scale, **event})
        return True

    def collect(self, raw, key: str, res: dict[str, Any], row: dict[str, Any] | None = None,
                arrays: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """롤아웃이 끝난 뒤 실측 readback 을 적고 켜짐을 확인한다.

        row 가 있으면 점수 행에 dr_scale · dr_fired · dr_push · dr_recovery 를 더한다(B2 · G18).
        arrays(alive · dones · vx · vy · xy, 평가 루프의 step 배열) 가 있으면 회복 지표를 센다. 없으면(시퀀스) 회복 지표는 None.
        """
        if self.mode == "off":
            return None
        self._pinned(raw)
        if self._rollout is None:
            raise RuntimeError("DR 켠 평가: begin 없이 collect 가 불렸다: %s" % key)
        if self._rollout["key"] != key:
            raise RuntimeError("DR 켠 평가: begin 의 롤아웃 %r 과 collect 의 %r 이 다르다" % (self._rollout["key"], key))
        rollout, self._rollout = self._rollout, None
        summary = self.readback.summary()
        checked = check_fired(summary, self.scale, self.table["full_ranges"], self.table["delay_max_s"],
                              num_envs=rollout["num_envs"], pushes=rollout["pushed"], expected_pushes=rollout["expected_pushes"])
        summary["rollout"] = {k: rollout[k] for k in ("key", "total_steps", "dt", "push_step", "push_t_s", "expected_pushes", "num_envs", "push_seed", "pushed")}
        summary["push_events"] = rollout["events"]
        recovery = None
        if arrays is not None:
            recovery = recovery_metrics(arrays["alive"], arrays["dones"], arrays["vx"], arrays["vy"], arrays["xy"], rollout["dt"], rollout["push_step"],
                                        wz=arrays.get("wz"), tilt=arrays.get("tilt"), cmd=arrays.get("cmd"))
        summary["recovery"] = recovery
        res.setdefault("dr", self._record)["readback"][key] = summary
        push_row = None
        if rollout["events"]:
            ev = rollout["events"][0]
            push_row = {"step": ev["step"], "t_s": ev["t_s"], "seed": ev["seed"], "envs": len(ev["env_ids"]),
                        "dv_xy_norm_mps_median": ev["dv_xy_norm_mps_median"], "dv_xy_norm_mps_max": ev["dv_xy_norm_mps_max"]}
        cell = {"scale": self.scale, "push": push_row, "fired": checked["fired"], "decision_use": "record_only"}
        if recovery is not None and recovery.get("defined"):
            cell.update({k: recovery.get(k) for k in ("envs_in_population", "fell_envs", "fell_fraction", "fall_time_s_median",
                                                      "tilt_max_rad_median", "tilt_max_rad_max", "path_deviation_m_median", "path_deviation_m_max",
                                                      "recovered_envs", "recovered_fraction", "recovery_time_s_median", "command")})
        self._record["push_cells"][key] = cell                                              # 점수 파일의 칸별 숫자 표(lead 16:30 · 기록 전용)
        if row is not None:
            row["dr_scale"] = self.scale
            row["dr_fired"] = checked["fired"]
            row["dr_push"] = push_row
            row["dr_recovery"] = recovery
        print("MAPMODE_DR", key, json.dumps({"scale": self.scale, **checked, "push": push_row, "recovery": recovery}), flush=True)
        return summary
