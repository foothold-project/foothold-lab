"""평가 파이프라인 v1 · 학습된 정책을 험지에서 N 에피소드 돌려 CSV 로 남긴다.

  왜 만드나
    지금까지 "보상 13.94" 같은 학습 지표만 있었다. 그건 학습이 잘 됐다는 뜻이지
    **로봇이 실제로 목적을 달성하는가**를 말해주지 않는다.
    이 스크립트가 프로젝트의 첫 성능 기록(통과율)을 만든다.

  성공 정의 (임시안 v1)
    ① 전진 거리 10m 이상   ② 넘어지지 않음   ③ 제한시간(에피소드 길이) 내

  Windows 우회: Kit 로드 전에 네이티브 확장 패키지를 선점 import
"""

import torch                       # noqa: F401
from tensordict import TensorDict  # noqa: F401
import rsl_rl.runners              # noqa: F401
import h5py                        # noqa: F401

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Go2 정책 평가 · N 에피소드 → CSV")
parser.add_argument("--checkpoint", type=str, required=True, help="JIT(TorchScript) policy.pt 경로")
parser.add_argument("--episodes", type=int, default=100, help="평가할 에피소드 수")
parser.add_argument("--num_envs", type=int, default=50, help="동시에 돌릴 환경 수")
parser.add_argument("--goal_m", type=float, default=10.0, help="성공으로 칠 전진 거리(m)")
parser.add_argument("--cmd_vx", type=float, default=1.0, help="고정 전진 명령 속도(m/s)")
parser.add_argument("--out", type=str, default="C:/isaac/IsaacLab/logs/eval/eval.csv")
parser.add_argument("--tag", type=str, default="run", help="결과 식별 이름")
parser.add_argument("--level", type=int, default=0, help="스폰 지형 난이도(0=가장 쉬움). 평가 일관성을 위해 고정한다")
parser.add_argument("--strict", action="store_true", help="선회까지 막아 직진만 시킨다(학습 분포에서 멀어짐)")
parser.add_argument("--free_cmd", action="store_true",
                    help="명령 고정을 끈다(기본 랜덤 명령). 원인 격리용 A/B 스위치")
parser.add_argument("--video", action="store_true", help="평가 장면을 mp4 로 남긴다 (눈으로 확인용)")

AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
if args_cli.video:
    args_cli.enable_cameras = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""------ Kit 기동 후 ------"""
import csv
import io
import os

import omni

from isaaclab.envs import ManagerBasedRLEnv

from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.rough_env_cfg import UnitreeGo2RoughEnvCfg_PLAY


def main():
    policy_path = os.path.abspath(args_cli.checkpoint)
    print(f"[EVAL] 정책: {policy_path}")
    fc = omni.client.read_file(policy_path)[2]
    policy = torch.jit.load(io.BytesIO(memoryview(fc).tobytes()), map_location=args_cli.device)

    cfg = UnitreeGo2RoughEnvCfg_PLAY()
    cfg.scene.num_envs = args_cli.num_envs
    cfg.curriculum = None
    cfg.sim.device = args_cli.device
    cfg.observations.policy.enable_corruption = False       # 평가에는 관측 노이즈를 끈다

    # ★ 스폰 난이도를 고정한다 · 평가의 생명은 일관성이다.
    #   PLAY 기본값 max_init_terrain_level=None 은 로봇을 랜덤 난이도 타일에 떨어뜨린다.
    #   실측 결과 로봇이 지형에 파묻힌 채(루트 z=-0.19, 기울기 23도) 시작하는 경우가 나왔고,
    #   그 에피소드는 정책 실력과 무관하게 0m 로 기록된다 (2026-08-11).
    tg = cfg.scene.terrain.terrain_generator
    if tg is not None:
        tg.num_rows = 10
        tg.num_cols = 10
        tg.curriculum = True                                 # 행(row)=난이도 로 정렬시킨다
    cfg.scene.terrain.max_init_terrain_level = args_cli.level

    # ★ 명령을 고정한다 · 랜덤 명령이면 "10m 전진"의 의미가 매 에피소드 달라진다
    cmd = cfg.commands.base_velocity
    #  ★ 학습 조건에서 최소한만 바꾼다. 평가가 학습과 다른 환경이면 정책은 제 실력을 못 낸다
    #    (heading_command 를 끄고 재샘플을 막았더니 로봇이 얼어붙었다 · 2026-08-11).
    #    학습 원본: lin_vel_x/y (-1,1) · ang_vel_z (-1,1) · heading (-pi,pi) · heading_command=True
    #             · rel_standing_envs=0.02 · resampling_time_range=(10,10)
    if not args_cli.free_cmd:
        cmd.ranges.lin_vel_x = (args_cli.cmd_vx, args_cli.cmd_vx)
        cmd.ranges.lin_vel_y = (0.0, 0.0)
        cmd.rel_standing_envs = 0.0        # 평가에서 "가만히 서 있으라"는 명령은 만들지 않는다
        if args_cli.strict:
            # 직진만 시키고 싶을 때 · 다만 이건 학습 분포에서 더 멀어진다
            cmd.ranges.ang_vel_z = (0.0, 0.0)
            cmd.ranges.heading = (0.0, 0.0)

    if args_cli.video:
        # ★ 기본 카메라는 고정 좌표를 본다 · 로봇이 없는 허공을 찍는다(2026-08-11 실제로 그랬다).
        #   로봇을 따라가게 바꾼다. 안 그러면 "영상은 나왔는데 아무것도 안 보이는" 조용한 실패다.
        cfg.viewer.origin_type = "asset_root"
        cfg.viewer.asset_name = "robot"
        cfg.viewer.env_index = 0
        cfg.viewer.eye = (2.5, 2.5, 1.6)
        cfg.viewer.lookat = (0.0, 0.0, 0.3)

    env = ManagerBasedRLEnv(cfg=cfg, render_mode="rgb_array" if args_cli.video else None)
    if args_cli.video:
        import gymnasium as gym
        vd = os.path.join(os.path.dirname(args_cli.out), "video")
        os.makedirs(vd, exist_ok=True)
        env = gym.wrappers.RecordVideo(
            env, video_folder=vd, step_trigger=lambda s: s == 0,
            video_length=600, name_prefix=args_cli.tag, disable_logger=True)
        env = env.unwrapped if False else env
    dev = env.unwrapped.device if args_cli.video else env.device
    N = env.unwrapped.num_envs if args_cli.video else env.num_envs
    U = env.unwrapped if args_cli.video else env
    dt = U.step_dt                                          # 정책 1스텝의 실제 시간(초)
    max_steps = int(cfg.episode_length_s / dt)
    print(f"[EVAL] env={N} · step_dt={dt:.4f}s · 에피소드 최대 {max_steps} step "
          f"({cfg.episode_length_s}s) · 목표 {args_cli.goal_m}m · 명령 {args_cli.cmd_vx}m/s")

    robot = U.scene["robot"]
    obs, _ = env.reset()

    start_xy = robot.data.root_pos_w[:, :2].clone()
    ep_steps = torch.zeros(N, dtype=torch.long, device=dev)
    max_dist = torch.zeros(N, device=dev)                     # 에피소드 중 도달한 최대 전진 거리

    # ★ Isaac Sim Kit 이 stdout 을 가로채서 print 가 로그에 남지 않는다(2026-08-11 확인).
    #   진단은 반드시 파일로 쓴다. 화면에 안 보이는 것과 실행되지 않은 것은 구분되어야 한다.
    diag_path = os.path.splitext(args_cli.out)[0] + ".diag.txt"
    os.makedirs(os.path.dirname(diag_path), exist_ok=True)
    dlog = io.open(diag_path, "w", encoding="utf-8")

    def D(msg):
        dlog.write(msg + "\n")
        dlog.flush()

    D(f"정책      : {policy_path}")
    D(f"환경      : {N}개 · step_dt {dt:.4f}s · 최대 {max_steps} step · 목표 {args_cli.goal_m}m")
    # 알려진 답 테스트 · "설정했다"는 사실은 증거가 아니다. 값을 되읽어 확인한다.
    try:
        c = U.command_manager.get_command("base_velocity")
        D(f"[CHECK] 명령 텐서 shape={tuple(c.shape)}  첫 환경={[round(v,3) for v in c[0].tolist()]}")
        D(f"[CHECK] 명령 x 평균={float(c[:, 0].mean()):.3f}  (기대 {args_cli.cmd_vx})")
    except Exception as e:
        D(f"[CHECK] 명령 조회 실패: {e}")
    D(f"[CHECK] 관측 차원={obs['policy'].shape[-1]}  (rough 기대 235)")
    D(f"[CHECK] cfg 상 lin_vel_x 범위={cmd.ranges.lin_vel_x} · heading_command="
      f"{getattr(cmd, 'heading_command', 'n/a')} · rel_standing={cmd.rel_standing_envs}")

    rows = []
    ep_id = 0
    step = 0
    diag = []                                                 # (명령x, 실제x) 표본

    with torch.inference_mode():
        while ep_id < args_cli.episodes and simulation_app.is_running():
            action = policy(obs["policy"])
            obs, _, terminated, truncated, _ = env.step(action)
            step += 1
            ep_steps += 1

            xy = robot.data.root_pos_w[:, :2]
            dist = torch.linalg.norm(xy - start_xy, dim=1)
            max_dist = torch.maximum(max_dist, dist)

            done = (terminated | truncated)
            idx = done.nonzero(as_tuple=False).flatten()
            for i in idx.tolist():
                if ep_id >= args_cli.episodes:
                    break
                fell = bool(terminated[i].item())             # 조기 종료 = 넘어짐/실패
                d = float(max_dist[i].item())
                t = float(ep_steps[i].item()) * dt
                success = (d >= args_cli.goal_m) and (not fell)
                rows.append({
                    "episode": ep_id,
                    "success": int(success),
                    "distance_m": round(d, 3),
                    "fell": int(fell),
                    "time_s": round(t, 3),
                    "steps": int(ep_steps[i].item()),
                    "timeout": int(bool(truncated[i].item()) and not fell),
                })
                ep_id += 1
            if len(idx) > 0:
                start_xy[idx] = xy[idx]
                ep_steps[idx] = 0
                max_dist[idx] = 0.0
            if step % 100 == 0:
                try:
                    cx = float(U.command_manager.get_command("base_velocity")[:, 0].mean())
                except Exception:
                    cx = float("nan")
                vx = float(robot.data.root_lin_vel_b[:, 0].mean())   # 몸통 좌표계 전진 속도
                diag.append((cx, vx))
                # 무엇이 멈췄는지 좁힌다 · 물리인가, 버퍼인가, 정책인가
                jp = robot.data.joint_pos[0, :3]
                rp = robot.data.root_pos_w[0]
                o0 = obs["policy"][0, :6]
                D(f"step {step:5d} · 에피소드 {ep_id}/{args_cli.episodes} "
                  f"· 명령 vx={cx:6.2f} · 실제 vx={vx:6.2f} · 평균이동 {float(dist.mean()):6.2f}m "
                  f"· 행동 |a|={float(action.abs().mean()):.4f}")
                # 관측 배치: lin_vel 0:3 · ang_vel 3:6 · gravity 6:9 · ★command 9:12 · joint_pos 12:24
                og = obs["policy"][0, 6:9]
                oc = obs["policy"][0, 9:12]
                D(f"          관절[0:3]={[round(v,4) for v in jp.tolist()]} "
                  f"· 루트위치={[round(v,3) for v in rp.tolist()]}")
                D(f"          중력[6:9]={[round(v,4) for v in og.tolist()]}  "
                  f"(수평이면 [0,0,-1] · 기울기 {float(torch.rad2deg(torch.arccos(-og[2].clamp(-1,1)))):.1f}도)")
                D(f"          ★명령[9:12]={[round(v,4) for v in oc.tolist()]}  "
                  f"← 매니저 {[round(v,3) for v in U.command_manager.get_command('base_velocity')[0].tolist()]}")

    env.close()

    # ── 집계 ──
    n = len(rows)
    if n == 0:
        print("[EVAL] ❌ 에피소드가 하나도 끝나지 않았다 · 결과 없음")
        return
    ok = sum(r["success"] for r in rows)
    fell = sum(r["fell"] for r in rows)
    to = sum(r["timeout"] for r in rows)
    mean_d = sum(r["distance_m"] for r in rows) / n
    mean_t = sum(r["time_s"] for r in rows) / n
    rate = 100.0 * ok / n

    os.makedirs(os.path.dirname(args_cli.out), exist_ok=True)
    with io.open(args_cli.out, "w", encoding="utf-8", newline="") as f:
        f.write("# FOOTHOLD 평가 파이프라인 v1\n")
        f.write(f"# 정책      : {policy_path}\n")
        f.write(f"# 태스크    : Isaac-Velocity-Rough-Unitree-Go2 (PLAY cfg, 커리큘럼 없음)\n")
        f.write(f"# 성공 정의 : 전진 {args_cli.goal_m}m 이상 · 넘어짐 없음 · 제한시간 "
                f"{cfg.episode_length_s}s 내\n")
        f.write(f"# 명령      : 전진 {args_cli.cmd_vx} m/s 고정 (에피소드 중 불변)\n")
        f.write(f"# 관측 노이즈: 끔 · 환경 {N}개 병렬 · step_dt {dt:.4f}s\n")
        f.write(f"# 에피소드  : {n}   통과율 {rate:.1f}%   넘어짐 {fell}   시간초과 {to}\n")
        f.write(f"# 평균 이동 : {mean_d:.2f} m   평균 시간 {mean_t:.2f} s\n")
        f.write("# distance_m 은 에피소드 중 시작점에서 떨어진 최대 거리(직선). "
                "전진 방향 성분이 아니라 평면 거리다.\n")
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    D("")
    D("=" * 56)
    D(f"★ 통과율  {rate:.1f}%   ({ok}/{n})")
    D(f"  넘어짐  {fell}   시간초과 {to}")
    D(f"  평균 이동 {mean_d:.2f} m · 평균 시간 {mean_t:.2f} s")
    D(f"  CSV: {args_cli.out}")
    D("=" * 56)
    dlog.close()


if __name__ == "__main__":
    main()
    simulation_app.close()



