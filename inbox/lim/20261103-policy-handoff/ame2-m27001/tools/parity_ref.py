"""AME-2 app handoff (2026-11-03), step 3a: original PyTorch (CPU, float32) on the recorded env inputs.

Uses the same construction as export_ame2_onnx.py (strict load of actor_state_dict, AME2GazeModel.forward,
deterministic mean) and also the code's own as_jit twin. Writes <rec>/ref_<tag>.npz with the recorded
inputs plus action_torch / gaze_r_torch / action_jit_twin, one step at a time (batch 1, as the ONNX).

  /workspace/isaaclab/_isaac_sim/python.sh parity_ref.py <ame2_spd> <run_dir> <ckpt name> <rec_dir>
"""

import json
import os
import sys

B, RUN, CKN, REC = sys.argv[1:5]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0], B, RUN, CKN, REC]
import export_ame2_onnx as ex  # noqa: E402  (puts <ame2_spd>/rsl_rl on sys.path)

import numpy as np  # noqa: E402
import torch  # noqa: E402
import yaml  # noqa: E402

with open(os.path.join(RUN, "params", "agent.yaml")) as f:
    agent = yaml.safe_load(f)
model = ex.build(agent)
ck = torch.load(os.path.join(RUN, CKN), map_location="cpu", weights_only=False)
print("load", model.load_state_dict(ck["actor_state_dict"], strict=True))
model.eval()
twin = model.as_jit().eval()  # before the export wrapper adds its hook
wrap = ex.Ame2DemoExport(model).eval()
out = {}
for tag in ("flat", "stairs"):
    z = np.load(os.path.join(REC, f"rec_{tag}.npz"))
    P = torch.from_numpy(z["prop"]).float()
    M = torch.from_numpy(z["mapping"]).float()
    A, R, J, LG, OF, MU = [], [], [], [], [], []
    with torch.inference_mode():
        for t in range(P.shape[0]):
            a, r, lg, off = wrap(P[t : t + 1], M[t : t + 1])
            A.append(a.numpy()[0])
            R.append(r.numpy()[0])
            LG.append(lg.numpy()[0])
            OF.append(off.numpy()[0])
            tw = twin.forward_with_gaze(P[t : t + 1], M[t : t + 1])
            J.append(tw[0].numpy()[0])
            MU.append(tw[3].numpy()[0])
    A, R, J, LG, OF, MU = np.stack(A), np.stack(R), np.stack(J), np.stack(LG), np.stack(OF), np.stack(MU)
    d = {k: z[k] for k in z.files}
    d.update(action_torch=A, gaze_r_torch=R, gaze_logits_torch=LG, gaze_offset_torch=OF, action_jit_twin=J)
    np.savez(os.path.join(REC, f"ref_{tag}.npz"), **d)
    out[tag] = {
        "steps": int(P.shape[0]),
        "max_abs_torch_cpu_vs_env_gpu": float(np.abs(A - z["action"]).max()),
        "max_abs_torch_vs_jit_twin": float(np.abs(A - J).max()),
        "max_abs_gaze_logits_vs_jit_twin_mu": float(np.abs(LG - MU).max()),
        "max_abs_gaze_r_torch_cpu_vs_env_gpu": float(np.abs(R - z["gaze_r"]).max()),
        "max_abs_action": float(np.abs(A).max()),
    }
out["torch"] = torch.__version__
with open(os.path.join(REC, "ref_info.json"), "w") as f:
    json.dump(out, f, indent=1)
print("REF_INFO", json.dumps(out))
print("REF_DONE")
