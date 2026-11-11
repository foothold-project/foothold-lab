"""EX-42 E1 first segment on the E0 path: real E0 m250 parent, real mesh, real chain, real runner mirror switch.

E1 (CG E.2): E0 m250 -> 1000 updates, the same continuous exposure with level cap 5, D174 critic mirror on
at the start. CPU only; the real E0 run's model_250.pt / manifest.json are used when this machine has them.
"""
from __future__ import annotations

import ast
import json
import pathlib
import shutil
import subprocess
import types

import pytest
import torch
import yaml

from foothold_s2.curriculum.ex42_prep import EX42Plan, validate_stage_e1_authorization
from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.terrains import ex42_column_reset as cr
from foothold_s2.terrains import ex42_exposure as ex

ROOT = pathlib.Path(__file__).resolve().parents[2]
TABLE = ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2" / "curriculum" / "ex42-approvals.yaml"
TRAIN_START = ROOT / "foothold_s2" / "scripts" / "train_start.py"
E0_RUN = pathlib.Path("/home/jay/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218")
if not E0_RUN.is_dir():
    E0_RUN = pathlib.Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218")
MESH = pathlib.Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333")
needs_run = pytest.mark.skipif(not (E0_RUN / "model_250.pt").is_file(), reason="the E0 run is not on this machine")
E1_PARENT = entry.E1_PARENT_SHA256


def _approvals(tmp_path, *, cell=True, scale=1.0, later=False, parent=E1_PARENT, maximum=1000, mirror=True, name="approvals.yaml",
               cell_edit=None):
    doc = yaml.safe_load(APPROVALS.read_text(encoding="utf-8"))
    doc.pop("stage_e1_authorization", None)
    if cell:
        doc["stage_e1_authorization"] = {
            "approved": True, "decision_id": "lead-e1-test", "approved_at": "2026-11-11T10:30:00Z", "approver": "lead",
            "scope": {"stage_id": "E1", "start_update": 0, "maximum_updates": maximum, "parent_sha256": parent,
                      "later_stages_authorized": later},
            "prerequisites": {"e0_rejudgment": {"required_result": "PASS", "checkpoint_key": "model_250.pt",
                                                "checkpoint_sha256": E1_PARENT}},
            "extension_authorized": False, "boundary_evaluation_interval_updates": 250}
        if cell_edit:
            cell_edit(doc["stage_e1_authorization"])
    doc["domain_randomization"]["stage_scales"]["E1"] = scale
    if not mirror:
        doc["fields"]["critic_mirror"]["boundaries"] = []
    path = tmp_path / name
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return path


# ---- plan and approval ----
def test_the_pin_constant_matches_the_plan_and_shipped_e1_approval():
    plan = EX42Plan.load(TABLE)
    pin = next(r for r in plan.document["stages"] if r["id"] == "E1")["parent"]
    assert pin == {"cumulative_update": 13250, "manifest_local_update": 250, "checkpoint_key": "model_250.pt",
                   "sha256": E1_PARENT}
    assert (E1_PARENT, 250) in entry.REWARD_CONTRACT_PARENTS
    decision = validate_stage_e1_authorization(plan, APPROVALS, E1_PARENT)
    assert decision["boundary_evaluation_interval_updates"] == 250


def test_e1_cell_is_bounded_and_every_guard_refuses_on_its_own(tmp_path):
    plan = EX42Plan.load(TABLE)
    proof = validate_stage_e1_authorization(plan, _approvals(tmp_path), E1_PARENT)
    assert proof["state"] == "stage_e1_only_authorized" and proof["scope"]["maximum_updates"] == 1000
    assert proof["later_stages_authorized"] is False
    assert proof["boundary_evaluation_interval_updates"] == 250 and proof["extension_authorized"] is False
    assert proof["e0_rejudgment_prerequisite"]["required_result"] == "PASS"
    for kw, match in (({"cell": False}, "authorization is missing"), ({"later": True}, "scope differs"),
                      ({"parent": "0" * 64}, "scope differs"), ({"maximum": 2000}, "scope differs"),
                      ({"scale": 0.8}, "DR scale"), ({"mirror": False}, "D174")):
        with pytest.raises(ValueError, match=match):
            validate_stage_e1_authorization(plan, _approvals(tmp_path, **kw), E1_PARENT)


