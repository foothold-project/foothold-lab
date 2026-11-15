"""CPU known-answer and targeted mutation tests; no Kit import or launch."""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from s2_eval_cases import CaseError, seal, verify, digest, canonical
from s2_eval_driver import (EvalHold, run, run_case, run_from_files, validate_job, load_policies,
                            PARENT_E1_SHA256, AGENT_YAML_SHA256)
from s2_eval_post import aggregate, aggregate_from_files
from s2_packet_17v import AtomicPacket, raw_sha
from s2_env_adapter_17v import expected_world_xy
from s2_policy import build_s2, load_parent_cpu
from test_s2_step11_eval import saved_runner


PASS = []
CAUGHT = []


def ok(label, condition):
    assert condition, label
    PASS.append(label)


def caught(label, want, fn):
    try:
        fn()
    except Exception as ex:
        got = str(ex)
        assert want in got, f"{label}: first_FAIL={got!r}, want={want!r}"
        CAUGHT.append({"name": label, "first_FAIL": got, "want": want})
    else:
        raise AssertionError(label + ": mutation survived")


def fixture_cases():
    x = seal(phase="full", counts={"gap": 1, "stepping_stones": 1, "flat": 1, "stairs_up": 1},
             eval_seeds=[1000, 1001, 1002, 1003], learning_seeds=[7, 11, 42],
             command="fwd03", difficulty=.5, friction=1.,
             terrain_source="1043-pinned-test-source", terrain_source_sha256="a" * 64,
             geometry_sha256="b" * 64)
    # Short CPU trajectory only; the actual generated CLI contract retains 20 s.
    for case in x["cases"]:
        case["command"] = {**case["command"], "duration_s": .04}
    x["cases_sha256"] = digest({k: v for k, v in x.items() if k != "cases_sha256"})
    return x


class MeanPolicy:
    def eval(self):
        return self

    def act(self, obs):
        raise AssertionError("stochastic act called")

    def act_inference(self, obs):
        assert set(obs) == {"policy", "single_obs", "critic", "map"}
        assert obs["map"].shape == (1, 374)
        return torch.zeros(1, 12)


class FakeAdapter:
    def __init__(self, case, mode, *, mesh="c" * 64, stale=False):
        self.case, self.mode, self.mesh, self.stale = case, mode, mesh, stale
        self.num = 0
        self.obs = {k: torch.zeros(1, w) for k, w in
                    (("policy", 450), ("single_obs", 45), ("critic", 275))}
        self.pos = torch.tensor([[0., 0., .5]])
        cfg = SimpleNamespace(ray_alignment="yaw", offset=SimpleNamespace(pos=(0., 0., 20.)),
            pattern_cfg=SimpleNamespace(ordering="xy", size=(1.6, 1.0), resolution=.1,
                                        direction=(0., 0., -1.)))
        xy = expected_world_xy(self.pos, torch.zeros(1))
        hits = torch.cat((xy, torch.zeros(1, 187, 1)), dim=-1)
        self.sensor = SimpleNamespace(cfg=cfg, data=SimpleNamespace(pos_w=self.pos, ray_hits_w=hits))
        self.receipt = None

    def reset(self, case):
        assert case == self.case
        return self.obs

    def reset_receipt(self):
        return {"case_id": self.case["case_id"], "eval_seed": self.case["eval_seed"],
                "initial_state_sha256": "d" * 64, "episode_id": 0,
                "previous_sensor_generation": 0, "post_reset_sensor_refresh": True}

    def case_fingerprint(self):
        return {"mesh_sha256": self.mesh, "initial_state_sha256": "d" * 64,
            "command_sha256": hashlib.sha256(canonical(self.case["command"])).hexdigest(),
            "friction": self.case["friction"], "terrain_seed": self.case["terrain_seed"],
            "eval_seed": self.case["eval_seed"], "policy_dt": self.case["policy_dt"],
            "physics_dt": self.case["physics_dt"], "origin_x": 0., "zone_end_x": 1.}

    def initial_physical_state(self):
        return dict(pos=[0., 0., .5], yaw=0., vb=[0., 0., 0.], wb=[0., 0., 0.],
                    grav_z=-1., hag=.5, term=False)

    def capture_packet_after_sensor_update(self):
        generation = 1 if self.stale else self.num + 1
        step = generation
        h = raw_sha(self.pos, self.sensor.data.ray_hits_w)
        self.receipt = {"generation": generation, "step": step, "raw_sha256": h,
            "generation_by_env": [generation], "sensor_timestamp_by_env": [float(step)],
            "hook_source_sha256": "f" * 64}
        return AtomicPacket(self.obs, self.sensor, self.pos.clone(),
                            torch.tensor([[1., 0., 0., 0.]]), torch.tensor([0]),
                            step, step, generation, h, f"{step}:{generation}:{h}",
                            self.receipt, (0., 0., 0.))

    def read_sensor_source_receipt(self):
        return self.receipt

    def step_recorded(self, action):
        self.num += 1
        return self.obs, self.num == 2, dict(pos=[0.1 * self.num, 0., .5],
            yaw=0., vb=[0., 0., 0.], wb=[0., 0., 0.], grav_z=-1., hag=.5,
            term=self.num == 2)

    def close(self):
        pass


