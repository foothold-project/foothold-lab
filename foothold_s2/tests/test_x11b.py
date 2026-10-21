"""SONNET-X11b (ASTRA-X13 H1~H4 · M1~M3) CPU 시험. 반례는 X13 이 재현한 입력을 그대로 쓴다.

Kit 없이 가짜 env 로 본다. 통과하는 것이 제품 동작이 아니라 «반례가 이제 잡힌다» 는 뜻이다.
"""

import json
import os
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.eval import adapters
from foothold_s2.eval.adapters import S2Policy, load_s2_runner
from foothold_s2.models.start_policy import ACTOR_KEY
from foothold_s2.runners import manifest as mf
from foothold_s2.runners.contracts import start_contract_bad
from foothold_s2.runners.reward_split import RewardSplit, StepClassifier
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _runner(seed=0, n=8, T=24, env=None, log_dir=None, **pc):
    torch.manual_seed(seed)
    p = {"microbatch_envs": 4, "map_input": "none"}
    p.update(pc)

    return StartRunner(env or FakeStartEnv(num_envs=n, seed=seed), train_cfg(T, p), log_dir=log_dir, device="cpu")


# ------------------------------------------------------------------ H1 평가 경계에서 모드 복원
@pytest.mark.parametrize("mode,expect_zero", [("zero", True), ("learned", False)])
def test_h1_saved_mode_is_restored_by_the_real_eval_loader(tmp_path, mode, expect_zero):
    r = _runner(est_mode=mode, critic_mode="clean52")
    ck = os.path.join(str(tmp_path), "model_0.pt")
    r.save(ck)
    # 평가 쪽은 «기본 learned · legacy» 설정으로 시작한다 (registry 기본값과 같다): 저장된 모드가 복원돼야 한다
    env = FakeStartEnv(num_envs=8, seed=3)
    runner, sd = load_s2_runner(env, train_cfg(24, {"microbatch_envs": 4}), ck, "cpu")

    assert runner.pcfg["est_mode"] == mode and runner.pcfg["critic_mode"] == "clean52" and runner.pcfg["map_input"] == "none"
    seen = {}
    orig = runner.alg.policy.act_inference
    runner.alg.policy.act_inference = lambda od: (seen.setdefault("a", od[ACTOR_KEY].clone()), orig(od))[1]
    S2Policy(runner, 8, z_mode="mean", act_mode="mean")(env.get_observations())
    tail = float(seen["a"][:, 45:].abs().max())

    assert (tail == 0.0) is expect_zero                                     # zero 면 est51 최댓값 0, learned 면 0 이 아니다


def test_h1_mismatch_with_requested_mode_is_refused_and_old_checkpoints_default(tmp_path):
    r = _runner(est_mode="zero")
    ck = os.path.join(str(tmp_path), "m.pt")
    r.save(ck)
    env = FakeStartEnv(num_envs=8, seed=3)

    with pytest.raises(ValueError, match="est_mode"):
        load_s2_runner(env, train_cfg(24, {"microbatch_envs": 4}), ck, "cpu", expect={"est_mode": "learned"})

    load_s2_runner(env, train_cfg(24, {"microbatch_envs": 4}), ck, "cpu", expect={"est_mode": "zero"})      # 일치하면 통과

    sd = torch.load(ck, weights_only=False)
    for k in ("est_mode", "critic_mode"):
        sd["perception_cfg"].pop(k)                                           # 옛 체크포인트(EX-09 · 10)에는 이 칸이 없다
    old = os.path.join(str(tmp_path), "old.pt")
    torch.save(sd, old)
    runner, _ = load_s2_runner(env, train_cfg(24, {"microbatch_envs": 4, "est_mode": "zero"}), old, "cpu")

    assert runner.pcfg["est_mode"] == "learned" and runner.pcfg["critic_mode"] == "legacy"           # 그때의 동작으로 본다


