"""Read saved S1 configs and diagnostic JSON on CPU; never imports Isaac or torch."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_read(path: Path):
    raw = path.read_bytes()
    encoding = "utf-8-sig"
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        encoding = "cp949"
        text = raw.decode(encoding)
    return {"path": path.as_posix(), "sha256": sha(path), "encoding": encoding,
            "data": json.loads(text)}


def flatten(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from flatten(item, f"{prefix}/{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from flatten(item, f"{prefix}/{i}")
    else:
        yield prefix, value


def yaml_read(path: Path):
    # BaseLoader retains text and cannot construct Python objects in Isaac YAML.
    data = yaml.load(path.read_text(encoding="utf-8-sig"), Loader=yaml.BaseLoader)
    node = yaml.compose(path.read_text(encoding="utf-8-sig"))
    lines, tags = {}, {}

    def walk(n, prefix=""):
        tags[prefix] = n.tag
        if isinstance(n, yaml.MappingNode):
            for key, val in n.value:
                walk(val, f"{prefix}/{key.value}")
        elif isinstance(n, yaml.SequenceNode):
            for i, val in enumerate(n.value):
                walk(val, f"{prefix}/{i}")
        else:
            lines[prefix] = n.start_mark.line + 1

    walk(node)
    return {"path": path.as_posix(), "sha256": sha(path), "data": data, "lines": lines,
            "yaml_tags": tags}


def diff(a, b):
    fa, fb = dict(flatten(a)), dict(flatten(b))
    return [{"key": k, "before": fa.get(k), "after": fb.get(k),
             "before_present": k in fa, "after_present": k in fb}
            for k in sorted(fa.keys() | fb.keys()) if fa.get(k) != fb.get(k)]


RUNS = {
    "EX01_scan": "foothold_s1a/2026-10-20_16-59-25_s1a_scan",
    "EX01_blind": "foothold_s1a/2026-10-20_17-00-34_s1a_blind",
    "EX02_D1": "foothold_s1a_diag/2026-10-21_03-50-41_S1a-diag-D1",
    "EX03_D2": "foothold_s1a_diag/2026-10-21_04-14-45_S1a-diag-D2-kernel025",
    "EX04_D2s43": "foothold_s1a_diag/2026-10-21_06-36-49_S1a-diag-D2-s43",
    "EX05_D3": "foothold_s1a_diag/2026-10-21_06-36-49_S1a-diag-D3-lin025-ang05",
    "EX06_scan": "foothold_s1a_v11/2026-10-21_09-17-28_s1a_v11_scan",
    "EX06_blind": "foothold_s1a_v11/2026-10-21_09-17-30_s1a_v11_blind",
    "EX07_C1": "foothold_s1a_diag/2026-10-21_14-45-28_S1a-diag-C1-torque-scan",
    "EX08_C2": "foothold_s1a_diag/2026-10-21_14-45-30_S1a-diag-C2-linvel-blind",
}
OUTER_LOGS = {
    "EX01_scan": "s1a_scan_20261020_165914",
    "EX01_blind": "s1a_blind_20261020_170021",
    "EX02_D1": "s1a_diag_D1_20261021_035030",
    "EX03_D2": "s1a_diag_D2_20261021_041433",
    "EX04_D2s43": "s1a_diag_D2_20261021_063639",
    "EX05_D3": "s1a_diag_D3_20261021_063639",
    "EX06_scan": "s1a_v11_scan_20261021_091717",
    "EX06_blind": "s1a_v11_blind_20261021_091719",
    "EX07_C1": "s1a_diag_C1-scan_20261021_144518",
    "EX08_C2": "s1a_diag_C2-blind_20261021_144520",
}
PAIRS = [("EX01_scan", "EX01_blind"), ("EX01_scan", "EX02_D1"),
         ("EX01_scan", "EX03_D2"), ("EX03_D2", "EX04_D2s43"),
         ("EX03_D2", "EX05_D3"), ("EX01_scan", "EX06_scan"),
         ("EX01_blind", "EX06_blind"), ("EX06_scan", "EX07_C1"),
         ("EX06_blind", "EX08_C2")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", type=Path, required=True)
    ap.add_argument("--diagnostics", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    assert diff({"a": "1"}, {"a": "2", "b": "3"}) == [
        {"key": "/a", "before": "1", "after": "2", "before_present": True, "after_present": True},
        {"key": "/b", "before": None, "after": "3", "before_present": False, "after_present": True}]
    assert dict(flatten({"a": [1, {"b": 2}]})) == {"/a/0": 1, "/a/1/b": 2}
    result = {"schema": "s1-history-audit/1", "self_check": "two known-input assertions passed",
              "limitation": "Saved configs prove serialization, not runtime application. Values retained as YAML text.",
              "runs": {}, "diffs": {}, "diagnostics": {}}
    for name, relative in RUNS.items():
        root = args.logs / relative
        record = {k: yaml_read(root / "params" / f"{k}.yaml") for k in ["env", "agent"]}
        status = root / "train_start_status.json"
        if status.exists():
            record["status"] = json_read(status)
        checkpoints = sorted((int(p.stem.split("_")[-1]), p.name) for p in root.glob("model_*.pt"))
        record["checkpoints_present"] = checkpoints
        if name in OUTER_LOGS:
            outer = args.logs.parent / OUTER_LOGS[name]
            record["outer_log_directory"] = outer.as_posix()
            record["launch_evidence"] = {}
            for filename in ["git_head.txt", "git_status.txt", "rc.txt"]:
                p = outer / filename
                record["launch_evidence"][filename] = (
                    {"path": p.as_posix(), "sha256": sha(p),
                     "text": p.read_text(encoding="utf-8-sig").strip()}
                    if p.exists() else {"missing": True, "path": p.as_posix()})
        result["runs"][name] = record
    for a, b in PAIRS:
        result["diffs"][f"{a}__{b}"] = {
            k: diff(result["runs"][a][k]["data"], result["runs"][b][k]["data"])
            for k in ["env", "agent"]}
    selected = ["base_scan_1500", "d1_scan_1500", "d2_scan_1500", "d3_scan_1500",
                "base_scan_1100", "d2_scan_1100", "d2s43_scan_1100",
                "base_scan_1500_turn", "d2_scan_1500_turn", "d3_scan_1500_turn1",
                "rw_scan_n16", "fbg2_sample", "fbg2_sample_m025", "act_base5999", "act_d2_1500"]
    for folder in selected:
        paths = sorted((args.diagnostics / folder).glob("*.json"))
        result["diagnostics"][folder] = [json_read(p) for p in paths]
        if not paths:
            result["diagnostics"][folder] = {"missing": True}
    zact = args.diagnostics.parent / "zact_1022/ex10/z_action.json"
    if zact.exists():
        result["EX10_sampling_diagnostic"] = json_read(zact)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "runs": len(result["runs"]),
                      "pairs": len(result["diffs"]), "diagnostic_groups": len(result["diagnostics"]),
                      "missing_groups": [k for k, v in result["diagnostics"].items() if isinstance(v, dict)],
                      "sha256": sha(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
