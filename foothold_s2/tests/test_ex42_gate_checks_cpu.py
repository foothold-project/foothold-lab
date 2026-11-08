from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from foothold_s2.ex42_gate_checks import (
    EX42_LOCKED_SOURCE_PATHS, REQUIRED_GATE_ROWS, audit_ex42_launch_source,
    audit_locked_checkout, checkpoint_ready, extract_realized_config,
    launch_argv_sha256, locked_source_contract, open_gate_rows,
    process_score_batch, validate_automatic_rule, validate_ex42_map_score,
    validate_score_pair, verify_launch_argv,
)
from foothold_s2.ex42_status import read_status, write_status


def _table(statuses: dict[str, str]) -> str:
    rows = ["| Gate | Issue | Risk | Guard | State | Owner |", "|---|---|---|---|---|---|"]
    rows.extend(f"| {row} | x | x | x | {statuses.get(row, '있음 · 코드')} | runner |"
                for row in REQUIRED_GATE_ROWS)
    return "\n".join(rows)


def test_g01_ops_gate_table_fails_closed_on_any_open_row(tmp_path):
    path = tmp_path / "gates.md"
    path.write_text(_table({"G01": "있음 · 코드"}), encoding="utf-8")
    assert open_gate_rows(path) == []
    path.write_text(_table({"G03": "예행 대기"}), encoding="utf-8")
    assert open_gate_rows(path) == ["G03"]
    path.write_text(_table({"G33": "없음 · 막음"}), encoding="utf-8")
    assert open_gate_rows(path) == ["G33"]
    with pytest.raises(ValueError, match="gate report unavailable"):
        open_gate_rows(tmp_path / "missing.md")


def test_g01_analyst_33_row_counterexample_blocks_g11():
    fixture = Path(__file__).with_name("fixtures") / "ex42-gate-g11-open.md"
    assert open_gate_rows(fixture) == ["G11"]


def test_g01_parses_analyst_register_cells_with_incident_suffix(tmp_path):
    path = tmp_path / "analyst-register.md"
    rows = ["| Gate | Risk | Guard | Evidence | State | Owner |",
            "|---|---|---|---|---|---|"]
    rows.extend(
        f"| G{index:02d} · R{index} incident | x | x | x | "
        f"{'예행 대기' if index == 11 else '검증 완료'} | runner |"
        for index in range(1, 34))
    path.write_text("\n".join(rows), encoding="utf-8")
    assert open_gate_rows(path) == ["G11"]


def test_g01_missing_and_unregistered_ids_are_blockers(tmp_path):
    ids = [f"G{i:02d}" for i in range(1, 34)]
    lines = ["| Gate | Issue | Risk | Guard | State | Owner |", "|---|---|---|---|---|---|"]
    lines.extend(f"| {row} | x | x | x | 검증 완료 | runner |" for row in ids if row != "G11")
    path = tmp_path / "missing-row.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    assert open_gate_rows(path) == ["G11"]
    lines.append("| G34 | x | x | x | 검증 완료 | runner |")
    path.write_text("\n".join(lines), encoding="utf-8")
    assert open_gate_rows(path) == ["G11", "G34"]


def test_g03_locked_head_inventory_and_writable_counter():
    modes = {"experiments/EX-42.yaml": stat.S_IREAD,
             "foothold_s2/curriculum/ex42-prep.yaml": stat.S_IREAD,
             "foothold_s2/scripts/ex42_ops.py": stat.S_IREAD}
    shas = {name: f"{i:064x}" for i, name in enumerate(modes, 1)}
    ok = locked_source_contract(launch_head="abc", remote_head="abc", clean=True,
                                file_modes=modes, file_sha256=shas, expected_sha256=shas)
    assert ok["writable_count"] == 0 and len(ok["files"]) == 3
    with pytest.raises(ValueError, match="remote HEAD"):
        locked_source_contract(launch_head="abc", remote_head="def", clean=True,
                              file_modes=modes, file_sha256=shas, expected_sha256=shas)
    with pytest.raises(ValueError, match="writable files"):
        locked_source_contract(launch_head="abc", remote_head="abc", clean=True,
                              file_modes={**modes, "experiments/EX-42.yaml": stat.S_IWRITE},
                              file_sha256=shas, expected_sha256=shas)
    with pytest.raises(ValueError, match="SHA differs"):
        locked_source_contract(launch_head="abc", remote_head="abc", clean=True,
                              file_modes=modes, file_sha256={**shas, "experiments/EX-42.yaml": "bad"},
                              expected_sha256=shas)


