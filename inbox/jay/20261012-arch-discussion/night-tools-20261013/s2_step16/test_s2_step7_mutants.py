"""Functional CPU mutants for the new 17ad fail-closed boundaries."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
PROBES={
"uuid_mismatch":'''from types import SimpleNamespace as S
from s2_device_binding_a2 import inspect_child_device,DeviceHold
c=S(is_available=lambda:True,device_count=lambda:1,current_device=lambda:0,get_device_properties=lambda i:S(uuid="GPU-1234",name="fake"))
s=S(get=lambda k:0)
ok=False
try:inspect_child_device("GPU-9999",S(device_id=0),torch_module=S(cuda=c),settings=s)
except DeviceHold as e:ok=str(e)=="torch_uuid_mismatch"
print(("PASS" if ok else "FAIL")+" uuid_mismatch");assert ok''',
"kit_setting_missing":'''from types import SimpleNamespace as S
from s2_device_binding_a2 import inspect_child_device,DeviceHold
c=S(is_available=lambda:True,device_count=lambda:1,current_device=lambda:0,get_device_properties=lambda i:S(uuid="GPU-1234",name="fake"))
ok=False
try:inspect_child_device("GPU-1234",S(device_id=0),torch_module=S(cuda=c),settings=S(get=lambda k:None))
except DeviceHold as e:ok=str(e)=="Kit_renderer_physics_unobserved"
print(("PASS" if ok else "FAIL")+" kit_setting_missing");assert ok''',
"mount_nonzero":'''import torch
from types import SimpleNamespace as S
from s2_train_entry_17v import checked_mount
pos=torch.zeros(2,3);pos[:,0]=.1;q=torch.zeros(2,4);q[:,0]=1
ok=False
try:checked_mount(S(_offset=(pos,q)))
except ValueError as e:ok="sensor_mount_unverified" in str(e)
print(("PASS" if ok else "FAIL")+" mount_nonzero");assert ok''',
"usd_reference":'''import json,tempfile
from pathlib import Path
from s2_train_launch import usd_evidence,TrainHold
with tempfile.TemporaryDirectory() as td:
 r=Path(td)/"out"/"usd"; d=r/"IsaacLab"/"usd_20261015_000000_1";d.mkdir(parents=True)
 (d/"robot.usd").write_bytes(b"x")
 (r/"isolate_state.json").write_text(json.dumps(dict(version="v3",root=str(r),expect_conversions="1",conversions=1,blocked=[])))
 (r/"assigned.jsonl").write_text(json.dumps(dict(kind="assigned",usd_dir=str(d),asset_path="robot.urdf"))+"\\n")
 ok=False
 try:usd_evidence(dict(usd_root=str(r)),dict(usd_reference_paths=[]))
 except TrainHold as e:ok=str(e)=="usd_actual_reference_mismatch"
 print(("PASS" if ok else "FAIL")+" usd_reference");assert ok''',
}
CASES=(
 ("uuid_mismatch","s2_device_binding_a2.py",
  'if normalize_uuid(raw)!=normalize_uuid(expected_uuid):raise DeviceHold("torch_uuid_mismatch")',
  'if False:raise DeviceHold("torch_uuid_mismatch")'),
 ("kit_setting_missing","s2_device_binding_a2.py",
  'if any(key not in observed for key in ("/renderer/activeGpu","/physics/cudaDevice")):',
  'if False:'),
 ("mount_nonzero","s2_train_entry_17v.py",
  'if value!=(0.,0.,0.):raise ValueError("sensor mount nonzero")',
  'if False:raise ValueError("sensor mount nonzero")'),
 ("usd_reference","s2_train_launch.py",
  'if not generated.is_file() or refs!=[generated]:',
  'if False:'),
)

def invoke(folder,script):
    env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1";env.pop("PYTHONPATH",None)
    code=f"import sys;sys.path.insert(0,{str(folder)!r});exec({script!r})"
    return subprocess.run([sys.executable,"-I","-B","-c",code],cwd=folder,env=env,
                          capture_output=True,text=True,timeout=60)

def test():
    with tempfile.TemporaryDirectory(prefix="s2_step7_mutants_") as td:
        base=Path(td)
        for name,source,old,new in CASES:
            normal=base/name/"normal";mutant=base/name/"mutant"
            normal.mkdir(parents=True);mutant.mkdir(parents=True)
            for path in HERE.glob("*.py"):
                shutil.copyfile(path,normal/path.name)
                shutil.copyfile(path,mutant/path.name)
            target=mutant/source;text=target.read_text(encoding="utf-8")
            assert text.count(old)==1,(name,"mutation_anchor")
            target.write_text(text.replace(old,new,1),encoding="utf-8")
            n=invoke(normal,PROBES[name]);m=invoke(mutant,PROBES[name])
            first=next((line for line in m.stdout.splitlines() if line.startswith("FAIL ")),None)
            want="FAIL "+name
            assert n.returncode==0 and "PASS "+name in n.stdout,(name,"normal",n.stdout,n.stderr)
            assert m.returncode!=0 and first==want,(name,"mutant",m.stdout,m.stderr,first,want)
            print(f"CAUGHT {name} first_FAIL={name} want={name}")

if __name__=="__main__":test()
