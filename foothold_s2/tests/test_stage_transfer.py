"""SONNET-X25 T1: EX-30 · EX-31 부모 전환과 정확한 재개. CPU 만(Kit · CUDA 없음).

실제 부모(B model_1500.pt)는 읽기만 한다. 가짜 env 의 BRunner 로 만든 작은 부모로 runner 단계의 반례와 재개를 시험한다.
"""

import copy
import dataclasses
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
import yaml

from foothold_s2.runners import stage_transfer as st
from foothold_s2.runners.course_runner import Ex30Runner, Ex31Runner
from foothold_s2.runners.manifest import state_sha
from foothold_s2.runners.sol23f_runner import BRunner
from foothold_s2.runners.stage_transfer import TransferRefused, TransferSpec, child_meta, file_sha256, import_parent, restore_child
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

REAL_PARENT = Path("C:/mai/wt/foothold-lab/lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main/model_1500.pt")
REAL_SHA = "cb65ba5641ac7265664a02110c51f9a57b1427ecee74356870fcd462907c43b8"
DESIGN_STD = [0.4227981, 0.4260888, 0.4208926, 0.4199505, 0.5929094, 0.6068594, 0.5590993, 0.5543236, 0.6921880, 0.6299430, 0.6669349, 0.6491234]
CUR = "c" * 64


def _pcfg(force_gt, **extra):
    return {"microbatch_envs": 4, "map_input": "reconstruction", "force_gt": force_gt, "critic_mode": "clean52", "contract": "start", **extra}


def _env(seed=42, counter=0, level=0):
    """START 계약을 만족하는 명령 term 과 env 상태(카운터 · 지형 레벨)가 있는 가짜 env."""
    env = FakeStartEnv(num_envs=8, seed=seed)
    term = SimpleNamespace(vel_command_b=torch.tensor([[0.5, 0.0, 0.0]] * 8))
    env.command_manager = SimpleNamespace(get_term=lambda name: term)
    env.common_step_counter = counter
    env.scene = SimpleNamespace(terrain=SimpleNamespace(terrain_levels=torch.full((8,), level), terrain_types=torch.zeros(8, dtype=torch.long)))

    return env


def _runner(cls, tmp_path, force_gt, name="r", pcfg=None, seed=42, counter=0, level=0, algo=None, from_parent_agent=False):
    cfg = train_cfg(4, pcfg if pcfg is not None else _pcfg(force_gt))
    cfg["save_interval"] = 1000

    if from_parent_agent:
        cfg.update(copy.deepcopy({k: v for k, v in st.load_parent_agent_cfg(REAL_PARENT)[0].items() if k in st.AGENT_CFG_KEYS}))
    cfg["algorithm"].update(algo or {})

    return cls(_env(seed, counter, level), cfg, log_dir=str(tmp_path / name), device="cpu")


@pytest.fixture(scope="module")
def parent(tmp_path_factory):
    """가짜 env 의 B 부모(force_gt True)를 2 번 갱신해 저장한다(iter=1)."""
    tmp = tmp_path_factory.mktemp("parent")
    r = _runner(BRunner, tmp, True, "b", counter=777, level=5)                                                  # 부모 env 상태가 새 env 초기값(0)과 다르게
    r.learn(2)
    path = tmp / "b" / "model_1.pt"

    assert path.exists()
    (tmp / "b" / "params").mkdir()
    (tmp / "b" / "params" / "agent.yaml").write_text(yaml.safe_dump({k: r.cfg[k] for k in st.AGENT_CFG_KEYS if k in r.cfg}), encoding="utf-8")        # 실제 부모 폴더의 params/agent.yaml 자리
    sd = torch.load(path, weights_only=False)

    return {"path": path, "sha": file_sha256(path), "iter": sd["iter"], "allowed": (file_sha256(path),), "shapes": {"std": tuple(sd["model_state_dict"]["std"].shape),
            "actor.0.weight": tuple(sd["model_state_dict"]["actor.0.weight"].shape), "critic.0.weight": tuple(sd["model_state_dict"]["critic.0.weight"].shape)}}


def _spec(parent, exp="EX-30", seed=42, sha=None):
    return TransferSpec(parent_sha256=sha or parent["sha"], experiment_id=exp, map_policy=st.EXPERIMENT_MAP[exp], seed=seed, curriculum_spec_sha256=CUR)