def _drop(key):
    return lambda cell: cell.pop(key)


def _set(path, value):
    def edit(cell):
        node = cell
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = value
    return edit


def test_e1_cell_conditions_are_read_not_assumed(tmp_path):
    """Reviewer 10:58 fix 1: the E0 re-judgement PASS prerequisite, extension_authorized false and the boundary
    interval are read from the cell and checked, each refusing on its own."""
    plan = EX42Plan.load(TABLE)
    cases = (
        (_drop("prerequisites"), "re-judgement PASS prerequisite"),
        (_set(("prerequisites", "e0_rejudgment", "required_result"), "HOLD"), "re-judgement PASS prerequisite"),
        (_set(("prerequisites", "e0_rejudgment", "checkpoint_sha256"), "0" * 64), "re-judgement PASS prerequisite"),
        (_set(("prerequisites", "e0_rejudgment", "checkpoint_key"), "model_1000.pt"), "re-judgement PASS prerequisite"),
        (_drop("extension_authorized"), "extension unauthorized"),
        (_set(("extension_authorized",), True), "extension unauthorized"),
        (_drop("boundary_evaluation_interval_updates"), "boundary evaluation interval"),
        (_set(("boundary_evaluation_interval_updates",), 500), "boundary evaluation interval"),      # differs from the plan 250
        (_set(("boundary_evaluation_interval_updates",), 250.0), "boundary evaluation interval"),
        (_set(("boundary_evaluation_interval_updates",), True), "boundary evaluation interval"),
    )
    for edit, match in cases:
        with pytest.raises(ValueError, match=match):
            validate_stage_e1_authorization(plan, _approvals(tmp_path, cell_edit=edit), E1_PARENT)


# ---- CLI ----
def _cli(tmp_path, parent_file, **over):
    base = dict(stage_id="E1", plan_path=TABLE, approvals_path=_approvals(tmp_path), experiment_path=ROOT / "experiments/EX-42.yaml",
                parent_checkpoint_path=parent_file, log_dir=tmp_path / "e1run", task=entry.STAGE_ZERO_TASK_ID,
                device="cuda:0", headless=True, distributed=True, max_iterations=1000, num_envs=3072,
                map_input="reconstruction", force_gt=False, approved_switch=True, world_size=2, rank=0)
    return base | over


@needs_run
def test_e1_cli_passes_on_the_real_m250_and_is_bounded_to_1000_updates_on_two_ranks(tmp_path):
    parent_file = E0_RUN / "model_250.pt"
    plan, parent, request = entry.validate_ex42_stage_e_cli(**_cli(tmp_path, parent_file))
    assert request["state"] == "stage_e1_preflight_passed" and request["max_iterations"] == 1000
    assert request["parent_cumulative_update"] == 13250 and request["total_envs"] == 6144
    assert request["critic_mirror"] == {"enabled_at_start": True, "decision_id": "D174"}
    for over, match in (({"max_iterations": 250}, "exactly 1000 updates"), ({"stage_id": "E1F"}, "E0 or E1 only"),
                        ({"distributed": False}, "exactly 1000 updates"), ({"num_envs": 1536}, "exactly 1000 updates"),
                        ({"force_gt": True}, "without forced GT"), ({"device": "cuda:1"}, "cuda:0")):
        with pytest.raises(ValueError, match=match):
            entry.validate_ex42_stage_e_cli(**_cli(tmp_path, parent_file, **over))
    other = tmp_path / "model_250.pt"
    other.write_bytes(b"not the parent")
    with pytest.raises(ValueError, match="differs from the pinned E0 m250"):
        entry.validate_ex42_stage_e_cli(**_cli(tmp_path, other))
    with pytest.raises(ValueError, match="authorization is missing"):
        entry.validate_ex42_stage_e_cli(**_cli(tmp_path, parent_file, approvals_path=_approvals(tmp_path, cell=False, name="no_cell.yaml")))


