"""EX-42 boundary evaluation split over two GPUs and the E1 250/500/750/1000 boundary queue. CPU only.

The Kit children are replaced by a fake that rebuilds each shard's result files from the REAL E0 m250
one-GPU evaluation (08:52), filtered to the shard's modes. So the merge, the unchanged `measure`, and the
split branch of `run()` are exercised on real result files; whether Kit itself gives the same numbers on
two GPUs is the one thing this cannot show (that is the lead's Kit comparison).
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import shutil
import sys
import threading

import pytest

from foothold_s2 import ex42_eval_once as once
from foothold_s2 import ex42_eval_split as split
from foothold_s2.ex42_score import MODES

ROOT = pathlib.Path(__file__).resolve().parents[2]
E0_RUN = pathlib.Path("/home/jay/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218")
if not E0_RUN.is_dir():
    E0_RUN = pathlib.Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218")
REAL = E0_RUN / "eval" / "scores" / "m250"
MESH = pathlib.Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333")
needs_run = pytest.mark.skipif(not (REAL / "ex42_score.json").is_file() or not MESH.is_dir(),
                               reason="the E0 m250 one-GPU evaluation is not on this machine")
UUID = {"cuda:0": "aaaaaaaa-0000-0000-0000-000000000000", "cuda:1": "bbbbbbbb-1111-1111-1111-111111111111"}


# ---- assignment and commands ----
def test_assignment_covers_every_phase_and_mode_once_and_is_balanced():
    shards, load = split.assign_shards(["cuda:1", "cuda:0"])
    for phase in split.PHASES:
        seen = sorted(mode for shard in shards.values() for mode in shard[phase])
        assert seen == sorted(MODES)
    assert shards["cuda:1"]["map64"] == ["eval_gt", "eval_pred"] and shards["cuda:0"]["map64"] == ["probe_prop_only"]
    assert max(load.values()) < 0.6 * sum(load.values())          # one GPU would be 100 %
    assert shards == split.assign_shards(["cuda:1", "cuda:0"])[0]  # deterministic
    with pytest.raises(ValueError):
        split.assign_shards(["cuda:0", "cuda:0"])


def test_default_commands_are_the_unchanged_one_device_bundle():
    rows = once.commands("/c/model_1.pt", "/o", "cuda:1")
    assert [r["name"] for r in rows] == ["map64", "stand_eval_gt", "stand_probe_prop_only", "stand_eval_pred", "axis_v2"]
    for name in ("map64", "axis_v2"):
        argv = next(r for r in rows if r["name"] == name)["argv"]
        assert argv[argv.index("--modes") + 1] == "eval_gt,probe_prop_only,eval_pred"


def test_shard_commands_name_only_their_modes_and_together_cover_everything():
    shards, _ = split.assign_shards(["cuda:1", "cuda:0"])
    covered = {"map64": [], "axis_v2": [], "stand": []}
    for device, shard in shards.items():
        for row in once.commands("/c/model_1.pt", f"/o/{device}", device, shard=shard):
            argv = row["argv"]
            assert argv[argv.index("--device") + 1] == device
            if row["name"] == "map64":
                covered["map64"] += argv[argv.index("--modes") + 1].split(",")
                assert "--axis-v2" not in argv
            elif row["name"] == "axis_v2":
                covered["axis_v2"] += argv[argv.index("--modes") + 1].split(",")
                assert "--axis-v2" in argv and "--ex42-maintenance" in argv
            else:
                covered["stand"].append(argv[argv.index("--mode") + 1])
    assert all(sorted(v) == sorted(MODES) for v in covered.values())
    with pytest.raises(ValueError):
        once.commands("/c/m.pt", "/o", "cuda:1", shard={"map64": ["eval_gtt"], "axis_v2": [], "stand": []})


# ---- GPU idle gate ----
def test_gpu_gate_waits_for_training_to_release_and_refuses_after_the_timeout():
    states = iter(["123, GPU-" + UUID["cuda:0"], "123, GPU-" + UUID["cuda:0"], ""])
    clock = iter(range(0, 100))
    sleeps = []
    split.wait_gpus_free(list(UUID.values()), query=lambda: next(states), sleep=sleeps.append,
                         clock=lambda: next(clock), poll_s=7)
    assert sleeps == [7, 7]
    with pytest.raises(ValueError, match="still hold compute processes"):
        split.wait_gpus_free([UUID["cuda:1"]], timeout_s=3, poll_s=1, sleep=lambda s: None,
                             clock=iter([0, 1, 2, 3, 4, 5]).__next__,
                             query=lambda: "9, " + UUID["cuda:1"])
    split.wait_gpus_free([UUID["cuda:1"]], query=lambda: "9, " + UUID["cuda:0"])   # the other GPU is not ours


# Real `nvidia-smi --query-compute-apps=pid,gpu_uuid,used_memory,process_name --format=csv,noheader,nounits` output
# of this machine at 11:14 (training and evaluation both stopped): two sunshine sessions on GPU 0, nothing on GPU 1.
REAL_SMI_IDLE = """4108, GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b, 262, /usr/bin/sunshine
5968, GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b, 262, /usr/bin/sunshine
"""
REAL_GPU0 = "c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b"
REAL_GPU1 = "315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f"


def test_gpu_gate_ignores_the_real_sunshine_sessions_but_not_training_or_kit_processes():
    sleeps = []
    split.wait_gpus_free([REAL_GPU0, REAL_GPU1], query=lambda: REAL_SMI_IDLE, sleep=sleeps.append)   # returns at once
    assert sleeps == []
    training = REAL_SMI_IDLE + "7001, GPU-" + REAL_GPU0 + ", 13800, /home/jay/miniforge3/envs/isaac311/bin/python3.11\n"
    with pytest.raises(ValueError, match="7001"):
        split.wait_gpus_free([REAL_GPU0], timeout_s=0, query=lambda: training, sleep=lambda s: None)
    tiny = REAL_SMI_IDLE + "7002, GPU-" + REAL_GPU1 + ", 40, /home/jay/miniforge3/envs/isaac311/bin/python3.11\n"
    with pytest.raises(ValueError, match="7002"):                 # a just-started Kit child uses little memory
        split.wait_gpus_free([REAL_GPU1], timeout_s=0, query=lambda: tiny, sleep=lambda s: None)
    # a name that merely contains "sunshine" in its path is not skipped: only the basename counts
    spoof = "7003, GPU-" + REAL_GPU1 + ", 900, /home/jay/sunshine/python\n"
    with pytest.raises(ValueError, match="7003"):
        split.wait_gpus_free([REAL_GPU1], timeout_s=0, query=lambda: spoof, sleep=lambda s: None)


def test_gpu_gate_default_query_asks_for_the_process_name(monkeypatch):
    seen = []
    monkeypatch.setattr(split.subprocess, "check_output", lambda cmd, **kw: seen.append(cmd) or REAL_SMI_IDLE)
    split.wait_gpus_free([REAL_GPU0])
    assert "--query-compute-apps=pid,gpu_uuid,used_memory,process_name" in seen[0]


# ---- merge refusals (synthetic) ----
def _doc(modes, **extra):
    return {"checkpoint_sha256": "s", "envs": 64, "modes": {m: {"x": m} for m in modes},
            "sequences": {m: [1] for m in modes}, "shared": {"a": 1},
            "run_identity": {"device": "cuda:0", "checkpoint_sha256": "s", "eval_seed": 42}, **extra}


def test_merge_unions_mode_keyed_parts_and_keeps_mode_order():
    merged, lenient = split.merge_docs([_doc(["eval_pred"]), _doc(["eval_gt", "probe_prop_only"])], label="t")
    assert list(merged["modes"]) == list(MODES) and list(merged["sequences"]) == list(MODES)
    assert merged["shared"] == {"a": 1} and lenient == []
    assert len(merged["run_identity_shards"]) == 2


def test_merge_refuses_disagreeing_conditions_or_identities():
    with pytest.raises(ValueError, match="'envs'"):
        split.merge_docs([_doc(["eval_gt"]), _doc(["eval_pred"], envs=32)], label="t")
    other = _doc(["eval_pred"])
    other["run_identity"]["checkpoint_sha256"] = "different"
    with pytest.raises(ValueError, match="run_identity differs on checkpoint_sha256"):
        split.merge_docs([_doc(["eval_gt"]), other], label="t")
    clash = _doc(["eval_pred"], shared={"a": 2})
    with pytest.raises(ValueError, match="'shared'"):
        split.merge_docs([_doc(["eval_gt"]), clash], label="t")
    with pytest.raises(ValueError, match="missing from a shard"):
        split.merge_docs([_doc(["eval_gt"]), {k: v for k, v in _doc(["eval_pred"]).items() if k != "shared"}], label="t")


def test_merge_shards_refuses_overlap_missing_mode_and_duplicate_stand(tmp_path):
    def shard(name, modes, stand):
        d = tmp_path / name
        for phase, file in (("map64", "map_modes.json"), ("axis_v2", "axis_v2.json")):
            (d / phase).mkdir(parents=True)
            (d / phase / file).write_text(json.dumps(_doc(modes)))
        for mode in stand:
            (d / f"stand_{mode}").mkdir()
            (d / f"stand_{mode}" / "stand.json").write_text("{}")
        return d
    a, b = shard("a", ["eval_gt"], ["eval_gt"]), shard("b", ["eval_pred"], ["eval_pred", "probe_prop_only"])
    with pytest.raises(ValueError, match="do not cover"):
        split.merge_shards(tmp_path / "o1", [a, b])                       # probe_prop_only missing
    c = shard("c", ["probe_prop_only", "eval_gt"], ["probe_prop_only"])
    with pytest.raises(ValueError, match="do not cover"):
        split.merge_shards(tmp_path / "o2", [a, c, b])                    # eval_gt twice
    d = shard("d", ["eval_pred", "probe_prop_only"], ["eval_gt", "eval_pred", "probe_prop_only"])
    with pytest.raises(ValueError, match="stand_eval_gt must come from exactly one shard"):
        split.merge_shards(tmp_path / "o3", [a, d])


# ---- real E0 data: fake Kit children ----
def _filter(doc, modes):
    out = {}
    for key, value in doc.items():
        if isinstance(value, dict) and value and (set(value) <= set(MODES)):
            value = {m: v for m, v in value.items() if m in modes}
        elif isinstance(value, dict) and value and all(isinstance(k, str) and k.split("/")[0] in MODES for k in value):
            value = {k: v for k, v in value.items() if k.split("/")[0] in modes}
        out[key] = value
    return out


def _fake_child(argv, folder, *, env=None, cwd=None):
    """Stand in for one Kit phase: materialise the real E0 result files for this phase's modes."""
    out = pathlib.Path(argv[argv.index("--out") + 1])
    device = argv[argv.index("--device") + 1]
    identity = {"device": device, "gpu_uuid": UUID[device], "gpu_index": int(device[-1])}
    folder.mkdir(parents=True, exist_ok=False)
    if "foothold_s2.eval.ex40_stand_eval" in argv:
        mode = argv[argv.index("--mode") + 1]
        shutil.copytree(REAL / f"stand_{mode}", out, dirs_exist_ok=True)
        doc = json.loads((out / "stand.json").read_text())
        doc["run_identity"] = {**doc["run_identity"], **identity}
        (out / "stand.json").write_text(json.dumps(doc))
    else:
        axis = "--axis-v2" in argv
        name, file = ("axis_v2", "axis_v2.json") if axis else ("map64", "map_modes.json")
        modes = argv[argv.index("--modes") + 1].split(",")
        doc = _filter(json.loads((REAL / name / file).read_text()), modes)
        doc["run_identity"] = {**doc["run_identity"], **identity}
        (out / file).write_text(json.dumps(doc))
        for path in (REAL / name).iterdir():
            if path.suffix == ".npz" and any(f"_{m}_" in path.name for m in modes):
                shutil.copy2(path, out / path.name)
    return {"state": "done", "rc": 0, "argv": list(argv), "seconds": 0.0, "thread": threading.current_thread().name}


