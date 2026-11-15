> 분류: A/평가 · EX-42 N21
> 작성: runner · 2026-11-07
> 근거: W59 msg_f4a6a1b0a570 · N21 의견 OPINION-N21-184x-1107.md · approvals 및 ex42-prep 고정 파일
> 요지: 승인된 DR-on 측정기를 유지 점수와 분리한 record-only 영수증으로 연결
> 상태: CPU 구현·시험 완료 · Kit 환경 생성과 PhysX 실측은 미확인

# W59 N21 DR 기록 평가

## 변경

- `eval_map_modes`가 `--dr-mode on`을 소비하고, DR-on은 `--n21-record-only`가 없으면 Kit 전에 거절한다. DR-off 경로의 무작위화 비활성화는 기존대로 유지한다.
- DR-on은 EX-42 approvals의 명시 stage scale을 확인한다. 범위표는 `ex42-prep.yaml`이 가리키는 `ex41-fixed5000.yaml`만 허용하고, approvals·준비표·범위표의 SHA를 함께 기록한다. 고정본에서는 EX-42가 이 EX-41 T0-prime 물리 범위표를 참조한다.
- DR scale 1.0은 `gym.make` 뒤, 첫 reset 전에 env에 적용한다. 각 rollout 종료 후 env별 질량, 재료별 정적·동적 마찰 및 반발계수, 실제 COM pose와 기준 pose·차이, actuator별 joint gains·effort 한계와 multiplier, action delay의 substeps 및 초를 JSON에 보존한다. 필요한 readback이 없거나 유한하지 않으면 영수증을 만들지 않는다.
- 고정 L2·64 env selector는 연속 지형 7종과 flat 전용으로 분리했다. 각 selector는 `eval_gt`, `eval_pred`, `probe_prop_only`의 3 모드와 `fwd0.5`, `fwd1.0`, `spin+1.2`, `spin-1.2`, `back0.5`, `side+0.5`, `side-0.5`, `stop`을 요구한다. seed 기본값은 기존 CLI와 같이 42이며 지형 생성기와 agent/env cfg에도 전달한다.
- 별도 `n21_record_only.json`은 schema `foothold-ex42-n21-dr-record-only/1` 및 `record_only: true`를 표시한다. 기존 EX-40/EX-41 유지 소비자 코드는 수정하지 않았다. 기존 `require_dr_off_document`로 DR-on 영수증을 넣는 CPU 시험에서 거절을 확인했다.

## 사용 형태

승인된 checkpoint와 task를 넣어 각 시점에서 연속 지형 및 flat selector를 별도 실행한다. 부모 기준 실행은 `--n21-point parent_e0 --n21-stage EX42_0_T0_prime`, 단계 끝 실행은 `--n21-point stage_end --n21-stage <approved-stage-id>`를 쓴다. 두 실행 모두 `--n21-record-only --dr-mode on --dr-scale 1.0 --command-suite n21 --commands all --modes eval_gt,eval_pred,probe_prop_only --envs 64 --fixed-terrain --fixed-level 2`를 요구하고, selector는 각각 `--terrain-set n21-continuous`와 `--terrain-set n21-flat`이다.

## 검증 결과

- CPU: `python -m pytest foothold_s2/tests/test_n21_dr_record_cpu.py foothold_s2/tests/test_a_push_video_cpu.py foothold_s2/tests/test_ex41_dr_off_consumer_cpu.py foothold_s2/tests/test_w15_map_mode_cells.py foothold_s2/tests/test_course_map_modes.py --basetemp=D:/mai-tmp/runner/pytest-w59-final5 -p no:cacheprovider` 결과 **34 passed, 6.00s**.
- N21 답 아는 입력 시험은 명령·지도 모드·지형·env 수·L2·stage/point 일치, approvals stage scale, range source pin, 첫 reset 전 scale, env별 실제값 텐서 축과 비유한 readback 경로, 누락 command 거절, DR-on 유지 소비자 거절을 확인한다.
- `pyflakes`는 수정 파일의 기존 Isaac side-effect import 등 unused 경고 7건을 출력했다. 새 `n21_dr_record.py`, N21 시험, `eval_dr_mode.py`에는 해당 경고가 없다. `git diff --check`는 통과했다.
- 설치 `isaac311`에서 `configure_terrain` CPU 호출을 시도했으나 Isaac Lab terrain cfg import가 `ModuleNotFoundError: No module named 'pxr'`로 막혔다. 실제 생성기 적용, 첫 reset 이벤트, PhysX per-env readback은 Kit 전용이므로 미검증이며 GPU·Kit 실행은 하지 않았다.
- 추가 관련 시험 `test_ex40_dr_v8_cpu.py`는 14 passed, 1 failed였다. 실패는 `test_com_and_motor_reset_adapters_restore_nominal_before_sampling`의 fixture가 `env.device`를 제공하지 않아 `reset_base_com`에서 발생했고, 해당 함수는 이번 변경 diff에 없다. 이 시험의 기준 HEAD 통과 여부는 미측정이다.

## 남은 확인

Kit 예행에서 연속 7종 및 flat L2 타일 적용, 64 env의 실제 배치, reset 후 DR scale 1.0, PhysX 질량·마찰·COM 및 actuator·delay readback이 JSON과 일치하는지 확인해야 한다. W59 구현은 단계 끝 평가를 자동 등록하지 않으며, 실제 촬영·평가 기동과 결과 판독은 각각 승인된 운영자 및 analyst 영역으로 남긴다.
