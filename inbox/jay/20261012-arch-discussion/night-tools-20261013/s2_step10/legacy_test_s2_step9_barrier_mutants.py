"""Normal-first functional mutations of short barrier and comparison gates."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
CASES=(
    ("arm_pair_guard","make_barrier_contract.py",
     'p.get("arm")!=arm or p.get("stage")!="short"',
     'False or p.get("stage")!="short"',"arm_mismatch"),
    ("checkpoint_boundary_guard","s2_compare_ab.py",
     'if not expected.issubset(hashes):raise ValueError("short_checkpoint_boundary_missing")',
     'if False:raise ValueError("short_checkpoint_boundary_missing")',
     "'checkpoint_000400.pt'"),
)


def invoke(folder,name,expected_error):
    env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1";env.pop("PYTHONPATH",None)
    code=("import sys;sys.path.insert(0,"+repr(str(folder))+");"
          "from test_s2_step9 import test;\n"
          "try:\n test()\n"
          "except Exception as ex:\n"
          " print('FAIL "+name+"' if str(ex)=="+repr(expected_error)+" else 'WRONG '+repr(ex));"
          " raise\n"
          "print('PASS "+name+"')")
    return subprocess.run([sys.executable,"-I","-B","-c",code],cwd=folder,env=env,
                          capture_output=True,text=True,timeout=90)


def test():
    with tempfile.TemporaryDirectory(prefix="s2_step9_mutants_") as td:
        for name,source,old,new,expected_error in CASES:
            normal=Path(td)/name/"normal";mutant=Path(td)/name/"mutant"
            normal.mkdir(parents=True);mutant.mkdir(parents=True)
            for path in list(HERE.glob("*.py"))+list(HERE.glob("request_short_*.json")):
                shutil.copyfile(path,normal/path.name)
                shutil.copyfile(path,mutant/path.name)
            target=mutant/source;value=target.read_text(encoding="utf-8")
            assert value.count(old)==1,(name,"mutation_anchor")
            target.write_text(value.replace(old,new,1),encoding="utf-8")
            n=invoke(normal,name,expected_error);m=invoke(mutant,name,expected_error)
            first=next((line for line in m.stdout.splitlines() if line.startswith("FAIL ")),None)
            want="FAIL "+name
            assert n.returncode==0 and "PASS "+name in n.stdout,(name,"normal",n.stdout,n.stderr)
            assert m.returncode!=0 and first==want,(name,"mutant",m.stdout,m.stderr,first,want)
            print(f"CAUGHT {name} first_FAIL={name} want={name}")


if __name__=="__main__":test()
