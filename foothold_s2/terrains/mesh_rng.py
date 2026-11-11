"""Seed the RNGs used by Isaac terrain leaf functions, without leaking state.

TerrainGeneratorCfg.seed controls its own default_rng, but boxes uses the
default Torch generator and random_rough uses legacy NumPy. The CUDA generator
covered here is the current device: Isaac's boxes explicitly allocates on
torch.device('cuda'). Other devices are not initialized or reseeded.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib


def _tensor_record(state):
    raw = state.cpu().numpy().tobytes()
    return {"encoding": "base64-uint8", "length": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "state": base64.b64encode(raw).decode("ascii")}


def _record(np_state, cpu_state, cuda_state):
    name, keys, pos, has_gauss, cached_gaussian = np_state
    return {
        "numpy": {"algorithm": name, "keys_uint32": keys.tolist(),
                  "position": int(pos), "has_gauss": int(has_gauss),
                  "cached_gaussian": float(cached_gaussian)},
        "torch_cpu": _tensor_record(cpu_state),
        "torch_cuda": None if cuda_state is None else _tensor_record(cuda_state),
    }


@contextmanager
def seeded_mesh_rng(seed: int):
    """Yield JSON-ready pre/post generation states; restore caller state even on failure.

Reproducibility is within a fixed software stack and geometry device. CPU and
CUDA random streams are different, even for the same seed. This context must
not overlap other mesh generation in the same process (the RNGs are global).
"""
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("mesh seed must be an explicit uint32")
    import numpy as np
    import torch

    cuda_index = torch.cuda.current_device() if torch.cuda.is_available() else None
    np_before = np.random.get_state()
    cpu_before = torch.get_rng_state()
    cuda_before = torch.cuda.get_rng_state(cuda_index) if cuda_index is not None else None
    receipt = {
        "format": "foothold-ex42-mesh-rng/1", "seed": seed, "status": "failed",
        "numpy_version": np.__version__, "torch_version": str(torch.__version__),
        "torch_cuda_version": torch.version.cuda,
        "geometry_rng_device": "cpu" if cuda_index is None else f"cuda:{cuda_index}",
        "cuda_device_name": None if cuda_index is None else torch.cuda.get_device_name(cuda_index),
        "scope": "legacy NumPy + Torch CPU + current CUDA device; TerrainGenerator default_rng uses cfg.seed",
        "caller_state_restored": False,
    }
    try:
        np.random.seed(seed)
        # Unlike torch.manual_seed, do not reseed other visible CUDA devices.
        torch.random.default_generator.manual_seed(seed)
        if cuda_index is not None:
            torch.cuda.manual_seed(seed)
        receipt["before_generation"] = _record(
            np.random.get_state(), torch.get_rng_state(),
            torch.cuda.get_rng_state(cuda_index) if cuda_index is not None else None)
        yield receipt
        receipt["status"] = "complete"
    finally:
        try:
            receipt["after_generation"] = _record(
                np.random.get_state(), torch.get_rng_state(),
                torch.cuda.get_rng_state(cuda_index) if cuda_index is not None else None)
        finally:
            np.random.set_state(np_before)
            torch.set_rng_state(cpu_before)
            if cuda_before is not None:
                torch.cuda.set_rng_state(cuda_before, cuda_index)
            receipt["caller_state_restored"] = True
