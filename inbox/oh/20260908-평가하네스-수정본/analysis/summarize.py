#!/usr/bin/env python3
"""play_eval.py 가 남긴 *_steps.csv 한 개를 한 줄 요약으로 줄인다.

사용법:  python3 summarize.py [--pass_x 20] [--runup 2.0] [--json <경로>] data/A2h_steps.csv [...]

[2026-09-07 추가] --json <경로> 를 주면 화면 출력과 똑같은 값을 metrics.json 으로도 남긴다.
  왜: 화면 출력은 사람만 읽을 수 있다. 실험이 열 개가 되면 "A2h 와 M1h 의 통과율을
  나란히 놓아라" 를 손으로 옮겨 적게 되고, 옮겨 적는 순간 오타가 결과가 된다.
  기계가 읽는 한 장을 실행 폴더에 같이 둔다 - 폴더 규칙(위키 05 · R-0q)의 metrics.json 이다.
  🔴 --pass_x 와 --runup 은 manifest.json 의 terrain.resolved.boundary_x_m 과
     runup_x_m 을 그대로 넣는다. 다르면 그 요약은 다른 기준으로 잰 숫자다.

--runup 은 평지/험지 경계 x [m]. 조주 지형(RUNUP_STONES_EVAL_CFG)이면 2.0 을 준다.
        주면 "험지 진입 후 몇 m 에서 넘어졌나" 줄이 추가로 나온다.

--pass_x 는 "통과" 로 셀 거리 [m]. 기본 4.0 은 stepping_stones 타일(8x8 m) 기준이다.
평지(FLAT_EVAL_CFG)는 타일이 40x16 m 라 앞으로 20 m 이므로 --pass_x 20 을 쓴다.

에피소드 = (env, episode) 한 쌍. env 10마리 x episodes 10회 = 100 에피소드.
통과 기준은 4.0 m - terrain_cfg.py 의 타일이 8x8 m 라 중심 출발 기준
징검다리가 앞으로 4 m 밖에 없다. 그 뒤는 border_width 20 m 의 평지다.
"""
import csv, sys, statistics as st, random
from collections import defaultdict


# ─── [2026-09-07 추가 S-2] env 균등가중 + env 클러스터 부트스트랩 ─────────────
#   왜 필요한가: 이 평가는 «벽시계 예산 고정 + 에피소드 길이 가변» 이다.
#   빨리 죽는 env 는 같은 시간에 에피소드를 더 많이 만들어 낸다.
#   M1 실측: env 별 에피소드 수가 [10,11,14,14,15,15,16,18,18,61] - 한 env 가 32%다.
#   그 env 의 낙상률이 0.98 이라, 전부 한 통에 넣고 세면(pooled) 71% 가 나오지만
#   env 를 균등하게 보면 60% 다. 11%p 가 «표본 편향» 이다.
#
#   그리고 오차를 에피소드 수로 계산하면 안 된다. 같은 env 안의 에피소드는 같은 타일
#   위에서 도는 것이라 서로 독립이 아니다. 독립 단위는 env(타일) 10개다.
#   그래서 env 를 통째로 복원추출하는 클러스터 부트스트랩으로 신뢰구간을 잡는다.
def _env_uniform_ci(per_env_num, per_env_den, n_boot=2000, seed=0):
    """env 별 (성공수, 시행수) -> (env 균등가중 평균, 95% CI 하단, 상단).

    per_env_num / per_env_den: {env: 값} 형태의 dict.
    반환값의 CI 는 env 를 복원추출한 분포의 2.5 / 97.5 백분위다.
    env 가 1개뿐이면 CI 를 못 만드므로 (평균, None, None) 을 준다.
    """
    envs = sorted(per_env_den)
    if not envs:
        return None, None, None
    rates = [per_env_num.get(e, 0) / per_env_den[e] for e in envs]
    mean = st.mean(rates)
    if len(envs) < 2:
        return mean, None, None
    rng = random.Random(seed)  # 씨앗 고정 = 같은 CSV 면 항상 같은 CI
    boots = []
    for _ in range(n_boot):
        pick = [rates[rng.randrange(len(rates))] for _ in rates]
        boots.append(st.mean(pick))
    boots.sort()
    lo = boots[int(0.025 * n_boot)]
    hi = boots[int(0.975 * n_boot) - 1]
    return mean, lo, hi
