> 분류: A/정책학습 · 증거 (S0 기준선 표)
> 작성: sonnet-code 세션 (10/20 SC-1 · SC-2)
> 근거: foothold_s2/eval/ (하네스 커밋 d8437c05 이후), 원자료 C:/Users/AI-WS01/s2_lab/eval_new/s0/ (판마다 run_manifest.json · command.txt · 체크포인트 sha256), 41-EVAL-AXES · 51-S0-BASELINES
> 요지: NVIDIA · v2 · E1 세 판을 새 평가 도구로 축 1 (48칸) · 축 2 (아홉 칸 x 시드 42 · 43 · 44) · 축 3 (21칸 중 범위 밖 1칸 제외 20칸) 잰 표. 숫자는 원자료에서 `s0_tables.py` 가 센 것이고 손으로 쓴 숫자 없음
> 상태: 초안 · lead 검수 전 · START 시험지는 Kit 실행 미연결이라 이 표에 없음

# S0 기준선 표

| 파일 | 내용 |
|---|---|
| `axis1_cells.csv` | 판 x 48칸 (성분 넷 + R_body/S/J_body + Wilson) 과 평균 두 줄(48칸 · 범위 안 32칸) |
| `axis2_cells.csv` | 판 x 아홉 칸. `value`/`passed` 는 기본 시드 42, 옆에 시드 43 · 44 값과 `seeds_failed` (문턱 못 넘은 시드 수) |
| `axis3_cells.csv` | 판 x 지형군 x 방향 21칸. 범위 밖은 `status=out_of_range`. 듬성한 행 좌 · 우는 `basis=가정값 0.2 (31 임시)` |
| `axis3_by_terrain.csv` | 위를 지형별로 (평균대 · 빔처럼 따로 볼 때) |
| `compare_policies.csv` | 칸마다 세 판을 나란히 (축 1 overall, 축 3 `J_body|S` · `yaw_dev_rate` · `progress_capped`) |
| `adapter_fix_before_after.csv` | Isaac Lab 어댑터 수정(d8437c05) 전 · 후. 수정은 축 2 루프만 바꿨다 |
| `axis1_e1_vs_old_harness.csv` | E1 축 1 48칸 새 도구 대 옛 하네스 (48/48 차이 0) |

## 읽는 법 · 주의

- `R_body` 는 「몸통이 기준 거리(3 m)에 도달」 이다. 41 §5 의 「네 발이 유효 지지면 위」 조건은 넣지 않았다 (lead 결정).
- 축 3 진행 비율의 분모는 기준 거리 3 m, 도달 뒤 명령을 0 으로 바꿔 시간 T 까지 서 있게 하고 생존을 잰다.
- 방향 이탈(`yaw_dev`) = 실제 요각 변화와 명령이 만든 요각 변화의 차가 30도 초과. 칸 비율이 `yaw_dev_rate`. E1 은 앞 0.5 칸에서도 0.25~0.37 이다.
- 축 2 hold/joint_target_delta_tail 은 reset 난수만 바꿔도 문턱 0.01 을 넘나든다 (조사 기록: 하네스 HANDOFF). 시드 셋 열이 그 때문에 있다.
- `degenerate=True` 는 한 판 안에서 R · S · J 비율이 전부 0 이거나 전부 1 이라는 뜻일 뿐이다. 「모든 판에서」 인지는 `compare_policies.csv` 에서 세 판을 같이 봐야 한다.

## 새 도구 대 옛 값

- E1 축 1: 48칸 모두 같음, 4,800 판 판정 일치. E1 축 2: 아홉 칸 비트 일치. v2 축 2: 아홉 칸 비트 일치(turn 낙상 0.109375 로 실패까지).
- v2 · NVIDIA 축 1 은 1.0 · 1.5 m/s 32칸이 옛 sweep 과 정확히 같고 0.5 m/s 만 v2 3칸 · NVIDIA 9칸 어긋남(최대 0.06). 새 도구는 비트 단위 결정적임(반복 시험 2회 + 연쇄 결과 모두 같음)이라 옛 sweep 쪽 실행 조건 차이로 기록한다. 그 조건 자체는 미확인.
- 축 3 은 옛 값이 없다. 어댑터 수정 전 · 후 대표 8 일(4,200 판)이 비트 일치.

## 한 일의 순서 (잘못 잡은 것 포함)

1. hold 값이 evidence 의 3배: reset 난수 순서가 달랐음 → 옛 순서로 고정.
2. S0 연쇄 첫 실패: 파이썬 자식의 `bash` 가 WSL bash 로 잡힘(rc 127) → Git bash 절대 경로.
3. 음수 명령 `--cmd -0.5` 를 argparse 가 옵션으로 읽음(rc 2) → `--cmd=-0.5,0,0`.
4. v2 축 2 가 evidence 와 달랐음: Isaac Lab 경로는 명령을 쓴 뒤 관측을 다시 지어야 함 → 고치고 v2 · NVIDIA 축 2 를 다시 쟀다.
