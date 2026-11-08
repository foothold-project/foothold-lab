"""Check the Linux env example against the training profile and the ops profile.

Usage: python machines/check_linux_env.py --ops-json <AI-WS01-linux-ops.example.json>
           [--env machines/AI-WS01-linux.env.example]

1. Every ${VAR} in machines/AI-WS01-linux.yaml is either assigned in the env
   example or listed there as a commented TODO-measure-on-linux line.
2. The ops profile (_out/tools/machines/AI-WS01-linux-ops.example.json, from
   89db2513) names the same places as the training profile wherever the
   Windows tools already share one place. Each pair below cites the Windows
   value both sides use today.
Exit 1 with one line per problem; exit 0 prints "ok".
"""
from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAKE_HOME = "/home/LINUX_USER"
_ASSIGN = re.compile(r"^([A-Z_][A-Z0-9_]*)=(.*)$")
_TODO = re.compile(r"^#\s*([A-Z_][A-Z0-9_]*)=\s*#\s*TODO-measure-on-linux\b")
_REF = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")


def parse_env(text: str, home: str = FAKE_HOME) -> tuple[dict[str, str], set[str]]:
    """Expand the file the way `set -a; . file` would, for $HOME and earlier names only."""
    values: dict[str, str] = {}
    todo: set[str] = set()
    scope = {"HOME": home}
    for raw in text.splitlines():
        line = raw.strip()
        if (m := _TODO.match(line)):
            todo.add(m.group(1))
            continue
        if not line or line.startswith("#"):
            continue
        m = _ASSIGN.match(line)
        if not m:
            raise ValueError(f"unparsed env line: {raw!r}")
        def sub(ref: re.Match[str]) -> str:
            name = ref.group(1) or ref.group(2)
            if name not in scope:
                raise ValueError(f"{m.group(1)} uses {name} before it is set")
            return scope[name]
        value = _REF.sub(sub, m.group(2).strip())
        values[m.group(1)] = scope[m.group(1)] = value
    return values, todo


def profile_vars(yaml_text: str) -> set[str]:
    return set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", yaml_text))


def coverage_problems(yaml_text: str, values: dict[str, str], todo: set[str]) -> list[str]:
    out = []
    for name in sorted(profile_vars(yaml_text)):
        if name not in values and name not in todo:
            out.append(f"profile variable {name} is neither set nor marked TODO-measure-on-linux")
        if name in values and name in todo:
            out.append(f"{name} is both set and marked TODO")
    return out


def ops_problems(values: dict[str, str], ops: dict, home: str = FAKE_HOME) -> list[str]:
    p = {k: (home + v[1:] if isinstance(v, str) and v.startswith("~") else v)
         for k, v in ops.get("paths", {}).items()}
    v = values
    out = []

    def same(ops_key, got, want, why):
        if got != want:
            out.append(f"ops {ops_key} = {got} but training side gives {want} ({why})")

    def under(ops_key, root_name):
        root = v.get(root_name, "")
        if not str(p.get(ops_key, "")).startswith(root.rstrip("/") + "/"):
            out.append(f"ops {ops_key} = {p.get(ops_key)} is not under {root_name} = {root}")

    # Windows: dispatch.py markers[0] "D:/mai-tmp/gpu" · windows.yaml gpu_queue D:/mai-tmp/gpu/queue.json
    same("gpu_root", p.get("gpu_root"), posixpath.dirname(v.get("GPU_JOBS_QUEUE", "")), "queue dir")
    # Windows: bind_registry marker gpu_root/PRIORITY_BUSY_GPU1 · windows.yaml gpu1_eval_marker
    same("gpu_root", posixpath.join(str(p.get("gpu_root")), "PRIORITY_BUSY_GPU1"),
         v.get("GPU1_EVAL_MARKER"), "P1 marker")
    # Windows: jobs.json w78-video D:/mai-tmp/ex41/w78_video · windows.yaml ex41_w78_video_root
    same("w78_video", p.get("w78_video"), v.get("EX41_W78_VIDEO_ROOT"), "W78 video root")
    # Windows: dispatch.py markers[1] s2_lab/c_layer_m6000/priority · windows.yaml a_layer_marker dir
    same("c_layer_priority", p.get("c_layer_priority"), posixpath.dirname(v.get("A_LAYER_MARKER", "")),
         "A-layer marker dir")
    same("c_layer_priority", p.get("c_layer_priority"), posixpath.dirname(v.get("GPU0_TRAINING_MARKER", "")),
         "GPU0 training marker dir")
    # Windows: dispatch.py eval_root and p1_attempt_globs under C:/Users/AI-WS01/s2_lab
    for key in ("eval_root", "p1_attempt_glob", "baseline_m6000"):
        under(key, "S2_LAB_ROOT")
    for key in ("stage_table", "worklist", "canon_retry"):
        under(key, "MAI_WORKTREE_ROOT")
    # Windows: jobs.json c-layer output D:/mai-tmp/c_layer_m6000/out
    under("c_layer_out", "MAI_TMP_ROOT")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env", type=Path, default=ROOT / "machines/AI-WS01-linux.env.example")
    ap.add_argument("--profile", type=Path, default=ROOT / "machines/AI-WS01-linux.yaml")
    ap.add_argument("--ops-json", type=Path, required=True)
    a = ap.parse_args(argv)
    values, todo = parse_env(a.env.read_text(encoding="utf-8"))
    problems = coverage_problems(a.profile.read_text(encoding="utf-8"), values, todo)
    problems += ops_problems(values, json.loads(a.ops_json.read_text(encoding="utf-8-sig")))
    for line in problems:
        print(line)
    if not problems:
        print("ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