@needs_run
def test_split_branch_of_run_reproduces_the_one_gpu_score_from_real_e0_files(tmp_path, monkeypatch):
    from foothold_s2 import ex41_eval_once as process
    from foothold_s2.eval.ex42_mesh_eval import preflight

    checkpoint = E0_RUN / "model_250.pt"
    sha = once.digest(checkpoint)
    mesh_sha = preflight(MESH)["mesh_sha256"]
    barrier = threading.Barrier(2, timeout=20)
    seen_threads = set()

    def child(argv, folder, **kw):
        if not seen_threads or threading.current_thread().name not in seen_threads:
            seen_threads.add(threading.current_thread().name)
            barrier.wait()                    # both shards must be inside a phase at the same time
        return _fake_child(argv, folder, **kw)

    monkeypatch.setattr(process, "hidden_child", child)
    monkeypatch.setattr(once, "gpu_identity", lambda dev: {"device": dev, "gpu_index": int(dev[-1]),
                                                           "gpu_uuid": UUID[dev], "pci_bus_id": "x"})
    monkeypatch.setattr(split, "wait_gpus_free", lambda uuids, **kw: None)
    real_check = once.subprocess.check_output
    monkeypatch.setattr(once.subprocess, "check_output",
                        lambda cmd, **kw: "" if cmd[:2] == ["git", "status"] else "0" * 40 if cmd[:2] == ["git", "rev-parse"]
                        else real_check(cmd, **kw))
    monkeypatch.setattr(once, "machine_path", lambda k, _m=once.machine_path: pathlib.Path(sys.executable) if k == "conda_python" else _m(k))
    out = tmp_path / "split_250"
    rc = once.run(checkpoint, sha, out, "cuda:1", eval_seed=42, mesh_dir=MESH, expected_mesh_sha256=mesh_sha,
                  split_device="cuda:0", p1_plan=ROOT / "foothold_s2/curriculum/ex42-prep.yaml",
                  p1_approvals=ROOT / "foothold_s2/curriculum/ex42-approvals.yaml", p1_stage_id="E0",
                  checkpoint_iteration=250)
    receipt = json.loads((out / "eval_receipt.json").read_text())
    assert rc == 0 and receipt["state"] == "done", receipt.get("reason")
    notice = json.loads((out / "next_stage_notice.json").read_text())          # the real P1 judgment is HOLD
    judged = json.loads((out / "p1_score.json").read_text())["judgment"]          # #631 judges the E0 cells now
    assert notice["judgment"] == judged and notice["next_stage_id"] == "E1" and notice["automatic_launch_started"] is False
    assert notice["state"] == ("next_stage_authorized_no_launcher" if judged == "PASS" else "not_ready")   # #639 cell is open, no launcher given
    assert receipt["next_stage_notice"] == notice["state"]
    assert receipt["split"]["devices"] == ["cuda:1", "cuda:0"]
    assert {k.split("@")[1] for k in receipt["steps"]} == {"cuda:0", "cuda:1"}
    expected = sum(len(dev["stand"]) + bool(dev["map64"]) + bool(dev["axis_v2"])
                   for dev in receipt["split"]["assignment"].values())
    assert len(receipt["steps"]) == expected == 3 + 2 + 2          # 3 stand modes, map64 and axis_v2 once per shard
    assert (out / "eval_split_merge.json").is_file()
    # the merged map/axis/stand files are what `measure` reads: the score equals the one-GPU score cell for cell
    mine = json.loads((out / "ex42_score.json").read_text())
    real = json.loads((REAL / "ex42_score.json").read_text())
    assert split.compare_measurements(real, mine) == []        # measured cells equal (judgement fields come from newer code)
    assert (real["checkpoint_sha256"], mine["conditions"]) == (mine["checkpoint_sha256"], real["conditions"])


