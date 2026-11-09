"""APP-TUNING-1109 측정: 정책 ONNX 의 크기 · 연산량 · CPU 추론 시간 (GPU 안 씀).

쓰는 법 (lab 저장소 뿌리에서):
  CUDA_VISIBLE_DEVICES= <onnxruntime 있는 python> inbox/jay/20261103-policy-handoff/app-tuning-1109/app_tuning_bench.py [--calls 500] [--out out.json]

- 입력은 각 묶음의 시험 벡터(평지 20 스텝)를 차례로 돌려 쓴다. start 는 GRU 상태를 되먹인다(앱과 같음).
- 연산량은 Conv · ConvTranspose · Gemm · MatMul · GRU 의 곱셈-덧셈 수(MAC)만 센다(활성 함수 · 원소별 연산은 뺌).
- 브라우저 onnxruntime-web(wasm) 시간은 이 스크립트가 재지 않는다. 같은 판 wasm 을 Node 로 잰 값은 app_tuning_bench_wasm.mjs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import time
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import numpy as np
import onnx
import onnxruntime as ort
from onnx import shape_inference

HERE = Path(__file__).resolve().parent.parent  # 묶음 폴더(20261103-policy-handoff)
MODELS = {
    "m6000_map_on": ("start-demo-app/start-demo_map_on.onnx", "start-demo-app/test_vectors_flat20_gt.npz", "start"),
    "m6000_map_off": ("start-demo-app/start-demo_map_off.onnx", "start-demo-app/test_vectors_flat20_off.npz", "start"),
    "m13000_map_on": ("start-m13000-app/start-m13000_map_on.onnx", "start-m13000-app/test_vectors_flat20_gt.npz", "start"),
    "m13000_map_off": ("start-m13000-app/start-m13000_map_off.onnx", "start-m13000-app/test_vectors_flat20_off.npz", "start"),
    "ame2": ("ame2-demo-app/ame2-demo.onnx", "ame2-demo-app/test_vectors_flat20.npz", "ame2"),
}
START_INPUTS = ["obs45", "hist", "depth2", "h_prop", "h_terr", "depth_tick", "first_after_reset", "use_gt", "gt_map"]


def macs(model: onnx.ModelProto) -> dict:
    m = shape_inference.infer_shapes(model)
    shapes = {}
    for vi in list(m.graph.value_info) + list(m.graph.input) + list(m.graph.output):
        shapes[vi.name] = [d.dim_value for d in vi.type.tensor_type.shape.dim]
    for init in m.graph.initializer:
        shapes[init.name] = list(init.dims)
    out = {"Conv": 0, "ConvTranspose": 0, "Gemm": 0, "MatMul": 0, "GRU": 0, "unknown_shape_nodes": 0}
    for n in m.graph.node:
        if n.op_type not in out:
            continue
        try:
            if n.op_type in ("Conv", "ConvTranspose"):
                w = shapes[n.input[1]]
                y = shapes[n.output[0]]
                x = shapes[n.input[0]]
                if n.op_type == "Conv":
                    out["Conv"] += int(np.prod(y)) * int(np.prod(w[1:]))
                else:
                    out["ConvTranspose"] += int(np.prod(x)) * int(np.prod(w[1:]))
            elif n.op_type == "Gemm":
                a, b = shapes[n.input[0]], shapes[n.input[1]]
                trans_b = any(at.name == "transB" and at.i == 1 for at in n.attribute)
                k = a[-1]
                nout = b[0] if trans_b else b[1]
                out["Gemm"] += a[0] * k * nout
            elif n.op_type == "MatMul":
                a, b = shapes[n.input[0]], shapes[n.input[1]]
                out["MatMul"] += int(np.prod(a[:-1])) * a[-1] * b[-1]
            elif n.op_type == "GRU":
                w, r = shapes[n.input[1]], shapes[n.input[2]]
                x = shapes[n.input[0]]
                out["GRU"] += x[0] * (int(np.prod(w[1:])) + int(np.prod(r[1:])))
            if 0 in [*shapes.get(n.output[0], [0])]:
                out["unknown_shape_nodes"] += 1
        except (KeyError, IndexError):
            out["unknown_shape_nodes"] += 1
    out["total_MAC"] = sum(v for k, v in out.items() if k not in ("unknown_shape_nodes",))
    return out


def feeds_start(z, step, state):
    p = f"step{step:02d}_"
    f = {k: z[p + k] for k in START_INPUTS}
    if state is not None:
        f["h_prop"], f["h_terr"] = state
    return f


def bench(name, rel_model, rel_vec, kind, calls, threads):
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    if threads:
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
    sess = ort.InferenceSession(str(HERE / rel_model), so, providers=["CPUExecutionProvider"])
    z = np.load(HERE / rel_vec)
    times = []
    state = None
    for i in range(calls + 20):
        s = i % 20
        if kind == "start":
            f = feeds_start(z, s, None if s == 0 else state)
        else:
            f = {"prop": z["prop"][s:s + 1], "mapping": z["mapping"][s:s + 1]}
        t = time.perf_counter()
        out = sess.run(None, f)
        dt = (time.perf_counter() - t) * 1000.0
        if kind == "start":
            names = [o.name for o in sess.get_outputs()]
            state = (out[names.index("h_prop_next")], out[names.index("h_terr_next")])
        if i >= 20:
            times.append(dt)
    times.sort()
    return {
        "median_ms": round(statistics.median(times), 4),
        "p95_ms": round(times[int(0.95 * len(times)) - 1], 4),
        "max_ms": round(times[-1], 4),
        "calls": len(times),
        "threads": threads or "default",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls", type=int, default=500)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    report = {"onnxruntime": ort.__version__, "onnx": onnx.__version__, "cpu": platform.processor(),
              "cpu_count": os.cpu_count(), "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"), "models": {}}
    for name, (rel_model, rel_vec, kind) in MODELS.items():
        path = HERE / rel_model
        data = path.read_bytes()
        model = onnx.load(str(path))
        params = sum(int(np.prod(t.dims)) for t in model.graph.initializer)
        sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        inputs = {i.name: {"shape": i.shape, "type": i.type} for i in sess.get_inputs()}
        float_in = sum(int(np.prod(v["shape"])) for v in inputs.values() if v["type"] == "tensor(float)")
        report["models"][name] = {
            "file": rel_model,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "nodes_top": len(model.graph.node),
            "params": params,
            "mac": macs(model),
            "inputs": inputs,
            "input_floats": float_in,
            "input_bytes": float_in * 4,
            "cpu_1thread": bench(name, rel_model, rel_vec, kind, args.calls, 1),
            "cpu_default": bench(name, rel_model, rel_vec, kind, args.calls, 0),
        }
        r = report["models"][name]
        print(f"{name:15s} {r['bytes']/1e6:5.2f} MB params {r['params']:>9,d} MAC {r['mac']['total_MAC']/1e6:7.2f} M "
              f"in {r['input_floats']:>5d} f32 | 1T med {r['cpu_1thread']['median_ms']:.3f} p95 {r['cpu_1thread']['p95_ms']:.3f} | "
              f"def med {r['cpu_default']['median_ms']:.3f} p95 {r['cpu_default']['p95_ms']:.3f} ms", flush=True)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