# ---- parent ----
@needs_run
def test_real_e0_m250_is_a_valid_e1_parent_and_its_placement_is_restored_with_diff_zero(tmp_path):
    plan = EX42Plan.load(TABLE)
    checkpoint, receipt = entry.inspect_ex42_stage_e1_parent(
        plan=plan, approvals_path=_approvals(tmp_path), parent_manifest_path=E0_RUN / "manifest.json")
    assert receipt["state"] == "parent_verified_for_stage_e1" and receipt["parent_cumulative_update"] == 13250
    assert receipt["parent_placement"] == "env_state_on_same_mesh" and checkpoint["ex41_critic_mirror"] is False
    with pytest.raises(ValueError, match="authorization is missing"):
        entry.inspect_ex42_stage_e1_parent(plan=plan, approvals_path=_approvals(tmp_path, cell=False),
                                           parent_manifest_path=E0_RUN / "manifest.json")
    # placement on the same mesh: 76 columns, exposure and cap from the plan's E1 section
    from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh
    families = list(load_combined_mesh(MESH / "terrain_mesh.npz")["column_family"])
    table = cr.build_column_table(families)
    stage = {**next(r for r in plan.document["stages"] if r["id"] == "E1")["terrain"],
             "kind_task": next(r for r in plan.document["stages"] if r["id"] == "E0")["terrain"]["kind_task"]}
    exposure, caps = ex.exposure_by_column(stage, table, "E1")
    e0_exposure, e0_caps = ex.exposure_by_column(
        next(r for r in plan.document["stages"] if r["id"] == "E0")["terrain"], table, "E0")
    assert (exposure, caps) == (e0_exposure, e0_caps) and max(caps) == 5 and sum(w > 0 for w in exposure) == 23
    env_state = checkpoint["env_state"]
    terrain = types.SimpleNamespace(
        terrain_levels=torch.zeros(3072, dtype=torch.long), terrain_types=torch.zeros(3072, dtype=torch.long),
        terrain_origins=torch.zeros(10, len(families), 3), env_origins=torch.zeros(3072, 3),
        update_env_origins=lambda *a: None)
    receipt = ex.apply_exposure(terrain, exposure, caps, parent_env_state=env_state, table=table, parent_same_mesh=True)
    assert torch.equal(terrain.terrain_types.cpu(), env_state["terrain_types"].long())
    assert torch.equal(terrain.terrain_levels.cpu(), env_state["terrain_levels"].long())       # diff 0 against the parent
    with pytest.raises(ValueError, match="outside the parent mesh"):                           # a column beyond the table
        ex.restore_parent_placement({**env_state, "terrain_types": env_state["terrain_types"] + 80}, table, 3072, same_mesh=True)


@needs_run
def test_real_m250_and_its_receipt_load_with_stage_e1_only(tmp_path):
    from foothold_s2.runners import start_runner
    from foothold_s2.tests.test_ex42_e0_launch_cpu import _loader_runner

    checkpoint, receipt = entry.inspect_ex42_stage_e1_parent(
        plan=EX42Plan.load(TABLE), approvals_path=_approvals(tmp_path), parent_manifest_path=E0_RUN / "manifest.json")
    pcfg = {**start_runner.MODE_DEFAULTS, **(checkpoint.get("perception_cfg") or {})}
    p_off = float(checkpoint["map_switch"]["p_map_off"])
    for kw in ({}, {"stage_e0": True}):
        with pytest.raises(ValueError, match="parent receipt is incomplete"):
            _loader_runner(p_off, pcfg).load_ex42_stage_zero_parent(checkpoint, receipt, **kw)
    runner = _loader_runner(p_off, pcfg)
    result = runner.load_ex42_stage_zero_parent(checkpoint, receipt, stage_e1=True)
    assert result["state"] == "loaded_for_ex42_stage_e1" and result["parent_cumulative_update"] == 13250
    assert result["local_iteration_origin"] == 0 and runner.current_learning_iteration == 0
    cfg = entry.configure_ex42_stage_zero_train_cfg({}, checkpoint, parent_path=receipt["parent_path"],
                                                    parent_sha256=receipt["parent_sha256"], updates=1000,
                                                    parent_local_update=250, parent_cumulative_update=13250, stage_id="E1")
    assert cfg["max_iterations"] == 1000 and cfg["ex41_critic_mirror"] is False         # the grant turns it on after load
    with pytest.raises(ValueError, match="not an approved value"):
        entry.configure_ex42_stage_zero_train_cfg({}, checkpoint, parent_path="p", parent_sha256="0" * 64, updates=250, stage_id="E1")


