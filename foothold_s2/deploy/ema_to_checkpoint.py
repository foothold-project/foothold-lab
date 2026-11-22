"""model_N_ema.pt as a model_N.pt the official evaluation and the stage parent loader accept (lead 2026-11-22 09:30, design (a)). CPU only.

Why: the planner scores E2 freeze and the prescription runs on the EMA column, but the official evaluation (ex42_eval_once
manifest_checkpoint_sha: name model_(\\d+)\\.pt, sha in manifest.json beside it) and the parent loader (plan pin checkpoint_key + sha,
verify_parent_manifest: exactly one manifest checkpoint with that sha, file beside the manifest) read model_N.pt only.

What the EMA file already is (start_runner._save_ema_checkpoint): the model_N.pt layout (state_dict() of the runner) with
model_state_dict and perception_state_dict replaced by the policy average, policy_ema dropped, policy_ema_of added. Optimizer states,
AdaSmpl, map switch, RNG, perception_ema are the live ones of that save. Measured on rx2qh m250 (09:3x): every other key is equal.

What every reader does with it: the evaluation adapter (eval/adapters.py load_s2_runner) and the stage parent loader
(start_runner.load_ex42_stage_zero_parent with a stage id) put perception_ema over perception_state_dict. perception_ema covers every
perception parameter (105 of 105 on rx2qh m250), so the perception the EMA file is scored with is the same perception_ema that
model_N.pt is scored with; only the actor / critic (model_state_dict) differ. This tool keeps that: nothing is re-averaged.

The output: the EMA file's dict unchanged plus an "ema_export" entry, saved as <out>/model_N.pt (a separate folder: it never sits
beside the original model_N.pt), and <out>/manifest.json = the source manifest with "checkpoints" replaced by the exported files only
and an "ema_export" record per file (source EMA sha256, source model_N.pt sha256, this tool's sha256). Optimizer entries stay the
originals (the parent loader calls optimizer.load_state_dict on them; an empty one would be refused).

  python -m foothold_s2.deploy.ema_to_checkpoint --run <run folder> --iter 250 [--iter 200 ...] --out <new folder>

Caution: evaluate the exported folder without --next-stage-launcher (the hand-off would otherwise start a stage from it).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import torch

FORMAT = "foothold-ema-export/1"


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def export(run_dir, iterations, out_dir) -> dict:
    run, out = Path(run_dir).resolve(strict=True), Path(out_dir).resolve()
    if out == run:
        raise ValueError("the output folder must not be the run folder (the export would sit beside the original model_N.pt)")
    out.mkdir(parents=True, exist_ok=True)
    if (out / "manifest.json").exists():
        raise ValueError(f"{out / 'manifest.json'} exists: use a new folder")
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8-sig"))
    tool_sha = sha256(__file__)
    checkpoints, records = {}, {}
    for n in sorted({int(i) for i in iterations}):
        src_ema, src_ckpt = run / f"model_{n}_ema.pt", run / f"model_{n}.pt"
        ema_sha, ckpt_sha = sha256(src_ema), sha256(src_ckpt)
        if (manifest.get("checkpoints") or {}).get(src_ckpt.name) != ckpt_sha:
            raise ValueError(f"{src_ckpt.name} differs from the run manifest sha")
        sd = torch.load(src_ema, map_location="cpu", weights_only=False)
        of = sd.get("policy_ema_of") or {}
        if sd.get("iter") != n or of.get("iter") != n or "policy_ema" in sd:
            raise ValueError(f"{src_ema.name} is not the EMA save of update {n}")
        record = {"format": FORMAT, "source_ema": str(src_ema), "source_ema_sha256": ema_sha, "source_checkpoint": str(src_ckpt),
                  "source_checkpoint_sha256": ckpt_sha, "tool": "foothold_s2/deploy/ema_to_checkpoint.py", "tool_sha256": tool_sha,
                  "policy_ema_of": of}
        sd["ema_export"] = record
        name = f"model_{n}.pt"
        if not re.fullmatch(r"model_(\d+)\.pt", name):
            raise AssertionError(name)
        tmp = out / f"{name}.tmp"
        torch.save(sd, tmp)
        os.replace(tmp, out / name)
        checkpoints[name] = sha256(out / name)
        records[name] = {**record, "sha256": checkpoints[name]}
    manifest["checkpoints"] = checkpoints
    manifest["ema_export"] = {"format": FORMAT, "source_run": str(run), "source_manifest_sha256": sha256(run / "manifest.json"),
                              "files": records}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True, allow_nan=False), encoding="utf-8")
    return manifest["ema_export"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--iter", type=int, action="append", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    print(json.dumps(export(a.run, a.iter, a.out), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
