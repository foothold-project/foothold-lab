"""평가 하네스의 판정·집계 로직. 시뮬레이터에 기대지 않는 순수 함수.

**스냅샷의 식을 그대로 옮겼습니다.** Candidate 스냅샷
`provenance/candidate-20260822/eval_generalization.py` 가 원본이고,
각 함수의 「스냅샷」 줄이 원본 행 번호입니다.

여기서 더한 것은 **관측 열 다섯과, 방향 판정의 자를 고르는 인자 하나**뿐입니다
(`ADDED_COLUMNS` · `episode_metrics(gate_progress_m=...)`).
그 인자를 안 주면 이 모듈은 스냅샷과 같은 값을 냅니다.

**관측 열은 판정에 하나도 안 들어갑니다.** `overall_success` 는 지금도 네 축
(`survival` · `progress` · `tracking` · `direction`)의 AND 이고 그대로 둡니다.
머리 접촉 열 셋은 «경고등»이지 판정이 아닙니다. 근거는
`docs/research/20260909-head-contact-observation.md`.

torch 도 Isaac 도 쓰지 않으므로 Windows 에서 그대로 돌아갑니다.
`tests/test_metrics.py` 가 스냅샷 원문을 다시 읽어 같은 값이 나오는지 고정합니다.

벡터는 평면 2성분 `(x, y)` 튜플입니다. 스냅샷이 `root_pos_w[env_id, :2]` 로
평면만 쓰기 때문입니다.
"""

# 스냅샷에 없던 열. 여기 있는 것만 Candidate 와 다르다 (#125 1번 · #99 2번 · 머리 접촉).
# 이 목록을 빼면 `RAW_COLUMNS` 는 스냅샷 543행의 키 순서와 정확히 같아야 한다.
ADDED_COLUMNS = (
    "peak_lateral_drift_m",
    "gate_lateral_drift_m",
    "head_contact_count",
    "head_contact_peak_n",
    "head_contact_first_s",
)

# 머리 접촉을 재는 링크. **Go2 USD 를 직접 열어 확인한 이름이다** `확인됨`.
#
# `sim/eval/probe_go2_bodies.py` 를 2026-09-09 에 돌린 결과가 근거다. Go2 는 강체가
# 19개이고, 그중 라이다·머리로 읽히는 이름은 이 둘뿐이다. 둘 다 충돌 메시를 하나씩
# 갖고 있어 접촉력이 실제로 잡힌다.
#
# **아이작 Go2 에는 `lidar` 라는 이름의 강체가 없다** `확인됨`. 실기 Go2 는 이 자리
# (머리 앞면)에 라이다가 얹힌다 (`docs/ROBOT-SPEC.md`). 그래서 열 이름을 `lidar_...`
# 로 두지 않았다. 시뮬에 없는 부품 이름을 열에 적으면 그 열이 조용히 거짓말을 한다.
# **재는 것은 머리 링크 접촉이고, 그 자리가 실기 라이다 자리라는 것이 쓰임새다.**
HEAD_BODY_NAMES = ("Head_upper", "Head_lower")

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
    "gate_lateral_drift_m",
    "velocity_mae_mps",
    "mean_reward_per_step",

    # 머리(= 실기 라이다 자리) 접촉 관측 셋. **판정에 안 들어간다.**
    # 스냅샷 열 뒤에 붙여서, 열 번호로 CSV 를 읽는 코드가 앞쪽에서 안 밀리게 한다.
    "head_contact_count",
    "head_contact_peak_n",
    "head_contact_first_s",
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


def forward_offset_m(start_xy, point_xy, forward_dir):
    """어느 한 순간의 전방축 전진거리. `lateral_offset_m` 의 짝.

    끝점만 보는 `forward_progress_m` 과 식이 같고 인자만 다릅니다.
    통과선을 언제 지났는지 찾으려면 순간값이 필요합니다.
    """
    return dot(displacement(start_xy, point_xy), forward_dir)