def test_g03_actual_git_checkout_matches_remote_and_readonly_inventory(tmp_path):
    origin, root = tmp_path / "origin.git", tmp_path / "source"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    files = ["experiments/EX-42.yaml", "foothold_s2/curriculum/ex42-prep.yaml",
             "foothold_s2/scripts/ex42_ops.py"]
    for index, relative in enumerate(files):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"pinned-{index}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", *files], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                    "commit", "-m", "pin"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", str(origin)], check=True)
    subprocess.run(["git", "-C", str(root), "push", "-u", "origin", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "checkout", "--detach", "origin/main"], check=True, capture_output=True)
    for relative in files:
        os.chmod(root / relative, stat.S_IREAD)
    result = audit_locked_checkout(root, remote_ref="origin/main", protected_paths=files)
    assert result["launch_head"] == result["remote_head"] and result["writable_count"] == 0
    os.chmod(root / files[0], stat.S_IREAD | stat.S_IWRITE)
    with pytest.raises(ValueError, match="writable files"):
        audit_locked_checkout(root, remote_ref="origin/main", protected_paths=files)


def test_g03_launch_caller_rejects_attached_branch_even_when_old_audit_passes(tmp_path):
    origin, root = tmp_path / "origin.git", tmp_path / "locked-source"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    for index, relative in enumerate(EX42_LOCKED_SOURCE_PATHS):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"source-pinned-{index}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", *EX42_LOCKED_SOURCE_PATHS],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=test", "-c",
                    "user.email=test@example.invalid", "commit", "-m", "pin"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", str(origin)],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "push", "-u", "origin", "main"],
                   check=True, capture_output=True)
    for relative in EX42_LOCKED_SOURCE_PATHS:
        os.chmod(root / relative, stat.S_IREAD)

    old_audit = audit_locked_checkout(
        root, remote_ref="origin/main", protected_paths=EX42_LOCKED_SOURCE_PATHS)
    assert old_audit["launch_head"] == old_audit["remote_head"]
    assert old_audit["writable_count"] == 0
    with pytest.raises(ValueError, match="must be detached"):
        audit_ex42_launch_source(root, remote_ref="origin/main")

    subprocess.run(["git", "-C", str(root), "checkout", "--detach", "origin/main"],
                   check=True, capture_output=True)
    locked = audit_ex42_launch_source(root, remote_ref="origin/main")
    assert locked["detached"] is True
    assert locked["launch_head"] == locked["remote_head"]
    assert locked["writable_count"] == 0


def test_g05_exact_interpreter_cli_and_argv_sha(tmp_path):
    python, cli = tmp_path / "python", tmp_path / "cli_args.py"
    python.write_text("", encoding="utf-8")
    cli.write_text("", encoding="utf-8")
    argv = ["--task", "EX42", "--num_envs", "3072", "--headless", "--device", "cuda:0"]
    expected = launch_argv_sha256(argv, python=str(python), isaac_cli=str(cli))
    result = verify_launch_argv(argv, python=str(python), isaac_cli=str(cli),
                                expected_sha256=expected)
    assert result["argv_sha256"] == expected
    assert result["evidence_scope"] == "path_and_argv_digest_only"
    assert result["runtime_import_verified"] is False
    assert result["new_output_sha256"] is None
    with pytest.raises(ValueError, match="argv hash"):
        verify_launch_argv(argv + ["--seed", "7"], python=str(python),
                           isaac_cli=str(cli), expected_sha256=expected)
    with pytest.raises(ValueError, match="missing"):
        verify_launch_argv(argv, python=str(tmp_path / "missing"), isaac_cli=str(cli),
                           expected_sha256=expected)


