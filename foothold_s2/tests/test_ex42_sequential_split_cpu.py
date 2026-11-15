"""EX-42 boundary evaluation: D44, the e1_v2 low-speed levels and the widened E1 cells run on two GPUs. CPU only.

The Kit children are replaced by a fake that copies the folder a child would write from the REAL v28 m250
one-GPU evaluation (11/14 15:43). So the commands, the lane assignment, the isolation and the folders the readers
get are checked on real result files; whether Kit gives the same numbers on the second GPU is the lead's Kit check.
"""
from __future__ import annotations

import inspect
import json
import pathlib
import shutil
import threading

import pytest

from foothold_s2 import ex42_eval_once as once
from foothold_s2 import ex42_eval_split as split

ROOT = pathlib.Path(__file__).resolve().parents[2]
REAL_RUN = pathlib.Path("/home/jay/data/foothold/s2_lab/ex42_main_20261114_131028/main/EX-42-B-E1-v28_20261114_131028")
REAL = REAL_RUN / "eval" / "scores" / "m250"
EVAL_PLAN = pathlib.Path("/home/jay/mai/tmp/lead/E1_v28_20261114_131028/eval_policy/ex42-prep.yaml")
needs_real = pytest.mark.skipif(not (REAL / "eval_receipt.json").is_file() or not EVAL_PLAN.is_file(),
                                reason="the v28 m250 one-GPU evaluation or its evaluation plan is not on this machine")
NAMES = ["d44", "e1_v2_L0", "e1_v2_L5", "wide_L3", "wide_L6", "wide_L9", "wide_endpoints"]
SERIAL_SECONDS = 118 + 196 + 196 + 208 + 208 + 211 + 261      # the v28 m250 child.json seconds, one GPU


# ---- assignment ----
def test_assignment_puts_every_unit_on_exactly_one_device_and_balances_the_lanes():
    lanes, load = split.assign_units(NAMES, ["cuda:1", "cuda:0"])
    assert sorted(n for lane in lanes.values() for n in lane) == sorted(NAMES)
    assert set(lanes) == {"cuda:1", "cuda:0"} and all(lanes.values())
    assert sum(load.values()) == pytest.approx(sum(split.sequential_unit_seconds(n) for n in NAMES))
    assert max(load.values()) - min(load.values()) <= max(split.sequential_unit_seconds(n) for n in NAMES)
    assert max(load.values()) < 0.6 * sum(load.values())            # one GPU no longer carries the whole chain
    assert split.assign_units(NAMES, ["cuda:1", "cuda:0"]) == (lanes, load)        # deterministic


def test_estimates_are_the_v28_m250_receipt_seconds_and_one_gpu_is_the_unchanged_chain():
    assert abs(SERIAL_SECONDS - 1398) == 0
    lanes, load = split.assign_units(NAMES, ["cuda:1"])
    assert list(lanes) == ["cuda:1"] and sorted(lanes["cuda:1"]) == sorted(NAMES) and load["cuda:1"] == pytest.approx(SERIAL_SECONDS, abs=5)   # constants round wide_L9 211 to 208
    lanes, load = split.assign_units(NAMES, ["cuda:1", "cuda:0"])
    assert max(load.values()) <= 0.55 * SERIAL_SECONDS            # about 12 min instead of 23 min of waiting


@pytest.mark.parametrize("names, devices", [(["d44", "d44"], ["cuda:0", "cuda:1"]), (["d44"], ["cuda:0", "cuda:0"]),
                                            (["d44"], []), (["mystery"], ["cuda:0", "cuda:1"])])
def test_assignment_refuses_duplicates_unknown_units_and_bad_devices(names, devices):
    with pytest.raises(ValueError):
        split.assign_units(names, devices)


