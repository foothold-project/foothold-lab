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
def clean(monkeypatch, tmp_path):
    for k in (bc.ENV_SWITCH,) + bc.KEYS:
        monkeypatch.delenv(k, raising=False)
    # a tiny training mesh: column 1 (A/balance_beams) has a beam top at z 0 from tile x 0.5 to 6.5, half width 0.30
    verts = np.array([[0.5, -0.3, 0.0], [0.5, 0.3, 0.0], [6.5, -0.3, 0.0], [6.5, 0.3, 0.0], [3.0, 0.0, -0.8]], dtype=np.float32)
    np.savez(tmp_path / "terrain_mesh.npz", vertices=verts, faces=np.array([[0, 1, 2]]), origins=np.zeros((1, 4, 3)))
    monkeypatch.setenv(bc.MESH_ENV, str(tmp_path))


def _on(monkeypatch, **extra):
    for k, v in {**ON, **extra}.items():
        monkeypatch.setenv(k, v)


def _quat_yaw(yaw):
    yaw = torch.as_tensor(yaw, dtype=torch.float32)
    return torch.stack([torch.cos(yaw / 2), torch.zeros_like(yaw), torch.zeros_like(yaw), torch.sin(yaw / 2)], -1)


def _env(cols, xy, map_off=None, origins=None, cmd=None, use_gt=None, yaw=None, z=None):
    n = len(cols)
    origins = torch.zeros((n, 3)) if origins is None else origins
    pos = torch.column_stack([torch.tensor(xy, dtype=torch.float32) + origins[:, :2], torch.full((n,), 0.3) if z is None else torch.tensor(z, dtype=torch.float32)])
    robot = SimpleNamespace(data=SimpleNamespace(root_pos_w=pos, root_quat_w=_quat_yaw([0.0] * n if yaw is None else yaw)))
    terrain = SimpleNamespace(terrain_types=torch.tensor(cols), terrain_levels=torch.zeros(n, dtype=torch.long), env_origins=origins)
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
    assert s["form"] == "l1" and s["weight"] == -5.0 and s["clip"] == 0.10 and s["x"] == (0.5, 6.5) and s["yaw"] == 0.3 and s["check_steps"] == 1200
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
    assert "EX42_BEAM_CENTER where=start weight=-5.0 form=l1 clip=0.1 x=[0.5, 6.5] yaw_max=0.3 kind=A/balance_beams" in out and "outside_START=1" in out
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


def test_map_off_is_reread_every_call_and_beam_columns_never_get_map_off(monkeypatch, capsys):
    """planner 07:26 (first_call beam_envs_map_on=430 of beam_envs=430): the real draw filter (map_switch.eligible_map_off, used by
    start_runner._restrict_map_off) never switches the map off on A/balance_beams (a sparse column, lead decision 11/11), so map-on = all
    beam envs is expected there; the term still re-reads env._ex42_map_off on every call (a map-off env's value is 0 from that call on)."""
    from foothold_s2.runners.map_switch import eligible_map_off
    _on(monkeypatch)
    names = ["boxes", "balance_beams", "flat", "B/beam"]                  # generator_column_names: A columns are bare kind names
    cols = torch.tensor([0, 1, 2, 3, 1])
    drawn = torch.ones(5, dtype=torch.bool)                              # every env drew «map off»
    off = drawn & eligible_map_off(cols, torch.zeros(5, dtype=torch.long), names)
    assert off.tolist() == [True, False, True, False, False]             # only A continuous / flat columns may lose the map
    env = _env(cols.tolist(), [[3.0, 0.05]] * 5, map_off=off)
    assert bc.beam_center_term(env).tolist() == pytest.approx([0, 0.05, 0, 0, 0.05], abs=1e-6)
    assert "beam_envs=2 beam_envs_map_on=2 of=5" in capsys.readouterr().out
    env._ex42_map_off = torch.tensor([False, True, False, False, False])  # the runner publishes a new flag before the next env.step
    assert bc.beam_center_term(env).tolist() == pytest.approx([0, 0, 0, 0, 0.05], abs=1e-6)   # a map-off env's term value is 0