# ---- D174 mirror at the start of an E1 process: the real runner switch with the committed-file check ----
def _committed_copy(tmp_path):
    repo = tmp_path / "repo"
    (repo / "curriculum").mkdir(parents=True)
    for source in TABLE.parent.glob("*.yaml"):                 # the plan reads its source plans beside it
        shutil.copy(source, repo / "curriculum" / source.name)
    shutil.copy(_approvals(tmp_path), repo / "curriculum" / "ex42-approvals.yaml")
    git = lambda *a: subprocess.check_call(["git", "-C", str(repo), *a], stdout=subprocess.DEVNULL)
    git("init", "-q")
    git("add", "-A")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x")
    return repo


def _mirror_runner():
    from foothold_s2.runners import start_runner

    runner = object.__new__(start_runner.StartRunner)
    runner.ex41_pose_commands = True
    runner.ex41_critic_mirror = False
    runner.ex41_mirror_approval = None
    runner.alg = types.SimpleNamespace(mirror_enabled=False)
    runner._assert_ex41_joint_order = lambda: None
    return runner


def test_mirror_proof_turns_the_runner_mirror_on_only_for_committed_plan_and_approval_bytes(tmp_path):
    from foothold_s2.curriculum.ex42_runtime import critic_mirror_proof

    repo = _committed_copy(tmp_path)
    plan = EX42Plan.load(repo / "curriculum" / "ex42-prep.yaml")
    proof = critic_mirror_proof(plan, repo / "curriculum" / "ex42-approvals.yaml")
    runner = _mirror_runner()
    runner.set_ex41_critic_mirror(True, approval=proof)
    assert runner.ex41_critic_mirror is True and runner.alg.mirror_enabled is True
    (repo / "curriculum" / "ex42-prep.yaml").write_text(                      # edited after the commit -> refused, mirror off
        (repo / "curriculum" / "ex42-prep.yaml").read_text() + "\n# edited\n")
    runner = _mirror_runner()
    with pytest.raises(ValueError, match="committed approval files or SHA256 differ"):
        runner.set_ex41_critic_mirror(True, approval=proof)
    assert runner.ex41_critic_mirror is False and runner.alg.mirror_enabled is False


# ---- chain: the real builder with the E1 stage id; boundaries 250/500/750/1000 are queued behind training ----
@needs_run
def test_real_chain_builder_takes_the_e0_run_as_e1_parent_and_queues_every_boundary_behind_training(tmp_path, monkeypatch):
    import hashlib
    import os
    from foothold_s2.tests.test_ex42_e0_launch_cpu import _chain_kwargs

    kwargs = _chain_kwargs(tmp_path, monkeypatch)
    kwargs["parent_manifest_path"] = E0_RUN / "manifest.json"
    argv = json.loads(kwargs["score_argv_json"])
    argv[argv.index("--p1-stage-id") + 1] = "E1"
    kwargs["score_argv_json"] = json.dumps(argv)
    kwargs["queue_path"] = pathlib.Path(kwargs["machine_profile"]["paths"]["gpu_queue"])
    kwargs.pop("dispatch_path")
    with pytest.raises(ValueError):
        entry.build_ex42_training_chain(**kwargs)                          # no stage id: the stage-zero parent is looked for
    interval = validate_stage_e1_authorization(EX42Plan.load(TABLE), _approvals(tmp_path), E1_PARENT)["boundary_evaluation_interval_updates"]
    chain = entry.build_ex42_training_chain(**kwargs, current_stage_id="E1", p1_interval=interval, defer_until_pid=os.getpid())
    assert chain.p1_interval == 250 and chain.consumer.current_stage_id == "E1"
    assert chain.parent["checkpoint_sha256"] == E1_PARENT
    run = pathlib.Path(kwargs["run_dir"])
    manifest = {"progress": {"completed_updates": 0}, "checkpoints": {}}
    for iteration in (250, 300, 500, 750, 1000):
        data = f"model {iteration}".encode()
        (run / f"model_{iteration}.pt").write_bytes(data)
        manifest["checkpoints"][f"model_{iteration}.pt"] = hashlib.sha256(data).hexdigest()
        manifest["progress"]["completed_updates"] = iteration
        (run / "manifest.json").write_text(json.dumps(manifest))
        state = chain.on_checkpoint_saved(types.SimpleNamespace(log_dir=str(run)), iteration)
        assert (state["state"] == "queued") == (iteration % 250 == 0), (iteration, state)
        if iteration % 250 == 0:
            assert state["stage_id"] == "E1"
    items = json.loads(kwargs["queue_path"].read_text())["items"]
    assert [i["argv"][i["argv"].index("--checkpoint") + 1].rsplit("_", 1)[-1] for i in items] == [
        "250.pt", "500.pt", "750.pt", "1000.pt"]
    assert all(i["wait_pids"] == [os.getpid()] and i["gpu"] == 1 for i in items)     # wait for training, never mid-run