def test_h1_runner_load_refuses_a_checkpoint_with_a_different_treatment(tmp_path):
    ck = os.path.join(str(tmp_path), "z.pt")
    _runner(est_mode="zero").save(ck)

    with pytest.raises(ValueError, match="est_mode"):
        _runner(est_mode="learned").load(ck)


def test_h1_all_eval_scripts_use_the_restoring_loader():
    for name in ("diag_z_action.py", "diag_cmd_response.py", "diag_s2_faithful.py"):
        src = open(os.path.join(REPO, "foothold_s2", "eval", name), encoding="utf-8").read()

        assert "load_s2_runner" in src, name
        assert "StartRunner(" not in src, name                                          # 직접 만들어 weight 만 읽는 경로가 없다

    adapter_src = open(os.path.join(REPO, "foothold_s2", "eval", "adapters.py"), encoding="utf-8").read()

    assert "load_s2_runner(env, agent_cfg.to_dict()" in adapter_src.split("class S2Adapter")[1]       # S2Adapter.load_policy 도 같은 로더


# ------------------------------------------------------------------ H2 지각 · AdaSmpl 손실과 갱신 뒤 파라미터 유한성
def test_h2_perception_nan_loss_is_an_invalid_run(tmp_path):
    r = _runner(log_dir=str(tmp_path), stop_on_nonfinite=True)
    orig = r.update_perception
    r.update_perception = lambda: {**orig(), "l_ie": float("nan")}

    with pytest.raises(RuntimeError, match="NaN/Inf"):
        r.learn(1)

    st = json.load(open(os.path.join(str(tmp_path), "train_start_status.json"), encoding="utf-8"))
    assert st["invalid_run"] is True and "perception" in st["reason"]


@pytest.mark.parametrize("owner", ["perception", "policy"])
def test_h2_nan_parameter_after_update_is_an_invalid_run(tmp_path, owner):
    r = _runner(log_dir=str(tmp_path), stop_on_nonfinite=True)
    orig = r.update_perception

    def poisoned():
        out = orig()
        module = r.perception if owner == "perception" else r.alg.policy

        with torch.no_grad():
            next(module.parameters()).view(-1)[0] = float("nan")

        return out

    r.update_perception = poisoned

    with pytest.raises(RuntimeError, match="NaN/Inf 파라미터"):
        r.learn(1)


def test_h2_adasmpl_nan_is_an_invalid_run(tmp_path):
    r = _runner(log_dir=str(tmp_path), stop_on_nonfinite=True)
    r.update_adasmpl = lambda: float("nan")

    with pytest.raises(RuntimeError, match="adasmpl_p"):
        r.learn(1)


def test_h2_clean_run_is_not_flagged(tmp_path):
    r = _runner(log_dir=str(tmp_path), stop_on_nonfinite=True)
    r.learn(1)

    assert r.current_learning_iteration == 0


# ------------------------------------------------------------------ H3 START 명령 계약
@pytest.mark.parametrize("cmd,bad", [
    ([0.5, 0, 0], False), ([0.0, 0, 0.0], False), ([0.0, 0, 1.2], False), ([1.5, 0, 0], False), ([0.3, 0, 0], False),
    ([0.1, 0, 0], True),                       # X13 반례: vx 가 (0, 0.3) 사이
    ([float("nan"), 0, 0], True), ([0, 0, float("nan")], True), ([float("inf"), 0, 0], True),
    ([2.0, 0, 0], True), ([0.5, 0.1, 0], True), ([0.5, 0, 0.3], True), ([0.0, 0, 1.5], True), ([-0.5, 0, 0], True),
])
def test_h3_contract_function(cmd, bad):
    assert bool(start_contract_bad(torch.tensor([cmd]))[0]) is bad


