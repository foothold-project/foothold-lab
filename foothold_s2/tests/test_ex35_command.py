"""EX-35: S2a 명령 표집기 · walkturn_v1 계약 · 명령 시계 흩기 · 이어 가기 회차 확장. CPU, Kit 없음.

답을 아는 입력: 슬롯 비율 75 / 2.5 / 2.5 / 10 / 10 (200,000 표본, 0.3 %p 안), B(START) 명령 전부가 새 계약을 통과, vx 1.0 wz 0.5 는 거절, 흩기 U(0, 4 s) 영수증.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.runners.contracts import contract_bad_fn, start_contract_bad, walkturn_contract_bad
from foothold_s2.sol23f_contract import TASKS, budget_iterations, command_settings, is_extended_resume, resume_budget, validate_launch

PKG = Path(__file__).resolve().parents[1]
N = 200_000


def _s2a(n=N, seed=1):
    return mc.resample_walkturn(mc.make_generator(seed), n, mc.CommandParams(walkturn_mode=True))


def test_slot_ratios_are_75_2p5_2p5_10_10_within_0p3_points():
    out = _s2a()
    frac = {k: float((out["slot"] == i).float().mean()) for i, k in enumerate(mc.WT_SLOTS)}
    want = {"forward": 0.75, "walk_left": 0.025, "walk_right": 0.025, "spin_left": 0.10, "spin_right": 0.10}

    for k, v in want.items():
        assert abs(frac[k] - v) < 0.003, (k, frac[k])


def test_each_slot_has_its_own_value_ranges_and_vy_is_always_zero():
    out = _s2a()
    cmd, slot = out["cmd"], out["slot"]
    vx, vy, wz = cmd[:, 0], cmd[:, 1], cmd[:, 2]
    fwd, wl, wr, sl, sr = (slot == i for i in range(5))

    assert bool((vy == 0).all())
    assert bool((vx[fwd] >= 0.3).all() and (vx[fwd] <= 1.5).all() and (wz[fwd] == 0).all())
    assert bool((vx[wl | wr] >= 0.3).all() and (vx[wl | wr] <= 0.8).all())
    assert bool((wz[wl] >= 0.2).all() and (wz[wl] <= 0.5).all() and (wz[wr] <= -0.2).all() and (wz[wr] >= -0.5).all())
    assert bool((vx[sl | sr] == 0).all() and (wz[sl] >= 0).all() and (wz[sr] <= 0).all() and (wz[sl | sr].abs() <= 1.2).all())
    assert bool(out["spin"][sl | sr].all()) and not bool(out["spin"][fwd | wl | wr].any())


def test_resample_free_modes_dispatches_to_s2a_only_when_asked_and_start_is_unchanged():
    p_old = mc.CommandParams(start_mode=True)
    a = mc.resample_free_modes(mc.make_generator(5), 1000, p_old, 0)["cmd"]
    b = mc.resample_start(mc.make_generator(5), 1000, p_old)["cmd"]
    c = mc.resample_free_modes(mc.make_generator(5), 1000, mc.CommandParams(start_mode=True, walkturn_mode=True), 0)

    assert torch.equal(a, b) and "slot" in c and float((c["slot"] == 1).float().sum()) > 0
    assert float(((c["cmd"][:, 0] > 0) & (c["cmd"][:, 2] != 0)).float().sum()) > 0


def test_walkturn_contract_passes_every_start_command_and_every_s2a_command_and_rejects_the_known_bad_ones():
    start = mc.resample_start(mc.make_generator(2), N, mc.CommandParams(start_mode=True))["cmd"]

    assert not bool(walkturn_contract_bad(start).any()) and not bool(walkturn_contract_bad(_s2a()["cmd"]).any())
    bad = torch.tensor([[1.0, 0.0, 0.5], [0.6, 0.0, 0.6], [0.2, 0.0, 0.0], [0.5, 0.1, 0.0], [0.0, 0.0, 1.3], [1.6, 0.0, 0.0], [float("nan"), 0.0, 0.0], [0.9, 0.0, 0.01]])
    ok = torch.tensor([[0.5, 0.0, 0.5], [0.8, 0.0, -0.5], [0.0, 0.0, 1.2], [0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [0.3, 0.0, 0.2]])

    assert walkturn_contract_bad(bad).tolist() == [True] * 8 and walkturn_contract_bad(ok).tolist() == [False] * 6


def test_start_contract_still_rejects_walking_turns_so_the_two_contracts_are_not_confused():
    walk = torch.tensor([[0.5, 0.0, 0.3]])

    assert bool(start_contract_bad(walk)[0]) and not bool(walkturn_contract_bad(walk)[0])
    assert contract_bad_fn(None) is None and contract_bad_fn("start") is start_contract_bad and contract_bad_fn("walkturn_v1") is walkturn_contract_bad

    with pytest.raises(ValueError, match="모르는 명령 계약"):
        contract_bad_fn("walkturn_v2")


def test_new_task_mask_marks_only_walking_turns_under_s2a():
    p = mc.CommandParams(walkturn_mode=True)                                                          # start_mode 없이도 표식이 붙어야 한다
    out = mc.resample_walkturn(mc.make_generator(3), 20_000, p)
    mark = mc.new_task_mask(out["cmd"], p)

    assert bool((mark == ((out["slot"] == 1) | (out["slot"] == 2))).all())


def test_slot_ratios_must_sum_to_one():
    with pytest.raises(ValueError, match="합"):
        mc.resample_walkturn(mc.make_generator(0), 10, mc.CommandParams(walkturn_mode=True, wt_p_forward=0.8))


def test_clock_scatter_receipt_accepts_uniform_and_rejects_range_nan_and_concentration():
    t = mc.scatter_clock(mc.make_generator(7), 3072, 4.0)
    rc = mc.scatter_receipt(t)

    assert rc["ok"] and rc["in_range"] and rc["finite"] and 0.0 <= rc["min"] and rc["max"] <= 4.0 and rc["max_bin_frac"] < 0.30 and len(rc["bin_counts"]) == 4
    assert not mc.scatter_receipt(torch.full((3072,), 4.0))["ok"]                                       # 흩지 않은 상태(전부 4 s)는 집중도로 거절
    assert not mc.scatter_receipt(torch.tensor([1.0, float("nan")]))["ok"]
    assert not mc.scatter_receipt(torch.tensor([1.0, 4.5, 2.0, 3.0]))["ok"]
    assert not mc.scatter_receipt(torch.full((3072,), 0.5))["ok"]


class _Term:
    def __init__(self, receipt, on=True, ep="good"):
        self.cfg = SimpleNamespace(clock_scatter=on)
        self.scatter_receipt = receipt
        self.episode_scatter_receipt = mc.scatter_receipt(mc.scatter_episode(mc.make_generator(2), 3072, 1000).float() * 0.02, 20.0, bins=5) if ep == "good" else (mc.scatter_receipt(torch.zeros(3072), 20.0, bins=5) if ep == "zero" else None)


def _fake_runner(term):
    from foothold_s2.runners.start_runner import StartRunner

    msgs = []

    def invalid(it, msg):
        msgs.append(msg)
        raise RuntimeError(msg)

    r = SimpleNamespace(map_ratio_events=[], _command_term=lambda: term, _invalid=invalid)

    return StartRunner._record_command_receipts, r, msgs


def test_runner_records_the_scatter_receipt_once_and_stops_the_run_on_a_bad_one():
    fn, r, _ = _fake_runner(_Term(mc.scatter_receipt(mc.scatter_clock(mc.make_generator(1), 3072))))
    fn(r, 0)
    fn(r, 1)

    assert [e["kind"] for e in r.map_ratio_events] == ["command_clock_scatter", "episode_progress_scatter"] and r.map_ratio_events[0]["ok"] is True and r.map_ratio_events[1]["ok"] is True
    fn, r, msgs = _fake_runner(_Term(mc.scatter_receipt(torch.full((3072,), 4.0))))

    with pytest.raises(RuntimeError):
        fn(r, 0)
    assert "영수증 위반" in msgs[0]
    fn, r, msgs = _fake_runner(_Term(None))

    with pytest.raises(RuntimeError):
        fn(r, 0)
    fn, r, _ = _fake_runner(_Term(None, on=False))
    fn(r, 0)                                                                                          # 흩기를 켜지 않은 판은 아무것도 안 함

    assert r.map_ratio_events == []


def test_term_and_runner_wiring_by_source():
    cmd = (PKG / "commands/mixed_command.py").read_text(encoding="utf-8")
    run = (PKG / "runners/start_runner.py").read_text(encoding="utf-8")

    assert "self._maybe_scatter_clock(ids)" in cmd and "len(ids) != self.num_envs" in cmd and "self._stepped = True" in cmd and "clock_scatter: bool = False" in cmd
    assert "contract_fn = contract_bad_fn(self.pcfg[\"contract\"])" in run and "bad_now = contract_fn(consumed)" in run and "self._record_command_receipts(it)" in run
    assert 'extra["command_slots"] = slot_stats' in run


def _real_scatter_method():
    """mixed_command.py 의 `_maybe_scatter_clock` 을 소스에서 꺼내 그대로 실행한다(Kit 없이 isaaclab 을 import 할 수 없어서)."""
    import ast
    import textwrap

    src = (PKG / "commands/mixed_command.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_maybe_scatter_clock")
    ns = {"mc": mc}
    exec(textwrap.dedent(ast.get_source_segment(src, fn)), ns)

    return ns["_maybe_scatter_clock"]


def _fake_term(on=True, n=3072):
    env = SimpleNamespace(max_episode_length=1000, step_dt=0.02, episode_length_buf=torch.zeros(n, dtype=torch.long))
    return SimpleNamespace(cfg=SimpleNamespace(clock_scatter=on, resampling_time_range=(4.0, 4.0)), _stepped=False, num_envs=n, gen=mc.make_generator(11), device="cpu", _env=env,
                           time_left=torch.full((n,), 4.0), scatter_receipt=None, episode_scatter_receipt=None)


def test_real_scatter_method_survives_a_second_full_reset_before_learning_and_stops_after_the_first_step():
    fn = _real_scatter_method()
    t = _fake_term()
    ids = torch.arange(t.num_envs)
    fn(t, ids)
    first = t.time_left.clone()

    assert t.scatter_receipt["ok"] and float(first.std()) > 0.5
    t.time_left[:] = 4.0                                                                              # reset_segment_physics 의 reset 이 시계를 4 s 로 되돌림
    fn(t, ids)

    assert t.scatter_receipt["ok"] and float(t.time_left.std()) > 0.5 and not torch.equal(first, t.time_left)
    t._stepped = True
    t.time_left[:] = 4.0
    fn(t, ids)

    assert bool((t.time_left == 4.0).all())                                                           # 학습 시작 뒤에는 손대지 않는다
    t2 = _fake_term(on=False)
    fn(t2, torch.arange(t2.num_envs))

    assert bool((t2.time_left == 4.0).all()) and t2.scatter_receipt is None
    t3 = _fake_term()
    fn(t3, torch.arange(10))                                                                          # 일부 env 만 reset 하는 호출은 흩지 않음

    assert bool((t3.time_left == 4.0).all())


# ---------------------------------------------------------------- 이어 가기 회차 확장 (막음 2)


def _args(**kw):
    v = dict(variant="SB", task=TASKS["SB"], agent="rsl_rl_cfg_entry_point", distributed=False, map_input="reconstruction", max_wall_s=3600, end_by="2099-01-01T00:00:00+00:00",
             num_envs=3072, seed=42, max_iterations=1501, force_gt=False, smoke_updates=None, resume_from=None, p_map_off=None)
    v.update(kw)

    return SimpleNamespace(**v)


def test_old_launch_contract_is_unchanged_fresh_and_without_extension():
    validate_launch(_args())
    validate_launch(_args(max_iterations=None))

    for bad in (2001, 1000):
        with pytest.raises(ValueError, match="1501"):
            validate_launch(_args(max_iterations=bad))                                              # 새로 시작하는 판은 1501 고정
    with pytest.raises(ValueError, match="1501"):
        validate_launch(_args(max_iterations=2001, smoke_updates=2, resume_from="x.pt"))            # smoke 2 도 고정
    with pytest.raises(ValueError, match="1501"):
        validate_launch(_args(variant="B", task=TASKS["B"], max_iterations=2001, resume_from="x.pt"))   # B 는 건드리지 않음


def test_sb_resume_accepts_a_larger_total_and_records_the_budget_from_the_parent_iteration():
    a = _args(max_iterations=2001, resume_from="m1500.pt")
    validate_launch(a)

    assert is_extended_resume(a) and budget_iterations(a) == 2001 and budget_iterations(_args()) == 1501 and budget_iterations(_args(smoke_updates=10)) == 10
    assert resume_budget(2001, 1500) == {"parent_completed_update": 1500, "max_iterations": 2001, "remaining": 500}
    assert not is_extended_resume(_args(max_iterations=1501, resume_from="m.pt")) and not is_extended_resume(_args(max_iterations=1000, resume_from="m.pt"))

    with pytest.raises(ValueError, match="남은"):
        resume_budget(1501, 1500)                                                                    # 0 회: 학습 없이 done 이 되는 경우는 확장 판에서는 거절
    with pytest.raises(ValueError, match="남은"):
        resume_budget(4000, 1500)
    with pytest.raises(ValueError, match="1501"):
        validate_launch(_args(max_iterations=3002, resume_from="m.pt"))
    with pytest.raises(ValueError, match="1501"):
        validate_launch(_args(max_iterations=1000, resume_from="m.pt"))


def test_command_mode_and_scatter_are_sb_only_and_s2a_needs_a_parent():
    validate_launch(_args(command_mode="s2a", clock_scatter="on", max_iterations=2001, resume_from="m1500.pt"))
    validate_launch(_args(command_mode="start", clock_scatter="off"))

    with pytest.raises(ValueError, match="SB variant only"):
        validate_launch(_args(variant="B", task=TASKS["B"], command_mode="s2a"))
    with pytest.raises(ValueError, match="SB variant only"):
        validate_launch(_args(variant="B", task=TASKS["B"], clock_scatter="on"))
    with pytest.raises(ValueError, match="resume_from"):
        validate_launch(_args(command_mode="s2a", smoke_updates=10))
    with pytest.raises(ValueError, match="command_mode"):
        validate_launch(_args(command_mode="s2b"))
    assert command_settings(_args(command_mode="s2a", clock_scatter="on")) == {"command_mode": "s2a", "command_contract": "walkturn_v1", "clock_scatter": True}
    assert command_settings(_args()) == {"command_mode": "start", "command_contract": "start", "clock_scatter": False}


def test_common_script_applies_the_command_settings_before_gym_make_and_records_them():
    run = (PKG / "scripts/train_sol23f_common.py").read_text(encoding="utf-8")

    assert '--command_mode' in run and '--clock_scatter' in run and '"walkturn_mode": True' in run and "cmd_cfg.clock_scatter" in run
    assert run.index("cmd_cfg.clock_scatter") < run.index("gym.make(") and 'pc["contract"] = cmd_set["command_contract"]' in run
    assert '"resume_budget": budget' in run and '"command_settings": command_settings(args_cli)' in run and '"command_params"' in run
    assert run.index("pc[\"contract\"] = cmd_set") < run.index("train_cfg[\"perception\"] = pc")


def test_treatment_without_an_extended_resume_is_refused_instead_of_ending_as_done_with_zero_updates():
    for kw in (dict(command_mode="s2a"), dict(clock_scatter="on"), dict(command_mode="s2a", clock_scatter="on")):
        with pytest.raises(ValueError, match="0 updates"):
            validate_launch(_args(resume_from="m1500.pt", **kw))                                       # 2001 을 빠뜨린 이어 가기(1501)
        with pytest.raises(ValueError, match="0 updates"):
            validate_launch(_args(**kw))                                                               # 새로 시작
    validate_launch(_args(resume_from="m1500.pt", max_iterations=2001, command_mode="s2a", clock_scatter="on"))
    validate_launch(_args(resume_from="smoke10.pt", smoke_updates=2, max_iterations=None, command_mode="s2a", clock_scatter="on"))    # 짧은 Kit smoke 2 는 허용
    validate_launch(_args(command_mode="start", clock_scatter="off"))                                  # 처치 없음은 기존 그대로


def test_episode_progress_is_scattered_with_the_clock_and_its_receipt_rejects_synchronised_episodes():
    fn = _real_scatter_method()
    t = _fake_term()
    fn(t, torch.arange(t.num_envs))
    buf = t._env.episode_length_buf

    assert int(buf.min()) >= 0 and int(buf.max()) < 1000 and float(buf.float().std()) > 200 and t.episode_scatter_receipt["ok"] and t.episode_scatter_receipt["max_bin_frac"] < 0.30
    zero = _Term(mc.scatter_receipt(mc.scatter_clock(mc.make_generator(1), 3072)), ep="zero")
    f, r, msgs = _fake_runner(zero)

    with pytest.raises(RuntimeError):
        f(r, 0)
    assert "에피소드 진행도" in msgs[0]
    f, r, msgs = _fake_runner(_Term(mc.scatter_receipt(mc.scatter_clock(mc.make_generator(1), 3072)), ep="none"))

    with pytest.raises(RuntimeError):
        f(r, 0)


def test_zero_remaining_with_a_treatment_is_a_startup_error_not_done():
    run = (PKG / "scripts/train_sol23f_common.py").read_text(encoding="utf-8")

    assert "if remaining <= 0 and (command_settings(args_cli)" in run and "raise RuntimeError(f\"명령 처치를 켰는데 남은 회차가" in run and "학습 없이 done 이 되는 것을 막는다" in run and run.index("학습 없이 done 이 되는 것을 막는다") < run.index('"note": "이미 끝난 체크포인트"')
