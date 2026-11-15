"""Normal-first CPU source mutations for the first no-extension short path."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
CASES=(
    ("output_isolation","s2_train_entry_17v.py",
     'def prepare_short_root(root, *, cpu_dry):\n    root=Path(root).resolve()\n    if root.exists():\n        if cpu_dry or {p.name for p in root.iterdir()}!={"usd"}:',
     'def prepare_short_root(root, *, cpu_dry):\n    root=Path(root).resolve()\n    if root.exists():\n        if cpu_dry or False:',
     "test_s2_step9_single.py","PASS short_usd_child_output_allowed"),
    ("exact_2000","s2_train_contract.py",
     'if p.get("updates")!=2000 or p.get("checkpoint_interval")!=200:',
     'if p.get("updates")!=2001 or p.get("checkpoint_interval")!=200:',
     "test_s2_step9_single.py","PASS requests_single_2000_no_grant"),
    ("sequential_cleanup","s2_train_contract.py",
     'prior.get("family_cleanup_confirmed") is not True',
     'False',"test_s2_step9_single.py","PASS reject_A_alive"),
    ("usd_refs","s2_train_launch.py",
     'refs!=[generated]', 'False',"test_s2_step9_single.py","PASS short_usd_reference_proof"),
    ("per_update_log","s2_train_entry_17v.py",
     'log.write(json.dumps(line,sort_keys=True,default=str)+"\\n");log.flush()',
     'pass',"test_s2_step9_single.py","PASS reject_foreign_output"),
    ("freeze_violation","s2_train_entry_17v.py",
     'record.get("frozen") is not True',
     'False',"test_s2_step9_single.py","PASS short_sensor_fault_preserves_first_two_and_failure"),
    ("nonfinite_loss","s2_train_entry_17v.py",
     '("surrogate","value","entropy","kl","loss","gradient_norm_min",',
     '("surrogate","value","entropy","kl","gradient_norm_min",',
     "test_s2_step9_single.py","PASS short_freeze_violation_hold"),
    ("every_200_checkpoint","s2_train_entry_17v.py",
     'if index%200==0:runner.save(root/f"checkpoint_{index:06d}.pt")',
     'if index==200:runner.save(root/f"checkpoint_{index:06d}.pt")',
     "test_s2_step9_single.py","PASS reject_foreign_output"),
    ("release_final_receipt","s2_train_launch.py",
     'if (m["plan"]["stage"]=="plumbing" or m["plan"].get("extension_disabled") is True) and receipt is not None:',
     'if m["plan"]["stage"]=="plumbing" and receipt is not None:',
     "test_s2_step9_cleanup.py",None),
    ("parent_immutable","s2_train_launch.py",
     'if receipt.get("parent_sha256_before")!=receipt.get("parent_sha256_after"):',
     'if False:',"test_s2_step9_cleanup.py",
     "PASS short_release_failure_final_receipt_hold"),
    ("effect_claim_guard","s2_compare_ab.py",
     'if any(loaded[arm][0].get("map_contract_verified") is not True for arm in ("A","B")):',
     'if False:',"test_s2_step9_compare_single.py",None),
)


def run(folder,test,label):
    env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1";env.pop("PYTHONPATH",None)
    path=folder/test
    code=("import sys,runpy;sys.path.insert(0,"+repr(str(folder))+ ")\n"
          "try:\n runpy.run_path("+repr(str(path))+",run_name='__main__')\n"
          "except Exception:\n print('FAIL "+label+"',flush=True);raise")
    return subprocess.run([sys.executable,"-I","-B","-c",code],cwd=folder,env=env,
                          capture_output=True,text=True,timeout=120)


def test():
    with tempfile.TemporaryDirectory(prefix="s2_step9_single_mutants_") as td:
        normals={}
        for label,source,old,new,test_name,last_good in CASES:
            normal=Path(td)/label/"normal";mutant=Path(td)/label/"mutant"
            normal.mkdir(parents=True);mutant.mkdir(parents=True)
            for file in list(HERE.glob("*.py"))+list(HERE.glob("request_short_*.json")):
                shutil.copyfile(file,normal/file.name);shutil.copyfile(file,mutant/file.name)
            path=mutant/source;content=path.read_text(encoding="utf-8")
            assert content.count(old)==1,(label,"anchor")
            path.write_text(content.replace(old,new,1),encoding="utf-8")
            if test_name not in normals:
                normals[test_name]=run(normal,test_name,label)
            n=normals[test_name]
            m=run(mutant,test_name,label)
            assert n.returncode==0,(label,"normal",n.stdout,n.stderr)
            assert m.returncode!=0,(label,"mutant",m.stdout,m.stderr)
            passes=[line for line in m.stdout.splitlines() if line.startswith("PASS ")]
            assert (passes[-1] if passes else None)==last_good,(label,"first",passes[-1] if passes else None,last_good)
            first=next((line for line in m.stdout.splitlines() if line.startswith("FAIL ")),None)
            assert first=="FAIL "+label,(label,"first_FAIL",first)
            failure_type="KeyError" if label=="release_final_receipt" else "AssertionError"
            assert failure_type in m.stderr,(label,"failure_type",m.stderr)
            print(f"CAUGHT {label} first_FAIL={label} want={label}")


if __name__=="__main__":test()