# ---- running the lanes ----
class FakeProcess:
    def __init__(self, fail=(), barrier=None, write=None):
        self.fail, self.barrier, self.write, self.prepared, self.calls = set(fail), barrier, write, [], []
        self.lock = threading.Lock()

    def prepare_phase_output(self, argv):
        out = pathlib.Path(argv[argv.index("--out") + 1])
        out.mkdir(parents=True, exist_ok=False)
        self.prepared.append(out)

    def hidden_child(self, argv, folder, *, env=None, cwd=None):
        folder.mkdir(parents=True, exist_ok=False)
        name = folder.name
        if self.barrier is not None:
            self.barrier.wait()
        with self.lock:
            self.calls.append((name, argv[argv.index("--device") + 1], env["TMPDIR"], folder))
        if name in self.fail:
            return {"state": "failed", "rc": 1}
        if self.write is not None:
            self.write(argv)
        return {"state": "done", "rc": 0, "argv": list(argv)}


def _build(name, device):
    cache = "--kit_args=--/UJITSO/datastore/localCachePath=/shared/cache"
    return ["python", "-m", "x", "--out", f"OUT/{name}", "--device", device, cache], True


def _lanes(tmp_path):
    lanes, _ = split.assign_units(NAMES, ["cuda:1", "cuda:0"])
    return lanes


def _build_in(tmp_path):
    def build(name, device):
        argv, prepare = _build(name, device)
        argv[argv.index("--out") + 1] = str(tmp_path / "out" / name)
        return argv, prepare
    return build


def test_both_lanes_run_at_the_same_time_with_their_own_kit_paths_and_a_stagger(tmp_path):
    slept = []
    process = FakeProcess(barrier=threading.Barrier(2, timeout=20))
    # each lane has several units, so the barrier is crossed once per unit pair; use a single pair of units
    lanes = {"cuda:1": ["d44"], "cuda:0": ["wide_L3"]}
    children = split.run_units(lanes, build=_build_in(tmp_path), output=tmp_path, env={"A": "1"}, process=process,
                               sleep=slept.append)
    assert slept == [30] and set(children) == {"d44", "wide_L3"}
    assert {c["lane_device"] for c in children.values()} == {"cuda:1", "cuda:0"}
    tmps = {name: tmp for name, _, tmp, _ in process.calls}
    assert len(set(tmps.values())) == 2 and all("kit_runtime" in t for t in tmps.values())
    for name, device, _, _ in process.calls:                       # the Kit cache argument moved under the unit's folder
        argv = children[name]["argv"]
        assert any(a == "--kit_args=--/UJITSO/datastore/localCachePath=" + children[name]["isolated_runtime"]["kit_cache"]
                   for a in argv)
        assert (tmp_path / "kit_runtime" / device.replace(":", "_") / name / "cache").is_dir()
    assert (tmp_path / "children" / "d44").is_dir() and (tmp_path / "children" / "wide_L3").is_dir()


def test_a_failed_or_broken_unit_never_stops_the_other_units_and_is_never_reported_done(tmp_path):
    process = FakeProcess(fail={"e1_v2_L0"})
    lanes = _lanes(tmp_path)
    base = _build_in(tmp_path)

    def build(name, device):
        if name == "wide_L6":
            raise ValueError("no such command")
        return base(name, device)

    children = split.run_units(lanes, build=build, output=tmp_path, env={}, process=process, sleep=lambda s: None)
    assert set(children) == set(NAMES)
    assert children["e1_v2_L0"]["state"] == "failed"
    assert children["wide_L6"]["state"] == "HOLD" and "no such command" in children["wide_L6"]["reason"]
    assert sum(c["state"] == "done" for c in children.values()) == len(NAMES) - 2


def test_two_units_never_share_an_output_folder_so_nothing_is_overwritten(tmp_path):
    process = FakeProcess()
    split.run_units(_lanes(tmp_path), build=_build_in(tmp_path), output=tmp_path, env={}, process=process,
                    sleep=lambda s: None)
    assert len(process.prepared) == len(set(process.prepared)) == len(NAMES)


# ---- the pool against the real v28 m250 evaluation ----
def _copy_from_real(output):
    def write(argv):
        out = pathlib.Path(argv[argv.index("--out") + 1])
        src = REAL / out.relative_to(output)
        shutil.copytree(src, out, dirs_exist_ok=True)
    return write


