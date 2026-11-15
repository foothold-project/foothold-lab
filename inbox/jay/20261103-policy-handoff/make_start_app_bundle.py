"""Build a START app bundle (ONNX map_on/map_off + parity + test vectors) from one checkpoint.

One command (see MAKE-APP-BUNDLE.md):

    python make_start_app_bundle.py all --checkpoint <model_N.pt> --sha256 <sha> \
        --name start-m13000 --label "EX-42 stage 0 model_1000 = cumulative m13000" \
        --contract-md <CONTRACT.md> --out <repo>/inbox/jay/20261103-policy-handoff/start-m13000-app

Reuse, not a new exporter:
  * The ONNX export and the synthetic CPU comparison are the m6000 scripts
    `foothold_s2/deploy/export_ex40_w89.py` and `verify_ex40_w89.py` (commit 34982e13),
    called unchanged.  Only their `load_components` is replaced, because the original
    pins iter == 6000, the m6000 sha and a 96-wide actor.
  * The real-input 20-step state-feedback comparison is `compare_trace` / `load_trace`
    from `foothold_s2/deploy/package_ex40_real20.py` (commit a10af76f), called unchanged.
  * The model code (StartPerception) comes from the commit that trained the checkpoint
    (manifest.json git.head next to the checkpoint), extracted with `git archive`.

Phases: `torch` runs in the isaac311 env (torch + onnx), `ort` runs in a Python that has
onnxruntime (base anaconda), exactly as the m6000 bundle was made.  `all` runs both.
CPU only: CUDA_VISIBLE_DEVICES is forced empty for both child processes.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

EXPORT_COMMIT = "34982e132b68ec1d62dbb3d7ab5a14fba2ed8a06"   # export_ex40_w89.py · verify_ex40_w89.py
PACKAGE_COMMIT = "a10af76f3631535468456917a88df07b0ef84e1b"  # capture_ex40_real20.py · package_ex40_real20.py
OVERLAYS = {EXPORT_COMMIT: ("foothold_s2/deploy/export_ex40_w89.py", "foothold_s2/deploy/verify_ex40_w89.py"),
            PACKAGE_COMMIT: ("foothold_s2/deploy/capture_ex40_real20.py",
                             "foothold_s2/deploy/package_ex40_real20.py")}
DEFAULT_CAPTURE = r"D:/mai-tmp/scripter/start_demo_real20_20261103_try03"
DEFAULT_TORCH_PY = r"C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe"
DEFAULT_ORT_PY = r"C:/Users/AI-WS01/anaconda3/python.exe"
HERE = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE / "start-demo-app" / "contract.json"
SYNTH_TOL = 3e-5
REAL_TOL = 1e-4
MODE_ALIAS = {"eval_pred": "reconstruction", "probe_prop_only": "off", "eval_gt": "gt"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def save_npz(path: Path, arrays: dict) -> None:
    """np.savez_compressed with fixed zip timestamps, so the same arrays give the same bytes."""
    import numpy as np

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for key in sorted(arrays):
            buf = io.BytesIO()
            np.lib.format.write_array(buf, np.asanyarray(arrays[key]), allow_pickle=False)
            info = zipfile.ZipInfo(key + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, buf.getvalue())


# ---------------------------------------------------------------- source tree

def prepare_source(repo: Path, ref: str, dest: Path) -> dict:
    """foothold_s2 at the training commit, plus the m6000 deploy scripts at their pinned commits."""
    data = git(repo, "archive", "--format=tar", ref, "foothold_s2")
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(dest, filter="data")
    overlays = {}
    for commit, paths in OVERLAYS.items():
        for rel in paths:
            blob = git(repo, "show", f"{commit}:{rel}")
            target = dest / rel
            if target.exists() and target.read_bytes() != blob:
                raise RuntimeError(f"{rel} at {ref} differs from {commit}; review before reuse")
            target.write_bytes(blob)
            overlays[rel] = {"commit": commit, "sha256": hashlib.sha256(blob).hexdigest()}
    return overlays


# ---------------------------------------------------------------- torch phase

def torch_phase(args) -> int:
    sys.path.insert(0, str(Path(args.src).resolve()))
    import numpy as np
    import torch
    from torch import nn

    import foothold_s2.deploy.export_ex40_w89 as exp
    import foothold_s2.deploy.verify_ex40_w89 as ver
    from foothold_s2.models.start_perception import PerceptionCfg, StartPerception

    work = Path(args.work).resolve()
    checkpoint = Path(args.checkpoint)
    receipt: dict = {}

    class ZeroPoseActor(nn.Module):
        """actor(obs45 + est51 + pose2); the pose command is fixed at 0 (D93 stage)."""

        def __init__(self, net: nn.Sequential) -> None:
            super().__init__()
            self.net = net

        def forward(self, x):
            return self.net(torch.cat((x, x.new_zeros(x.shape[0], 2)), dim=-1))

    def load_components(path: Path, expected_sha256: str):
        if not Path(path).is_file() or sha256(Path(path)) != expected_sha256:
            raise ValueError("checkpoint missing or SHA256 differs")
        sd = torch.load(path, map_location="cpu", weights_only=False)
        cfg = sd.get("perception_cfg") or {}
        if (cfg.get("map_input") != "reconstruction" or cfg.get("est_mode") != "learned"
                or cfg.get("fast_gt_only")):
            raise ValueError(f"perception contract differs from START bundle: {cfg}")
        norm = sd.get("normalization_state") or {}
        if norm.get("actor_obs_enabled"):
            raise ValueError("actor observation normalization is on; the bundle has no normalizer")
        perception = StartPerception(PerceptionCfg(map_input="reconstruction",
                                                   force_gt=bool(cfg.get("force_gt"))))
        perception.load_state_dict(sd["perception_state_dict"], strict=True)
        msd = sd["model_state_dict"]
        layers, i = [], 0
        while f"actor.{i}.weight" in msd:
            w = msd[f"actor.{i}.weight"]
            layers.append(nn.Linear(w.shape[1], w.shape[0]))
            if f"actor.{i + 2}.weight" in msd:
                layers.append(nn.ELU())
            i += 2
        actor = nn.Sequential(*layers)
        actor.load_state_dict({k.removeprefix("actor."): v for k, v in msd.items()
                               if k.startswith("actor.")}, strict=True)
        in_dim = int(msd["actor.0.weight"].shape[1])
        pose = bool(sd.get("ex41_pose_commands", False))
        if in_dim != 96 + (2 if pose else 0) or int(msd[f"actor.{i - 2}.weight"].shape[0]) != 12:
            raise ValueError(f"actor input {in_dim} does not match pose flag {pose}")
        receipt.update({"checkpoint_iter": int(sd.get("iter", -1)), "actor_input_dim": in_dim,
                        "actor_hidden": [int(msd[f"actor.{j}.weight"].shape[0]) for j in range(0, i - 2, 2)],
                        "pose_cmd_in_actor": pose,
                        "perception_cfg": {k: cfg.get(k) for k in
                                           ("contract", "map_input", "est_mode", "force_gt", "p_map_off",
                                            "critic_mode", "depth_dtype")}})
        return perception.eval(), (ZeroPoseActor(actor) if pose else actor).eval()

    # The only change to the m6000 scripts: their checkpoint loader.
    exp.load_components = load_components
    onnx_dir = work / "onnx"
    exported = exp.export(checkpoint, onnx_dir, args.sha256)
    fixtures = work / "fixtures"
    ver.make_fixtures(checkpoint, args.sha256, fixtures)

    import onnx
    for mode in ("map_on", "map_off"):
        onnx.checker.check_model(onnx.load(str(onnx_dir / f"ex40_m6000_{mode}.onnx")))
        receipt[f"onnx_nodes_{mode}"] = len(onnx.load(str(onnx_dir / f"ex40_m6000_{mode}.onnx")).graph.node)

    # Real Kit inputs: replay the recorded inputs; GRU state is this checkpoint's own (torch).
    from foothold_s2.deploy.capture_ex40_real20 import CASES, INPUTS, MODES, OUTPUTS
    capture = Path(args.capture_dir)
    cap = json.loads((capture / "capture.json").read_text(encoding="utf-8"))
    torch.set_num_threads(1)
    torch.backends.mha.set_fastpath_enabled(False)
    nets = {}
    for graph in ("map_on", "map_off"):
        perception, actor = load_components(checkpoint, args.sha256)
        nets[graph] = exp.PerceptionActor(perception, actor, map_off=(graph == "map_off")).eval()
    real = work / "real_ref"
    real.mkdir(parents=True)
    for case, _level, _col in CASES:
        for mode in MODES:
            key = f"{case}/{mode}"
            path = capture / f"{case}_{mode}.npz"
            if sha256(path) != cap["cases"][key]["sha256"]:
                raise AssertionError(f"capture changed: {key}")
            net = nets["map_off" if mode == "probe_prop_only" else "map_on"]
            arrays, hidden = {}, None
            with np.load(path, allow_pickle=False) as data:
                for k in range(20):
                    feed = {n: data[f"step{k:02d}_{n}"].copy() for n in INPUTS}
                    if k:
                        feed["h_prop"], feed["h_terr"] = hidden
                    with torch.no_grad():
                        out = net(*[torch.from_numpy(feed[n]) for n in INPUTS])
                    out = [t.detach().cpu().numpy() for t in out]
                    hidden = out[1], out[2]
                    arrays.update({f"step{k:02d}_{n}": feed[n] for n in INPUTS})
                    arrays.update({f"step{k:02d}_{n}": v for n, v in zip(OUTPUTS, out)})
            save_npz(real / f"{case}_{mode}.npz", arrays)
    receipt.update({"capture_sha256": sha256(capture / "capture.json"),
                    "capture_checkpoint_sha256": cap.get("checkpoint_sha256"),
                    "export_contract": {k: exported[k] for k in ("inputs", "outputs", "actor_input_order")},
                    "torch": torch.__version__, "onnx": onnx.__version__})
    (work / "torch_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"torch_phase": "ok", "actor_input_dim": receipt["actor_input_dim"]}))
    return 0


# ---------------------------------------------------------------- ort phase

def ort_phase(args) -> int:
    sys.path.insert(0, str(Path(args.src).resolve()))
    import numpy as np
    import onnxruntime as ort

    import foothold_s2.deploy.verify_ex40_w89 as ver
    from foothold_s2.deploy.capture_ex40_real20 import CASES, INPUTS, MODES, OUTPUTS
    from foothold_s2.deploy.package_ex40_real20 import compact_json_row, compare_trace, load_trace

    work, out = Path(args.work).resolve(), Path(args.out).resolve()
    if out.exists():
        raise FileExistsError(out)
    rec = json.loads((work / "torch_receipt.json").read_text(encoding="utf-8"))
    template = json.loads(Path(args.template_contract).read_text(encoding="utf-8"))
    name = args.name
    files = {"map_on": f"{name}_map_on.onnx", "map_off": f"{name}_map_off.onnx"}
    onnx_dir = work / "onnx"

    synthetic = ver.compare(onnx_dir, work / "fixtures", SYNTH_TOL)
    sessions = {}
    for graph in files:
        sess = ort.InferenceSession(str(onnx_dir / f"ex40_m6000_{graph}.onnx"),
                                    providers=["CPUExecutionProvider"])
        io_now = ([{"name": i.name, "dims": i.shape, "type": i.type} for i in sess.get_inputs()],
                  [{"name": o.name, "dims": o.shape, "type": o.type} for o in sess.get_outputs()])
        app = template["app_onnx"]
        want_types = {"float32": "tensor(float)", "bool": "tensor(bool)"}
        want = ([{"name": i["name"], "dims": i["dims"], "type": want_types[i["type"]]} for i in app["inputs"]],
                [{"name": o["name"], "dims": o["dims"], "type": want_types[o["type"]]} for o in app["outputs"]])
        if io_now != want:
            raise AssertionError(f"{graph} IO differs from the template app_onnx; bump the format "
                                 f"(/1 -> /2) and update the app doc by hand: {io_now}")
        sessions[graph] = sess

    real, traces = {}, {}
    for case, _level, _col in CASES:
        for mode in MODES:
            rows = load_trace(work / "real_ref" / f"{case}_{mode}.npz")
            if not bool(rows[0]["first_after_reset"][0]):
                raise AssertionError(f"missing first flag: {case}/{mode}")
            graph = "map_off" if mode == "probe_prop_only" else "map_on"
            real[f"{case}/{mode}"] = compare_trace(sessions[graph], rows, REAL_TOL)
            traces[f"{case}/{mode}"] = rows

    out.mkdir(parents=True)
    shas = {}
    for graph, fname in files.items():
        shutil.copyfile(onnx_dir / f"ex40_m6000_{graph}.onnx", out / fname)
        shas[graph] = sha256(out / fname)
    shutil.copyfile(args.contract_md, out / "CONTRACT.md")
    (out / ".gitattributes").write_bytes(b"* -text\n")
    flat_all = {}
    for mode, alias in MODE_ALIAS.items():
        rows = traces[f"flat/{mode}"]
        graph = "map_off" if mode == "probe_prop_only" else "map_on"
        payload = {"format": f"{name}-test-vectors/1", "model": name,
                   "checkpoint_sha256": args.sha256, "onnx": {files[graph]: shas[graph]},
                   "map_mode": alias, "steps": 20, "tolerance": REAL_TOL, "state_feedback": True,
                   "inputs": [compact_json_row(r, INPUTS) for r in rows],
                   "expected": [compact_json_row(r, OUTPUTS) for r in rows],
                   "input_shapes": {i.name: i.shape for i in sessions[graph].get_inputs()},
                   "input_types": {i.name: i.type for i in sessions[graph].get_inputs()}}
        (out / f"test_vectors_flat20_{alias}.json").write_text(
            json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
        arrays = {f"step{k:02d}_{n}": r[n] for k, r in enumerate(rows) for n in (*INPUTS, *OUTPUTS)}
        save_npz(out / f"test_vectors_flat20_{alias}.npz", arrays)
        flat_all.update({f"{alias}_{k}": v for k, v in arrays.items()})
    shutil.copyfile(out / "test_vectors_flat20_reconstruction.json", out / "test_vectors_flat20.json")
    save_npz(out / "test_vectors_flat20.npz", flat_all)

    real_max = max(v for row in real.values() for v in row.values())
    syn_max = max(v for row in synthetic.values() for v in row.values())
    parity = {"format": f"{name}-parity/1", "checkpoint_sha256": args.sha256,
              "onnxruntime": ort.__version__, "torch": rec["torch"],
              "synthetic": {"format": "foothold-ex40-w89-cpu-comparison/1", "cases": synthetic,
                            "max_abs": syn_max, "tolerance_max_abs": SYNTH_TOL},
              "real": {"source_capture": Path(args.capture_dir).joinpath("capture.json").as_posix(),
                       "capture_sha256": rec["capture_sha256"],
                       "capture_driven_by_checkpoint_sha256": rec["capture_checkpoint_sha256"],
                       "note": ("Kit inputs recorded while m6000 drove the robot; this checkpoint's own torch "
                                "GRU state is fed back; open-loop replay, not this checkpoint's closed loop"),
                       "cases": real, "steps_per_case": 20, "state_feedback": True,
                       "max_abs": real_max, "tolerance": REAL_TOL, "passed": True}}
    (out / "parity.json").write_text(json.dumps(parity, indent=2) + "\n", encoding="utf-8")

    contract = {k: v for k, v in template.items() if k not in ("renamed_from",)}
    contract.update({
        "format": f"{name}-onnx/1", "model": name, "label": args.label,
        "checkpoint": args.checkpoint, "checkpoint_sha256": args.sha256,
        "checkpoint_iter": rec["checkpoint_iter"],
        "source": "inbox/jay/20261103-policy-handoff/make_start_app_bundle.py",
        "source_ref": args.source_ref, "overlays": json.loads(args.overlays),
        "actor_input_order": ("obs45 + [mu16, v3, zf16, zb16] + pose_cmd2 (fixed 0 inside the graph)"
                              if rec["pose_cmd_in_actor"] else "obs45 + [mu16, v3, zf16, zb16]"),
        "actor_input_dim": rec["actor_input_dim"], "actor_hidden": rec["actor_hidden"],
        "perception_cfg": rec["perception_cfg"],
        "artifacts": {g: {"name": files[g], "sha256": shas[g], "bytes": (out / files[g]).stat().st_size}
                      for g in files},
        "test_vectors": {alias: f"test_vectors_flat20_{alias}.json" for alias in MODE_ALIAS.values()},
        "default_test_vectors": "test_vectors_flat20.json"})
    if rec["pose_cmd_in_actor"]:
        contract["pose_cmd"] = {"columns": ["height_delta_m", "body_roll_rad"], "value_in_graph": [0.0, 0.0],
                                "why": "trained only with zero pose commands (D93 first stage); not an ONNX input"}
    (out / "contract.json").write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [f"{sha256(p)}  {p.name}" for p in sorted(out.iterdir(), key=lambda p: p.name)
             if p.is_file() and p.name not in ("SHA256SUMS", ".gitattributes")]
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"synthetic_max_abs": syn_max, "real_max_abs": real_max, "out": str(out),
                      "map_on": shas["map_on"], "map_off": shas["map_off"]}))
    return 0


# ---------------------------------------------------------------- driver

def run_all(args) -> int:
    # children run with cwd=work, so every path handed to them must be absolute
    for key in ("contract_md", "template_contract", "capture_dir"):
        setattr(args, key, Path(getattr(args, key)).resolve().as_posix())
    checkpoint = Path(args.checkpoint)
    out = Path(args.out).resolve()
    if out.exists():
        raise FileExistsError(out)
    if sha256(checkpoint) != args.sha256:
        raise ValueError("checkpoint SHA256 differs from --sha256")
    repo = Path(args.repo or git(HERE, "rev-parse", "--show-toplevel").decode().strip())
    manifest = checkpoint.parent / "manifest.json"
    ref = args.source_ref
    if ref is None:
        man = json.loads(manifest.read_text(encoding="utf-8"))
        ref = man["git"]["head"]
        if man["git"].get("dirty_diff_bytes", 0):
            raise RuntimeError("training source was dirty; pass --source-ref after review")
    work = Path(args.work or tempfile.mkdtemp(prefix="app_bundle_", dir=os.environ.get("TMP"))).resolve()
    work.mkdir(parents=True, exist_ok=True)
    src = work / "src"
    if src.exists():
        raise FileExistsError(src)
    src.mkdir()
    git(repo, "cat-file", "-e", f"{ref}^{{commit}}")
    overlays = prepare_source(repo, ref, src)
    if manifest.is_file():
        want = json.loads(manifest.read_text(encoding="utf-8")).get("files", {}).get(
            "imported_sha256", {}).get("foothold_s2.models.start_perception")
        got = sha256(src / "foothold_s2/models/start_perception.py")
        if want and want != got:
            raise RuntimeError(f"start_perception.py at {ref} differs from the training import")
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONDONTWRITEBYTECODE="1")
    me = str(Path(__file__).resolve())
    subprocess.run([args.torch_python, me, "torch", "--src", str(src), "--work", str(work),
                    "--checkpoint", str(checkpoint), "--sha256", args.sha256,
                    "--capture-dir", args.capture_dir], check=True, env=env, cwd=str(work))
    subprocess.run([args.ort_python, me, "ort", "--src", str(src), "--work", str(work), "--out", str(out),
                    "--checkpoint", str(checkpoint), "--sha256", args.sha256, "--name", args.name,
                    "--label", args.label, "--contract-md", args.contract_md,
                    "--template-contract", args.template_contract, "--source-ref", ref,
                    "--overlays", json.dumps(overlays, sort_keys=True),
                    "--capture-dir", args.capture_dir], check=True, env=env, cwd=str(work))
    print(json.dumps({"work": str(work), "out": str(out), "source_ref": ref}))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("all")
    a.add_argument("--checkpoint", required=True)
    a.add_argument("--sha256", required=True)
    a.add_argument("--name", required=True, help="bundle id, e.g. start-m13000 (folder = <name>-app)")
    a.add_argument("--label", required=True, help="one line: experiment · stage · cumulative update")
    a.add_argument("--contract-md", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--capture-dir", default=DEFAULT_CAPTURE)
    a.add_argument("--template-contract", default=str(DEFAULT_TEMPLATE))
    a.add_argument("--source-ref", default=None, help="default: manifest.json git.head next to the checkpoint")
    a.add_argument("--repo", default=None)
    a.add_argument("--work", default=None)
    a.add_argument("--torch-python", default=DEFAULT_TORCH_PY)
    a.add_argument("--ort-python", default=DEFAULT_ORT_PY)
    t = sub.add_parser("torch")
    for k in ("--src", "--work", "--checkpoint", "--sha256", "--capture-dir"):
        t.add_argument(k, required=True)
    o = sub.add_parser("ort")
    for k in ("--src", "--work", "--out", "--checkpoint", "--sha256", "--name", "--label",
              "--contract-md", "--template-contract", "--source-ref", "--overlays", "--capture-dir"):
        o.add_argument(k, required=True)
    args = p.parse_args()
    return {"all": run_all, "torch": torch_phase, "ort": ort_phase}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
