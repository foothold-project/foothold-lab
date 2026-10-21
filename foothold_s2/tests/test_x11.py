"""SONNET-X11 (EX-11 · EX-12) CPU 시험: est mask · clean critic 664 · 행동 포화 기록 · X6 KL · 항별 보상 분할 · manifest · 실행 무효.

Kit 없이 가짜 env(start_fake_env) 로 runner 배선을 본다. 답을 아는 입력을 쓴다.
"""

import json
import os
import re
from types import SimpleNamespace

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.commands import mixed_core as mc
from foothold_s2.eval.adapters import S2Policy
from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY
from foothold_s2.runners import kl_probe
from foothold_s2.runners import manifest as mf
from foothold_s2.runners.action_stats import ActionStats, phys_probe
from foothold_s2.runners.reward_split import split_stats
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _runner(seed=0, n=8, T=24, **pc):
    torch.manual_seed(seed)
    p = {"microbatch_envs": 4, "map_input": "none"}
    p.update(pc)

    return StartRunner(FakeStartEnv(num_envs=n, seed=seed), train_cfg(T, p), log_dir=None, device="cpu")


def _collect(r):
    """learn() 의 수집(①)만 돌리고 PPO update 직전에 멈춰 저장 버퍼를 돌려준다."""
    out = {}
    orig = r.alg.update

    def stop():
        out["obs"] = r.alg.storage.observations.clone()
        raise StopIteration

    r.alg.update = stop

    try:
        r.learn(1)
    except StopIteration:
        pass

    r.alg.update = orig

    return out


# ------------------------------------------------------------------ X2 est mask
def test_est_zero_masks_actor_tail_but_perception_still_runs():
    r = _runner(est_mode="zero")
    c = _collect(r)
    actor = c["obs"][ACTOR_KEY]

    assert actor.shape[-1] == 96
    assert float(actor[..., 45:].abs().max()) == 0.0                 # 저장된 actor 입력의 est 51 칸이 0
    assert float(actor[..., :45].abs().max()) > 0.0                  # o45 는 그대로(잡음 포함 관측)
    assert float(r.pstate.h_prop.abs().max()) > 0.0                  # 지각 GRU 는 그대로 돈다
    assert r.replay.full()                                           # 재생 버퍼도 찼다
    loss = r.update_perception()                                     # 감독 갱신이 돌고 값이 유한하다
    assert loss["l_ie"] > 0 and all(v == v for v in loss.values())


def test_est_learned_keeps_tail_nonzero():
    r = _runner(est_mode="learned")
    actor = _collect(r)["obs"][ACTOR_KEY]

    assert float(actor[..., 45:].abs().max()) > 0.0


def test_one_function_feeds_rollout_bootstrap_and_eval():
    """수집 · 부트스트랩 · 평가 adapter 가 모두 _ppo_obs 를 지난다: est 에 5 를 넣어도 zero 모드면 actor 의 est 칸은 0."""
    r = _runner(est_mode="zero")
    raw = r.env.get_observations()
    boot = r._ppo_obs(raw, torch.full((8, 51), 5.0))
    assert float(boot[ACTOR_KEY][:, 45:].abs().max()) == 0.0

    seen = {}
    orig = r.alg.policy.act_inference
    r.alg.policy.act_inference = lambda od: (seen.setdefault("a", od[ACTOR_KEY].clone()), orig(od))[1]
    pol = S2Policy(r, 8, z_mode="mean", act_mode="mean")
    pol(raw)

    assert float(seen["a"][:, 45:].abs().max()) == 0.0               # 평가 adapter 도 같은 mask
    assert float(pol.last_est.abs().max()) > 0.0                     # 지각 est 자체는 계산됐다(actor 에만 안 들어감)

    r2 = _runner(est_mode="learned")
    seen2 = {}
    orig2 = r2.alg.policy.act_inference
    r2.alg.policy.act_inference = lambda od: (seen2.setdefault("a", od[ACTOR_KEY].clone()), orig2(od))[1]
    S2Policy(r2, 8, z_mode="mean", act_mode="mean")(r2.env.get_observations())

    assert float(seen2["a"][:, 45:].abs().max()) > 0.0


