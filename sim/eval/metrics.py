"""평가 하네스의 판정·집계 로직. 시뮬레이터에 기대지 않는 순수 함수.

**동작을 바꾸지 않았습니다.** Candidate 스냅샷
`provenance/candidate-20260822/eval_generalization.py` 의 식을 그대로 옮긴 것입니다.
각 함수의 「스냅샷」 줄이 원본 행 번호입니다.

torch 도 Isaac 도 쓰지 않으므로 Windows 에서 그대로 돌아갑니다.
`tests/test_metrics.py` 가 스냅샷 원문을 다시 읽어 같은 값이 나오는지 고정합니다.

벡터는 평면 2성분 `(x, y)` 튜플입니다. 스냅샷이 `root_pos_w[env_id, :2]` 로
평면만 쓰기 때문입니다.
"""

# 스냅샷에 없던 열. 여기 있는 것만 Candidate 와 다르다 (#125 1번).
# 이 목록을 빼면 `RAW_COLUMNS` 는 스냅샷 543행의 키 순서와 정확히 같아야 한다.
ADDED_COLUMNS = ("peak_lateral_drift_m",)

# 원시 CSV 열 순서. `ADDED_COLUMNS` 를 뺀 나머지가 스냅샷 543행의 키 순서다.
RAW_COLUMNS = (
    "terrain",
    "env_id",
    "episode",
    "start_x_offset_m",
    "start_y_offset_m",
    "start_yaw_deg",
    "overall_success",
    "survival_success",
    "progress_success",
    "tracking_success",
    "direction_success",
    "termination_reason",
    "duration_s",
    "forward_progress_m",
    "ideal_distance_m",
    "progress_ratio",
    "lateral_drift_m",
    "peak_lateral_drift_m",
    "velocity_mae_mps",
    "mean_reward_per_step",
)

# 요약 CSV 열 순서. 스냅샷 272행 딕셔너리의 키 순서와 같아야 한다.
SUMMARY_COLUMNS = (
    "terrain",
    "episodes",
    "overall_success_rate",
    "survival_rate",
    "progress_success_rate",
    "tracking_success_rate",
    "direction_success_rate",
    "mean_forward_progress_m",
    "mean_lateral_drift_m",
    "mean_velocity_mae_mps",
    "mean_episode_duration_s",
    "mean_fall_time_s",
    "mean_reward_per_step",
)


# ---------------------------------------------------------------- 기하

def dot(a, b):
    """평면 내적. 스냅샷의 `torch.dot` 자리."""
    return a[0] * b[0] + a[1] * b[1]


def displacement(start_xy, end_xy):
    """시작점에서 끝점까지의 변위 하나. 스냅샷 473행.

    **경로를 더하지 않습니다.** 끝점에서 시작점을 뺀 벡터입니다.
    문서가 오래 「누적·적분」이라 적어 온 자리이고, 그것이 오기입니다 (#125 7번).
    """
    return (end_xy[0] - start_xy[0], end_xy[1] - start_xy[1])


def lateral_axis(forward_dir):
    """전방축을 좌로 90도 돌린 축. 스냅샷 480~485행."""
    return (-forward_dir[1], forward_dir[0])


def forward_progress_m(disp, forward_dir):
    """전방축 끝점 전진거리. 스냅샷 475~478행."""
    return dot(disp, forward_dir)


def lateral_drift_m(disp, forward_dir):
    """측면축 끝점 이탈의 절댓값. 스냅샷 487~489행."""
    return abs(dot(disp, lateral_axis(forward_dir)))


def lateral_offset_m(start_xy, point_xy, forward_dir):
    """어느 한 순간의 측면축 이탈. **부호가 남습니다.**

    스냅샷에는 없는 함수입니다. 스냅샷은 끝점 하나만 보고 곧바로 `abs` 를 씌웁니다.
    최댓값을 집으려면 순간값이 필요하고, 어느 쪽으로 벗어났는지는 진단에 쓰입니다.
    """
    return dot(displacement(start_xy, point_xy), lateral_axis(forward_dir))


