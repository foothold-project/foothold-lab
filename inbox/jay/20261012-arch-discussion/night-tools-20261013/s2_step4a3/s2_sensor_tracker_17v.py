"""Freeze RayCaster bytes and pose at private update completion; verify before reading."""
from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
from types import SimpleNamespace

from s2_env_adapter_17v import AdapterFault
from s2_packet_17v import raw_sha


def tensor_sha(value):
    t=value.detach().cpu().contiguous()
    return hashlib.sha256(str(tuple(t.shape)).encode()+t.numpy().tobytes()).hexdigest()


class SensorUpdateTracker:
    def __init__(self,sensor,*,num_envs:int,step_getter,root_pose_getter,
                 expected_hook_path,expected_hook_sha256):
        if type(num_envs) is not int or num_envs<=0 or not callable(step_getter) or not callable(root_pose_getter):
            raise ValueError("tracker arguments")
        original=getattr(sensor,"_update_buffers_impl",None)
        source=inspect.getsourcefile(original.__func__ if hasattr(original,"__func__") else original)
        if not callable(original) or not source:raise AdapterFault("RayCaster update hook missing")
        path=Path(source).resolve();digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if path!=Path(expected_hook_path).resolve() or digest!=expected_hook_sha256:
            raise AdapterFault("RayCaster hook source binding mismatch")
        if not hasattr(sensor,"_data") or not hasattr(sensor,"_timestamp"):
            raise AdapterFault("RayCaster private buffers unavailable")
        self.sensor,self.original,self.step_getter,self.root_pose_getter=sensor,original,step_getter,root_pose_getter
        self.num_envs=num_envs;self.source_path=str(path);self.source_sha256=digest
        self.generations=[0]*num_envs;self.last_steps=[-1]*num_envs
        self.raw_hashes=[None]*num_envs;self.pose_hashes=[None]*num_envs;self.timestamps=[None]*num_envs
        self.installed=True
        def tracked(env_ids):
            result=original(env_ids)
            ids=[int(x) for x in env_ids];step=int(step_getter())
            pose=root_pose_getter().detach().clone();data=sensor._data
            for i in ids:
                if i<0 or i>=num_envs:raise AdapterFault("sensor update env id out of range")
                self.generations[i]+=1;self.last_steps[i]=step
                self.raw_hashes[i]=raw_sha(data.pos_w[i:i+1],data.ray_hits_w[i:i+1])
                self.pose_hashes[i]=tensor_sha(pose[i:i+1])
                self.timestamps[i]=float(sensor._timestamp[i])
            return result
        sensor._update_buffers_impl=tracked;self.tracked=tracked

    def snapshot(self):
        if not self.installed or self.sensor._update_buffers_impl is not self.tracked:
            raise AdapterFault("RayCaster hook detached or replaced")
        if hashlib.sha256(Path(self.source_path).read_bytes()).hexdigest()!=self.source_sha256:
            raise AdapterFault("RayCaster source changed")
        data=self.sensor.data
        step=int(self.step_getter())
        if any(x!=step for x in self.last_steps) or min(self.generations)<=0:
            raise AdapterFault("not every RayCaster env updated for this control step")
        pos=data.pos_w.detach().clone();hits=data.ray_hits_w.detach().clone()
        pose=self.root_pose_getter().detach().clone()
        if pos.shape!=(self.num_envs,3) or hits.shape!=(self.num_envs,187,3) or pose.shape!=(self.num_envs,7):
            raise AdapterFault("RayCaster snapshot shape mismatch")
        now_ts=[float(x) for x in self.sensor._timestamp]
        if any(now_ts[i]!=self.timestamps[i] or
               raw_sha(pos[i:i+1],hits[i:i+1])!=self.raw_hashes[i] or
               tensor_sha(pose[i:i+1])!=self.pose_hashes[i] for i in range(self.num_envs)):
            raise AdapterFault("sensor or root pose differs from update-completion receipt")
        receipt={"generation":min(self.generations),"generation_by_env":list(self.generations),
                 "step":step,"raw_sha256":raw_sha(pos,hits),"raw_sha256_by_env":list(self.raw_hashes),
                 "pose_sha256_by_env":list(self.pose_hashes),"sensor_timestamp_by_env":list(self.timestamps),
                 "hook_source_path":self.source_path,"hook_source_sha256":self.source_sha256}
        frozen=SimpleNamespace(cfg=self.sensor.cfg,data=SimpleNamespace(pos_w=pos,ray_hits_w=hits))
        return frozen,receipt

    def source_receipt(self):return self.snapshot()[1]

    def detach(self):
        if self.installed:
            self.sensor._update_buffers_impl=self.original;self.installed=False
