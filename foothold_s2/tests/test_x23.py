"""SONNET-X23: EX-23 (START 구조 G1 + EX-11 환경 + 약한 DR + 행동 지연 끔) · EX-24 (v2 에서 actor 높이 스캔만 뺌) CPU 시험.

EX-23: 구성 대조(AST) · G1 에서 IE 로 가는 지도가 실제 정답 지도(use_gt)인지의 배선 · 지도 입력 통계 기록 · 정답 지도의 값 모양(평지 상수 · 계단 모양) 기록 함수.
EX-24: v2 env.yaml · agent.yaml 대조(차이는 height_scan 하나) · actor 입력 차원이 정확히 스캔 칸 수만큼 적음 · 학습 스크립트 확인.
"""

import ast
import json
import os

import pytest
import torch

from foothold_s2.runners.manifest import yaml_flat
from foothold_s2.runners.map_stats import MapStatsRecorder, map_stats
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V2 = "C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/params"
GAP = "C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2"
needs_v2 = pytest.mark.skipif(not os.path.exists(V2 + "/env.yaml"), reason="v2 실행 기록 없음")


def _src(rel):
    return open(os.path.join(REPO, rel), encoding="utf-8").read()


def _post_init(rel, cls):
    tree = ast.parse(_src(rel))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    post = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__post_init__")

    return {ast.unparse(a.targets[0]): ast.unparse(a.value) for a in ast.walk(post) if isinstance(a, ast.Assign)}, node


def _fields(rel, cls):
    node = next(n for n in ast.parse(_src(rel)).body if isinstance(n, ast.ClassDef) and n.name == cls)

    return {(n.targets[0].id if isinstance(n, ast.Assign) else n.target.id): n.value for n in node.body if isinstance(n, (ast.Assign, ast.AnnAssign))}, node


def _runner(map_input="reconstruction", n=8, seed=0, **pc):
    torch.manual_seed(seed)
    p = {"microbatch_envs": 4, "map_input": map_input}
    p.update(pc)

    return StartRunner(FakeStartEnv(num_envs=n, seed=seed), train_cfg(24, p), log_dir=None, device="cpu")


# ------------------------------------------------------------------ EX-23 구성
def test_x23_env_adds_only_the_x19_events_and_x20_action_on_top_of_x11():
    a23, n23 = _post_init("foothold_s2/tasks/s2_x23_cfg.py", "FootholdS2X23EnvCfg")
    a19, _ = _post_init("foothold_s2/tasks/s2_x19_cfg.py", "FootholdS2X19EnvCfg")
    a20, _ = _post_init("foothold_s2/tasks/s2_x20_cfg.py", "FootholdS2X20EnvCfg")

    assert [ast.unparse(b) for b in n23.bases] == ["FootholdS2X11EnvCfg"]
    assert set(a23) == set(a19) | {"self.actions.joint_pos"}                                  # DR 다섯 + 행동 하나
    assert all(a23[k] == a19[k] for k in a19) and a23["self.actions.joint_pos"] == a20["self.actions.joint_pos"]            # 식까지 EX-19 · EX-20 과 같음
    body = _src("foothold_s2/tasks/s2_x23_cfg.py").split('"""', 2)[2]

    assert "terminations" not in body and "rewards" not in body and "commands" not in body and "curriculum" not in body             # 종료 · 보상 · 명령은 START(EX-11) 그대로


