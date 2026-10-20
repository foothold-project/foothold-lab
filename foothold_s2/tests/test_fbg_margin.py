"""foot_below_ground 문턱 0.25 m (lead 10/21 안 B): 계단 단 최대 0.23 m 에서 안 켜지고 깊이 0.3 m 틈 낙하에서는 켜진다. Kit 없이 합성 입력으로 시험한다."""

import os
import re
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.robots import go2_params as gp
from foothold_s2.tasks import mdp_extra

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _Scene:
    def __init__(self, asset, scanner):
        self._asset = asset
        self.sensors = {"scan": scanner}

    def __getitem__(self, name):
        return self._asset


def _env(foot_z, ground_z, dist=0.05):
    """발 하나(나머지 세 발은 같은 지면 위), 가장 가까운 스캔 점의 지면 높이 `ground_z`, 수평 거리 `dist`."""
    feet = torch.zeros(1, 4, 3)
    feet[0, :, 2] = 0.0
    feet[0, 0, 0] = dist
    feet[0, 0, 2] = foot_z
    hits = torch.zeros(1, 4, 3)
    hits[0, :, 2] = 0.0
    hits[0, 0, :] = torch.tensor([0.0, 0.0, ground_z])
    asset = SimpleNamespace(data=SimpleNamespace(body_pos_w=feet))
    scanner = SimpleNamespace(data=SimpleNamespace(ray_hits_w=hits))

    return SimpleNamespace(scene=_Scene(asset, scanner)), SimpleNamespace(name="robot", body_ids=slice(None)), SimpleNamespace(name="scan")


def _fires(foot_z, ground_z, margin):
    env, asset_cfg, scanner_cfg = _env(foot_z, ground_z)

    return bool(mdp_extra.foot_below_ground(env, None, scanner_cfg, asset_cfg, margin=margin)[0])


def test_margin_constant_is_025_and_the_env_cfg_reads_it():
    assert gp.TERMINATION["foot_below_ground_m"] == pytest.approx(0.25)
    source = open(os.path.join(ROOT, "foothold_s2", "tasks", "s1_env_cfg.py"), encoding="utf-8").read()
    assert re.search(r'"margin":\s*gp\.TERMINATION\["foot_below_ground_m"\]', source)


def test_stair_step_023_does_not_fire_at_025_but_did_at_02():
    assert not _fires(-0.23, 0.0, gp.TERMINATION["foot_below_ground_m"])
    assert _fires(-0.23, 0.0, 0.2)                                  # 옛 값에서는 오판이었다 (fbg2 측정 56 건)


def test_gap_fall_of_depth_03_fires_at_025():
    assert _fires(-0.30, 0.0, gp.TERMINATION["foot_below_ground_m"])


def test_boundary_values():
    assert not _fires(-0.249, 0.0, 0.25)
    assert _fires(-0.251, 0.0, 0.25)


def test_a_foot_far_from_every_scan_point_is_ignored():
    env, asset_cfg, scanner_cfg = _env(-0.5, 0.0, dist=0.5)

    assert not bool(mdp_extra.foot_below_ground(env, None, scanner_cfg, asset_cfg, margin=0.25)[0])