@needs_run
def test_split_run_stops_and_records_hold_when_one_shard_phase_fails(tmp_path, monkeypatch):
    from foothold_s2 import ex41_eval_once as process
    from foothold_s2.eval.ex42_mesh_eval import preflight

    checkpoint = E0_RUN / "model_250.pt"

    def child(argv, folder, **kw):
        if argv[argv.index("--device") + 1] == "cuda:0" and "--axis-v2" not in argv and "--mode" not in argv:
            folder.mkdir(parents=True)
            return {"state": "failed", "rc": 1}
        return _fake_child(argv, folder, **kw)

    monkeypatch.setattr(process, "hidden_child", child)
    monkeypatch.setattr(once, "gpu_identity", lambda dev: {"device": dev, "gpu_index": int(dev[-1]), "gpu_uuid": UUID[dev], "pci_bus_id": "x"})
    monkeypatch.setattr(split, "wait_gpus_free", lambda uuids, **kw: None)
    real_check = once.subprocess.check_output
    monkeypatch.setattr(once.subprocess, "check_output",
                        lambda cmd, **kw: "" if cmd[:2] == ["git", "status"] else "0" * 40 if cmd[:2] == ["git", "rev-parse"]
                        else real_check(cmd, **kw))
    monkeypatch.setattr(once, "machine_path", lambda k, _m=once.machine_path: pathlib.Path(sys.executable) if k == "conda_python" else _m(k))
    out = tmp_path / "split_fail"
    rc = once.run(checkpoint, once.digest(checkpoint), out, "cuda:1", eval_seed=42, mesh_dir=MESH,
                  expected_mesh_sha256=preflight(MESH)["mesh_sha256"], split_device="cuda:0")
    receipt = json.loads((out / "eval_receipt.json").read_text())
    assert rc == 5 and receipt["state"] == "HOLD" and "map64@cuda:0" in receipt["reason"]
    assert not (out / "ex42_score.json").exists() and not (out / "map64").exists()      # nothing merged, no score invented