def test_x23_agent_turns_on_the_map_and_keeps_the_rest_of_ex11():
    fields, node = _fields("foothold_s2/tasks/agents/s2_x23_ppo_cfg.py", "S2X23PPORunnerCfg")
    ppo = _src("foothold_s2/tasks/agents/s2_ppo_cfg.py")
    x11 = ppo[ppo.index("class S2X11PPORunnerCfg"):ppo.index("class S2X13PPORunnerCfg")]
    x11_fields, _ = _fields("foothold_s2/tasks/agents/s2_ppo_cfg.py", "S2X11PPORunnerCfg")
    base_perc = ast.literal_eval(x11_fields["perception"])
    perc = ast.literal_eval(fields["perception"])

    assert [ast.unparse(b) for b in node.bases] == ["S2X11PPORunnerCfg"] and set(fields) == {"save_interval", "experiment_name", "perception"}
    assert ast.literal_eval(fields["save_interval"]) == 50 and ast.literal_eval(fields["experiment_name"]) == "foothold_s2_x23"
    assert {k: v for k, v in perc.items() if k not in ("map_input", "log_map_stats", "force_gt")} == base_perc                           # 지도 입력 · 기록 두 칸만 다르다
    assert perc["map_input"] == "reconstruction" and perc["est_mode"] == "learned" and perc["critic_mode"] == "clean52" and perc["contract"] == "start" and perc["log_map_stats"] is True
    assert perc["force_gt"] is True
    assert ast.literal_eval(x11_fields["max_iterations"]) == 1501                                                              # 1501 회는 EX-11 에서 상속


def test_x23_registration_and_run_script():
    import gymnasium as gym

    import foothold_s2.x23_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-X23-v0")

    assert spec.entry_point == "isaaclab.envs:ManagerBasedRLEnv" and spec.kwargs["env_cfg_entry_point"].endswith("s2_x23_cfg:FootholdS2X23EnvCfg")
    assert spec.kwargs["rsl_rl_cfg_entry_point"].endswith("s2_x23_ppo_cfg:S2X23PPORunnerCfg")
    run = _src("foothold_s2/run_s2_x23.sh")

    assert "FootholdS2-Go2-S2-X23-v0" in run and "ex23-g1" in run and "--map_input reconstruction" in run and "--map_input none" not in run
    assert "--max_iterations 1501" in run and "--num_envs 3072" in run and "--seed 42" in run
    ts = _src("foothold_s2/scripts/train_start.py")

    assert "import foothold_s2.x23_tasks" in ts and 'runner.pcfg.get("log_map_stats")' in ts and "MapStatsRecorder(runner, log_dir).attach()" in ts


# ------------------------------------------------------------------ EX-23 지도 배선 · 통계
def _step_inputs(runner, raw):
    o, depth, gmap, _gf, _v, _c = runner._split(raw)
    pst = runner.perception.init_state(raw.batch_size[0], "cpu")

    return pst, runner.perception.ingest(pst, o, depth), gmap


def test_g1_ie_receives_the_env_gt_map_for_gt_envs_and_the_reconstruction_otherwise():
    r = _runner("reconstruction")
    raw = r.env.get_observations()
    sentinel = torch.arange(8 * 512, dtype=torch.float32).reshape(8, 512) / 1000.0                 # 칸마다 다른 값(자리표)
    raw["gt_map"] = sentinel
    pst, inp, gmap = _step_inputs(r, raw)

    assert torch.equal(gmap.reshape(8, 512), sentinel)                                           # runner 가 env 의 gt_map 묶음을 그대로(모양만 32x16) 지각에 넘긴다
    seen = []
    orig = r.perception.ie.estimate
    r.perception.ie.estimate = lambda h, hmap: (seen.append(None if hmap is None else hmap.clone()), orig(h, hmap))[1]
    pst.use_gt = torch.ones(8, dtype=torch.bool)
    r.perception.step(pst, inp, gmap)

    assert torch.equal(seen[-1].reshape(8, 512), sentinel)                                       # 정답 env: IE 입력 = 정답 지도 그대로

    pst2, inp2, _ = _step_inputs(r, raw)
    pst2.use_gt = torch.zeros(8, dtype=torch.bool)
    r.perception.step(pst2, inp2, gmap)

    assert not torch.equal(seen[-1].reshape(8, 512), sentinel)                                   # 복원 env: IE 입력은 TR-Net 복원 지도(정답과 다름)


