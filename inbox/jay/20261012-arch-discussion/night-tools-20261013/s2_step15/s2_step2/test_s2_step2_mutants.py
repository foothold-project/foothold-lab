"""New code mutants: same normal test first, then exact first failure."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).parent
OUT = Path(os.environ.get("S2_EVIDENCE_DIR", HERE.parent / "evidence_s2_step2" /
                          f"mutants_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"))
CASES = [
    ("adaptive_lr", "s2_ppo.py", 'kl_mean > desired_kl * 2.0',
     'kl_mean > desired_kl * 200.0', "adaptive LR parent thresholds"),
    ("ray_order", "s2_env_adapter.py", '(pattern.ordering == M.GRID_ORDERING, "ray ordering")',
     '(True, "ray ordering")', "ray order mismatch rejected"),
    ("map_snapshot", "s2_runner.py", 'frame["map"] = mapped.detach().clone()',
     'frame["map"] = torch.zeros_like(mapped)', "rollout map snapshot and bootstrap time"),
    ("validity_gate", "s2_runner.py", 'gate.require_valid()  # Every arm checks before any PPO update.',
     'None  # removed validity gate', "reward NaN gate blocks update"),
    ("terrain_geometry", "s2_terrain_overlay.py", 'sub["gap"].gap_width_range = (0.10, 0.25)',
     'sub["gap"].gap_width_range = (0.0, 0.9)', "terrain geometry from CPU probe and parent untouched"),
    ("approval_gate", "s2_launch_gate.py", 'approval.get("approved") is not True',
     'False', "unapproved launch denied"),
]
FILES = ["s2_ppo.py", "s2_runner.py", "s2_env_adapter.py", "s2_terrain_overlay.py",
         "s2_launch_gate.py", "test_s2_step2.py"]


def run(path, log):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", PYTHONIOENCODING="utf-8")
    began = time.monotonic()
    with log.open("wb") as stream:
        result = subprocess.run([sys.executable, "-B", "-u", str(path / "test_s2_step2.py")],
                                cwd=path, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=120)
    return result.returncode, round(time.monotonic()-began, 2), log.read_text(encoding="utf-8")


def main():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1":
        raise RuntimeError("CPU-only mutation suite")
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for name, filename, old, new, want in CASES:
        source = (HERE / filename).read_text(encoding="utf-8")
        if source.count(old) != 1:
            raise AssertionError(f"mutation anchor {name} count {source.count(old)}")
        normal_log = OUT / f"{name}.normal.log"
        nr, ns, nt = run(HERE, normal_log)
        if nr or f"PASS {want}" not in nt:
            raise AssertionError(f"normal control failed: {normal_log}")
        dest = OUT / "mutants" / name
        dest.mkdir(parents=True, exist_ok=False)
        for file in FILES:
            shutil.copy2(HERE / file, dest / file)
        shutil.copytree(HERE / "base_step1", dest / "base_step1")
        mutant = dest / filename
        mutant.write_text(source.replace(old, new, 1), encoding="utf-8")
        mutant_log = OUT / f"{name}.mutant.log"
        mr, ms, mt = run(dest, mutant_log)
        actual = next((match.group(1) for line in mt.splitlines()
                       if (match := re.match(r"FAIL (.+)", line))), None)
        print(f"failed [{actual}] want [{want}]", flush=True)
        caught = mr != 0 and actual == want and f"AssertionError: {want}" in mt
        print("CAUGHT" if caught else "NOT_CAUGHT", name, "normal", nr, "mutant", mr, flush=True)
        records.append({"name": name, "normal_exit": nr, "normal_s": ns, "normal_log": str(normal_log),
                        "mutant_exit": mr, "mutant_s": ms, "mutant_log": str(mutant_log),
                        "first_failed": actual, "want": want, "caught": caught,
                        "mutant_sha256": hashlib.sha256(mutant.read_bytes()).hexdigest()})
        if not caught:
            break
    (OUT / "summary.json").write_text(json.dumps({"step1_code_mutants": 68,
        "step1_input_gate_mutants": 1,
        "code_mutants_step2": len(CASES), "records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if len(records) == len(CASES) and all(x["caught"] for x in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
