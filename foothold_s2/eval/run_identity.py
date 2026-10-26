"""X27j5: 평가 한 번이 어느 장치 · 코드 · 저장본으로 돌았는지의 기록(실행 계열 대조용). turn_probe 가 쓴다.

eval_map_modes._run_identity 와 같은 칸을 같은 이름으로 낸다(창 판정기 run_identity_check 가 둘을 같은 식으로 읽는다).
turn_probe 에는 시드 인자가 없어 eval_seed 칸은 없다. 못 알아낸 칸은 비우고 까닭(gpu_error · code_error)을 남기며, 기록 실패가 평가를 막지 않는다."""
from __future__ import annotations

import os
import subprocess


def collect(device, checkpoint_sha256, repo_root=None, eval_seed=None) -> dict:
    out = {"device": str(device), "checkpoint_sha256": checkpoint_sha256}

    if eval_seed is not None:
        out["eval_seed"] = eval_seed

    try:
        import torch

        out["torch"] = torch.__version__
        out["torch_cuda"] = torch.version.cuda
        d = torch.device(device)
        pr = torch.cuda.get_device_properties(d)
        out.update({"gpu_name": pr.name, "gpu_total_mem_mib": int(pr.total_memory // (1 << 20)), "gpu_index": d.index, "gpu_uuid": str(getattr(pr, "uuid", None))})
    except Exception as e:                                                             # noqa: BLE001
        out["gpu_error"] = repr(e)

    try:
        root = repo_root or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        out["code_head"] = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=20).stdout.strip() or None
        out["code_dirty_files"] = len([ln for ln in subprocess.run(["git", "-C", root, "status", "--short", "foothold_s2"], capture_output=True, text=True, timeout=20).stdout.splitlines() if ln.strip()])
    except Exception as e:                                                             # noqa: BLE001
        out["code_error"] = repr(e)

    return out


def safe_collect(device, checkpoint_sha256, repo_root=None, eval_seed=None) -> dict:
    """collect 가 예외를 내도 평가는 계속한다(기록 자리에 오류 문구만)."""
    try:
        return collect(device, checkpoint_sha256, repo_root, eval_seed)
    except Exception as e:                                                             # noqa: BLE001
        return {"device": str(device), "checkpoint_sha256": checkpoint_sha256, "identity_error": repr(e)}
