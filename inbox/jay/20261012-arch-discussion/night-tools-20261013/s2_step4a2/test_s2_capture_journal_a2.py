"""A failed map keeps the first raw row, boundary row and error receipt."""
import json
from pathlib import Path
import tempfile

import numpy as np

from s2_capture_journal_a2 import CaptureJournal
from s2_connect_diag_17v import capture


class Provider:
    num_envs=8
    def __init__(self):self.step=-1
    def reset(self):pass
    def translate(self):pass
    def reset_new_height_position(self):pass
    def change_yaw(self):pass
    def step_zero(self):self.step+=1
    def sample_raw(self,step):return {"step":np.int64(step),"raw_hits":np.full((8,187,3),float(step))}
    def derive_map(self,row):
        if self.step==64:raise ValueError("synthetic bad ray")
        row["height"]=np.zeros((8,187));row["mask"]=np.ones((8,187))
        return row


def check(name,good):
    print(("PASS" if good else "FAIL")+" "+name,flush=True)
    assert good,name


def main():
    root=Path(tempfile.mkdtemp(prefix="s2_a2_journal_"))/"capture"
    journal=CaptureJournal(root,{"attempt":"fixture","argv":["fake"],"gpu_uuid":"GPU-fixture"})
    try:capture(Provider(),steps=256,journal=journal)
    except ValueError as ex:
        journal.fail(str(ex),"synthetic traceback",{"provider_closed":True})
    else:raise AssertionError("bad map did not fail")
    progress=json.loads((root/"progress.json").read_text())
    failure=json.loads((root/"failure.json").read_text())
    check("raw_row_before_map_error",(root/"raw_rows/row_064.npz").is_file() and
          not (root/"raw_rows/mapped_064.npz").exists())
    check("boundary_rows_kept",all((root/f"raw_rows/row_{i:03d}.npz").is_file() for i in (0,63,64)))
    check("partial_not_complete",progress["partial_rows"]==65 and failure["last_valid_step"]==63 and
          not (root/"completion.json").exists())
    check("start_before_failure",json.loads((root/"launch.json").read_text())["started_epoch"]<failure["ended_epoch"])

if __name__=="__main__":main()