class _CmdEnv(FakeStartEnv):
    """step 마다 명령 열(sequence)을 돌려주는 가짜 command_manager 를 달고 있다. seq[k] 는 k 번째 step 의 명령(모든 env 같음)."""

    def __init__(self, seq, has_term=True, **kw):
        super().__init__(**kw)
        self.seq = seq
        self.k = 0
        self.has_term = has_term
        self.vel = torch.tensor([seq[0]] * self.num_envs)
        env = self
        self.command_manager = SimpleNamespace(get_term=lambda name: SimpleNamespace(vel_command_b=env.vel) if env.has_term else None)

    @property
    def unwrapped(self):
        return self

    def step(self, actions):
        out = super().step(actions)
        self.k += 1
        self.vel = torch.tensor([self.seq[min(self.k, len(self.seq) - 1)]] * self.num_envs)

        return out


def _contract_runner(seq, tmp_path, has_term=True):
    torch.manual_seed(0)
    env = _CmdEnv(seq, has_term=has_term, num_envs=8, seed=0)

    return StartRunner(env, train_cfg(24, {"microbatch_envs": 4, "map_input": "none", "contract": "start"}), log_dir=str(tmp_path), device="cpu")


def test_h3_valid_commands_pass(tmp_path):
    _contract_runner([[0.5, 0, 0]] * 12 + [[0.0, 0, 1.0]] * 12, tmp_path).learn(1)


@pytest.mark.parametrize("bad", [[0.1, 0, 0], [float("nan"), 0, 0], [0.0, 0, float("nan")], [0.5, 0, 0.3]])
def test_h3_violation_in_the_middle_of_the_rollout_is_caught_even_if_it_ends_valid(tmp_path, bad):
    seq = [[0.5, 0, 0]] * 5 + [bad] + [[0.5, 0, 0]] * 30              # 5 번째 step 만 위반하고 rollout 끝은 정상

    with pytest.raises(RuntimeError, match="START 명령 계약"):
        _contract_runner(seq, tmp_path).learn(1)


def test_h3_missing_command_term_fails(tmp_path):
    with pytest.raises(RuntimeError, match="term 이 없다"):
        _contract_runner([[0.5, 0, 0]] * 30, tmp_path, has_term=False).learn(1)


# ------------------------------------------------------------------ H4 reward_split 시점 · 부호 · 전환
class _FakeIsaac:
    """Isaac step 의 순서를 흉내 낸다: 보상 계산(compute) -> reset -> 명령 재표집 -> 반환. compute 시점의 값만 «보상과 같은 시점»."""

    def __init__(self, N, names):
        self.N = N
        self.names = names
        self.data = SimpleNamespace(root_lin_vel_b=torch.zeros(N, 3), root_ang_vel_b=torch.zeros(N, 3))
        self.term = SimpleNamespace(vel_command_b=torch.zeros(N, 3))
        self._step_reward = torch.zeros(N, len(names))
        self.reset_buf = torch.zeros(N, dtype=torch.bool)
        self.reward_manager = SimpleNamespace(active_terms=names, _step_reward=self._step_reward, compute=self._compute)
        self.scene = {"robot": SimpleNamespace(data=self.data)}
        self.command_manager = SimpleNamespace(get_term=lambda name: self.term)
        self.pending = None

    def _compute(self, dt=0.02):
        self.reward_manager._step_reward = self.pending["reward"].clone()

        return self.reward_manager._step_reward.sum(-1)

    def step(self, vx, wz, cmd, reward, reset=None, post=None):
        """vx · wz · cmd 는 보상 시점 값. post=(vx, wz, cmd) 는 reset 뒤 값."""
        self.data.root_lin_vel_b[:, 0] = vx
        self.data.root_ang_vel_b[:, 2] = wz
        self.term.vel_command_b[:] = cmd
        self.reset_buf = torch.zeros(self.N, dtype=torch.bool) if reset is None else reset
        self.pending = {"reward": reward}
        self.reward_manager.compute()
        if post is not None:                                           # reset 과 재표집이 값을 덮는다
            self.data.root_lin_vel_b[:, 0], self.data.root_ang_vel_b[:, 2] = post[0], post[1]
            self.term.vel_command_b[:] = post[2]