def test_g05_placeholder_paths_and_argv_hash_do_not_close_native_gate(tmp_path, monkeypatch):
    from foothold_s2.scripts import ex42_ops

    python, cli = tmp_path / "python.exe", tmp_path / "cli_args.py"
    python.write_text("placeholder", encoding="utf-8")
    cli.write_text("placeholder", encoding="utf-8")
    argv = ["--task", "EX42", "--headless", "--device", "cuda:0"]
    digest = launch_argv_sha256(argv, python=str(python), isaac_cli=str(cli))
    fake_preflight = verify_launch_argv(argv, python=str(python), isaac_cli=str(cli),
                                        expected_sha256=digest)
    assert fake_preflight["argv_sha256"] == digest  # old CPU check looked successful

    monkeypatch.setattr(ex42_ops, "verify_train_entry_contract", lambda: {
        "parser": "source-only", "runtime_identity": None,
        "final_argv_sha256": fake_preflight["argv_sha256"], "training_started": False})
    monkeypatch.setattr(ex42_ops, "verify_env_cfg_import", lambda task_id: {
        "task_id": task_id, "imported": False, "error_type": "ModuleNotFoundError",
        "error": "No module named 'pxr'", "kit_started": False})
    result = ex42_ops.ops_check(ex42_ops.DEFAULT_TABLE, ex42_ops.DEFAULT_APPROVALS)
    assert result["g05_evidence"]["state"] == "kit_required"
    assert result["g05_evidence"]["complete"] is False
    assert result["g05_evidence"]["environment_imported"] is False
    assert result["g05_evidence"]["new_output_sha256"] is None


def test_g13_checkpoint_and_score_pair_distinguish_late_corrupt_and_old_pass():
    sha = "a" * 64
    manifest = {"progress": {"completed_updates": 249},
                "checkpoints": {"model_250.pt": sha}}
    assert checkpoint_ready(manifest, iteration=250, checkpoint_exists=True,
                            checkpoint_sha256=sha)
    assert not checkpoint_ready(manifest, iteration=249, checkpoint_exists=True,
                                checkpoint_sha256=sha)
    assert not checkpoint_ready({"progress": {"completed_updates": 500}, "checkpoints": {}},
                                iteration=250, checkpoint_exists=False, checkpoint_sha256=sha)
    good = {"checkpoint_iteration": 250, "checkpoint_sha256": sha, "state": "complete"}
    validate_score_pair(expected_iteration=250, score=good, manifest=manifest,
                        checkpoint_exists=True, checkpoint_sha256=sha)
    for bad in ({**good, "checkpoint_iteration": 249},
                {**good, "checkpoint_sha256": "b" * 64},
                {**good, "state": "invalid"}):
        with pytest.raises(ValueError):
            validate_score_pair(expected_iteration=250, score=bad, manifest=manifest,
                                checkpoint_exists=True, checkpoint_sha256=sha)


def test_g15_three_modes_and_commands_reject_missing_duplicate_or_extra():
    from foothold_s2.eval.map_mode_cells import commands
    aliases = {"gt": "eval_gt", "pred": "eval_pred", "off": "probe_prop_only"}
    rows = [{"map_mode": aliases[mode], "command": command,
             "role": "record_only" if mode == "off" else "judge"}
            for mode in ("gt", "pred", "off") for command in commands("extended")]
    complete = {"map_matrix": rows, "judge_count": 26, "record_only_count": 13}
    validate_ex42_map_score(complete, ["gt", "pred", "off"])
    assert len(rows) == 39
    for bad in (rows[:-1], rows + [rows[0]],
                rows[:-1] + [{"map_mode": "eval_gt", "command": "unregistered", "role": "judge"}]):
        with pytest.raises(ValueError, match="missing, duplicate"):
            validate_ex42_map_score({**complete, "map_matrix": bad}, ["gt", "pred", "off"])
    wrong_role = [dict(row) for row in rows]
    wrong_role[0]["role"] = "record_only"
    with pytest.raises(ValueError, match="incorrect judge/record role"):
        validate_ex42_map_score({**complete, "map_matrix": wrong_role}, ["gt", "pred", "off"])
    with pytest.raises(ValueError, match="role counts"):
        validate_ex42_map_score({**complete, "judge_count": 25}, ["gt", "pred", "off"])


