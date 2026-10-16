"""Private-hook generation observer CPU fake, including partial update and stale bytes."""
from types import SimpleNamespace
from pathlib import Path
import hashlib
import torch
from s2_sensor_tracker_17v import SensorUpdateTracker
from s2_env_adapter_17v import AdapterFault


class FakeSensor:
    def __init__(self):
        self.cfg=SimpleNamespace()
        self.step=0
        self.pos=torch.zeros(2,3)
        self.hits=torch.zeros(2,187,3)
        self.hits[...,0]=torch.arange(187).remainder(17)*.1-.8
        self.hits[...,1]=torch.arange(187).div(17,rounding_mode="floor")*.1-.5
        self._data=SimpleNamespace(pos_w=self.pos,ray_hits_w=self.hits)
        self._timestamp=torch.zeros(2)
        self.pose=torch.zeros(2,7);self.pose[:,0]=1
    def _update_buffers_impl(self,env_ids):
        for i in env_ids:
            self.pos[i,2]=self.step
            self._timestamp[i]=self.step
    @property
    def data(self):
        return SimpleNamespace(pos_w=self.pos,ray_hits_w=self.hits)


def main():
    s=FakeSensor();source=Path(__file__).resolve()
    t=SensorUpdateTracker(s,num_envs=2,step_getter=lambda:s.step,
        root_pose_getter=lambda:s.pose,expected_hook_path=source,
        expected_hook_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    s._update_buffers_impl([0,1])
    frozen,r=t.snapshot()
    assert r["step"]==0 and r["generation"]==1 and frozen.data.pos_w.shape==(2,3)
    print("PASS source_generation_and_clone")
    s.step=1;s._update_buffers_impl([0])
    try:t.snapshot()
    except AdapterFault as ex: assert "not every" in str(ex)
    else:raise AssertionError("partial")
    print("PASS partial_env_update_rejected")
    s._update_buffers_impl([1]);_,r2=t.snapshot()
    assert r2["generation"]==2 and r2["raw_sha256"]!=r["raw_sha256"]
    print("PASS same_xy_height_change_observed")
    t.detach()
    try:t.snapshot()
    except AdapterFault:pass
    else:raise AssertionError("detached")
    print("PASS detached_tracker_rejected")

if __name__=="__main__":main()
