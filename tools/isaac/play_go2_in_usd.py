"""학습된 Go2 정책을 '학습에 쓰지 않은' 임의의 USD 씬에서 재생한다.

NVIDIA 공식 튜토리얼(scripts/tutorials/03_envs/policy_inference_in_usd.py)의 Go2판.
원본은 H1 + 창고였다. 여기서는 Go2 + 원하는 USD 환경으로 바꾸고, 영상 저장을 추가했다.

이것이 증명하려는 것:
  "회색 지형에서 학습한 정책을, 정책만 들고 나와서, 완전히 다른 씬에서 걷게 할 수 있다"
  = 학습 씬과 렌더 씬의 분리. 극사실주의 렌더 경로의 주춧돌.

Windows 우회: Kit 로드 전에 네이티브 확장 패키지를 선점 import (play_go2_win.py 와 동일 이유)
"""

import torch  # noqa: F401  (선점)
from tensordict import TensorDict  # noqa: F401  (선점 - access violation 방지)
import rsl_rl.runners  # noqa: F401  (선점)
import h5py  # noqa: F401  (선점 - GUI 모드 entrypoint 오류 방지)

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Go2 정책을 임의의 USD 씬에서 재생")
parser.add_argument("--checkpoint", type=str, required=True, help="JIT(TorchScript)로 익스포트된 policy.pt 경로")
parser.add_argument("--env_usd", type=str, default="Environments/Simple_Warehouse/warehouse.usd",
                    help="ISAAC_NUCLEUS_DIR 하위의 USD 환경 경로")
parser.add_argument("--steps", type=int, default=500, help="재생할 스텝 수 (50Hz 이므로 500 = 10초)")
parser.add_argument("--video", action="store_true", help="mp4 저장")
parser.add_argument("--out", type=str, default="C:/isaac/IsaacLab/logs/usd_play", help="영상 출력 폴더")
parser.add_argument("--tag", type=str, default="run", help="출력 파일 이름표")
parser.add_argument("--renderer", type=str, default=None,
                    choices=["RaytracedLighting", "PathTracing"],
                    help="렌더러 강제 지정. PathTracing 은 고품질/저속")
parser.add_argument("--spp", type=int, default=64, help="PathTracing 샘플 수 (품질)")
parser.add_argument("--res", type=str, default=None, help="렌더 해상도 예: 1920x1080")
parser.add_argument("--hdri", type=str, default=None, help="돔 라이트에 걸 HDRI(.hdr) 경로. 가장 싼 룩 개선")
parser.add_argument("--hdri_intensity", type=float, default=1000.0, help="HDRI 돔 라이트 강도")

AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