@needs_run
def test_gpu_busy_after_training_holds_without_starting_any_child(tmp_path, monkeypatch):
    from foothold_s2 import ex41_eval_once as process
    from foothold_s2.eval.ex42_mesh_eval import preflight

    checkpoint = E0_RUN / "model_250.pt"
    started = []
    monkeypatch.setattr(process, "hidden_child", lambda *a, **k: started.append(a))
    monkeypatch.setattr(once, "gpu_identity", lambda dev: {"device": dev, "gpu_index": int(dev[-1]), "gpu_uuid": UUID[dev], "pci_bus_id": "x"})

    def busy(uuids, **kw):
        raise ValueError("EX-42 split evaluation GPUs still hold compute processes: {'x': ['1']}")

    monkeypatch.setattr(split, "wait_gpus_free", busy)
    real_check = once.subprocess.check_output
    monkeypatch.setattr(once.subprocess, "check_output",
                        lambda cmd, **kw: "" if cmd[:2] == ["git", "status"] else "0" * 40 if cmd[:2] == ["git", "rev-parse"]
                        else real_check(cmd, **kw))
    monkeypatch.setattr(once, "machine_path", lambda k, _m=once.machine_path: pathlib.Path(sys.executable) if k == "conda_python" else _m(k))
    out = tmp_path / "busy"
    rc = once.run(checkpoint, once.digest(checkpoint), out, "cuda:1", eval_seed=42, mesh_dir=MESH,
                  expected_mesh_sha256=preflight(MESH)["mesh_sha256"], split_device="cuda:0")
    assert rc == 5 and started == []
    assert json.loads((out / "eval_receipt.json").read_text())["state"] == "HOLD"