# ─── 여기까지 S-2 ───────────────────────────────────────────────────────────

PASS_X = 4.0  # [m] 징검다리 구간 끝. 여기를 넘으면 평지라 의미가 없다. --pass_x 로 바꾼다.
# ─── [2026-09-07 추가 S-1] 앞발 오프셋 ──────────────────────────────────────
#   [m] base(몸통 중심) -> 앞발 x 거리. play_eval.py 가 [EVAL] 줄에 실측해서 찍어 준다.
#   왜 필요한가: CSV 의 x 는 몸통 중심인데 지형과 먼저 만나는 건 앞발이다.
#   0.0 으로 두면 예전과 «똑같은» 숫자가 나온다(기존 요약과 비교가 깨지지 않는다).
#   --foot_dx 로 준다.
FOOT_DX = 0.0
# ─── 여기까지 S-1 ───────────────────────────────────────────────────────────
RUNUP = 0.0   # [m] 평지/험지 경계 x. 조주 지형(RUNUP_STONES_EVAL_CFG)은 2.0.
#             play_eval.py 가 [EVAL] 줄에 찍어 주는 값을 그대로 넣는다. --runup 으로 바꾼다.
#             0 이면 관련 줄이 안 나온다(기존 실험과 출력이 같아진다).


def summarize(path):
    eps = defaultdict(list)
    for r in csv.DictReader(open(path)):
        eps[(r["env"], r["episode"])].append(r)

    forward, first_fall_x, lat, falls, sits = [], [], [], [], []
    # ─── [2026-09-07 추가 S-3] env 별 분자/분모 ─────────────────────────────
    #   낙상률을 env 마다 따로 세어 둔다. 아래에서 균등가중 평균과 CI 를 만든다.
    _ep_n = defaultdict(int)     # env -> 에피소드 수
    _fall_n = defaultdict(int)   # env -> 낙상 에피소드 수
    # ─── [2026-09-08 추가 S-12] env 별 성공/진입 분자·분모 ──────────────────
    #   왜: PLAN.md 는 성공률을 «env 균등가중 + 클러스터 부트스트랩 CI» 로 내라고
    #   못 박았는데, 지금 CI 가 붙는 것은 낙상률뿐이었다. pass_count 는 에피소드를
    #   그냥 센 값이라 빨리 죽는 env 가 과대표집된다(위 S-2 주석과 같은 문제).
    #   판정은 base x 가 아니라 «앞발 x»(x + FOOT_DX) 로 한다. S-7 과 같은 기준이다.
    _entered_n = defaultdict(int)  # env -> 유효 진입한 에피소드 수 (앞발이 경계를 넘음)
    _succ_n = defaultdict(int)     # env -> 성공 에피소드 수 (낙상 없이 통과선 도달)
    # ─── 여기까지 S-12 ───────────────────────────────────────────────────────
    # ─── 여기까지 S-3 ────────────────────────────────────────────────────────
    peak_y = []  # 가장 많이 벗어난 순간의 y 를 "부호까지" 담는다.
    #  절댓값만 보면 왼쪽 3 m 와 오른쪽 3 m 가 구별이 안 돼 편향을 볼 수 없다.
    #  마지막 행의 y 를 쓰면 안 된다 - 종료 스텝은 이미 리셋된 뒤라 y ~ 0 이다(x 와 같은 함정).
    for _key, rows in eps.items():
        # ─── [2026-09-07 수정 S-4] 원본은 eps.values() 였다 ─────────────────
        #   env 별로 세려면 키(env, episode)의 env 가 필요해서 items() 로 바꿨다.
        _env = _key[0]
        _ep_n[_env] += 1
        # ─── 여기까지 S-4 ────────────────────────────────────────────────────
        rows.sort(key=lambda r: int(r["step"]))
        x = [float(r["x"]) for r in rows]
        forward.append(max(x))
        _ys = [float(r["y"]) for r in rows]
        lat.append(max(abs(v) for v in _ys))
        peak_y.append(max(_ys, key=abs))
        # 🔴 종료된 스텝의 x 를 그대로 쓰면 안 된다. env.step() 이 그 자리에서 리셋까지
        #    해 버리므로, 우리가 읽는 값은 이미 "다음 에피소드의 출발 위치"(x~0) 다.
        #    한 스텝 앞의 x 가 실제로 넘어진 지점이다.
        fell = [i for i, r in enumerate(rows) if int(r["term_base_contact"])]
        if fell:
            falls.append(1)
            _fall_n[_env] += 1  # [2026-09-07 추가 S-5] env 별 낙상 수
            first_fall_x.append(float(rows[max(fell[0] - 1, 0)]["x"]))
        # ─── [2026-09-08 추가 S-13] 성공/진입 판정 ──────────────────────────
        #   성공 = 낙상 없이 통과선(PASS_X)까지 앞발이 도달.
        #   진입 = 앞발이 평지/험지 경계(RUNUP)를 넘음. RUNUP=0 이면 전부 진입이다.
        #   🔴 「차선 안에서」 조건은 여기 넣지 않았다. 실패선을 5 cm 로 볼지 2.5 m 로
        #      볼지가 팀 안에서 미결이라, 기준을 박으면 기준이 바뀔 때 다시 돌려야 한다.
        #      횡이탈은 lateral_max_* 로 «원값» 을 따로 남긴다.
        _mx_foot = max(x) + FOOT_DX
        if _mx_foot >= RUNUP:
            _entered_n[_env] += 1
        if _mx_foot >= PASS_X and not fell:
            _succ_n[_env] += 1
        # ─── 여기까지 S-13 ───────────────────────────────────────────────────
        # 주저앉기: 몸통은 한 번도 안 닿았는데 허벅지에는 힘이 걸린 에피소드
        if not fell and max(float(r["thigh_force_N"]) for r in rows) > 1.0:
            sits.append(1)

    n = len(eps)
    print(f"\n=== {path}  (에피소드 {n}개)")
    print(f"  전진 최대 x 중앙값 : {st.median(forward):6.2f} m   (최대 {max(forward):.2f})")
    print(f"  {PASS_X:g} m 통과{' ' * max(0, 13 - len(f'{PASS_X:g}'))}: {sum(1 for v in forward if v >= PASS_X)} / {n}")
    print(f"  낙상(base_contact) : {len(falls)} 회")
    # ─── [2026-09-07 추가 S-6] pooled 와 env 균등가중을 «나란히» 찍는다 ──────
    #   둘 중 하나만 찍으면 어느 쪽 숫자인지 나중에 알 수 없게 된다.
    #   결론에 쓰는 것은 env 균등가중 쪽이다. pooled 는 예전 기록과 대조용으로만 남긴다.
    _fm, _flo, _fhi = _env_uniform_ci(_fall_n, _ep_n)
    print(f"  낙상률(전부 한 통)  : {len(falls) / n:.3f}   <- 빨리 죽는 env 가 과대표집된 값")
    print(f"  낙상률(env 균등)   : {_fm:.3f}"
          + (f"  95%CI [{_flo:.3f}, {_fhi:.3f}]  (env {len(_ep_n)}개 클러스터 부트스트랩)"
             if _flo is not None else "  (env 가 1개라 CI 없음)"))
    print(f"  env 별 에피소드 수  : {sorted(_ep_n.values())}"
          + ("   🔴 한 env 가 30% 넘게 차지한다" if max(_ep_n.values()) > 0.3 * n else ""))
    # ─── 여기까지 S-6 ────────────────────────────────────────────────────────
    # ─── [2026-09-08 추가 S-14] 성공률 두 가지 ─────────────────────────────
    #   unconditional : 분모 = 전체 에피소드
    #   valid-entry   : 분모 = 유효 진입한 에피소드만 (진입 자체를 실패한 것은 뺀다)
    #   한 env 가 한 번도 진입 못 하면 그 env 는 conditional 평균에서 «빠진다».
    #   0 으로 채우지 않는다 - 정의되지 않은 값이지 0 이 아니다.
    _sm, _slo, _shi = _env_uniform_ci(_succ_n, _ep_n)
    _cm, _clo, _chi = _env_uniform_ci(_succ_n, _entered_n)
    _n_entered = sum(_entered_n.values())
    print(f"  성공(무조건)       : {sum(_succ_n.values())} / {n}   "
          f"env 균등 {_sm:.3f}"
          + (f"  95%CI [{_slo:.3f}, {_shi:.3f}]" if _slo is not None else "  (CI 없음)"))
    print(f"  성공(유효진입 조건) : {sum(_succ_n.values())} / {_n_entered}  "
          + (f"env 균등 {_cm:.3f}"
             + (f"  95%CI [{_clo:.3f}, {_chi:.3f}]" if _clo is not None else "  (CI 없음)")
             + (f"   (진입 0인 env {len(_ep_n) - len(_entered_n)}개는 제외)"
                if len(_entered_n) < len(_ep_n) else "")
             if _cm is not None else "진입한 env 가 없다"))
    print(f"  성공 기준          : 앞발 x >= {PASS_X:g} m 도달 + 낙상 없음 "
          f"(진입선 {RUNUP:g} m, 앞발 오프셋 {FOOT_DX:+.3f} m)")
    # ─── 여기까지 S-14 ───────────────────────────────────────────────────────
    print(f"  첫 낙상까지 거리   : "
          + (f"중앙값 {st.median(first_fall_x):.2f} m" if first_fall_x else "낙상 없음"))
    print(f"  주저앉기(판정누락) : {len(sits)} / {n}")
    print(f"  횡방향 최대 이탈   : 중앙값 {st.median(lat):.2f} m / 최대 {max(lat):.2f} m")
    # 부호 = 방향. +y 는 왼쪽, -y 는 오른쪽. 중앙값이 0 근처면 쏠림이 없다는 뜻이다.
    print(f"  최대이탈 y(부호)   : 중앙값 {st.median(peak_y):+.2f} m   "
          f"(왼쪽 {sum(1 for v in peak_y if v > 0)} / 오른쪽 {sum(1 for v in peak_y if v < 0)})")
    if RUNUP > 0:
        # 조주 지형 전용. 평지에서 죽은 것과 돌에서 죽은 것을 갈라야 실험이 성립한다.
        # ─── [2026-09-07 수정 S-7] 판정 기준을 base x 에서 «앞발 x» 로 ────────
        #   원본: entered / died_flat / into 를 전부 base x 로 판정했다.
        #   그런데 지형과 먼저 만나는 것은 앞발이다. base 가 아직 평지 위에 있어도
        #   앞발은 이미 돌 위에 있다. 그 사이에 넘어지면 원본은 «평지 낙상» 으로 세고
        #   험지 낙상거리 집계에서 빼 버린다.
        #   M1 실측: 낙상 136건 중 61건(45%)이 이 경우였다. base x 중앙값 1.965 m,
        #   최소 1.885 m - 경계 2.0 m 에서 겨우 3~11 cm 모자란 값들이다.
        #   그 61건을 빼고 낸 "험지 진입 후 0.11 m" 는 잘린 분포의 중앙값이라 틀렸다.
        #   전부 넣고 다시 재면 (FOOT_DX=0 기준) 중앙값 +0.02 m 다.
        #
        #   FOOT_DX 를 더한 값이 «앞발 x» 다. FOOT_DX=0 이면 예전과 같은 숫자가 나온다.
        _contact_x = [v + FOOT_DX for v in first_fall_x]
        entered = sum(1 for v in forward if v + FOOT_DX >= RUNUP)
        died_flat = sum(1 for v in _contact_x if v < RUNUP)
        into = [v - RUNUP for v in _contact_x if v >= RUNUP]
        # 잘라 낸 것 없이 «모든» 낙상을 넣은 분포도 같이 낸다. 음수 = 경계 앞에서 넘어짐.
        _all_into = [v - RUNUP for v in _contact_x]
        print(f"  --- 조주 지형 (경계 x = {RUNUP:g} m, 앞발 오프셋 {FOOT_DX:+.2f} m) ---")
        print(f"  험지 진입          : {entered} / {n}")
        print(f"  평지에서 낙상      : {died_flat} 회"
              + ("   🔴 FOOT_DX 가 0 이면 이 값은 대부분 «경계 직전 낙상» 이지 평지 낙상이 아니다"
                 if died_flat and FOOT_DX == 0.0 else ""))
        print(f"  험지 진입 후 낙상거리 : "
              + (f"중앙값 {st.median(into):.2f} m / 최대 {max(into):.2f} m  (n={len(into)})"
                 if into else "해당 없음"))
        print(f"  낙상 깊이(전부)    : "
              + (f"중앙값 {st.median(_all_into):+.3f} m / 최소 {min(_all_into):+.3f} / "
                 f"최대 {max(_all_into):+.3f}  (n={len(_all_into)}, 음수=경계 앞)"
                 if _all_into else "낙상 없음"))
        # ─── 여기까지 S-7 ────────────────────────────────────────────────────

    # ─── [2026-09-07 추가] 화면에 찍은 것과 똑같은 값을 dict 로도 돌려준다 ────────
    #   왜 돌려주기만 하나: 파일로 쓰는 것은 아래 __main__ 이 한다. 이 함수는
    #   "한 CSV 를 숫자로 줄이는 일" 만 한다. 섞어 두면 나중에 이 함수를 다른 데서
    #   부를 때 원치 않는 파일이 생긴다.
    #   🔴 여기 담는 것은 전부 "잰 값" 이다. passed / failed 같은 판정 열은 넣지 않는다 -
    #      횡이탈 실패선을 5 cm 로 볼지 2.5 m 로 볼지가 팀 안에서 아직 미결이라,
    #      기준을 파일에 박아 두면 기준이 바뀔 때마다 실험을 다시 돌려야 한다.
    #      pass_count 만은 예외인데, 그 기준(pass_x_m)을 같은 파일에 함께 적어 두므로
    #      나중에 다른 기준으로 다시 세는 것이 가능하다.
    _out = {
        "source_csv": path,
        "n_episodes": n,
        "pass_x_m": PASS_X,                                   # 이 요약이 쓴 통과선
        "runup_x_m": RUNUP if RUNUP > 0 else None,            # 조주 경계. 0 이면 안 씀
        "forward_max_x_median_m": st.median(forward),
        "forward_max_x_max_m": max(forward),
        "pass_count": sum(1 for v in forward if v >= PASS_X),
        "fall_count": len(falls),                             # base 접촉으로 끝난 에피소드 수
        # ─── [2026-09-07 추가 S-8] 결론에 쓰는 것은 아래 3개다 ────────────────
        "fall_rate_pooled": len(falls) / n,                    # 예전 기록과 대조용
        "fall_rate_env_uniform": _fm,                          # 🔴 결론은 이 값으로 낸다
        "fall_rate_env_uniform_ci95": [_flo, _fhi],            # env 클러스터 부트스트랩
        "episodes_per_env": dict(sorted(_ep_n.items())),       # 표본 편향을 눈으로 보는 값
        "foot_dx_m": FOOT_DX,                                  # 이 요약이 쓴 앞발 오프셋
        # ─── 여기까지 S-8 ─────────────────────────────────────────────────────
        # ─── [2026-09-08 추가 S-15] 성공률 (PLAN.md 의 primary 지표) ──────────
        "success_count": sum(_succ_n.values()),
        "entered_count": _n_entered,
        "success_rate_env_uniform": _sm,                       # 분모 = 전체 에피소드
        "success_rate_env_uniform_ci95": [_slo, _shi],
        "success_rate_valid_entry_env_uniform": _cm,           # 분모 = 유효 진입만
        "success_rate_valid_entry_env_uniform_ci95": [_clo, _chi],
        "envs_with_no_entry": len(_ep_n) - len(_entered_n),
        # ─── 여기까지 S-15 ────────────────────────────────────────────────────
        "first_fall_x_median_m": st.median(first_fall_x) if first_fall_x else None,
        "sit_count": len(sits),                               # 종료 판정이 놓친 주저앉기
        "lateral_max_median_m": st.median(lat),
        "lateral_max_max_m": max(lat),
        "peak_y_median_m": st.median(peak_y),                 # 부호 = 쏠린 방향
        "peak_y_left_count": sum(1 for v in peak_y if v > 0),
        "peak_y_right_count": sum(1 for v in peak_y if v < 0),
    }
    if RUNUP > 0:
        # 조주 지형에서만 뜻이 있는 값. 아닐 때 0 으로 채우면 "평지에서 안 넘어졌다" 로
        # 잘못 읽힌다. 키 자체를 안 넣는다.
        _out.update({
            "entered_rough_count": sum(1 for v in forward if v >= RUNUP),
            "died_before_rough_count": sum(1 for v in first_fall_x if v < RUNUP),
            "fall_dist_into_rough_median_m": (
                st.median([v - RUNUP for v in _contact_x if v >= RUNUP])
                if [v for v in _contact_x if v >= RUNUP] else None
            ),
            # ─── [2026-09-07 추가 S-9] 자르지 않은 낙상 깊이 ────────────────
            #   위 값은 "경계를 넘은 낙상만" 의 중앙값이라 분포가 잘려 있다.
            #   아래는 모든 낙상을 넣은 값이다. 음수면 경계 앞에서 넘어진 것.
            "fall_depth_all_median_m": st.median(_all_into) if _all_into else None,
            "fall_depth_all_min_m": min(_all_into) if _all_into else None,
            "fall_depth_all_max_m": max(_all_into) if _all_into else None,
            # ─── 여기까지 S-9 ────────────────────────────────────────────────
        })
    return _out
    # ─── 여기까지 ─────────────────────────────────────────────────────────────


