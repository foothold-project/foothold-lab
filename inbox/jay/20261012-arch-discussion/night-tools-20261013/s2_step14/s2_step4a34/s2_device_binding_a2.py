"""Validate logical cuda:0 against the lead-frozen physical GPU UUID; record Kit observations.

17x P1: the installed torch (2.7.0+cu128) has no `cudart().cudaDeviceGetPCIBusId`; the supported
child-side identity is `torch.cuda.get_device_properties(0).uuid`. The raw value is stored in
`evidence` BEFORE any comparison so a hold still leaves the real representation on disk.
"""
from __future__ import annotations

import re


class DeviceHold(RuntimeError):pass


def normalize_uuid(value):
    s=re.sub(r"^gpu-?","",str(value).strip().lower())
    return s.replace("-","")


def inspect_child_device(expected_uuid,launcher,*,torch_module=None,settings=None,evidence=None):
    ev=evidence if evidence is not None else {}
    if torch_module is None:
        import torch as torch_module
    cuda=torch_module.cuda
    if not cuda.is_available() or cuda.device_count()!=1 or cuda.current_device()!=0:
        raise DeviceHold("visible_cuda_device_not_unique_zero")
    try:
        props=cuda.get_device_properties(0)
    except Exception as ex:
        ev["properties_error"]=repr(ex)
        raise DeviceHold("torch_properties_unavailable") from ex
    raw=getattr(props,"uuid",None)
    ev["torch_uuid_raw"]=repr(raw)
    ev["torch_device_name"]=str(getattr(props,"name",None))
    if raw is None or str(raw).strip()=="":raise DeviceHold("torch_uuid_attribute_missing")
    if normalize_uuid(raw)!=normalize_uuid(expected_uuid):raise DeviceHold("torch_uuid_mismatch")
    if getattr(launcher,"device_id",None)!=0:raise DeviceHold("Kit_requested_nonzero_device")
    if settings is None:
        try:
            import carb.settings
            settings=carb.settings.get_settings()
        except Exception:settings=None
    observed={}
    if settings is not None:
        for key in ("/renderer/activeGpu","/app/renderer/activeGpu","/physics/cudaDevice"):
            try:value=settings.get(key)
            except Exception:value=None
            if value is not None:observed[key]=value
    ev["kit_observed"]=dict(observed)
    if any(value!=0 for value in observed.values()):raise DeviceHold("Kit_renderer_physics_device_mismatch")
    return {"torch_logical_device":0,"torch_uuid":str(raw),"torch_uuid_normalized":normalize_uuid(raw),
            "kit_requested_device":0,"kit_observed":observed,
            "kit_observation_status":"verified" if observed else "unobserved"}
