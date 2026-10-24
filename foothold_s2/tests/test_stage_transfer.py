"""SONNET-X25 T1: EX-30 · EX-31 부모 전환과 정확한 재개. CPU 만(Kit · CUDA 없음).

실제 부모(B model_1500.pt)는 읽기만 한다. 가짜 env 의 BRunner 로 만든 작은 부모로 runner 단계의 반례와 재개를 시험한다.
"""

import copy
import os
from pathlib import Path

import pytest
import torch

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


def _pcfg(force_gt):
    return {"microbatch_envs": 4, "map_input": "reconstruction", "force_gt": force_gt, "critic_mode": "clean52"}


def _runner(cls, tmp_path, force_gt, name="r"):
    env = FakeStartEnv(num_envs=8, seed=3)
    cfg = train_cfg(4, _pcfg(force_gt))
    cfg["save_interval"] = 1000

    return cls(env, cfg, log_dir=str(tmp_path / name), device="cpu")


@pytest.fixture(scope="module")
def parent(tmp_path_factory):
    """가짜 env 의 B 부모(force_gt True)를 2 번 갱신해 저장한다(iter=1)."""
    tmp = tmp_path_factory.mktemp("parent")
    r = _runner(BRunner, tmp, True, "b")
    r.learn(2)
    path = tmp / "b" / "model_1.pt"

    assert path.exists()
    sd = torch.load(path, weights_only=False)

    return {"path": path, "sha": file_sha256(path), "iter": sd["iter"], "shapes": {"std": tuple(sd["model_state_dict"]["std"].shape),
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
        import_parent(parent["path"], _spec(parent, sha="0" * 64), shapes=parent["shapes"])
    with pytest.raises(TransferRefused, match="짝"):
        import_parent(parent["path"], TransferSpec(parent["sha"], "EX-30", "gt", 42, CUR), shapes=parent["shapes"])
    with pytest.raises(TransferRefused, match="짝"):
        import_parent(parent["path"], TransferSpec(parent["sha"], "EX-99", "adaptive", 42, CUR), shapes=parent["shapes"])
    with pytest.raises(TransferRefused, match="seed"):
        import_parent(parent["path"], _spec(parent, seed=True), shapes=parent["shapes"])


def test_importer_refuses_wrong_dimension_other_model_and_nonfinite(parent, tmp_path):
    with pytest.raises(TransferRefused, match="모양"):
        import_parent(parent["path"], _spec(parent), shapes={**parent["shapes"], "actor.0.weight": (512, 97)})
    sd = torch.load(parent["path"], weights_only=False)

    def variant(mod, name):
        s = copy.deepcopy(sd)
        mod(s)
        p = tmp_path / name
        torch.save(s, p)

        return p, file_sha256(p)

    p, sha = variant(lambda s: s["sol23f"].update(variant="START_TopDown"), "other_model.pt")

    with pytest.raises(TransferRefused, match="variant"):
        import_parent(p, _spec(parent, sha=sha), shapes=parent["shapes"])

    p, sha = variant(lambda s: s["sol23f"].update(initial_snapshot=True), "initial.pt")

    with pytest.raises(TransferRefused, match="snapshot"):
        import_parent(p, _spec(parent, sha=sha), shapes=parent["shapes"])

    p, sha = variant(lambda s: s["model_state_dict"]["std"].__setitem__(0, float("nan")), "nan.pt")

    with pytest.raises(TransferRefused, match="NaN"):
        import_parent(p, _spec(parent, sha=sha), shapes=parent["shapes"])

    p, sha = variant(lambda s: s.pop("optimizer_state_dict"), "no_opt.pt")

    with pytest.raises(TransferRefused, match="optimizer_state_dict"):
        import_parent(p, _spec(parent, sha=sha), shapes=parent["shapes"])

    p, sha = variant(lambda s: s.update(format="other"), "format.pt")

    with pytest.raises(TransferRefused, match="START"):
        import_parent(p, _spec(parent, sha=sha), shapes=parent["shapes"])


# ------------------------------------------------------------------ 정상: 두 판이 같고 처치만 다르다
def test_two_children_start_identical_except_the_map_policy(parent, tmp_path):
    a, b = _runner(Ex30Runner, tmp_path, False, "a"), _runner(Ex31Runner, tmp_path, True, "b")
    ra, rb = a.begin_from_parent(parent["path"], _spec(parent, "EX-30"), parent["shapes"]), b.begin_from_parent(parent["path"], _spec(parent, "EX-31"), parent["shapes"])

    assert state_sha(a.alg.policy.state_dict()) == state_sha(b.alg.policy.state_dict()) == ra["state_sha"]["model"] == rb["state_sha"]["model"]
    assert state_sha(a.alg.optimizer.state_dict()) == state_sha(b.alg.optimizer.state_dict()) == ra["state_sha"]["optimizer"]
    assert state_sha(a.perception.state_dict()) == state_sha(b.perception.state_dict())
    assert state_sha(a.perception_optimizer.state_dict()) == state_sha(b.perception_optimizer.state_dict())
    assert a.alg.learning_rate == b.alg.learning_rate and a.current_learning_iteration == b.current_learning_iteration == parent["iter"]
    x = torch.randn(5, a.alg.policy.actor[0].in_features, generator=torch.Generator().manual_seed(1))

    assert torch.equal(a.alg.policy.actor(x), b.alg.policy.actor(x))                                               # 같은 입력이면 출력 같음
    assert bool(a.adasmpl.sample(64, "cpu").all()) and bool(b.adasmpl.sample(64, "cpu").all())                      # 첫 GT mask 는 두 판 모두 True
    assert a.adasmpl.force_gt is False and b.adasmpl.force_gt is True


def test_only_mainline_can_move_p_after_the_first_valid_update(parent, tmp_path):
    a, b = _runner(Ex30Runner, tmp_path, False, "a"), _runner(Ex31Runner, tmp_path, True, "b")
    a.begin_from_parent(parent["path"], _spec(parent, "EX-30"), parent["shapes"])
    b.begin_from_parent(parent["path"], _spec(parent, "EX-31"), parent["shapes"])

    for r in (a, b):
        r.adasmpl.add(torch.tensor([0.1, 5.0, 0.2, 3.0]))
        r.adasmpl.update()

    assert a.adasmpl.p < 1.0 and b.adasmpl.p == 1.0


def test_importer_alone_does_not_touch_env_state_rng_or_counters(parent, tmp_path):
    r = _runner(Ex30Runner, tmp_path, False)
    rng_before = torch.get_rng_state().clone()
    r.begin_from_parent(parent["path"], _spec(parent), parent["shapes"])

    assert torch.equal(torch.get_rng_state(), rng_before) and not hasattr(r, "env_state_loaded")
    assert r.stage_transfer["parent_iter"] == parent["iter"]

    with pytest.raises(TransferRefused, match="이미"):
        r.begin_from_parent(parent["path"], _spec(parent), parent["shapes"])


def test_runner_force_gt_must_match_the_map_policy(parent, tmp_path):
    with pytest.raises(TransferRefused, match="force_gt"):
        _runner(Ex30Runner, tmp_path, True).begin_from_parent(parent["path"], _spec(parent, "EX-30"), parent["shapes"])
    with pytest.raises(TransferRefused, match="force_gt"):
        _runner(Ex31Runner, tmp_path, False).begin_from_parent(parent["path"], _spec(parent, "EX-31"), parent["shapes"])


# ------------------------------------------------------------------ 재개
def test_child_resume_continues_numbering_and_counters(parent, tmp_path):
    spec = _spec(parent)
    r = _runner(Ex30Runner, tmp_path, False, "run")
    r.begin_from_parent(parent["path"], spec, parent["shapes"])
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
    r.begin_from_parent(parent["path"], spec, parent["shapes"])
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
