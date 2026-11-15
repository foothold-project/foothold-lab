"""EX-42 speed probe (two ranks, 20 / 50 updates) and the E0 entry. CPU only, no Kit, no torch."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import EX42Plan, validate_stage_e0_authorization
from foothold_s2.scripts import ex42_training_entry as entry

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"
EXPERIMENT = ROOT / "experiments/EX-42.yaml"
TRAIN_START = ROOT / "foothold_s2/scripts/train_start.py"
TEST_PARENT_SHA = hashlib.sha256(b"parent").hexdigest()
E_PARENT_SHA = "20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768"
ZERO_SHA = "1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613"


def _zero_receipt():
    scope = {"stage_id": "EX42_0_T0_prime", "source_stage_id": "T0_prime", "start_update": 0,
             "maximum_updates": 1000, "parent_sha256": ZERO_SHA, "later_stages_authorized": False}
    return {"state": "parent_verified_for_stage_zero", "parent_sha256": ZERO_SHA,
            "approval": {"state": "stage_zero_only_authorized", "scope": scope,
                         "approvals_sha256": "a" * 64, "later_stages_authorized": False}}


@pytest.fixture
def zero_args(tmp_path, monkeypatch):
    monkeypatch.setattr(entry, "inspect_ex42_stage_zero_parent",
                        lambda **_k: ({"format": "foothold-start/1", "iter": 6000}, _zero_receipt()))
    return dict(plan_path=TABLE, approvals_path=APPROVALS, parent_manifest_path=tmp_path / "manifest.json",
                log_dir=tmp_path / "run", task=entry.STAGE_ZERO_TASK_ID, device="cuda:0", headless=True,
                distributed=False, max_iterations=1000, num_envs=3072, map_input="reconstruction",
                force_gt=False, approved_switch=True)


# ---- speed probe ----

def test_probe_off_is_unchanged_and_probe_values_are_refused_without_the_switch(zero_args):
    request = entry.validate_ex42_stage_zero_cli(**zero_args)[3]
    assert "speed_probe" not in request and request["max_iterations"] == 1000
    for change in ({"max_iterations": 20}, {"num_envs": 1536}, {"distributed": True}):
        with pytest.raises(ValueError, match="stage zero requires|bounded to exactly 1000"):
            entry.validate_ex42_stage_zero_cli(**(zero_args | change))
    assert entry.stage_zero_updates(1000, False) == 1000 and entry.stage_zero_updates(20, False) == 1000


@pytest.mark.parametrize("updates,envs,dist", [(20, 3072, False), (20, 1536, True), (50, 3072, True), (50, 1536, True)])
def test_probe_on_allows_two_ranks_and_the_bounded_counts(zero_args, updates, envs, dist):
    request = entry.validate_ex42_stage_zero_cli(
        **(zero_args | {"max_iterations": updates, "num_envs": envs, "distributed": dist}), speed_probe=True)[3]
    assert request["speed_probe"] == {"updates": updates, "num_envs": envs, "distributed": dist}
    assert request["production_launch_allowed"] is False and request["later_stages_authorized"] is False
    assert entry.stage_zero_updates(updates, True) == updates


@pytest.mark.parametrize("change", [{"max_iterations": 1000}, {"max_iterations": 21}, {"num_envs": 2048},
                                    {"device": "cuda:1"}, {"headless": False}, {"approved_switch": False},
                                    {"resume_from": "model_350.pt", "self_resume": True}])
def test_probe_on_still_refuses_everything_else(zero_args, change):
    with pytest.raises(ValueError):
        entry.validate_ex42_stage_zero_cli(**(zero_args | {"max_iterations": 20} | change), speed_probe=True)


def test_probe_rank_directories_rank0_is_the_run_dir_and_others_are_private(tmp_path):
    run = tmp_path / "M2_x"
    assert entry.speed_probe_rank_log_dir(run, 0, True) == str(run)
    assert entry.speed_probe_rank_log_dir(run, 1, False) == str(run)          # probe off: nothing changes
    other = Path(entry.speed_probe_rank_log_dir(run, 1, True))
    assert other != run and run not in other.parents and not other.exists()    # not created, not under the run dir
    # rank 1 passes the "new output" check on its own path while rank 0 has already created the shared one
    run.mkdir()
    (run / "startup_receipt.json").write_text("{}")


def test_rank_one_passes_the_new_output_check_even_after_rank_zero_made_the_shared_dir(zero_args, tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "startup_receipt.json").write_text("{}")
    with pytest.raises(ValueError, match="must be new"):
        entry.validate_ex42_stage_zero_cli(**(zero_args | {"log_dir": shared, "max_iterations": 20,
                                                           "distributed": True}), speed_probe=True)
    private = entry.speed_probe_rank_log_dir(shared, 1, True)
    entry.validate_ex42_stage_zero_cli(**(zero_args | {"log_dir": private, "max_iterations": 20,
                                                       "distributed": True}), speed_probe=True)
    assert sorted(p.name for p in shared.iterdir()) == ["startup_receipt.json"]    # rank 1 added nothing there


def test_runtime_and_train_cfg_accept_the_probe_bound_only_with_the_probe():
    with pytest.raises(ValueError, match="bounded to 1000"):
        entry.EX42StageZeroRuntime.__init__.__wrapped__ if False else None
        entry.EX42StageZeroRuntime(stage_zero_plan=type("P", (), {"stages": [object()]})(), plan_sha256="p",
                                   approval_sha256="a", parent_sha256="s", maximum_updates=20, push_vmax_mps=1.0)
    runtime = entry.EX42StageZeroRuntime(stage_zero_plan=type("P", (), {"stages": [object()]})(), plan_sha256="p",
                                         approval_sha256="a", parent_sha256="s", maximum_updates=20,
                                         push_vmax_mps=1.0, speed_probe=True)
    assert runtime.maximum_updates == 20
    with pytest.raises(ValueError, match="not an approved value"):
        entry.configure_ex42_stage_zero_train_cfg({}, {}, parent_path="x", parent_sha256="y", updates=21)


def test_train_start_wiring_has_every_site_that_pinned_1000():
    text = TRAIN_START.read_text(encoding="utf-8")
    ast.parse(text)
    assert text.count("args_cli.max_iterations if args_cli.ex42_speed_probe else EX42_STAGE_UPDATES") == 6
    assert "agent_cfg.max_iterations = 1000\n" not in text                       # every literal 1000 bound is now switch-aware


@pytest.mark.parametrize("bad", [0, 2, 19, 21, 51, 100, 1000])
def test_probe_update_bound_is_exactly_20_and_50(zero_args, bad):
    assert entry.SPEED_PROBE_UPDATES == (20, 50) and entry.SPEED_PROBE_ENVS == (1536, 3072)
    with pytest.raises(ValueError):
        entry.validate_ex42_stage_zero_cli(**(zero_args | {"max_iterations": bad}), speed_probe=True)
    if bad != 1000:
        with pytest.raises(ValueError, match="not an approved value"):
            entry.configure_ex42_stage_zero_train_cfg({}, {}, parent_path="x", parent_sha256="y", updates=bad)
        with pytest.raises(ValueError, match="bounded to 1000"):
            entry.EX42StageZeroRuntime(stage_zero_plan=type("P", (), {"stages": [object()]})(), plan_sha256="p",
                                       approval_sha256="a", parent_sha256="s", maximum_updates=bad,
                                       push_vmax_mps=1.0, speed_probe=True)


# ---- train_start pre-parse block, run for real in a subprocess (rank, guards) ----

def _preparse_harness(tmp_path, argv, local_rank):
    """Execute train_start's pre-parser through the rank override, exactly as written in the file."""
    import json
    import subprocess
    import sys
    text = TRAIN_START.read_text(encoding="utf-8")
    head = text[text.index("_pre = argparse.ArgumentParser"):text.index("EX41_PLAN = None")]
    script = tmp_path / "harness.py"
    script.write_text("import argparse, os, sys, json\n" + head
                      + "\nprint(json.dumps({'rank': EX42_SPEED_PROBE_RANK, 'log_dir': _pre_args.ex42_log_dir}))\n",
                      encoding="utf-8")
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT), "LOCAL_RANK": str(local_rank)}
    return subprocess.run([sys.executable, str(script)] + argv, env=env, capture_output=True, text=True, cwd=ROOT)


