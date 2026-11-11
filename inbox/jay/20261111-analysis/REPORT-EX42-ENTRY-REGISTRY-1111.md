> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: verifier-lx · 2026-11-11
> 근거: lead 19:53·19:55 이름 규약 · 원장 7121e018 · Refs #555
> 요지: 뒤 단계 입구 이름을 선행 판정기와 연결하고 materialize가 그 이름을 덮어쓰지 않게 한다.
> 상태: CPU 검증 · 실제 기동과 미구현 판정기는 별도

# 단계 입구와 레지스트리 연결

| 진입 단계 | prep·승인 칸의 입구 이름 | 해석 |
|---|---|---|
| E2 | flag_two_window | E1F 출구 |
| E3 | kind_two_window_e2 | E2 출구 |
| E4 | kind_two_window_e3 | E3 출구 |
| E5 | kind_two_window_e4 | E4 출구 |
| E6a | kind_two_window_e5 | E5 출구. M을 E5 졸업의 대체로 삼지 않음 |
| E6b | posture_two_window_e6a | E6a 출구 |
| M | stage_exit_v1 | 실제 source_stage_ids를 레지스트리에서 찾아 해당 단계 출구를 사용 |

`ex42_prep.entry_gate_adapter_ready`는 이름이 pending이 아니라는 이유만으로 준비 완료를 반환하지 않는다. 선행 단계의 `exit_judge`가 실제 레지스트리에 없거나, 이름이 없거나, 지정한 이름과 다른 판정기이면 false다. 기존 `ex42_auto_authorization`의 ready 검사에서 부모 파일을 열기 전에 기동을 거절한다. M resolver는 E5를 임의 선행 단계로 고정하지 않는다. 승인된 E0/E1의 map39 별칭과 기존 E1→E1F 별칭은 보존한다.

`ex42_stage_materialize._prepare`가 뒤 단계 이름을 모두 flag_two_window로 덮던 두 줄을 없앴다. 계획 표의 이름을 유지하고 승인 칸에도 그 이름을 기록한다. 다른 부모·범위·원장·출구 증거·transition 대조는 그대로다. 승인 파일 이름 변경 뒤 prep의 approval_sha256을 재고정했다.

## 검증과 미확인 경계

새 답 아는 입력 5개는 선언 이름, 모듈 결측 거절, 등록 뒤 허용, 다른 선행 판정기 거절, 자동 기동의 부모 I/O 전 거절, 실제 materialize의 이름 보존을 확인한다. registry 대조를 옛 `name != pending`으로 바꾼 제거본은 3개 시험이 실패했다. materialize의 flag_two_window 덮어쓰기를 되살린 제거본은 이름 보존 시험이 실패했다. 원출력은 `/home/jay/mai/tmp/verifier-lx/entry-registry-1111/`에 보존한다.

이 PR은 E2 이후 출구 판정기 구현을 만들지 않는다. 검증 시작점에서 등록된 실제 판정기는 map39_e0·map39_e1_two_window·flag_two_window뿐이다. E3 이후 입구는 scripter가 대응하는 출구 모듈과 선행 단계 exit_judge를 연결하기 전까지 거절된다. M의 enabled=false와 빈 실제 source·부모·영수증 칸도 이 PR에서 채우지 않는다. 따라서 이름 연결 완료를 전체 자동 사슬의 실행 완료로 읽으면 안 된다. GPU·Kit·운영 plan·실제 학습 사본은 건드리지 않았다.

승인·표·materialize·자동 기동 연결 회귀 10개 파일 최종 결과: **202 passed in 83.93s (0:01:23)**, skip·실패 없음. 신규 5개 시험을 포함한다. 변경 Python 다섯 파일 pyflakes와 `git diff --check` 통과. 이번 가지에서는 전체 EX-42를 반복하지 않고 변경 소비 경계의 회귀만 실행했다. 선행 #708 최종 머리에서는 전체 EX-42 1096 passed·3 skipped를 별도 확인했다. 승인 SHA `b0f8689736c875eb6d074535c8ea579689c4710342a19d829f896f75b3d92308`, prep SHA `af950d2d1a9054da38c41b6c61fd2e0e79f94998aa4527e6561f55e111947752`를 직접 다시 계산해 pin 일치를 확인했다.
