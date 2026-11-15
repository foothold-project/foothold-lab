# EX-42 E2 깃발 메시 결측과 원본 보존 사본

> 분류: 실험
> 작성: 오흥재 · 2026-11-11
> 근거: 통합 3c3de50e · scripter PR #713 7f222a3a · 실제 E0 메시 CPU 되읽기 · 이슈 #714
> 요지: E1F 재핀은 깃발 메시를 만들지 않는다. 원본 기하·측정값을 보존한 별도 깃발 메시와 실행 manifest를 준비했다.
> 상태: CPU 검증 완료 · GPU/학습 기동 없음 · E2 운영 경로 연결은 runner/lead 확인 필요
> 판: v1.0

## 1. 질문 셋의 답

**확인됨: 원본 E0에는 `flags`가 없다. E1F 재핀은 NPZ를 만들지 않는다. E2 런처가 같은 원본 경로를 받으면 #713의 종류별 깃발 평가가 Kit 전에 rc2로 거절된다.** 새 사본에는 E2 디딤돌 L0와 대안 평균대·틈 L0의 네 깃발이 들어 있다.

| 확인점 | 코드 근거 | 결론 · 등급 |
|---|---|---|
| E2 학습 과제 | `foothold_s2/curriculum/ex42-prep.yaml:401`, `:431`, `:445` | A/stepping_stones_low L0 · 몫 0.05. 대안은 평균대·틈. 코드 |
| E1F 재핀 산출 | `foothold_s2/ex42_stage_materialize.py:438`, `:464` | YAML/JSON 스냅숏과 EX42_AUTO_PLAN/EX42_AUTO_APPROVALS만. 메시 생성·메시 경로 변경 없음. 코드 |
| E1F 후속 사슬 | `foothold_s2/scripts/ex42_post_e1_gpu_chain.py:95`, `:123`, `:132` | 기존 E1 메시로 깃발 기준선을 재고 계획만 재핀. annotate 호출 없음. 코드 |
| E2 실제 경로 선택 | `foothold_s2/scripts/ex42_stage_launcher.py:36`, `:98` | EX42_MESH_DIR_E2 우선, 없으면 EX42_MESH_DIR. prep E2 행에는 파일 경로가 없음. 코드 |
| 학습·평가 같은 경로 | 같은 실행기 `:79`, `:128` | 선택한 메시를 학습과 P1 평가 모두에 전달. 코드 |
| 실제 깃발 소비 | `foothold_s2/scripts/ex42_training_entry.py:249` · `terrains/ex42_flags.py:21`, `:57` | NPZ 표를 명령 생성기에 연결. 기존 파일에 표가 없으면 학습은 직선 대체 경로, #713 named-kind 평가는 거절. 코드 |

**운영 경로의 한계:** 이번 조사에서 실제 E1F/E2 실행용으로 발행된 메시 경로 영수증은 발견하지 못했다. E2가 이미 새 파일을 선택했다고 말할 수 없다. 기존 메시 기본 경로는 `seed42_E0_c333`이고, 새 사본은 아래 E2 전용 환경값으로 연결할 수 있다. 운영 환경·사슬·승인 파일은 고치지 않았다. E1F 성과 관문이나 E2 승인과 이번 메시 산출은 별개다.

## 2. 새 산출과 원본 보존

- 원본: `/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333`
- 준비한 실행 사본: `/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2`
- 실행 manifest: `/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2/terrain_manifest.json`
- 선언: `inbox/jay/20261111-analysis/evidence/ex42-declarations-1111.json` SHA `083e6e7010c2903ef17c4e2ae6f6544b57be4fd62a407230dd22f32e8de6e499`.

