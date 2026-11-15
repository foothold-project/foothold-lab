"""SONNET-X17: EX-17 (EX-16 + 몸통 접촉 종료) · EX-18 (EX-16 + est_mode=oracle_vel) CPU 시험.

EX-17 은 구성 대조(AST) + v2 실행 기록 env.yaml 과의 일치, EX-18 은 가짜 env 의 StartRunner 로 «앞 3 칸에만 실제 속도» 를 수집 · 저장 · 부트스트랩 · 평가 adapter 경로에서 확인한다.
"""

import ast
import os

import pytest
import torch

from foothold_s2.eval.adapters import S2Policy, load_s2_runner
from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY
from foothold_s2.runners.manifest import yaml_flat
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V2_YAML = "C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/params/env.yaml"


def _src(rel):
    return open(os.path.join(REPO, rel), encoding="utf-8").read()


def _runner(seed=0, n=8, T=24, log_dir=None, **pc):
    torch.manual_seed(seed)
    p = {"microbatch_envs": 4, "map_input": "none"}
    p.update(pc)

    return StartRunner(FakeStartEnv(num_envs=n, seed=seed), train_cfg(T, p), log_dir=log_dir, device="cpu")


def _post_init_targets(src, cls):
    tree = ast.parse(src)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    post = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__post_init__")

    return [ast.unparse(a.targets[0]) for a in ast.walk(post) if isinstance(a, ast.Assign)], node


# ------------------------------------------------------------------ EX-17
def test_x17_differs_from_x16n_only_by_base_contact_termination():
    src = _src("foothold_s2/tasks/s2_x17_cfg.py")
    targets, node = _post_init_targets(src, "FootholdS2X17EnvCfg")

    assert [ast.unparse(b) for b in node.bases] == ["FootholdS2X16nEnvCfg"]
    assert targets == ["self.terminations.base_contact"]                                   # 바꾸는 것은 이 한 줄뿐(기존 종료 time_out · bad_orientation · foot_below_ground 는 상속 그대로)
    body = src.split('"""', 2)[2]

    assert "rewards" not in body and "commands" not in body and "observations" not in body and "curriculum" not in body


def test_x17_base_contact_equals_v2_env_yaml():
    src = _src("foothold_s2/tasks/s2_x17_cfg.py")
    call = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and ast.unparse(n.func) == "DoneTerm")
    kw = {k.arg: k.value for k in call.keywords}
    params = kw["params"]
    sensor = next(n for n in ast.walk(params) if isinstance(n, ast.Call) and ast.unparse(n.func) == "SceneEntityCfg")
    threshold = ast.literal_eval(next(v for k, v in zip(params.keys, params.values) if ast.literal_eval(k) == "threshold"))

    assert ast.unparse(kw["func"]) == "mdp.illegal_contact" and "time_out" not in {k.arg for k in call.keywords}          # time_out 기본 False
    assert ast.literal_eval(sensor.args[0]) == "contact_forces" and ast.literal_eval(next(k.value for k in sensor.keywords if k.arg == "body_names")) == "base" and threshold == 1.0

    if os.path.exists(V2_YAML):
        ref = yaml_flat(V2_YAML)

        assert ref["terminations.base_contact.func"].endswith(":illegal_contact")
        assert ref["terminations.base_contact.params.sensor_cfg.name"] == "contact_forces"
        assert ref["terminations.base_contact.params.sensor_cfg.body_names"] == "base"
        assert float(ref["terminations.base_contact.params.threshold"]) == 1.0 and ref["terminations.base_contact.time_out"] == "False"


def test_existing_terminations_are_kept_and_x17_registration():
    s1 = _src("foothold_s2/tasks/s1_env_cfg.py")

    for name in ("time_out = DoneTerm", "bad_orientation = DoneTerm", "foot_below_ground = DoneTerm"):
        assert name in s1
    import gymnasium as gym

    import foothold_s2.x17_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-X17-v0")

    assert spec.entry_point == "isaaclab.envs:ManagerBasedRLEnv"
    assert spec.kwargs["env_cfg_entry_point"].endswith("s2_x17_cfg:FootholdS2X17EnvCfg") and spec.kwargs["rsl_rl_cfg_entry_point"].endswith("s2_x17_ppo_cfg:S2X17PPORunnerCfg")
    agent = _src("foothold_s2/tasks/agents/s2_x17_ppo_cfg.py")

    assert "S2X16nPPORunnerCfg" in agent and "max_iterations = 301" in agent and "save_interval = 50" in agent and 'experiment_name = "foothold_s2_x17"' in agent
    run = _src("foothold_s2/run_s2_x17.sh")

    assert "FootholdS2-Go2-S2-X17-v0" in run and "ex17-basecontact" in run and "--max_iterations 301" in run and "--num_envs 3072" in run and "--seed 42" in run