def test_preparse_moves_only_non_zero_ranks_to_a_private_dir(tmp_path):
    import json
    argv = ["--ex42_speed_probe", "--ex42_log_dir", str(tmp_path / "run" / "M2_x")]
    got = {}
    for rank in (0, 1):
        proc = _preparse_harness(tmp_path, argv, rank)
        assert proc.returncode == 0, proc.stderr
        got[rank] = json.loads(proc.stdout.splitlines()[-1])
    assert got[0]["log_dir"] == argv[-1] and got[0]["rank"] == 0
    assert got[1]["rank"] == 1 and got[1]["log_dir"] != argv[-1] and "ex42_probe_rank1_M2_x" in got[1]["log_dir"]
    off = _preparse_harness(tmp_path, ["--ex42_log_dir", argv[-1]], 1)                 # probe off: rank is ignored
    assert json.loads(off.stdout.splitlines()[-1]) == {"rank": 0, "log_dir": argv[-1]}


def test_speed_probe_needs_a_stage_approval_switch():
    entry.validate_speed_probe_switches(speed_probe=False, stage_zero_requested=False, stage_e0_requested=False)
    entry.validate_speed_probe_switches(speed_probe=True, stage_zero_requested=True, stage_e0_requested=False)
    entry.validate_speed_probe_switches(speed_probe=True, stage_zero_requested=False, stage_e0_requested=True)
    with pytest.raises(ValueError, match="only valid with"):
        entry.validate_speed_probe_switches(speed_probe=True, stage_zero_requested=False, stage_e0_requested=False)


