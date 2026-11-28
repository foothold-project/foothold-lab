"""Does the number of frames given to the mapper in one call change its output? (Codex 430_55 P2-3; CPU only.)

The student training ran the TorchScript mapper on up to 512 frames per call (the chunk setting); step 3 compares one frame per call. This
tool gives the 40 recorded frames of each tag to the SAME TorchScript once as one batch and once frame by frame and reports the largest
difference of the two outputs. It says nothing about the training GPU.
usage: python batch_check.py <extract npz> <mapper_jit> <out json>
"""
import hashlib
import json
import sys

import numpy as np
import torch

EX, MJIT, OUT = sys.argv[1:4]
MJIT_SHA = "52dd869b9fe5bc0ee1973138e72d56d66bee459626da36fed2e2efa716a0e060"


def sha256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


if sha256(MJIT) != MJIT_SHA:
    sys.exit("BATCH_CHECK_FAIL mapper sha256 is not the bundle's")
jm = torch.jit.load(MJIT, map_location="cpu").eval()
z = np.load(EX)
res = {"what": "the same TorchScript mapper, 40 recorded frames in one call vs one frame per call", "torch": torch.__version__,
       "recording_npz_sha256": sha256(EX), "mapper_jit_sha256": MJIT_SHA, "runs": []}
for nt in (1, 4):
    torch.set_num_threads(nt)
    row = {"torch_threads": nt}
    for tag in ("flat", "stairs"):
        G = torch.from_numpy(z[f"{tag}_frame_grid"].astype(np.float32))[:, None]
        with torch.no_grad():
            eb, lb = jm(G)
            single = [jm(G[k:k + 1]) for k in range(G.shape[0])]
        e1, l1 = torch.cat([s[0] for s in single]), torch.cat([s[1] for s in single])
        for name, t in (("batch elevation", eb), ("batch logvar", lb), ("single elevation", e1), ("single logvar", l1)):
            if not bool(torch.isfinite(t).all()):
                sys.exit(f"BATCH_CHECK_FAIL non-finite {name} ({tag})")
        row[tag] = {"frames": int(G.shape[0]), "max_abs_elevation_m": float((eb - e1).abs().max()), "max_abs_logvar": float((lb - l1).abs().max())}
    res["runs"].append(row)
    print(json.dumps(row), flush=True)
json.dump(res, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1)
print("BATCH_CHECK_DONE")
