"""Known-input CPU contracts for W57 preflight and isolated retry evidence."""

from __future__ import annotations

import ctypes
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from foothold_s2.eval.w57_checkpoint_hash import hash_checkpoint
from foothold_s2.ex40_eval_once import BASH, DEFAULT_CONFIG, DEFAULT_TABLE
from foothold_s2.eval.map_mode_cells import EX40_B3_COMMANDS, commands
from foothold_s2.ex40_score import config, judge, sha256
import foothold_s2.ex40_w57_retry as retry_module
from foothold_s2.ex40_w57_retry import retry
from foothold_s2.tests.test_ex40_scorer_cpu import _axis, _evidence, _source


def test_original_redirect_leaves_zero_byte_and_fixed_hash_retries(tmp_path, capsys):
    old_receipt = tmp_path / "old_sha.txt"
    checkpoint = tmp_path / "model_1500.pt"
    checkpoint.write_bytes(b"known checkpoint")
    # The original redirect creates a zero-byte receipt if another Windows
    # process temporarily denies file sharing during the hash read.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                   ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                   ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    handle = kernel.CreateFileW(str(checkpoint), 0x80000000, 0, None, 3, 0, None)
    assert handle not in (None, ctypes.c_void_p(-1).value)
    try:
        with old_receipt.open("w", encoding="utf-8") as stream:
            result = subprocess.run([str(BASH), "-c", 'sha256sum "$1"', "--",
                                     str(checkpoint)], stdout=stream, capture_output=False,
                                    check=False)
    finally:
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(handle)
    assert result.returncode != 0 and old_receipt.is_file() and old_receipt.stat().st_size == 0
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    calls = []

    def transient(path):
        calls.append(path)
        if len(calls) == 1:
            raise PermissionError("known transient sharing failure")
        return digest

    receipt = tmp_path / "checkpoint_sha256.txt"
    assert hash_checkpoint(checkpoint, receipt, reader=transient, sleep=lambda _: None) == digest
    assert len(calls) == 2 and receipt.read_text(encoding="utf-8").startswith(digest)
    assert "attempt 1/5" in capsys.readouterr().err
    with pytest.raises(OSError, match="after 2 attempts"):
        hash_checkpoint(checkpoint, tmp_path / "permanent.txt", attempts=2,
                        reader=lambda _p: (_ for _ in ()).throw(PermissionError("held")),
                        sleep=lambda _: None)
    assert not (tmp_path / "permanent.txt").exists()
    normal = tmp_path / "normal.txt"
    assert hash_checkpoint(checkpoint, normal) == digest


def _original(tmp_path):
    checkpoint, _ = _source(tmp_path, update=1500)
    prior = tmp_path / "failed_eval"
    _evidence(prior, checkpoint)
    (prior / "axis_v2").mkdir()
    (prior / "axis_v2/checkpoint_sha256.txt").write_bytes(b"")
    phases = {name: {"rc": 0} for name in
              ("map64", "stand_eval_gt", "stand_probe_prop_only", "stand_eval_pred")}
    phases["axis_v2"] = {"rc": 1}
    row = {"state": "failed", "checkpoint": str(checkpoint),
           "checkpoint_sha256": sha256(checkpoint), "stage": "B0", "arm": "B",
           "device": "cuda:1", "source_git_head": "f" * 40,
           "score_config_sha256": sha256(DEFAULT_CONFIG),
           "table_sha256": sha256(DEFAULT_TABLE), "steps": phases}
    (prior / "eval_receipt.json").write_text(json.dumps(row), encoding="utf-8")
    return checkpoint, prior