def test_train_start_calls_the_entry_helpers_in_the_places_that_matter():
    text = TRAIN_START.read_text(encoding="utf-8")
    for needle in ("validate_speed_probe_switches(speed_probe=_pre_args.ex42_speed_probe",
                   "run_ex42_stage_e0_entry(", "dry_run=_e_dry_run",
                   "speed_probe_builds_chain(\n            EX42_RANK_SPLIT, EX42_SPEED_PROBE_RANK)",
                   "args_cli.ex42_log_dir = speed_probe_rank_log_dir(", "raise SystemExit(0)"):
        assert needle in text, needle


# ---- rank 1 on the real Linux machine profile (reviewer r593_rank1_chain.py, through the same gate train_start uses) ----

def _linux_profile(work, monkeypatch):
    names = ("A_LAYER_MARKER C_LAYER_LOCK EX41_PUSH250_OUTPUT EX41_STAGE_VIDEO_OUTPUT EX41_STAGE_VIDEO_SOURCE "
             "EX41_W78_VIDEO_ROOT FOOTHOLD_BASH FOOTHOLD_EX42_GATE_REPORT GPU0_EVAL_MARKER GPU0_TRAINING_MARKER "
             "GPU0_TRAINING_MARKER_ALT GPU1_EVAL_MARKER GPU1_TRAINING_MARKER GPU_JOBS_CONFIG GPU_JOBS_QUEUE "
             "ISAAC311_PYTHON ISAAC_CACHE_ROOT ISAACLAB_ROOT ISAAC_SIM_ROOT MAI_TMP_ROOT MAI_WORKTREE_ROOT "
             "PLAYLIST_ROOT RSL_RL_MODULE RUNNER_HOME S2_LAB_ROOT TELEGRAM_OUTBOX TELEGRAM_SCRIPT").split()
    for name in names:
        monkeypatch.setenv(name, str(work / name.lower()))
    monkeypatch.setenv("GPU0_UUID", "GPU-11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("GPU1_UUID", "GPU-22222222-2222-2222-2222-222222222222")
    monkeypatch.setenv("FOOTHOLD_MACHINE_PROFILE", str(ROOT / "machines/AI-WS01-linux.yaml"))
    from foothold_s2.machine_profile import load_machine_profile
    return load_machine_profile()


def test_two_rank_probe_on_the_linux_profile_builds_one_chain_and_rank1_does_not_die(tmp_path, monkeypatch):
    import json
    from foothold_s2.tests.test_ex42_calibrate_cpu import mesh_fixture

    profile = _linux_profile(tmp_path, monkeypatch)
    run_dir = tmp_path / "s2_lab" / "ex42_probe_m2"
    mesh_dir = tmp_path / "mesh"
    mesh_dir.mkdir()
    mesh = mesh_fixture(mesh_dir)
    argv = [profile["paths"]["conda_python"], "-m", "foothold_s2.ex42_eval_once",
            "--checkpoint", str(run_dir / "model_{iteration}.pt"), "--sha-from-manifest",
            "--out", str(tmp_path / "scores" / "p1_{iteration}"), "--device", "cuda:1",
            "--eval-seed", "42", "--mesh-dir", str(mesh_dir),
            "--expected-mesh-sha256", mesh["mesh_sha256"], "--p1-plan", str(TABLE),
            "--p1-approvals", str(APPROVALS), "--p1-stage-id", "EX42_0_T0_prime", "--execute"]

    def build(rank):
        return entry.build_ex42_training_chain(
            plan_path=TABLE, approvals_path=APPROVALS, parent_manifest_path=tmp_path / "manifest.json",
            run_dir=entry.speed_probe_rank_log_dir(run_dir, rank, True), repo_root=ROOT,
            queue_path=tmp_path / "gpu_jobs_queue", score_argv_json=json.dumps(argv),
            machine_profile=profile, dispatch_path=tmp_path / "dispatch.json")

    with pytest.raises(FileNotFoundError):                        # rank 0 passes the P1 command check, stops at the missing manifest
        build(0)
    with pytest.raises(ValueError, match="does not score this manifest-published checkpoint"):
        build(1)                                                  # negative control: rank 1 would die here if it built a chain
    built = [rank for rank in (0, 1) if entry.speed_probe_builds_chain(True, rank)]
    assert built == [0]                                           # the gate train_start uses: rank 1 builds nothing
    assert entry.speed_probe_builds_chain(False, 1) is True       # probe off: every rank builds as before


# ---- E0 entry ----

def _approvals(tmp_path, *, cell=True, e0_scale=1.0, later=False, parent=TEST_PARENT_SHA, edit=None):
    doc = yaml.safe_load(APPROVALS.read_text(encoding="utf-8"))
    doc.pop("stage_e0_authorization", None)  # cell=False must mean missing, even after E0 approval.
    if cell:
        doc["stage_e0_authorization"] = {
            "approved": True, "decision_id": "lead-e0-test", "approved_at": "2026-11-10T00:00:00Z", "approver": "lead",
            "scope": {"stage_id": "E0", "start_update": 0, "maximum_updates": 250, "parent_sha256": parent,
                      "later_stages_authorized": later}}
    doc["domain_randomization"]["stage_scales"]["E0"] = e0_scale
    if edit:
        edit(doc)
    path = tmp_path / "approvals.yaml"
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture
def parent_file(tmp_path):
    folder = tmp_path / "stage0_run"
    folder.mkdir()
    return folder / "model_1000.pt"


def _e0_args(tmp_path, approvals, parent_file, monkeypatch, **over):
    parent_file.write_bytes(b"parent")
    monkeypatch.setattr(entry, "read_e_stage_parent", lambda _p: {
        "cumulative_update": 13000, "checkpoint_key": "model_1000.pt", "sha256": TEST_PARENT_SHA})
    base = dict(stage_id="E0", plan_path=TABLE, approvals_path=approvals, experiment_path=EXPERIMENT,
                parent_checkpoint_path=parent_file, log_dir=tmp_path / "e0run", task=entry.STAGE_ZERO_TASK_ID,
                device="cuda:0", headless=True, distributed=False, max_iterations=250, num_envs=3072,
                map_input="reconstruction", force_gt=False, approved_switch=True)
    return base | over


def test_shipped_approvals_authorize_only_the_bounded_e0_entry():
    plan = EX42Plan.load(TABLE)
    proof = validate_stage_e0_authorization(plan, APPROVALS, E_PARENT_SHA)
    assert proof["scope"]["maximum_updates"] == 250
    assert proof["scope"]["later_stages_authorized"] is False
    parent = entry.read_e_stage_parent(EXPERIMENT)
    assert parent["sha256"] == E_PARENT_SHA and parent["cumulative_update"] == 13000


def test_e0_cell_present_passes_and_is_bounded(tmp_path, parent_file, monkeypatch):
    approvals = _approvals(tmp_path)
    plan, parent, request = entry.validate_ex42_stage_e_cli(**_e0_args(tmp_path, approvals, parent_file, monkeypatch))
    assert request["state"] == "stage_e0_preflight_passed" and request["max_iterations"] == 250
    assert request["parent_cumulative_update"] == 13000 and request["later_stages_authorized"] is False
    assert request["approval"]["scope"]["maximum_updates"] == 250


@pytest.mark.parametrize("kw,match", [
    ({"cell": False}, "authorization is missing"),
    ({"later": True}, "scope differs"),
    ({"parent": ZERO_SHA}, "scope differs"),
    ({"e0_scale": 0.8}, "DR scale"),
])
def test_e0_cell_missing_or_wrong_is_refused(tmp_path, parent_file, monkeypatch, kw, match):
    with pytest.raises(ValueError, match=match):
        entry.validate_ex42_stage_e_cli(**_e0_args(tmp_path, _approvals(tmp_path, **kw), parent_file, monkeypatch))


@pytest.mark.parametrize("over,match", [
    ({"stage_id": "E1F"}, "E0 or E1 only"), ({"stage_id": "E2"}, "E0 or E1 only"), ({"stage_id": "M"}, "E0 or E1 only"),
    ({"approved_switch": False}, "approval switch"), ({"max_iterations": 1000}, "exactly 250"),
    ({"num_envs": 1536}, "exactly 250"), ({"distributed": True}, "exactly 250"), ({"device": "cuda:1"}, "cuda:0"),
    ({"force_gt": True}, "forced GT"), ({"task": "other"}, "task differs"),
])
def test_e0_refuses_e1_and_every_unbounded_variant(tmp_path, parent_file, monkeypatch, over, match):
    with pytest.raises(ValueError, match=match):
        entry.validate_ex42_stage_e_cli(**_e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch, **over))


