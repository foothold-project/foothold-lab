"""Run the CPU generator in two clean copies and compare every output byte."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest_tree(root):
    files = sorted(p for p in root.rglob("*") if p.is_file()
                   and "__pycache__" not in p.parts)
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(root).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest(), [p.relative_to(root).as_posix() for p in files]


def main():
    with tempfile.TemporaryDirectory(prefix="sol26b-repro-") as scratch:
        roots = [Path(scratch) / n for n in ("copy_a", "copy_b")]
        records = []
        for root in roots:
            out = root / "figs/ex33-34"
            out.mkdir(parents=True)
            for name in ("gen_result.py", "test_gen_result.py", "verify_repro.py"):
                shutil.copy2(HERE / name, out / name)
            env = os.environ.copy()
            env["CUDA_VISIBLE_DEVICES"] = "-1"
            run = subprocess.run(
                [sys.executable, str(out / "gen_result.py"),
                 "--out-dir", str(out), "--result-dir", str(root)],
                env=env, capture_output=True, text=True, check=True)
            records.append({"root": root, "result": json.loads(run.stdout),
                            "digest": digest_tree(root)})
        a, b = records
        assert a["result"] == b["result"], "generator summaries differ"
        assert a["digest"] == b["digest"], "clean-copy bytes differ"
        receipt = {
            "copies": 2,
            "files_per_copy": len(a["digest"][1]),
            "tree_sha256_both": a["digest"][0],
            "assertions_each": a["result"]["assertions"],
            "byte_identical": True,
            "source_video_sha_list_sha256": json.loads(
                (a["root"] / "figs/ex33-34/summary.json").read_text(encoding="utf-8")
            )["source_video_sha_list_sha256"],
            "paths": a["digest"][1],
        }
    with (HERE / "reproducibility.json").open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: receipt[k] for k in
                      ("copies", "files_per_copy", "assertions_each",
                       "byte_identical", "tree_sha256_both")}))


if __name__ == "__main__":
    main()
