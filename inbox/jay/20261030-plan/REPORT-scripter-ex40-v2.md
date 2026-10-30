> 분류: A/정책학습
> 작성: scripter · 2026-10-30
> 근거: EX-40 D70 의뢰와 광선 정렬 후속, WORKLIST D68~D70, analyst 0111f9d5, CPU 시험과 설치 RayCaster 소스
> 요지: B0 보상과 정지 벌점, heading, 승급 점수, 실제 소비 기록, 발 광선 수직 정렬을 CPU에서 확인했다.
> 상태: CPU 고정 · Kit 미실행 · 팀장 승급 방식 결정 대기
> 판: v1.1

# EX-40 D70 고침 1차

## 1. 바뀐 동작

1차 코드 커밋 `f92b84a7`, 광선 정렬 고침 `cb1678b2`. 활성 학습 worktree를 건드리지 않고 별도 detached `C:/mai/wt/foothold-lab/scripter-ex40-v2-ray`에서 후속 작업했다. GPU와 Isaac은 실행하지 않았다.

| 영역 | 확인한 구현 |
|---|---|
| B0 보상 | 8항을 m0부터 등록. B1에 추가 보상 없음. `lin_vel_z`만 실제 B1 진입 회차를 원점으로 1500회 선형 변경. 상태 저장과 복원에 원점 포함. |
| 정지 | 정지 슬롯에서만 발 collision sphere 높이와 전용 ray 지면을 비교. 네 발 수직 힘과 DR 후 전체 질량을 사용. 첫 0.5초 선형 ramp. |
| heading | B arm 전진 절반의 시작 방향 유지 B0부터. B2부터 회전 목표 30 %. 각각 |wz| 상한 0.5와 1.5. A arm은 난수 세 배열을 소비하되 heading 출력 없음. |
| 승급 | `fixed`와 `gate` 설정. gate는 500회 이후 두 PASS 저장본 간격 250회, SHA·단계·시각 검증. 뒤의 FAIL이 PASS 및 대기 승급 취소. HOLD는 학습 지속. |
| 소비 증거 | 단계·13 슬롯·GT/PRED/OFF별 걸음과 종료, yaw와 y 부호별 종료, 발별 접촉과 소형 원시 힘·관절 샘플을 update마다 기록. |
| Kit smoke 준비 | 경계 B1=3, B2=6, B3=9, T0=12, 최종 `model_14.pt` 검증. |

## 2. 답 아는 CPU 증거

`isaac311-moects/python.exe -m pytest foothold_s2/tests/test_w55_continuous_cpu.py -q`: **11 passed**. 시험에는 10만 표본 B0 몫, 실제 parser 인자, 명목 보상과 B1 상대 일정, 네 발 mg/4 대 한 발 0 N, stop ramp, RR NPZ의 `valid & step>=50` 평균, 점수 PASS/FAIL 순서·저장 복원, pre-reset 단계 소비 집계, Kit 영수증 정상·변이 입력이 있다. 광선 시험은 설치 RayCaster의 yaw 분기와 수직 기본 방향을 읽고 발 roll 30도 입력에서 hit XY가 발의 local x −0.002 m 지점과 같은지 계산한다. 원래 `base` 값에서 지정 첫 FAIL, `yaw` 변경 뒤 PASS였다. NPZ는 옛 근사 간격 자료라 새 RayCaster의 Kit 성능 증명으로 쓰지 않았다. `ruff check --select F`와 `pyflakes`는 바뀐 Python 파일에서 0건, `git diff --check`도 0건이다.

실제 `run_ex40.sh`를 `LIVE=0`으로 A smoke, B smoke, A main 세 번 실행했다. A smoke 영수증은 `C:/Users/AI-WS01/s2_lab/ex40_v2_cpu_dry_a/receipts/ex40/A_smoke_20261030_184224_1088102/`, B smoke는 `C:/Users/AI-WS01/s2_lab/ex40_v2_cpu_dry_b/receipts/ex40/B_smoke_20261030_184244_1088137/`, A main은 `C:/Users/AI-WS01/s2_lab/ex40_v2_cpu_dry_main2/receipts/ex40/A_main_20261030_184302_1088175/`이다. 각각 `prestart_pass`, 실제 train parser 통과, 소스 git clean, `DRY: training not started`를 확인했다. main의 첫 시험은 종료시각을 너무 가깝게 주어 시간 관문에서 정확히 거절됐다. 이것은 코드 결함이 아니라 예정된 마감 상한 검사다.

## 3. 남은 확인

Kit 안에서는 새 네 발 RayCaster prim과 지면 mesh의 실제 유효 hit, 질량 readback, 보상 등록, 자연 reset 뒤 지도·명령 소비, model_14 저장을 확인해야 한다. 기존 `base`는 20 m 시작점과 방향을 발 roll·pitch로 함께 기울여 인접 단을 맞힐 수 있었다. 현재 `yaw`는 설치 소스상 시작점을 yaw만 회전하고 방향을 수직으로 유지한다. 실제 Kit 지형의 hit 유효성은 아직 미확인이다. 이번 CPU 결과를 Kit 합격으로 읽지 않는다.

승급 방식 `fixed` 또는 `gate`, stand 계수, arm A/B는 YAML의 설정값과 별개로 팀장 최종 결정 대기다. 성과 점수를 만들어 넣거나 학습을 시작하지 않았다. SHA 목록은 `EX40-V2-SHA256SUMS.txt`에 있다.

## 이력

| 판 | 날짜 | 변경 |
|---|---|---|
| v1.0 | 2026-10-30 | D70 1차 CPU 구현과 DRY. |
| v1.1 | 2026-10-30 | 발 ray를 yaw 정렬로 변경하고 30도 roll 반례를 추가. |