# ------------------------------------------------------------------ 실제 부모 (읽기만)
@pytest.mark.skipif(not REAL_PARENT.exists(), reason="실제 B 부모 없음")
def test_real_parent_import_matches_the_design_numbers_and_is_untouched():
    before = file_sha256(REAL_PARENT)

    assert before == REAL_SHA
    results = {}
    for exp in ("EX-30", "EX-31"):
        results[exp] = import_parent(REAL_PARENT, TransferSpec(REAL_SHA, exp, st.EXPERIMENT_MAP[exp], 42, CUR))

    a, b = results["EX-30"], results["EX-31"]

    assert a.parent_iter == b.parent_iter == 1500 and a.parent_completed_updates == 1501 and a.new_completed_updates == 0
    assert [round(x, 7) for x in a.receipt["action_std"]] == pytest.approx(DESIGN_STD, abs=2e-7)                    # 설계 §2.1 의 std 12 개 그대로
    assert a.ppo_learning_rate == pytest.approx(0.00038443359375000017) and a.perception_learning_rate == pytest.approx(0.0005)
    assert a.receipt["state_sha"] == b.receipt["state_sha"]                                                         # 모델 · optimizer · LR · 지각이 두 판에서 같다
    assert a.adasmpl_state["force_gt"] is False and b.adasmpl_state["force_gt"] is True and a.adasmpl_state["p"] == b.adasmpl_state["p"] == 1.0
    assert a.adasmpl_state["count"] == 0.0 and a.perception_cfg["force_gt"] is False and b.perception_cfg["force_gt"] is True
    assert {k: v for k, v in a.perception_cfg.items() if k != "force_gt"} == {k: v for k, v in b.perception_cfg.items() if k != "force_gt"}
    assert a.receipt["parent_env_state_discarded"] and "env_state" in a.explicit_reset_fields
    assert file_sha256(REAL_PARENT) == before                                                                       # 부모 파일은 그대로


@pytest.mark.skipif(not REAL_PARENT.exists(), reason="실제 B 부모 없음")
def test_real_parent_refused_by_ordinary_resume_with_force_gt_false(tmp_path):
    """기존 resume 검사는 그대로다: force_gt False 인 runner 가 부모를 일반 load 하면 거절한다."""
    r = _runner(BRunner, tmp_path, False)

    with pytest.raises(ValueError, match="force_gt mismatch"):
        r.load(str(REAL_PARENT))


# ------------------------------------------------------------------ 반례
def test_importer_refuses_wrong_sha_and_bad_pairs(parent):
    with pytest.raises(TransferRefused, match="SHA"):
        import_parent(parent["path"], _spec(parent, sha="0" * 64), shapes=parent["shapes"], allowed_parent_shas=parent["allowed"])
    with pytest.raises(TransferRefused, match="짝"):
        import_parent(parent["path"], TransferSpec(parent["sha"], "EX-30", "gt", 42, CUR), shapes=parent["shapes"], allowed_parent_shas=parent["allowed"])
    with pytest.raises(TransferRefused, match="짝"):
        import_parent(parent["path"], TransferSpec(parent["sha"], "EX-99", "adaptive", 42, CUR), shapes=parent["shapes"], allowed_parent_shas=parent["allowed"])
    with pytest.raises(TransferRefused, match="seed"):
        import_parent(parent["path"], _spec(parent, seed=True), shapes=parent["shapes"], allowed_parent_shas=parent["allowed"])


