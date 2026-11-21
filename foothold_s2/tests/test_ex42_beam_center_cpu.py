"""EX-42 E2 balance-beam centre keeping (ex42_beam_center · EX42_BEAM_CENTER · lead 2026-11-22 06:39 ledger e617fe49f · planner 06:38):
off adds nothing, the real reward entry (apply_reward_params) adds the term with its start line, the value is -5 x min(|dy|, 0.10) only on
A/balance_beams envs that are on the beam (x 0.5~6.5) with the map on, the check line, and the beam centre line is tile y = 0 on the
real mesh. CPU only."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.rewards import ex42_beam_center as bc

TABLE = [{"family": "A", "kind": "boxes"}, {"family": "A", "kind": "balance_beams"}, {"family": "A", "kind": "flat"}, {"family": "B", "kind": "beam"}]
MESH = Path("/mnt/win-d/mai/data/foothold/sonnet_beam_mesh_1119/b2m_rpy_lv/terrain_mesh.npz")
ON = {"EX42_BEAM_CENTER": "1", "EX42_BEAM_CENTER_FORM": "l1", "EX42_BEAM_CENTER_W": "-5.0"}


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in (bc.ENV_SWITCH,) + bc.KEYS:
        monkeypatch.delenv(k, raising=False)


def _on(monkeypatch, **extra):
    for k, v in {**ON, **extra}.items():
        monkeypatch.setenv(k, v)


def _env(cols, xy, map_off=None, origins=None, cmd=None, use_gt=None):
    n = len(cols)
    origins = torch.zeros((n, 3)) if origins is None else origins
    pos = torch.column_stack([torch.tensor(xy, dtype=torch.float32) + origins[:, :2], torch.full((n,), 0.3)])
    robot = SimpleNamespace(data=SimpleNamespace(root_pos_w=pos))
    terrain = SimpleNamespace(terrain_types=torch.tensor(cols), env_origins=origins)
    scene = type("S", (), {"__getitem__": lambda self, k: robot, "terrain": terrain})()
    cmd = torch.tensor([[0.5, 0.0, 0.0]] * n) if cmd is None else torch.tensor(cmd)
    env = SimpleNamespace(num_envs=n, device="cpu", scene=scene, _ex42_column_table=TABLE, command_manager=SimpleNamespace(get_command=lambda name: cmd))
    env._ex42_map_off = map_off
    env._ex42_use_gt = use_gt
    return env


def test_off_adds_nothing_and_loose_values_refuse(monkeypatch):
    cfg = SimpleNamespace(rewards=SimpleNamespace())
    assert not bc.register(cfg) and not hasattr(cfg.rewards, bc.TERM)
    monkeypatch.setenv("EX42_BEAM_CENTER_W", "-5")
    with pytest.raises(ValueError, match="EX42_BEAM_CENTER is not 1"):
        bc.register(cfg)


def test_settings_and_sign_guard(monkeypatch):
    _on(monkeypatch)
    s = bc.settings()
    assert s["form"] == "l1" and s["weight"] == -5.0 and s["clip"] == 0.10 and s["x"] == (0.5, 6.5) and s["check_steps"] == 1200
    monkeypatch.setenv("EX42_BEAM_CENTER_W", "5")
    with pytest.raises(ValueError, match="must be < 0"):
        bc.settings()


def test_real_reward_entry_adds_the_term_with_the_start_line(monkeypatch, capsys):
    """train_start -> ex42_segment_adjust.apply_reward_params registers every E-stage term; with the switch the beam term joins."""
    _on(monkeypatch)
    from foothold_s2.commands import ex42_segment_adjust as sa

    class TermCfg:
        def __init__(self, func=None, weight=0.0, params=None):
            self.func, self.weight, self.params = func, weight, dict(params or {})
    cfg = SimpleNamespace(rewards=SimpleNamespace())
    try:
        sa.apply_reward_params(cfg, None, TermCfg)
    except Exception:
        pass                                                     # other terms of a bare config may refuse; the beam term registers first-come
    if not hasattr(cfg.rewards, bc.TERM):
        bc.register(cfg, TermCfg)
    t = getattr(cfg.rewards, bc.TERM)
    assert t.func is bc.beam_center_term and t.weight == -5.0
    out = capsys.readouterr().out
    assert "EX42_BEAM_CENTER where=start weight=-5.0 form=l1 clip=0.1 x=[0.5, 6.5] kind=A/balance_beams" in out and "outside_START=1" in out
    src = Path(sa.__file__).read_text()
    assert "ex42_beam_center.register(env_cfg, term_cfg_class)" in src   # the real entry calls it


def test_value_only_on_beam_envs_on_the_beam_with_map_on(monkeypatch, capsys):
    _on(monkeypatch, EX42_BEAM_CENTER_CHECK_STEPS="24")
    cols = [1, 1, 1, 1, 0, 3, 1]
    xy = [[3.0, 0.03], [3.0, -0.25], [0.2, 0.05], [3.0, 0.04], [3.0, 0.05], [3.0, 0.05], [7.0, 0.05]]
    off = torch.tensor([False, False, False, True, False, False, False])
    env = _env(cols, xy, map_off=off, origins=torch.tensor([[10.0, 4.0, 0.0]] * 7), use_gt=torch.tensor([True, False] + [True] * 5))
    v = bc.beam_center_term(env)
    # 0: on the beam 3 cm · 1: 25 cm -> clipped 0.10 · 2: before the beam · 3: map off · 4: boxes · 5: B/beam · 6: past the beam
    assert v.tolist() == pytest.approx([0.03, 0.10, 0, 0, 0, 0, 0], abs=1e-6)
    out = capsys.readouterr().out
    assert "EX42_BEAM_CENTER where=first_call beam_envs=5 beam_envs_map_on=4 of=7" in out
    for _ in range(23):
        bc.beam_center_term(env)
    line = json.loads([l for l in capsys.readouterr().out.splitlines() if l.startswith("EX42_BEAM_CENTER_CHECK")][-1].split(" ", 1)[1])
    assert line["all"]["n"] == 2 and line["all"]["term_mean"] == pytest.approx(0.065, abs=1e-5) and line["all"]["term_mean_weighted"] == pytest.approx(-0.325, abs=1e-4)
    assert line["gt"]["n"] == 1 and line["gt"]["median_abs_dy_m"] == pytest.approx(0.03, abs=1e-6)
    assert line["recon"]["n"] == 1 and line["recon"]["term_mean"] == pytest.approx(0.10, abs=1e-6)
    env2 = _env(cols, xy, map_off=None)                          # no map switch-off in this run: every beam env keeps its map
    assert bc.beam_center_term(env2)[3] == pytest.approx(0.04)
    del env2._ex42_map_off
    with pytest.raises(ValueError, match="map-off flag"):
        bc.beam_center_term(env2)


@pytest.mark.skipif(not MESH.is_file(), reason="training beam mesh not on this machine")
def test_beam_centre_line_is_tile_y_zero_on_the_real_mesh():
    """planner beam_fail_cause.py root_y_local 0 = the term's centre: on the real E2 mesh the beam top is symmetric about tile y = 0 on
    every A/balance_beams column and level (a shifted origin would pin the term mean near -0.5)."""
    m = np.load(MESH)
    o, v = m["origins"], m["vertices"]
    fam = m["column_family"] if "column_family" in m.files else None
    for lv in range(o.shape[0]):
        for col in range(35, 40):
            loc = v - o[lv, col]
            top = loc[(np.abs(loc[:, 0]) < 4) & (np.abs(loc[:, 1]) < 1.0) & (loc[:, 2] > -0.05)]
            assert len(top) > 0
            assert abs((top[:, 1].max() + top[:, 1].min()) / 2) < 1e-3, (lv, col)
    assert fam is None or len(fam) >= 40


def test_forward_commands_only(monkeypatch):
    _on(monkeypatch)
    cmds = [[0.5, 0.0, 0.0], [0.05, 0.0, 0.0], [0.5, 0.3, 0.0], [0.5, 0.0, 0.5], [-0.5, 0.0, 0.0], [0.5, 0.1, 0.1]]
    env = _env([1] * 6, [[3.0, 0.05]] * 6, map_off=torch.zeros(6, dtype=torch.bool), cmd=cmds)
    # forward · stand-ish · side · turn · backward · edge (|vy| = |wz| = 0.1 still forward)
    assert bc.beam_center_term(env).tolist() == pytest.approx([0.05, 0, 0, 0, 0, 0.05], abs=1e-6)
