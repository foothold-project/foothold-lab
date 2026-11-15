# EX-42 E0 승인·측정 누락 대조

> 분류: 구현 검증
> 작성: verifier-lx · 2026-11-11
> 근거: planner EX42-V017-PREP-LINES-1111 A/B/C/E · 통합 9002c0eb · decisions.tsv 406, 412~414
> 요지: 이미 반영된 줄은 보존하고 E0 한정 승인·병합 증거·최신 메시 측정만 보완
> 상태: 확인됨 · 승인·측정 서류 범위 막음 0 · 실행용 terrain_manifest 연결은 별도

## 수정 전 대조 (9002c0eb)

| 줄 | 이미 반영 여부 | 이번 조치 |
|---|---|---|
| A evaluation_friction | 0.8/0.6 승인 있음 | 보존 |
| A q4_two_window_range | 식 승인·measured null·E1 전 확정 있음 | 보존, 실측 완료로 바꾸지 않음 |
| A next_jump_study_start | E4/E6b 조건 승인 있음 | 보존 |
| A terrain_manifest_measurements | 승인 있으나 seed42_ABCDE 구판 | seed42_E0_c333 원자료로 교체, 3072 대리 광선 측정이라는 한계 보존 |
| A runtime_integration | #600 구 HEAD·merged null | #600 f007b640, #615 9002c0eb 병합 증거 |
| B-1 | environment 6144 있음 | 보존 |
| B-2 | denominator 6144 있음 | 보존 |
| B-3 | require_graduation false·285348de 부모 채택 있음 | 보존 |
| B-4 | E0 m13000/model_1000 SHA 핀 있음 | 보존 |
| B-5 | preparation_measurements 구판 값 있음 | A와 같은 최신 원자료 값 |
| B-6 | 평균대·계단 물리 표시 제거됨 | 보존 |
| B-7 | E0 kind_task 전 종 push on/off 있음 | 보존 |
| B-8 | 평가 push_cells 기록·동일 마스크·n/a 있음 | 보존 |
| B-9 | 승인 SHA 7b931673 구판 | 승인 파일 수정 마지막에 raw bytes SHA 재계산 |
| B-10 | E L0 0.4/0.23 있음 | 보존 |
| B-11 | B rough 20도 굴곡·0.16 거칠기 분리 있음 | 보존 |
| C-1 | 6144·2 GPU·3072/rank·M3·NCCL_SHM_DISABLE=1 있음 | 보존 |
| C-2 | 기준선 예정 경로·planned_after_e0_local_update0 있음 | 보존, 아직 만들어진 증거 아님 |
| C-3 | approvals requirements만 옛 ex41_graduation_receipt | parent_adoption_decision으로 교체·결정 출처 명시 |
| C-4 | DR1.0 있음·push_mask 없음 | E0 kind_task의 off 종과 같은 목록 기록 |
| E-1 | ex42_prep 6144 검사 있음 | 보존 |
| E-2 | approved+merged 검사·ops 위임 있음 | 코드 보존, 입력만 병합 완료로 |
| E-3 | 채택 결정·E0 pin·실제 부모 파일 SHA 검사 있음 | 보존 |
| E-4 | #615 열 gate로 대체 | 지시대로 수정 안 함 |
| #615 exposure 1 | exposure_at_E0 있음 | 보존 |
| #615 exposure 2 | default exposure0 있음 | 보존 |
| #615 exposure 3 | default level_cap0 있음 | 보존 |
| #615 exposure 4 | positive family A, kinds_of continuous 있음 | 보존 |
| #615 exposure 5 | positive exposure1, level_cap5 있음 | 보존 |
| E0 승인 칸 | stage_e0_authorization 없음 | 미리 승인 b에 따라 E0 250회·m13000 한정 칸 추가 |
| F 정본 CG | 범위 밖 | 변경 없음 |

## 적용과 근거