def test_retry_new_bundle_links_failed_source_and_never_changes_original(tmp_path):
    checkpoint, prior = _original(tmp_path)
    original_receipt = (prior / "eval_receipt.json").read_bytes()
    original_empty_hash = (prior / "axis_v2/checkpoint_sha256.txt").read_bytes()
    cfg = config(DEFAULT_CONFIG)
    attempted = []

    def known_axis(source, axis_dir, device, given_cfg):
        assert source == checkpoint and device == "cuda:1" and given_cfg == cfg
        attempted.append(axis_dir)
        axis_dir.mkdir()
        axis = {"checkpoint_sha256": sha256(source), "envs": 64,
                "modes": {mode: {name: {"stop_complete_envs": 64,
                                          "stop_end_error_median_rad": .01}
                                 for name in cfg["axis_goal"]["cases"]}
                          for mode in ("eval_gt", "probe_prop_only", "eval_pred")}}
        (axis_dir / "axis_v2.json").write_text(json.dumps(axis), encoding="utf-8")
        (axis_dir / "git_head.txt").write_text("a" * 40, encoding="utf-8")
        return 0

    retry_root = tmp_path / "separate_retries"
    row = retry(prior, checkpoint, retry_root, "try02", runner=known_axis)
    assert len(attempted) == 1 and row["attempt_id"] == "try02"
    assert row["prior_source_sha256"]["eval_receipt.json"] == hashlib.sha256(original_receipt).hexdigest()
    assert row["retry_axis_sha256"] == sha256(attempted[0] / "axis_v2.json")
    assert row["retry_source_git_head"] == "a" * 40
    assert row["verdict"] == "PASS" and row["canonical_watch_state_changed"] is False
    score = json.loads(Path(row["score_path"]).read_text(encoding="utf-8"))
    assert score["verdict"] == "PASS" and score["retry_attempt_id"] == "try02"
    assert (prior / "eval_receipt.json").read_bytes() == original_receipt
    assert (prior / "axis_v2/checkpoint_sha256.txt").read_bytes() == original_empty_hash
    ledger = retry_root / "w57_retry_ledger.jsonl"
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1
    with pytest.raises(ValueError, match="already present in separate ledger"):
        retry(prior, checkpoint, retry_root, "try02", runner=known_axis)
    assert len(attempted) == 1 and len(ledger.read_text(encoding="utf-8").splitlines()) == 1
    (retry_root / "w57_retry_model_1500_try02").rename(retry_root / "archived_try02")
    with pytest.raises(ValueError, match="already present in separate ledger"):
        retry(prior, checkpoint, retry_root, "try02", runner=known_axis)


def test_retry_rejects_changed_checkpoint_or_non_w57_failure(tmp_path):
    checkpoint, prior = _original(tmp_path)
    checkpoint.write_bytes(b"changed checkpoint")
    with pytest.raises(ValueError, match="identity differs"):
        retry(prior, checkpoint, tmp_path / "retries", "try03", runner=lambda *_: 0)
    assert not (tmp_path / "retries").exists()
    checkpoint.write_bytes(b"known policy checkpoint")
    row = json.loads((prior / "eval_receipt.json").read_text(encoding="utf-8"))
    row["steps"]["map64"]["rc"] = 1
    (prior / "eval_receipt.json").write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="non-W57 phase"):
        retry(prior, checkpoint, tmp_path / "retries", "try03", runner=lambda *_: 0)
    assert not (tmp_path / "retries").exists()