def test_bad_modes_rejected():
    with pytest.raises(ValueError):
        _runner(est_mode="half")

    with pytest.raises(ValueError):
        _runner(critic_mode="noisy")


# ------------------------------------------------------------------ 공통 계약 3: clean critic 664
class _SentinelEnv(FakeStartEnv):
    """policy(잡음 섞임) · critic(clean) · base_vel · contacts · gt_map · gt_feet 이 서로 다른 상수 자리표(sentinel)를 가진다."""

    def _make(self):
        td = super()._make()
        n = self.num_envs
        td["policy"] = torch.full((n, 45), 1.0)
        td["critic"] = torch.cat([torch.full((n, 45), 2.0), torch.full((n, 3), 3.0), torch.full((n, 4), 4.0)], -1)
        td["base_vel"] = torch.full((n, 3), 5.0)
        td["contacts"] = torch.full((n, 4), 6.0)
        td["gt_map"] = torch.full((n, 512), 7.0)
        td["gt_feet"] = torch.full((n, 100), 8.0)

        return td


def _sentinel_runner(mode):
    torch.manual_seed(0)

    return StartRunner(_SentinelEnv(num_envs=8, seed=0), train_cfg(24, {"microbatch_envs": 4, "map_input": "none", "critic_mode": mode}), log_dir=None, device="cpu")


def test_clean52_critic_is_664_without_duplicates():
    r = _sentinel_runner("clean52")
    c = r._ppo_obs(r.env.get_observations(), torch.zeros(8, 51))[CRITIC_KEY]

    assert c.shape == (8, 664)
    assert torch.all(c[:, :45] == 2.0)                               # clean o45 (actor 의 잡음 섞인 1.0 이 아니다)
    assert torch.all(c[:, 45:48] == 3.0) and torch.all(c[:, 48:52] == 4.0)   # clean 안의 vel3 · contact4
    assert torch.all(c[:, 52:564] == 7.0) and torch.all(c[:, 564:664] == 8.0)
    assert not bool((c == 5.0).any()) and not bool((c == 6.0).any())  # 별도 base_vel · contacts 묶음을 또 붙이지 않았다(중복 없음)
    assert not bool((c == 1.0).any())                                # 잡음 섞인 policy 값이 critic 에 안 들어갔다


def test_legacy_critic_unchanged():
    r = _sentinel_runner("legacy")
    c = r._ppo_obs(r.env.get_observations(), torch.zeros(8, 51))[CRITIC_KEY]

    assert c.shape == (8, 664)
    assert torch.all(c[:, :45] == 1.0) and torch.all(c[:, 45:48] == 5.0) and torch.all(c[:, 48:52] == 6.0)


def test_clean52_requires_critic_group():
    class NoCritic(FakeStartEnv):
        def _make(self):
            td = super()._make()
            del td["critic"]

            return td

    with pytest.raises(KeyError):
        StartRunner(NoCritic(num_envs=8), train_cfg(24, {"microbatch_envs": 4, "map_input": "none", "critic_mode": "clean52"}), log_dir=None, device="cpu")


def test_runner_never_recomputes_observations():
    """관측 매니저를 다시 불러 clean 값을 만들면 잡음 표본 · 센서 시점이 바뀐다: 소스에 그 호출이 없어야 한다."""
    src = open(os.path.join(REPO, "foothold_s2", "runners", "start_runner.py"), encoding="utf-8").read()

    assert "observation_manager" not in src and "compute_group" not in src


def test_same_initial_state_regardless_of_est_mode_and_differs_by_seed():
    a, b, c = _runner(seed=0, est_mode="zero"), _runner(seed=0, est_mode="learned"), _runner(seed=1, est_mode="learned")

    def shas(r):
        pol = r.alg.policy.state_dict()
        return (mf.state_sha({k: v for k, v in pol.items() if k.startswith("actor") or k == "std"}),
                mf.state_sha({k: v for k, v in pol.items() if k.startswith("critic")}),
                mf.state_sha(r.alg.optimizer.state_dict()), mf.state_sha(r.perception.state_dict()))

    assert shas(a) == shas(b)
    assert shas(a)[0] != shas(c)[0] and shas(a)[1] != shas(c)[1]


