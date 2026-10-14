"""A2 source mutations. Each identical known-answer probe runs normally first."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
CASES=[
    ("nan_height","s2_connect_check_17v.py",
     'if not np.isfinite(a["height"]).all():','if False:',
     "height_nan_height_nonfinite","test_s2_connect_a2"),
    ("fixed_one","s2_connect_check_17v.py",
     'hold("fixed_schedule",not np.array_equal(a["mode"],np.r_[np.zeros(16,dtype=int),',
     'hold("fixed_schedule",False and not np.array_equal(a["mode"],np.r_[np.zeros(16,dtype=int),',
     "fixed_one_fixed_schedule","test_s2_connect_a2"),
    ("root_100m","s2_connect_check_17v.py",
     'hold("root_sensor_transform",np.max(np.abs(a["root_pos_w"]+rotated-a["pos_w"]),initial=0)>',
     'hold("root_sensor_transform",False and np.max(np.abs(a["root_pos_w"]+rotated-a["pos_w"]),initial=0)>',
     "root_100m_root_sensor_transform","test_s2_connect_a2"),
    ("step90","s2_connect_check_17v.py",
     'hold("scene_hit_z",np.max(np.abs(hits[...,2][finite&oracle_finite&interior]-',
     'hold("scene_hit_z",False and np.max(np.abs(hits[...,2][finite&oracle_finite&interior]-',
     "marker_step90_scene_hit_z","test_s2_connect_a2"),
    ("disk1","s2_stage0_contract_a2.py",
     'if manifest["max_disk_bytes"]<16*1024*1024:','if False:',
     "disk1_rejected","test_s2_stage0_contract_a2"),
    ("raw_before_map","s2_connect_diag_17v.py",
     'if journal is not None:journal.raw(step,raw)',
     'if False:journal.raw(step,raw)',
     "raw_row_before_map_error","test_s2_capture_journal_a2"),
    ("torch_bus","s2_device_binding_a2.py",
     'if actual_bus!=normalize_bus(expected_bus):raise DeviceHold("torch_physical_bus_mismatch")',
     'if False:raise DeviceHold("torch_physical_bus_mismatch")',
     "torch_bus_mismatch_rejected","test_s2_device_binding_a2"),
]

def run(out:Path):
    out.mkdir(parents=True,exist_ok=False)
    results=[]
    for name,source,old,new,want,module in CASES:
        case=out/name
        normal=case/"normal";mutant=case/"mutant"
        normal.mkdir(parents=True);mutant.mkdir()
        original=(HERE/source).read_text(encoding="utf-8")
        if original.count(old)!=1:raise AssertionError("mutation anchor "+name)
        (normal/source).write_text(original,encoding="utf-8")
        (mutant/source).write_text(original.replace(old,new,1),encoding="utf-8")
        logs=[]
        for kind,folder in (("normal",normal),("mutant",mutant)):
            env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1"
            env["PYTHONPATH"]=os.pathsep.join((str(folder),str(HERE)))
            p=subprocess.run([sys.executable,"-B","-c",f"from {module} import main;main()"],
                             cwd=folder,env=env,text=True,stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,timeout=120)
            (case/(kind+".log")).write_text(p.stdout,encoding="utf-8")
            logs.append((p.returncode,p.stdout))
        first_fail=next((line for line in logs[1][1].splitlines() if line.startswith("FAIL ")),None)
        caught=(logs[0][0]==0 and "PASS "+want in logs[0][1] and
                logs[1][0]!=0 and first_fail=="FAIL "+want)
        item={"name":name,"source":source,"want":want,
              "normal_exit":logs[0][0],"mutant_exit":logs[1][0],
              "first_fail":first_fail,"result":"CAUGHT" if caught else "NOT_CAUGHT"}
        results.append(item)
        print(item["result"],name,first_fail,flush=True)
    summary={"cases":results,"caught":sum(i["result"]=="CAUGHT" for i in results),
             "total":len(results)}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    if summary["caught"]!=summary["total"]:raise AssertionError("A2 mutant set incomplete")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True,type=Path)
    run(p.parse_args().out)
