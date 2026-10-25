"""SONNET-X25f: EX-33 S-B (에피소드 단위 지도 끔) CPU 시험. Kit 없이.

핵심 물음 둘: (1) p_off 0 이면 B 와 같은 출력인가 (2) rollout 에서 끈 env 가 update(지각 재생 · 확률 재계산)에서도 꺼지는가.
"""

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.models.start_perception import PerceptionCfg, StartPerception
from foothold_s2.runners.map_switch import MapSwitchRecorder, draw_map_off, make_generator
from foothold_s2.runners.perception_replay import PerceptionReplay
from foothold_s2.sol23f_contract import BUDGET_VARIANTS, CKPT_VARIANT, FORCE_GT, MAP_INPUT, TASKS, validate_launch

ROOT = Path(__file__).resolve().parents[2]
B_COMMIT = "d9517fb9"
NOW = 1_700_000_000.0


def _src(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _b_perception_module(tmp_path):
    """B 코드(d9517fb9)의 start_perception.py 를 그대로 불러온다: 같은 가중치로 «B 와 같은 출력» 을 대조하려는 것."""
    text = subprocess.run(["git", "show", f"{B_COMMIT}:foothold_s2/models/start_perception.py"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    path = tmp_path / "b_start_perception.py"
    path.write_text(text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("b_start_perception", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["b_start_perception"] = mod
    spec.loader.exec_module(mod)

    return mod


def _inputs(n, T, seed=0):
    g = torch.Generator().manual_seed(seed)
    for _ in range(T):
        yield (torch.randn(n, 45, generator=g), torch.rand(n, 60, 60, generator=g), torch.randn(n, 32, 16, generator=g) * 0.1,
               torch.randn(n, 100, generator=g), torch.randn(n, 3, generator=g), torch.randn(n, 45, generator=g))


def _rollout(p, n, T, off_schedule, seed=0, record_off=True):
    """off_schedule(t, st) 가 매 step 앞에서 st.map_off 를 정한다(reset 때만 바뀌도록 시험이 짠다). 재생 버퍼와 수집 est 를 돌려준다."""
    st = p.init_state(n, "cpu")
    st.use_gt = torch.tensor([True] * n)                        # B 와 같이 force_gt: 켠 env 는 정답 지도
    rb = PerceptionReplay(n, T, "cpu", torch.float32)
    rb.start(st.h_prop, st.h_terr)
    ests = []
    for t, (o, d, gm, gf, vel, nxt) in enumerate(_inputs(n, T, seed)):
        off_schedule(t, st)
        inp = p.ingest(st, o, d)
        ests.append(p.step(st, inp, gm, deterministic=True))
        rb.add_pre(inp, o, gm, gf, vel, st.use_gt, st.map_off if record_off else None)
        rb.add_post(nxt, torch.zeros(n, dtype=torch.bool))

    return rb, torch.stack(ests), st


# ---------------------------------------------------------------- (1) p_off 0 == B

def test_p_off_zero_gives_the_same_output_as_the_b_code_with_the_same_weights(tmp_path):
    b_mod = _b_perception_module(tmp_path)
    torch.manual_seed(3)
    b = b_mod.StartPerception(b_mod.PerceptionCfg())
    sb = StartPerception(PerceptionCfg())
    sb.load_state_dict(b.state_dict())                          # 가중치 같음
    n, T = 6, 12
    st_b, st_s = b.init_state(n, "cpu"), sb.init_state(n, "cpu")
    st_b.use_gt = st_s.use_gt = torch.ones(n, dtype=torch.bool)
    for o, d, gm, *_ in _inputs(n, T, 1):
        e_b = b.step(st_b, b.ingest(st_b, o, d), gm, deterministic=True)
        e_s = sb.step(st_s, sb.ingest(st_s, o, d), gm, deterministic=True)

        assert torch.equal(e_b, e_s)
    assert st_s.map_off is not None and not st_s.map_off.any()


def test_p_off_zero_replay_loss_is_the_b_loss(tmp_path):
    b_mod = _b_perception_module(tmp_path)
    torch.manual_seed(4)
    b = b_mod.StartPerception(b_mod.PerceptionCfg())
    sb = StartPerception(PerceptionCfg())
    sb.load_state_dict(b.state_dict())
    rb, _, _ = _rollout(sb, 6, 8, lambda t, st: None)
    batch = rb.gather(torch.arange(6))
    batch_b = {k: v for k, v in batch.items() if k != "map_off"}           # B 의 재생 버퍼에는 이 칸이 없다
    eps = torch.randn(8, 6, 16, generator=torch.Generator().manual_seed(1))
    la, lb = sb.sequence_loss(batch, eps=eps, impl="loop"), b.sequence_loss(batch_b, eps=eps, impl="loop")        # a1~a3 는 replay_fast 가 이 저장소 판이라 B 모듈과 섞이지 않게 loop 만 견준다(빠른 경로는 아래에서 loop 와 견준다)

    assert torch.equal(la["loss"], lb["loss"]) and all(torch.equal(la[k], lb[k]) for k in ("kl", "o_next", "v", "hf", "hb", "l_tr"))


def test_p_off_zero_draws_no_random_numbers_and_p_one_none():
    g = make_generator("cpu", 7)
    state = g.get_state().clone()
    glob = torch.get_rng_state().clone()

    assert not draw_map_off(100, 0.0, "cpu", g).any() and draw_map_off(100, 1.0, "cpu", g).all()
    assert torch.equal(g.get_state(), state) and torch.equal(torch.get_rng_state(), glob)
    draw_map_off(100, 0.5, "cpu", g)

    assert not torch.equal(g.get_state(), state) and torch.equal(torch.get_rng_state(), glob)        # 전용 난수열만 움직이고 전역은 그대로
    with pytest.raises(ValueError):
        draw_map_off(10, 1.5, "cpu", g)


# ---------------------------------------------------------------- (2) p_off 1 / 혼합: 지도 토큰이 정말 빠지는가

def _est_fn(p, n, map_off, hmap):
    z = torch.randn(n, 128, generator=torch.Generator().manual_seed(9))

    return p.ie.estimate(z, hmap, map_off)


def test_masked_rows_ignore_the_map_and_equal_the_prop_only_attention():
    torch.manual_seed(5)
    p = StartPerception(PerceptionCfg())
    ie = p.ie.eval()
    n = 4
    z = torch.randn(n, 128, generator=torch.Generator().manual_seed(9))
    h1 = torch.randn(n, 32, 16)
    h2 = torch.randn(n, 32, 16) * 3
    off = torch.tensor([True, True, False, False])
    o1, o2 = ie.estimate(z, h1, off), ie.estimate(z, h2, off)
    # 끈 행(0, 1)은 지도를 바꿔도 값이 안 변한다. 켠 행(2, 3)은 변한다
    assert torch.allclose(o1["mu"][:2], o2["mu"][:2], atol=1e-6) and not torch.allclose(o1["mu"][2:], o2["mu"][2:], atol=1e-4)
    # 끈 행 == 지도 토큰을 아예 안 넣은 attention (prop 토큰 하나만)
    prop = ie.prop_token(z).unsqueeze(1)
    ref = ie.attn(prop)[:, 0]
    h_ref = ie.heads(ref)
    assert torch.allclose(o1["mu"][:2], h_ref[:2, :16], atol=1e-5)
    # 혼합 batch 의 행 == 전부 켠 / 전부 끈 batch 의 같은 행
    all_on, all_off = ie.estimate(z, h1, torch.zeros(n, dtype=torch.bool)), ie.estimate(z, h1, torch.ones(n, dtype=torch.bool))
    assert torch.allclose(o1["mu"][2:], all_on["mu"][2:], atol=1e-5) and torch.allclose(o1["mu"][:2], all_off["mu"][:2], atol=1e-5)


def test_p_off_one_all_masked_means_the_map_does_not_matter_at_all():
    torch.manual_seed(6)
    ie = StartPerception(PerceptionCfg()).ie.eval()
    z = torch.randn(3, 128)
    off = torch.ones(3, dtype=torch.bool)
    a, b = ie.estimate(z, torch.randn(3, 32, 16), off), ie.estimate(z, torch.randn(3, 32, 16) * 9, off)

    assert all(torch.allclose(a[k], b[k], atol=1e-6) for k in a)
    assert ie.last_num_map_tokens == 128          # 토큰 자체는 있고 attention 키에서만 빠진다(모양 불변), 영향이 0 이라는 것은 위에서 확인


# ---------------------------------------------------------------- (3) 에피소드 안 유지 · reset 때 다시 뽑힘

def test_mask_is_kept_inside_an_episode_and_redrawn_only_for_reset_envs():
    p = StartPerception(PerceptionCfg())
    n = 8
    st = p.init_state(n, "cpu")
    g = make_generator("cpu", 11)
    st.map_off = draw_map_off(n, 0.5, "cpu", g)
    first = st.map_off.clone()
    for _ in range(5):                                          # reset 이 없으면 step 을 아무리 해도 유지
        p.step(st, p.ingest(st, torch.randn(n, 45), torch.rand(n, 60, 60)), torch.zeros(n, 32, 16), deterministic=True)

        assert torch.equal(st.map_off, first)
    reset = torch.zeros(n, dtype=torch.bool)
    reset[[0, 3]] = True
    new = ~first                                                # 일부러 전부 뒤집은 후보
    p.reset_envs(st, reset, torch.ones(n, dtype=torch.bool), new)

    assert st.map_off[0] == new[0] and st.map_off[3] == new[3]
    keep = ~reset

    assert torch.equal(st.map_off[keep], first[keep])           # reset 아닌 env 는 그대로
    p.reset_envs(st, reset, torch.ones(n, dtype=torch.bool))    # new_map_off 를 안 주면 건드리지 않는다(B 호출 모양)

    assert st.map_off[0] == new[0]


def test_realized_fraction_close_to_p_and_reproducible():
    n = 3072
    a = draw_map_off(n, 0.5, "cpu", make_generator("cpu", 20251025))
    b = draw_map_off(n, 0.5, "cpu", make_generator("cpu", 20251025))
    frac = float(a.float().mean())

    assert torch.equal(a, b) and abs(frac - 0.5) < 4 * (0.25 / n) ** 0.5


# ---------------------------------------------------------------- (4) update 경로의 마스크 일치 (결함 = rollout 끔 · update 켬)

def _schedule_two_resets(n):
    drawn = {}

    def schedule(t, st):
        if t == 0:
            st.map_off = torch.tensor([True, False] * (n // 2))
        if t == 4:                                              # 일부 env 가 reset 해서 새로 뽑힘
            st.map_off = torch.tensor([False, True, True, False, True, False][:n])
        drawn[t] = st.map_off.clone()

    return schedule, drawn


def test_replay_reproduces_the_rollout_estimate_with_the_same_mask():
    torch.manual_seed(7)
    p = StartPerception(PerceptionCfg())
    n, T = 6, 10
    sched, drawn = _schedule_two_resets(n)
    rb, ests, _ = _rollout(p, n, T, sched)
    batch = rb.gather(torch.arange(n))

    assert torch.equal(batch["map_off"][0], drawn[0]) and torch.equal(batch["map_off"][5], drawn[5]) and not torch.equal(batch["map_off"][0], batch["map_off"][5])
    eps0 = torch.zeros(T, n, 16)
    with torch.no_grad():
        replay = p.est_sequence(batch, eps0)                    # z = mu: 수집(deterministic) 과 같아야 한다

    assert torch.allclose(replay, ests, atol=1e-5), float((replay - ests).abs().max())


def test_guard_replay_without_the_mask_differs_from_the_rollout():
    """관문 확인: 재생이 마스크를 모르면(= rollout 끔 · update 켬) 추정이 어긋난다. 위 시험이 이 차이를 잡는다는 증거."""
    torch.manual_seed(7)
    p = StartPerception(PerceptionCfg())
    n, T = 6, 10
    sched, _ = _schedule_two_resets(n)
    rb, ests, _ = _rollout(p, n, T, sched)
    batch = rb.gather(torch.arange(n))
    stripped = {k: v for k, v in batch.items() if k != "map_off"}
    with torch.no_grad():
        replay = p.est_sequence(stripped, torch.zeros(T, n, 16))

    assert float((replay - ests).abs().max()) > 1e-3


@pytest.mark.parametrize("impl", ["a1", "a2", "a3"])
def test_fast_replay_paths_use_the_same_mask_as_the_loop(impl):
    torch.manual_seed(8)
    p = StartPerception(PerceptionCfg())
    n, T = 6, 10
    sched, _ = _schedule_two_resets(n)
    rb, _, _ = _rollout(p, n, T, sched)
    batch = rb.gather(torch.arange(n))
    eps = torch.randn(T, n, 16, generator=torch.Generator().manual_seed(2))
    ref = p.sequence_loss(batch, eps=eps, impl="loop")
    new = p.sequence_loss(batch, eps=eps, impl=impl)
    nomask = p.sequence_loss({k: v for k, v in batch.items() if k != "map_off"}, eps=eps, impl="loop")

    for k in ("kl", "o_next", "v", "hf", "hb", "loss"):
        assert abs(float(ref[k]) - float(new[k])) <= 1e-4, (impl, k)
    assert abs(float(ref["kl"]) - float(nomask["kl"])) > 1e-5               # 마스크가 손실에 실제로 영향을 준다(시험이 헛돌지 않는다)


def test_ppo_update_does_not_recompute_est_it_uses_the_stored_actor_obs():
    """PPO update 경로: 저장된 actor 입력(est 포함)만 쓰고 지각을 다시 부르지 않는다(소스 대조). 그래서 PPO 쪽에는 마스크 불일치가 생길 자리가 없다."""
    src = _src("foothold_s2/runners/start_runner.py")
    tree = ast.parse(src)
    learn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "learn")
    update_call = next(n for n in ast.walk(learn) if isinstance(n, ast.Call) and ast.unparse(n.func) == "self.alg.update")
    after = [n for n in ast.walk(learn) if isinstance(n, ast.Call) and getattr(n, "lineno", 0) > update_call.lineno and ast.unparse(n.func).startswith("self.perception.")]

    assert not any(ast.unparse(c.func) in ("self.perception.step", "self.perception.est_sequence") for c in after)
    assert "self.alg.process_env_step(ppo_obs" in src and "self.alg.act(ppo_obs)" in src            # 수집 때 만든 ppo_obs 가 act 와 저장 둘 다에 쓰인다


def test_runner_wiring_order_in_learn():
    src = _src("foothold_s2/runners/start_runner.py")

    assert "self.replay.add_pre(inp, o, gmap, gfeet, vel, self.pstate.use_gt, self.pstate.map_off)" in src
    i_add, i_step, i_rec, i_reset = (src.index(s) for s in ("self.replay.add_pre(", "raw, rewards, dones, extras = self.env.step", "self.map_switch.add_step(self.pstate.map_off", "self.perception.reset_envs(self.pstate"))

    assert i_add < i_step < i_rec < i_reset                     # 기록은 env.step 뒤 · reset_envs 앞(끝난 에피소드가 속한 집단으로 센다)
    assert "EX33_MAP_SWITCH p_off=" in src and "realized=" in src
    assert 'draw_map_off(n, self.p_map_off, self.device, self.map_switch_gen) if self.p_map_off > 0.0 else None' in src


# ---------------------------------------------------------------- 기록기

def test_recorder_counts_groups_with_known_inputs():
    rec = MapSwitchRecorder(4, "cpu")
    off = torch.tensor([True, True, False, False])
    lv = torch.tensor([1.0, 3.0, 5.0, 7.0])
    tl, ta = torch.tensor([0.5, 0.7, 0.1, 0.3]), torch.tensor([0.2, 0.4, 0.6, 0.8])
    rec.add_step(off, torch.tensor([1.0, 2.0, 3.0, 4.0]), torch.tensor([0, 1, 0, 0]), lv, tl, ta)
    rec.add_step(off, torch.tensor([1.0, 2.0, 3.0, 4.0]), torch.tensor([0, 0, 1, 1]), lv, tl, ta)
    s = rec.summary()

    assert s["steps"] == 2 and s["off_frac_steps"] == 0.5
    assert s["off"]["episodes_ended"] == 1 and s["off"]["ep_reward_mean"] == 2.0 and s["off"]["ep_length_mean"] == 1.0       # env1 은 첫 step 에서 끝남: 보상 2, 길이 1
    assert s["on"]["episodes_ended"] == 2 and s["on"]["ep_reward_mean"] == 7.0 and s["on"]["ep_length_mean"] == 2.0         # env2: 6, env3: 8
    assert s["off"]["terrain_level_mean"] == 2.0 and s["on"]["terrain_level_mean"] == 6.0
    assert s["off"]["track_lin_vel_per_s"] == pytest.approx(0.6) and s["on"]["track_ang_vel_per_s"] == pytest.approx(0.7)
    rec.reset_window()

    assert rec.summary()["off"]["episodes_ended"] == 0 and rec.summary()["off"]["ep_reward_mean"] != rec.summary()["off"]["ep_reward_mean"]     # NaN: 끝난 에피소드 없음


# ---------------------------------------------------------------- 계약 · cfg

def _plan(variant="SB", **changes):
    values = dict(variant=variant, task=TASKS[variant], agent="rsl_rl_cfg_entry_point", distributed=False, map_input="reconstruction", max_wall_s=3600,
                  end_by="2023-11-14T23:13:20+00:00", num_envs=3072, seed=42, max_iterations=1501, force_gt=False)
    values.update(changes)

    return SimpleNamespace(**values)


def test_sb_launch_contract():
    assert "SB" in BUDGET_VARIANTS and MAP_INPUT["SB"] == "reconstruction" and FORCE_GT["SB"] is True and CKPT_VARIANT["SB"] == "SB_map_switch"
    assert validate_launch(_plan(), now=NOW) == NOW + 3600
    assert validate_launch(_plan(smoke_updates=10), now=NOW) and validate_launch(_plan(smoke_updates=2, resume_from="x.pt"), now=NOW)
    for bad in (_plan(smoke_updates=2), _plan(smoke_updates=10, resume_from="x.pt"), _plan(smoke_updates=5), _plan(num_envs=1024), _plan(seed=1), _plan(max_iterations=1502),
                _plan(map_input="none"), _plan(p_map_off=0.0), _plan(p_map_off=1.0), _plan(task=TASKS["B"]), _plan("B", p_map_off=0.5)):
        with pytest.raises(ValueError):
            validate_launch(bad, now=NOW)
    assert validate_launch(_plan(p_map_off=0.3), now=NOW)
    assert validate_launch(_plan("B"), now=NOW)                                                      # B 규칙은 그대로
    with pytest.raises(ValueError):
        validate_launch(_plan("B", smoke_updates=2, resume_from="x.pt"), now=NOW)


def _class(rel, name):
    return next(n for n in ast.parse(_src(rel)).body if isinstance(n, ast.ClassDef) and n.name == name)


def test_cfg_differs_from_b_only_in_p_map_off_and_name():
    env = _class("foothold_s2/tasks/s2_sb_cfg.py", "FootholdS2SBEnvCfg")

    assert [ast.unparse(b) for b in env.bases] == ["FootholdS223FBEnvCfg"] and len(env.body) == 1 and isinstance(env.body[0], ast.Pass)
    agent = _class("foothold_s2/tasks/agents/s2_sb_ppo_cfg.py", "S2SBPPORunnerCfg")

    assert [ast.unparse(b) for b in agent.bases] == ["S223FBPPORunnerCfg"]
    post = next(n for n in agent.body if isinstance(n, ast.FunctionDef) and n.name == "__post_init__")

    assert ast.unparse(post.body[1]) == "self.perception = {**self.perception, 'p_map_off': P_MAP_OFF_DEFAULT}" and len(post.body) == 2
    assert "P_MAP_OFF_DEFAULT = 0.5" in _src("foothold_s2/tasks/agents/s2_sb_ppo_cfg.py")
    sets = [n.targets[0].id for n in agent.body if isinstance(n, ast.Assign)]

    assert sets == ["experiment_name"]


def test_registry_and_entry_point_for_sb():
    gym = pytest.importorskip("gymnasium")
    import foothold_s2.sb_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-SB-v0")

    assert spec.kwargs["env_cfg_entry_point"] == "foothold_s2.tasks.s2_sb_cfg:FootholdS2SBEnvCfg"
    assert spec.kwargs["rsl_rl_cfg_entry_point"] == "foothold_s2.tasks.agents.s2_sb_ppo_cfg:S2SBPPORunnerCfg"
    entry = _src("foothold_s2/scripts/train_sb.py")

    assert '"--task", "FootholdS2-Go2-S2-SB-v0", "--variant", "SB"' in entry


def test_b_cfg_friction_is_unchanged_in_this_branch():
    b = _src("foothold_s2/tasks/s2_23f_b_cfg.py")

    assert '"static_friction_range": (0.2, 1.2)' in b and '"dynamic_friction_range": (0.2, 1.2)' in b and '"make_consistent": True' in b


def test_default_p_map_off_is_zero_so_other_runs_are_b_behavior():
    src = _src("foothold_s2/runners/start_runner.py")

    assert '"p_map_off": 0.0' in src and "self.map_switch = MapSwitchRecorder(self.env.num_envs, device) if p_off > 0.0 else None" in src
    assert 'p_off > 0.0 and pcfg.get("map_input", "reconstruction") == "none"' in src


def test_installed_isaaclab_names_the_recorder_reads_exist():
    root = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab")
    if not root.exists():
        pytest.skip("Isaac Lab 소스 없음")
    rm = (root / "managers/reward_manager.py").read_text(encoding="utf-8")
    ti = (root / "terrains/terrain_importer.py").read_text(encoding="utf-8")

    assert "self._step_reward[:, term_idx] = value / dt" in rm and "def active_terms" in rm
    assert "self.terrain_levels" in ti


def test_wrappers_of_advance_accept_the_optional_last_argument():
    for rel, name in (("foothold_s2/runners/map_stats.py", "advance"), ("foothold_s2/eval/train_trace.py", "tapped_advance"), ("foothold_s2/eval/record_sol23f.py", "tapped_advance")):
        fn = next(n for n in ast.walk(ast.parse(_src(rel))) if isinstance(n, ast.FunctionDef) and n.name == name)

        assert fn.args.vararg is not None and len(fn.args.args) >= 8, rel


def test_run_script_shape():
    p = ROOT / "foothold_s2/run_sb.sh"
    raw = p.read_bytes()
    s = raw.decode("utf-8")

    assert b"\r" not in raw
    for must in ("train_sb.py", "--num_envs 3072", "--max_iterations 1501", "--seed 42", "--run_name sb-main", "CUDA_DEVICE_ORDER=PCI_BUS_ID", "--p_map_off", "P_OFF", "TRAIN_START_STATUS done"):
        assert must in s, must
    assert "--map_input" not in s
    r = subprocess.run([r"C:\Program Files\Git\bin\bash.exe", "-n", str(p)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)

    assert r.returncode == 0, r.stderr