# ------------------------------------------------------------------ EX-18
def test_oracle_vel_puts_the_real_velocity_only_in_the_first_three_slots():
    r = _runner(est_mode="oracle_vel", oracle_vel_noise=0.0)
    raw = r.env.get_observations()
    obs = r._ppo_obs(raw, torch.full((8, 51), 5.0))                                            # est 를 5 로 채워도 무시된다
    tail = obs[ACTOR_KEY][:, 45:]

    assert torch.equal(tail[:, :3], raw["base_vel"])                                           # 앞 3 칸 = env 의 실제 base_lin_vel (잡음 0 이면 정확히 같음)
    assert float(tail[:, 3:].abs().max()) == 0.0 and tail.shape[1] == 51                       # 나머지 48 칸 0
    assert torch.equal(obs[ACTOR_KEY][:, :45], raw["policy"])                                  # o45 는 그대로


def test_oracle_vel_noise_is_uniform_within_the_bound():
    r = _runner(est_mode="oracle_vel", oracle_vel_noise=0.1)
    vel = torch.zeros(40000, 3)
    out = r._est_in(torch.zeros(40000, 51), vel)[:, :3]

    assert float(out.min()) >= -0.1 and float(out.max()) <= 0.1
    assert float(out.std()) == pytest.approx(0.1 / 3 ** 0.5, rel=0.03) and abs(float(out.mean())) < 0.002          # 균일 ±0.1 의 표준편차 0.0577
    assert float(r._est_in(torch.zeros(5, 51), torch.ones(5, 3), noise=0.0)[:, :3].min()) == 1.0                    # noise=0 이면 잡음 없음


def test_oracle_vel_collection_storage_bootstrap_and_critic_unchanged():
    r = _runner(est_mode="oracle_vel", critic_mode="clean52")
    stored = {}
    orig = r.alg.update

    def stop():
        stored["obs"] = r.alg.storage.observations.clone()
        raise StopIteration

    r.alg.update = stop

    try:
        r.learn(1)
    except StopIteration:
        pass

    r.alg.update = orig
    actor = stored["obs"][ACTOR_KEY]

    assert float(actor[..., 48:].abs().max()) == 0.0 and float(actor[..., 45:48].abs().max()) > 0.0                # 저장된 입력: 앞 3 칸만 값
    assert float(r.pstate.h_prop.abs().max()) > 0.0 and r.replay.full()                                           # 지각은 그대로 돌고 재생 버퍼도 찼다
    raw = r.env.get_observations()
    a = r._ppo_obs(raw, torch.zeros(8, 51))
    b = _runner(est_mode="learned", critic_mode="clean52")._ppo_obs(raw, torch.zeros(8, 51))

    assert torch.equal(a[CRITIC_KEY], b[CRITIC_KEY])                                                              # critic 은 est 모드와 무관하게 그대로
    assert float(a[ACTOR_KEY][:, 48:].abs().max()) == 0.0                                                         # 부트스트랩 호출 모양도 같은 함수


