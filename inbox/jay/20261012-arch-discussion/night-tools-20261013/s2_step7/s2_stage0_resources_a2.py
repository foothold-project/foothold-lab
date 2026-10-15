"""Fail-closed resource meters for the lead's attended one-shot collection."""
from __future__ import annotations

from pathlib import Path
import shutil


class ResourceHold(RuntimeError):pass


def normalize_bus(value):
    s=str(value).lower()
    return s[-7:]


class NvmlMeter:
    def __init__(self):
        try:
            import pynvml
            pynvml.nvmlInit()
            self.n=pynvml
        except Exception as ex:raise ResourceHold("nvml_unavailable") from ex

    def probe(self,index:int):
        try:
            handle=self.n.nvmlDeviceGetHandleByIndex(index)
            uuid=self.n.nvmlDeviceGetUUID(handle)
            if isinstance(uuid,bytes):uuid=uuid.decode()
            pci=self.n.nvmlDeviceGetPciInfo(handle).busId
            if isinstance(pci,bytes):pci=pci.decode()
            info=self.n.nvmlDeviceGetMemoryInfo(handle)
            driver=self.n.nvmlSystemGetDriverVersion()
            if isinstance(driver,bytes):driver=driver.decode()
            return {"uuid":str(uuid),"bus":normalize_bus(pci),"index":index,
                    "free_vram_bytes":int(info.free),"total_vram_bytes":int(info.total),
                    "driver_version":str(driver)}
        except Exception as ex:raise ResourceHold("nvml_probe_failed") from ex

    def close(self):self.n.nvmlShutdown()


def disk_free(path):
    try:return shutil.disk_usage(Path(path)).free
    except OSError as ex:raise ResourceHold("disk_probe_failed") from ex


def tree_bytes(root):
    total=0
    try:
        for path in Path(root).rglob("*"):
            if path.is_file():total+=path.stat().st_size
    except OSError as ex:raise ResourceHold("output_size_probe_failed") from ex
    return total


def check_mapping(sample,manifest):
    if (sample.get("uuid")!=manifest["gpu_uuid"] or sample.get("bus")!=normalize_bus(manifest["gpu_bus_id"])
        or sample.get("index")!=manifest["gpu_index"]):
        raise ResourceHold("gpu_uuid_index_bus_mismatch")


def preflight(sample,free_disk,manifest):
    check_mapping(sample,manifest)
    if sample["free_vram_bytes"]<manifest["min_free_vram_bytes"]:raise ResourceHold("vram_preflight_low")
    if free_disk<manifest["min_free_disk_bytes"]:raise ResourceHold("disk_preflight_low")


def running(sample,free_disk,output_bytes,manifest):
    check_mapping(sample,manifest)
    if sample["free_vram_bytes"]<manifest["running_floor_vram_bytes"]:raise ResourceHold("vram_running_low")
    if output_bytes>manifest["max_disk_bytes"]:raise ResourceHold("output_budget_exceeded")
    if free_disk<=0:raise ResourceHold("disk_exhausted")
