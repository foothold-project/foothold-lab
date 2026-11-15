"""Validate logical cuda:0 against the lead-frozen physical bus; record Kit observations."""
from __future__ import annotations

import ctypes

from s2_stage0_resources_a2 import normalize_bus


class DeviceHold(RuntimeError):pass


def inspect_child_device(expected_bus,launcher,*,torch_module=None,settings=None):
    if torch_module is None:
        import torch as torch_module
    cuda=torch_module.cuda
    if not cuda.is_available() or cuda.device_count()!=1 or cuda.current_device()!=0:
        raise DeviceHold("visible_cuda_device_not_unique_zero")
    try:
        bus=ctypes.create_string_buffer(64)
        rc=cuda.cudart().cudaDeviceGetPCIBusId(bus,64,0)
        if rc!=0:raise DeviceHold("cudart_bus_query_failed")
        actual_bus=normalize_bus(bus.value.decode())
    except DeviceHold:raise
    except Exception as ex:raise DeviceHold("cudart_bus_unavailable") from ex
    if actual_bus!=normalize_bus(expected_bus):raise DeviceHold("torch_physical_bus_mismatch")
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
    if any(value!=0 for value in observed.values()):raise DeviceHold("Kit_renderer_physics_device_mismatch")
    return {"torch_logical_device":0,"torch_pci_bus":actual_bus,"kit_requested_device":0,
            "kit_observed":observed,"kit_observation_status":"verified" if observed else "unobserved"}