def test_deferred_pid_is_checked_and_plain_chains_queue_without_a_wait(tmp_path):
    import os
    from foothold_s2.ex42_chain import EX42TrainingChain
    from foothold_s2.tests.test_ex42_chain_cpu import make_chain, _manifested_checkpoint
    with pytest.raises(ValueError, match="training process id"):
        EX42TrainingChain.__init__(object.__new__(EX42TrainingChain), plan=None, approvals_path="", parent_manifest_path="",
                                   run_dir="", repo_root="", queue_path="", defer_until_pid=0)
    chain, _ = make_chain(tmp_path)
    ck = _manifested_checkpoint(tmp_path / "ck", 250)
    chain.register_checkpoint_p1(iteration=250, checkpoint_dir=ck.parent, score_argv=["python", "-m", "known.score_command"])
    assert "wait_pids" not in json.loads((tmp_path / "gpu/queue.json").read_text())["items"][0]
    assert os.getpid() > 1


# ---- train_start wiring (AST / text, no Kit) ----
def test_train_start_wires_e1_the_same_way_as_e0():
    src = TRAIN_START.read_text(encoding="utf-8")
    tree = ast.parse(src)
    assert 'EX42_STAGE_ID = "E1" if _E1_FLAGS else "E0" if _E0_FLAGS else "EX42_0_T0_prime"' in src
    assert "EX42_STAGE_UPDATES = 1000 if _E1_FLAGS else 250 if _E0_FLAGS else 1000" in src
    assert "--ex42_stage_e1_approved" in src and "--ex42_stage_e1_dry_run" in src
    assert "args_cli.ex42_stage_e1_approved != _pre_args.ex42_stage_e1_approved" in src
    calls = {n.func.attr: n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    load = calls["load_ex42_stage_zero_parent"]
    kw = {k.arg: ast.unparse(k.value) for k in load.keywords}
    assert kw["stage_e0"] == "EX42_STAGE_ID == 'E0'" and kw["stage_e1"] == "EX42_STAGE_ID == 'E1'"
    assert "runner.set_ex41_critic_mirror(True, approval=critic_mirror_proof(" in src          # mirror on right after the load
    assert src.index("load_ex42_stage_zero_parent(") < src.index("runner.set_ex41_critic_mirror(True")
    assert 'parent_same_mesh=(EX42_STAGE_ID == "E1")' in src and "stage_id=EX42_STAGE_ID)" in src
    assert '_e0_preflight["approval"]["boundary_evaluation_interval_updates"]' in src       # read from the approval cell
    assert 'if EX42_STAGE_ID == "E1" else EX42_STAGE_UPDATES)} if EX42_E0_REQUESTED else {}),' in src
    assert '**({"defer_until_pid": os.getpid()} if _E1_FLAGS else {})' in src               # boundaries wait for training
    assert "250" not in src[src.index('_e0_preflight["approval"]["boundary'):][:200]         # no hard-coded number there
    assert "inspect_ex42_stage_e1_parent(" in src


def test_e1_runtime_stamps_the_env_with_the_e1_stage_id_the_first_reset_check_compares():
    plan = types.SimpleNamespace(stages=[types.SimpleNamespace(name="s")])
    runtime = entry.EX42StageZeroRuntime(stage_zero_plan=plan, plan_sha256="1" * 64, approval_sha256="2" * 64,
                                         parent_sha256=E1_PARENT, maximum_updates=1000, push_vmax_mps=2.0, stage_id="E1")
    env = types.SimpleNamespace(num_envs=4, device="cpu")
    runtime.attach_environment(env, types.SimpleNamespace())
    assert env._ex42_stage_id == "E1" and runtime.maximum_updates == 1000
    assert env._ex41_terrain == {"policy": "performance", "level_cap": 5}          # the E1 first segment keeps cap 5