def test_importer_refuses_wrong_dimension_other_model_and_nonfinite(parent, tmp_path):
    with pytest.raises(TransferRefused, match="모양"):
        import_parent(parent["path"], _spec(parent), shapes={**parent["shapes"], "actor.0.weight": (512, 97)}, allowed_parent_shas=parent["allowed"])
    sd = torch.load(parent["path"], weights_only=False)

    def variant(mod, name):
        s = copy.deepcopy(sd)
        mod(s)
        p = tmp_path / name
        torch.save(s, p)

        return p, file_sha256(p)

    p, sha = variant(lambda s: s["sol23f"].update(variant="START_TopDown"), "other_model.pt")

    with pytest.raises(TransferRefused, match="variant"):
        import_parent(p, _spec(parent, sha=sha), shapes=parent["shapes"], allowed_parent_shas=(sha,))

    p, sha = variant(lambda s: s["sol23f"].update(initial_snapshot=True), "initial.pt")

    with pytest.raises(TransferRefused, match="snapshot"):
        import_parent(p, _spec(parent, sha=sha), shapes=parent["shapes"], allowed_parent_shas=(sha,))

    p, sha = variant(lambda s: s["model_state_dict"]["std"].__setitem__(0, float("nan")), "nan.pt")

    with pytest.raises(TransferRefused, match="NaN"):
        import_parent(p, _spec(parent, sha=sha), shapes=parent["shapes"], allowed_parent_shas=(sha,))

    p, sha = variant(lambda s: s.pop("optimizer_state_dict"), "no_opt.pt")

    with pytest.raises(TransferRefused, match="optimizer_state_dict"):
        import_parent(p, _spec(parent, sha=sha), shapes=parent["shapes"], allowed_parent_shas=(sha,))

    p, sha = variant(lambda s: s.update(format="other"), "format.pt")

    with pytest.raises(TransferRefused, match="START"):
        import_parent(p, _spec(parent, sha=sha), shapes=parent["shapes"], allowed_parent_shas=(sha,))


# ------------------------------------------------------------------ 정상: 두 판이 같고 처치만 다르다
def test_two_children_start_identical_except_the_map_policy(parent, tmp_path):
    a, b = _runner(Ex30Runner, tmp_path, False, "a"), _runner(Ex31Runner, tmp_path, True, "b")
    ra, rb = a.begin_from_parent(parent["path"], _spec(parent, "EX-30"), parent["shapes"], parent["allowed"]), b.begin_from_parent(parent["path"], _spec(parent, "EX-31"), parent["shapes"], parent["allowed"])

    assert state_sha(a.alg.policy.state_dict()) == state_sha(b.alg.policy.state_dict()) == ra["state_sha"]["model"] == rb["state_sha"]["model"]
    assert state_sha(a.alg.optimizer.state_dict()) == state_sha(b.alg.optimizer.state_dict()) == ra["state_sha"]["optimizer"]
    assert state_sha(a.perception.state_dict()) == state_sha(b.perception.state_dict())
    assert state_sha(a.perception_optimizer.state_dict()) == state_sha(b.perception_optimizer.state_dict())
    assert a.alg.learning_rate == b.alg.learning_rate and a.current_learning_iteration == b.current_learning_iteration == parent["iter"]
    x = torch.randn(5, a.alg.policy.actor[0].in_features, generator=torch.Generator().manual_seed(1))

    assert torch.equal(a.alg.policy.actor(x), b.alg.policy.actor(x))                                               # 같은 입력이면 출력 같음
    assert bool(a.adasmpl.sample(64, "cpu").all()) and bool(b.adasmpl.sample(64, "cpu").all())                      # 첫 GT mask 는 두 판 모두 True
    assert a.adasmpl.force_gt is False and b.adasmpl.force_gt is True
    assert {k: v for k, v in a.pcfg.items() if k != "force_gt"} == {k: v for k, v in b.pcfg.items() if k != "force_gt"} and a.pcfg["force_gt"] != b.pcfg["force_gt"]     # 두 자식 runner 의 실제 cfg(부모 dict 가 아니라)
    ca, cb = dataclasses.asdict(a.perception.cfg), dataclasses.asdict(b.perception.cfg)

    assert {k: v for k, v in ca.items() if k != "force_gt"} == {k: v for k, v in cb.items() if k != "force_gt"} and ca["force_gt"] is False and cb["force_gt"] is True


def test_only_mainline_can_move_p_after_the_first_valid_update(parent, tmp_path):
    a, b = _runner(Ex30Runner, tmp_path, False, "a"), _runner(Ex31Runner, tmp_path, True, "b")
    a.begin_from_parent(parent["path"], _spec(parent, "EX-30"), parent["shapes"], parent["allowed"])
    b.begin_from_parent(parent["path"], _spec(parent, "EX-31"), parent["shapes"], parent["allowed"])

    for r in (a, b):
        r.adasmpl.add(torch.tensor([0.1, 5.0, 0.2, 3.0]))
        r.adasmpl.update()

    assert a.adasmpl.p < 1.0 and b.adasmpl.p == 1.0