| 항목 | 원자료에서 읽은 값 | 등급 |
|---|---|---|
| 원본 NPZ SHA | `b3e6ab6f5093cc78ad2cbb8848d8caa2969ad44774ad7889d5e16d1d8ed7734d` | 실측 |
| 새 NPZ SHA | `59b0bf3e3023f40da828b86eebff4513222e13452c70fc49b8951d7e8d42d771` | 실측 |
| 두 사본의 공통 기하 SHA | `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95` | 실측 |
| 새 terrain_manifest SHA | `7e9dab9420c3c6694df9e2e5d5d9155ff4a5448d1ac7a9936a96c07d2a7a6740` | 실측 |
| 깃발 배열 SHA | `f58819fcc9a109ad05dcf6581624dfaf0a3dc5986faab93a4f053a76368d7207` | 실측 |
| 보존한 원본 배열 | vertices · faces · origins · column_family, dtype·shape·내용 바이트 모두 동일 | 실측 |
| flags 배열 | (10, 76, 4, 2) float32, 24320 bytes | 실측 |
| 유한 깃발 칸 / 직선 대체 칸 | 530 / 230. A 연속 23열은 기존 NaN 대체 규칙 유지 | 실측 · 코드 |
| aggregate_measurements 원본/사본 | 바이트 동일 · SHA `27f05942b1f2437ec6c22f46de76edb01f17c4ac8e4d176ecbc2f6da6aa24f84` | 실측 |
| 측정 영수증 | 기존 기하의 GPU 측정값 승계. 새 Kit 실행 아님 | 실측 범위 설명 |

전체 NPZ 파일은 배열 하나가 추가되어 SHA가 바뀐다. 원본 운영 파일은 바꾸지 않았다. 초기 CPU 사본 `seed42_E0_c333_flags_E2_1111`과 최종 `_v2`는 독립적으로 생성했으며 NPZ SHA가 같았다. 초기 사본은 실행 manifest가 없는 중간본이므로 `_v2`만 전달한다.

기존 aggregate와 계획에 고정된 측정값 대조는 그대로 통과해야 한다. 새 manifest의 `provenance.flag_annotation`에 원본 경로·원본 NPZ/영수증 SHA·배열 보존·`measurements_inherited=true`·`new_kit_validation=false`를 남긴다. 추가 깃발 표의 Kit 장착·전송 시간은 미측정이다. 검증된 것은 원본 기하와 영수증 보존 및 CPU 소비 계약이며, 보행 성공이나 새 Kit 측정 통과가 아니다.

## 3. E2 좌표와 소비 확인

| 종류 | L0 열 번호 | 실제 네 목표 수 | 원본 #713 guard | 새 사본 #713 guard · 명령 생성기 |
|---|---|---|---|---|
| A/stepping_stones_low L0 | 23, 24, 25, 26, 27, 28, 29 | 28 | rc2 | CPU 통과 · 64/64 동일 |
| A/balance_beams L0 | 35, 36, 37, 38, 39 | 20 | rc2 | CPU 통과 · 64/64 동일 |
| A/gaps L0 | 45, 46, 47 | 12 | rc2 | CPU 통과 · 64/64 동일 |

모든 좌표는 세계 XY(m)다. 예를 들어 디딤돌 23열 L0 시작 원점은 `[-39.5, -12, 0]`; 네 목표는 아래와 같다. 나머지 열 좌표와 지지 높이는 [원자료 JSON](evidence/ex42-e2-flags-readback-1111.json)에 있다.

```json
[
  [
    -37.87586975097656,
    -11.999262809753418
  ],
  [
    -36.25031661987305,
    -12.000737190246582
  ],
  [
    -34.626609802246094,
    -12.000737190246582
  ],
  [
    -32.996665954589844,
    -11.986666679382324
  ]
]
```

각 저장된 float32 목표에서 원본 삼각형을 다시 읽어 XY 내부 판정과 높이를 독립 계산했다. 메타데이터의 지지면 높이와 차이는 1e-6 m 이내이며, 목표 X는 전진한다. `MeshFlagProvider`가 64개 환경에 내는 값과 저장 배열을 직접 대조했다. 목표는 도달 좌표이며 발 디딤 순서·충돌 없는 경로·과제 성공을 보증하지 않는다. A 목표는 `sparse_terrains.FLAG_X`를 실제 지지면으로 옮기는 기존 규칙을 재사용했다.

#713 `ex42_flag_eval.py`의 **실제 AST에서 Kit 전 종류별 검사만** 추출해 원본 거절(rc2)과 새 사본 통과를 확인했다. 전체 평가기나 Kit는 돌리지 않았다. 실제 AppLauncher import만 시도했을 때 이 설치는 Kit bootstrap/EULA 입력으로 들어가 EOF로 종료했으므로, 그 import 결과를 평가 통과 근거로 쓰지 않았다. 이후 검사는 Isaac import 없는 CPU 구간만 실행했다.

