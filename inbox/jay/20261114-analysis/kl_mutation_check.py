"""CPU counterexamples in disposable source copies; never touch the working tree."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    module = "runners/ppo_kl_audit.py"
    cases = [
        ("control", module, None, None),
        ("epsilon_removed", module, "sigma / old_sigma + 1.0e-5", "sigma / old_sigma"),
        ("after_optimizer", module, "register_step_pre_hook(self._optimizer_pre_step)", "register_step_post_hook(self._optimizer_pre_step)"),
        ("wrong_env_id", module, "env_id=flat_id % self.alg.storage.num_envs", "env_id=(flat_id + 1) % self.alg.storage.num_envs"),
        ("quarantine_included", "runners/ex41_valid_storage.py", "batch_idx = batch_idx[valid[batch_idx]]", "batch_idx = batch_idx"),
        ("sample_weighted_rank_mean", module, "mean_tensor = means.sum() / world",
         "mean_tensor = (means * torch.tensor([r[\"valid_count\"] for r in sorted(rows, key=lambda r: r[\"rank\"])])).sum() / sum(r[\"valid_count\"] for r in rows)"),
        ("missing_pair_hidden", module, "grouped.setdefault((*update_key, epoch, batch), [])", "pass"),
        ("off_overridden_by_gt", module, "torch.where(state.map_off.bool(), 2, torch.where(state.use_gt.bool(), 0, 1))",
         "torch.where(state.use_gt.bool(), 0, torch.where(state.map_off.bool(), 2, 1))"),
        ("reset_not_marked", module, "torch.where(done, 0, self.reset_age + 1)", "self.reset_age + 1"),
    ]
    results = []
    for name, relative, old, new in cases:
        case = out / name
        case.mkdir(exist_ok=False)
        shutil.copytree(root / "foothold_s2", case / "foothold_s2",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        if old is not None:
            path = case / "foothold_s2" / relative
            text = path.read_text(encoding="utf-8")
            if text.count(old) != 1:
                raise ValueError(f"{name}: mutation needs exactly one target")
            path.write_text(text.replace(old, new), encoding="utf-8")
        env = {**os.environ, "CUDA_VISIBLE_DEVICES": "", "PYTHONDONTWRITEBYTECODE": "1",
               "OMP_NUM_THREADS": "2", "PYTHONPATH": str(case)}
        command = [sys.executable, "-B", "-m", "pytest", "foothold_s2/tests/test_ppo_kl_audit_cpu.py",
                   "-q", "-p", "no:cacheprovider", "--basetemp", str(case / "tmp")]
        run = subprocess.run(command, cwd=case, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, timeout=90)
        (case / "pytest.log").write_text(run.stdout, encoding="utf-8")
        # Import/syntax failures are an invalid mutant, not test detection.
        valid = "ERROR collecting" not in run.stdout and "SyntaxError" not in run.stdout
        caught = run.returncode == 1 and " failed" in run.stdout and valid
        results.append({"name": name, "rc": run.returncode, "caught": caught,
                        "valid_test_run": valid, "log": str(case / "pytest.log")})
        print(name, run.returncode, "caught" if caught else "control" if name == "control" else "NOT CAUGHT", flush=True)
        if name == "control" and run.returncode != 0:
            raise RuntimeError("control failed; no mutation result is valid")
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0 if results[0]["rc"] == 0 and all(r["caught"] for r in results[1:]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
