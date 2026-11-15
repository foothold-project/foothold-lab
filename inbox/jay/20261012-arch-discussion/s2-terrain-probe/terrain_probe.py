# S2 지형 생성 확인 (lead · 2026-10-13 저녁 · ASTRA 17 §3.2 「그대로 켜면 안 되는 설정이 있다」). CPU · Isaac 앱 없이.
# Isaac Lab 의 생성기 함수 자체 (hf_terrains.stepping_stones_terrain · mesh_terrains.gap_terrain) 를 파일 경로로 불러
# 실제 높이맵 · mesh 를 만들고 잰다. isaaclab 패키지 __init__ 은 pxr 이 필요해 건너뛰므로, height_field / trimesh 하위
# 폴더를 가짜 패키지 이름으로 올린다 (생성기 코드는 고치지 않고 그대로 실행).
# 재는 것: 실제 돌 폭 · 빈 간격 (칸 수와 m) · 구멍 비율 · 높이 값 종류 · mesh sha256 (가운데 출발 판 제외 구간 포함).
# 대상: E1 학습 설정 (비율 0 이던 stones · gap) · v2 미경험 평가 설정 · S2 입문 후보 (ASTRA 17 §3.2 표).
# 사용: python terrain_probe.py [out_dir]   (기본 _eval/out_s2probe)
import hashlib
import importlib.util
import json
import os
import sys
import types
from types import SimpleNamespace

import numpy as np

IL = "C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains"
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out_s2probe")


