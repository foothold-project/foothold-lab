"""지면 OBJ를 Isaac Lab 충돌체 USD로 저장하고 새 프로세스에서 재검증한다.

분류: 실험
작성: 오흥재 · 2026-09-16 19:28 (Codex 작업 보조)
근거: WORKER-05-usd.md · Isaac Lab v2.3.2 terrains/utils.py 및 terrain_importer.py
요지: 원본 삼각형 메시를 보존하고 충돌·물리 재질·단위 및 187개 높이 광선을 검증한다.
인자: --obj 입력 OBJ · --usd 출력 USD · --verify 저장 파일 재개방 및 스캔
      --device cuda:<n> 사용할 GPU (기본 cuda:0) · --skip-scan 5번 미수행 명시
사용: isaac311/python.exe poc_mesh_to_usd.py --obj "ground.obj" --usd "ground.usd" --device cuda:0
      위 명령을 새 프로세스로 실행하면서 --verify를 추가한다.
환경 변수는 이 프로세스에서만 설정한다. CUDA_VISIBLE_DEVICES는 변경하지 않는다.
"""

import argparse
from datetime import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import traceback


def now():
    return datetime.now().astimezone().isoformat()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--obj", type=Path, required=True)
    parser.add_argument("--usd", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--skip-scan", action="store_true")
    args = parser.parse_args()
    args.obj = args.obj.resolve()
    args.usd = args.usd.resolve()
    stats_path = args.obj.with_name("ground_stats.json")
    if not args.obj.is_file() or not stats_path.is_file():
        parser.error("선행 조건 없음: ground.obj 또는 ground_stats.json")
    if args.verify and not args.usd.is_file():
        parser.error("재검증할 USD 파일이 없습니다")
    args.usd.parent.mkdir(parents=True, exist_ok=True)
    result_path = args.usd.with_name("ground_usd_check.json" if args.verify else "ground_usd_build.json")
    result = {
        "started_at": now(), "pid": os.getpid(), "mode": "verify" if args.verify else "build",
        "command_argv": sys.argv.copy(), "python": sys.executable, "device": args.device,
        "obj_path": str(args.obj), "usd_path": str(args.usd),
        "obj_sha256": sha256(args.obj), "ground_stats_sha256": sha256(stats_path),
        "passed": False,
    }
    os.environ["OMNI_KIT_ACCEPT_EULA"] = "YES"
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    # Prevent Kit from interpreting this script's CLI flags; preserve the required Windows import order.
    sys.argv[:] = [sys.argv[0]]
    app = None
    exit_code = 1
    try:
        import torch
        from tensordict import TensorDict  # noqa: F401
        import rsl_rl.runners  # noqa: F401
        from isaaclab.app import AppLauncher

        launch_start = time.perf_counter()
        app = AppLauncher(headless=True, device=args.device).app
        result["app_launch_seconds"] = time.perf_counter() - launch_start

        import numpy as np
        import trimesh
        import omni.usd
        from pxr import Gf, PhysxSchema, Usd, UsdGeom, UsdPhysics, UsdShade
        import isaaclab.sim as sim_utils
        from isaaclab.terrains.utils import create_prim_from_mesh

        result["environment"] = {
            "isaacsim": importlib.metadata.version("isaacsim"),
            "isaaclab": Path("C:/isaac/IsaacLab/VERSION").read_text().strip(),
            "trimesh": trimesh.__version__, "numpy": np.__version__, "torch": torch.__version__,
            "gpu_name": torch.cuda.get_device_name(torch.device(args.device)),
        }
        obj_vertices = 0
        obj_face_sizes = []
        for line in args.obj.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if parts and parts[0] == "v":
                obj_vertices += 1
            elif parts and parts[0] == "f":
                obj_face_sizes.append(len(parts) - 1)
        mesh = trimesh.load(str(args.obj), process=False)
        if not isinstance(mesh, trimesh.Trimesh):
            raise TypeError("입력 OBJ가 단일 trimesh.Trimesh가 아닙니다")
        triangles = bool(obj_face_sizes and all(n == 3 for n in obj_face_sizes) and mesh.faces.shape[1] == 3)
        result["obj"] = {
            "vertex_count": len(mesh.vertices), "face_count": len(mesh.faces),
            "raw_vertex_count": obj_vertices, "raw_face_count": len(obj_face_sizes),
            "all_triangles": triangles, "bounds_m": mesh.bounds.tolist(),
            "trimesh_process": False,
        }
        previous_mesh = json.loads(stats_path.read_text(encoding="utf-8"))["mesh"]
        result["obj"]["matches_ground_stats_counts"] = (
            len(mesh.vertices) == previous_mesh["vertex_count"] == obj_vertices
            and len(mesh.faces) == previous_mesh["face_count"] == len(obj_face_sizes)
        )
        if not triangles or not result["obj"]["matches_ground_stats_counts"]:
            raise ValueError("OBJ 삼각형 또는 정점·면 수 선행 통계 대조 실패")

        if not args.verify:
            if not omni.usd.get_context().new_stage():
                raise RuntimeError("새 USD 스테이지 생성 실패")
            stage = omni.usd.get_context().get_stage()
            world = UsdGeom.Xform.Define(stage, "/World").GetPrim()
            stage.SetDefaultPrim(world)
            create_prim_from_mesh(
                "/World/ground", mesh,
                visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.5, 0.5, 0.5)),
                physics_material=sim_utils.RigidBodyMaterialCfg(
                    static_friction=1.0, dynamic_friction=1.0, restitution=0.0,
                ),
            )
            mesh_prim = stage.GetPrimAtPath("/World/ground/mesh")
            result["mesh_collision_api_before_explicit_none"] = mesh_prim.HasAPI(UsdPhysics.MeshCollisionAPI)
            # The helper applies CollisionAPI and PhysxCollisionAPI; explicitly author the mesh approximation.
            UsdPhysics.MeshCollisionAPI.Apply(mesh_prim).CreateApproximationAttr().Set(UsdPhysics.Tokens.none)
            result["mesh_collision_adjustment"] = "MeshCollisionAPI.Apply + approximation=none"
            result["metadata_before"] = {"meters_per_unit": UsdGeom.GetStageMetersPerUnit(stage), "up_axis": str(UsdGeom.GetStageUpAxis(stage))}
            UsdGeom.SetStageMetersPerUnit(stage, 1.0)
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
            result["prim_paths"] = [{"path": str(p.GetPath()), "type": p.GetTypeName()} for p in stage.Traverse()]
            result["export_method"] = "stage.GetRootLayer().Export"
            if not stage.GetRootLayer().Export(str(args.usd)):
                raise RuntimeError("USD Export가 False를 반환했습니다")
            result["usd_size_bytes"] = args.usd.stat().st_size
            result["usd_sha256"] = sha256(args.usd)
            result["passed"] = True
        else:
            # Read-only reopen in this fresh process, before any importer creates a new scene.
            stage = Usd.Stage.Open(str(args.usd))
            if stage is None:
                raise RuntimeError("Usd.Stage.Open 실패")
            result["reopen_method"] = "Usd.Stage.Open (fresh process)"
            build_path = args.usd.with_name("ground_usd_build.json")
            build = json.loads(build_path.read_text(encoding="utf-8")) if build_path.is_file() else None
            result["build_pid"] = build["pid"] if build else None
            result["usd_sha256"] = sha256(args.usd)
            result["matches_build_usd_sha256"] = result["usd_sha256"] == build["usd_sha256"] if build else None
            ground = stage.GetPrimAtPath("/World/ground")
            if not ground:
                raise ValueError("/World/ground가 없습니다")
            prims = list(Usd.PrimRange(ground))
            meshes = [p for p in prims if p.GetTypeName() == "Mesh"]
            planes = [str(p.GetPath()) for p in stage.Traverse() if p.GetTypeName() == "Plane"]
            if len(meshes) != 1:
                raise ValueError(f"Mesh 개수가 1이 아닙니다: {len(meshes)}")
            prim = meshes[0]
            geom = UsdGeom.Mesh(prim)
            points = np.asarray(geom.GetPointsAttr().Get(), dtype=np.float64)
            counts = np.asarray(geom.GetFaceVertexCountsAttr().Get())
            indices = np.asarray(geom.GetFaceVertexIndicesAttr().Get())
            world_matrix = np.asarray(UsdGeom.XformCache().GetLocalToWorldTransform(prim))
            identity = bool(np.allclose(world_matrix, np.eye(4), atol=1e-7, rtol=0))
            world_points = (np.column_stack([points, np.ones(len(points))]) @ world_matrix)[:, :3]
            near_z = world_points[np.linalg.norm(world_points[:, :2], axis=1) <= 1.0, 2]

            def z_stats(values):
                return {"count": int(len(values)), "min_m": float(np.min(values)) if len(values) else None,
                        "max_m": float(np.max(values)) if len(values) else None,
                        "median_m": float(np.median(values)) if len(values) else None}

            material, relationship = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(materialPurpose="physics")
            mat_prim = material.GetPrim() if material else None
            physics_mat = UsdPhysics.MaterialAPI(mat_prim) if mat_prim else None
            material_values = {
                "path": str(mat_prim.GetPath()) if mat_prim else None,
                "binding_relationship": str(relationship.GetPath()) if relationship else None,
                "material_api_applied": bool(mat_prim and mat_prim.HasAPI(UsdPhysics.MaterialAPI)),
                "static_friction": physics_mat.GetStaticFrictionAttr().Get() if physics_mat else None,
                "dynamic_friction": physics_mat.GetDynamicFrictionAttr().Get() if physics_mat else None,
                "restitution": physics_mat.GetRestitutionAttr().Get() if physics_mat else None,
            }
            collision = {
                "collision_api": prim.HasAPI(UsdPhysics.CollisionAPI),
                "collision_enabled": UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get(),
                "physx_collision_api": prim.HasAPI(PhysxSchema.PhysxCollisionAPI),
                "mesh_collision_api": prim.HasAPI(UsdPhysics.MeshCollisionAPI),
                "approximation": UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get(),
            }
            rows = []

            def check(name, expected, actual, passed):
                rows.append({"name": name, "expected": expected, "actual": actual, "passed": bool(passed)})

            check("Mesh·Plane", "Mesh 1개, Plane 0개", {"mesh_paths": [str(p.GetPath()) for p in meshes], "plane_paths": planes}, len(meshes) == 1 and not planes)
            check("삼각형", "faceVertexCounts 전부 3", {"unique_counts": np.unique(counts).tolist(), "index_count": len(indices)}, len(counts) > 0 and np.all(counts == 3) and len(indices) == 3 * len(counts))
            counts_match = len(points) == len(mesh.vertices) and len(counts) == len(mesh.faces)
            check("OBJ 대조", "정점·면 수 동일", {"vertex_count": len(points), "face_count": len(counts)}, counts_match)
            result["topology_identical"] = bool(np.array_equal(indices, mesh.faces.flatten()))
            result["max_vertex_coordinate_error_m"] = float(np.max(np.abs(points - mesh.vertices))) if counts_match else None
            check("충돌 스키마", "CollisionAPI·PhysxCollisionAPI 적용, MeshCollisionAPI approximation none", collision, all(collision[k] for k in ("collision_api", "collision_enabled", "physx_collision_api", "mesh_collision_api")) and collision["approximation"] == "none")
            check("물리 재질", "physicsMaterial 바인딩, 마찰 1/1, 반발 0", material_values, material_values["path"] == "/World/ground/physicsMaterial" and material_values["material_api_applied"] and material_values["static_friction"] == 1.0 and material_values["dynamic_friction"] == 1.0 and material_values["restitution"] == 0.0)
            units = {"meters_per_unit": UsdGeom.GetStageMetersPerUnit(stage), "up_axis": str(UsdGeom.GetStageUpAxis(stage))}
            check("단위·축", "metersPerUnit 1.0, upAxis Z", units, units["meters_per_unit"] == 1.0 and units["up_axis"] == "Z")
            check("월드 변환", "항등행렬", world_matrix.tolist(), identity)
            check("원점 반지름 1 m", "정점 z 최소·최대·중앙값 기록 (수치 문턱 지정 없음)", z_stats(near_z), len(near_z) > 0 and np.isfinite(near_z).all())
            check("파일 크기", "양수 바이트 수 기록", args.usd.stat().st_size, args.usd.stat().st_size > 0)
            result["checks"] = rows
            result["checks_passed"] = sum(row["passed"] for row in rows)
            result["checks_total"] = len(rows)
            result["step4_passed"] = all(row["passed"] for row in rows)
            result["scan"] = {"status": "5번 미수행", "reason": "--skip-scan" if args.skip_scan else "4번 실패 시 중단"}
            write_json(result_path, result)
            if result["step4_passed"] and not args.skip_scan:
                try:
                    from isaaclab.terrains import TerrainImporter, TerrainImporterCfg
                    from isaaclab.sensors import RayCaster, RayCasterCfg
                    from isaaclab.sensors.ray_caster.patterns import GridPatternCfg

                    if not omni.usd.get_context().new_stage():
                        raise RuntimeError("TerrainImporter용 새 스테이지 생성 실패")
                    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=0.01, device=args.device))
                    importer = TerrainImporter(TerrainImporterCfg(
                        terrain_type="usd", usd_path=str(args.usd), prim_path="/World/ground",
                        env_spacing=2.0, num_envs=1,
                    ))
                    sim_utils.create_prim("/World/scan", "Xform", translation=(0.0, 0.0, 1.0))
                    sensor = RayCaster(RayCasterCfg(
                        prim_path="/World/scan", mesh_prim_paths=["/World/ground"],
                        pattern_cfg=GridPatternCfg(resolution=0.1, size=(1.6, 1.0)),
                        ray_alignment="world", debug_vis=False,
                    ))
                    sim.reset()
                    sim.step(render=False)
                    sensor.update(sim.get_physics_dt(), force_recompute=True)
                    hits = sensor.data.ray_hits_w.detach().cpu().numpy().reshape(-1, 3)
                    finite = np.isfinite(hits).all(axis=1)
                    origins = importer.env_origins.detach().cpu().numpy()
                    result["scan"] = {
                        "status": "수행", "terrain_prim_paths": importer.terrain_prim_paths,
                        "env_origins": origins.tolist(), "env_origin_is_zero": bool(np.allclose(origins, [[0, 0, 0]], atol=1e-7)),
                        "sensor_position_w": sensor.data.pos_w.detach().cpu().tolist(),
                        "resolution_m": 0.1, "size_m": [1.6, 1.0], "steps": 1,
                        "ray_count": len(hits), "finite_count": int(finite.sum()),
                        "hit_z": z_stats(hits[finite, 2]),
                        "hits_w": [hit.tolist() if valid else None for hit, valid in zip(hits, finite)],
                        "passed": bool(len(hits) == 187 and finite.all() and np.allclose(origins, [[0, 0, 0]], atol=1e-7)),
                    }
                    sim.stop()
                except Exception:
                    result["scan"] = {"status": "5번 미수행", "reason": "실행 중 예외로 중단", "error": traceback.format_exc()}
            result["passed"] = result["step4_passed"] and (result["scan"]["status"] == "5번 미수행" or result["scan"]["passed"])
        exit_code = 0 if result["passed"] else 1
    except Exception:
        result["error"] = traceback.format_exc()
        print(result["error"], flush=True)
    finally:
        result["finished_at"] = now()
        write_json(result_path, result)
        print(json.dumps({"result_path": str(result_path), "passed": result["passed"]}, ensure_ascii=False), flush=True)
        if app is not None:
            app.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
