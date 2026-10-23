"""legged_gym A1 기저 묶음(EX-15)의 Isaac Lab 보상 항 (SONNET-X15). Kit 안에서만 불린다. 계산은 `lg_core.py`."""

from foothold_s2.rewards import lg_core
from foothold_s2.rewards.start_rewards import collision_term

_CHECKED = {"done": False}


def collision_checked(env, sensor_cfg, threshold):
    """START 충돌 항(collision_term)과 같은 값. 첫 호출에서 calf · foot 이 서로 다른 강체이고 calf 만 벌점 대상인지 확인하고 run.log 에 이름표를 한 번 찍는다.
    맞지 않으면 예외로 멈춘다(조용히 정상 접지에 벌점을 주지 않는다)."""
    if not _CHECKED["done"]:
        sensor = env.scene.sensors[sensor_cfg.name]
        table = lg_core.check_collision_bodies(sensor.body_names, sensor_cfg.body_ids)
        print("[X15] 충돌 벌점 확인 통과:", table, flush=True)
        _CHECKED["done"] = True

    return collision_term(env, sensor_cfg, threshold)
