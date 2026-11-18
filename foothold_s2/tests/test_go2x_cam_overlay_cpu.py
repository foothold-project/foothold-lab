"""실기 카메라 장착 덧대기 (eval/go2x_cam_overlay.py) CPU 시험: 기하 답 대조 · 재투영 · 가면 · stall · 가짜 env 에 붙이기 (Kit 없음)."""
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.eval import go2x_cam_overlay as ov
from foothold_s2.sensors import depth_aug

SIM, REAL = (0.25, 0.0, 0.12), (0.35, 0.0, 0.07)


def test_flat_ground_center_pixel_answers_A_0_723_B_0_637():
    a = ov.flat_ground_depth(SIM, 35.0, 0.30)
    b = ov.flat_ground_depth(REAL, 35.0, 0.30)
    assert float(a[30, 30]) == pytest.approx(0.723, abs=1e-3)
    assert float(b[30, 30]) == pytest.approx(0.637, abs=1e-3)


def test_reproject_real_view_back_to_sim_matches_A_on_filled_pixels():
    a = ov.flat_ground_depth(SIM, 35.0, 0.30)[None]
    b = ov.flat_ground_depth(REAL, 35.0, 0.30)[None]
    r = ov.reproject(b, REAL, 35.0, SIM, 35.0)
    filled = torch.isfinite(r[0]) & torch.isfinite(a[0])
    rows = torch.nonzero(filled.any(1)).flatten()
    assert 40 <= int(filled.any(1).sum()) <= 55                                  # 설계: 채워지는 행은 약 1~50 (아래 9 행이 빈다)
    assert not torch.isfinite(r[0, -9:]).all() or not filled[-9:].all()           # 아래 행은 실측 카메라가 못 본 바닥
    assert float((r[0] - a[0])[filled].abs().median()) < 0.01                    # 채운 화소 깊이 차 중앙값 1 cm 아래 (설계는 2~6 mm)
    assert abs(float(r[0, 30, 30]) - float(a[0, 30, 30])) < 0.01
    assert int(rows.min()) <= 2 and int(rows.max()) >= 45


def test_reproject_same_mount_is_identity_on_valid_pixels():
    a = ov.flat_ground_depth(SIM, 35.0, 0.30)[None]
    r = ov.reproject(a, SIM, 35.0, SIM, 35.0)
    both = torch.isfinite(a[0]) & torch.isfinite(r[0])
    assert float((r[0] - a[0])[both].abs().max()) < 2e-3 and both.float().mean() > 0.9


def test_reproject_keeps_the_nearest_point_per_pixel():
    d = torch.full((1, 60, 60), 1.0)
    d[0, 10:20, 10:20] = 0.5                                                      # 가까운 물체 앞이 뒤 배경보다 이겨야 한다
    r = ov.reproject(d, REAL, 35.0, SIM, 35.0)
    assert float(torch.nan_to_num(r, posinf=9.0).min()) < 0.7


def test_invalid_mask_fraction_and_dropout():
    g = torch.Generator().manual_seed(0)
    m = ov.invalid_mask(256, 0.11, 6, g)
    frac = float(m.float().mean())
    assert 0.09 < frac < 0.13, frac                                              # 문턱을 분위수로 잡아 평균 무효 비율이 11 % (고정 문턱 0.11 은 5 % 쯤이라 안 씀)
    assert float((depth_aug.smooth_noise(256, 60, 60, 6, torch.Generator().manual_seed(0)) < 0.11).float().mean()) < 0.07
    d = torch.full((4, 60, 60), 1.0)
    out = ov.apply_invalid(d, torch.zeros(4, 60, 60, dtype=torch.bool), torch.tensor([True, False, False, True]))
    assert torch.isinf(out[0]).all() and torch.isinf(out[3]).all() and (out[1] == 1.0).all()
    assert float(depth_aug.normalize(out[0]).min()) == 1.0                        # 무효 = 미검출 = 정규화 1.0


