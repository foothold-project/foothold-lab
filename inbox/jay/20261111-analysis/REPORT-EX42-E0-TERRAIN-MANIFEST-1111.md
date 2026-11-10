# EX-42 E0 실행용 지형 manifest

> 분류: 구현 검증
> 작성: analyst-lx · 2026-11-11
> 근거: lead-lx 실행 manifest 카드 · 통합 3b78bf18 (#619 포함) · planner 선언 083e6e70 · 실제 seed42_E0_c333 메시
> 요지: 저장된 메시와 종별 선언을 CPU로 연결해 46행 manifest 생성, 공식 E0 dry의 training_blockers=[] 확인
> 상태: 확인됨 · 이 카드 범위 막음 0 · GPU/Kit/학습 미실행

실행 파일은 `/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333/terrain_manifest.json`이다. [저장소 사본](evidence/ex42-e0-terrain_manifest.json)의 SHA256은 `39145e734002859dfc384d3e010c6d3115056d8ce01b341d561499b23a7f50bd`이며 실행 파일과 바이트가 같다.

## 무엇을 만들었나

[CPU 도구](../../../foothold_s2/tools/ex42_execution_manifest.py)는 다음 순서로 읽는다.

1. 생성기의 종류 목록: `columns.FULL/CONTINUOUS`, AME-2·JEPLO·HiPAN의 `KINDS`, 확장 지형의 `PAPER_EXT_SPECS`. 종류와 열 배치는 손으로 다시 적지 않는다.
2. planner의 [치수 선언 스냅샷](evidence/ex42-declarations-1111.json). 원본 `/home/jay/mai/tmp/planner-lx/ex42-declarations-1111.json`과 SHA `083e6e7010c2903ef17c4e2ae6f6544b57be4fd62a407230dd22f32e8de6e499`가 같다. 원 치수·학습 치수·평가 치수·방향·출처·물리 표시를 그대로 읽는다. B·D 학습 치수는 코드의 `dimensions()`·`build_tile().dimensions` 값과도 대조한다.
3. 저장 NPZ의 실제 정점·삼각형과 `mesh_manifest.json`. 합친 기하 SHA가 승인 핀 `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95`와 같은지 확인한다.
4. 종류마다 해당 열 안에 중심점이 있는 삼각형을 모아 별도 SHA를 계산한다. 이동한 안전 시작점을 열 중심으로 쓰지 않고, 생성기 칸 크기와 실제 배치 offset을 쓴다. 생성기 외곽 경계는 제외한다. 선택 열·행·정점 수·면 수·범위·해시 바이트 형식을 행마다 남긴다.
5. `aggregate_measurements.json`의 값을 복사하기 전에 메시 영수증의 `aggregates`와 prep 측정 핀을 대조한다. `receipt_ids`는 실제 메시 기하 SHA와 aggregate 파일 SHA를 가리킨다. 존재하지 않는 종별 Kit 실행 영수증을 만들지 않는다.

| 행 묶음 | 행 수 | 기하 출처 |
|---|---:|---|
| A | 13 | 실제 A 열 |
| B | 12 | 실제 B 열 |
| C | 7 | 실제 C 열 |
| D | 3 | 실제 D 열 |
| E | 4 | 실제 E 열 |
| continuous | 7 | A의 연속 7종 별칭, 같은 기하 SHA |
| 계약 합계 | 46 | 고유 종류 기하 SHA 39개 |

숫자 등급은 위 행 수·SHA·시험·dry 모두 **실측**이다. 종별 치수의 논문/코드/위임 추정 등급은 planner의 `paper_reference`를 보존했다. 이 작업에서 논문을 다시 검증했다고 주장하지 않는다. `*_dimensions_m`이라는 기존 계약 이름 아래에도 `*_deg`, `*_rad`, `*_ratio`, `*_per_m2`가 있으므로 각 축 이름의 단위를 따른다.

## 검사 결과

| 검사 | 확인된 결과 |
|---|---|
| 새 시험을 먼저 실행 | 모듈 부재로 collection 오류. 구현 뒤 신규 20개 통과 |
| 신규·Kit manifest·E0 guard·prep·승인 핀 시험 묶음 | **96 passed in 3.68s** |
| 답을 아는 한 삼각형 | 직접 계산한 SHA와 일치, 정점 하나를 바꾸면 SHA 변경 |
| 선언이 없는 B/D 원본 | 31행 partial, 누락 15종을 필드별 출력. runtime 계약이 partial 거절 |
| 선언 완성 + D preset 정합 | 46행 measured, 누락 0, `plan.validate_terrain_manifest` 통과 |
| 다른 메시·다른 aggregate·null preset·잘못된 방향·NaN 치수 | 거절 |
| B/D 선언에 없는 학습 치수 또는 코드와 다른 치수 | 거절. 1.2 m 벽을 99 m로 바꾸는 반례 포함 |
| 같은 산출 경로에 다른 내용 게시 | 거절. 기존 파일 덮어쓰기 없음 |
| 공식 train_start E0 dry | 아래 원문, `training_blockers=[]` |

공식 dry [원기록](evidence/ex42-e0-manifest-dry.json)에서 필요한 칸을 그대로 발췌했다.

```json
{
  "state": "stage_e0_preflight_passed",
  "training_blockers": [],
  "app_launcher_started": false,
  "training_requested": false,
  "total_envs": 6144
}
```

dry에는 3,072/rank, world_size=2, 부모 m13000 실제 체크포인트, E0 250회 승인, 복원 지도 설정을 넣었다. `CUDA_VISIBLE_DEVICES=''`이며 torchrun을 실행하지 않았다. 지정 run·queue가 생성되지 않은 것도 확인했다. score argv는 dry에서 실행되지 않는 자리표시다.

## 변경 범위와 한계

- prep 변경은 `environment.training_presets.D: null → posture_go2_v1` 한 줄이다. lead 06:00/06:02 지시이며 `hipan_posture.PRESET_ID`와 같다. 승인 파일은 바이트 불변이다. 나머지 prep·학습·평가 코드는 변경하지 않았다.
- **측정 범위:** 메모리 0.90625 GiB, 생성 9.176870384999347초, 687191753.0844679 rays/s는 이미 실행한 **3,072 환경의 대리 하향 광선** 측정이다. 실제 깊이 센서 패턴·6,144 환경·DDP 비용으로 해석하지 않는다. 원 영수증의 `ray_measurement`·`memory_measurement`를 보존했다.
- **치수 범위:** planner 선언은 명목 치수다. C의 격자화, A의 표시 반올림과 코드 원값을 혼동하지 않도록 코드 매개변수·출처 파일 SHA를 함께 남겼다. A/C/E의 모든 축을 실제 메시에서 다시 역산해 같음을 증명한 것은 아니다.
- **평가 범위:** 평가 치수 선언은 있어도 변형 평가 메시를 이번에 생성·측정하지 않았다. `evaluation_geometry_measured=false`로 표시했다.
- 생성기 파일 SHA는 이번 목록·매개변수 해석 코드의 출처다. 과거 메시를 만든 코드 HEAD의 증거로 대체하지 않는다.
- dry 막음 0은 이 manifest 연결이 해결됐다는 뜻이다. N1 예행·실센서·DDP·학습 첫 update 통과를 뜻하지 않는다. R6·M27에 따라 이 차이를 남긴다.

## 재현

자기 작업 사본 루트에서, GPU를 사용하지 않는 명령이다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python \
  -m foothold_s2.tools.ex42_execution_manifest \
  --mesh-dir /mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333 \
  --declarations inbox/jay/20261111-analysis/evidence/ex42-declarations-1111.json \
  --output /home/jay/mai/tmp/analyst-lx/terrain-manifest-replay.json
```

실제 실행 경로에 이미 다른 파일이 있으면 덮지 않고 거절한다. 다른 사본에서 실행하면 선언 파일의 절대경로 provenance가 달라질 수 있으므로, 전체 파일 SHA와 기하 SHA를 구별한다. 같은 사본·같은 입력·같은 경로 재실행은 바이트가 같은 기존 파일을 허용한다.

CPU 시험·dry 전체 로그: `/home/jay/mai/tmp/analyst-lx/terrain-manifest-1111/`의 `red.log`, `tests-final.log`, `generated.log`, `replay.log`, `e0-dry.log`. 공식 dry 명령은 [명령 파일](evidence/ex42-e0-manifest-dry.sh)에 보존했다. GPU 실행·학습 시작은 이 카드에서 하지 않았다.