- prep `:71~77`, `:568~588`: 새 aggregate 값 두 자리를 일치시키고 runtime #600/#615 병합 커밋을 기입했다. 새 값은 0.90625 GiB · 9.176870384999347 s · 687191753.0844679 rays/s. 원자료는 `/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333/aggregate_measurements.json`, 파일 SHA `27f05942b1f2437ec6c22f46de76edb01f17c4ac8e4d176ecbc2f6da6aa24f84`.
- 같은 폴더 실제 `terrain_mesh.npz`를 `load_combined_mesh`로 CPU 되읽기하여 vertex float32 + face int32 기하 SHA `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95`를 manifest와 직접 대조했다. **3072 env 대리 하향 광선 측정**이다. 6144 실센서 측정으로 승격하지 않았다.
- approvals `:6`, `:43~50`, `:63~79`: 부모 채택·push 제외 선언·E0 250회 한정 승인. DR 배율은 모두 1.0 보존. global production/automatic false 및 E1 이후 비승인 보존.
- 승인 근거는 `c85efabb`의 `inbox/jay/20261104-ex41-restart/decisions.tsv:413` 미리 승인 b. 원문 승인 시각이 `01:5x`라 `approved_at`에도 그 불완전 표기를 보존했다. 정확한 분·초를 발명하지 않았다.
- decisions `:406` 방식: 승인 파일 diff 대조 후 raw bytes SHA를 마지막에 계산, prep `:123`을 `7b93167330f8c065ef11e3dc0177194e5d4c2bc3040cb01c5b2a261888f677a8`에서 `c4c76916f8d126694c7c8c9be81430919d99cf09a27375379f727cc19c24f680`으로 재고정. 승인 파일에 주석 한 줄을 더한 반례는 SHA 불일치로 거절된다.
- EX-42.yaml은 이미 C-1/C-2가 있어 변경하지 않았다. 예정 기준선 파일은 생성 증거로 간주하지 않았다. E-1~E-3 생산 코드는 이미 반영되어 변경하지 않았다. E-4, F, EX-41 생산 코드, #615 exposure는 바이트 그대로다.

## CPU 확인

환경: isaac311 · `CUDA_VISIBLE_DEVICES=''` · `PYTHONDONTWRITEBYTECODE=1` · pytest 캐시 끔. GPU/Kit 실행 없음.

| 검사 | 실제 결과 |
|---|---|
| 수정 전 새 시험 3개 | 3 failed: E0 승인 없음, runtime 병합 미표시, 구판 메시 |
| prep/ops/E0 guards/speed-probe/신규 approval-pin 다섯 파일 | **128 passed in 5.29s** |
| 승인 파일 한 줄 추가 | stage-zero pin 거절 |
| E0 범위 251회 / 다른 부모 SHA / 이후 단계 승인 | 각각 scope differs 거절 |
| 공식 `ex42_preflight --dry-run` | rc0, 전체 기동은 계속 blocked; runtime/가정/채택 관련 막음은 없음 |
| 공식 `train_start.py --ex42_stage_e0_approved --ex42_stage_e0_dry_run` | **rc0 · stage_e0_preflight_passed · 3072/rank × world_size2=6144 · 250회 · 실제 부모 SHA 일치** |
| dry 실행 부작용 | app_launcher_started=false · training_requested=false, 지정 run/queue 생성 없음 |

시험 원출력: `/home/jay/mai/tmp/verifier-lx/e0-prep-1111/{red,green,final}.log`, `prep-dry.json`, `e0-dry-profile.log`.
처음 공식 CLI는 machine profile 미선택으로 거절됐고, `/home/jay/mai/foothold-linux.env`를 현재 subprocess에만 읽은 뒤 정상 dry 통과했다. 설치·설정 파일 변경은 없다.
기존 시험의 「아직 runtime 미병합」 세 기대와 「E0 승인 칸 없음」 기대만 현재 승인 상태로 고쳤다. `cell=False` 음성 fixture가 새 승인 칸을 명시적으로 지우도록 고쳤으며, 기존 누락·부정 승인 거절 시험은 통과한다. git dirty 여부를 보는 옛 시험은 실제 byte pin·전체 기동 차단 검사로 바꿨다.

## 남은 경계

**이번 승인·측정 서류 범위 막음 0. 전체 E0 기동 완료 판정 아님.**

실제 공식 dry에서 `training_blockers=[terrain_manifest_missing_or_invalid]`가 남았다. 이 검증에는 실행용 `terrain_manifest.json`을 주지 않았다. `mesh_manifest.json`과 `aggregate_measurements.json`은 실제 확인했지만 `read_e0_terrain_manifest`의 종별 치수·측정 계약과 다르므로 대신 넣지 않았다. lead는 최종 실행에서 유효한 별도 manifest를 연결해야 한다.
CLI dry의 score argv는 `unused-in-dry-preflight` 자리표시이며 그 사슬은 dry 조기 종료 뒤에 있다. 이번 결과는 score 사슬·출처 잠금·Kit 장착·두 GPU 실행을 검증한 결과가 아니다. q4 실측 수치와 update0 push 기준선 생성도 이번 범위 밖이며 각각 기존 null/예정 상태를 보존했다.