def test_e0_refuses_a_wrong_parent_and_an_existing_output(tmp_path, parent_file, monkeypatch):
    approvals = _approvals(tmp_path)
    args = _e0_args(tmp_path, approvals, parent_file, monkeypatch)
    parent_file.write_bytes(b"other bytes")
    with pytest.raises(ValueError, match="pinned m13000"):
        entry.validate_ex42_stage_e_cli(**args)
    parent_file.write_bytes(b"parent")
    (tmp_path / "e0run").mkdir()
    with pytest.raises(ValueError, match="must be new"):
        entry.validate_ex42_stage_e_cli(**args)


def test_e0_speed_probe_uses_the_same_bounded_path(tmp_path, parent_file, monkeypatch):
    args = _e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch, max_iterations=20, distributed=True, num_envs=1536)
    request = entry.validate_ex42_stage_e_cli(**args, speed_probe=True)[2]
    assert request["speed_probe"] == {"updates": 20, "num_envs": 1536, "distributed": True}
    with pytest.raises(ValueError, match="exactly 250"):
        entry.validate_ex42_stage_e_cli(**args)                                 # probe values without the switch


def test_the_shipped_approval_file_remains_pinned_and_full_plan_blocked():
    from foothold_s2.curriculum.ex42_prep import validate_stage_zero_authorization
    plan = EX42Plan.load(TABLE)
    proof = validate_stage_zero_authorization(plan, APPROVALS)
    assert proof["production_launch_allowed"] is False
    assert proof["later_stages_authorized"] is False


