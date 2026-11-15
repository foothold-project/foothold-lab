"""action 클립 17 (lead 10/21): 설정 한 줄을 학습과 평가가 같이 읽고, S1-b · 진단 판이 상속한다. Kit 없이 소스를 읽어 확인한다."""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(*parts):
    return open(os.path.join(ROOT, *parts), encoding="utf-8").read()


def test_runner_cfg_sets_clip_actions_17():
    source = _read("foothold_s2", "tasks", "agents", "s1_ppo_cfg.py")
    block = source.split("class S1aPPORunnerCfg")[1].split("@configclass")[0]

    assert re.search(r"^\s+clip_actions = 17\.0\s*$", block, re.M)


def test_derived_cfgs_do_not_override_it():
    source = _read("foothold_s2", "tasks", "agents", "s1_ppo_cfg.py")

    assert len(re.findall(r"^\s+clip_actions\s*=", source, re.M)) == 1       # 값을 정하는 줄은 한 곳뿐: 상속 판이 덮어쓰지 않는다
    assert "class S1bPPORunnerCfg(S1aPPORunnerCfg)" in source
    assert "class S1aDiagPPORunnerCfg(S1aPPORunnerCfg)" in source


def test_training_and_evaluation_both_read_the_cfg_value():
    assert "RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)" in _read("foothold_s2", "train_s1.py")
    assert 'clip_actions=built["agent_cfg"].clip_actions' in _read("foothold_s2", "eval", "adapters.py")
    assert '"clip_actions": _s1_clip_actions()' in _read("foothold_s2", "eval", "run_eval.py")