def test_yaw_condition_and_check_line(monkeypatch, capsys):
    """lead 07:39 (planner 07:38): only a body facing along the beam (|yaw| <= 0.3 rad from +x) is scored; the check line gives candidates,
    the yaw pass share and the |dy| median of candidates and of passed samples, per all / gt / recon."""
    _on(monkeypatch, EX42_BEAM_CENTER_CHECK_STEPS="24")
    yaw = [0.0, 0.29, -0.31, 3.0, 0.1]
    xy = [[3.0, 0.02], [3.0, 0.04], [3.0, 0.30], [3.0, 0.20], [3.0, 0.06]]
    env = _env([1] * 5, xy, map_off=torch.zeros(5, dtype=torch.bool), yaw=yaw, use_gt=torch.tensor([True, True, True, False, False]))
    v = bc.beam_center_term(env)
    assert v.tolist() == pytest.approx([0.02, 0.04, 0, 0, 0.06], abs=1e-6)      # turned bodies (|yaw| 0.31 · 3.0) score 0
    for _ in range(23):
        bc.beam_center_term(env)
    line = json.loads([l for l in capsys.readouterr().out.splitlines() if l.startswith("EX42_BEAM_CENTER_CHECK")][-1].split(" ", 1)[1])
    a = line["all"]
    assert a["n_cand"] == 5 and a["n"] == 3 and a["yaw_pass"] == pytest.approx(0.6) and a["median_abs_dy_m"] == pytest.approx(0.04, abs=1e-6)
    assert a["median_abs_dy_m_cand"] == pytest.approx(0.06, abs=1e-6)
    assert line["gt"]["n_cand"] == 3 and line["gt"]["n"] == 2 and line["recon"]["n_cand"] == 2 and line["recon"]["n"] == 1
    monkeypatch.setenv("EX42_BEAM_CENTER_YAW", "0")
    with pytest.raises(ValueError, match="EX42_BEAM_CENTER_YAW"):
        bc.settings()


def test_only_a_body_on_the_beam_is_scored(monkeypatch, capsys):
    """lead 08:28 (planner 08:27): a robot that stepped off the beam and then got a forward command scores 0: root z above top - 0.10 and
    |dy| <= half width + 0.05 (the tiny mesh: top 0, half 0.30)."""
    _on(monkeypatch, EX42_BEAM_CENTER_CHECK_STEPS="24")
    xy = [[3.0, 0.05], [3.0, 0.34], [3.0, 0.40], [3.0, 0.05], [3.0, 0.05]]
    z = [0.30, 0.30, 0.30, -0.50, -0.05]                       # on · edge (0.34 <= 0.35) · off to the side · down in the pit · just above top-0.10
    env = _env([1] * 5, xy, map_off=torch.zeros(5, dtype=torch.bool), z=z)
    assert bc.beam_center_term(env).tolist() == pytest.approx([0.05, 0.10, 0, 0, 0.05], abs=1e-6)
    for _ in range(23):
        bc.beam_center_term(env)
    a = json.loads([l for l in capsys.readouterr().out.splitlines() if l.startswith("EX42_BEAM_CENTER_CHECK")][-1].split(" ", 1)[1])["all"]
    assert a["n_cand"] == 5 and a["n"] == 3 and a["on_beam_of_yaw_pass"] == pytest.approx(0.6) and a["at_clip_share"] == pytest.approx(1 / 3, abs=1e-4)


@pytest.mark.skipif(not MESH.is_file(), reason="training beam mesh not on this machine")
def test_beam_geometry_from_the_real_mesh():
    """Half width narrows by level (0.266 m at level 0 to 0.045 m at level 9) and the top is within 6 cm of the tile origin z (the rpy-tilted beams: 0.050 m measured)."""
    table = [{"family": "A", "kind": "x"}] * 35 + [{"family": "A", "kind": "balance_beams"}] * 5 + [{"family": "A", "kind": "x"}] * 36
    top, half = bc.beam_geometry(str(MESH.parent), table)
    assert half[0, 37] == pytest.approx(0.266, abs=2e-3) and half[9, 37] == pytest.approx(0.045, abs=2e-3)
    assert bool((half[1:, 35:40] < half[:-1, 35:40]).all()) and float(top[:, 35:40].abs().max()) < 0.06
    assert bool(torch.isnan(half[:, 0]).all())


def test_missing_mesh_refuses(monkeypatch):
    _on(monkeypatch)
    monkeypatch.delenv(bc.MESH_ENV)
    env = _env([1], [[3.0, 0.0]], map_off=torch.zeros(1, dtype=torch.bool))
    with pytest.raises(ValueError, match=bc.MESH_ENV):
        bc.beam_center_term(env)