def test_g1_estimate_follows_the_gt_map_when_use_gt_and_ignores_depth():
    r = _runner("reconstruction")
    raw = r.env.get_observations()

    def est_for(gt, depth_scale):
        raw2 = raw.clone()
        raw2["gt_map"] = gt
        raw2["depth"] = raw["depth"] * depth_scale
        pst, inp, gmap = _step_inputs(r, raw2)
        pst.use_gt = torch.ones(8, dtype=torch.bool)

        return r.perception.step(pst, inp, gmap, deterministic=True)

    g1, g2 = raw["gt_map"].reshape(8, 512).clone(), (raw["gt_map"].reshape(8, 512) + 0.5)

    assert torch.allclose(est_for(g1, 1.0), est_for(g1, 0.5))                                    # 정답 env: 깊이를 바꿔도 est 가 같다
    assert not torch.allclose(est_for(g1, 1.0), est_for(g2, 1.0))                                # 정답 지도를 바꾸면 est 가 바뀐다(지도가 actor 쪽으로 실제로 흐른다)


def test_map_stats_flat_stairs_and_missed_rays_known_values():
    flat = torch.full((4, 32, 16), -0.30)                                                        # 평지: h = z_hit - z_base = -(몸 높이) 상수
    s = map_stats(flat, torch.ones(4, dtype=torch.bool))

    assert s["gt_mean"] == pytest.approx(-0.30) and s["gt_cell_std"] == pytest.approx(0.0, abs=1e-6) and s["gt_missed_frac"] == 0.0
    assert s["gt_abs_lt_0p05"] == 0.0 and s["use_gt_frac"] == 1.0                                # 평지에서도 «0 근처» 가 아니다(몸 높이만큼 아래)
    stairs = torch.zeros(4, 32, 16)

    for k in range(32):
        stairs[:, k, :] = -0.30 + 0.05 * (k // 4)                                                # x 방향 계단: 4 줄마다 5 cm 높아짐
    st = map_stats(stairs, torch.ones(4, dtype=torch.bool))

    assert st["gt_cell_std"] > 0.05 and st["gt_std"] == pytest.approx(float(stairs.std()))        # 계단: 칸 사이 편차가 평지보다 훨씬 크다
    near = torch.full((2, 32, 16), -0.30)
    near[:, :8, :] = 0.02                                                                         # 앞쪽 8 줄은 몸 높이 근처까지 올라온 칸(1/4)
    near[:, 8:12, :] = -1.0                                                                       # 4 줄은 못 맞힌 광선(-1)
    sm = map_stats(near, torch.ones(2, dtype=torch.bool))

    assert sm["gt_abs_lt_0p05"] == pytest.approx(0.25) and sm["gt_missed_frac"] == pytest.approx(0.125)
    refined = torch.full((4, 32, 16), 0.1)
    mix = map_stats(flat, torch.tensor([True, True, False, False]), refined)

    assert mix["use_gt_frac"] == 0.5 and mix["eff_mean"] == pytest.approx(0.5 * -0.30 + 0.5 * 0.1) and mix["refined_mean"] == pytest.approx(0.1)


def test_start_obs_gt_map_is_height_relative_to_base_clipped():
    src = _src("foothold_s2/sensors/start_obs.py")
    fn = src[src.index("def height_rel_base"):src.index("def feet_height")]

    assert "z - base_z" in fn and "nan=-1.0" in fn and ".clamp(-1.0, 1.0)" in fn                  # 평지 = -(몸 높이) 상수, 못 맞힌 광선 -1, ±1 m 로 자름
    assert 'gt_map = ObsTerm(func=height_rel_base, params={"sensor_cfg": SceneEntityCfg("gt_map_scan")})' in src


def test_recorder_writes_one_row_per_iteration_and_a_log_line(tmp_path, capsys):
    r = _runner("reconstruction")
    r.log_dir = str(tmp_path)
    rec = MapStatsRecorder(r, str(tmp_path))
    rec.attach()
    r.learn(2)                                                                                 # 두 iteration
    rows = [json.loads(line) for line in open(os.path.join(str(tmp_path), "map_stats.jsonl"), encoding="utf-8").read().splitlines()]

    assert [row["it"] for row in rows] == [0, 1] and rec.calls == 48
    assert {"gt_mean", "gt_std", "gt_cell_std", "gt_missed_frac", "gt_abs_lt_0p05", "use_gt_frac", "refined_mean", "eff_mean", "eff_std"} <= set(rows[0])
    assert 0.0 <= rows[0]["use_gt_frac"] <= 1.0
    out = capsys.readouterr().out

    assert "[G1] 지도 입력 통계 it=0" in out                                                      # 첫 update 에 run.log 로 한 줄
    assert not rec.in_step                                                                     # 재생 손실(sequence_loss)의 _advance 호출은 세지 않는다


def test_recorder_does_not_change_the_perception_outputs(tmp_path):
    a, b = _runner("reconstruction", seed=1), _runner("reconstruction", seed=1)
    MapStatsRecorder(b, str(tmp_path)).attach()
    raw = a.env.get_observations()
    out = []

    for r in (a, b):
        pst, inp, gmap = _step_inputs(r, raw)
        pst.use_gt = torch.ones(8, dtype=torch.bool)
        out.append(r.perception.step(pst, inp, gmap, deterministic=True))

    assert torch.equal(out[0], out[1])                                                         # 감싸도 est 가 비트 단위로 같다


# ------------------------------------------------------------------ EX-24
@needs_v2
def test_x24_actor_input_is_exactly_the_scan_cells_smaller_than_v2():
    ref = yaml_flat(V2 + "/env.yaml")
    width = {"base_lin_vel": 3, "base_ang_vel": 3, "projected_gravity": 3, "velocity_commands": 3, "joint_pos": 12, "joint_vel": 12, "actions": 12}
    terms = {k.split(".")[2] for k in ref if k.startswith("observations.policy.") and k.endswith(".func")}

    assert terms == set(width) | {"height_scan"}                                                 # v2 policy 그룹 = 7 항 + height_scan
    res, (sx, sy) = float(ref["scene.height_scanner.pattern_cfg.resolution"]), (float(ref["scene.height_scanner.pattern_cfg.size[0]"]), float(ref["scene.height_scanner.pattern_cfg.size[1]"]))
    scan = (int(round(sx / res)) + 1) * (int(round(sy / res)) + 1)
    v2_dim = sum(width.values()) + scan
    ex24_dim = sum(width[t] for t in terms if t != "height_scan")

    assert (res, sx, sy) == (0.1, 1.6, 1.0) and scan == 187 and v2_dim == 235 and ex24_dim == 48
    assert v2_dim - ex24_dim == scan                                                             # 정확히 스캔 칸 수만큼 적다
    assert not any(k.startswith("observations.critic.") for k in ref)                            # v2 에는 critic 그룹이 없다 -> critic 도 policy 그룹(=스캔 포함)을 쓴다
    agent = yaml_flat(V2 + "/agent.yaml")

    assert not any(k.startswith("obs_groups") for k in agent)                                    # obs_groups {} : critic 이 policy 그룹을 그대로 씀 -> EX-24 에서는 critic 입력도 48 칸이 된다(의도, 기록)


def test_x24_env_differs_from_v2b_only_by_height_scan():
    a, node = _post_init("foothold_s2/tasks/v2_noscan_cfg.py", "FootholdV2bNoScanEnvCfg")

    assert [ast.unparse(b) for b in node.bases] == ["UnitreeGo2V2bEnvCfg"] and a == {"self.observations.policy.height_scan": "None"}
    src = _src("foothold_s2/tasks/v2_noscan_cfg.py").split('"""', 2)[2]                            # 머리말 설명을 빼고 코드만

    assert "super().__post_init__()" in src and src.index("super().__post_init__()") < src.index("height_scan = None")      # v2a 의 검증(height_scan 잡음 읽기) 뒤에 뺀다
    inst = open(f"{GAP}/gap_training/v2a_env_cfg.py", encoding="utf-8").read() if os.path.exists(GAP) else ""

    assert (not inst) or "self.observations.policy.height_scan.noise" in inst                    # 뺀 항을 부모가 post_init 안에서 읽는다 = 뒤에 빼야 하는 근거


@needs_v2
def test_x24_agent_matches_v2_agent_yaml_except_the_asked_changes():
    ag = yaml_flat(V2 + "/agent.yaml")
    new, node = _post_init("foothold_s2/tasks/agents/v2_noscan_ppo_cfg.py", "FootholdV2bNoScanPPORunnerCfg")
    parent = open(f"{GAP}/gap_training/gap_ppo_cfg.py", encoding="utf-8").read()
    rough = open(f"{GAP}/agents/rsl_rl_ppo_cfg.py", encoding="utf-8").read()

    assert [ast.unparse(b) for b in node.bases] == ["UnitreeGo2GapPPORunnerCfg"]
    assert new == {"self.experiment_name": "'foothold_v2_noscan'", "self.max_iterations": "1501", "self.save_interval": "50"}      # 바꾸는 것은 세 칸뿐
    assert ag["algorithm.learning_rate"] == "0.0001" and "learning_rate = 1.0e-4" in parent                                      # v2 값 = 부모 설치본 값
    assert ag["num_steps_per_env"] == "24" and "num_steps_per_env = 24" in rough and ag["policy.class_name"] == "ActorCritic" and ag["class_name"] == "OnPolicyRunner"
    assert [ag[f"policy.actor_hidden_dims[{i}]"] for i in range(3)] == ["512", "256", "128"] and "actor_hidden_dims=[512, 256, 128]" in rough
    assert ag["algorithm.desired_kl"] == "0.01" and ag["algorithm.schedule"] == "adaptive" and ag["clip_actions"] == "None"
    assert ag["resume"] == "True" and ag["load_run"] == "nvidia_pretrained_source"               # v2 는 사전학습에서 이어 학습 -> EX-24 는 입력 차원이 달라 처음부터(아래 스크립트에 resume 없음)


def test_x24_registration_launcher_and_run_script():
    import gymnasium as gym

    import foothold_s2.x24_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-X24-v0")

    assert spec.entry_point == "isaaclab.envs:ManagerBasedRLEnv" and spec.kwargs["env_cfg_entry_point"].endswith("v2_noscan_cfg:FootholdV2bNoScanEnvCfg")
    assert spec.kwargs["rsl_rl_cfg_entry_point"].endswith("v2_noscan_ppo_cfg:FootholdV2bNoScanPPORunnerCfg")
    launcher = _src("foothold_s2/scripts/train_v2_noscan.py")

    assert 'runpy.run_path(TRAIN, run_name="__main__")' in launcher and '"rsl_rl", "train.py"' in launcher and "import foothold_s2.x24_tasks" in launcher
    assert launcher.index("import rsl_rl.runners") < launcher.index("runpy.run_path")                                                # Kit 이 뜨기 전 선행 import
    assert os.path.exists("C:/isaac/IsaacLab/scripts/reinforcement_learning/rsl_rl/train.py") or not os.path.exists("C:/isaac")
    run = _src("foothold_s2/run_s2_x24.sh")

    assert "train_v2_noscan.py" in run and "FootholdS2-Go2-S2-X24-v0" in run and "ex24-v2-noscan" in run and "--num_envs 4096" in run and "--seed 42" in run and "--max_iterations 1501" in run
    assert "--resume" not in run.split("\n", 6)[-1] and "agent.device=$DEV" in run


def test_x23_force_gt_reaches_adasmpl_as_p_one_and_is_recorded_in_manifest_modes():
    import torch

    from foothold_s2.models.start_perception import AdaSmpl

    perc = ast.literal_eval(_fields("foothold_s2/tasks/agents/s2_x23_ppo_cfg.py", "S2X23PPORunnerCfg")[0]["perception"])
    ada = AdaSmpl(0.3, 1e-6, bool(perc.get("force_gt", False)))                                           # StartRunner 가 하는 그대로(start_runner.py:109)

    assert ada.force_gt is True and ada.sample(64, "cpu").all()
    ada.add(torch.tensor([0.1, 5.0, 0.2]))                                                               # 끝난 에피소드가 있어도 p 는 1 고정
    ada.update()

    assert ada.p == 1.0
    assert 'bool(pcfg.get("force_gt", False))' in _src("foothold_s2/runners/start_runner.py")
    assert '"force_gt": bool(runner.pcfg.get("force_gt", False))' in _src("foothold_s2/scripts/train_start.py")       # manifest modes 칸