@pytest.mark.parametrize("name,edit", [
    ("approved_yes", lambda d: d["stage_e0_authorization"].__setitem__("approved", "yes")),
    ("status_open", lambda d: d.__setitem__("status", "approved")),
    ("production_open", lambda d: d.__setitem__("production_launch_allowed", True)),
    ("automatic_open", lambda d: d.__setitem__("automatic_launch_allowed", True)),
    ("no_decision_id", lambda d: d["stage_e0_authorization"].__setitem__("decision_id", " ")),
    ("no_approved_at", lambda d: d["stage_e0_authorization"].__setitem__("approved_at", "")),
    ("no_approver", lambda d: d["stage_e0_authorization"].__setitem__("approver", None)),
    ("dr_not_approved", lambda d: d["domain_randomization"].__setitem__("approved", "yes")),
    ("scope_stage", lambda d: d["stage_e0_authorization"]["scope"].__setitem__("stage_id", "E1")),
    ("scope_start", lambda d: d["stage_e0_authorization"]["scope"].__setitem__("start_update", 1)),
    ("scope_max", lambda d: d["stage_e0_authorization"]["scope"].__setitem__("maximum_updates", 251)),
])
def test_every_closing_condition_of_the_e0_approval_is_pinned(tmp_path, name, edit):
    plan = EX42Plan.load(TABLE)
    validate_stage_e0_authorization(plan, _approvals(tmp_path), TEST_PARENT_SHA)         # control: the unedited cell opens
    with pytest.raises(ValueError):
        validate_stage_e0_authorization(plan, _approvals(tmp_path, edit=edit), TEST_PARENT_SHA)