def test_g17_extracts_observed_values_and_sources_without_defaults(tmp_path):
    env = tmp_path / "env.yaml"
    agent = tmp_path / "agent.yaml"
    env.write_text("commands:\n  ranges: [0.1, 0.2]\nobservations:\n  policy:\n    map_mode: pred\nevents:\n  push: enabled\nscene:\n  robot:\n    actuators: motorA\nrewards:\n  feet: 0.5\ncurriculum:\n  terrain_levels: 2\n", encoding="utf-8")
    agent.write_text("algorithm:\n  lr: 0.0003\n", encoding="utf-8")
    values = extract_realized_config(env, agent)
    assert values["commands"]["value"]["ranges"] == [0.1, 0.2]
    assert values["map_selection"]["value"] == "pred"
    assert values["domain_randomization"]["value"] == {"push": "enabled"}
    assert values["actuators"]["value"] == "motorA"
    assert values["rewards"]["value"] == {"feet": 0.5}
    assert values["level_cap"]["value"] == 2
    assert values["algorithm"]["value"] == {"lr": 0.0003}
    env.write_text("commands: {}\n", encoding="utf-8")
    assert extract_realized_config(env, agent)["map_selection"]["observed"] is False


def test_g18_automatic_rule_true_false_boundary_and_rejected_approval():
    rule = {"field": "critic_mirror", "decision_id": "D155", "choices": [False, True],
            "boundaries": [250, 500]}
    approved = {"fields": {"critic_mirror": {"approved": True, "decision_id": "D155"}}}
    assert validate_automatic_rule(rule=rule, approval=approved, value=True, boundary=250)
    assert validate_automatic_rule(rule=rule, approval=approved, value=False, boundary=500)
    for bad_approval, value, boundary in (
            ({"fields": {}}, True, 250),
            ({"fields": {"critic_mirror": {"approved": False, "decision_id": "D155"}}}, True, 250),
            (approved, 1.0, 250), (approved, True, 751)):
        with pytest.raises(ValueError, match="approved boundary"):
            validate_automatic_rule(rule=rule, approval=bad_approval,
                                    value=value, boundary=boundary)


def test_g33_mixed_all_invalid_and_reset_failure_are_alerted_without_throwing():
    alerts = []
    validate = lambda row: row["value"] if row.get("valid") else (_ for _ in ()).throw(ValueError("bad row"))
    mixed = process_score_batch([{"valid": True, "value": 1}, {"valid": False}],
                                validate, reset=lambda: None, alert=alerts.append)
    assert mixed["state"] == "partial" and mixed["accepted"] == [1]
    all_bad = process_score_batch([{"valid": False}], validate, reset=lambda: None,
                                  alert=alerts.append)
    assert all_bad["state"] == "unknown" and not all_bad["accepted"]
    reset_bad = process_score_batch([{"valid": True, "value": 2}], validate,
                                   reset=lambda: (_ for _ in ()).throw(RuntimeError("reset")),
                                   alert=alerts.append)
    assert reset_bad["state"] == "unknown" and len(alerts) == 2


def test_g08_status_write_failure_is_unknown_retry_not_training_exception(tmp_path):
    path = tmp_path / "status.json"
    path.write_text('{"old":true}', encoding="utf-8")
    calls = []
    def blocked_replace(src, dst):
        calls.append((src, dst))
        raise PermissionError("reader holds existing status open")
    result = write_status(path, {"update": 250}, replace=blocked_replace, sleep=lambda _: None)
    assert result["state"] == "unknown" and result["retry"] is True
    assert result["attempts"] == len(calls) == 6
    assert json.loads(path.read_text(encoding="utf-8")) == {"old": True}
    success = write_status(path, {"update": 250}, sleep=lambda _: None)
    assert success["state"] == "written"
    assert read_status(path) == {"state": "read", "value": {"update": 250}}
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("file", encoding="utf-8")
    result = write_status(blocked_parent / "status.json", {"update": 251})
    assert result["state"] == "unknown" and result["retry"] is True


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing lock semantics only")
def test_g08_real_windows_open_reader_causes_bounded_unknown_then_retry(tmp_path):
    path = tmp_path / "status.json"
    path.write_text('{"old":true}', encoding="utf-8")
    with path.open("rb") as held:
        result = write_status(path, {"update": 250})
        assert held.read(1)
    assert result["state"] == "unknown" and result["attempts"] == 6
    assert write_status(path, {"update": 250})["state"] == "written"