def test_checkpoint_restores_oracle_vel_and_eval_adapter_uses_the_same_input(tmp_path):
    r = _runner(est_mode="oracle_vel", oracle_vel_noise=0.1, critic_mode="clean52")
    ck = os.path.join(str(tmp_path), "m.pt")
    r.save(ck)
    env = FakeStartEnv(num_envs=8, seed=3)
    runner, sd = load_s2_runner(env, train_cfg(24, {"microbatch_envs": 4}), ck, "cpu")                            # 평가 쪽은 기본(learned · legacy)으로 시작

    assert runner.pcfg["est_mode"] == "oracle_vel" and runner.pcfg["critic_mode"] == "clean52" and runner.pcfg["oracle_vel_noise"] == 0.0
    seen = {}
    orig = runner.alg.policy.act_inference
    runner.alg.policy.act_inference = lambda od: (seen.setdefault("a", od[ACTOR_KEY].clone()), orig(od))[1]
    raw = env.get_observations()
    S2Policy(runner, 8, z_mode="mean", act_mode="mean")(raw)

    assert torch.equal(seen["a"][:, 45:48], raw["base_vel"]) and float(seen["a"][:, 48:].abs().max()) == 0.0           # 평가: 잡음 없이 실제 속도만 앞 3 칸
    with pytest.raises(ValueError, match="est_mode"):
        load_s2_runner(env, train_cfg(24, {"microbatch_envs": 4}), ck, "cpu", expect={"est_mode": "zero"})
    with pytest.raises(ValueError, match="est_mode"):
        _runner(est_mode="learned").load(ck)


def test_phi_kl_is_zero_in_oracle_mode(tmp_path):
    r = _runner(est_mode="oracle_vel", log_kl=True, kl_probe_envs=8, log_dir=str(tmp_path))
    r.learn(1)
    import json

    rec = json.loads(open(os.path.join(str(tmp_path), "train_extra.jsonl"), encoding="utf-8").read().splitlines()[-1])

    assert rec["kl_probe"]["ppo"]["all"]["mean"] > 0 and rec["kl_probe"]["phi"]["all"]["max"] == 0.0                # actor 가 phi 와 무관하다


def test_bad_est_mode_is_still_rejected():
    with pytest.raises(ValueError):
        _runner(est_mode="oracle")


def test_x18_differs_from_x16n_only_by_est_mode():
    src = _src("foothold_s2/tasks/agents/s2_x18_ppo_cfg.py")
    tree = ast.parse(src)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "S2X18PPORunnerCfg")

    assert [ast.unparse(b) for b in node.bases] == ["S2X16nPPORunnerCfg"]
    fields = {n.targets[0].id if isinstance(n, ast.Assign) else n.target.id: n.value for n in node.body if isinstance(n, (ast.Assign, ast.AnnAssign))}

    assert set(fields) == {"max_iterations", "save_interval", "experiment_name", "perception"}
    assert ast.literal_eval(fields["max_iterations"]) == 301 and ast.literal_eval(fields["save_interval"]) == 50 and ast.literal_eval(fields["experiment_name"]) == "foothold_s2_x18"
    ppo = _src("foothold_s2/tasks/agents/s2_ppo_cfg.py")
    base = ast.parse(ppo)
    x13 = next(n for n in base.body if isinstance(n, ast.ClassDef) and n.name == "S2X13PPORunnerCfg")
    base_perc = ast.literal_eval(next(n.value for n in x13.body if isinstance(n, ast.AnnAssign) and n.target.id == "perception"))
    perc = ast.literal_eval(fields["perception"])

    assert {k: v for k, v in perc.items() if k not in ("est_mode", "oracle_vel_noise")} == {k: v for k, v in base_perc.items() if k != "est_mode"}          # est 관련 두 칸만 다르다
    assert perc["est_mode"] == "oracle_vel" and perc["oracle_vel_noise"] == 0.1 and base_perc["est_mode"] == "zero"


def test_x18_registration_uses_ex16_env_and_run_script_and_manifest_mode():
    import gymnasium as gym

    import foothold_s2.x18_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-X18-v0")

    assert spec.entry_point == "isaaclab.envs:ManagerBasedRLEnv"
    assert spec.kwargs["env_cfg_entry_point"].endswith("s2_x16n_cfg:FootholdS2X16nEnvCfg")                       # 환경 · 보상 · 종료는 EX-16 그대로
    assert spec.kwargs["rsl_rl_cfg_entry_point"].endswith("s2_x18_ppo_cfg:S2X18PPORunnerCfg")
    run = _src("foothold_s2/run_s2_x18.sh")

    assert "FootholdS2-Go2-S2-X18-v0" in run and "ex18-oraclevel" in run and "--max_iterations 301" in run and "--num_envs 3072" in run and "--seed 42" in run
    ts = _src("foothold_s2/scripts/train_start.py")

    assert "import foothold_s2.x17_tasks" in ts and "import foothold_s2.x18_tasks" in ts and '"oracle_vel_noise": runner.pcfg["oracle_vel_noise"]' in ts