def _names():
    return ["track_lin_vel", "track_ang_vel", "action_rate", "action_smoothness", "joint_torques"]


def test_h4_opposite_sign_rotations_are_both_moving_not_cancelled():
    N, names = 2, _names()
    env = _FakeIsaac(N, names)
    rs = RewardSplit()
    rs.attach(env)
    rew = torch.tensor([[0.5, 0.5, -0.1, -0.1, -0.2]] * N)

    for k in range(24):
        sign = 1.0 if k < 12 else -1.0                                  # +1.2 회전 12 step 후 -1.2 회전 12 step, 완벽히 추종
        env.step(0.0, sign * 1.2, torch.tensor([0.0, 0.0, sign * 1.2]), rew)
        rs.add()

    out = rs.summary()

    assert out["frac_moving"] == pytest.approx(1.0) and out["frac_stalled"] == 0.0 and out["frac_no_move_command"] == 0.0     # X13: 예전엔 전부 «명령 없음»
    assert out["moving"]["track_ang_vel"] == pytest.approx(0.5)


def test_h4_straight_to_spin_transition_is_classified_per_step():
    N, names = 1, _names()
    env = _FakeIsaac(N, names)
    rs = RewardSplit()
    rs.attach(env)
    rew = torch.tensor([[0.1, 0.0, -1.0, 0.0, 0.0]])

    for k in range(24):
        if k < 12:
            env.step(0.4, 0.0, torch.tensor([0.5, 0.0, 0.0]), rew)           # 직진 12 step: 실제 0.4 로 움직임
        else:
            env.step(0.0, 0.0, torch.tensor([0.0, 0.0, 1.2]), rew)           # 회전 명령인데 안 돈다: 멈춤
        rs.add()

    out = rs.summary()

    assert out["frac_moving"] == pytest.approx(0.5) and out["frac_stalled"] == pytest.approx(0.5)


def test_h4_reward_and_state_use_the_same_pre_reset_moment():
    N, names = 2, _names()
    env = _FakeIsaac(N, names)
    rs = RewardSplit()
    rs.attach(env)
    big = torch.tensor([[1.5, 0, 0, 0, 0], [0.2, 0, 0, 0, 0]])
    reset = torch.tensor([True, False])

    # env0: 보상 시점에는 직진 0.5 · 속도 0.4(움직임, 보상 1.5) 였는데 이 step 에서 reset 되어 반환 시점에는 속도 0 · 명령 0
    env.step(torch.tensor([0.4, 0.0]), 0.0, torch.tensor([[0.5, 0, 0], [0.5, 0, 0]]), big, reset=reset,
             post=(torch.tensor([0.0, 0.0]), 0.0, torch.tensor([[0.0, 0, 0], [0.5, 0, 0]])))
    rs.add()
    out = rs.summary()

    assert out["moving"]["track_lin_vel"] == pytest.approx(1.5)           # 보상 1.5 는 «움직이는» 쪽에 들어갔다 (예전엔 reset 뒤 0 속도 · 0 명령이라 어느 집단에도 안 들어갔다)
    assert out["stalled"]["track_lin_vel"] == pytest.approx(0.2)         # env1 은 속도 0 이라 멈춤
    assert out["reset_env_steps"] == 1


def test_h4_classifier_restarts_after_reset_and_after_command_change():
    clf = StepClassifier()
    cmd = torch.tensor([[0.5, 0.0, 0.0]])
    for _ in range(30):                                                   # 오래 걸어서 지수평균이 0.4 근처
        clf.classify(torch.tensor([0.4]), torch.tensor([0.0]), cmd)

    moving, stalled, _ = clf.classify(torch.tensor([0.0]), torch.tensor([0.0]), cmd, reset_prev=torch.tensor([True]))      # reset 직후 속도 0: 지수평균을 다시 시작해 즉시 멈춤으로

    assert bool(stalled[0]) and not bool(moving[0])