def test_stall_clock_durations_and_records():
    c = ov.StallClock(64, 0.02, 2.0, (0.1, 1.0), torch.Generator().manual_seed(1))
    act = torch.stack([c.tick() for _ in range(500)])
    assert act.any() and c.records
    assert all(5 <= n <= 50 for _, _, n in c.records)                             # 0.1~1.0 s 를 0.02 s 스텝으로
    assert float(act.float().mean()) < 0.9


class FakeCam:
    def __init__(self, n):
        self._offset_pos = torch.zeros(n, 3); self._offset_quat = torch.tensor([[1.0, 0, 0, 0]]).repeat(n, 1); self.reset_ids = []
        self.data = SimpleNamespace(output={"distance_to_image_plane": ov.flat_ground_depth(SIM, 35.0, 0.30)[None, :, :, None].repeat(n, 1, 1, 1)})

    def reset(self, ids):
        self.reset_ids.append(ids.clone())


def _fake_env(n=4, jitter_on_reset=True):
    cam = FakeCam(n)
    cam._offset_pos[:] = torch.tensor(SIM); cam._offset_quat[:] = ov.pitch_quat(torch.full((n,), 35.0))
    term = SimpleNamespace(func=lambda env, sensor_cfg: torch.zeros(n, 3600))
    events = {"reset": [SimpleNamespace(func=randomize_topdown_camera)]}
    env = SimpleNamespace(device="cpu", num_envs=n, step_dt=0.02, scene=SimpleNamespace(sensors={"depth_cam": cam}),
                          observation_manager=SimpleNamespace(_group_obs_term_cfgs={"depth": [term]}, _group_obs_term_names={"depth": ["depth"]}),
                          event_manager=SimpleNamespace(_mode_term_cfgs=events))
    env.unwrapped = env
    return env, cam, term, events


def randomize_topdown_camera(env, env_ids):                                                      # tasks/s2_23f_camera.randomize_topdown_camera 흉내: 리셋 때 장착을 시뮬 값 + 흔들림으로 되쓴다
    cam = env.scene.sensors["depth_cam"]
    ids = torch.as_tensor(env_ids, dtype=torch.long)
    cam._offset_pos[ids] = torch.tensor(SIM) + 0.005
    cam._offset_quat[ids] = ov.pitch_quat(torch.full((len(ids),), 35.5))


def test_B_moves_camera_to_real_mount_and_survives_a_reset_event(capsys):
    env, cam, term, events = _fake_env()
    o = ov.install(env, ov.OverlayCfg(variant="B"))
    assert torch.allclose(cam._offset_pos, torch.tensor(REAL).expand(4, 3), atol=1e-6)
    events["reset"][0].func(env, torch.tensor([1, 2]))                            # 리셋 이벤트가 흔든 뒤에도 실측 장착으로 돌아와야 한다
    assert torch.allclose(cam._offset_pos, torch.tensor(REAL).expand(4, 3), atol=1e-6)
    assert float(cam._offset_quat[1, 2]) == pytest.approx(float(ov.pitch_quat(torch.tensor([35.0]))[0, 2]), abs=1e-6)
    out = term.func(env, SimpleNamespace(name="depth_cam"))
    assert out.shape == (4, 3600)
    assert "GO2X_CAM_OFFSET_READBACK variant=B" in capsys.readouterr().out and cam.reset_ids


def test_readback_raises_when_the_buffers_were_not_reached():
    env, cam, term, events = _fake_env()
    o = ov.install(env, ov.OverlayCfg(variant="B"))
    cam._offset_pos[:] = torch.tensor(SIM)                                        # 덧댄 뒤 누군가 되돌림 = 덧대기가 안 걸린 것
    with pytest.raises(RuntimeError, match="MISMATCH"):
        term.func(env, SimpleNamespace(name="depth_cam"))


def test_A_is_untouched_but_prints_the_readback(capsys):
    env, cam, term, events = _fake_env()
    before = (cam._offset_pos.clone(), cam._offset_quat.clone())
    o = ov.install(env, ov.OverlayCfg(variant="A"))
    out = term.func(env, SimpleNamespace(name="depth_cam"))
    assert torch.equal(cam._offset_pos, before[0]) and torch.equal(cam._offset_quat, before[1]) and (out == 0).all()
    assert "variant=A" in capsys.readouterr().out and not cam.reset_ids


