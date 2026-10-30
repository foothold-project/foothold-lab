"""Known-answer and mutation checks for the W55 in-process stage contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
import yaml

from foothold_s2.commands.mixed_core import EX39_SLOTS, make_generator, resample_stage
from foothold_s2.curriculum.continuous import Plan, Runtime, command_bad
from foothold_s2.ex40_launch import PARENT, build_args, receipt
from foothold_s2.ex40_kit_smoke import check as check_kit_smoke
from foothold_s2.prestart_check import actual_parser


SOURCE = Path(__file__).resolve().parents[1] / "curriculum" / "ex40.yaml"


def _mutated(tmp_path, change):
    doc = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    change(doc)
    path = tmp_path / "mutant.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def test_stage_table_and_narrowing_mutations(tmp_path):
    plan = Plan(SOURCE, arm="A")
    assert [(s.id, s.fixed_update) for s in plan.stages] == [
        ("B1", 1501), ("B2", 3001), ("B3", 4501), ("T0", 5501)]
    assert all(abs(sum(s.shares.values()) - 1) < 1e-9 for s in plan.stages)
    assert set(plan.stages[0].rewards) == set(plan.stages[-1].rewards)
    assert plan.stages[-1].force_gt is False and plan.stages[0].force_gt is True
    with pytest.raises(ValueError, match="sum to 100"):
        Plan(_mutated(tmp_path, lambda d: d["stages"][2]["shares"].update(forward=0.35)), arm="A")
    with pytest.raises(ValueError, match="range narrows"):
        Plan(_mutated(tmp_path, lambda d: d["stages"][2]["ranges"].update(reverse_vx=[-0.7, -0.2])), arm="A")
    with pytest.raises(ValueError, match="only be added once"):
        Plan(_mutated(tmp_path, lambda d: d["stages"][1]["adds"].update(rewards={"track_lin_vel": 3})), arm="A")
    unresolved = Runtime(Plan(SOURCE), 1, "cpu", tmp_path / "unresolved")
    with pytest.raises(RuntimeError, match="arm unresolved"):
        unresolved.on_update_start(3001)


def test_each_stage_sampler_and_per_env_contract():
    plan = Plan(SOURCE, arm="B")
    gen = make_generator(42)
    n = 8192
    yaw = torch.zeros(n)
    for i, stage in enumerate(plan.stages):
        row = resample_stage(gen, n, stage, yaw)
        assert row["cmd"].shape == (n, 3)
        assert not command_bad(row["cmd"], row["slot"], row["heading"],
                               torch.full((n,), i), plan).any()
        assert set(row["slot"].unique().tolist()) == {EX39_SLOTS.index(k) for k in stage.shares}
    row = resample_stage(gen, n, plan.stages[0], yaw)
    damaged = row["cmd"].clone()
    damaged[0, 0] = -1.4
    bad = command_bad(damaged, row["slot"], row["heading"], torch.zeros(n, dtype=torch.long), plan)
    assert bad[0] and int(bad.sum()) == 1


def test_fixed_boundary_only_reset_applies_and_shadow_does_not_promote(tmp_path):
    plan = Plan(SOURCE, arm="A", smoke_boundaries=(1503, 1506, 1509))
    runtime = Runtime(plan, 4, "cpu", tmp_path / "out", tmp_path / "scores")
    runner = SimpleNamespace(adasmpl=SimpleNamespace(force_gt=True, p=1.0), pcfg={"force_gt": True},
                             perception=SimpleNamespace(cfg=SimpleNamespace(force_gt=True)))
    term = SimpleNamespace()
    runtime.attach(runner, term)
    runtime.start(plan.parent_sha256)
    runtime.on_update_start(1501)
    runtime.on_update_start(1503)
    assert runtime.active == 1 and runtime.env_stage.tolist() == [0, 0, 0, 0]
    runtime.on_reset(torch.tensor([1, 3]))
    assert runtime.env_stage.tolist() == [0, 1, 0, 1]
    runtime.on_update_start(1506)
    assert runtime.env_stage.tolist() == [0, 1, 0, 1]
    runtime.on_reset(torch.tensor([0, 1]))
    assert runtime.env_stage.tolist() == [2, 2, 0, 1]
    runtime.on_update_start(1509)
    assert runtime.active == 3 and runtime.env_stage[2].item() == 0
    assert runner.adasmpl.force_gt is False
    assert runner.perception.cfg.force_gt is False


def test_shadow_score_reads_real_checkpoint_sha_without_changing_stage(tmp_path):
    plan = Plan(SOURCE, arm="A")
    runtime = Runtime(plan, 2, "cpu", tmp_path / "out", tmp_path / "scores")
    checkpoint = tmp_path / "model_1502.pt"
    checkpoint.write_bytes(b"known checkpoint")
    score_dir = tmp_path / "scores"
    score_dir.mkdir()
    score = {"format": "foothold-w55-score/1", "from": "B1", "to": "B2",
             "verdict": "EXPAND", "checkpoint": str(checkpoint),
             "checkpoint_iteration": 1502, "checkpoint_sha256": __import__("hashlib").sha256(checkpoint.read_bytes()).hexdigest()}
    (score_dir / "1502.json").write_text(json.dumps(score), encoding="utf-8")
    runtime.on_checkpoint(1502, checkpoint)
    runtime.on_update_start(1503)
    assert runtime.active == 0
    rows = [json.loads(line) for line in (tmp_path / "out" / "stage_log.jsonl").read_text().splitlines()]
    assert [r["event"] for r in rows] == ["shadow_gate"]
    assert rows[0]["checkpoint_sha256"] == score["checkpoint_sha256"]


def test_gate_mode_promotes_only_after_next_checkpoint_and_reset(tmp_path):
    path = _mutated(tmp_path, lambda d: d.update(promotion="gate", shadow_gate=False))
    plan = Plan(path, arm="A")
    runtime = Runtime(plan, 2, "cpu", tmp_path / "out", tmp_path / "scores")
    checkpoint = tmp_path / "model_1502.pt"
    checkpoint.write_bytes(b"checkpoint")
    score_dir = tmp_path / "scores"
    score_dir.mkdir()
    score = {"format": "foothold-w55-score/1", "from": "B1", "to": "B2",
             "verdict": "EXPAND", "checkpoint": str(checkpoint),
             "checkpoint_iteration": 1502, "checkpoint_sha256": __import__("hashlib").sha256(checkpoint.read_bytes()).hexdigest()}
    (score_dir / "1502.json").write_text(json.dumps(score), encoding="utf-8")
    runtime.on_update_start(1502)
    assert runtime.active == 0
    runtime.on_checkpoint(1502, checkpoint)
    assert runtime.active == 0
    runtime.on_update_start(1503)
    assert runtime.active == 1 and runtime.env_stage.tolist() == [0, 0]
    runtime.on_reset(torch.tensor([0]))
    assert runtime.env_stage.tolist() == [1, 0]
    state = copy.deepcopy(runtime.state_dict())
    other = Runtime(plan, 2, "cpu", tmp_path / "resume")
    other.load_state_dict(state)
    assert other.active == 1 and other.env_stage.tolist() == [1, 0]
    with pytest.raises(ValueError, match="curriculum SHA"):
        Runtime(Plan(path, arm="A", smoke_boundaries=(1503, 1506, 1509)),
                2, "cpu", tmp_path / "smoke").load_state_dict(state)
    with pytest.raises(ValueError, match="curriculum SHA"):
        Runtime(Plan(path, arm="B"), 2, "cpu", tmp_path / "other_arm").load_state_dict(state)


def test_actual_parent_and_train_parser_accept_smoke_and_main(tmp_path):
    assert PARENT.is_file()
    for smoke, last in ((True, 1511), (False, 6001)):
        args = build_args(arm="A", device="cuda:0", end_by="2026-11-05T12:00:00+09:00",
                          log_root=tmp_path / "output", score_dir=tmp_path / "scores", smoke=smoke)
        parsed, unknown = actual_parser().parse_known_args([
            "--task", "FootholdS2-Go2-S2-SB-v0", "--variant", "SB", *args])
        assert parsed.max_iterations == last
        assert parsed.curriculum_arm == "A" and parsed.curriculum_kit_smoke == smoke
        assert unknown[0] == "--headless" and unknown[-1].startswith("--kit_args=")
        row = receipt(args)
        assert row["parent_completed_update"] == 1500
        assert row["state"] == "CPU_PREPARED_NOT_LAUNCHED"
    with pytest.raises(ValueError, match="parent checkpoint SHA"):
        build_args(arm="A", device="cuda:0", end_by="2026-11-05T12:00:00+09:00",
                   log_root=tmp_path / "output", score_dir=tmp_path / "scores", smoke=True,
                   parent=_bad_parent(tmp_path))


def _bad_parent(tmp_path):
    path = tmp_path / "model_1500.pt"
    path.write_bytes(b"wrong parent")
    return path


def test_smoke_checker_known_good_and_mutations(tmp_path):
    args = build_args(arm="B", device="cuda:1", end_by="2026-11-05T12:00:00+09:00",
                      log_root=tmp_path / "output", score_dir=tmp_path / "scores", smoke=True)
    row = {"state": "CPU_PREPARED_NOT_LAUNCHED", "arm": "B", "argv": args,
           "stage_boundaries": {"B1": 1501, "B2": 1503, "B3": 1506, "T0": 1509}}
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(row), encoding="utf-8")
    run_log = tmp_path / "run.log"
    run_log.write_text("Learning iteration 1501/1511\n", encoding="utf-8")
    run = tmp_path / "output" / "smoke" / "EX-40-B-kit-smoke_20261030_1"
    run.mkdir(parents=True)
    events = [{"event": "stage_enter", "to": k, "iteration": v}
              for k, v in row["stage_boundaries"].items()]
    events[-1]["force_gt"] = False
    events.append({"event": "env_reset_applied", "to": "B2", "changed_envs": 2})
    stage_log = run / "stage_log.jsonl"
    stage_log.write_text("\n".join(json.dumps(r) for r in events) + "\n", encoding="utf-8")
    (run / "train_start_status.json").write_text(json.dumps({"state": "done", "iter": 1510}), encoding="utf-8")
    (run / "model_1510.pt").write_bytes(b"known model")
    (run / "train_start_status.json").write_text(json.dumps({"state": "done", "iter": 1510,
        "sha256": __import__("hashlib").sha256(b"known model").hexdigest()}), encoding="utf-8")
    assert check_kit_smoke(receipt_path, run_log, 0)["state"] == "PASS"
    with pytest.raises(ValueError, match="child failed"):
        check_kit_smoke(receipt_path, run_log, 1)
    stage_log.write_text("\n".join(json.dumps(r) for r in events if r.get("to") != "T0") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="all planned stages"):
        check_kit_smoke(receipt_path, run_log, 0)
