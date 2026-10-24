"""종아리 펴짐 한계 띠 보상 항 (창 3 처방 후보 1축, SONNET-X25). CPU 만: 식은 core 로, Isaac Lab 쪽 연결은 소스 AST 와 설치 소스 대조로 시험한다."""

import ast
from pathlib import Path

import pytest
import torch

from foothold_s2.rewards import core

ROOT = Path(__file__).resolve().parents[1]
HI = torch.tensor([-0.8378] * 4)


def T(rows):
    return torch.tensor(rows, dtype=torch.float32)


def test_known_inputs_from_the_design_draft():
    q = T([[-0.8378] * 4,                     # 네 관절 모두 hard 상한 -> 4 * 0.05
           [-0.8878] * 4,                     # 띠 시작점 -> 0
           [-1.5] * 4,                        # 한참 굽힘 -> 0
           [-2.72] * 4,                       # 하한 쪽 -> 0
           [-0.8378, -1.5, -1.5, -1.5]])      # 한 관절만 상한 -> 0.05
    r = core.calf_extension_band(q, HI)

    assert torch.allclose(r, T([0.20, 0.0, 0.0, 0.0, 0.05]), atol=1e-6)
    assert torch.allclose(-2.0 * r[0], T(-0.40), atol=1e-6) and torch.allclose(-2.0 * r[4], T(-0.10), atol=1e-6)      # 초안의 최대 -0.40 / 한 관절 -0.10


def test_linear_inside_the_band_and_grows_past_the_limit_and_per_env_limits_are_used():
    assert torch.allclose(core.calf_extension_band(T([[-0.8628, -1.5, -1.5, -1.5]]), HI), T([0.025]), atol=1e-6)
    assert torch.allclose(core.calf_extension_band(T([[-0.8278, -1.5, -1.5, -1.5]]), HI), T([0.06]), atol=1e-6)
    per_env = torch.stack([HI, HI + 0.1])                                   # env 마다 상한이 다르면 그 상한을 쓴다
    q = T([[-0.8378] * 4, [-0.8378] * 4])

    assert torch.allclose(core.calf_extension_band(q, per_env), T([0.20, 0.0]), atol=1e-6)


def test_the_term_is_off_by_default_and_the_default_weight_is_zero():
    src = (ROOT / "rewards" / "start_rewards.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

    assert "calf_ext_limit_band" in fn and "calf_ext_limit_band_term" in fn and core.CALF_BAND_WEIGHT_OFF == 0.0
    defaults = [ast.unparse(d) for d in fn["calf_ext_limit_band_term"].args.defaults]

    assert defaults[0] == "core.CALF_BAND_WEIGHT_OFF"
    assert "joint_pos_limits" in ast.unparse(fn["calf_ext_limit_band"]) and "[:, ids, 1]" in ast.unparse(fn["calf_ext_limit_band"])      # hard 상한을 시뮬레이터에서, 위쪽(1) 열
    assert "-0.8378" not in src                                              # 상수로 박지 않는다
    cfg_cls = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "StartRewardsCfg"][0]

    assert "calf_ext_limit_band" not in ast.unparse(cfg_cls)                  # 기본 StartRewardsCfg 에는 붙이지 않았다(기존 task 의 cfg 덤프가 바뀌지 않는다)


def test_installed_reward_manager_skips_zero_weight_terms():
    src = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/managers/reward_manager.py")
    if not src.exists():
        pytest.skip("Isaac Lab 소스 없음")
    text = src.read_text(encoding="utf-8")

    assert "if term_cfg.weight == 0.0:" in text and "continue" in text[text.index("if term_cfg.weight == 0.0:"):][:160]


def test_penalty_log_names_were_not_extended_and_the_term_does_not_call_it():
    src = (ROOT / "rewards" / "start_rewards.py").read_text(encoding="utf-8")
    body = ast.unparse([n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "calf_ext_limit_band"][0])

    assert "record(" not in body