@pytest.mark.parametrize("key,value", [("minimum_updates", 249), ("maximum_updates", 251), ("extension_updates", 1), ("enabled", False)])
def test_e0_stage_row_must_be_the_bounded_250_update_row(tmp_path, key, value):
    plan = EX42Plan.load(TABLE)
    row = next(r for r in plan.document["stages"] if r["id"] == "E0")
    original = row[key]
    row[key] = value
    try:
        with pytest.raises(ValueError, match="bounded 250-update stage"):
            validate_stage_e0_authorization(plan, _approvals(tmp_path), TEST_PARENT_SHA)
    finally:
        row[key] = original


def test_e0_entry_as_train_start_calls_it_never_starts_training(tmp_path, parent_file, monkeypatch):
    args = _e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch)
    args.pop("approved_switch")
    args.pop("stage_id")
    cli = dict(args, stage_id="E0")
    request = entry.run_ex42_stage_e0_entry(dry_run=True, stage_zero_requested=False, resume_requested=False,
                                            e0_approved=True, **cli)
    assert request["state"] == "stage_e0_preflight_passed"
    assert request["training_requested"] is False
    assert request["terrain_mesh_swap"]["state"] == "mounted_at_env_build"
    assert request["terrain_mesh_swap"]["terrain_manifest"]["state"] == "missing_or_invalid"
    assert request["training_blockers"] == ["terrain_manifest_missing_or_invalid"]
    with pytest.raises(ValueError, match="terrain_manifest_missing"):
        entry.run_ex42_stage_e0_entry(dry_run=False, stage_zero_requested=False, resume_requested=False,
                                      e0_approved=True, **cli)
    with pytest.raises(ValueError, match="cannot be combined"):
        entry.run_ex42_stage_e0_entry(dry_run=True, stage_zero_requested=True, resume_requested=False,
                                      e0_approved=True, **cli)
    with pytest.raises(ValueError, match="cannot be combined"):
        entry.run_ex42_stage_e0_entry(dry_run=True, stage_zero_requested=False, resume_requested=True,
                                      e0_approved=True, **cli)
    with pytest.raises(ValueError, match="also requires"):
        entry.run_ex42_stage_e0_entry(dry_run=True, stage_zero_requested=False, resume_requested=False,
                                      e0_approved=False, **cli)


def _chain_selection_node():
    tree = ast.parse(TRAIN_START.read_text(encoding="utf-8"))
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.If) and "speed_probe_builds_chain" in ast.dump(n.test)]
    assert len(nodes) == 1, "the rank gate in front of the stage-zero chain build must exist exactly once"
    return nodes[0]


def _run_chain_selection(speed_probe, rank):
    """Execute the real if/elif block from train_start.py with stubs; return (built_calls, chain)."""
    node = _chain_selection_node()
    built = []
    ns = {
        "EX42_STAGE_ZERO_PLAN": type("P", (), {"sha256": "p"})(), "EX42_STAGE_ZERO_PARENT": {"parent_sha256": "s"},
        "EX42_STAGE_ZERO_RESUME_SAME_RUN": False, "EX42_STAGE_ZERO_RESUME": None, "EX42_SPEED_PROBE_RANK": rank, "EX42_RANK_SPLIT": speed_probe,
        "EX42_TRAINING_CHAIN": None, "EX42_STAGE_ZERO_CHAIN_RECEIPT": None, "json": __import__("json"),
        "_pre_args": type("A", (), {"ex42_speed_probe": speed_probe, "ex42_log_dir": "x"})(),
        "speed_probe_builds_chain": entry.speed_probe_builds_chain, "_build_ex42_chain": lambda: "chain",
        "build_stage_zero_chain_with_receipt_checks": lambda *a, **k: (built.append(1) or ("chain", {"state": "ok"})),
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), "train_start_chain_selection", "exec"), ns)
    return built, ns["EX42_TRAINING_CHAIN"]


