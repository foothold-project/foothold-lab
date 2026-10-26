"""DESIGN-MAPRATIO v0.2 7 절 M-T1 · M-T2 · M-T3 · M-T5 시험 (CPU, 가짜 env 로 실제 StartRunner 를 돌린다).

숫자(하한 · 폭 · 체류 · 회차)는 코드에 박혀 있지 않고 cfg 칸(`p_map_off_change` · `resume_adasmpl`)으로만 들어온다. 시험의 숫자는 시험 입력일 뿐이다.
M-T4(되돌림 인자 생성)는 judge_gate 가 있는 impl-judge 쪽(eval/mapratio_revert.py).
"""

import json

import pytest
import torch

from foothold_s2.runners.map_switch import MapSwitchRecorder, draw_map_off, make_generator
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

SEED = 20251025


class HookEnv(FakeStartEnv):
    """보상 · time_outs 를 시험이 바꿀 수 있는 가짜 env. hook(rewards, runner) 는 env.step 때 runner.pstate(그 step 의 map_off · use_gt)를 본다."""

    runner = None
    reward_hook = None
    timeout_even = False

    def step(self, actions):
        obs, rewards, dones, extras = super().step(actions)
        if self.reward_hook is not None:
            rewards = self.reward_hook(rewards, self.runner)
        if self.timeout_even:
            extras["time_outs"] = dones.bool() & (torch.arange(self.num_envs) % 2 == 0)

        return obs, rewards, dones, extras


def _runner(p=0.0, seed=0, n=16, T=24, log_dir=None, **perception):
    torch.manual_seed(seed)
    pc = {"microbatch_envs": 4, "p_map_off": p, **perception}
    env = HookEnv(num_envs=n, seed=seed)
    r = StartRunner(env, train_cfg(T, pc), log_dir=log_dir, device="cpu")
    env.runner = r

    return r


def _ckpt(tmp_path, name, p=0.5, iters=2, **perception):
    r = _runner(p, **perception)
    r.learn(iters)
    path = str(tmp_path / name)
    r.save(path)

    return r, path, torch.load(path, weights_only=False)["iter"]


# ---------------------------------------------------------------- M-T1: p_map_off 변경

def test_m_t1_different_p_without_the_argument_is_still_refused(tmp_path):
    _, path, _ = _ckpt(tmp_path, "a.pt", 0.5)

    with pytest.raises(ValueError, match="p_map_off"):
        _runner(0.3).load(path)


