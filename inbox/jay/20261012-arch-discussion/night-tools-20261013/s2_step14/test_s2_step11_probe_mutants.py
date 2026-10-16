"""A mutant is CAUGHT only when its first FAIL equals its declared want."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
PY=Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")
BASE=(HERE/"s2_physx_probe_diag.py").read_text(encoding="utf-8")
MUTATIONS=(
    ("variant_missing",'            ("carb_float3_d80", "carb.Float3", 80.0))',
     '            )',"variants"),
    ("raw_rewrite",'"raw_repr": repr(answer)',
     '"raw_repr": repr(str(answer))',"raw_repr"),
    ("double_offset",'float(origin[2])+0.4',
     'float(origin[2])+20.4',"start_z"),
    ("no_forces",'"foot_contact_forces_w":forces.tolist()',
     '"foot_contact_forces_w":[]',"foot_forces"),
)


def run():
    with tempfile.TemporaryDirectory(prefix="s2_11_probe_mut_") as td:
        root=Path(td)
        (root/"test_s2_step11_probe.py").write_bytes((HERE/"test_s2_step11_probe.py").read_bytes())
        env=dict(os.environ,CUDA_VISIBLE_DEVICES="-1",PYTHONDONTWRITEBYTECODE="1")
        env.pop("PYTHONPATH",None)
        code=("import runpy,sys;from pathlib import Path;p=Path(sys.argv[1]);"
              "sys.path.insert(0,str(p.parent));runpy.run_path(str(p),run_name='__main__')")
        for name,old,new,want in MUTATIONS:
            assert BASE.count(old)==1,name
            (root/"s2_physx_probe_diag.py").write_text(BASE.replace(old,new),encoding="utf-8")
            proc=subprocess.run([str(PY),"-I","-B","-c",code,
                                 str(root/"test_s2_step11_probe.py")],cwd=root,env=env,
                                text=True,capture_output=True,timeout=90)
            passed=[x.removeprefix("PASS ") for x in proc.stdout.splitlines() if x.startswith("PASS ")]
            order=["steps","variants","raw_repr","start_z","foot_forces","raycaster_miss","record_hash"]
            first=order[len(passed)] if len(passed)<len(order) else None
            assert proc.returncode!=0 and first==want,(name,first,want,proc.stdout,proc.stderr)
            print(f"CAUGHT {name} first_FAIL={first} want={want}")


if __name__=="__main__":run()