## 4. 코드·시험·재현

수정은 기존 `ex42_mesh_flags`의 안전한 발행 경로에 한정한다. `--table`과 `--declarations`를 함께 주면 기존 측정값·선언·기하 핀 검증 뒤 실행 manifest까지 만든다. 일부 인자만 주면 출력 전 거절한다. `ex42_execution_manifest`는 사본의 원본 영수증과 모든 원본 배열을 대조하고, 새 파일 SHA도 검사한다. 생성기 치수·학습 계획·승인·원본 메시·측정 문턱은 그대로다.

CPU 시험: 관련 세 파일 **44 passed**. 답을 아는 반례는 기하 SHA가 같은 원점 변경, 열 순서 변경, 깃발 결측/NaN/Inf, 새 파일 SHA 불일치, 원본 SHA 불일치, 같은 수치여도 다른 aggregate 영수증, 원본 측정 영수증 결측이다. 첫 시험에서 원점 변경을 거절하지 못하는 현상을 실제로 재현한 뒤 고쳤다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 \
/home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.tools.ex42_mesh_flags \
  --source /home/jay/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333 \
  --out /home/jay/data/foothold/s2_lab/ex42_mesh_1111/NEW_UNIQUE_FLAGS_FOLDER \
  --table foothold_s2/curriculum/ex42-prep.yaml \
  --declarations inbox/jay/20261111-analysis/evidence/ex42-declarations-1111.json
```

출력 폴더가 이미 있으면 거절한다. 판독 재현:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. \
/home/jay/miniforge3/envs/isaac311/bin/python \
  inbox/jay/20261111-analysis/audit_e2_flag_mesh.py \
  --mesh-dir /mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2 \
  --plan foothold_s2/curriculum/ex42-prep.yaml \
  --consumer-ref 7f222a3a606eafe600bdb6fe8820ce0134d34a0c \
  --out /home/jay/mai/tmp/analyst-lx/NEW_E2_FLAG_READBACK.json
```

## 5. runner 인계와 남은 경계

아래는 **적용하지 않은 인계값**이다. E1F용 공통 경로는 바꾸지 않고 E2 학습·평가 경로를 함께 지정한다.

```bash
EX42_MESH_DIR_E2=/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2
EX42_MESH_SHA256_E2=88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95
```

`MESH_SHA256`는 정점·면 기하 SHA다. 새 파일 SHA `59b0bf3e3023f40da828b86eebff4513222e13452c70fc49b8951d7e8d42d771` 및 manifest SHA `7e9dab9420c3c6694df9e2e5d5d9155ff4a5448d1ac7a9936a96c07d2a7a6740`를 실행 영수증에도 따로 고정해야 한다. E3 이후에도 깃발이 필요하므로 그 단계별 경로가 다시 원본으로 돌아가지 않는지 runner가 함께 확인한다. 옛 측정/승인 영수증을 수정하거나 새 사본으로 경로만 덮어쓰는 절차는 넣지 않았다.

| 남은 항목 | 상태 | 담당 |
|---|---|---|
| 깃발 사본·manifest·CPU 계약 | 완료 · `확인됨` | analyst-lx |
| E2 런처의 위 사본 선택과 실행 영수증 | 미적용 · 경로 연결 필요 | runner/lead |
| E1F→E2 성과·승인·측정 관문 | 기존 관문 그대로 · 이번 PR이 대신 통과시키지 않음 | lead/verifier |
| 새 사본의 실제 Kit 네 깃발 소비와 보행 | 미실행 | 승인된 슬롯의 실행 담당 |

관련: [이슈 #714](https://github.com/foothold-project/foothold-lab/issues/714), [소비자 PR #713](https://github.com/foothold-project/foothold-lab/pull/713). 입력 보고서 `/home/jay/mai/tmp/scripter/REPORT-ex42-e2-1111.md`는 읽기만 했다.

| 판 | 날짜 | 바뀐 내용 |
|---|---|---|
| v1.0 | 2026-11-11 | 실제 경로 구분 · 원본 보존 사본 · 측정 승계 증거 · E2 소비 판독 |