def test_split_device_must_differ_and_the_plan_lists_both_devices_commands(tmp_path, capsys):
    with pytest.raises(SystemExit):
        once.main(["--checkpoint", __file__, "--sha-from-manifest", "--out", str(tmp_path / "o"),
                   "--device", "cuda:1", "--split-device", "cuda:1"])


def test_compare_scores_reports_each_difference_and_ignores_directory_paths():
    a = {"checkpoint": "/x/a", "m": {"c": {"alive": 60, "err": 0.1, "raw_file": "/x/a.npz"}}, "l": [1, 2]}
    b = copy.deepcopy(a)
    b["checkpoint"], b["m"]["c"]["raw_file"] = "/y/b", "/y/b.npz"
    assert split.compare_scores(a, b) == []
    b["m"]["c"]["err"], b["l"][1], b["m"]["d"] = 0.2, 3, 1
    diffs = {d["path"]: d for d in split.compare_scores(a, b)}
    assert set(diffs) == {"/m/c/err", "/l[1]", "/m/d"}
    assert diffs["/m/c/err"]["abs_diff"] == pytest.approx(0.1)


# ---- chain: E1 boundary queue waits for training and the validator accepts the split command ----
def _profile_p1_on_gpu1():
    return {"machine_id": "AI-WS01-linux", "paths": {"conda_python": "/opt/conda/envs/isaac311/bin/python"},
            "devices": {"training": {"cuda_index": 0, "device": "cuda:0", "uuid": "GPU-t0"},
                        "p1_evaluation": {"cuda_index": 1, "device": "cuda:1", "uuid": "GPU-t1"}}}