def _tree(path):
    return {p.relative_to(path).as_posix(): (p.stat().st_size, __import__("hashlib").sha256(p.read_bytes()).hexdigest())
            for p in sorted(pathlib.Path(path).rglob("*")) if p.is_file()}


@needs_real
def test_pool_runs_the_real_unit_commands_and_writes_the_same_leaves_the_readers_read(tmp_path, monkeypatch):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_e1_v2 import measure_cells
    from foothold_s2.ex42_e1_wide import read_cells

    receipt = json.loads((REAL / "eval_receipt.json").read_text())
    sha, seed, mesh_sha = receipt["checkpoint_sha256"], receipt["eval_seed"], receipt["ex42_mesh"]["mesh_sha256"]
    policy = EX42Plan.load(EVAL_PLAN)
    out = tmp_path / "split_250"
    out.mkdir()
    for part in REAL.iterdir():                   # shard folders and receipts come from the unchanged shard stage
        if part.name not in ("d44", "e1_v2", "wide", "children") and part.is_dir():
            shutil.copytree(part, out / part.name)
    # the D44 replica needs the real tile mesh; its command shape is checked separately, so give it a plain builder
    monkeypatch.setattr(once, "d44_argv_builder", lambda checkpoint, output, **kw: (
        lambda device: once.d44_kit_command(checkpoint, output, device, task="t", plan_path=EVAL_PLAN,
                                            mesh_dir=out / "m", replica_dir=out / "d44_mesh",
                                            replica_sha256="0" * 64, seed=seed)))
    cfg = {"task": receipt.get("task") or "Isaac-Velocity-Rough-Unitree-Go2-v0"}
    process = FakeProcess(write=_copy_from_real(out))
    pool = once.run_sequential_pool(
        pathlib.Path("/x/model_250.pt"), out, ["cuda:1", "cuda:0"], cfg, seed=seed, mesh_dir=pathlib.Path("/x/mesh"),
        policy=policy, policy_path=EVAL_PLAN, p1_stage_id="E1", evaluation_plan=EVAL_PLAN, retained=("d44",),
        process=process, env={}, record=lambda name, child: None)
    assert pool is not None and pool.errors == {} and set(pool.children) == set(NAMES)
    assert all(c["state"] == "done" for c in pool.children.values())
    # both GPUs worked, and each unit asked for exactly the device its lane runs on
    devices = {c["lane_device"] for c in pool.children.values()}
    assert devices == {"cuda:1", "cuda:0"}
    for child in pool.children.values():
        assert child["argv"][child["argv"].index("--device") + 1] == child["lane_device"]
    # same leaves: the folders the readers use are byte for byte the one-GPU folders
    for sub in ("d44", "e1_v2", "wide"):
        assert _tree(out / sub) == _tree(REAL / sub), sub
    def leaves(value, root):                      # compare values, not the folder the files were read from
        return json.loads(json.dumps(value, default=str).replace(str(root), "ROOT"))

    assert leaves(measure_cells(out, sha, seed), out) == leaves(measure_cells(REAL, sha, seed), REAL)
    assert leaves(read_cells(out, sha, seed, policy.document, mesh_sha), out) == \
        leaves(read_cells(REAL, sha, seed, policy.document, mesh_sha), REAL)


