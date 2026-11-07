"""W39 CPU/read-only evidence recheck. Writes only the supplied analyst output folder."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOTS = {
    "runner": ("D:/mai-wt/foothold-lab/runner-ex42-v016", "5e0c37a1"),
    "w35": ("D:/mai-wt/foothold-lab/scripter-ex42-gates", "a8381f8a"),
    "i36": ("D:/mai-wt/foothold-lab/scripter-ops-check-i36", "1d382122"),
    "dark": ("D:/mai-wt/foothold-lab/stagevideo-darkdiag-1107", "b07b4089"),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True,
                                   encoding="utf-8").strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = {"at": datetime.now().astimezone().isoformat(), "roots": {}}
    for key, (name, prefix) in ROOTS.items():
        root = Path(name)
        head = git(root, "rev-parse", "HEAD")
        assert head.startswith(prefix), (name, head, prefix)
        dirty = git(root, "status", "--porcelain=v1")
        assert not dirty, (name, dirty)
        result["roots"][key] = {"path": name, "head": head, "dirty": dirty}

    runner = Path(ROOTS["runner"][0])
    w35 = Path(ROOTS["w35"][0])
    i36 = Path(ROOTS["i36"][0])
    gates = module("w39_gates", runner / "foothold_s2/ex42_gate_checks.py")
    ops = module("w39_ops", i36 / "_out/tools/ex41/ops_check.py")
    split = module("w39_split", w35 / "foothold_s2/eval/ex42_w78_gate.py")

    # Known-answer fixture: G11 alone is open. Do not edit a real launch gate.
    rows = [f"G{n:02d}" for n in range(1, 34)]
    table = out / "fixture-g11-open.md"
    table.write_text("| ID | a | b | c | status | owner |\n|---|---|---|---|---|---|\n" +
                     "\n".join(f"| {key} | x | x | x | " +
                               ("예행 대기" if key == "G11" else "검증 완료") + " | fixture |"
                               for key in rows), encoding="utf-8")
    default = gates.open_gate_rows(table)
    all_rows = gates.open_gate_rows(table, rows)
    assert default == [] and all_rows == ["G11"]
    result["gate_subset_counterexample"] = {"fixture": str(table), "expected_open": ["G11"],
        "default_actual": default, "explicit_all33_actual": all_rows,
        "required": list(gates.REQUIRED_GATE_ROWS)}

    # Known-answer fixture: completed item with nonexistent evidence must not prove completion.
    worklist = out / "fixture-done-missing.tsv"
    missing = out / "never-created-evidence.md"
    assert not missing.exists()
    worklist.write_text("id\tsource\tpriority\tdue\towner\tevidence\tstatus\twhat\n"
        f"WTEST\tCPU fixture\tP0\tat:2026-11-06T10:00\tanalyst\t{missing}\tdone\tmissing evidence\n",
        encoding="utf-8")
    done = ops.worklist(worklist, datetime(2026, 11, 7, 10).timestamp(), 6000)
    assert not any(row[0] == "FAIL" for row in done)
    result["false_done_counterexample"] = {"fixture": str(worklist), "output": done,
                                            "evidence_exists": missing.exists()}

    # W35's own successful synthetic sample contract, with a changed terrain in repeats only.
    def receipt(value):
        return {"state": "done", "run_identity": {"code_head": "a" * 40},
            "source_sha256": {"terrain_skill_v2_run.py": "b" * 64},
            "checkpoint_sha256": "c" * 64, "checkpoint_iter": 750, "eval_seed": 42,
            "envs": 64, "levels": [2], "start_angles_deg": [0], "dt_s": .02,
            "dr_off": True, "curriculum_off": True, "mode_selection": ["eval_gt"],
            "case_selection": ["stairs_side_left"],
            "modes": {"eval_gt": {"L2_a000_stairs_side_left": {"distance": value,
                "case": "stairs_side_left", "requested_kinds": ["stairs"],
                "terrain_assignment_sha256": "d" * 64,
                "terrain_tiles": [{"env": 0, "kind": "stairs", "level": 2, "column": 0}],
                "phase_steps": [50]}}}}
    full, unit = receipt(1), receipt(1.1)
    repeats = [receipt(1.04), receipt(1.2)]
    base = split.compare_split(full, [unit], repeats=deepcopy(repeats))
    assert base["state"] == "PASS"
    for repeat in repeats:
        row = repeat["modes"]["eval_gt"]["L2_a000_stairs_side_left"]
        row["terrain_assignment_sha256"] = "e" * 64
        row["terrain_tiles"][0]["level"] = 9
    changed = split.compare_split(full, [unit], repeats=repeats)
    assert changed["state"] == "PASS"
    (out / "fixture-repeat-wrong-terrain.json").write_text(json.dumps(
        {"full": full, "unit": unit, "repeats": repeats}, indent=2), encoding="utf-8")
    result["repeat_terrain_counterexample"] = {"expected": "HOLD", "actual": changed,
        "control_actual": base, "changed": ["terrain_assignment_sha256", "terrain_tiles[0].level=9"]}

    # Directly recount the diagnostic raw outputs, without sim or video rendering.
    raw = Path("D:/mai-tmp/runner/ex41_dark_diag_1107/capture/attempts/"
        "6929329c023ea3d97c6e7d59d5013be0a167b57ac7991f31198ec519fdd8fcb6/01/dark_render_diagnostics")
    samples = raw / "render_samples.jsonl"
    records = [json.loads(line) for line in samples.read_text(encoding="utf-8").splitlines()]
    image_checks = []
    from PIL import Image
    import numpy as np
    for row in records:
        if row["raw_rgb_path"]:
            path = raw / row["raw_rgb_path"]
            assert sha(path) == row["raw_rgb_sha256"]
            pixels = np.asarray(Image.open(path).convert("RGB"))
            assert int(pixels.max()) == 0
            image_checks.append(path.name)
    result["dark_raw"] = {"source": str(samples), "sha256": sha(samples),
        "sample_count": len(records), "dark_png_sha_and_pixels_checked": len(image_checks),
        "frames": {}}
    for frame in [17, 72]:
        part = [r for r in records if r["frame_index"] == frame]
        result["dark_raw"]["frames"][str(frame)] = {
            "rows": len(part), "dark": sum(r["dark"] for r in part),
            "brightness": [r["mean_brightness"] for r in part],
            "ticks": sorted(set(r["details"]["physics_tick"] for r in part)),
            "all_states_equal": all(r["details"]["render_state_before"] ==
                                     r["details"]["render_state_after"] for r in part)}
    queue_result = Path("D:/mai-tmp/gpu/results/item_827.json")
    result["dark_raw"]["queue"] = json.loads(queue_result.read_text(encoding="utf-8"))
    result["dark_raw"]["queue_sha256"] = sha(queue_result)

    files = {
        "runner": ["foothold_s2/curriculum/ex42_runtime.py", "experiments/EX-42.yaml",
            "foothold_s2/ex42_gate_checks.py", "foothold_s2/ex42_status.py",
            "foothold_s2/scripts/ex42_ops.py", "foothold_s2/curriculum/ex42-prep.yaml"],
        "w35": [f"foothold_s2/eval/ex42_{n}.py" for n in
            ["w78_gate", "component_receipts", "terrain_evidence", "video_sample", "video_delivery"]],
        "i36": ["_out/tools/ex41/ops_check.py"],
        "dark": ["foothold_s2/eval/video25/dark_render_diagnostics.py"],
    }
    result["source_files"] = []
    for key, names in files.items():
        root = Path(ROOTS[key][0])
        for name in names:
            path = root / name
            target = out / "source" / key / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            result["source_files"].append({"group": key, "path": str(path),
                "sha256": sha(path), "snapshot": str(target)})
    # Match production references only, not claims in tests or documentation.
    symbols = ["ex42_w78_gate", "ex42_component_receipts", "ex42_terrain_evidence",
               "ex42_video_sample", "ex42_video_delivery", "ex42_status",
               "validate_map_matrix", "extract_realized_config", "validate_automatic_rule",
               "process_score_batch", "audit_locked_checkout"]
    result["runner_call_search"] = {s: [] for s in symbols}
    for path in (runner / "foothold_s2").rglob("*.py"):
        if "tests" in path.parts:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            for symbol in symbols:
                if symbol in line:
                    result["runner_call_search"][symbol].append({"path": str(path.relative_to(runner)),
                        "line": lineno, "text": line.strip()})
    (out / "recheck.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"counterexamples_reproduced": 3, "dark_samples": len(records),
                      "dark_pngs_checked": len(image_checks), "output": str(out / "recheck.json")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
