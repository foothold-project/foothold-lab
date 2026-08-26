"""우리 Isaac Lab env 의 관절 순서·기본 자세·관측 스케일 실측 (#28 마지막 관문).

  왜: RoboGauge 공개 정책은 다리별 묶음(FL_h,FL_t,FL_c,FR_h,...) 순서다.
      우리 env 가 관절종류별 묶음(BFS)이면 재배열 없이는 붙일 수 없다.
      관행이 아니라 실측으로 확정한다 (foothold-lab research/robogauge-observation-mapping.md §5).

  Windows 함정 회피: Kit 이 stdout 을 삼키므로 결과는 파일로도 남긴다.
"""

import torch                       # noqa: F401 (Kit 로드 전 선점 import. Windows 우회)

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Go2 env 관절 순서 실측")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.headless = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""------ Kit 기동 후 ------"""
import io
import os

from isaaclab.envs import ManagerBasedRLEnv
from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.rough_env_cfg import UnitreeGo2RoughEnvCfg_PLAY

OUT = r"C:\isaac\IsaacLab\logs\probe_joint_order.txt"


def D(*msg):
    line = " ".join(str(m) for m in msg)
    print(line, flush=True)
    with io.open(OUT, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write("")

    cfg = UnitreeGo2RoughEnvCfg_PLAY()
    cfg.scene.num_envs = 1
    cfg.curriculum = None
    env = ManagerBasedRLEnv(cfg=cfg)

    robot = env.scene["robot"]
    D("[JOINT_NAMES]", robot.joint_names)
    D("[DEFAULT_JOINT_POS]", robot.data.default_joint_pos[0].tolist())

    # 관측 항목 구성·스케일: obs manager 의 policy 그룹 항목명과 차원
    om = env.observation_manager
    D("[OBS_TERMS]", om.active_terms["policy"])
    dims = om.group_obs_term_dim["policy"]
    D("[OBS_DIMS]", [tuple(d) for d in dims])

    # action 스케일
    D("[ACTION_CFG]", type(env.action_manager).__name__,
      getattr(cfg.actions.joint_pos, "scale", "?"),
      "use_default_offset=", getattr(cfg.actions.joint_pos, "use_default_offset", "?"))

    env.close()
    D("[DONE]")


if __name__ == "__main__":
    main()
    simulation_app.close()
