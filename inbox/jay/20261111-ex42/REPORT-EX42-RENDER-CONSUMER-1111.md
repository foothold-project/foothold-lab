# EX-42 렌더 소비 경로 점검

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: runner-lx · 2026-11-11
> 근거: 팀장 결정 `0b51913f` · `record_c_layer.py` · EX-42 mesh manifests
> 요지: 기존 recorder는 EX-42 메시·체크포인트를 렌더하지 못하며, CPU 계획만 고정하는 초기 소비 경로를 추가했다.
> 상태: CPU 계획 확인 · Kit 렌더 연결 대기

## 판정

기존 `record_c_layer.parse_spec()`는 `B`, `TD`, `G0B`, `SB`만 받으며 EX42 프로필이 없다(`record_c_layer.py:52,464-485`). 촬영 실행에서도 `rough_go2_cfg.build_generator()`로 sparse 지형을 다시 만들고(`:1477-1492`), 또는 기존 B/SB 지형 생성기를 씁니다(`:1506-1518`). 따라서 EX-42의 고정 메시를 보존하지 않습니다. 해당 렌더 경로에는 EX-42 저장본 전용 체크포인트 준비, EX-42 mesh attach, family/kind 열 선택이 연결되어 있지 않습니다.

평가 도구 쪽은 다른 경로입니다. `eval_map_modes.py:214-224`가 `--mesh-dir`를 `ex42_mesh_eval.attach()`에 전달하고 공통 체크포인트 평가 로더를 부릅니다. 이 adapter는 학습용 ABCDE 결합 메시의 A 연속 23열 calibration 계약과, 별도 1행 V family 평가 전용 메시 계약으로 나뉩니다(`ex42_mesh_eval.py:14-38,77-89`). 둘 다 renderer의 환경 구성에서 호출되지 않습니다.

## 추가한 CPU 계획 경로

`foothold_s2.eval.ex42_render_plan`은 pinned `seed42_E0_c333` 결합 메시와 terrain manifest의 종류·열을 대조하고, 체크포인트 파일 SHA, 승인된 학습 종류, 현재 상한을 입력으로 받아 고정 렌더 요청을 출력합니다. 승인된 학습 종류는 호출자가 checkpoint/runtime 노출 기록에서 명시해야 하며, 미지정하거나 manifest에 없는 종류는 실패합니다. 요청은 `eval_gt`·`eval_pred` 각각 성공·실패·조감 슬롯 하나씩이며, 실제 성공/실패 표본 선택은 평가 영수증이 도착할 때까지 비워 둡니다.

실제 `seed42_E0_c333` manifest와 고정 규칙 입력으로 CPU plan-only를 실행했다. 39개 `(mesh family, terrain kind)`에서 7개 학습 종류는 L9 42건, 나머지 32개는 L0 192건으로 총 234요청이 나왔고, 메시 배열 SHA는 `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95`였다. 예시 체크포인트는 CPU 계획시험용 임시 파일이며 실제 EX-42 체크포인트가 아니다.

계획은 `selection_pending`, `selected_env_id=null`, `capture_ready=false`를 내보냅니다. 이는 의도한 fail-closed 출력입니다. 현재 recorder에 촬영 백엔드가 없으므로 이 PR만으로 GPU 대기열에 넣거나 렌더 성공을 주장할 수 없습니다. 실제 촬영에는 EX-42 전용 recorder backend가 `ex42_eval_mesh` attach와 동일 체크포인트 로더를 공유하고, 측정 결과에서 각 역할을 골라 프레임 검수 영수증까지 연결해야 합니다. 이 부분은 Kit 미실행 상태입니다.

## 재현

```bash
CUDA_VISIBLE_DEVICES='' /home/jay/miniforge3/envs/isaac311/bin/python -m pytest -q foothold_s2/eval/tests/test_ex42_render_plan_cpu.py -p no:cacheprovider --basetemp=/home/jay/mai/tmp/runner/ex42-render-plan-green
```

결과: **3 passed**. 거절 반례는 미등록 kind, L9 초과 상한, 기존 `record_c_layer`의 EX42 입력이다. `py_compile` 및 `git diff --check`도 통과했다. Kit/GPU 촬영은 실행하지 않았다.