def test_importer_alone_does_not_touch_env_state_rng_or_counters(parent, tmp_path):
    r = _runner(Ex30Runner, tmp_path, False)                                                                       # 새 env: 카운터 0 · 지형 레벨 0 (부모 env 는 777 · 5)
    rng_before = torch.get_rng_state().clone()
    r.begin_from_parent(parent["path"], _spec(parent), parent["shapes"], parent["allowed"])
    sd = torch.load(parent["path"], weights_only=False)

    assert sd["env_state"]["common_step_counter"] == 777 and int(sd["env_state"]["terrain_levels"][0]) == 5          # 부모에는 실제로 다른 값이 있었다
    assert torch.equal(torch.get_rng_state(), rng_before)
    assert r.env.common_step_counter == 0 and bool((r.env.scene.terrain.terrain_levels == 0).all())                 # 전환은 env 상태를 가져오지 않는다
    assert r.stage_transfer["parent_iter"] == parent["iter"]

    with pytest.raises(TransferRefused, match="이미"):
        r.begin_from_parent(parent["path"], _spec(parent), parent["shapes"], parent["allowed"])


def test_runner_force_gt_must_match_the_map_policy(parent, tmp_path):
    with pytest.raises(TransferRefused, match="force_gt"):
        _runner(Ex30Runner, tmp_path, True).begin_from_parent(parent["path"], _spec(parent, "EX-30"), parent["shapes"], parent["allowed"])
    with pytest.raises(TransferRefused, match="force_gt"):
        _runner(Ex31Runner, tmp_path, False).begin_from_parent(parent["path"], _spec(parent, "EX-31"), parent["shapes"], parent["allowed"])


# ------------------------------------------------------------------ 재개
def test_child_resume_continues_numbering_and_counters(parent, tmp_path):
    spec = _spec(parent)
    r = _runner(Ex30Runner, tmp_path, False, "run")
    r.begin_from_parent(parent["path"], spec, parent["shapes"], parent["allowed"])
    k = 3
    r.learn(k)
    P = parent["iter"]
    path = tmp_path / "run" / f"model_{P + k}.pt"                                                                  # model_{부모 번호 + k}

    assert path.exists() and r.current_learning_iteration == P + k
    sd = torch.load(path, weights_only=False)
    meta = sd["stage_transfer"]

    assert meta["parent_completed_updates"] == P + 1 and meta["new_completed_updates"] == k and meta["total_completed_updates"] == P + 1 + k
    assert meta == child_meta(spec, P, P + k)
    steps_before = {id(p): s.get("step") for p, s in r.alg.optimizer.state.items()}
    r2 = _runner(Ex30Runner, tmp_path, False, "run2")
    r2.set_spec(spec, P)
    r2.load(str(path))

    assert r2.current_learning_iteration == P + k and r2._resumed
    assert state_sha(r2.alg.policy.state_dict()) == state_sha(sd["model_state_dict"]) and state_sha(r2.alg.optimizer.state_dict()) == state_sha(sd["optimizer_state_dict"])
    assert r2.alg.learning_rate == sd["ppo_learning_rate"]
    assert {p.dtype for p in r2.alg.policy.parameters()} == {torch.float32} and {p.device.type for p in r2.alg.policy.parameters()} == {"cpu"}
    old_steps = sorted(float(s["step"]) for s in r2.alg.optimizer.state.values())
    r2.learn(1)
    new_steps = sorted(float(s["step"]) for s in r2.alg.optimizer.state.values())

    assert r2.current_learning_iteration == P + k + 1                                                              # 추가 k 다음 갱신은 한 번 더(번호 이어짐)
    assert all(n > o for n, o in zip(new_steps, old_steps)) and steps_before
    assert (tmp_path / "run2" / f"model_{P + k + 1}.pt").exists()
    meta2 = torch.load(tmp_path / "run2" / f"model_{P + k + 1}.pt", weights_only=False)["stage_transfer"]

    assert meta2["new_completed_updates"] == k + 1 and meta2["total_completed_updates"] == P + 1 + k + 1


