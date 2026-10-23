"""S1-b env: S2 의 듬성한 지형 side table 묶기에 «단계 시작 회차» 저장을 더한다. Kit 안에서만 불린다.

S1-b 는 S1-a 체크포인트에서 이어 시작하므로 common_step_counter 가 S1-a 끝(약 144,000)에서 이어진다. p_advance 의 T 를 0 부터 세려고
`stage_iteration_offset`(이어 시작한 회차)을 들고, 체크포인트에 같이 저장 · 복원한다(S1Runner 의 env 훅).
"""

from foothold_s2.tasks.s2_env import FootholdS2Env


class FootholdS1bEnv(FootholdS2Env):
    stage_iteration_offset = 0
    mass_log_tag = "S1b env"

    def foothold_state_dict(self):
        return {"stage_iteration_offset": int(self.stage_iteration_offset)}

    def foothold_load_state_dict(self, state):
        self.stage_iteration_offset = int(state["stage_iteration_offset"])
