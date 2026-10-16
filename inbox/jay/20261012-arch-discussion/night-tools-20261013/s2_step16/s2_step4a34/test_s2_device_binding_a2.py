"""Deterministic CUDA/Kit binding tests without touching a physical GPU (17x: uses the real
`get_device_properties(0).uuid` attribute shape instead of a nonexistent cudart bus API)."""
from types import SimpleNamespace

from s2_device_binding_a2 import DeviceHold,inspect_child_device,normalize_uuid

UUID="GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b"


class Cuda:
    def __init__(self,uuid,error=None,count=1):self.uuid=uuid;self.error=error;self.count=count
    def is_available(self):return True
    def device_count(self):return self.count
    def current_device(self):return 0
    def get_device_properties(self,index):
        assert index==0
        if self.error:raise self.error
        return SimpleNamespace(name="NVIDIA GeForce RTX 5080",uuid=self.uuid)


def check(name,good):
    print(("PASS" if good else "FAIL")+" "+name,flush=True)
    assert good,name


def hold(torch,settings,uuid=UUID,evidence=None):
    try:inspect_child_device(uuid,SimpleNamespace(device_id=0),torch_module=torch,settings=settings,evidence=evidence)
    except DeviceHold as ex:return str(ex)
    return None


def main():
    kit=SimpleNamespace(get=lambda key:0 if key=="/renderer/activeGpu" else None)
    ev={}
    value=inspect_child_device(UUID,SimpleNamespace(device_id=0),torch_module=SimpleNamespace(cuda=Cuda(UUID)),
                               settings=kit,evidence=ev)
    check("uuid_match_and_kit_zero",value["torch_uuid_normalized"]==normalize_uuid(UUID) and
          value["kit_observation_status"]=="verified" and ev["torch_uuid_raw"]==repr(UUID))
    check("uuid_representation_variants_equal",all(
        hold(SimpleNamespace(cuda=Cuda(v)),kit) is None
        for v in (UUID.upper(),UUID[4:],UUID.replace("-","")," "+UUID)))
    other="GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f"
    ev={}
    check("other_gpu_uuid_rejected",hold(SimpleNamespace(cuda=Cuda(other)),kit,evidence=ev)=="torch_uuid_mismatch"
          and ev["torch_uuid_raw"]==repr(other))
    ev={}
    check("missing_uuid_attribute_rejected_with_evidence",
          hold(SimpleNamespace(cuda=Cuda(None)),kit,evidence=ev)=="torch_uuid_attribute_missing" and
          ev["torch_uuid_raw"]=="None")
    ev={}
    check("properties_error_rejected_with_evidence",
          hold(SimpleNamespace(cuda=Cuda(UUID,error=RuntimeError("boom"))),kit,evidence=ev)=="torch_properties_unavailable"
          and "boom" in ev["properties_error"])
    check("two_visible_devices_rejected",hold(SimpleNamespace(cuda=Cuda(UUID,count=2)),kit)=="visible_cuda_device_not_unique_zero")
    bad=SimpleNamespace(get=lambda key:1 if key=="/renderer/activeGpu" else None)
    check("kit_renderer_mismatch_rejected",hold(SimpleNamespace(cuda=Cuda(UUID)),bad)=="Kit_renderer_physics_device_mismatch")
    unknown=SimpleNamespace(get=lambda key:None)
    value=inspect_child_device(UUID,SimpleNamespace(device_id=0),torch_module=SimpleNamespace(cuda=Cuda(UUID)),settings=unknown)
    check("kit_unknown_recorded",value["kit_observation_status"]=="unobserved")
    try:inspect_child_device(UUID,SimpleNamespace(device_id=1),torch_module=SimpleNamespace(cuda=Cuda(UUID)),settings=kit)
    except DeviceHold as ex:check("kit_requested_nonzero_rejected",str(ex)=="Kit_requested_nonzero_device")
    else:check("kit_requested_nonzero_rejected",False)


if __name__=="__main__":main()