def load_pkg(name, path, mods):
    pkg = types.ModuleType(name)
    pkg.__path__ = [path]
    sys.modules[name] = pkg
    out = {}
    for m in mods:
        spec = importlib.util.spec_from_file_location(f"{name}.{m}", os.path.join(path, m + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"{name}.{m}"] = mod
        spec.loader.exec_module(mod)
        out[m] = mod
    return out


HF = load_pkg("_hf", os.path.join(IL, "height_field"), ["utils", "hf_terrains"])
TM = load_pkg("_tm", os.path.join(IL, "trimesh"), ["utils", "mesh_terrains"])
stones_raw = HF["hf_terrains"].stepping_stones_terrain.__wrapped__   # 높이맵 그대로 (decorator 가 mesh 로 바꾸기 전)
stones_mesh = HF["hf_terrains"].stepping_stones_terrain               # 실제로 쓰는 mesh
gap_mesh = TM["mesh_terrains"].gap_terrain


def runs(row, hole):
    """한 줄에서 연속된 구간 길이 (구멍 · 돌) 를 칸 수로."""
    out = {"hole": [], "stone": []}
    cur, n = row[0] == hole, 0
    for v in row:
        h = v == hole
        if h == cur:
            n += 1
        else:
            out["hole" if cur else "stone"].append(n)
            cur, n = h, 1
    out["hole" if cur else "stone"].append(n)
    return out


def mesh_sha(meshes):
    h = hashlib.sha256()
    for m in meshes:
        h.update(np.ascontiguousarray(m.vertices, dtype=np.float64).tobytes())
        h.update(np.ascontiguousarray(m.faces, dtype=np.int64).tobytes())
    return h.hexdigest()


def probe_stones(label, p, diffs, seed=0):
    res = []
    for d in diffs:
        cfg = SimpleNamespace(size=p["size"], horizontal_scale=p["hs"], vertical_scale=p["vs"], slope_threshold=0.75,
                              border_width=p.get("border", 0.0), stone_height_max=p["hmax"], stone_width_range=p["w"],
                              stone_distance_range=p["dist"], holes_depth=p["holes"], platform_width=p["platform"])
        np.random.seed(seed)
        w_cfg = p["w"][1] - d * (p["w"][1] - p["w"][0])
        g_cfg = p["dist"][0] + d * (p["dist"][1] - p["dist"][0])
        try:
            hf = stones_raw(d, cfg)
        except Exception as ex:  # noqa: BLE001  생성기 자체가 멈추는 설정도 사실로 남긴다
            res.append({"difficulty": d, "cfg_stone_width_m": round(w_cfg, 4), "cfg_gap_m": round(g_cfg, 4),
                        "px_stone_width": int(w_cfg / p["hs"]), "px_gap": int(g_cfg / p["hs"]),
                        "generator_error": f"{type(ex).__name__}: {ex}"})
            continue
        hole = int(p["holes"] / p["vs"])
        c = hf.shape[0] // 2
        pw = int(p["platform"] / p["hs"])
        mask = np.ones_like(hf, bool)
        mask[c - pw // 2: c + pw // 2, c - pw // 2: c + pw // 2] = False   # 가운데 출발 판 밖만 잰다
        holes = (hf == hole) & mask
        rr = [runs(hf[i, :], hole) for i in range(0, hf.shape[0], max(1, hf.shape[0] // 20))]
        hole_runs = [x for r in rr for x in r["hole"]]
        stone_runs = [x for r in rr for x in r["stone"]]
        np.random.seed(seed)
        meshes, origin = stones_mesh(d, SimpleNamespace(**vars(cfg)))
        res.append({"difficulty": d, "cfg_stone_width_m": round(w_cfg, 4), "cfg_gap_m": round(g_cfg, 4),
                    "px_stone_width": int(w_cfg / p["hs"]), "px_gap": int(g_cfg / p["hs"]),
                    "hole_fraction_outside_platform": round(float(holes.sum() / mask.sum()), 4),
                    "measured_hole_run_px": sorted(set(hole_runs))[:8], "measured_stone_run_px_min_max": [min(stone_runs), max(stone_runs)],
                    "height_levels_m": sorted({round(float(v) * p["vs"], 3) for v in np.unique(hf) if v != hole})[:10],
                    "mesh_sha256": mesh_sha(meshes if isinstance(meshes, list) else [meshes])})
    return {"label": label, "params": {k: v for k, v in p.items()}, "rows": res}


def probe_gap(label, p, diffs):
    res = []
    for d in diffs:
        cfg = SimpleNamespace(size=p["size"], gap_width_range=p["gap"], platform_width=p["platform"])
        meshes, origin = gap_mesh(d, cfg)
        g = p["gap"][0] + d * (p["gap"][1] - p["gap"][0])
        res.append({"difficulty": d, "gap_width_m": round(g, 4), "platform_m": p["platform"], "mesh_sha256": mesh_sha(meshes)})
    return {"label": label, "params": p, "rows": res}


def main():
    os.makedirs(OUT, exist_ok=True)
    D = [0.0, 0.25, 0.5, 0.75, 0.99]
    rep = {"generator_files": {f: hashlib.sha256(open(os.path.join(IL, f), "rb").read()).hexdigest()
                               for f in ("height_field/hf_terrains.py", "height_field/utils.py", "trimesh/mesh_terrains.py")},
           "probes": []}
    # E1 학습 설정 (params/env.yaml · 비율 0) · 크기 9 x 9 · 0.1 / 0.005
    rep["probes"].append(probe_stones("E1 train stones (proportion 0)", dict(size=(9.0, 9.0), hs=0.1, vs=0.005, hmax=0.0, w=(0.075, 1.575),
                                                                          dist=(0.05, 0.1), holes=-10.0, platform=4.0, border=0.5), D))
    rep["probes"].append(probe_gap("E1 train gap (proportion 0)", dict(size=(9.0, 9.0), gap=(0.0, 0.9), platform=3.0), D))
    # v2 미경험 평가 (lab sim/eval/generalization_env_cfg.py · 크기 8 x 8)
    rep["probes"].append(probe_stones("v2 unseen10 stones (eval)", dict(size=(8.0, 8.0), hs=0.1, vs=0.005, hmax=0.12, w=(0.35, 0.65),
                                                                     dist=(0.08, 0.20), holes=-1.0, platform=1.5, border=0.25), D))
    rep["probes"].append(probe_gap("v2 unseen10 gap (eval)", dict(size=(8.0, 8.0), gap=(0.15, 0.40), platform=1.5), D))
    # S2 입문 후보 (ASTRA 17 §3.2 · 사전 제안 · Go2 통과 가능 미확인)
    rep["probes"].append(probe_stones("S2 entry stones candidate", dict(size=(8.0, 8.0), hs=0.1, vs=0.005, hmax=0.06, w=(0.50, 0.70),
                                                                     dist=(0.10, 0.10), holes=-1.0, platform=1.5, border=0.25), D))
    rep["probes"].append(probe_gap("S2 entry gap candidate", dict(size=(8.0, 8.0), gap=(0.10, 0.25), platform=1.5), D))
    with open(os.path.join(OUT, "terrain_probe.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    for pr in rep["probes"]:
        print("##", pr["label"])
        for r in pr["rows"]:
            print("  ", {k: v for k, v in r.items() if k != "mesh_sha256"}, r.get("mesh_sha256", "")[:10])


if __name__ == "__main__":
    main()