# ------------------------------------------------------------------ X5 행동 포화 기록
def test_action_stats_known_answer():
    st = ActionStats(clip=2.0, num_envs=2, num_joints=3)
    # 스텝 0: env0 관절0 = 3(포화) · 나머지 1 / env1 전부 1
    # 스텝 1: env0 관절0 = -3(포화, 연속 2) · env1 관절2 = 5(포화)
    # 스텝 2: env0 관절0 = 0 (연속 끊김) · env1 전부 0.5, env1 이 끝남
    steps = [torch.tensor([[3.0, 1.0, 1.0], [1.0, 1.0, 1.0]]), torch.tensor([[-3.0, 1.0, 1.0], [1.0, 1.0, 5.0]]), torch.tensor([[0.0, 1.0, 1.0], [0.5, 0.5, 0.5]])]
    dones = [torch.tensor([False, False]), torch.tensor([False, False]), torch.tensor([False, True])]

    for a, d in zip(steps, dones):
        st.add(a, d)

    s = st.summary()

    assert s["element_saturation_rate"] == pytest.approx(3 / 18)
    assert s["any_joint_saturated_env_step_frac"] == pytest.approx(3 / 6)        # (스텝0 env0)(스텝1 env0)(스텝1 env1)
    assert s["max_consecutive_saturation_steps_by_joint"] == [2, 0, 1]
    assert s["raw_abs_max"] == 5.0 and s["exec_abs_max"] == 2.0                  # clip 뒤는 2 로 잘림
    assert s["raw_abs_p50_p99_p999"][1] > s["exec_abs_p50_p99_p999"][1]


def test_phys_probe_with_fake_robot():
    data = SimpleNamespace(joint_pos_target=torch.tensor([[0.0, 2.0], [-2.0, 0.5]]), joint_pos_limits=torch.tensor([[[-1.0, 1.0], [-1.0, 1.0]]] * 2),
                           computed_torque=torch.tensor([[10.0, 30.0], [5.0, 5.0]]), applied_torque=torch.tensor([[10.0, 23.5], [5.0, 5.0]]))
    env = SimpleNamespace(scene={"robot": SimpleNamespace(data=data)})
    p = phys_probe(env)

    assert p["target_out_of_limit_frac"] == pytest.approx(2 / 4)
    assert p["torque_clipped_frac"] == pytest.approx(1 / 4)
    assert phys_probe(SimpleNamespace(scene={}))["target_out_of_limit_frac"] is None      # 속성이 없으면 None


# ------------------------------------------------------------------ X6 KL
def test_gaussian_kl_known_answers():
    z = torch.zeros(5, 12)
    o = torch.ones(5, 12)

    assert float(kl_probe.gaussian_kl(z, o, z, o).abs().max()) == 0.0
    assert float(kl_probe.gaussian_kl(z, o, o, o)[0]) == pytest.approx(0.5 * 12)                # 평균 1 이동, std 1: 차원당 0.5
    import math
    assert float(kl_probe.gaussian_kl(z, o, z, 2 * o)[0]) == pytest.approx((math.log(2) + 1 / 8 - 0.5) * 12)


def test_command_branch_and_summary():
    cmd = torch.tensor([[0.5, 0, 0], [0.0, 0, 1.2], [0.0, 0, 0.0], [1.0, 0, 0]])
    br = kl_probe.command_branch(cmd)

    assert br.tolist() == [0, 1, 2, 0]
    s = kl_probe.summarize(torch.tensor([1.0, 2.0, 3.0, 5.0]), br)
    assert s["walk"]["mean"] == 3.0 and s["spin"]["mean"] == 2.0 and s["stand"]["n"] == 1 and s["all"]["max"] == 5.0