def test_restore_child_refuses_parent_wrong_spec_and_tampered_counts(parent, tmp_path):
    spec = _spec(parent)

    with pytest.raises(TransferRefused, match="자식 체크포인트가 아니다"):
        restore_child(parent["path"], spec.sha256())

    r = _runner(Ex30Runner, tmp_path, False, "run")
    r.begin_from_parent(parent["path"], spec, parent["shapes"], parent["allowed"])
    r.learn(1)
    path = tmp_path / "run" / f"model_{parent['iter'] + 1}.pt"

    assert restore_child(path, spec.sha256()).meta["new_completed_updates"] == 1

    with pytest.raises(TransferRefused, match="spec SHA"):
        restore_child(path, _spec(parent, "EX-31").sha256())
    with pytest.raises(TransferRefused, match="spec SHA"):
        restore_child(path, _spec(parent, seed=7).sha256())

    sd = torch.load(path, weights_only=False)
    sd["stage_transfer"]["new_completed_updates"] = 5
    bad = tmp_path / "bad.pt"
    torch.save(sd, bad)

    with pytest.raises(TransferRefused, match="어긋난다"):
        restore_child(bad, spec.sha256())

    r3 = _runner(Ex30Runner, tmp_path, False, "run3")

    with pytest.raises(TransferRefused, match="set_spec"):
        r3.load(str(path))

    r3.set_spec(spec, parent["iter"] + 9)

    with pytest.raises(TransferRefused, match="부모 번호"):
        r3.load(str(path))


def test_ordinary_load_paths_still_reject_the_other_kind(parent, tmp_path):
    """자식 runner 의 일반 load 는 부모 체크포인트를 받지 않고, 전환 기록 없이는 저장도 하지 않는다."""
    r = _runner(Ex30Runner, tmp_path, False, "a")
    r.set_spec(_spec(parent), parent["iter"])

    with pytest.raises(TransferRefused):
        r.load(str(parent["path"]))

    fresh = _runner(Ex30Runner, tmp_path, False, "f")

    with pytest.raises(TransferRefused, match="전환 기록 없이"):
        fresh.state_dict()


def test_sol23f_runner_is_untouched():
    import subprocess

    root = Path(__file__).resolve().parents[2]
    out = subprocess.run(["git", "diff", "--stat", "d9517fb9", "--", "foothold_s2/runners/sol23f_runner.py"], capture_output=True, text=True, cwd=root).stdout

    assert out.strip() == ""


# ------------------------------------------------------------------ 막음 1: 학습 0 회 자식
def test_zero_or_negative_extra_updates_are_refused_at_start(parent, tmp_path):
    for n in (0, -1):
        r = _runner(Ex30Runner, tmp_path, False, f"z{n}")
        r.begin_from_parent(parent["path"], _spec(parent), parent["shapes"], parent["allowed"])

        with pytest.raises(TransferRefused, match="<= 0"):
            r.learn(n)

        assert not list((tmp_path / f"z{n}").glob("model_*.pt"))                                                   # 저장 파일 없음


def test_child_with_no_finished_update_cannot_be_saved(parent, tmp_path):
    r = _runner(Ex30Runner, tmp_path, False, "s")
    r.begin_from_parent(parent["path"], _spec(parent), parent["shapes"], parent["allowed"])

    with pytest.raises(TransferRefused, match="0 회"):
        r.state_dict()
    with pytest.raises(TransferRefused, match="0 회"):
        r.save(str(tmp_path / "s" / "x.pt"))

    r.current_learning_iteration += 1                                                                             # learn(0) 이 하던 일: 회차만 올림
    with pytest.raises(TransferRefused):
        r.state_dict()


def test_learn_zero_bypassing_the_start_check_still_cannot_save(parent, tmp_path):
    """기동 검사를 우회해 StartRunner.learn(0) 을 부르면 회차만 오르고 마지막 저장이 거절돼야 한다(두 번째 문)."""
    from foothold_s2.runners.start_runner import StartRunner

    r = _runner(Ex30Runner, tmp_path, False, "bypass")
    r.begin_from_parent(parent["path"], _spec(parent), parent["shapes"], parent["allowed"])

    with pytest.raises(TransferRefused, match="0 회"):
        StartRunner.learn(r, 0)

    assert not list((tmp_path / "bypass").glob("model_*.pt"))


# ------------------------------------------------------------------ 막음 2: 허용 목록
@pytest.mark.parametrize("extra", [{"critic_mode": "legacy"}, {"est_mode": "zero"}, {"microbatch_envs": 8}, {"contract": None}, {"log_kl": True}, {"stop_on_nonfinite": True}])
def test_cfg_outside_the_allow_list_is_refused(parent, tmp_path, extra):
    r = _runner(Ex30Runner, tmp_path, False, pcfg=_pcfg(False, **extra))

    with pytest.raises(TransferRefused, match="밖의 cfg"):
        r.begin_from_parent(parent["path"], _spec(parent), parent["shapes"], parent["allowed"])

    assert r.stage_transfer is None


