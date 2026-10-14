"""Deterministic CUDA/Kit binding tests without touching a physical GPU."""
from types import SimpleNamespace

from s2_device_binding_a2 import DeviceHold,inspect_child_device


class Cudart:
    def __init__(self,bus):self.bus=bus
    def cudaDeviceGetPCIBusId(self,buf,length,index):
        assert index==0
        buf.value=self.bus.encode()
        return 0


class Cuda:
    def __init__(self,bus):self.bus=bus
    def is_available(self):return True
    def device_count(self):return 1
    def current_device(self):return 0
    def cudart(self):return Cudart(self.bus)


def check(name,good):
    print(("PASS" if good else "FAIL")+" "+name,flush=True)
    assert good,name


def main():
    torch=SimpleNamespace(cuda=Cuda("00000000:41:00.0"))
    kit=SimpleNamespace(get=lambda key:0 if key=="/renderer/activeGpu" else None)
    value=inspect_child_device("41:00.0",SimpleNamespace(device_id=0),torch_module=torch,settings=kit)
    check("physical_bus_and_kit_zero",value["torch_pci_bus"]=="41:00.0" and
          value["kit_observation_status"]=="verified")
    try:inspect_child_device("42:00.0",SimpleNamespace(device_id=0),torch_module=torch,settings=kit)
    except DeviceHold as ex:check("torch_bus_mismatch_rejected",str(ex)=="torch_physical_bus_mismatch")
    else:check("torch_bus_mismatch_rejected",False)
    bad=SimpleNamespace(get=lambda key:1 if key=="/renderer/activeGpu" else None)
    try:inspect_child_device("41:00.0",SimpleNamespace(device_id=0),torch_module=torch,settings=bad)
    except DeviceHold as ex:check("kit_renderer_mismatch_rejected",str(ex)=="Kit_renderer_physics_device_mismatch")
    else:check("kit_renderer_mismatch_rejected",False)
    unknown=SimpleNamespace(get=lambda key:None)
    value=inspect_child_device("41:00.0",SimpleNamespace(device_id=0),torch_module=torch,settings=unknown)
    check("kit_unknown_recorded",value["kit_observation_status"]=="unobserved")

if __name__=="__main__":main()