def test_runner_kl_probe_phi_zero_when_est_masked_and_positive_when_learned(tmp_path):
    for mode, expect_positive in (("zero", False), ("learned", True)):
        r = _runner(est_mode=mode, log_kl=True, log_action_stats=True, kl_probe_envs=8)
        r.log_dir = str(tmp_path / mode)
        os.makedirs(r.log_dir, exist_ok=True)
        r.learn(1)
        rec = json.loads(open(os.path.join(r.log_dir, "train_extra.jsonl"), encoding="utf-8").read().splitlines()[-1])
        kl = rec["kl_probe"]

        assert kl["ppo"]["all"]["mean"] > 0                                           # PPO update 는 theta 를 바꾼다
        assert set(kl["ppo"]) >= {"all", "walk", "spin", "stand"}

        if expect_positive:
            assert kl["phi"]["all"]["mean"] > 0
        else:
            assert kl["phi"]["all"]["max"] == 0.0                                     # est 가 가려져 있으면 phi 전후 KL 은 정확히 0

        assert rec["action_stats"]["raw_abs_max"] > 0


def test_phi_kl_is_zero_without_phi_update_same_history_hidden_epsilon():
    r = _runner(est_mode="learned", log_kl=True, kl_probe_envs=8)
    _collect(r)
    snap = r._kl_phi_before(0)
    res = r._kl_phi_after(snap)                                                       # update_perception 을 부르지 않았다 -> 같은 입력 · 같은 eps 라 0

    assert res["all"]["max"] == 0.0


# ------------------------------------------------------------------ 항별 보상 분할 (lead 요청)
def test_reward_split_known_answer_half_moving_half_stalled():
    T, N = 24, 8
    names = ["track_lin_vel", "track_ang_vel", "action_rate", "action_smoothness", "joint_torques", "flat_orientation"]
    rew = torch.zeros(T, N, 6)
    cmd = torch.zeros(T, N, 3)
    vx = torch.zeros(T, N)
    wz = torch.zeros(T, N)
    # env 0~1: 직진 명령 0.5, 실제 0.4 (움직임) / env 2~3: 직진 0.5, 실제 0.01 (멈춤)
    # env 4: 회전 +1.2, 실제 +1.0 (움직임) / env 5: 회전 -1.2, 실제 잡음만(부호 번갈아, 평균 0) (멈춤: |요| 는 크지만 추종 비율 0)
    # env 6~7: 명령 0 (어느 집단도 아님)
    cmd[:, 0:4, 0] = 0.5
    vx[:, 0:2] = 0.4
    vx[:, 2:4] = 0.01
    cmd[:, 4, 2] = 1.2
    wz[:, 4] = 1.0
    cmd[:, 5, 2] = -1.2
    wz[:, 5] = torch.tensor([1.0, -1.0] * 12)
    moving, stalled = [0, 1, 4], [2, 3, 5]
    rew[:, moving, 0] = 1.0                          # track_lin: 움직임 1.0
    rew[:, stalled, 0] = 0.4
    rew[:, moving, 2] = -0.5                         # action_rate
    rew[:, stalled, 2] = -2.0
    rew[:, moving, 3] = -0.25                        # smoothness
    rew[:, stalled, 3] = -1.0
    rew[:, moving, 4] = -0.1                         # 나머지 벌점(joint_torques)
    rew[:, stalled, 4] = -0.3
    rew[:, moving, 5] = -0.1
    rew[:, stalled, 5] = -0.2
    out = split_stats(rew, names, vx, wz, cmd)

    assert out["frac_moving"] == pytest.approx(3 / 8) and out["frac_stalled"] == pytest.approx(3 / 8) and out["frac_no_move_command"] == pytest.approx(2 / 8)
    m, s = out["moving"], out["stalled"]
    assert m["env_steps"] == 3 * 24 and s["env_steps"] == 3 * 24
    assert m["track_lin_vel"] == pytest.approx(1.0) and s["track_lin_vel"] == pytest.approx(0.4)
    assert m["action_rate"] == pytest.approx(-0.5) and s["action_rate"] == pytest.approx(-2.0)
    assert m["action_smoothness"] == pytest.approx(-0.25) and s["action_smoothness"] == pytest.approx(-1.0)
    assert m["other_penalty_sum"] == pytest.approx(-0.2) and s["other_penalty_sum"] == pytest.approx(-0.5)
    assert m["total"] == pytest.approx(1.0 - 0.5 - 0.25 - 0.2) and s["total"] == pytest.approx(0.4 - 2.0 - 1.0 - 0.5)


