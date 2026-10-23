"""EX-23 agent cfg (SONNET-X23): START 구조 G1. EX-11 agent 와 같은 PPO · 지각 설정에서 지도 입력만 켠다:
map_input reconstruction + force_gt True(AdaSmpl p=1 고정: IE 는 항상 정답 지도만 받는다, lead 10/22 결정) · est_mode learned · critic clean52 · clip 17 · START 명령 계약 · 1501 회 · 50 회마다 저장.
log_map_stats: IE 로 가는 지도 입력 통계를 map_stats.jsonl · run.log 에 남긴다(runners/map_stats.py)."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_ppo_cfg import S2X11PPORunnerCfg


@configclass
class S2X23PPORunnerCfg(S2X11PPORunnerCfg):
    save_interval = 50
    experiment_name = "foothold_s2_x23"
    perception: dict = {"microbatch_envs": 256, "replay_autocast": "none", "kl_fp32": False, "map_input": "reconstruction",
                        "est_mode": "learned", "critic_mode": "clean52", "log_action_stats": True, "log_kl": True, "log_reward_split": True,
                        "contract": "start", "stop_on_nonfinite": True, "log_map_stats": True,
                        "force_gt": True}                                                                    # lead 10/22: 정답 지도만(AdaSmpl p=1 고정, TR-Net 복원 노이즈 제외)