def test_retry_failed_child_is_hold_with_separate_ledger(tmp_path):
    checkpoint, prior = _original(tmp_path)
    root = tmp_path / "retries"
    row = retry(prior, checkpoint, root, "try04", runner=lambda *_: 4)
    assert row["child_rc"] == 4 and row["verdict"] == "HOLD"
    assert row["retry_axis_sha256"] is None
    assert len((root / "w57_retry_ledger.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_retry_check_only_cli_uses_real_receipt_without_kit(tmp_path):
    checkpoint, prior = _original(tmp_path)
    root = tmp_path / "unused_retries"
    result = subprocess.run([sys.executable, "-m", "foothold_s2.ex40_w57_retry",
                             "--prior-eval", str(prior), "--checkpoint", str(checkpoint),
                             "--retry-root", str(root), "--attempt-id", "preflight",
                             "--check-only"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["checkpoint_sha256"] == sha256(checkpoint)
    assert not root.exists()


def test_zero_completed_goals_are_fail_not_missing_evidence(tmp_path):
    checkpoint, _ = _source(tmp_path, update=3500)
    out = tmp_path / "eval"
    main = _evidence(out, checkpoint)
    extra = {**main, "command_suite": "ex40_b3", "commands": commands("ex40_b3"),
             "policy_dt_s": .02,
             "modes": {mode: {name: {**copy.deepcopy(main["modes"][mode]["fwd0.5"]),
                                      "command": command}
                              for name, command in EX40_B3_COMMANDS.items()}
                       for mode in ("eval_gt", "probe_prop_only", "eval_pred")}}
    (out / "map64_b3").mkdir()
    (out / "map64_b3/map_modes.json").write_text(json.dumps(extra), encoding="utf-8")
    _axis(out, checkpoint)
    axis_path = out / "axis_v2/axis_v2.json"
    axis = json.loads(axis_path.read_text(encoding="utf-8"))
    name = config(DEFAULT_CONFIG)["axis_goal"]["cases"][0]
    case = axis["modes"]["eval_gt"][name]
    case["stop_complete_envs"] = 0
    case["stop_end_error_median_rad"] = None
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    failed, _ = judge(checkpoint, "B2", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert failed["verdict"] == "FAIL"
    assert failed["cells"][f"eval_gt/{name}"]["stop_end_error_median_rad"] is None
    assert any(p["kind"] == "FAIL" and p["cell"] == f"eval_gt/{name}"
               for p in failed["problems"])
    case.pop("stop_end_error_median_rad")
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    missing, _ = judge(checkpoint, "B2", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert missing["verdict"] == "HOLD"
    case["stop_end_error_median_rad"] = None
    case["stop_complete_envs"] = 1
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    held, _ = judge(checkpoint, "B2", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert held["verdict"] == "HOLD"
    case["stop_complete_envs"] = 0
    case["stop_end_error_median_rad"] = float("nan")
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    invalid, _ = judge(checkpoint, "B2", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert invalid["verdict"] == "HOLD"
    case["stop_complete_envs"] = 1
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    positive_nan, _ = judge(checkpoint, "B2", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert positive_nan["verdict"] == "HOLD"


def test_zero_completed_boundary_is_recorded_without_axis_gate(tmp_path):
    checkpoint, _ = _source(tmp_path, update=1500)
    out = tmp_path / "eval"
    _evidence(out, checkpoint)
    _axis(out, checkpoint)
    axis_path = out / "axis_v2/axis_v2.json"
    axis = json.loads(axis_path.read_text(encoding="utf-8"))
    name = config(DEFAULT_CONFIG)["axis_goal"]["cases"][0]
    axis["modes"]["eval_gt"][name] = {"stop_complete_envs": 0,
                                        "stop_end_error_median_rad": None}
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    score, _ = judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert score["verdict"] == "PASS"
    assert score["cells"][f"eval_gt/{name}"]["stop_complete_envs"] == 0
    axis["modes"]["eval_gt"][name].pop("stop_end_error_median_rad")
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    missing, _ = judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert missing["verdict"] == "HOLD"
    axis["modes"]["eval_gt"][name]["stop_end_error_median_rad"] = None
    axis["modes"]["eval_gt"][name]["stop_complete_envs"] = 1
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    positive_null, _ = judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert positive_null["verdict"] == "HOLD"
    axis["modes"]["eval_gt"][name]["stop_complete_envs"] = 0
    axis["modes"]["eval_gt"][name]["stop_end_error_median_rad"] = float("nan")
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    invalid, _ = judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert invalid["verdict"] == "HOLD"
    axis["modes"]["eval_gt"][name]["stop_complete_envs"] = 1
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    positive_nan, _ = judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert positive_nan["verdict"] == "HOLD"


def test_retry_writer_lock_and_source_mutation_do_not_claim_success(tmp_path, monkeypatch):
    checkpoint, prior = _original(tmp_path)
    root = tmp_path / "retries"
    root.mkdir()
    lock = root / "w57_retry.lock"
    lock.write_text("another writer", encoding="utf-8")
    with pytest.raises(RuntimeError, match="retry writer active"):
        retry(prior, checkpoint, root, "locked", runner=lambda *_: 0)
    assert not (root / "w57_retry_ledger.jsonl").exists()
    lock.unlink()
    original_copy = shutil.copy2

    def changed_copy(source, target):
        if str(source).endswith("map64\\map_modes.json"):
            Path(source).write_bytes(Path(source).read_bytes() + b" ")
        return original_copy(source, target)

    monkeypatch.setattr(retry_module.shutil, "copy2", changed_copy)
    with pytest.raises(ValueError, match="copied evidence changed"):
        retry(prior, checkpoint, root, "changed", runner=lambda *_: 0)
    assert not lock.exists() and not (root / "w57_retry_ledger.jsonl").exists()


def test_retry_checkpoint_mutation_during_child_cannot_write_ledger(tmp_path):
    checkpoint, prior = _original(tmp_path)
    root = tmp_path / "retries"

    def changed_checkpoint(*_):
        checkpoint.write_bytes(b"mutated during retry")
        return 4

    with pytest.raises(ValueError, match="checkpoint changed during retry"):
        retry(prior, checkpoint, root, "changed-checkpoint", runner=changed_checkpoint)
    assert not (root / "w57_retry_ledger.jsonl").exists()
    assert not (root / "w57_retry.lock").exists()


def test_retry_prior_evidence_mutation_during_child_cannot_write_ledger(tmp_path):
    checkpoint, prior = _original(tmp_path)
    root = tmp_path / "retries"

    def changed_evidence(*_):
        source = prior / "map64/map_modes.json"
        source.write_bytes(source.read_bytes() + b" ")
        return 4

    with pytest.raises(ValueError, match="prior evidence changed during retry"):
        retry(prior, checkpoint, root, "changed-evidence", runner=changed_evidence)
    assert not (root / "w57_retry_ledger.jsonl").exists()
    assert not (root / "w57_retry.lock").exists()
