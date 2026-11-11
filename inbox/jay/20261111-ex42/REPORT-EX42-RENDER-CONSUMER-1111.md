# EX-42 렌더 소비 경로

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: runner-lx · 2026-11-11
> 근거: 팀장 렌더 규칙 `0b51913f` · EX-42 E0 평가 영수증 · 결합 메시 manifest
> 요지: 평가 결과에서 EX-42 한 칸을 선택해 기존 record_c_layer로 넘기는 CPU 준비·검증 경로를 추가한다.
> 상태: CPU 확인 · Kit 촬영 대기

## 구현

기존 `record_c_layer`에는 EX-42 저장본과 결합 메시를 같은 평가 셀에서 읽는 소비 경로가 없었다. 새 `ex42_render_capture`는 요청, 체크포인트, 메시, map-mode JSON, NPZ 배정 해시를 서로 대조하고, 64 환경 평가 배열에서 요청된 kind · 열 · 레벨에 맞는 성공 또는 실패 환경을 고른다. 조감 셀은 명시적으로 지정해야 한다. 평가는 64 환경 · seed 42 · `fwd1.0` · eval_gt/eval_pred · 18초 계약이어야 하며, 요청이 맞지 않으면 거절한다.

`record_c_layer`는 공통 EX-41 체크포인트 로더와 `ex42_mesh_eval.attach`를 사용해 같은 정책·메시로 캡처하도록 연결됐다. 평가의 전체 64개 level/column 배정을 그대로 복원하고, 다른 로봇은 렌더에서 제외한다. 촬영 후 전체 프레임을 기존 감사기로 검사하고 영상, 화면 내 위치, robot instance 증거를 별도 JSON으로 남긴다. `--plan-only` 명령 준비기는 spec과 실행 명령을 출력하지만 Kit을 실행하지 않는다.

요청 목록의 학습 kind 상한 규칙은 PR #649에 별도로 남긴다. 이 backend 변경은 별도 브랜치/PR이다.

## 실측과 한계

실제 `seed42_E0_c333` 메시의 배열 SHA는 `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95`이며 76열 reset 표와 manifest kind가 일치했다. CPU plan-only에서 39개 kind 중 7개 학습 kind는 cap 5와 L9 각각 6 조합으로 84요청, 나머지 32개 비학습 kind는 L0 6조합으로 192요청, 총 276요청이다.

실제 E0 m250 map64 결과는 64환경 · seed42 · 300 step · 0.02초 tick이지만, 평가 배열은 A 연속 23열과 level 0~2만 포함한다. 따라서 cap5/L9 계획 셀의 성공·실패를 해당 결과에서 선택할 수 없다. 실제 요청에 맞는 평가 배열이 생기기 전까지 `capture_spec_from_evaluation`은 이를 거절한다. Kit 촬영·전 프레임 영상 검수는 아직 하지 않았다.

## CPU 확인

```bash
CUDA_VISIBLE_DEVICES='' /home/jay/miniforge3/envs/isaac311/bin/python -m pytest -q foothold_s2/eval/tests/test_ex42_render_plan_cpu.py -p no:cacheprovider --basetemp=/home/jay/mai/tmp/runner/ex42-render-backend-green
```

결과: **8 passed**. 검증 범위에는 계획 슬롯 생성, cap5/L9 요청, 실제 parser로 spec 수락, mesh 열 불일치 거절, 정확한 evaluation assignment 재생, 전체 프레임 감사의 정상·검정 화면 입력이 포함된다. py_compile, pyflakes, `git diff --check`도 통과했다. GPU/Kit은 실행하지 않았다.
