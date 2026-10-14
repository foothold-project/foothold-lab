"""Write each raw control-step row before map validation; preserve failure evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time

import numpy as np


def atomic_json(path:Path,value):
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(value,sort_keys=True,indent=2,default=str),encoding="utf-8")
    os.replace(tmp,path)


class CaptureJournal:
    def __init__(self,root:Path,launch:dict):
        self.root=root
        self.root.mkdir(parents=True,exist_ok=False)
        self.rows=root/"raw_rows";self.rows.mkdir()
        self.started_epoch=time.time();self.last_valid_step=-1;self.partial_rows=0
        atomic_json(root/"launch.json",{**launch,"started_epoch":self.started_epoch,
                                        "state":"STARTED","partial_rows":0})

    def raw(self,step:int,row:dict):
        path=self.rows/f"row_{step:03d}.npz"
        if path.exists():raise ValueError("raw row reused")
        tmp=path.with_suffix(".tmp")
        with tmp.open("wb") as stream:
            np.savez_compressed(stream,**{k:np.asarray(v) for k,v in row.items()})
        os.replace(tmp,path)
        self.partial_rows+=1
        atomic_json(self.root/"progress.json",{"last_raw_step":step,"last_valid_step":self.last_valid_step,
                                               "partial_rows":self.partial_rows,"epoch":time.time()})

    def valid(self,step:int):
        self.last_valid_step=step
        atomic_json(self.root/"progress.json",{"last_raw_step":step,"last_valid_step":step,
                                               "partial_rows":self.partial_rows,"epoch":time.time()})

    def derived(self,step:int,row:dict):
        path=self.rows/f"mapped_{step:03d}.npz"
        tmp=path.with_suffix(".tmp")
        with tmp.open("wb") as stream:
            np.savez_compressed(stream,**{k:np.asarray(v) for k,v in row.items()})
        os.replace(tmp,path)

    def stage_failure(self,step:int,stage:str,error:str,emergency=None):
        """17x: preserve which stage failed at which step, and the emergency raw row when possible."""
        note={"step":step,"stage":stage,"error":error,"emergency_raw":"not_attempted","epoch":time.time()}
        if emergency is not None and step>=0:
            if (self.rows/f"row_{step:03d}.npz").exists():
                note["emergency_raw"]="already_saved"
            else:
                try:
                    self.raw(step,emergency(step));note["emergency_raw"]="saved"
                except BaseException as ex:
                    note["emergency_raw"]="failed";note["emergency_error"]=repr(ex)
        atomic_json(self.root/"stage_failure.json",note)

    def fail(self,error:str,traceback_text:str,cleanup:dict):
        atomic_json(self.root/"failure.json",{"error":error,"traceback":traceback_text,
                                              "last_valid_step":self.last_valid_step,
                                              "partial_rows":self.partial_rows,"cleanup":cleanup,
                                              "ended_epoch":time.time(),"verdict":"HOLD_INFORMATION_ONLY"})

    def complete(self,*,captured:int,cleanup:dict):
        atomic_json(self.root/"completion.json",{"captured_steps":captured,"partial_rows":self.partial_rows,
                                                 "last_valid_step":self.last_valid_step,"cleanup":cleanup,
                                                 "ended_epoch":time.time(),"verdict":"HOLD_INFORMATION_ONLY"})