def test_m_t1_with_the_argument_it_passes_records_and_realizes_the_new_ratio(tmp_path, capsys):
    _, path, it = _ckpt(tmp_path, "a.pt", 0.5)
    r = _runner(0.3, p_map_off_change={"from_iter": it + 1, "to": 0.3, "from": 0.5}, log_dir=str(tmp_path))
    r.load(path)
    r.learn(1)
    out = capsys.readouterr().out
    ev = [e for e in r.map_ratio_events if e["kind"] == "p_map_off_change"]

    assert len(ev) == 1 and ev[0]["from"] == 0.5 and ev[0]["to"] == 0.3 and ev[0]["from_iter"] == it + 1 and ev[0]["rng"] == "continued"
    assert "MAP_RATIO_CHANGE from=0.5 to=0.3" in out
    lines = [json.loads(ln) for ln in (tmp_path / "map_ratio_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [ln["kind"] for ln in lines].count("p_map_off_change") == 1
    drawn = draw_map_off(3072, r.p_map_off, "cpu", r.map_switch_gen).float().mean().item()

    assert abs(drawn - 0.3) <= 0.03                                      # 새 값 ± 0.03 안 (M-T1 시험)


def test_m_t1_manifest_gets_the_event_and_the_diff_allows_that_field(tmp_path):
    from foothold_s2.runners import manifest as run_manifest

    _, path, it = _ckpt(tmp_path, "a.pt", 0.5)
    r = _runner(0.3, p_map_off_change={"from_iter": it + 1, "to": 0.3})
    r.load(path)
    m = {"run": {}, "files": {"imported_sha256": {}}, "checkpoints": {}}
    r.attach_manifest(str(tmp_path), m)

    chg = [e for e in m["map_ratio_events"] if e["kind"] == "p_map_off_change"]

    assert len(chg) == 1 and (chg[0]["from"], chg[0]["to"]) == (0.5, 0.3)
    assert "map_ratio_events" in run_manifest.ALLOWED_DIFF_PREFIXES


def test_m_t1_wrong_iteration_or_from_or_to_is_refused(tmp_path):
    _, path, it = _ckpt(tmp_path, "a.pt", 0.5)

    for bad_iter in (it, it + 2, 1):
        with pytest.raises(ValueError, match="from_iter"):
            _runner(0.3, p_map_off_change={"from_iter": bad_iter, "to": 0.3}).load(path)
    with pytest.raises(ValueError, match="from"):
        _runner(0.3, p_map_off_change={"from_iter": it + 1, "to": 0.3, "from": 0.4}).load(path)
    with pytest.raises(ValueError, match="to"):
        _runner(0.3, p_map_off_change={"from_iter": it + 1, "to": 0.2})                     # 인자의 to 와 p_map_off 가 어긋남(바꿀 값은 한 곳에서)
    with pytest.raises(ValueError, match="p_map_off_change"):
        _runner(0.3, p_map_off_change={"to": 0.3})


def test_m_t1_rng_rules_for_each_direction(tmp_path):
    a, path, it = _ckpt(tmp_path, "a.pt", 0.5)
    saved_next = draw_map_off(64, 0.3, "cpu", a.map_switch_gen)                           # 멈추지 않았다면 이어서 나왔을 다음 뽑기(같은 난수열)
    b = _runner(0.3, p_map_off_change={"from_iter": it + 1, "to": 0.3})
    b.load(path)

    assert torch.equal(draw_map_off(64, 0.3, "cpu", b.map_switch_gen), saved_next)       # 0.5 -> 0.3: 저장된 난수열 상태를 이어 쓴다
    z, zpath, zit = _ckpt(tmp_path, "z.pt", 0.0)
    c = _runner(0.3, p_map_off_change={"from_iter": zit + 1, "to": 0.3})
    c.load(zpath)

    assert [e for e in c.map_ratio_events if e["kind"] == "p_map_off_change"][0]["rng"] == "fresh_from_seed"
    assert torch.equal(draw_map_off(64, 0.3, "cpu", c.map_switch_gen), draw_map_off(64, 0.3, "cpu", make_generator("cpu", SEED)))   # 0 -> 0.3: 시드에서 새로
    d = _runner(0.0, p_map_off_change={"from_iter": it + 1, "to": 0.0})
    d.load(path)

    assert d.map_switch_gen is None and [e for e in d.map_ratio_events if e["kind"] == "p_map_off_change"][0]["rng"] == "none"             # 0.5 -> 0: 끔 난수열 없음


def test_m_t1_history_travels_in_the_checkpoint_and_a_later_resume_needs_no_argument(tmp_path):
    _, path, it = _ckpt(tmp_path, "a.pt", 0.5)
    b = _runner(0.3, p_map_off_change={"from_iter": it + 1, "to": 0.3})
    b.load(path)
    b.learn(1)
    path2 = str(tmp_path / "b.pt")
    b.save(path2)
    sd = torch.load(path2, weights_only=False)

    assert [(e["from"], e["to"]) for e in sd["map_switch"]["changes"]] == [(0.5, 0.3)]
    c = _runner(0.3)                                                                        # 인자 없음 + 같은 p: 통과(이전 값 이력은 그대로 이어받음)
    c.load(path2)

    assert [(e["from"], e["to"]) for e in c.map_switch_changes] == [(0.5, 0.3)] and not [e for e in c.map_ratio_events if e["kind"] == "p_map_off_change"]
    with pytest.raises(ValueError, match="p_map_off"):
        _runner(0.5).load(path2)                                                            # 되돌리려면 또 인자가 있어야 한다


# ---------------------------------------------------------------- M-T2: 끔 env 보상은 AdaSmpl CV 에서 제외

def _p_after_one_iter(p_off, off_reward, on_reward=None):
    r = _runner(p_off, seed=3, n=16)
    seen = []
    orig_add = r.adasmpl.add

    def rec(x):
        seen.append(x.clone())
        orig_add(x)

    r.adasmpl.add = rec

    def hook(rewards, runner):
        off = runner.pstate.map_off.bool()
        rewards = rewards.clone()
        rewards[off] = off_reward(rewards[off])
        if on_reward is not None:
            rewards[~off] = on_reward(rewards[~off])

        return rewards

    r.env.reward_hook = hook
    r.learn(1)

    return r.adasmpl.p, torch.cat(seen) if seen else torch.zeros(0)


def test_m_t2_changing_off_rewards_does_not_move_p_gt_but_changing_on_rewards_does():
    p_a, seen_a = _p_after_one_iter(0.5, lambda x: x)
    p_b, seen_b = _p_after_one_iter(0.5, lambda x: torch.zeros_like(x))                       # 끔 env 보상을 0 으로
    p_c, _ = _p_after_one_iter(0.5, lambda x: x, on_reward=lambda x: x * 7.0 - 3.0)             # 켬 env 보상만 바꿈

    assert p_a == p_b and torch.equal(seen_a, seen_b)
    assert p_a != p_c


def test_m_t2_off_episodes_are_not_added_and_the_count_is_smaller_than_the_done_count():
    r = _runner(0.5, seed=3, n=16)
    dones_total = []
    orig_step = r.env.step

    def step(a):
        out = orig_step(a)
        dones_total.append(int((out[2] > 0).sum()))

        return out

    r.env.step = step
    r.learn(1)
    seen = _p_after_one_iter(0.5, lambda x: x)[1]

    assert seen.numel() < sum(dones_total) and seen.numel() > 0


def test_m_t2_p_off_zero_is_the_b_behavior_every_done_episode_is_added():
    r = _runner(0.0, seed=3, n=16)
    seen = []
    orig_add = r.adasmpl.add
    r.adasmpl.add = lambda x: (seen.append(x.numel()), orig_add(x))[1]
    dones_total = []
    orig_step = r.env.step
    r.env.step = lambda a: (lambda out: (dones_total.append(int((out[2] > 0).sum())), out)[1])(orig_step(a))
    r.learn(1)

    assert sum(seen) == sum(dones_total)


def test_m_t2_guard_wiring_uses_the_pre_reset_map_off():
    src = open(__file__.replace("tests\\test_mapratio.py", "runners\\start_runner.py").replace("tests/test_mapratio.py", "runners/start_runner.py"), encoding="utf-8").read()
    i_add = src.index("self.adasmpl.add(cur_reward_sum[done_ids][~self.pstate.map_off[done_ids].bool()])")
    i_reset = src.index("self.perception.reset_envs(self.pstate")

    assert i_add < i_reset                                                                  # 분류는 reset_envs 가 map_off 를 새로 뽑기 전 값


# ---------------------------------------------------------------- M-T3: 기록기 확장

def test_m_t3_recorder_counts_causes_and_sources_with_known_inputs():
    rec = MapSwitchRecorder(4, "cpu")
    off = torch.tensor([True, True, False, False])
    gt = torch.tensor([True, False, True, False])
    rew = torch.ones(4)
    rec.add_step(off, rew, torch.tensor([1, 1, 0, 0]), None, None, None, torch.tensor([True, False, False, False]), gt)    # env0 시간 제한(끔), env1 낙상(끔)
    rec.add_step(off, rew, torch.tensor([0, 0, 1, 1]), None, None, None, torch.tensor([False, False, True, False]), gt)    # env2 시간 제한(켬), env3 낙상(켬)
    s = rec.summary()

    assert s["off"]["ended_timeout"] == 1 and s["off"]["ended_terminated"] == 1 and s["on"]["ended_timeout"] == 1 and s["on"]["ended_terminated"] == 1
    assert s["off"]["episodes_ended"] == 2 and s["on"]["episodes_ended"] == 2
    assert s["source_steps"] == {"gt": 2, "recon": 2, "off": 4, "total": 8}                  # 끔이 먼저, 켬이면서 정답 / 켬이면서 복원
    assert s["source_steps"]["total"] == s["on"]["env_steps"] + s["off"]["env_steps"] == 4 * s["steps"]
    rec.reset_window()
    rec.add_step(off, rew, torch.tensor([0, 0, 0, 0]))                                       # 원인 · 출처를 안 준 창은 None(0 으로 오해하지 않는다)

    assert rec.summary()["source_steps"] is None and rec.summary()["on"]["ended_timeout"] is None


def test_m_t3_runner_sums_equal_total_steps_and_causes_equal_ended():
    r = _runner(0.5, seed=3, n=16, T=24)
    r.env.timeout_even = True
    caught = {}
    orig = r.map_switch.summary
    r.map_switch.summary = lambda: caught.setdefault("s", orig())
    r.learn(1)
    s = caught["s"]

    assert s["source_steps"]["total"] == 16 * 24 == s["on"]["env_steps"] + s["off"]["env_steps"]
    for g in ("on", "off"):
        assert s[g]["ended_timeout"] + s[g]["ended_terminated"] == s[g]["episodes_ended"]
    assert s["on"]["ended_timeout"] + s["off"]["ended_timeout"] > 0                          # 시간 제한 분류가 실제로 들어왔다
    assert s["source_steps"]["off"] == s["off"]["env_steps"]


# ---------------------------------------------------------------- M-T5: resume 뒤 force_gt · p 덮어쓰기

def _gt_ckpt(tmp_path):
    r = _runner(0.0, n=64, force_gt=True)
    r.learn(1)
    path = str(tmp_path / "gt.pt")
    r.save(path)

    return path


def test_m_t5_without_the_argument_the_saved_force_gt_silently_returns_and_a_warning_is_printed(tmp_path, capsys):
    path = _gt_ckpt(tmp_path)
    r = _runner(0.0, n=64)                                                                   # 설정은 force_gt=False
    r.load(path)
    r.learn(1)
    out = capsys.readouterr().out
    first = [e for e in r.map_ratio_events if e["kind"] == "first_iter_sources"][-1]

    assert "RESUME_ADASMPL_WARN" in out and r.adasmpl.force_gt is True
    assert first["recon"] == 0 and first["gt"] == 64                                          # 저장본 값이 그대로 돌아와 복원 env 가 0


def _events(r, kind):
    return [e for e in r.map_ratio_events if e["kind"] == kind]


def test_m_t5_with_the_argument_first_iteration_is_all_gt_and_the_iteration_after_the_first_update_has_reconstruction(tmp_path):
    path = _gt_ckpt(tmp_path)
    r = _runner(0.0, n=64, resume_adasmpl={"force_gt": False})
    r.load(path)
    r.learn(2)
    first, ev = _events(r, "first_iter_sources")[-1], _events(r, "resume_adasmpl")[0]
    it0, it1 = _events(r, "iter_sources")
    upd = _events(r, "first_update_adasmpl")[0]

    assert first["recon"] == 0 and first["p"] == 1.0 and first["gt"] == 64                    # 첫 회차: 저장본 p 1.0 이라 전부 정답 지도(명세 v0.4)
    assert it0["recon_steps"] == 0 and it0["total"] == 64 * 24 and it0["p_start"] == 1.0
    assert 0.0 < upd["p_after"] < 1.0 and upd["cv"] is not None and upd["count"] >= 2           # 첫 update 에서 식 5 가 p 를 계산했다
    assert it1["recon_steps"] > 0 and it1["gt_steps"] + it1["recon_steps"] + it1["off_steps"] == it1["total"] == 64 * 24     # 첫 update 뒤 회차에 복원 env
    assert ev["applied"] and ev["saved"] == {"force_gt": True, "p": 1.0} and ev["after"] == {"force_gt": False, "p": 1.0}


def test_m_t5_p_in_the_argument_is_refused(tmp_path):
    with pytest.raises(ValueError, match="resume_adasmpl"):
        _runner(0.0, resume_adasmpl={"force_gt": False, "p": 0.5})


def test_m_t5_events_reach_the_jsonl_and_the_manifest(tmp_path):
    path = _gt_ckpt(tmp_path)
    r = _runner(0.0, n=64, resume_adasmpl={"force_gt": False}, log_dir=str(tmp_path / "run"))
    (tmp_path / "run").mkdir()
    m = {"run": {}, "files": {"imported_sha256": {}}, "checkpoints": {}}
    r.attach_manifest(str(tmp_path / "run"), m)
    r.load(path)
    r.learn(2)
    kinds = [json.loads(ln)["kind"] for ln in (tmp_path / "run" / "map_ratio_events.jsonl").read_text(encoding="utf-8").splitlines()]

    assert {"resume_adasmpl", "first_iter_sources", "iter_sources", "first_update_adasmpl"} <= set(kinds)
    assert "first_update_adasmpl" in [e["kind"] for e in m["map_ratio_events"]]


def test_m_t5_bad_arguments_are_refused():
    with pytest.raises(ValueError, match="resume_adasmpl"):
        _runner(0.0, resume_adasmpl={})
    with pytest.raises(ValueError, match="resume_adasmpl"):
        _runner(0.0, resume_adasmpl={"force_gt": False, "extra": 1})


def test_first_sources_sum_to_envs_with_off_envs_and_flush_never_duplicates_lines(tmp_path):
    (tmp_path / "run").mkdir()
    r = _runner(0.5, n=64, log_dir=str(tmp_path / "run"))
    r.learn(1)
    first = [e for e in r.map_ratio_events if e["kind"] == "first_iter_sources"][0]

    assert first["off"] > 0 and first["gt"] + first["recon"] + first["off"] == first["envs"] == 64
    r._flush_map_ratio_events()
    r._flush_map_ratio_events()
    lines = (tmp_path / "run" / "map_ratio_events.jsonl").read_text(encoding="utf-8").splitlines()

    assert len(lines) == len(r.map_ratio_events)


def test_iteration_sources_count_off_envs_apart_from_reconstruction(tmp_path):
    r0 = _runner(0.5, n=64)
    r0.learn(1)
    path = str(tmp_path / "o.pt")
    r0.save(path)
    r = _runner(0.5, n=64, resume_adasmpl={"force_gt": r0.adasmpl.force_gt})
    r.load(path)
    r.learn(2)
    it1 = _events(r, "iter_sources")[1]

    assert it1["off_steps"] > 0 and it1["recon_steps"] > 0 and it1["gt_steps"] + it1["recon_steps"] + it1["off_steps"] == 64 * 24


# ---------------------------------------------------------------- 실제 SBRunner 경로 (reviewer 막음 1)

def _sb(n=64, force_gt=False, **perception):
    from foothold_s2.runners.sol23f_runner import SBRunner

    torch.manual_seed(0)
    pc = {"microbatch_envs": 4, "p_map_off": 0.5, "force_gt": force_gt, **perception}
    env = HookEnv(num_envs=n, seed=0)
    r = SBRunner(env, train_cfg(24, pc), log_dir=None, device="cpu")
    env.runner = r

    return r


def _sb_gt_ckpt(tmp_path):
    r = _sb(force_gt=True)
    r.learn(1)
    path = str(tmp_path / "sbgt.pt")
    r.save(path)

    return path


def test_sbrunner_without_the_argument_still_refuses_a_force_gt_change(tmp_path):
    path = _sb_gt_ckpt(tmp_path)

    with pytest.raises(ValueError, match="force_gt mismatch"):
        _sb(force_gt=False).load(path)


def test_sbrunner_with_the_argument_reaches_reconstruction_after_the_first_update_and_records_the_real_value(tmp_path):
    path = _sb_gt_ckpt(tmp_path)
    r = _sb(force_gt=False, resume_adasmpl={"force_gt": False})
    r.load(path)
    r.learn(2)
    first = _events(r, "first_iter_sources")[-1]
    it0, it1 = _events(r, "iter_sources")
    path2 = str(tmp_path / "sb2.pt")
    r.save(path2)
    sd = torch.load(path2, weights_only=False)

    assert first["recon"] == 0 and first["p"] == 1.0 and it0["recon_steps"] == 0           # 첫 회차 복원 env 0 · p 1.0 기록
    assert it1["recon_steps"] > 0 and it1["off_steps"] > 0                                  # 첫 update 뒤 회차에 복원 env > 0 (p = tanh(CV) < 1)
    assert 0.0 < _events(r, "first_update_adasmpl")[0]["p_after"] < 1.0
    assert sd["sol23f"]["force_gt"] is False and sd["perception_cfg"]["force_gt"] is False and sd["adasmpl"]["force_gt"] is False   # 기록이 실제와 같다
    _sb(force_gt=False).load(path2)                                                       # 덮은 뒤의 저장본은 인자 없이도 이어 간다


def test_resume_adasmpl_force_gt_must_equal_the_configured_force_gt():
    with pytest.raises(ValueError, match="force_gt"):
        _sb(force_gt=True, resume_adasmpl={"force_gt": False})                  # 설정(yaml)이 True 로 남는 길을 막는다