if args_cli.video:
    args_cli.enable_cameras = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""------ Kit 기동 후 ------"""
import io
import os

import gymnasium as gym
import omni

from isaaclab.envs import ManagerBasedRLEnv
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.utils.assets import ISAAC_NUCLEUS_DIR

from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.rough_env_cfg import UnitreeGo2RoughEnvCfg_PLAY


def _force_renderer():
    """Kit 기동 뒤 carb 설정으로 렌더러를 직접 바꾼다.

    --kit_args 로 /rtx/rendermode 를 넘기는 방법은 실측 결과 적용되지 않았다
    (세 렌더가 픽셀상 동일했다). 여기서 설정하고, 설정 후 값을 되읽어 확인한다.
    """
    if not args_cli.renderer:
        return
    import carb
    s = carb.settings.get_settings()
    s.set("/rtx/rendermode", args_cli.renderer)
    if args_cli.renderer == "PathTracing":
        # ★ 애니메이션 캡처에서는 프레임마다 새로 그리므로 totalSpp(누적 목표)가 의미 없다.
        #    한 번의 렌더 호출에서 쓰는 샘플 수인 spp 를 직접 올려야 실제 품질이 오른다.
        s.set("/rtx/pathtracing/spp", int(args_cli.spp))
        s.set("/rtx/pathtracing/totalSpp", int(args_cli.spp))
        s.set("/rtx/pathtracing/maxBounces", 8)
        s.set("/rtx/pathtracing/optixDenoiser/enabled", True)
    # ★ 되읽어 확인 — 설정했다는 사실이 아니라 설정된 값을 본다
    print(f"[RENDER] 요청={args_cli.renderer}  실제 /rtx/rendermode={s.get('/rtx/rendermode')}")
    print(f"[RENDER] spp={s.get('/rtx/pathtracing/spp')}  totalSpp={s.get('/rtx/pathtracing/totalSpp')}")


def main():
    _force_renderer()
    policy_path = os.path.abspath(args_cli.checkpoint)
    print(f"[INFO] 정책 로드: {policy_path}")
    file_content = omni.client.read_file(policy_path)[2]
    file = io.BytesIO(memoryview(file_content).tobytes())
    policy = torch.jit.load(file, map_location=args_cli.device)

    env_cfg = UnitreeGo2RoughEnvCfg_PLAY()
    env_cfg.scene.num_envs = 1
    env_cfg.curriculum = None
    if args_cli.env_usd.lower() == "none":
        # 지형 교체 없이 기본 절차생성 험지(하늘이 열려 있음)를 쓴다.
        # 돔 라이트가 실내(지붕 있는 USD)에서 차단되는지 판별할 때 필요하다.
        print("[INFO] USD 교체 없음: 기본 험지(열린 하늘)")
    else:
        usd_full = f"{ISAAC_NUCLEUS_DIR}/{args_cli.env_usd}"
        print(f"[INFO] USD 환경: {usd_full}")
        # ★ 핵심 한 줄 — 학습에 쓰던 절차생성 지형을 통째로 USD 파일로 교체
        env_cfg.scene.terrain = TerrainImporterCfg(
            prim_path="/World/ground",
            terrain_type="usd",
            usd_path=usd_full,
        )
    env_cfg.sim.device = args_cli.device
    if args_cli.device == "cpu":
        env_cfg.sim.use_fabric = False

    if args_cli.res:
        w, h = (int(v) for v in args_cli.res.lower().split("x"))
        env_cfg.viewer.resolution = (w, h)
        print(f"[RENDER] 해상도 {w}x{h}")

    if args_cli.hdri:
        # 기본 씬의 돔 라이트(sky_light)에 실사 HDRI 를 건다.
        # 조사 결론: 가장 싸게 룩이 올라가는 첫 수 (omniverse-stack.md §3)
        env_cfg.scene.sky_light.spawn.texture_file = os.path.abspath(args_cli.hdri)
        env_cfg.scene.sky_light.spawn.intensity = args_cli.hdri_intensity
        # 되읽어 확인. 설정했다는 사실은 증거가 아니다
        print(f"[RENDER] HDRI={env_cfg.scene.sky_light.spawn.texture_file} "
              f"intensity={env_cfg.scene.sky_light.spawn.intensity}")

    env = ManagerBasedRLEnv(cfg=env_cfg, render_mode="rgb_array" if args_cli.video else None)

    # ★ cfg 되읽기가 아니라 «USD 스테이지의 실제 프림»을 되읽는다.
    #   cfg 확인까지 통과하고도 화면이 안 변한 사고가 있었다(2026-08-12 HDRI).
    try:
        # ★ `import omni.usd` 를 함수 안에서 하면 omni 가 지역 이름이 되어
        #   함수 첫머리의 omni.client 호출이 UnboundLocalError 로 죽는다(2026-08-12 실제).
        from omni.usd import get_context
        stage = get_context().get_stage()
        prim = stage.GetPrimAtPath("/World/skyLight")
        if prim and prim.IsValid():
            tex = prim.GetAttribute("inputs:texture:file").Get()
            inten = prim.GetAttribute("inputs:intensity").Get()
            print(f"[STAGE] /World/skyLight 존재 · texture={tex} · intensity={inten}")
        else:
            print("[STAGE] ★ /World/skyLight 프림이 없다 — 돔 라이트가 스폰되지 않았다")
    except Exception as e:
        print(f"[STAGE] 확인 실패: {e}")

    if args_cli.video:
        os.makedirs(args_cli.out, exist_ok=True)
        env = gym.wrappers.RecordVideo(
            env,
            video_folder=args_cli.out,
            step_trigger=lambda s: s == 0,
            video_length=args_cli.steps,
            name_prefix=args_cli.tag,
            disable_logger=True,
        )
        print(f"[INFO] 영상 저장 위치: {args_cli.out}")

    obs, _ = env.reset()
    n = 0
    with torch.inference_mode():
        while simulation_app.is_running() and n < args_cli.steps:
            action = policy(obs["policy"])
            obs, _, _, _, _ = env.step(action)
            n += 1
            if n % 100 == 0:
                print(f"[INFO] {n}/{args_cli.steps} 스텝")

    print(f"[DONE] {n} 스텝 재생 완료")
    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
