"""Normal-first isolated mutations for 17ae boundaries."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
PROBES={
    "optimizer_device_normalization":'''import inspect,s2_plumbing as p
s=inspect.getsource(p)
ok="left.detach().cpu(),right.detach().cpu()" in s
print(("PASS" if ok else "FAIL")+" optimizer_device_normalization");assert ok''',
    "optimizer_cpu_load":'''import inspect,s2_plumbing as p
s=inspect.getsource(p.roundtrip_policy)
ok='map_location="cpu"' in s and s.index('map_location="cpu"')<s.index('if not _same(state["optimizer"]')
print(("PASS" if ok else "FAIL")+" optimizer_cpu_load");assert ok''',
    "capture_answer_bypass":'''import torch
from test_s2_step8 import capture_fixture,packet_with_hits
from s2_plumbing import verify_synthetic_capture_packet,PlumbingHold
packet=capture_fixture("B").capture_packet_after_sensor_update()
hits=packet.sensor.data.ray_hits_w.clone();hits[:,1,2]+=.1
altered=packet_with_hits(packet,hits)
ok=False
try:verify_synthetic_capture_packet(altered,arm="B",geometry_tolerance_m=.02)
except PlumbingHold as e:ok=str(e)=="synthetic_capture_map_answer_mismatch"
print(("PASS" if ok else "FAIL")+" capture_answer_bypass");assert ok''',
}
CASES=(
    ("optimizer_device_normalization",
     'return torch.equal(left.detach().cpu(),right.detach().cpu())',
     'return torch.equal(left,right)'),
    ("optimizer_cpu_load",'state=torch.load(checkpoint,map_location="cpu",weights_only=False)',
     'state=torch.load(checkpoint,map_location=device,weights_only=False)'),
    ("capture_answer_bypass",
     'if faults.total or not torch.equal(b,expected):',
     'if False:'),
)


def invoke(folder,probe):
    env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1";env.pop("PYTHONPATH",None)
    code=f"import sys;sys.path.insert(0,{str(folder)!r});exec({probe!r})"
    return subprocess.run([sys.executable,"-I","-B","-c",code],cwd=folder,env=env,
                          capture_output=True,text=True,timeout=60)


def test():
    with tempfile.TemporaryDirectory(prefix="s2_step8_mutants_") as td:
        for name,old,new in CASES:
            normal=Path(td)/name/"normal";mutant=Path(td)/name/"mutant"
            normal.mkdir(parents=True);mutant.mkdir(parents=True)
            for source in HERE.glob("*.py"):
                shutil.copyfile(source,normal/source.name)
                shutil.copyfile(source,mutant/source.name)
            target=mutant/"s2_plumbing.py";source=target.read_text(encoding="utf-8")
            assert source.count(old)==1,(name,"anchor")
            source=source.replace(old,new,1)
            if name=="capture_answer_bypass":
                extra='if not torch.equal(actual,arm_expected):'
                assert source.count(extra)==1
                source=source.replace(extra,'if False:',1)
            target.write_text(source,encoding="utf-8")
            n=invoke(normal,PROBES[name]);m=invoke(mutant,PROBES[name])
            first=next((line for line in m.stdout.splitlines() if line.startswith("FAIL ")),None)
            want="FAIL "+name
            assert n.returncode==0 and "PASS "+name in n.stdout,(name,"normal",n.stdout,n.stderr)
            assert m.returncode!=0 and first==want,(name,"mutant",m.stdout,m.stderr,first,want)
            print(f"CAUGHT {name} first_FAIL={name} want={name}")


if __name__=="__main__":test()