def test_h4_missing_attributes_are_recorded_not_silently_disabled():
    rs = RewardSplit()
    rs.attach(SimpleNamespace())                                          # 보상 관리자 등이 없다
    rs.add()
    out = rs.summary()

    assert "unavailable" in out and "속성 없음" in out["unavailable"]

    rs2 = RewardSplit()                                                   # attach 는 됐는데 compute 가 불리지 않은 경우도 «없음» 으로
    env = _FakeIsaac(2, _names())
    rs2.attach(env)
    rs2.add()

    assert "unavailable" in rs2.summary()


def test_h4_runner_writes_unavailable_marker_for_env_without_reward_objects(tmp_path):
    r = _runner(log_dir=str(tmp_path), log_reward_split=True)
    r.learn(1)
    rec = json.loads(open(os.path.join(str(tmp_path), "train_extra.jsonl"), encoding="utf-8").read().splitlines()[-1])

    assert "unavailable" in rec["reward_split"]


# ------------------------------------------------------------------ M1 · M2 · M3 manifest
def _manifest_for(tmp_path, tag, mode="learned", hydra=(), device="cuda:0", extra_args=None):
    r = _runner(est_mode=mode)

    return mf.build_manifest(repo=REPO, log_dir=str(tmp_path / tag), run_name=tag, cli_args={"seed": 42, "run_name": tag, "device": device, "hydra_args": list(hydra), **(extra_args or {})},
                             modes={"est_mode": mode, "clip_actions": 17.0}, runner=r)


def test_m1_file_changes_detect_missing_added_and_changed(monkeypatch, tmp_path):
    m = _manifest_for(tmp_path, "a")
    real = mf.imported_files()
    victim = sorted(m["files"]["imported_sha256"])[0]
    other = sorted(m["files"]["imported_sha256"])[1]

    monkeypatch.setattr(mf, "imported_files", lambda *a, **k: {n: s for n, s in real.items() if n != victim})
    assert mf.file_changes(m)["missing"] == [victim]                                    # old 에만 있는 모듈 소실

    monkeypatch.setattr(mf, "imported_files", lambda *a, **k: {**real, "foothold_s2.brand_new": "f" * 64})
    ch = mf.file_changes(m)
    assert list(ch["added"]) == ["foothold_s2.brand_new"] and ch["changed"] == [] and ch["missing"] == []

    monkeypatch.setattr(mf, "imported_files", lambda *a, **k: {**real, other: "0" * 64})
    assert mf.file_changes(m)["changed"] == [other]


def test_m1_runner_checks_code_at_latest_saves_too_and_missing_is_invalid(tmp_path, monkeypatch):
    r = _runner(log_dir=str(tmp_path), latest_interval=1)
    r.save_interval = 1000                                                              # model_N 저장 주기에는 안 걸리고 latest 저장 주기에만 걸리는 iteration(1)에서 시험
    r.current_learning_iteration, r._resumed = 0, True                                  # 다음 learn 은 iteration 1 부터
    m = mf.build_manifest(repo=REPO, log_dir=str(tmp_path), run_name="t", cli_args={}, modes={}, runner=r)
    r.attach_manifest(str(tmp_path), m)
    victim = sorted(m["files"]["imported_sha256"])[0]
    real = mf.imported_files()
    monkeypatch.setattr(mf, "imported_files", lambda *a, **k: {n: s for n, s in real.items() if n != victim})

    with pytest.raises(RuntimeError, match="소비 코드가 바뀜"):
        r.learn(1)

    assert 1 % r.save_interval != 0 and 1 % r.pcfg["latest_interval"] == 0


