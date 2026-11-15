"""Source-only checks for the unlaunched Kit adapter and untouched A3.3 map."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
A33=HERE/"a33"
MAP_HASHES={
    "s2_env_adapter_17v.py":"ebac0f1e2225959da1cacf0fc63aeef6a441e9fd5a08c0d11b7a899fdec496a7",
    "s2_known_scene_a2.py":"9a4a38bfbcc530e8e8f28b7ecbf1c2f4ecaeae3dcd9b217ae8fe73f1bf7aac07",
    "s2_map_obs.py":"cf05528619052c73facba9268cc8823156f3106d9ce65ddacf16be30961f348b",
    "s2_runner_17v.py":"7d1158df2923dffe72436f43b5e4673167ced611afec4912ccaef782035b4ddc",
    "s2_scene_answer_a2.json":"b3a9c5be54e4e16856249c2426d39640f450b18778e24e979fc1a1f1d18a4296",
    "s2_sensor_tracker_17v.py":"5bca01b9f4755299d45d1c47e98d22aa06212243fc796c9e36da25c4c654fe02",
}


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    for name,want in MAP_HASHES.items():
        assert digest(A33/name)==want,name
    lines=(A33/"SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines)==50
    for line in lines:
        want,name=line.split("  ",1)
        assert digest(A33/name)==want,name
    print("PASS a33_map_bytes")
    source=(A33/"s2_connect_diag_17v.py").read_text(encoding="utf-8")
    tree=ast.parse(source)
    provider=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="IsaacProvider")
    assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="configure_env"
               for n in ast.walk(provider))
    assert any(isinstance(n,ast.Attribute) and n.attr=="step_zero" for n in ast.walk(
        ast.parse((HERE/"s2_physx_probe_live.py").read_text(encoding="utf-8"))))
    assert "provider.reset()" in (HERE/"s2_physx_probe_live.py").read_text(encoding="utf-8")
    assert "[0,0,1,1,2,2,3,3]" in (HERE/"s2_physx_probe_live.py").read_text(encoding="utf-8")
    print("PASS a33_provider_reuse")
    live=ast.parse((HERE/"s2_physx_probe_live.py").read_text(encoding="utf-8"))
    top=[n for n in live.body if isinstance(n,(ast.Import,ast.ImportFrom))]
    assert not any((alias.name.startswith(("isaaclab","omni","carb")) for n in top for alias in n.names))
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="AppLauncher"
                   for n in ast.walk(live))
    print("PASS no_kit_import_or_launch")
    owner=(A33/"s2_zero_supervisor.py").read_text(encoding="utf-8")
    assert 's2_connect_diag_17v.py' in owner and '"--steps":"256"' in owner
    assert (A33/"s2_stage0_contract_a2.py").read_text(encoding="utf-8").count('"steps"]!=256')==1
    print("PASS supervisor_contract_block_identified")


if __name__=="__main__":run()