# ------------------------------------------------------------------ 실행 무효 · manifest
def test_nonfinite_stops_the_run(tmp_path):
    class NanEnv(FakeStartEnv):
        def step(self, actions):
            obs, rew, dones, extras = super().step(actions)
            rew[0] = float("nan")

            return obs, rew, dones, extras

    torch.manual_seed(0)
    r = StartRunner(NanEnv(num_envs=8), train_cfg(24, {"microbatch_envs": 4, "map_input": "none", "stop_on_nonfinite": True}), log_dir=str(tmp_path), device="cpu")

    with pytest.raises(RuntimeError, match="NaN/Inf"):
        r.learn(1)

    assert json.load(open(os.path.join(str(tmp_path), "train_start_status.json"), encoding="utf-8"))["invalid_run"] is True


def test_manifest_progress_checkpoint_sha_and_code_change_guard(tmp_path, monkeypatch):
    r = _runner()
    r.log_dir = str(tmp_path)
    m = mf.build_manifest(repo=REPO, log_dir=str(tmp_path), run_name="t", cli_args={"seed": 1, "api_key": "SECRET"}, modes={"est_mode": "learned"}, runner=r)
    mf.write_manifest(str(tmp_path), m)
    r.attach_manifest(str(tmp_path), m)

    assert "api_key" not in m["run"]["cli_args"]                                       # 비밀값 이름은 뺀다
    assert set(m["initial_state_sha256"]) == {"actor", "critic", "ppo_optimizer", "perception", "perception_optimizer"}
    assert any(k.startswith("foothold_s2.runners") for k in m["files"]["imported_sha256"])

    r.save(os.path.join(str(tmp_path), "model_0.pt"))
    r._manifest_checkpoint(0, "model_0.pt", 8)
    saved = json.load(open(os.path.join(str(tmp_path), "manifest.json"), encoding="utf-8"))

    assert saved["progress"] == {"completed_updates": 1, "total_env_steps": 1 * 24 * 8}
    assert saved["checkpoints"]["model_0.pt"] == mf.sha256_file(os.path.join(str(tmp_path), "model_0.pt"))

    victim = next(iter(m["files"]["imported_sha256"]))
    real = mf.imported_files
    monkeypatch.setattr(mf, "imported_files", lambda *a, **k: {**real(), victim: "0" * 64})

    with pytest.raises(RuntimeError, match="소비 코드가 바뀜"):
        r._manifest_checkpoint(1, "model_0.pt", 8)


def test_manifest_diff_only_est_mode_and_run_name_allowed(tmp_path):
    ra, rb = _runner(seed=0, est_mode="zero"), _runner(seed=0, est_mode="learned")
    args = {"seed": 42, "task": "X11"}
    ma = mf.build_manifest(repo=REPO, log_dir=str(tmp_path / "a"), run_name="ex11", cli_args={**args, "run_name": "ex11", "hydra_args": ["agent.perception.est_mode=zero"]},
                           modes={"est_mode": "zero", "clip_actions": 17.0, "critic_mode": "clean52"}, runner=ra)
    mb = mf.build_manifest(repo=REPO, log_dir=str(tmp_path / "b"), run_name="ex12", cli_args={**args, "run_name": "ex12", "hydra_args": []},
                           modes={"est_mode": "learned", "clip_actions": 17.0, "critic_mode": "clean52"}, runner=rb)
    d = mf.diff_manifests(ma, mb)

    assert d["ok"], d["unexpected_differences"]
    assert "modes.est_mode" in d["allowed_differences"] and "run.name" in d["allowed_differences"]

    mb["modes"]["clip_actions"] = 100.0
    bad = mf.diff_manifests(ma, mb)
    assert not bad["ok"] and "modes.clip_actions" in bad["unexpected_differences"]

    mb["modes"]["clip_actions"] = 17.0
    mb["initial_state_sha256"]["actor"] = "x"
    assert "initial_state_sha256.actor" in mf.diff_manifests(ma, mb)["unexpected_differences"]

    pa, pb = tmp_path / "ma.json", tmp_path / "mb.json"
    pa.write_text(json.dumps(ma), encoding="utf-8")
    pb.write_text(json.dumps(mb), encoding="utf-8")
    assert mf.main([str(pa), str(pb)]) == 1                                            # 허용 밖 차이가 있으면 종료 코드 1


