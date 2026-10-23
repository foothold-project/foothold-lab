"""install_fixed_reset 이 Isaac reset_root_state_uniform 에 넘기는 값은 파이썬 float 이어야 한다.

numpy float64 가 pose_range 에 섞이면 torch.tensor 가 double 이 되어 `write_root_pose_to_sim` 이
'Float 대 Double' 로 죽는다 (N1d 병합 뒤 첫 Kit 예행에서 9 칸 전부 이 오류로 죽었다).
"""

from foothold_s2.eval import sparse_starts


def test_ready_plans_carry_plain_python_floats():
    for cmd in ((-0.3, 0.0, 0.0), (0.0, 0.2, 0.0), (0.0, -0.2, 0.0)):
        plan = sparse_starts.start_plan(0.5, cmd)

        for name, record in plan.items():
            if record["status"] != "ready":
                continue

            assert type(record["root_z_offset_m"]) is float, (name, cmd)
            assert type(record["spawn_root_z_m"]) is float, (name, cmd)
            assert type(record["yaw_rad"]) is float, (name, cmd)