def test_the_real_rank_gate_in_train_start_skips_the_chain_only_for_probe_rank_one():
    assert _run_chain_selection(True, 0) == ([1], "chain")        # rank 0 builds
    assert _run_chain_selection(True, 1) == ([], None)            # probe rank 1 builds nothing
    assert _run_chain_selection(False, 1) == ([1], "chain")       # probe off: every rank builds as before


def test_e0_real_run_with_measured_manifest_returns_the_request_for_training(
        tmp_path, parent_file, monkeypatch):
    args = _e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch)
    args.pop("approved_switch")
    monkeypatch.setattr(entry, "read_e0_terrain_manifest", lambda plan, path: {
        "state": "measured", "path": "x", "sha256": "0" * 64, "kinds": 46, "receipt_ids": []})
    request = entry.run_ex42_stage_e0_entry(dry_run=False, stage_zero_requested=False, resume_requested=False,
                                            e0_approved=True, terrain_manifest_path="m.json", **args)
    assert request["training_requested"] is True and request["total_envs"] == 3072


def test_read_e0_terrain_manifest_fails_closed(tmp_path):
    plan = EX42Plan.load(TABLE)
    with pytest.raises(ValueError, match="terrain_manifest_missing"):
        entry.read_e0_terrain_manifest(plan, None)
    with pytest.raises(ValueError, match="terrain_manifest_missing"):
        entry.read_e0_terrain_manifest(plan, tmp_path / "nope.json")
    partial = tmp_path / "terrain_manifest.json"
    partial.write_text('{"format": "foothold-ex42-terrain-manifest/1", "status": "partial"}', encoding="utf-8")
    with pytest.raises(ValueError, match="not measured"):
        entry.read_e0_terrain_manifest(plan, partial)
    partial.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        entry.read_e0_terrain_manifest(plan, partial)


def test_train_start_passes_the_manifest_path_and_only_dry_run_exits():
    text = (Path(__file__).resolve().parents[1] / "scripts" / "train_start.py").read_text(encoding="utf-8")
    assert "terrain_manifest_path=_pre_args.ex42_terrain_manifest" in text
    assert "raise SystemExit(0 if _pre_args.ex42_stage_e0_dry_run else 3)" not in text      # real E0 no longer exits 3
    assert "if _e_dry_run and not _pre_args.ex42_resume_from:\n            raise SystemExit(0)" in text                        # only the dry run exits (E0 and E1 flags)
    assert text.count("--ex42_terrain_manifest") == 2


def test_e0_accepts_one_process_or_a_two_rank_torchrun_with_3072_per_rank(tmp_path, parent_file, monkeypatch):
    approvals = _approvals(tmp_path)
    one = entry.validate_ex42_stage_e_cli(**_e0_args(tmp_path, approvals, parent_file, monkeypatch))[2]
    assert one["world_size"] == 1 and one["total_envs"] == 3072
    for rank in (0, 1):
        two = entry.validate_ex42_stage_e_cli(**_e0_args(
            tmp_path, approvals, parent_file, monkeypatch, distributed=True, world_size=2, rank=rank))[2]
        assert two["rank"] == rank and two["total_envs"] == 6144 and two["num_envs"] == 3072
    for bad in ({"distributed": True}, {"world_size": 2}, {"distributed": True, "world_size": 3},
                {"distributed": True, "world_size": 2, "rank": 2}, {"distributed": True, "world_size": 2, "num_envs": 6144}):
        with pytest.raises(ValueError, match="exactly 250"):
            entry.validate_ex42_stage_e_cli(**_e0_args(tmp_path, approvals, parent_file, monkeypatch, **bad))


def test_only_rank_zero_insists_the_run_directory_is_new(tmp_path, parent_file, monkeypatch):
    approvals = _approvals(tmp_path)
    (tmp_path / "e0run").mkdir()
    over = dict(distributed=True, world_size=2)
    with pytest.raises(ValueError, match="must be new"):
        entry.validate_ex42_stage_e_cli(**_e0_args(tmp_path, approvals, parent_file, monkeypatch, rank=0, **over))
    entry.validate_ex42_stage_e_cli(**_e0_args(tmp_path, approvals, parent_file, monkeypatch, rank=1, **over))