def test_depth_delay_ticks_must_match_the_parent(parent, tmp_path):
    r = _runner(Ex30Runner, tmp_path, False, pcfg=_pcfg(False, depth_delay_ticks=0))

    with pytest.raises(TransferRefused, match="depth_delay_ticks"):
        r.begin_from_parent(parent["path"], _spec(parent), parent["shapes"], parent["allowed"])


def test_map_input_must_match_the_parent(parent, tmp_path):
    r = _runner(Ex30Runner, tmp_path, False, pcfg=_pcfg(False, map_input="none"))

    with pytest.raises(TransferRefused):
        r.begin_from_parent(parent["path"], _spec(parent), parent["shapes"], parent["allowed"])


def test_allow_list_accepts_treatment_and_the_operational_keys(parent, tmp_path):
    ops = {k: "x" for k in st.OPERATIONAL_KEYS}                                                                    # 운영 칸 다섯: 달라도 통과
    a = _runner(Ex30Runner, tmp_path, False, "a", pcfg=_pcfg(False, **ops))
    b = _runner(Ex31Runner, tmp_path, True, "b")                                                                   # 처치(force_gt)만 다름

    a.begin_from_parent(parent["path"], _spec(parent, "EX-30"), parent["shapes"], parent["allowed"])
    b.begin_from_parent(parent["path"], _spec(parent, "EX-31"), parent["shapes"], parent["allowed"])

    assert a.stage_transfer and b.stage_transfer


# ------------------------------------------------------------------ 고침
def test_runner_class_must_match_the_spec_experiment(parent, tmp_path):
    with pytest.raises(TransferRefused, match="실험"):
        _runner(Ex31Runner, tmp_path, False).begin_from_parent(parent["path"], _spec(parent, "EX-30"), parent["shapes"], parent["allowed"])
    with pytest.raises(TransferRefused, match="실험"):
        _runner(Ex30Runner, tmp_path, True).begin_from_parent(parent["path"], _spec(parent, "EX-31"), parent["shapes"], parent["allowed"])


def test_spec_seed_must_match_the_env_seed(parent, tmp_path):
    r = _runner(Ex30Runner, tmp_path, False, seed=7)

    with pytest.raises(TransferRefused, match="seed"):
        r.begin_from_parent(parent["path"], _spec(parent, seed=42), parent["shapes"], parent["allowed"])


def test_parent_must_be_in_the_allowed_sha_list(parent):
    """기본 허용 목록은 설계 §2.1 의 B model_1500 하나다: 같은 실행의 다른 회차는 SHA 를 맞게 적어도 거절."""
    other = REAL_PARENT.parent / "model_1450.pt"

    if not other.exists():
        pytest.skip("B model_1450 없음")

    with pytest.raises(TransferRefused, match="허용 목록"):
        import_parent(other, TransferSpec(file_sha256(other), "EX-30", "adaptive", 42, CUR))
    with pytest.raises(TransferRefused, match="허용 목록"):
        import_parent(parent["path"], _spec(parent))                                                               # 가짜 부모도 기본 목록에서는 거절


def test_set_spec_alone_does_not_open_the_save_gate(parent, tmp_path):
    spec = _spec(parent)
    r = _runner(Ex30Runner, tmp_path, False, "g")
    r.set_spec(spec, parent["iter"])

    with pytest.raises(TransferRefused, match="전환 기록 없이"):
        r.state_dict()
    with pytest.raises(TransferRefused, match="전환"):
        r.learn(1)                                                                                                 # load 없이 학습하면 무작위 가중치가 자식으로 저장될 길

    assert not list((tmp_path / "g").glob("model_*.pt"))
    with pytest.raises(TransferRefused, match="실험"):
        _runner(Ex31Runner, tmp_path, True, "g2").set_spec(spec, parent["iter"])


def test_nan_in_the_perception_optimizer_state_is_refused(parent, tmp_path):
    sd = torch.load(parent["path"], weights_only=False)
    states = sd["perception_optimizer_state_dict"]["state"]
    first = next(iter(states.values()))
    key = "exp_avg_sq"
    first[key] = first[key].clone()
    first[key].view(-1)[0] = float("inf")
    p = tmp_path / "perc_inf.pt"
    torch.save(sd, p)
    sha = file_sha256(p)

    with pytest.raises(TransferRefused, match="NaN"):
        import_parent(p, _spec(parent, sha=sha), shapes=parent["shapes"], allowed_parent_shas=(sha,))