@needs_real
def test_pool_commands_equal_the_one_device_commands_for_the_device_each_unit_runs_on(tmp_path):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_e1_wide import kit_commands

    policy = EX42Plan.load(EVAL_PLAN)
    receipt = json.loads((REAL / "eval_receipt.json").read_text())
    seed, cfg = receipt["eval_seed"], {"task": "T"}
    out = tmp_path / "o"
    out.mkdir()
    seen = {}

    class Spy(FakeProcess):
        def hidden_child(self, argv, folder, *, env=None, cwd=None):
            seen[folder.name] = argv
            return super().hidden_child(argv, folder, env=env, cwd=cwd)

    pool = once.run_sequential_pool(
        pathlib.Path("/x/model_250.pt"), out, ["cuda:1", "cuda:0"], cfg, seed=seed, mesh_dir=pathlib.Path("/x/mesh"),
        policy=policy, policy_path=EVAL_PLAN, p1_stage_id="E1", evaluation_plan=EVAL_PLAN, retained=(),
        process=Spy(), env={}, record=lambda name, child: None)
    assert set(seen) == {n for n in NAMES if n != "d44"}
    for name, argv in seen.items():
        device = pool.children[name]["lane_device"]
        wanted = (dict(once.e1_v2_commands(pathlib.Path("/x/model_250.pt"), out, device, cfg, eval_seed=seed,
                                           mesh_dir=pathlib.Path("/x/mesh"), evaluation_plan=EVAL_PLAN))
                  if name.startswith("e1_v2") else
                  dict(kit_commands(pathlib.Path("/x/model_250.pt"), out, device, task="T", plan_path=EVAL_PLAN,
                                    plan=policy.document, mesh_dir=pathlib.Path("/x/mesh"), seed=seed)))[name]
        cache = "--kit_args=--/UJITSO/datastore/localCachePath="
        strip = lambda a: [x if not x.startswith(cache) else cache for x in a]
        assert strip(argv) == strip(wanted), name


@needs_real
def test_a_group_that_cannot_be_built_is_raised_where_the_one_device_code_raised_it(tmp_path):
    from foothold_s2.curriculum.ex42_prep import EX42Plan

    policy = EX42Plan.load(EVAL_PLAN)
    out = tmp_path / "o"
    out.mkdir()
    pool = once.run_sequential_pool(
        pathlib.Path("/x/model_250.pt"), out, ["cuda:1", "cuda:0"], {"task": "T"}, seed=42, mesh_dir=None,
        policy=policy, policy_path=EVAL_PLAN, p1_stage_id="E1", evaluation_plan=EVAL_PLAN, retained=(),
        process=FakeProcess(), env={}, record=lambda name, child: None)
    assert set(pool.errors) == {"e1_v2", "wide"} and pool.children == {}      # mesh_dir None: both groups refuse
    with pytest.raises(ValueError, match="pinned"):
        pool.take("e1_v2", "e1_v2_L0")
    with pytest.raises(ValueError, match="pinned"):
        pool.take("wide", "wide_L3")


def test_no_applicable_phase_means_no_pool():
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    policy = EX42Plan.load(ROOT / "foothold_s2/curriculum/ex42-prep.yaml")
    assert once.run_sequential_pool(pathlib.Path("/x/m.pt"), pathlib.Path("/x/o"), ["cuda:1", "cuda:0"], {"task": "T"},
                                    seed=42, mesh_dir=pathlib.Path("/x/mesh"), policy=policy,
                                    policy_path=ROOT / "foothold_s2/curriculum/ex42-prep.yaml", p1_stage_id="E0",
                                    evaluation_plan=None, retained=(), process=FakeProcess(), env={},
                                    record=lambda n, c: None) is None


# ---- wiring of run() ----
def test_run_uses_the_pool_only_with_a_split_device_and_checks_each_childs_own_gpu():
    source = inspect.getsource(once.run)
    assert "if split_device is not None and policy_path is not None:" in source
    for call in ('pool.take("d44", "d44")', 'pool.take("e1_v2", phase)', 'pool.take("wide", phase)'):
        assert call in source
    assert source.count('child.get("lane_device", device)') == 3 and "physical_by_device[lane]" in source
    # the one-device path is the old sequential code
    assert source.count("process.hidden_child(") >= 4 and "process.prepare_phase_output(argv)" in source


def test_a_lane_that_dies_on_an_unexpected_error_is_not_reported_as_complete(tmp_path):
    class Dies(FakeProcess):
        def hidden_child(self, argv, folder, *, env=None, cwd=None):
            raise RuntimeError("thread died")

    with pytest.raises(ValueError, match="did not all report"):
        split.run_units({"cuda:1": ["d44"], "cuda:0": ["wide_L3"]}, build=_build_in(tmp_path), output=tmp_path,
                        env={}, process=Dies(), sleep=lambda s: None)