# ------------------------------------------------------------------ X1 지형 · 명령 계약 (Kit 없이: 소스 · 순수 함수)
def _src(rel):
    return open(os.path.join(REPO, rel), encoding="utf-8").read()


def test_x11_env_cfg_keeps_s1_terrain_and_start_command():
    src = _src("foothold_s2/tasks/s2_env_cfg.py")
    body = src[src.index("class FootholdS2X11EnvCfg"):]

    assert "FootholdS2DiagG0StartEnvCfg" in body.split(":", 1)[0]                      # START 명령(start_mode · 깃발 없음)을 그대로 상속
    assert re.search(r"def use_full_terrain\(self\):\s+return None", body)             # 50 열 생성기 · sparse · 깃발 공급자를 쓰지 않는다
    assert "apply_full_terrain_and_flags" not in body and "terrain_levels_s2" not in body and "terrain_generator" not in body
    s1 = _src("foothold_s2/tasks/s1_env_cfg.py")

    assert "terrain_generator=s1a_generator()" in s1 and "max_init_terrain_level=2" in s1       # 상속하는 S1 장면: 이어진 7종 · 23 열 · 초기 레벨
    assert "terrain_levels = CurrTerm(func=tlm.terrain_levels_mixed)" in s1             # S1 승급 · 강등 규칙


def test_x11_task_registration_uses_plain_env_without_side_table():
    import gymnasium as gym

    import foothold_s2.tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-X11-v0")

    assert spec.entry_point == "isaaclab.envs:ManagerBasedRLEnv"                       # FootholdS2Env 가 아니라 side table 을 붙이지 않는다
    assert spec.kwargs["env_cfg_entry_point"].endswith("FootholdS2X11EnvCfg")
    assert spec.kwargs["rsl_rl_cfg_entry_point"].endswith("S2X11PPORunnerCfg")
    agent_src = _src("foothold_s2/tasks/agents/s2_ppo_cfg.py")
    body = agent_src[agent_src.index("class S2X11PPORunnerCfg"):]

    assert "max_iterations = 1501" in body and "save_interval = 500" in body and '"critic_mode": "clean52"' in body
    assert '"est_mode": "learned"' in body and '"contract": "start"' in body
    from foothold_s2.terrains import columns

    assert columns.CONTINUOUS_COLS == 23


def test_start_branch_ignores_range_curriculum_vmax():
    """범위 커리큘럼이 vmax 를 올려도 START 명령 분포는 그대로(같은 난수열이면 같은 명령)."""
    params = mc.CommandParams(start_mode=True)

    def draw(vmax):
        g = torch.Generator().manual_seed(7)

        return mc.resample_free_modes(g, 4096, params, 100000, vmax, vmax)["cmd"]

    a, b = draw(1.0), draw(3.0)

    assert torch.equal(a, b)
    assert float(a[:, 0].max()) <= 1.5 + 1e-6 and float(a[:, 1].abs().max()) == 0.0
    walk = a[:, 0] > 0
    assert float(a[walk, 0].min()) >= 0.3 - 1e-6 and float(a[walk, 2].abs().max()) == 0.0            # 걷는 가지는 wz 0, vx >= 0.3
    assert float(a[~walk, 2].abs().max()) <= 1.2 + 1e-6 and float(a[~walk, 2].abs().max()) > 0.5