def test_failed_apply_marks_the_runner_broken(parent, tmp_path):
    r = _runner(Ex30Runner, tmp_path, False, "bk")
    result = import_parent(parent["path"], _spec(parent), shapes=parent["shapes"], allowed_parent_shas=parent["allowed"])
    result.optimizer_state = {"state": {}, "param_groups": []}                                                      # optimizer load 가 도중에 실패하도록

    with pytest.raises(Exception):
        st.apply_transfer(r, result, _spec(parent))

    assert r._transfer_broken is True and r.stage_transfer is None

    with pytest.raises(TransferRefused):
        r.state_dict()


# ------------------------------------------------------------------ 고침 6: 실제 부모 pcfg(contract=start) 를 runner 단계에 쓴다
@pytest.mark.skipif(not REAL_PARENT.exists(), reason="실제 B 부모 없음")
def test_real_parent_pcfg_through_both_children_and_one_update(tmp_path, monkeypatch):
    from foothold_s2.runners import start_runner as sr

    real = torch.load(REAL_PARENT, weights_only=False, map_location="cpu")["perception_cfg"]
    assert real["contract"] == "start" and real["force_gt"] is True
    monkeypatch.setattr(sr.RewardSplit, "attach", lambda self, env: None)                                          # 가짜 env 에는 reward manager 가 없다(기록 장치만 끔)
    out = {}
    for cls, exp in ((Ex30Runner, "EX-30"), (Ex31Runner, "EX-31")):
        gt = exp == "EX-31"
        spec = TransferSpec(REAL_SHA, exp, st.EXPERIMENT_MAP[exp], 42, CUR)
        r = _runner(cls, tmp_path, gt, exp, pcfg={**real, "force_gt": gt}, from_parent_agent=True)                      # PPO · 정책 cfg 도 실제 부모 params/agent.yaml 그대로
        r.begin_from_parent(REAL_PARENT, spec)

        assert r.pcfg["contract"] == "start" and r.pcfg["force_gt"] is gt and r.current_learning_iteration == 1500
        out[exp] = r

    assert state_sha(out["EX-30"].alg.policy.state_dict()) == state_sha(out["EX-31"].alg.policy.state_dict())
    assert state_sha(out["EX-30"].perception_optimizer.state_dict()) == state_sha(out["EX-31"].perception_optimizer.state_dict())
    out["EX-30"].learn(1)                                                                                         # contract=start 로 실제 명령 term 을 거쳐 1 회 학습

    saved = torch.load(tmp_path / "EX-30" / "model_1501.pt", weights_only=False)

    assert saved["stage_transfer"]["new_completed_updates"] == 1 and saved["stage_transfer"]["total_completed_updates"] == 1502
    assert saved["perception_cfg"]["force_gt"] is False and saved["adasmpl"]["force_gt"] is False


def test_parent_depth_delay_recorded_in_sol23f_must_match_the_child(parent, tmp_path):
    """pcfg 에 없는 칸: 부모 sol23f 기록의 depth_delay_ticks 가 자식 perception.cfg 와 다르면 거절(pcfg 대조와 별개 문)."""
    sd = torch.load(parent["path"], weights_only=False)
    sd["sol23f"]["depth_delay_ticks"] = 0
    p = tmp_path / "delay0_parent.pt"
    torch.save(sd, p)
    shutil.copy(Path(parent["path"]).parent / "params" / "agent.yaml", (tmp_path / "params").mkdir() or tmp_path / "params" / "agent.yaml")
    sha = file_sha256(p)

    with pytest.raises(TransferRefused, match="depth_delay_ticks"):
        _runner(Ex30Runner, tmp_path, False).begin_from_parent(p, _spec(parent, sha=sha), parent["shapes"], (sha,))


def test_iteration_number_must_equal_start_plus_finished_updates(parent, tmp_path):
    r = _runner(Ex30Runner, tmp_path, False, "m")
    r.begin_from_parent(parent["path"], _spec(parent), parent["shapes"], parent["allowed"])
    r.iter_log.append({"it": parent["iter"] + 1})                                                                   # 갱신 1 회를 끝냈다고 하면서
    r.current_learning_iteration = parent["iter"] + 3                                                               # 회차는 3 칸 올라간 경우

    with pytest.raises(TransferRefused, match="다르다"):
        r.state_dict()


