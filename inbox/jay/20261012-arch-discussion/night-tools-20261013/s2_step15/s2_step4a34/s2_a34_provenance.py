"""CPU-verifiable asset and USD evidence for the A3.4 diagnostic."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


class ProvenanceHold(RuntimeError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def closure_sha256(snapshot):
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(",",":"),
                                     allow_nan=False).encode()).hexdigest()


def asset_snapshot(urdf, cfg_source, converter_source, env_cfg_source=None):
    urdf = Path(urdf).resolve(strict=True)
    root = ET.parse(urdf).getroot()
    refs = sorted({node.attrib["filename"] for node in root.iter("mesh")})
    if not refs:
        raise ProvenanceHold("mesh_reference_missing")
    meshes = []
    for ref in refs:
        if not ref.startswith("package://go2/meshes/"):
            raise ProvenanceHold("mesh_reference_unknown:" + ref)
        path = urdf.parents[1] / "meshes" / ref.split("/meshes/", 1)[1]
        if not path.is_file():
            raise ProvenanceHold("mesh_file_missing:" + ref)
        meshes.append({"reference": ref, "path": str(path.resolve()), "sha256": sha(path)})
    sources = {}
    if env_cfg_source is None:
        env_cfg_source="C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab/tasks/go2/env_cfg.py"
    for name, path in (("robotlab_asset_cfg", cfg_source),
                       ("robotlab_env_cfg",env_cfg_source), ("converter", converter_source)):
        path = Path(path).resolve(strict=True)
        sources[name] = {"path": str(path), "sha256": sha(path)}
    return {"urdf": {"path": str(urdf), "sha256": sha(urdf)},
            "meshes": meshes, "sources": sources}


def assert_asset_unchanged(before, after, expected_urdf_sha):
    if before != after or before["urdf"]["sha256"] != expected_urdf_sha:
        raise ProvenanceHold("asset_dependency_changed")
    return True


def usd_evidence(usd_root, asset_path, robot_refs, *, environment_created):
    root = Path(usd_root).resolve(strict=True)
    state = json.loads((root / "isolate_state.json").read_text(encoding="utf-8"))
    assigned = [json.loads(line) for line in (root / "assigned.jsonl").read_text(encoding="utf-8").splitlines() if line]
    if (state.get("version") != "v3" or state.get("expect_conversions") != "1" or
        state.get("conversions") != 1 or state.get("blocked") != [] or
        state.get("warnings") != [] or Path(state.get("root", "")).resolve() != root):
        raise ProvenanceHold("usd_isolation_state")
    if len(assigned) != 1 or assigned[0].get("kind") not in ("assigned", "explicit_inside"):
        raise ProvenanceHold("usd_assignment_count_or_kind")
    row = assigned[0]
    if Path(row.get("asset_path", "")).resolve() != Path(asset_path).resolve():
        raise ProvenanceHold("usd_input_asset")
    assigned_dir = Path(row.get("usd_dir", "")).resolve()
    if root not in assigned_dir.parents:
        raise ProvenanceHold("usd_assignment_outside")
    output = sorted(p for p in assigned_dir.rglob("*.usd*") if p.is_file())
    if not output:
        raise ProvenanceHold("usd_output_missing")
    if not environment_created or not robot_refs:
        raise ProvenanceHold("usd_environment_or_reference_missing")
    refs = []
    for ref in robot_refs:
        p = Path(ref).resolve()
        if root not in p.parents or not p.is_file():
            raise ProvenanceHold("usd_robot_reference_outside_or_missing")
        refs.append({"path": str(p), "sha256": sha(p)})
    return {"state_sha256": sha(root / "isolate_state.json"),
            "assigned_sha256": sha(root / "assigned.jsonl"),
            "assigned": row, "outputs": [{"path": str(p), "sha256": sha(p)} for p in output],
            "robot_references": refs, "environment_created": True,
            "conversion_counter_meaning": "constructor_entries_not_success"}
