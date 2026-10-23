"""EX-26 env cfg (SONNET-X26): EX-23/25 환경 그대로 + 토크 벌점 가중치만 -1e-5 → -2e-4. Kit 안에서만 불린다. 기존 파일은 고치지 않는다.

까닭(lead 10/23): EX-11 · 23 · 25(START 보상)는 처음부터 «낮은 채 이동» 해 뒷다리를 뒤로 뻗은 기는 자세로 간다. 같은 환경에 NVIDIA 보상을 넣은
EX-16 · 19 · 21 은 811 처럼 300 회에 «낮게 서서 제자리» 였다. 두 보상 세트에서 자세에 직접 걸리는 가장 큰 차이가 토크 벌점의 비중이다
(811 300 회 토크 항 -0.093 / track_lin 0.75 = 12 % · EX-23 230 회 -0.0052 / 0.80 = 0.65 %). 몸을 낮추면 무릎 모멘트 팔이 길어져 토크² 가
커지므로, 이 비중이 작으면 웅크린 자세가 공짜다. -2e-4 는 legged_gym A1 · NVIDIA Go2 rough 값(START 표와 legged_gym 기본값은 -1e-5).
"""

from isaaclab.utils import configclass

from foothold_s2.tasks.s2_x23_cfg import FootholdS2X23EnvCfg


@configclass
class FootholdS2X26EnvCfg(FootholdS2X23EnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.rewards.joint_torques.weight = -2.0e-4
