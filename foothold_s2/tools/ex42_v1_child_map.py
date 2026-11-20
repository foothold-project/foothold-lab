"""New E2 v1 boundary child (sonnet-code-lx 11/20): planner-lx run_child_map.py with the map-position modes of this session. MAPSWAP=flat (body-row median) or cm5..cm20 (terrain looks 5..20 cm ahead);
only when use_gt is true for all envs (the right-map input mode). MAPSAVE=<npz> stores maps. A `MAPPROBE {... swapped_calls ...}` line proves a swap happened (> 0)."""
import os
import runpy

import numpy as np
import torch

from foothold_s2.models import start_perception as sp

MODE = os.environ.get("MAPSWAP", "")
SAVE = os.environ.get("MAPSAVE", "")
FLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ex42_v1_child_flag.py")   # yawkit child (heading fixed, PROBE_CASES speeds); planner-lx 11/15, copied unchanged
_adv = sp.StartPerception._advance
st = {"n": 0, "gt": [], "dec": [], "ref": [], "usegt": [], "step": [], "swapped": 0}


def adv(self, h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, *rest):
    true_map = gt_map
    if MODE and gt_map is not None and bool(use_gt.all()):
        g = gt_map
        assert g.ndim == 3 and g.shape[1] == 32 and g.shape[2] == 16, tuple(g.shape)
        if MODE == "flat":
            base = g[:, 9:11, :].flatten(1).median(1).values
            gt_map = base[:, None, None].expand_as(g).clone()
        elif MODE.startswith("cm"):
            cm = int(MODE[2:]); assert cm % 5 == 0 and 5 <= cm <= 20, cm   # 0.05 m 칸: cm5..cm20 = 1..4 칸 (cm20 = 기존 shift20)
            k = cm // 5
            gt_map = torch.cat([g[:, :1].expand(-1, k, -1), g[:, :-k]], 1)
        else:
            raise ValueError(MODE)
        st["swapped"] += 1
    res = _adv(self, h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, *rest)
    if true_map is not None and true_map.shape[0] > 1:
        if st["n"] % 5 == 0:
            out = res[2]
            with torch.no_grad():
                dec = self.ie.dec_b(out["zb"].float()).reshape(true_map.shape)
            st["gt"].append(true_map.detach().float().cpu().numpy().astype(np.float16))
            st["dec"].append(dec.cpu().numpy().astype(np.float16))
            if "refined" in out:
                st["ref"].append(out["refined"].detach().float().reshape(true_map.shape).cpu().numpy().astype(np.float16))
            st["usegt"].append(bool(use_gt.all()))
            st["step"].append(st["n"])
            if len(st["gt"]) % 20 == 0:
                dump()
        st["n"] += 1
    return res


def dump():
    print("MAPPROBE", {"mode": MODE, "swapped_calls": st["swapped"], "saved_frames": len(st["gt"])}, flush=True)
    if SAVE and st["gt"]:
        extra = {"ref": np.stack(st["ref"])} if len(st["ref"]) == len(st["gt"]) else {}
        np.savez_compressed(SAVE + ".tmp.npz", gt=np.stack(st["gt"]), dec=np.stack(st["dec"]), usegt=np.array(st["usegt"]), step=np.array(st["step"]), **extra)
        os.replace(SAVE + ".tmp.npz", SAVE)


sp.StartPerception._advance = adv
try:
    runpy.run_path(FLAG, run_name="__main__")
finally:
    dump()