if __name__ == "__main__":
    argv = sys.argv[1:]
    # ─── [2026-09-07 수정] --json 추가 ────────────────────────────────────────
    #   원본: while argv[:1] in (["--pass_x"], ["--runup"]):
    #   옵션 이름 목록에 --json 을 더하고, 값을 변수에 받는 가지를 하나 늘렸다.
    #   argparse 를 쓰지 않는 이유: 이 스크립트는 표준 라이브러리만으로 Pod 에서도
    #   노트북에서도 그대로 돌아야 하고, 옵션이 셋뿐이다.
    _json_path = None
    # [2026-09-07 수정 S-10] 옵션 목록에 --foot_dx 를 더했다.
    while argv[:1] in (["--pass_x"], ["--runup"], ["--json"], ["--foot_dx"]):
        if argv[0] == "--pass_x":
            PASS_X = float(argv[1])   # 모듈 상수를 덮어쓴다
        elif argv[0] == "--json":
            _json_path = argv[1]      # metrics.json 을 쓸 자리
        elif argv[0] == "--foot_dx":
            FOOT_DX = float(argv[1])  # base -> 앞발 x [m]. play_eval 이 실측해 찍어 준 값
        else:
            RUNUP = float(argv[1])
        argv = argv[2:]
    # ─── 여기까지 ─────────────────────────────────────────────────────────────
    assert argv, __doc__
    _results = [summarize(p) for p in argv]

    # ─── [2026-09-07 추가] metrics.json 쓰기 ──────────────────────────────────
    if _json_path:
        import json  # 여기서만 쓰므로 이 자리에서 import 한다
        # 한 장의 모양을 항상 같게 둔다 - CSV 가 하나든 셋이든 runs 는 항상 리스트다.
        # 읽는 쪽이 "이번엔 dict 인가 list 인가" 를 분기하지 않아도 되게.
        with open(_json_path, "w", encoding="utf-8") as _f:
            json.dump({
                "schema": "foothold-eval-metrics/1",  # manifest 와 같은 방식의 판 표시
                "pass_x_m": PASS_X,                   # 이 파일 전체가 쓴 통과선
                "runup_x_m": RUNUP if RUNUP > 0 else None,
                "foot_dx_m": FOOT_DX,   # [2026-09-07 추가 S-11] 이 요약이 쓴 앞발 오프셋
                "runs": _results,
            }, _f, ensure_ascii=False, indent=2)
        print(f"\n[metrics] -> {_json_path}")
    # ─── 여기까지 ─────────────────────────────────────────────────────────────