def test_m1_added_files_are_noted_not_fatal(tmp_path, monkeypatch):
    r = _runner(log_dir=str(tmp_path))
    m = mf.build_manifest(repo=REPO, log_dir=str(tmp_path), run_name="t", cli_args={}, modes={}, runner=r)
    r.attach_manifest(str(tmp_path), m)
    real = mf.imported_files()
    monkeypatch.setattr(mf, "imported_files", lambda *a, **k: {**real, "foothold_s2.lazy_mod": "a" * 64})
    r._check_code(0)

    assert m["files"]["added_after_start"] == {"foothold_s2.lazy_mod": "a" * 64}


def test_m2_hydra_overrides_are_compared_by_key(tmp_path):
    a = _manifest_for(tmp_path, "ex11", "zero", ["agent.perception.est_mode=zero", "agent.algorithm.learning_rate=0.001"])
    b = _manifest_for(tmp_path, "ex12", "learned", ["agent.perception.est_mode=learned", "agent.algorithm.learning_rate=0.001"])
    ok = mf.diff_manifests(a, b)

    assert ok["ok"], ok["unexpected_differences"]
    assert "run.hydra_overrides.agent.perception.est_mode" in ok["allowed_differences"]

    c = _manifest_for(tmp_path, "ex12", "learned", ["agent.perception.est_mode=learned", "agent.algorithm.learning_rate=0.1"])
    bad = mf.diff_manifests(a, c)

    assert not bad["ok"] and "run.hydra_overrides.agent.algorithm.learning_rate" in bad["unexpected_differences"]            # X13: 예전엔 학습률 override 도 허용으로 나왔다


def test_m2_device_placement_is_a_separate_allowed_bucket(tmp_path):
    a = _manifest_for(tmp_path, "ex11", "zero", ["agent.perception.est_mode=zero"], device="cuda:0")
    b = _manifest_for(tmp_path, "ex12", "learned", ["agent.perception.est_mode=learned"], device="cuda:1")
    d = mf.diff_manifests(a, b)

    assert d["ok"], d["unexpected_differences"]
    assert "run.cli_args.device" in d["device_placement_differences"]
    assert "run.cli_args.device" not in d["allowed_differences"]


def test_m3_record_contract_states_what_is_not_guaranteed(tmp_path):
    m = _manifest_for(tmp_path, "a")
    rc = m["record_contract"]

    assert "시작 hidden" in rc["kl_probe"] and "전체 3072" in rc["kl_probe"]
    assert "범위 밖" in rc["consumed_code"] and "관절각" in rc["action_probe"]


def test_h3_consumed_command_is_moved_to_the_runner_device():
    """env 와 runner 가 다른 GPU 일 때(실제 예행: env cuda:1 · runner cuda:0) 누적 텐서와 섞이지 않게 runner 장치로 옮긴다. 장치 이동 호출을 가로채 확인한다."""
    r = _runner()
    seen = []

    class Spy:
        def __getitem__(self, idx):
            return self

        def detach(self):
            return self

        def clone(self):
            return self

        def to(self, device):
            seen.append(device)

            return torch.zeros(8, 3)

    r._command_term = lambda: SimpleNamespace(vel_command_b=Spy())
    out = r._consumed_command(0)

    assert seen == [r.device] and out.shape == (8, 3)


def test_new_runner_tensors_are_never_built_on_a_hardcoded_device():
    """새 모듈 · 새 코드가 장치 이름(cuda)을 박아 쓰지 않는다(인자 · self.device · 대상 텐서의 장치만)."""
    import re

    for rel in ("runners/contracts.py", "runners/reward_split.py", "runners/action_stats.py", "runners/kl_probe.py", "runners/manifest.py"):
        src = open(os.path.join(REPO, "foothold_s2", rel), encoding="utf-8").read()
        code = " ".join(line.split("#")[0] for line in src.splitlines())

        assert not re.search(r"cuda", code), rel