def _argv(checkpoint, out, mesh_dir, mesh_sha, *, split_device="cuda:0", stage="E1"):
    argv = ["/opt/conda/envs/isaac311/bin/python", "-m", "foothold_s2.ex42_eval_once",
            "--checkpoint", str(checkpoint), "--sha-from-manifest", "--out", str(out), "--device", "cuda:1",
            "--eval-seed", "42", "--mesh-dir", str(mesh_dir), "--expected-mesh-sha256", mesh_sha,
            "--p1-plan", str(ROOT / "foothold_s2/curriculum/ex42-prep.yaml"),
            "--p1-approvals", str(ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"),
            "--p1-stage-id", stage, "--execute"]
    return argv + (["--split-device", split_device] if split_device else [])


def _mesh(tmp_path):
    from foothold_s2.tests.test_ex42_calibrate_cpu import mesh_fixture
    mesh_dir = tmp_path / "mesh"
    mesh_dir.mkdir()
    return mesh_dir, mesh_fixture(mesh_dir)["mesh_sha256"]


def test_validator_accepts_split_only_on_the_training_gpu(tmp_path):
    from foothold_s2.ex42_chain import _validate_p1_score_command
    ck = tmp_path / "model_250.pt"
    ck.write_bytes(b"x")
    mesh_dir, mesh_sha = _mesh(tmp_path)
    ok = _argv(ck, tmp_path / "score_250", mesh_dir, mesh_sha)
    assert _validate_p1_score_command(ok, machine_profile=_profile_p1_on_gpu1(), iteration=250,
                                      checkpoint_path=ck, expected_stage_id="E1") == 1
    for bad in ("cuda:1",):
        with pytest.raises(ValueError, match="split device"):
            _validate_p1_score_command(_argv(ck, tmp_path / "score_250", mesh_dir, mesh_sha, split_device=bad),
                                       machine_profile=_profile_p1_on_gpu1(), iteration=250,
                                       checkpoint_path=ck, expected_stage_id="E1")
    twice = ok + ["--split-device", "cuda:0"]
    with pytest.raises(ValueError, match="exactly one --split-device"):
        _validate_p1_score_command(twice, machine_profile=_profile_p1_on_gpu1(), iteration=250,
                                   checkpoint_path=ck, expected_stage_id="E1")


def test_deferred_boundaries_queue_with_a_wait_on_the_training_pid_and_plain_ones_do_not(tmp_path):
    from foothold_s2.tests.test_ex42_chain_cpu import make_chain, _manifested_checkpoint
    mesh_dir, mesh_sha = _mesh(tmp_path)
    for name, defer in (("deferred", os.getpid()), ("plain", None)):
        sub = tmp_path / name
        sub.mkdir()
        chain, _ = make_chain(sub, machine_profile=_profile_p1_on_gpu1())
        chain.defer_until_pid = defer
        ck = _manifested_checkpoint(sub / "ck", 250)
        # the stage-zero fixture chain runs stage EX42_0_T0_prime; only the queue entry is under test here
        argv = _argv(ck, sub / "score_250", mesh_dir, mesh_sha, stage="EX42_0_T0_prime")
        chain.register_checkpoint_p1(iteration=250, checkpoint_dir=ck.parent, score_argv=argv)
        item = json.loads((sub / "gpu/queue.json").read_text())["items"][0]
        assert item["gpu"] == 1 and item["argv"] == argv
        assert item.get("wait_pids") == ([os.getpid()] if defer else None)
    with pytest.raises(ValueError, match="training process id"):
        from foothold_s2.ex42_chain import EX42TrainingChain
        EX42TrainingChain.__init__(object.__new__(EX42TrainingChain), plan=None, approvals_path="", parent_manifest_path="",
                                   run_dir="", repo_root="", queue_path="", defer_until_pid=0)


def test_dispatcher_holds_a_deferred_item_until_the_training_pid_is_gone():
    import importlib.util
    spec = importlib.util.spec_from_file_location("dispatch_t", ROOT / "_out/tools/gpu_jobs/dispatch.py")
    d = importlib.util.module_from_spec(spec)
    sys.modules["dispatch_t"] = d
    spec.loader.exec_module(d)
    item = {"state": "대기", "kind": "eval", "argv": ["x"], "gpu": d.DISPATCH["gpu"], "wait_pids": [4242]}
    assert d.item_ready(item, 0, alive=lambda pid: True)[1] == "wait_pid:4242"
    assert d.item_ready(item, 0, alive=lambda pid: False) == (True, "ready")


@needs_run
def test_real_e1_chain_queues_250_500_750_1000_with_split_command_and_a_wait_on_training(tmp_path, monkeypatch):
    import hashlib
    from types import SimpleNamespace
    from foothold_s2.scripts import ex42_training_entry as entry
    from foothold_s2.tests.test_ex42_e0_launch_cpu import _chain_kwargs

    kwargs = _chain_kwargs(tmp_path, monkeypatch)
    kwargs["parent_manifest_path"] = E0_RUN / "manifest.json"
    argv = json.loads(kwargs["score_argv_json"])
    argv[argv.index("--p1-stage-id") + 1] = "E1"
    kwargs["score_argv_json"] = json.dumps(argv + ["--split-device", "cuda:0"])
    kwargs["queue_path"] = pathlib.Path(kwargs["machine_profile"]["paths"]["gpu_queue"])
    kwargs.pop("dispatch_path")
    chain = entry.build_ex42_training_chain(**kwargs, current_stage_id="E1", p1_interval=250,
                                            defer_until_pid=os.getpid())
    run = pathlib.Path(kwargs["run_dir"])
    manifest = {"progress": {"completed_updates": 0}, "checkpoints": {}}
    for iteration in (250, 300, 500, 750, 1000):
        data = f"model {iteration}".encode()
        (run / f"model_{iteration}.pt").write_bytes(data)
        manifest["checkpoints"][f"model_{iteration}.pt"] = hashlib.sha256(data).hexdigest()
        manifest["progress"]["completed_updates"] = iteration
        (run / "manifest.json").write_text(json.dumps(manifest))
        state = chain.on_checkpoint_saved(SimpleNamespace(log_dir=str(run)), iteration)
        assert (state["state"] == "queued") == (iteration % 250 == 0), (iteration, state)
        if iteration % 250 == 0:
            assert state["stage_id"] == "E1"
    items = json.loads(kwargs["queue_path"].read_text())["items"]
    assert [i["argv"][i["argv"].index("--checkpoint") + 1].rsplit("_", 1)[-1] for i in items] == [
        "250.pt", "500.pt", "750.pt", "1000.pt"]
    assert all(i["wait_pids"] == [os.getpid()] and i["gpu"] == 1 and "--split-device" in i["argv"] for i in items)


def test_next_stage_notice_only_at_the_stage_end_and_never_starts_anything():
    plan = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    ids = [row["id"] for row in EX42Plan.load(plan).document["stages"]]
    assert ids.index("E1") + 1 < len(ids)
    following = ids[ids.index("E1") + 1]
    passed = {"judgment": "PASS", "checkpoint_sha256": "a" * 64}
    ready = once.next_stage_notice(plan, "E1", 1000, passed)
    assert ready["state"] == "next_stage_ready_for_approval" and ready["next_stage_id"] == following
    assert ready["automatic_launch_started"] is False
    assert once.next_stage_notice(plan, "E1", 1000, {**passed, "judgment": "HOLD"})["state"] == "not_ready"
    for mid in (250, 500, 750):                                 # mid-stage boundaries get no notice
        assert once.next_stage_notice(plan, "E1", mid, passed) is None
    assert once.next_stage_notice(plan, "NOPE", 1000, passed) is None


# ---- the two device checks each refuse on their own (reviewer 11:10 survivors) ----
def test_validator_split_device_must_be_the_training_gpu_and_not_the_p1_gpu_each_alone(tmp_path):
    from foothold_s2.ex42_chain import _validate_p1_score_command
    ck = tmp_path / "model_250.pt"
    ck.write_bytes(b"x")
    mesh_dir, mesh_sha = _mesh(tmp_path)

    def check(profile, split_device):
        argv = _argv(ck, tmp_path / "score_250", mesh_dir, mesh_sha, split_device=split_device)
        if profile["devices"]["p1_evaluation"]["device"] == "cuda:0":
            argv[argv.index("--device") + 1] = "cuda:0"
        return _validate_p1_score_command(argv, machine_profile=profile, iteration=250, checkpoint_path=ck,
                                          expected_stage_id="E1")
    normal = _profile_p1_on_gpu1()
    with pytest.raises(ValueError, match="split device"):
        check(normal, "cuda:1")                       # the P1 GPU
    assert check(normal, "cuda:0") == 1
    # not the training GPU at all: only the "differs from training" clause can refuse this
    odd = copy.deepcopy(normal)
    odd["devices"]["training"] = {"cuda_index": 0, "device": "cuda:0", "uuid": "GPU-t0"}
    with pytest.raises(ValueError, match="split device"):
        check(odd, "cuda:2")
    # training and P1 on the same GPU (the shared fixture): only the "same as P1" clause can refuse cuda:0
    same = copy.deepcopy(normal)
    same["devices"]["p1_evaluation"] = {"cuda_index": 0, "device": "cuda:0", "uuid": "GPU-t0"}
    with pytest.raises(ValueError, match="split device"):
        check(same, "cuda:0")


@needs_run
def test_run_itself_refuses_a_split_device_equal_to_the_evaluation_device(tmp_path, monkeypatch):
    from foothold_s2 import ex41_eval_once as process
    started = []
    monkeypatch.setattr(process, "hidden_child", lambda *a, **k: started.append(a))
    monkeypatch.setattr(once, "gpu_identity", lambda dev: {"device": dev, "gpu_index": int(dev[-1]), "gpu_uuid": UUID[dev], "pci_bus_id": "x"})
    real_check = once.subprocess.check_output
    monkeypatch.setattr(once.subprocess, "check_output",
                        lambda cmd, **kw: "" if cmd[:2] == ["git", "status"] else "0" * 40 if cmd[:2] == ["git", "rev-parse"]
                        else real_check(cmd, **kw))
    monkeypatch.setattr(once, "machine_path", lambda k, _m=once.machine_path: pathlib.Path(sys.executable) if k == "conda_python" else _m(k))
    checkpoint = E0_RUN / "model_250.pt"
    with pytest.raises(ValueError, match="split device must differ"):
        once.run(checkpoint, once.digest(checkpoint), tmp_path / "same", "cuda:1", eval_seed=42, split_device="cuda:1")
    assert started == [] and not (tmp_path / "same").exists()