def job(cases):
    parent_root = Path("C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192")
    return {"schema": "s2-eval-job-v1", "inference": "act_inference", "phase": cases["phase"], "update": 0,
        "cases_sha256": cases["cases_sha256"],
        "parent": {"path": str(parent_root / "model_20000.pt"), "sha256": PARENT_E1_SHA256},
        "agent_yaml": {"path": str(parent_root / "params/agent.yaml"), "sha256": AGENT_YAML_SHA256},
        "arms": {m: {"checkpoint": m, "checkpoint_sha256": "0" * 64,
                    "env_config_sha256": "e" * 64, "map_init_seed": 0} for m in ("A", "B")}}


def main():
    torch.set_num_threads(2)
    cases = fixture_cases()
    ok("case SHA sealed", verify(cases) == cases["cases_sha256"])
    smoke = seal(phase="smoke", counts={"gap": 2, "stepping_stones": 2, "flat": 0, "stairs_up": 0},
                 eval_seeds=[1100, 1101, 1102, 1103], learning_seeds=[7, 11, 42],
                 command="fwd03", difficulty=.5, friction=1., terrain_source="source",
                 terrain_source_sha256="a"*64, geometry_sha256="b"*64)
    ok("smoke has only four target cases", verify(smoke) == smoke["cases_sha256"] and
       len(smoke["cases"]) == 4 and smoke["counts"]["flat"] == 0)
    j = job(cases)
    ok("deterministic job accepted", validate_job(j, cases))
    result = run(j, cases, lambda c, m: FakeAdapter(c, m),
                 policies={"A": MeanPolicy(), "B": MeanPolicy()})
    ok("same four cases both arms", len(result["records"]) == 8 and
       all(r.get("missing_reason") is None for r in result["records"]))
    post = aggregate(cases, result)
    ok("paired physical initial state", post["valid_pairs"] == 4 and
       all(p["paired"] and p["B_minus_A"] == 0 for p in post["paired_cases"]))
    ok("numerator denominator and hold flags", post["layers"]["gap"]["numerator_denominator"]["A_success"] == [0, 1]
       and post["comparison_ready"] is False and post["performance_verified"] is False)
    broken = copy.deepcopy(result)
    broken["records"] = [r for r in broken["records"] if not
                         (r["case_id"] == cases["cases"][0]["case_id"] and r["arm"] == "B")]
    miss = aggregate(cases, broken)
    ok("one-arm missing disclosed", miss["layers"]["gap"]["numerator_denominator"]["A_success"] == [0, 0]
       and miss["layers"]["gap"]["missing"][0]["reasons"] == ["B:absent"])
    unequal = copy.deepcopy(result)
    unequal["records"][1]["fingerprint"]["mesh_sha256"] = "f" * 64
    mismatch = aggregate(cases, unequal)
    ok("different mesh removes pair", mismatch["valid_pairs"] == 3 and
       mismatch["layers"]["gap"]["missing"][0]["reasons"] == ["physical_fingerprint_diff"])
    def demand_all_pairs(report):
        for row in report["paired_cases"]:
            if not row["paired"]:
                raise AssertionError(";".join(row["reasons"]))
    caught("initial physical state mutation", "physical_fingerprint_diff",
           lambda: demand_all_pairs(aggregate(cases, unequal)))
    ok("1043 Tango interval not two Wilson subtractions", post["interval_method"] ==
       "1043 paired_ci.tango score 95%" and len(post["layers"]["gap"]["paired_tango_95"]) == 3)
    with tempfile.TemporaryDirectory() as td:
        parent, _ = load_parent_cpu(j["parent"]["path"], j["agent_yaml"]["path"])
        real = copy.deepcopy(j)
        for mode in ("A", "B"):
            policy, _, _ = build_s2(mode, parent=parent, map_init_seed=0)
            path = Path(td) / (mode + ".pt")
            saved_runner(policy, mode).save(path)
            real["arms"][mode]["checkpoint"] = str(path)
            real["arms"][mode]["checkpoint_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            real["arms"][mode]["env_config_sha256"] = "a" * 64
        loaded_real = load_policies(real)
        ok("real E1 and S2 strict load", set(loaded_real) == {"A", "B"} and
           all(loaded_real[m][1]["policy_tensor_count"] == 38 for m in ("A", "B")))
        direct = run_case(FakeAdapter(cases["cases"][0], "A"), loaded_real["A"][0],
                          cases["cases"][0], "A", geometry_tolerance_m=.002)
        ok("real deterministic forward with map", direct["missing_reason"] is None and direct["steps"] == 2)

    altered = copy.deepcopy(cases); altered["cases"][0]["eval_seed"] = 7
    caught("seed overlap mutation", "case list SHA", lambda: verify(altered))
    caught("seed overlap generator", "disjoint", lambda: seal(
        phase="full",
        counts={f: 1 for f in ("gap", "stepping_stones", "flat", "stairs_up")},
        eval_seeds=[7, 1001, 1002, 1003], learning_seeds=[7, 11], command="fwd03",
        difficulty=.5, friction=1., terrain_source="x", terrain_source_sha256="a"*64,
        geometry_sha256="b"*64))
    caught("UNDECIDED count mutation", "UNDECIDED", lambda: seal(
        phase="full", counts={"gap": "UNDECIDED", "stepping_stones": 1, "flat": 1, "stairs_up": 1},
        eval_seeds=[1000, 1001, 1002, 1003], learning_seeds=[7, 11], command="fwd03",
        difficulty=.5, friction=1., terrain_source="x", terrain_source_sha256="a"*64,
        geometry_sha256="b"*64))
    stochastic = copy.deepcopy(j); stochastic["inference"] = "act"
    caught("stochastic inference mutation", "deterministic_inference_required",
           lambda: validate_job(stochastic, cases))
    driver_source = (Path(__file__).parent / "s2_eval_driver.py").read_text(encoding="utf-8")
    mutant_source = driver_source.replace("policy.act_inference(frame)", "policy.act(frame)")
    assert mutant_source != driver_source
    mutant_ns = {"__name__": "s2_eval_driver_stochastic_mutant", "__file__": str(Path(__file__).parent / "s2_eval_driver.py")}
    exec(compile(mutant_source, mutant_ns["__file__"], "exec"), mutant_ns)
    caught("stochastic code mutation", "stochastic act called", lambda: mutant_ns["run_case"](
        FakeAdapter(cases["cases"][0], "A"), MeanPolicy(), cases["cases"][0], "A",
        geometry_tolerance_m=.002))
    post_source = (Path(__file__).parent / "s2_eval_post.py").read_text(encoding="utf-8")
    bad_post_source = post_source.replace('n = layer["valid_pairs"]', 'n = layer["planned_pairs"]')
    assert bad_post_source != post_source
    post_ns = {"__name__": "s2_eval_post_bad_denominator", "__file__": str(Path(__file__).parent / "s2_eval_post.py")}
    exec(compile(bad_post_source, post_ns["__file__"], "exec"), post_ns)
    def check_missing_denominator():
        bad = post_ns["aggregate"](cases, broken)
        actual = bad["layers"]["gap"]["numerator_denominator"]["A_success"]
        if actual != [0, 0]:
            raise AssertionError(f"denominator mismatch: {actual} != [0,0]")
    caught("missing denominator code mutation", "denominator mismatch", check_missing_denominator)
    # A repeated generation must be rejected once a second frame is consumed.
    # The case returns after two steps, so use an alive third-frame variant below.
    class ThreeFrame(FakeAdapter):
        def step_recorded(self, action):
            self.num += 1
            return self.obs, self.num == 3, dict(pos=[0.1 * self.num, 0., .5],
                yaw=0., vb=[0., 0., 0.], wb=[0., 0., 0.], grav_z=-1., hag=.5,
                term=self.num == 3)
    longer = copy.deepcopy(cases["cases"][0]); longer["command"]["duration_s"] = .06
    caught("stale packet mutation", "stale sensor packet", lambda: run_case(
        ThreeFrame(longer, "A", stale=True), MeanPolicy(), longer, "A", geometry_tolerance_m=.002))
    class BadReset(FakeAdapter):
        def reset_receipt(self):
            return {**super().reset_receipt(), "post_reset_sensor_refresh": False}
    caught("reset receipt mutation", "reset_receipt_missing_or_mismatched", lambda: run_case(
        BadReset(cases["cases"][0], "A"), MeanPolicy(), cases["cases"][0], "A",
        geometry_tolerance_m=.002))
    original = FakeAdapter(cases["cases"][0], "A"); original.reset(cases["cases"][0])
    packet = original.capture_packet_after_sensor_update()
    next_receipt = {**packet.source_receipt, "generation": 2, "step": 2,
                    "generation_by_env": [2], "sensor_timestamp_by_env": [2.]}
    next_packet = replace(packet, sim_step=2, sensor_step=2, sensor_generation=2,
                          packet_id="2:new", source_receipt=next_receipt)
    caught("reset episode id mutation", "reset episode id did not advance",
           lambda: next_packet.validate(previous=packet, previous_done=torch.tensor([True])))
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for name in ("A", "B"):
            (root / name).write_bytes(name.encode())
        checked = copy.deepcopy(j)
        for mode in ("A", "B"):
            checked["arms"][mode]["checkpoint"] = str(root / mode)
            checked["arms"][mode]["checkpoint_sha256"] = hashlib.sha256(mode.encode()).hexdigest()
        calls = []
        def parent_loader(*args):
            calls.append("parent")
            return object(), {}
        def ckpt_loader(*args, **kwargs):
            calls.append(kwargs["mode"])
            return MeanPolicy(), {}
        loaded = load_policies(checked, parent_loader=parent_loader, checkpoint_loader=ckpt_loader)
        ok("hashes before deserialization", calls == ["parent", "A", "B"] and set(loaded) == {"A", "B"})
        calls.clear(); (root / "B").write_bytes(b"tampered")
        caught("checkpoint SHA mutation", "B_checkpoint_sha256", lambda: load_policies(
            checked, parent_loader=parent_loader, checkpoint_loader=ckpt_loader))
        ok("bad checkpoint rejected before parent load", calls == [])
        (root / "B").write_bytes(b"B"); checked["agent_yaml"]["sha256"] = "0" * 64
        caught("agent YAML SHA mutation", "agent_yaml_sha256", lambda: load_policies(
            checked, parent_loader=parent_loader, checkpoint_loader=ckpt_loader))
        checked["agent_yaml"]["sha256"] = AGENT_YAML_SHA256
        case_path, job_path, output_path = root / "cases.json", root / "job.json", root / "episodes.json"
        case_path.write_bytes(canonical(cases) + b"\n")
        job_path.write_bytes(canonical(checked) + b"\n")
        file_hash = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        sealed_run = run_from_files(job_path=job_path, job_sha256=file_hash(job_path),
                                    cases_path=case_path, cases_file_sha256=file_hash(case_path),
                                    adapter_factory=lambda c, m: FakeAdapter(c, m), output_path=output_path,
                                    parent_loader=parent_loader, checkpoint_loader=ckpt_loader)
        ok("one sealed case file produces episode file", output_path.is_file() and
           len(sealed_run["records"]) == 8 and json.loads(output_path.read_text())["cases_sha256"] == cases["cases_sha256"])
        aggregate_path = root / "aggregate.json"
        file_post = aggregate_from_files(cases_path=case_path, cases_file_sha256=file_hash(case_path),
            episodes_path=output_path, episodes_file_sha256=file_hash(output_path),
            output_path=aggregate_path)
        ok("sealed file post and input hashes", aggregate_path.is_file() and
           file_post["valid_pairs"] == 4 and file_post["episodes_file_sha256"] == file_hash(output_path))
        caught("case file SHA mutation", "input_sha256", lambda: run_from_files(
            job_path=job_path, job_sha256=file_hash(job_path), cases_path=case_path,
            cases_file_sha256="0"*64, adapter_factory=lambda c, m: FakeAdapter(c, m),
            output_path=root/"bad.json", parent_loader=parent_loader, checkpoint_loader=ckpt_loader))
    ok("no legacy loader assumptions", "loaded_iter" not in driver_source and
       "runner.load" not in driver_source and "model_N.pt" not in driver_source)
    old = '    for key in ("parent", "agent_yaml"):'
    injected = ('    if any(Path(job["arms"][m]["checkpoint"]).name != "model_0.pt" '
                'for m in ("A", "B")):\n'
                '        raise EvalHold("loaded_iter_filename_assumption")\n' + old)
    legacy_source = driver_source.replace(old, injected)
    assert legacy_source != driver_source
    legacy_ns = {"__name__": "s2_eval_driver_legacy_mutant", "__file__": str(Path(__file__).parent / "s2_eval_driver.py")}
    exec(compile(legacy_source, legacy_ns["__file__"], "exec"), legacy_ns)
    caught("loaded_iter code mutation", "loaded_iter_filename_assumption",
           lambda: legacy_ns["load_policies"](j, parent_loader=lambda *_: (None, {})))
    print(json.dumps({"normal_PASS": PASS, "mutants_CAUGHT": CAUGHT}, ensure_ascii=False))


if __name__ == "__main__":
    main()