# ------------------------------------------------------------------ PPO · 정책 cfg 를 부모 params/agent.yaml 과 대조 (reviewer d1c22796 막음)
@pytest.mark.parametrize("algo", [{"entropy_coef": 0.1}, {"num_learning_epochs": 1}, {"clip_param": 0.3}, {"gamma": 0.9}])
def test_ppo_cfg_different_from_the_parent_agent_yaml_is_refused(parent, tmp_path, algo):
    r = _runner(Ex30Runner, tmp_path, False, algo=algo)

    with pytest.raises(TransferRefused, match="agent.yaml"):
        r.begin_from_parent(parent["path"], _spec(parent), parent["shapes"], parent["allowed"])

    assert r.current_learning_iteration == 0 and not getattr(r, "_transfer_broken", False)                            # 쓰기 전에 거절: 가중치도 번호도 그대로


def test_num_steps_and_policy_cfg_differences_are_refused_and_operational_keys_are_not_compared(parent, tmp_path):
    r = _runner(Ex31Runner, tmp_path, True)
    r.cfg["run_name"], r.cfg["max_iterations"], r.cfg["save_interval"] = "other", 7, 3                                   # 운영 칸은 달라도 통과

    r.begin_from_parent(parent["path"], _spec(parent, "EX-31"), parent["shapes"], parent["allowed"])

    r2 = _runner(Ex30Runner, tmp_path, False, "r2")
    r2.policy_cfg["init_noise_std"] = 0.5

    with pytest.raises(TransferRefused, match="agent.yaml"):
        r2.begin_from_parent(parent["path"], _spec(parent), parent["shapes"], parent["allowed"])


def test_missing_parent_agent_yaml_is_refused(parent, tmp_path):
    d = tmp_path / "noyaml"
    d.mkdir()
    shutil.copy(parent["path"], d / "model_1.pt")

    with pytest.raises(TransferRefused, match="agent.yaml"):
        import_parent(d / "model_1.pt", _spec(parent), shapes=parent["shapes"], allowed_parent_shas=parent["allowed"])


@pytest.mark.skipif(not REAL_PARENT.exists(), reason="실제 B 부모 없음")
def test_real_parent_agent_yaml_matches_b_hyperparameters_and_detects_the_two_reviewer_counterexamples():
    parent_agent, _ = st.load_parent_agent_cfg(REAL_PARENT)

    assert parent_agent["algorithm"]["entropy_coef"] == 0.01 and parent_agent["algorithm"]["num_learning_epochs"] == 5 and parent_agent["num_steps_per_env"] == 24
    assert st.agent_cfg_diffs(parent_agent, copy.deepcopy(parent_agent)) == {}
    for key, val in (("entropy_coef", 0.1), ("num_learning_epochs", 1)):
        bad = copy.deepcopy(parent_agent)
        bad["algorithm"][key] = val

        assert list(st.agent_cfg_diffs(parent_agent, bad)) == ["algorithm"]

    ops = copy.deepcopy(parent_agent)
    ops.update({"run_name": "x", "max_iterations": 10, "save_interval": 5, "device": "cuda:1"})
    ops["policy"]["class_name"] = "StartActorCritic"

    assert st.agent_cfg_diffs(parent_agent, ops) == {}


@pytest.mark.skipif(not REAL_PARENT.exists(), reason="실제 B 부모 없음")
def test_dumped_yaml_pair_diff_counts_only_non_operational_differences(tmp_path):
    env_yaml = REAL_PARENT.parent / "params" / "env.yaml"
    same = tmp_path / "env.yaml"
    same.write_text(env_yaml.read_text(encoding="utf-8").replace("2026-10-24_06-52-56_ex28-b-main", "NEW-RUN"), encoding="utf-8")        # log_dir 만 다른 사본

    assert st.yaml_pair_diff(env_yaml, same) == {}
    changed = tmp_path / "env2.yaml"
    changed.write_text(env_yaml.read_text(encoding="utf-8").replace("seed: 42", "seed: 43", 1), encoding="utf-8")
    diff = st.yaml_pair_diff(env_yaml, changed)

    assert diff == {"seed": (42, 43)} and st.yaml_pair_diff(env_yaml, changed, allowed_paths=("seed",)) == {}
