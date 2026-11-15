# W55 Kit 확인기 H1 수정

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 · scripter 반영 · 2026-10-30
> 근거: `REVIEW-W55-verifier-1030.md` H1 · 고정 W55 Kit 산출 · CPU 시험
> 요지: 단계별 reset 적용, 실제 명령과 지도 소비, 보상 가중치를 확인기에 묶었다.
> 상태: CPU 검증 완료 · 새 코드의 Kit 짧은 확인 대기

## 변경

- `ex40_kit_smoke.py`는 B2, B3, T0 각각에서 양수의 reset 적용 수, 남은 이전 단계 env 수, 단계표의 명령 비율과 범위, 실제 `env.yaml`의 보상 가중치와 명령 설정을 대조한다. 실제 명령과 지도 소비 영수증도 요구한다.
- `continuous.py`, `mixed_command.py`, `start_runner.py`는 새 단계로 옮겨진 env의 reset 직후 명령 표본과 지도 선택을 단계 로그에 기록한다. T0에서는 `force_gt`가 꺼졌는지 확인하며, AdaSmpl 확률이 1이면 GT만 뽑혀도 허용한다. pred 실현을 거짓으로 요구하지 않는다.
- 깃발 env가 명령 단계 검사를 우회하지 않도록 실제 설정의 `flag_stride=0`, `dynamic_flags=false`를 단언한다.

## 반례와 CPU 결과

- 지정 첫 실패: 기존 확인기는 B2 `changed_envs=0` 변이도 PASS로 냈다. 수정 뒤 이 변이는 `positive reset adoption`으로 거절한다.
- B2에만 두 env 적용하고 B3, T0 reset을 없앤 변이와 `track_ang_vel=99.0` 변이를 각각 거절한다. 추가로 단계 비율, 지도 정책, 실제 소비 명령과 지도 플래그 변이를 거절한다.
- `CUDA_VISIBLE_DEVICES=''`와 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe`에서 지정 세 시험 파일 19 PASS. `pyflakes` 0건, `ruff check --select F` 0건, `git diff --check` 통과.
- `isaac311-moects`는 다른 `rsl_rl`을 참조해 기존 부모 저장본 시험에서 `store_code_state` import 오류가 났다. 설치된 실제 학습 환경인 `isaac311`로 재실행해 19 PASS를 확인했다.

## 실제 산출 읽기와 남은 확인

- 읽기 전용 기존 Kit smoke `C:/Users/AI-WS01/s2_lab/ex40/w55_kit_smoke_20261030_lead1`에서 새 확인기의 단계표, 실제 보상, reset 대조는 B2 253 env, B3 197 env, T0 175 env로 통과했다.
- 이 Kit 실행은 새 `stage_command_consumed`, `stage_map_consumed` 영수증을 생성하기 전 코드다. 새 확인기 전체는 `reset and consumed command counts differ: B2`로 거절한다. 따라서 새 코드 사본으로 Kit 짧은 확인을 다시 해야 H1 완결이다. 이 작업에서는 GPU나 Kit을 실행하지 않았다.
- verifier의 M1~M4는 이번 H1 지시 범위 밖이다. 미해결 항목으로 그대로 둔다.

## 변경 파일

`foothold_s2/ex40_kit_smoke.py`, `foothold_s2/curriculum/continuous.py`, `foothold_s2/commands/mixed_command.py`, `foothold_s2/runners/start_runner.py`, `foothold_s2/tests/test_w55_continuous_cpu.py`.
