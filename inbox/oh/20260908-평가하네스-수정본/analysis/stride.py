"""발 접촉 CSV 에서 보폭을 «직접» 잰다. 가정 없이.

지금까지 쓰던 39 cm 는 평지 순항 구간의 몸통 z 진동 5.00 Hz 와 평균속도 0.985 m/s 에서
«트롯이다» 를 가정해 «유도» 한 값이다. 가설이지 측정이 아니다.
여기서는 발이 언제 어디에 닿는지를 그대로 세므로 그 가정이 필요 없다.

착지(touchdown) = contact 가 0 에서 1 로 «바뀌는» 순간.
  🔴 contact==1 인 스텝을 다 세면 «디디고 있는 동안» 이 전부 잡혀
     보폭이 0 에 가깝게 나온다. 전이만 세야 한다.
보폭 = 같은 발의 «연속 착지 지점» x 간격.
"""

import csv
import os
import statistics as st
from collections import defaultdict

# 출발 직후 한두 걸음은 정지에서 밀고 나가는 것이라 순항 보폭이 아니다. 그만큼 버린다.
X_MIN = 1.0


def analyze(feet_csv, x_min=X_MIN):
    tr = defaultdict(list)                      # (env, episode, foot) -> [(t, fx, contact)]
    with open(feet_csv) as f:
        for r in csv.DictReader(f):
            tr[(r["env"], r["episode"], r["foot"])].append(
                (float(r["t"]), float(r["fx"]), int(r["contact"])))

    strides, periods, duty, air = [], [], [], []
    for v in tr.values():
        v.sort()
        td, prev, on = [], 0, 0
        for t, fx, c in v:
            if c and not prev and fx > x_min:
                td.append((t, fx))
            on += c
            prev = c
        duty.append(on / len(v))                # 접지 비율 (duty factor)
        for i in range(1, len(td)):
            d = td[i][1] - td[i - 1][1]
            dt = td[i][0] - td[i - 1][0]
            # 물리적으로 말이 되는 것만. 뒤로 가거나 1.5 m 를 뛰는 건 접촉 튐이다.
            if 0.02 < d < 1.5 and 0.05 < dt < 2.0:
                strides.append(d)
                periods.append(dt)
    return strides, periods, duty


O = os.environ.get("STRIDE_OUT", "")
if not O:
    raise SystemExit("STRIDE_OUT 에 보폭 실험 결과 폴더를 지정해야 한다. 예: export STRIDE_OUT=<볼륨>/experiments/20260908_stride")

ROWS = [("v025", 0.25), ("v050", 0.50), ("v075", 0.75), ("v100", 1.00), ("v125", 1.25),
        ("v150", 1.50), ("v175", 1.75), ("v200", 2.00), ("v250", 2.50), ("v300", 3.00)]
print(f"{'명령속도':>8} {'착지수':>7} {'보폭중앙':>10} {'보폭평균':>10} {'표준편차':>10} "
      f"{'착지주기':>9} {'착지빈도':>9} {'접지비율':>9} {'속도검산':>9}")
for name, v in ROWS:
    p = f"{O}/{name}_s42/{name}_feet.csv"
    try:
        s, per, du = analyze(p)
    except FileNotFoundError:
        print(f"{v:8.2f}  (파일 없음)")
        continue
    if not s:
        print(f"{v:8.2f}  (착지 없음)")
        continue
    ms, mp = st.median(s), st.median(per)
    print(f"{v:8.2f} {len(s):7} {ms*100:9.1f}cm {st.mean(s)*100:9.1f}cm "
          f"{st.pstdev(s)*100:9.1f}cm {mp:8.3f}s {1/mp:8.2f}Hz "
          f"{st.mean(du):9.2f} {ms/mp:8.2f}")

print()
print("보폭중앙 = 같은 발의 연속 착지 x 간격 중앙값 (발 하나 기준)")
print("접지비율 = 한 발이 땅에 닿아 있는 시간 비율. 0.5 면 절반은 공중")
print("속도검산 = 보폭 / 착지주기. 명령속도와 맞아야 계측이 일관된 것이다")
print("🔴 학습 명령 범위는 lin_vel_x ∈ (-1.0, 1.0) 이라 1.25 는 «분포 밖» 이다")
