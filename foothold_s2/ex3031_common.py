"""EX-30 · EX-31 Kit 스크립트가 같이 쓰는 기록 · 대조 함수 (창 1). 짧은 시험 스크립트(train_ex3031_smoke.py)의 같은 이름 함수와 내용이 같다.
isaaclab 을 import 하지 않아 CPU 에서도 불러 시험할 수 있다(Kit 객체는 인자로 받는다).
"""

from __future__ import annotations

import json
import os

from foothold_s2.runners.sol23f_runner import save_material_array, tensor_summary
from foothold_s2.runners.stage_transfer import file_sha256, yaml_pair_diff

AGENT_PAIR_IGNORE = ("log_dir", "device", "run_name", "max_iterations")                                      # 운영 칸. 처치는 perception.force_gt 하나(EX-31 은 부모와 같아 차이 없음)


def record_realized_physics(gym_env, env_cfg, log_dir, parent_ckpt):
    """train_sol23f_common 과 같은 기록(realized_material.json · realized_physics.json)을 남기고 부모 실행의 기록과 대조한다.
    구동기 값과 dynamic<=static 은 결정적이라 어긋나면 멈춘다. 질량 · 무게중심 · 재질 배열은 무작위 추출이라 같은지만 적는다."""
    robot = gym_env.unwrapped.scene["robot"]
    material = save_material_array(robot.root_physx_view.get_material_properties(), log_dir)
    floor = env_cfg.scene.terrain.physics_material
    material["floor_material_cfg"] = {"static_friction": floor.static_friction, "dynamic_friction": floor.dynamic_friction, "restitution": floor.restitution,
                                      "friction_combine_mode": floor.friction_combine_mode, "restitution_combine_mode": floor.restitution_combine_mode}
    material["floor_material_physx_readback"] = "API unverified; cfg recorded only"
    with open(os.path.join(log_dir, "realized_material.json"), "w", encoding="utf-8") as stream:
        json.dump(material, stream, ensure_ascii=False, indent=2)
    if not material["dynamic_le_static_all"]:
        raise RuntimeError("realized material violates dynamic<=static")
    physx = robot.root_physx_view
    physics = {"material": material, "masses": tensor_summary(physx.get_masses()), "com_poses": tensor_summary(physx.get_coms()), "actuators": {},
               "camera_and_delay": "recorded after first reset in step evidence"}
    for name, actuator in robot.actuators.items():
        physics["actuators"][name] = {"stiffness": tensor_summary(actuator.stiffness), "damping": tensor_summary(actuator.damping),
                                      "strength_scale": tensor_summary(actuator.strength_scale) if hasattr(actuator, "strength_scale") else "not_configured"}
    with open(os.path.join(log_dir, "realized_physics.json"), "w", encoding="utf-8") as stream:
        json.dump(physics, stream, ensure_ascii=False, indent=2)
    print("EX3031_REALIZED_PHYSICS " + json.dumps({k: physics[k] for k in ("masses", "com_poses", "actuators")}), flush=True)
    parent_file = os.path.join(os.path.dirname(os.path.abspath(parent_ckpt)), "realized_physics.json")
    check = {"parent_file": parent_file, "actuators_equal": None, "masses_equal": None, "com_equal": None}
    if os.path.isfile(parent_file):
        with open(parent_file, encoding="utf-8") as stream:
            parent = json.load(stream)
        check.update(actuators_equal=parent["actuators"] == json.loads(json.dumps(physics["actuators"])), masses_equal=parent["masses"] == json.loads(json.dumps(physics["masses"])),
                     com_equal=parent["com_poses"] == json.loads(json.dumps(physics["com_poses"])))
    with open(os.path.join(log_dir, "physics_vs_parent.json"), "w", encoding="utf-8") as stream:
        json.dump(check, stream, ensure_ascii=False, indent=2)
    if check["actuators_equal"] is not True:
        raise RuntimeError("구동기 값이 부모 실행 기록과 같다는 것을 확인하지 못했다: %r" % (check,))

    return check


def check_dumped_cfg_against_parent(log_dir, parent_ckpt, exp):
    """덤프한 env.yaml · agent.yaml 을 부모 실행의 같은 파일과 잎 단위로 대조해 json 으로 남기고, 처치 칸 밖 차이가 있으면 학습 전에 멈춘다."""
    pdir = os.path.join(os.path.dirname(os.path.abspath(parent_ckpt)), "params")
    env_diff = yaml_pair_diff(os.path.join(pdir, "env.yaml"), os.path.join(log_dir, "params", "env.yaml"))
    agent_diff = yaml_pair_diff(os.path.join(pdir, "agent.yaml"), os.path.join(log_dir, "params", "agent.yaml"), allowed_paths=("perception.force_gt",), ignore_names=AGENT_PAIR_IGNORE)
    with open(os.path.join(log_dir, "cfg_pair_diff.json"), "w", encoding="utf-8") as stream:
        json.dump({"exp": exp, "env_yaml": env_diff, "agent_yaml": agent_diff, "sha256": {"parent_env": file_sha256(os.path.join(pdir, "env.yaml")), "parent_agent": file_sha256(os.path.join(pdir, "agent.yaml")),
                   "child_env": file_sha256(os.path.join(log_dir, "params", "env.yaml")), "child_agent": file_sha256(os.path.join(log_dir, "params", "agent.yaml"))}}, stream, ensure_ascii=False, indent=2, default=str)
    if env_diff or agent_diff:
        raise RuntimeError("부모 params 와 처치 칸 밖의 차이가 있다(cfg_pair_diff.json): env %d칸 · agent %d칸" % (len(env_diff), len(agent_diff)))

    return 0