def peak_lateral_drift_m(start_xy, path_xy, forward_dir):
    """경로 전체에서 가장 크게 벗어난 측면 이탈의 절댓값. #125 1번.

    **관측용입니다. 성공 판정에 쓰지 마십시오.** 판정은 멘토 기준대로 끝점입니다
    (`direction_success`).

    좌우 어느 쪽으로 벗어났든 크기만 봅니다. 표본이 하나도 없으면 0.0 입니다.

    **이름을 `max` 가 아니라 `peak` 으로 둔 이유.** 하네스에는 이미
    `--max_lateral_drift` 라는 **문턱값**이 있습니다. 관측된 최고값을
    `max_lateral_drift_m` 이라 부르면 CSV 열과 인자가 한 글자 차이가 되어
    「이 숫자가 재본 값인가 기준값인가」가 헷갈립니다. `#125` 본문의 말은
    「최대 좌우 이탈」이고 뜻은 그대로입니다. 이름만 갈랐습니다.
    """
    largest = 0.0

    for point in path_xy:
        offset = abs(lateral_offset_m(start_xy, point, forward_dir))

        if offset > largest:
            largest = offset

    return largest


# ---------------------------------------------------------------- 기준값

def ideal_distance_m(command_vx, eval_duration):
    """명령을 완전히 따랐을 때의 거리. 스냅샷 372행."""
    return command_vx * eval_duration


def min_progress_m(min_progress_ratio, ideal_distance):
    """통과로 치는 최소 전진거리. 스냅샷 373행."""
    return min_progress_ratio * ideal_distance


def progress_ratio(forward, ideal_distance):
    """이상 거리 대비 비율. 스냅샷 531~535행. 0 나눗셈은 0.0 으로 막는다."""
    return forward / ideal_distance if ideal_distance > 0.0 else 0.0


# ---------------------------------------------------------------- 평균

def step_count(sample_count):
    """0 나눗셈을 막은 스텝 수. 스냅샷 491행."""
    return max(int(sample_count), 1)


def velocity_mae_mps(velocity_error_sum, sample_count):
    """스텝당 평균 속도 오차. 스냅샷 493~495행."""
    return velocity_error_sum / step_count(sample_count)


def mean_reward_per_step(reward_sum, sample_count):
    """스텝당 평균 보상. 스냅샷 497~499행."""
    return reward_sum / step_count(sample_count)


# ---------------------------------------------------------------- 판정 5축

def survival_success(timed_out, terminated):
    """넘어지지 않고 제한 시간을 채웠나. 스냅샷 503~506행."""
    return bool(timed_out and not terminated)


def progress_success(forward, min_progress):
    """충분히 전진했나. 스냅샷 508~510행."""
    return bool(forward >= min_progress)


def tracking_success(vel_mae, max_velocity_mae):
    """명령 속도를 따랐나. 스냅샷 512~514행."""
    return bool(vel_mae <= max_velocity_mae)


def direction_success(lateral, max_lateral_drift):
    """방향을 지켰나. 스냅샷 516~518행.

    **끝점 이탈로 봅니다.** 옆으로 크게 밀렸다가 돌아오면 이 판정은 통과합니다.
    그 흔들림을 보려고 #125 1번이 최대 이탈 열을 따로 더합니다.
    """
    return bool(lateral <= max_lateral_drift)


def overall_success(survival, progress, tracking, direction):
    """네 축을 모두 통과했나. 스냅샷 520~525행."""
    return bool(survival and progress and tracking and direction)


def termination_reason(timed_out):
    """종료 사유. 스냅샷 537~541행."""
    return "timeout" if timed_out else "base_contact"


# ---------------------------------------------------------------- 한 판 묶기