def gate_lateral_drift_m(start_xy, path_xy, forward_dir, gate_progress_m):
    """**전진이 통과선을 지나는 순간**의 좌우 이탈 절댓값. #99 2번.

    멘토 기준은 「목표점에 도달했을 때 좌우 5 cm」입니다. 목표점은 10 m 이고,
    에피소드가 끝나는 자리가 아닙니다. 20초를 걸으면 끝점은 20 m 근처라
    **끝점으로 재면 목표점이 아니라 그 두 배 지점을 재게 됩니다.**

    경로 표본에서 전진이 처음 `gate_progress_m` 이상이 되는 자리를 찾고,
    그 앞뒤 표본 사이를 **선형보간**해 정확히 통과선 위의 이탈을 냅니다.
    표본 간격은 스텝 하나(1.0 m/s 에서 약 2 cm)라 보간 구간이 짧습니다.

    통과선을 한 번도 못 넘겼으면 `None` 입니다. **0.0 이 아닙니다.**
    0.0 으로 돌려주면 「도달했고 완벽하게 곧았다」와 구별이 안 됩니다.
    """
    if not path_xy:
        return None

    previous = None

    for point in path_xy:
        forward = forward_offset_m(start_xy, point, forward_dir)
        lateral = lateral_offset_m(start_xy, point, forward_dir)

        if forward >= gate_progress_m:
            if previous is None:
                return abs(lateral)

            back_forward, back_lateral = previous
            span = forward - back_forward

            if span <= 0.0:
                return abs(lateral)

            t = (gate_progress_m - back_forward) / span

            return abs(back_lateral + t * (lateral - back_lateral))

        previous = (forward, lateral)

    return None


# ---------------------------------------------------------------- 머리 접촉 (관측 전용)

def head_contact_summary(step_forces_n, threshold_n, step_dt):
    """머리 링크가 몇 스텝이나 · 얼마나 세게 · 언제 처음 닿았나.

    **경고등이지 판정이 아닙니다.** 이 함수의 어떤 값도 `overall_success` 에
    들어가지 않고, 들어가서도 안 됩니다. 근거 셋은 아래에 적습니다.

    `step_forces_n` 은 스텝마다 머리 링크 두 개(`HEAD_BODY_NAMES`)에 걸린
    접촉력 크기의 **최댓값** 목록입니다(N). `None` 이면 「안 쟀다」는 뜻이고
    세 값 모두 `None` 입니다. **0 이 아닙니다.** 0 으로 돌려주면 「쟀는데 한 번도
    안 닿았다」와 구별이 안 됩니다. `gate_lateral_drift_m` 이 쓰는 규칙과 같습니다.

    | 돌려주는 것 | 무엇 |
    |---|---|
    | `count` | 힘이 문턱을 **넘은** 스텝 수. 「닿았나」 |
    | `peak_n` | 문턱과 무관한 최댓값. 「얼마나 세게」 |
    | `first_s` | 처음 넘은 스텝의 경과 시각(초). 안 넘었으면 `None` |

    **문턱을 `>` 로 봅니다.** 종료 조건 `mdp.illegal_contact` 가 같은 부등호를
    쓰기 때문입니다. 같은 자로 재야 「몸통은 종료시켰는데 머리는 몇 번 닿았나」가
    비교됩니다.

    **`peak_n` 은 문턱을 안 봅니다.** 나중에 팀이 「몇 N 부터 부서지는가」를
    확보하면, 이 열만으로 지나간 판을 **소급해서** 다시 걸를 수 있어야 합니다.
    문턱으로 미리 잘라 두면 그 기회가 사라집니다.
    """
    if step_forces_n is None:
        return {
            "head_contact_count": None,
            "head_contact_peak_n": None,
            "head_contact_first_s": None,
        }

    count = 0
    peak = 0.0
    first_index = None

    for index, force in enumerate(step_forces_n):
        if force > peak:
            peak = force

        if force > threshold_n:
            count += 1

            if first_index is None:
                first_index = index

    return {
        "head_contact_count": count,
        "head_contact_peak_n": peak,
        "head_contact_first_s": (
            None if first_index is None else first_index * step_dt
        ),
    }


