"""NuRec USDZ 를 Isaac Sim 5.1 에 참조해 COLMAP 카메라 포즈(메시 프레임)에서 렌더하고 숨김 렌더 · 원본과 비교한다.

분류: 실험
작성: 오흥재 지시 Codex · 2026-09-16 21:14
근거: WORKER-07-nurec.md 1절 4) · _out/nurec/splat.usdz · _out/colmap/undistorted/sparse_txt
요지: 5/255 초과 픽셀 비율로 «렌더 됨» 을 판정하고 metrics.json · compare_cam<idx>.png 를 남긴다.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
os.environ['OMNI_KIT_ACCEPT_EULA'] = 'YES'
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
ROOT = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--attempt', choices=['default', 'no_fabric', 'pathtracing', 'gauss', 'applauncher'], default='default')
p.add_argument('--device', default='cuda:0')
args = p.parse_args()
OUT = ROOT / '_out/nurec' / args.attempt
OUT.mkdir(parents=True, exist_ok=True)
START = time.monotonic()


def stamp(event, **kw):
    print(json.dumps(dict(event=event, pid=os.getpid(), seconds=time.monotonic()-START, **kw)), flush=True)


stamp('launch', attempt=args.attempt, device=args.device)
import torch  # Isaac Windows startup order
if args.attempt == 'applauncher':
    from isaaclab.app import AppLauncher
    app = AppLauncher(headless=True, enable_cameras=True, device=args.device).app
else:
    from isaacsim import SimulationApp
    config = dict(headless=True, renderer='PathTracing' if args.attempt == 'pathtracing' else 'RaytracedLighting',
                  width=1280, height=720, active_gpu=int(args.device.split(':')[-1]), multi_gpu=False)
    if args.attempt == 'no_fabric':
        config['extra_args'] = ['--/app/useFabricSceneDelegate=false']
    app = SimulationApp(config)
stamp('launched')


def main():
    import numpy as np
    from scipy.spatial.transform import Rotation
    from PIL import Image
    from pxr import Usd, UsdGeom, Gf
    import carb
    import omni.usd
    import omni.replicator.core as rep
    from isaacsim.core.utils.stage import add_reference_to_stage
    settings = carb.settings.get_settings()
    if args.attempt == 'pathtracing':
        settings.set('/rtx/pathtracing/spp', 16)
        settings.set('/rtx/pathtracing/totalSpp', 16)
    context = omni.usd.get_context()
    context.new_stage()
    stage = context.get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.Xform.Define(stage, '/World')
    asset = str(ROOT / '_out/nurec/splat.usdz')
    if args.attempt == 'gauss':
        asset += '[gauss.usda]'
    add_reference_to_stage(usd_path=asset, prim_path='/World/nurec')
    root = stage.GetPrimAtPath('/World/nurec')
    prims = [dict(path=str(x.GetPath()), type=x.GetTypeName(),
                  properties=[dict(name=a.GetName(), value=str(a.Get())) for a in x.GetAttributes()])
             for x in Usd.PrimRange(root)]
    (OUT / 'prims.json').write_text(json.dumps(prims, indent=2), encoding='utf-8')
    stamp('reference_loaded', prims=[(x['path'], x['type']) for x in prims])
    stats = json.loads((ROOT / '_out/mesh/ground_stats.json').read_text(encoding='utf-8'))
    m = np.array(stats['transform']['world_to_mesh_4x4'])
    r = m[:3, :3] / stats['scale']['meters_per_scene_unit']
    images = []
    with (ROOT / '_out/colmap/undistorted/sparse_txt/images.txt').open(encoding='utf-8') as f:
        while True:
            line = f.readline()
            if not line:
                break
            if line.startswith('#') or not line.strip():
                continue
            images.append(line.split())
            f.readline()
    idx = 142
    image = images[idx]
    q = np.array(image[1:5], dtype=float)
    rwc = Rotation.from_quat(q[[1, 2, 3, 0]]).as_matrix()
    center = -rwc.T @ np.array(image[5:8], dtype=float)
    pose = np.eye(4)
    pose[:3, 3] = m[:3, :3] @ center + m[:3, 3]
    pose[:3, :3] = r @ rwc.T @ np.diag([1, -1, -1])
    camera = UsdGeom.Camera.Define(stage, '/World/Camera')
    camera.AddTransformOp().Set(Gf.Matrix4d(pose.T.tolist()))
    intrinsics = [line.split() for line in (ROOT / '_out/colmap/undistorted/sparse_txt/cameras.txt').read_text().splitlines()
                  if line.strip() and not line.startswith('#')]
    intr = next(row for row in intrinsics if row[0] == image[8])
    assert intr[1] == 'PINHOLE'
    width, height, fx, fy = map(float, intr[2:6])
    aperture = 20.955
    camera.GetHorizontalApertureAttr().Set(aperture)
    camera.GetVerticalApertureAttr().Set(aperture * 720 / 1280)
    camera.GetFocalLengthAttr().Set(aperture * fx / width)
    camera.GetClippingRangeAttr().Set(Gf.Vec2f(.001, 1000))
    camera_info = dict(index_one_based=idx+1, image=image[9], camera_to_mesh_4x4=pose.tolist(),
                       intrinsics=intr, horizontal_fov_degrees=float(np.degrees(2*np.arctan(width/(2*fx)))))
    (OUT / 'camera.json').write_text(json.dumps(camera_info, indent=2), encoding='utf-8')
    stamp('camera', **camera_info)
    product = rep.create.render_product('/World/Camera', (1280, 720))
    annotator = rep.AnnotatorRegistry.get_annotator('rgb')
    annotator.attach([product])
    import omni.timeline
    omni.timeline.get_timeline_interface().play()
    def capture(label):
        for step in range(60):
            app.update()
            if step % 10 == 0:
                stamp('frame', capture=label, frame=step)
        # A headless paused stage requires an explicit render request for annotators.
        for request in range(5):
            rep.orchestrator.step(rt_subframes=16, pause_timeline=False)
            app.update()
            data = np.array(annotator.get_data())
            stamp('annotator', capture=label, request=request, shape=list(data.shape))
            if data.shape[:2] == (720, 1280):
                break
        assert data.shape[:2] == (720, 1280), data.shape
        rgb = data[:, :, :3].astype(np.uint8)
        Image.fromarray(rgb).save(OUT / f'render_{label}.png')
        return rgb
    a = capture('a_nurec')
    UsdGeom.Imageable(root).MakeInvisible()
    b = capture('b_hidden')
    original = Image.open(ROOT / '_out/colmap/undistorted/images' / image[9]).convert('RGB').resize((1280,720))
    delta = np.abs(a.astype(float)-b.astype(float))
    # Pixel means mean absolute RGB-channel difference; threshold is strictly > 5/255.
    fraction = float((delta.mean(axis=2) > 5).mean())
    gray = np.asarray(Image.fromarray(a).convert('L'), dtype=float)
    small_a = np.asarray(Image.fromarray(a).convert('L').resize((128,72)), dtype=float).ravel()
    small_o = np.asarray(original.convert('L').resize((128,72)), dtype=float).ravel()
    ncc = float(np.corrcoef(small_a,small_o)[0,1]) if small_a.std() and small_o.std() else None
    metrics = dict(attempt=args.attempt, mean_abs_difference_0_255=float(delta.mean()),
                   fraction_pixels_over_5_255=fraction, pixel_definition='mean absolute RGB channel difference > 5',
                   gray_std_0_255=float(gray.std()), ncc_128px=ncc, rendered=fraction >= .30,
                   settings={k:settings.get(k) for k in ['/rtx/rendermode','/app/useFabricSceneDelegate','/rtx/pathtracing/spp']})
    (OUT / 'metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    compare = Image.new('RGB',(3840,720))
    for i, im in enumerate([original, Image.fromarray(a), Image.fromarray(b)]):
        compare.paste(im,(1280*i,0))
    compare.save(OUT / f'compare_cam{idx+1}.png')
    stamp('metrics', **metrics)
    annotator.detach()


try:
    main()
except BaseException:
    import traceback
    error = traceback.format_exc()
    (OUT / 'error.txt').write_text(error, encoding='utf-8')
    print(error, flush=True)
    raise
finally:
    app.close()