def test_D_samples_per_env_mounts_in_range():
    env, cam, term, events = _fake_env(n=64)
    o = ov.install(env, ov.OverlayCfg.from_env({"GO2X_CAM_VARIANT": "D", "GO2X_CAM_SEED": "3"}))
    x, z = cam._offset_pos[:, 0], cam._offset_pos[:, 2]
    assert (x >= 0.25).all() and (x <= 0.35).all() and (z >= 0.07).all() and (z <= 0.12).all() and float(x.std()) > 0.01
    pitch = torch.rad2deg(2 * torch.atan2(cam._offset_quat[:, 2], cam._offset_quat[:, 0]))
    assert (pitch >= 34.0 - 1e-3).all() and (pitch <= 36.0 + 1e-3).all() and float(pitch.std()) > 0.1


def test_depth_stall_holds_the_last_frame():
    env, cam, term, events = _fake_env(n=8)
    o = ov.install(env, ov.OverlayCfg(variant="B", stall="depth", stall_rate=50.0, stall_s=(0.1, 0.1), seed=0))
    first = term.func(env, SimpleNamespace(name="depth_cam"))
    cam.data.output["distance_to_image_plane"] = cam.data.output["distance_to_image_plane"] * 0.5      # 장면이 바뀜
    held = 0
    for _ in range(3):
        out = term.func(env, SimpleNamespace(name="depth_cam"))
        held += int(torch.isclose(out, first).all(1).sum())
    assert held > 0 and o.clock.records


def test_obs_stall_freezes_observation_and_repeats_the_last_action():
    env, cam, term, events = _fake_env(n=4)
    calls = []

    def raw_step(action):
        calls.append(action.clone())
        return {"policy": torch.full((4, 2), float(len(calls)))}, torch.zeros(4), torch.zeros(4), torch.zeros(4), {}
    env.step = raw_step
    o = ov.install(env, ov.OverlayCfg(variant="B", stall="obs", stall_rate=1000.0, stall_s=(0.1, 0.1), seed=0))
    a0 = torch.zeros(4, 12)
    obs0 = env.step(a0)[0]["policy"]
    obs1 = env.step(torch.ones(4, 12))[0]["policy"]
    assert (torch.stack(calls)[1] == 0).all()                                     # 정책이 낸 1 은 버려지고 마지막 행동 0 이 들어감 (전 env stall)
    assert torch.equal(obs1, obs0)                                                # 관측은 얼려서 돌려줌 (첫 스텝은 얼릴 값이 없어 그대로)
    assert o.stall_obs_active_log and len(o.action_log) == 2


def test_config_from_env_validates():
    with pytest.raises(ValueError):
        ov.OverlayCfg.from_env({"GO2X_CAM_VARIANT": "Z"})
    with pytest.raises(ValueError):
        ov.OverlayCfg.from_env({"GO2X_CAM_STALL": "x"})
    c = ov.OverlayCfg.from_env({"GO2X_CAM_VARIANT": "C"})
    assert c.masks and c.dropout_p == 0.03 and c.stall == "none"


def test_dump_records_mounts_stalls_actions(tmp_path):
    import numpy as np

    env, cam, term, events = _fake_env(n=4)
    env.step = lambda a: ({"policy": torch.zeros(4, 2)}, torch.zeros(4), torch.zeros(4), torch.zeros(4), {})
    o = ov.install(env, ov.OverlayCfg(variant="D", stall="obs", stall_rate=50.0, seed=2, record_path=str(tmp_path / "r.npz")))
    for _ in range(5):
        env.step(torch.zeros(4, 12))
    path = o.dump()
    z = np.load(path)
    assert z["mount_pos"].shape == (4, 3) and z["actions_applied"].shape == (5, 4, 12) and z["stall_records_env_start_len"].shape[1] == 3
