"""B2a 기하 채널 (DESIGN-MAP-EDGE 11 절): 투영 (평지 · 기울인 몸 · 계단 한 단) · U-Net 첫 층 이어받기 · 기록기 grav · 오프라인 맞추기에서 켜기. CPU · Kit 없음."""
import math

import numpy as np
import pytest
import torch

from foothold_s2.eval import ex42_mapfit_offline as off
from foothold_s2.eval import ex42_mapfit_record as rec
from foothold_s2.models import geom_channel as gc
from foothold_s2.models import start_perception as sp
from foothold_s2.sensors import depth_cam_cfg as cam

BASE_H = 0.34
UP = torch.tensor([[0.0, 0.0, -1.0]])


def _depth_of_ground(gravity, plane_z, step=None):
    """정답을 아는 입력: 수평면 (수평 틀에서 z' = plane_z) 을 광선으로 맞혀 정규화 깊이를 만든다. step = (x 경계, 윗면 z') 이면 경계 앞은 plane_z · 뒤는 윗면 (벽 사이 화소는 미검출)."""
    rays = gc._rays_body()
    mount = torch.tensor(cam.OFFSET_POS)
    L = gc.level_frame(gravity)[0]
    rz, rx = rays @ L[2], rays @ L[0]
    mz, mx = float(mount @ L[2]), float(mount @ L[0])

    def hit(z):
        d = (z - mz) / rz.clamp(max=-1e-6)
        return d, mx + d * rx

    d, x = hit(plane_z)
    ok = rz < -1e-6
    if step is not None:
        xb, zt = step
        d2, x2 = hit(zt)
        on_top = ok & (x2 >= xb)
        wall = ok & (x >= xb) & ~on_top
        d = torch.where(on_top, d2, d)
        ok = ok & ~wall
    dn = ((d - gc.NEAR) / (gc.FAR - gc.NEAR)).clamp(0, 1)
    return torch.where(ok & (d <= gc.FAR), dn, torch.ones_like(dn))[None]


def test_flat_ground_upright_gives_base_height_in_the_front_cells_only():
    h, s = gc.project(_depth_of_ground(UP, -BASE_H), UP)
    seen = s[0] > 0
    assert 0.2 < float(seen.float().mean()) < 0.45 and not bool(seen[:15].any())          # 앞쪽 4 할 · 몸 밑은 안 보임 (설계 11.1 의 29 %)
    assert float((h[0][seen] + BASE_H).abs().max()) < 0.02                                # 칸 안 점들은 한 칸 (5 cm) 안의 깊이 차이 · 평지라 높이는 같다
    assert float(h[0][~seen].abs().max()) == 0.0                                          # 안 보인 칸은 0


def test_tilted_body_is_corrected_by_gravity_and_ignored_when_level_is_assumed():
    a = math.radians(5.0)
    g = torch.tensor([[math.sin(a), 0.0, -math.cos(a)]])
    depth = _depth_of_ground(g, -BASE_H)
    h_ok, s_ok = gc.project(depth, g)
    h_bad, s_bad = gc.project(depth, UP)
    ok, bad = s_ok[0] > 0, s_bad[0] > 0
    assert float((h_ok[0][ok] + BASE_H).abs().mean()) < 0.01                               # 중력을 알면 평지는 평지
    assert float((h_bad[0][bad] + BASE_H).abs().mean()) > 0.05                             # 수평이라 놓으면 5 cm 이상 틀림 (설계 11.1: 3.8 cm 급)


def test_stair_step_is_drawn_sharp_with_max_and_blurred_with_mean():
    xb, rise = 0.80, 0.10
    depth = _depth_of_ground(UP, -BASE_H, step=(xb, -BASE_H + rise))
    h, s = gc.project(depth, UP)
    x_c = gc.X0 + gc.RES * (torch.arange(gc.MAP_X) + 0.5)
    low = (x_c < xb - 0.1)[:, None] & (s[0] > 0)
    top = (x_c > xb + 0.1)[:, None] & (s[0] > 0)
    assert bool(low.any()) and bool(top.any())
    assert float((h[0][low] + BASE_H).abs().max()) < 0.02 and float((h[0][top] + BASE_H - rise).abs().max()) < 0.02
    hm, _ = gc.project(depth, UP, agg="mean")
    assert float((hm[0][top] + BASE_H - rise).abs().max()) < 0.02                           # 평면 안은 둘이 같다 (경계 칸만 다르다)


def test_level_frame_is_orthonormal_identity_when_upright_and_keeps_heading():
    assert torch.allclose(gc.level_frame(UP)[0], torch.eye(3), atol=1e-6)
    a = math.radians(10.0)
    g = torch.tensor([[math.sin(a), 0.0, -math.cos(a)], [0.0, math.sin(a), -math.cos(a)]])
    L = gc.level_frame(g)
    assert torch.allclose(L @ L.transpose(1, 2), torch.eye(3).expand(2, 3, 3), atol=1e-5)
    assert torch.allclose(torch.einsum("bij,bj->bi", L, g), torch.stack([torch.zeros(2), torch.zeros(2), -torch.ones(2)], 1), atol=1e-6)    # 중력은 -z' 로만
    assert float(L[0, 1, 0]) == pytest.approx(0.0, abs=1e-6)                                # 앞뒤로 기울면 y' 는 몸 y 와 같다


