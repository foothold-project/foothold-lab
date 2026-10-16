"""Import the runtime closure from a clean temporary directory without Isaac startup."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from s2_train_contract import CODE,HERE,PYTHON


def test():
    with tempfile.TemporaryDirectory(prefix="s2_step5_closure_") as td:
        target=Path(td)
        for name in CODE:
            shutil.copyfile(HERE/name,target/name)
        env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1"
        env.pop("PYTHONPATH",None)
        run=subprocess.run([str(PYTHON),"-I","-B","-c",
            "import sys;sys.path.insert(0,"+repr(str(target))+");"
            "import s2_train_entry_17v,s2_train_launch,s2_train_manifest;print('CLEAN_IMPORT_OK')"],
            cwd=target,env=env,capture_output=True,text=True,timeout=30)
        assert run.returncode==0 and "CLEAN_IMPORT_OK" in run.stdout,(run.returncode,run.stdout,run.stderr)
    print(f"PASS clean_runtime_closure_import_{len(CODE)}")


if __name__=="__main__":test()
