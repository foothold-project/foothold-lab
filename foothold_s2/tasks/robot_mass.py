"""로드 뒤 로봇 총질량 한 줄 (lead SC-9): 학습 자산이 공식 go2.usd(15.019 kg, fable 20t)와 같은지 본다.

`[MASS] tag: default <kg>, after DR mean <kg> (min .. max over envs), n_envs N` 를 찍는다.
default = 자산 처음 질량(짐 도메인 무작위화 전, `data.default_mass`), after DR = 지금 PhysX 값(env 마다 다름).
Kit 안에서 env 를 만든 직후에 부른다.
"""

import sys


def robot_mass_line(env, tag, asset_name="robot"):
    asset = env.scene[asset_name]
    default = asset.data.default_mass.sum(dim=-1)                       # (n_envs,)
    now = asset.root_physx_view.get_masses().sum(dim=-1)

    return ("[MASS] %s: default %.3f kg, after DR mean %.3f kg (min %.3f .. max %.3f over envs), n_envs %d"
            % (tag, float(default.mean()), float(now.mean()), float(now.min()), float(now.max()), int(now.numel())))


def log_robot_mass(env, tag, asset_name="robot"):
    """한 줄을 찍는다. 실패해도 학습 · 평가를 막지 않는다(그 사실을 줄로 남긴다)."""
    try:
        line = robot_mass_line(getattr(env, "unwrapped", env), tag, asset_name)
    except Exception as exc:                                              # noqa: BLE001
        line = "[MASS] %s: 읽지 못함 %r" % (tag, exc)

    print(line, flush=True)
    sys.stdout.flush()

    return line