def episode_metrics(
    start_xy,
    end_xy,
    forward_dir,
    velocity_error_sum,
    reward_sum,
    sample_count,
    elapsed_s,
    timed_out,
    terminated,
    path_xy,
    command_vx,
    eval_duration,
    min_progress_ratio,
    max_velocity_mae,
    max_lateral_drift,
):
    """한 에피소드의 파생값 전부.

    스냅샷 473~541행을 한 자리에 모으고, 거기에 `peak_lateral_drift_m` 하나를
    더했습니다. 스냅샷과 다른 것은 그 열 하나뿐입니다 (`ADDED_COLUMNS`).
    나머지는 스냅샷과 같은 순서로 계산하므로 부동소수 결과까지 같습니다.

    `path_xy` 는 에피소드 중 표본된 평면 위치들입니다. `None` 이면 끝점 하나만
    본 것으로 칩니다. 경로를 안 넘겼다고 이탈이 0 이었던 것은 아니기 때문입니다.
    """
    disp = displacement(start_xy, end_xy)

    forward = forward_progress_m(disp, forward_dir)
    lateral = lateral_drift_m(disp, forward_dir)

    sampled = (end_xy,) if path_xy is None else path_xy
    peak_lateral = peak_lateral_drift_m(start_xy, sampled, forward_dir)

    ideal = ideal_distance_m(command_vx, eval_duration)
    floor = min_progress_m(min_progress_ratio, ideal)

    vel_mae = velocity_mae_mps(velocity_error_sum, sample_count)
    reward = mean_reward_per_step(reward_sum, sample_count)

    survival = survival_success(timed_out, terminated)
    progress = progress_success(forward, floor)
    tracking = tracking_success(vel_mae, max_velocity_mae)
    direction = direction_success(lateral, max_lateral_drift)

    return {
        "overall_success": overall_success(survival, progress, tracking, direction),
        "survival_success": survival,
        "progress_success": progress,
        "tracking_success": tracking,
        "direction_success": direction,
        "termination_reason": termination_reason(timed_out),
        "duration_s": elapsed_s,
        "forward_progress_m": forward,
        "ideal_distance_m": ideal,
        "progress_ratio": progress_ratio(forward, ideal),
        "lateral_drift_m": lateral,
        "peak_lateral_drift_m": peak_lateral,
        "velocity_mae_mps": vel_mae,
        "mean_reward_per_step": reward,
    }


# ---------------------------------------------------------------- 지형별 집계

def summarize(rows, terrain_names):
    """지형별 요약 행. 스냅샷 240~290행.

    `rows` 는 원시 행 목록입니다. 수치 열은 `float()` 로 되읽으므로 문자열이어도
    되지만, **판정 열은 실제 불리언이어야 합니다.** 스냅샷이 `int(r[...])` 를 쓰는데
    CSV 에서 되읽은 `"True"` 는 `int()` 가 받지 못합니다. 스냅샷과 같은 제약입니다.
    """
    grouped = {}

    for row in rows:
        grouped.setdefault(row["terrain"], []).append(row)

    summary_rows = []

    for terrain_name in terrain_names:
        episodes = grouped.get(terrain_name, [])

        n = len(episodes)

        def rate(key):
            return sum(int(r[key]) for r in episodes) / n

        def mean(key):
            return sum(float(r[key]) for r in episodes) / n

        failed = [r for r in episodes if not bool(r["survival_success"])]

        if failed:
            mean_fall_time = sum(float(r["duration_s"]) for r in failed) / len(failed)
        else:
            mean_fall_time = ""

        summary_rows.append(
            {
                "terrain": terrain_name,
                "episodes": n,
                "overall_success_rate": rate("overall_success"),
                "survival_rate": rate("survival_success"),
                "progress_success_rate": rate("progress_success"),
                "tracking_success_rate": rate("tracking_success"),
                "direction_success_rate": rate("direction_success"),
                "mean_forward_progress_m": mean("forward_progress_m"),
                "mean_lateral_drift_m": mean("lateral_drift_m"),
                "mean_velocity_mae_mps": mean("velocity_mae_mps"),
                "mean_episode_duration_s": mean("duration_s"),
                "mean_fall_time_s": mean_fall_time,
                "mean_reward_per_step": mean("mean_reward_per_step"),
            }
        )

    return summary_rows