def test_miss_pixels_and_bad_agg_are_handled():
    h, s = gc.project(torch.ones(2, 60, 60), UP.expand(2, 3))
    assert float(s.sum()) == 0 and float(h.abs().sum()) == 0
    with pytest.raises(ValueError):
        gc.project(torch.ones(1, 60, 60), UP, agg="min")


def test_unet_geom_off_is_the_old_module_and_geom_on_starts_equal_after_first_layer_extension():
    torch.manual_seed(0)
    old, new = sp.UNetRefine(), sp.UNetRefine(geom=True)
    assert list(old.state_dict()) == list(sp.UNetRefine().state_dict())
    ext = sp.geom_extend_first_layer({"refine." + k: v for k, v in old.state_dict().items()}, {"refine." + k: v for k, v in new.state_dict().items()})
    new.load_state_dict({k[len("refine."):]: v for k, v in ext.items()})
    rough = torch.randn(3, sp.MAP_X, sp.MAP_Y)
    assert torch.allclose(old(rough), new(rough, torch.randn(3, 2, sp.MAP_X, sp.MAP_Y)), atol=1e-6)        # 새 두 채널의 첫 가중은 0
    with pytest.raises(ValueError):
        new(rough)
    with pytest.raises(ValueError):
        old(rough, torch.zeros(3, 2, sp.MAP_X, sp.MAP_Y))


def test_recorder_saves_the_gravity_columns_of_the_newest_history_frame():
    torch.manual_seed(0)
    per = sp.StartPerception(sp.PerceptionCfg())
    n = 2
    st = per.init_state(n, "cpu")
    r = rec.Recorder(); r.install()
    obs = torch.randn(n, sp.OBS_DIM)
    try:
        with torch.no_grad():
            per.step(st, per.ingest(st, obs, torch.rand(n, 60, 60)), torch.rand(n, sp.MAP_X, sp.MAP_Y), deterministic=True)
    finally:
        r.uninstall()
    assert np.allclose(np.concatenate(r.rec["grav"]), obs[:, 3:6].numpy())


def _fake_record(path, n_env=3, ticks=6, seed=0, grav=True):
    g = np.random.default_rng(seed)
    env = np.repeat(np.arange(n_env, dtype=np.int16), ticks)
    n = n_env * ticks
    depth = _depth_of_ground(UP, -BASE_H)[0].numpy()
    extra = {"grav": np.tile(np.array([0.0, 0.0, -1.0], np.float32), (n, 1))} if grav else {}
    gt = np.full((n, sp.MAP_X, sp.MAP_Y), -BASE_H, np.float32); gt[:, :, 8:] += 0.1
    np.savez(path, env=env, call=np.tile(np.arange(ticks, dtype=np.int32) * 5 + 1, n_env), first=np.tile(np.arange(ticks) == 0, n_env),
             depth2=np.tile(depth[None, None], (n, 2, 1, 1)).astype(np.float16), z_prop=g.standard_normal((n, 128)).astype(np.float32), gt=gt, **extra)


def test_offline_fit_can_switch_geom_on_and_refuses_a_record_without_gravity(tmp_path):
    _fake_record(tmp_path / "a.npz"); _fake_record(tmp_path / "b.npz", seed=1); _fake_record(tmp_path / "nog.npz", grav=False)
    ck = tmp_path / "m.pt"
    torch.manual_seed(3)
    torch.save({"perception_state_dict": {f"trnet.{k}": v for k, v in sp.TRNet().state_dict().items()}}, ck)
    args = type("A", (), dict(checkpoint=str(ck), train_dirs=str(tmp_path / "a.npz"), eval_dirs=str(tmp_path / "b.npz"), out=str(tmp_path / "o"), variants="ctrl,G",
                              weight=4.0, width=256, epochs=2, batch=3, lr=1e-3, geom_agg="max", geom_y_flip=False))()
    res = off.run(args, log=lambda *_: None)
    assert res["rows"]["G"]["geom"] is True and res["rows"]["ctrl"]["geom"] is False
    assert res["rows"]["G"]["load"]["new_keys"] == []                                      # 첫 층은 확장해 이어받음 (새 키 없음)
    assert res["checkpoint_sha256"] == res["checkpoint_sha256_after"]
    args.train_dirs = str(tmp_path / "nog.npz")
    with pytest.raises(ValueError, match="grav"):
        off.run(args, log=lambda *_: None)
    args.variants = "ctrl"                                                                  # 기본 (G 없음) 은 grav 없는 옛 기록도 그대로 돈다
    assert "ctrl" in off.run(args, log=lambda *_: None)["rows"]
