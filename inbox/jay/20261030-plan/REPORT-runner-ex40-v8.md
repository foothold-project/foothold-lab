> 분류: 운영 · 평가 실행
> 작성: 오흥재 (runner 반영) · 2026-10-30
> 근거: WORKLIST D73 · lead 의 EX-40 v8 DR 의뢰 · analyst DR-RANGES-EX40-1030.md 경로 확인
> 요지: EX-40 v8 DR 일정 CPU 계약과 빈 범위 기동 차단 초안
> 상태: CPU 계약 시험 통과 · 범위표 미수신 · runtime 이벤트 연결 미구현 · Kit/GPU 미실행

# EX-40 v8 DR 일정 준비 보고

## 결과

전용 worktree `C:/mai/wt/foothold-lab/runner-ex40-v8`에서 v7 뒤에 분기해 작업했다. v7 worktree와 공유 체크아웃은 수정하지 않았다.

`foothold_s2/curriculum/ex40_dr.py`에 CPU 전용 일정 계약을 추가했다. D73에 명시된 update 구간은 B0 0~1500에서 배율 0, B1~B3c 1501~6000에서 0~0.5 선형 보간, 6001에서 1이다. D 길이 설정은 1500 또는 3000 update이며, T0는 D 직후 500 update다. 이에 따른 max_iterations는 각각 8001 또는 9501이다. 위 숫자는 D73 설계값이며 실측값이 아니다.

관측 잡음 배율은 `1 + s * (목표 - 1)`로 계산하며, 범위 보간과 재개 상태의 update·배율·설정 해시 일치를 CPU에서 확인한다. 마찰 0.2~1.2와 질량 변화 -1~3 kg는 기존 startup 값으로 YAML에 표시하고 이 모듈은 이를 변경하지 않는다. 이 값들은 D73에 제공된 설정 범위이며 새 계측 결과가 아니다.

## 실행 차단 사유

지정한 analyst 자료 `C:/mai/wt/foothold-lab/analyst-ame2/_out/reports/DR-RANGES-EX40-1030.md`를 확인했지만 파일이 없다. `ex40.yaml`에는 여섯 DR 범위 칸을 비워 두고 `runtime_adapter_status: not_implemented`로 표시했다. 범위가 비었거나 runtime adapter가 검증되지 않으면 `ex40_launch.py`와 실제 trainer가 Kit 생성 전에 실행을 거부하도록 차단을 넣었다.

따라서 이번 제출은 실제 reset 이벤트 등록, push interval 이벤트, `train_extra` update별 배율 및 실현 readback, Kit 확인기 연동을 완료하지 않았다. 범위표 없이 이 동작의 분포나 센서 노이즈를 추정하지 않았다. v7의 `continuous.py` 단계표도 바꾸지 않았다. 범위표가 도착해도 adapter 연결과 회귀 시험을 먼저 마치기 전에는 실행할 수 없다.

## 검증

- `python -m pytest -q foothold_s2/tests/test_ex40_dr_v8_cpu.py foothold_s2/tests/test_ex40_v7_continue_cpu.py`: 14 passed.
- CPU 알려진 입력: schedule 경계, 선형 중간값, L_D 두 설정, T0 500 update, smoke 0→0.5→1, noise 식, 수치 구조 보간, 설정 해시 재개 복원, 빈 범위 거절, 실제 trainer의 AppLauncher 전 기동 차단 순서를 확인했다.
- 범위가 채워진 값은 합성 fixture로만 validator를 시험했다. fixture 값은 제안 범위가 아니며 실행 설정으로 쓰지 않았다.
- Kit smoke와 GPU는 의뢰대로 실행하지 않았다. 실제 Isaac event 적용, 관측 noise 실현, push 적용 속도 및 물리 readback은 미확인이다.

## 변경 파일

- `foothold_s2/curriculum/ex40_dr.py`
- `foothold_s2/curriculum/ex40.yaml`
- `foothold_s2/ex40_launch.py`
- `foothold_s2/scripts/train_sol23f_common.py`
- `foothold_s2/tests/test_ex40_dr_v8_cpu.py`
- `inbox/jay/20261030-plan/REPORT-runner-ex40-v8.md`

이 보고서는 v8 DR 실행 준비를 완료했다고 주장하지 않는다. analyst 범위표 수신 뒤 reset adapter·기록·Kit checker를 구현하고 CPU 및 Kit 검증을 별도 재개해야 한다.
