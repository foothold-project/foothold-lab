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
    # 17x: a failure in the control-step stage (not just map derivation) keeps the earlier rows and the failing stage.
    class StepFails(Provider):
        def step_zero(self):
            super().step_zero()
            if self.step==64:raise RuntimeError("synthetic hook error in step_zero")
        def emergency_raw(self,step):return {"step":np.int64(step),"raw_hits":np.full((8,187,3),-1.0)}
    root2=Path(tempfile.mkdtemp(prefix="s2_a2_journal2_"))/"capture"
    journal2=CaptureJournal(root2,{"attempt":"fixture2","argv":["fake"],"gpu_uuid":"GPU-fixture"})
    try:capture(StepFails(),steps=256,journal=journal2)
    except RuntimeError:pass
    else:raise AssertionError("step failure did not propagate")
    check("step_failure_note_exists",(root2/"stage_failure.json").is_file())
    note=json.loads((root2/"stage_failure.json").read_text())
    check("step_stage_failure_keeps_rows_and_stage",all((root2/f"raw_rows/row_{i:03d}.npz").is_file() for i in (0,63)) and
          note["stage"]=="step_zero" and note["step"]==64 and note["emergency_raw"]=="saved" and
          (root2/"raw_rows/row_064.npz").is_file())
    class EmergencyFails(StepFails):
        def emergency_raw(self,step):raise RuntimeError("emergency accessor down")
    root3=Path(tempfile.mkdtemp(prefix="s2_a2_journal3_"))/"capture"
    journal3=CaptureJournal(root3,{"attempt":"fixture3","argv":["fake"],"gpu_uuid":"GPU-fixture"})
    try:capture(EmergencyFails(),steps=256,journal=journal3)
    except RuntimeError:pass
    note=json.loads((root3/"stage_failure.json").read_text())
    check("emergency_failure_recorded",note["emergency_raw"]=="failed" and "emergency accessor down" in note["emergency_error"]
          and not (root3/"raw_rows/row_064.npz").exists())
    # 17x: per-row ray_index copies collapse to the checker's single (187,) vector; drift is rejected.
    class Ray(Provider):
        def derive_map(self,row):
            row["ray_index"]=np.arange(187) if self.step<100 else np.arange(187)[::-1] if self.step==100 else np.arange(187)
            row["height"]=np.zeros((8,187));row["mask"]=np.ones((8,187))
            return row
    class RayOk(Provider):
        def derive_map(self,row):
            row["ray_index"]=np.arange(187);row["height"]=np.zeros((8,187));row["mask"]=np.ones((8,187))
            return row
    got=capture(RayOk(),steps=256)
    check("ray_index_collapsed_to_checker_shape",got["ray_index"].shape==(187,))
    try:capture(Ray(),steps=256)
    except ValueError as ex:check("ray_index_drift_rejected","ray_index changed" in str(ex))
    else:check("ray_index_drift_rejected",False)

if __name__=="__main__":main()