# ------------------------------------------------------------------ X11d 시뮬과 신경망이 같은 GPU
def _cfgs(agent_dev="cuda:0", sim_dev="cuda:0"):
    return SimpleNamespace(sim=SimpleNamespace(device=sim_dev)), SimpleNamespace(device=agent_dev)


def test_x11d_device_arg_sets_both_sim_and_agent():
    from foothold_s2.runners.devices import resolve_devices

    env_cfg, agent_cfg = _cfgs()
    assert resolve_devices("cuda:1", env_cfg, agent_cfg) == ("cuda:1", "cuda:1")
    assert env_cfg.sim.device == "cuda:1" and agent_cfg.device == "cuda:1"          # 예전엔 agent 가 cuda:0 에 남았다

    env_cfg, agent_cfg = _cfgs("cuda:0", "cuda:0")
    assert resolve_devices(None, env_cfg, agent_cfg) == ("cuda:0", "cuda:0")         # 인자가 없으면 기존 값 그대로

    env_cfg, agent_cfg = _cfgs()
    assert resolve_devices("cuda:0", env_cfg, agent_cfg, distributed=True, local_rank=1) == ("cuda:1", "cuda:1")         # 분산이면 rank 의 GPU


def test_x11d_train_start_uses_the_helper_and_agent_yaml_device_is_placement(tmp_path):
    src = open(os.path.join(REPO, "foothold_s2", "scripts", "train_start.py"), encoding="utf-8").read()

    assert "resolve_devices(args_cli.device, env_cfg, agent_cfg" in src
    assert "env_cfg.sim.device = args_cli.device" not in src                        # 시뮬만 바꾸던 줄이 없다

    a = _manifest_for(tmp_path, "ex11", "zero", ["agent.perception.est_mode=zero"], device="cuda:0")
    b = _manifest_for(tmp_path, "ex12", "learned", ["agent.perception.est_mode=learned"], device="cuda:1")
    a["yaml"]["agent"]["device"], b["yaml"]["agent"]["device"] = "cuda:0", "cuda:1"
    a["yaml"]["env"]["sim.device"], b["yaml"]["env"]["sim.device"] = "cuda:0", "cuda:1"
    d = mf.diff_manifests(a, b)

    assert d["ok"], d["unexpected_differences"]
    assert "yaml.agent.device" in d["device_placement_differences"] and "yaml.env.sim.device" in d["device_placement_differences"]


# ------------------------------------------------------------------ X11e 비분산 경로가 AppLauncher 의 분산 전용 속성을 읽지 않는다
def test_x11e_non_distributed_path_never_reads_app_launcher_attributes_other_than_app():
    """AppLauncher 는 local_rank 같은 속성을 분산일 때만 만든다. train_start.py 의 모든 app_launcher.<속성> 읽기는 `app` 이거나 args_cli.distributed 로 막힌 안쪽이어야 한다(AST)."""
    import ast

    path = os.path.join(REPO, "foothold_s2", "scripts", "train_start.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    parents = {}

    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def mentions_distributed(test):
        return any(isinstance(n, ast.Attribute) and n.attr == "distributed" for n in ast.walk(test))

    def guarded(node):
        child, cur = node, parents.get(node)

        while cur is not None:
            if isinstance(cur, ast.If) and mentions_distributed(cur.test) and any(child is b or any(child is d for d in ast.walk(b)) for b in cur.body):
                return True

            if isinstance(cur, ast.IfExp) and mentions_distributed(cur.test) and (child is cur.body or any(child is d for d in ast.walk(cur.body))):
                return True

            child, cur = cur, parents.get(cur)

        return False

    reads = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "app_launcher" and isinstance(n.ctx, ast.Load)]
    unguarded = [(n.attr, n.lineno) for n in reads if n.attr != "app" and not guarded(n)]

    assert reads and not unguarded, unguarded                                           # X11d 의 실패(local_rank, 줄 82)가 여기서 잡혔어야 한다