def gate_direction_success(gate_lateral, max_lateral_drift):
    """통과선 위에서 방향을 지켰나. #99 2번.

    통과선을 못 넘겼으면(`None`) **실패입니다.** 도착하지 않았는데
    「도착했을 때 5 cm 안」을 통과시킬 수는 없습니다.
    """
    if gate_lateral is None:
        return False

    return bool(gate_lateral <= max_lateral_drift)


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

    **끝점이 목표점이 아닐 때는 이 자가 안 맞습니다.** 20초 규격에서는
    끝점이 20 m 인데 목표점은 10 m 입니다. 그때 쓰는 것이
    `gate_direction_success` 이고, 고르는 자리는 `episode_metrics` 의
    `gate_progress_m` 입니다 (#99 2번).
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
    gate_progress_m=None,
    head_contact_forces=None,
    head_contact_threshold_n=1.0,
    step_dt=0.0,
):
    """한 에피소드의 파생값 전부.

    스냅샷 473~541행을 한 자리에 모으고, 거기에 열 둘을 더했습니다
    (`ADDED_COLUMNS`). 나머지는 스냅샷과 같은 순서로 계산하므로 부동소수
    결과까지 같습니다.

    `path_xy` 는 에피소드 중 표본된 평면 위치들입니다. `None` 이면 끝점 하나만
    본 것으로 칩니다. 경로를 안 넘겼다고 이탈이 0 이었던 것은 아니기 때문입니다.

    **`gate_progress_m` 이 방향 판정의 자를 고릅니다** (#99 2번).

    | 값 | `direction_success` 를 무엇으로 재나 |
    |---|---|
    | `None` (기본) | 끝점 이탈. **스냅샷과 같습니다** |
    | 숫자 | 전진이 그 거리를 지나는 순간의 이탈 |

    기본값을 `None` 으로 둔 것은 뜻이 있습니다. 이 인자를 안 주면 이 함수는
    스냅샷과 **글자 그대로 같은 값**을 냅니다. Candidate 와의 동치가
    `tests/test_metrics.py` 로 계속 고정되고, 자를 옮기는 것은 부르는 쪽이
    명시적으로 골라야 하는 일이 됩니다.

    20초 규격에서는 하네스가 통과선 10 m 를 넣어 부릅니다. 20초를 걸으면
    끝점이 20 m 근처라, 끝점으로 재면 목표점의 두 배 지점을 재게 됩니다.

    **`head_contact_forces` 는 판정을 하나도 안 바꿉니다** (`head_contact_summary`).
    안 넘기면 세 열이 `None` 이고, 넘겨도 `overall_success` 는 그대로입니다.
    아래 `overall_success(...)` 호출에 인자가 넷뿐인 것이 그 보증이고,
    `tests/test_metrics.py` 가 같은 것을 시험으로 못 박습니다.
    """
    disp = displacement(start_xy, end_xy)

    forward = forward_progress_m(disp, forward_dir)
    lateral = lateral_drift_m(disp, forward_dir)

    sampled = (end_xy,) if path_xy is None else path_xy
    peak_lateral = peak_lateral_drift_m(start_xy, sampled, forward_dir)

    if gate_progress_m is None:
        gate_lateral = None
    else:
        gate_lateral = gate_lateral_drift_m(
            start_xy, sampled, forward_dir, gate_progress_m
        )

    ideal = ideal_distance_m(command_vx, eval_duration)
    floor = min_progress_m(min_progress_ratio, ideal)

    vel_mae = velocity_mae_mps(velocity_error_sum, sample_count)
    reward = mean_reward_per_step(reward_sum, sample_count)

    survival = survival_success(timed_out, terminated)
    progress = progress_success(forward, floor)
    tracking = tracking_success(vel_mae, max_velocity_mae)
    if gate_progress_m is None:
        direction = direction_success(lateral, max_lateral_drift)
    else:
        direction = gate_direction_success(gate_lateral, max_lateral_drift)

    head = head_contact_summary(
        head_contact_forces, head_contact_threshold_n, step_dt
    )

    return {
        # ★ 인자가 **넷**이다. 머리 접촉은 여기에 들어가지 않는다.
        #   AND 에 축을 더하면 성공률이 반드시 깎이고, 정책이 웅크리는 쪽으로
        #   선택된다. `docs/research/20260909-head-contact-observation.md` 참고.
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
        "gate_lateral_drift_m": gate_lateral,
        "velocity_mae_mps": vel_mae,
        "mean_reward_per_step": reward,
        "head_contact_count": head["head_contact_count"],
        "head_contact_peak_n": head["head_contact_peak_n"],
        "head_contact_first_s": head["head_contact_first_s"],
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
