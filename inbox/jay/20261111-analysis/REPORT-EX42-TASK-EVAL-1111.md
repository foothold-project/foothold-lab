# EX-42 논문 과제 · 상자 · 확장 E · 방향 · 밀기 평가 연결

> 분류: A/평가
> 작성: 오흥재 · analyst-lx · 2026-11-11 15:18
> 근거: #673 · CG 368d03e2:299,316,387,393,394 · lead 11/11 15:05·15:20 결정 · 저장 메시 CPU 대조
> 요지: 실제 기하에서 평가 시간을 먼저 고정하고, 64개 독립 타일의 원자료로 완료와 방향별 진행을 다시 센다.
> 상태: CPU 구현·검증 완료. Kit 실행 및 단계 체인의 실제 호출은 미확인. 학습 메시·운영 사본 변경 없음.
> 판: v0.1

## 1. 맡은 여섯 칸과 남은 연결

| 점검표 번호 | 이번 구현 | 판정과 기록 | 아직 재지 않은 것 |
|---|---|---|---|
| 20 논문 과제 | 경사 30·35도, 전진 계단 0.15·0.20·0.25 m, 후진 계단 0.10 m를 저장 메시에서 선택. 공통 EX-41 로더와 64개 타일 평가기 연결 | E4부터 GT·Pred 판정, 끔은 기록. 이전 단계는 기록 | Kit 장착·정책 실행, 단계 어댑터의 실제 호출 |
| 21 상자·확장 E | C box는 중앙 상단 접촉을 거친 뒤 출구에서 0.5초 유지. 우회는 따로 기록. 확장 E는 입구부터 반대 끝까지 평가 | 경사·역경사 L6, 계단·역계단 L3와 네 종류의 완료 증거를 모두 요구하는 집계 함수 | 네 종류의 실제 평가 결과, 두 창 연결 |
| 23 DR 밀기 | 학습과 같은 `stages[E0].terrain.kind_task` 마스크. 기존 `DRMode`로 배율 1, 실제 물리값·밀기 1회·회복값 수집 | 켬 종만 기록, 끔 종은 `n/a`. 유지·승급 점수로 넣지 않음 | 실제 물리 readback |
| 25 종류별 네 방향 | 전진 1.0, 후진 0.5, 옆 ±0.5 m/s. 300 step. 같은 조건의 평지 64개를 별도 측정 | 전진 300은 기록. 후진·옆은 E5 이후 첫 창 기록, 둘째부터 평지비 판정. 끔은 기록 | Kit 실행, 단계 어댑터가 `cases[id].judgement`를 읽는 연결 |
| 34 물리 표시 | 0.75 m 턱, 0.20 m 천장 등의 평가 전용 저장 열을 같은 실행기로 읽음. 통로는 비발 링크 접촉이 있으면 무접촉 완료로 세지 않음 | 전부 기록. 이 실패로 단계 승급을 막지 않음 | 실제 영상·행동, 천장 관측·몸 낮추기 처리는 별도 담당 |
| 15 START 변형 | 실제 평가 메시의 START 12열을 읽고, 원 메시·타일·입력 해시를 영수증에 보존 | 틈 ×1.15, 받침 ×0.85, 둘을 합친 변형 ×4종. 전부 기록 | 두 지형 시드의 실제 정책 평가 |

여기서 `kind` 완료 실행기는 **C box와 확장 E 네 종만** 받는다. 다른 종류의 마지막 디딤면 완료는 scripter의 종류별 완료 실행기 영역이다. 계단참 회전·정지 재출발은 #664 D44 실행기를 사용하며, `eval_stair_surface_spin`도 직진 평가로 대신하지 않고 거절한다.

## 2. 300 step 반례와 결정 반영

**확인됨 · 기하 실측:** C box L0는 시작 x=0.96 m에서 출구 x=8.5 m까지 7.54 m다. 1 m/s를 완벽하게 따라도 6초에는 도착하지 못한다. 확장 E의 원래 학습 원점은 중앙 높은 곳이라 그것을 평가 시작점으로 쓰면 오르는 부분을 생략한다.

lead 15:20 결정에 따라, 결과를 보기 전에 다음 식으로 각 칸 시간을 고정했다. 여유 2초는 **가정**, 거리와 지지면 높이는 **CPU 기하 실측**, 0.5초 완료 유지는 **설계**다.

`steps = ceil((distance_m / command_speed_mps + 0.5 + 2.0) / 0.02)`

| 실제 요청으로 다시 읽은 칸 | 거리 | 속도 | 고정 step·시간 | 평가 원점 |
|---|---:|---:|---:|---|
| C box L0 | 7.54 m | 1.0 m/s | 502 · 10.04 s | 원래 시작 받침 (0.96, 4.48, 약 0.005) m |
| E slope_steep L6 | 7.00 m | 1.0 m/s | 475 · 9.50 s | (0.5, 4.0, 약 0.120) m. 원래 학습 원점 (4,4,1.205) m 보존 |
| 후진 계단 0.10 m | 2.20 m | 0.5 m/s | 345 · 6.90 s | (0.5,4,0) m |

목표 영역에 들어간 다음 step부터 명령을 0으로 바꾸고 그 자리의 접촉·생존 유지 시간을 센다. 목표 진입 전에 0 명령을 준 원자료는 거절한다. 넘어져 자동 리셋된 env는 두 번째 시도로 세지 않는다.

학습 메시 39종×10레벨 390행과 평가 전용 32행, 합 **422행**의 시작점·목표 영역·시간을 [기하 시간표](ex42-task-geometry-times.json)에 먼저 기록했다. 모든 행이 이 실행기의 승급 대상이라는 뜻은 아니다. 표에는 다른 담당 실행기가 쓸 기하 행도 있다.

- 표 SHA256: `5977df4ea4fb633aaf0e017572cc4e1def75687826637c48037f0761aa0c015d`
- `ex42-prep.yaml`의 `evaluation.forward_completion_timing.calibration_table`이 이 파일과 SHA를 고정한다. 원 메시 또는 시작점·목표 영역이 달라지면 요청 생성을 거절한다.
- C333 원 메시 geometry SHA: `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95`
- 평가 32열 geometry SHA: `057b6a292681f95bf669e8c1213d51f4e1e74bdacee02a05d07aca73a7ffc01a`
- 평가 32열 manifest SHA: `47cc98a51db4771eb4ee2a68919ee98613e8b03f99db1b05e6761ef79090064e`
- 실제 요청 CPU 영수증: `/home/jay/mai/tmp/analyst-lx/task-real-requests-1111/CPU-receipt.json`, SHA `354799e9abf6bac631cb2814e6191d2950625b4b39d5d37a7a8ff4b7c30d97a2`.

세 요청 모두 실제 부모 `model_6000.pt`의 SHA `1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613`로 준비·되읽기했다. 이 확인은 **체크포인트 파일·요청·메시의 연결 확인**이며, 신경망 추론이나 Kit 실행 확인이 아니다.

## 3. 방향별 평지비 계약

lead 15:05 결정의 집계법·시간·속도는 prep에 **가정**으로 적었다.

- 짝의 체크포인트 SHA, 평가 시드, 지도 모드, 몸 좌표 명령, step 수, dt가 전부 같아야 한다.
- 명령 방향으로 초기 몸 yaw를 회전해 지형 전진축을 따라 이동한다. 월드 변위를 그 초기 명령 방향에 투영한다. 좌·우는 몸 기준이다.
- **출발 64개 전부**의 최종 부호 있는 투영 거리 중앙값을 쓴다. 넘어진 env는 첫 리셋 직전 마지막 위치에서 멈춘다. 리셋 후 순간이동을 진행 거리로 세지 않는다.
- `terrain_median / flat_median >= 0.5`. 평지 중앙값 ≤0이면 HOLD다.
- 초기 배치 유효 수 <48이면 HOLD. 그 이상이면 생존 문턱은 `ceil(60 × valid / 64)`. 정책 실패는 유효 수에서 빼지 않는다.
- 둘째 창부터 판정한다. 첫 창·끔·전진 300step은 기록만. 별도의 전진 완료 칸은 §2의 시간 식을 쓴다.
- 보통 완료 칸은 64개의 유효 시작, 완료 ≥52, 생존 ≥60을 요구한다. 두 창 반복 조건과 이전 능력 유지의 최종 결합은 단계 판정기 몫이다.

접촉은 1 N, 비발 링크 접촉은 0.1 N 기준이다. 상단 받침 높이 허용 0.08 m는 기존 D44 측정과 맞춘 **측정 가정**으로 case에 남긴다. 실제 장착·센서 값을 확인하기 전, 이 허용값이 모든 지형에서 충분하다고 단정하지 않는다.

## 4. 소비 계약과 실행 순서

| 순서 | 모듈·함수 | 입출력 |
|---|---|---|
| 결과 전 시간 고정 | `tools.ex42_task_timing.table` | 저장 삼각형 → 종·레벨·원점·목표·시간 표. 재생성하지 않음 |
| CPU 요청 | `eval.ex42_task_suite.create_request` | plan, checkpoint, source_mesh, family, kind, level, stage, group, window_index, steps → `request.json` |
| 사전검사 | `validate_request`, `ex42_task_mesh.preflight` | 원 파일 SHA·정확한 칸 목록·역할·64개 서로 다른 시작점 확인 |
| 운영자 실행 | `run_request(request, device=...)` | 별도 자식 프로세스. 평지비는 평지와 실제 지형 순서. stdin=DEVNULL. 기본 CPU CLI는 실행하지 않음 |
| 원자료 | `ex42_task_eval` | 칸마다 root·발 위치, 접촉, 명령, 생존, 첫 done의 NPZ와 JSON. 공통 EX-41 평가 로더 사용 |
| 판독 | `ex42_task_evidence.read_evidence(folder, request_path=...)` | exact case list와 해시 확인, NPZ로 다시 계산. `rows`, `cases`, `judge_rows`, 영수증 SHA |
| 단계 소비 | scripter/sonnet 단계 어댑터 | **`cases[id].judgement`**를 사용. 특히 cross_dir는 `success_count`로 대체하면 안 됨 |

`group=paper`는 평가 전용 V열, `group=kind`는 C box·확장 E, `group=directions`는 네 방향, `group=push`는 G18 기록이다. paper·kind의 `steps` 입력은 기하식으로 다시 계산되며, directions는 정확히 300이어야 한다. DR 켬은 고정 범위 표와 배율 1.0을 요구한다.

검증된 C box 요청의 운영자용 실행 예시는 아래다. **이번 작업에서는 실행하지 않았다.** 새 통합 plan을 쓰면 그 SHA로 요청부터 새로 만들어야 한다.

```bash
python -c 'from foothold_s2.eval.ex42_task_suite import run_request; print(run_request("/home/jay/mai/tmp/analyst-lx/task-real-requests-1111/C_box/request.json", device="cuda:1"))'
```

종류별 다른 완료 실행기는 같은 `completion_timing(plan, origin=..., anchors=..., speed=...)` 함수를 사용할 수 있다. 확장 E에서는 `select_tile`이 주는 평가 원점을 써야 하며 학습 원점으로 되돌리면 안 된다.

## 5. 시험과 한계

**확인됨:** isaac311, `CUDA_VISIBLE_DEVICES=''`, CPU 시험 **25 PASS**. pyflakes 0건. CLI 도움말은 Kit를 띄우지 않는다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -m pytest \
  foothold_s2/tests/test_ex42_task_cells_cpu.py \
  foothold_s2/tests/test_ex42_task_mesh_cpu.py \
  foothold_s2/tests/test_ex42_task_suite_cpu.py \
  foothold_s2/tests/test_ex42_task_evidence_cpu.py \
  foothold_s2/tests/test_ex42_task_runtime_cpu.py \
  -q -p no:cacheprovider --basetemp=/home/jay/mai/tmp/analyst-lx/task-verified-tests-1111
```

답을 아는 시험: 중앙 상자 우회는 완료가 아님, 상단 높이에 닿지 않은 접촉은 중앙 통과가 아님, 도착 뒤 넘어짐은 실패, 잠깐 진입은 0.5초 유지가 아님, 목표 전에 정지 명령 거절, 방향 부호·yaw·같은 평지 짝·0 분모, 48 유효 시 비례 문턱, E4 방향 칸의 조기 판정 차단, 원 자료·count·role·SHA 변경 거절, 64개 독립 타일, E 입구와 학습 원점 분리, 원본 메시 바이트 불변, 실제 요청→원자료→되읽기.

관련 기존 시험을 넓혀 돌린 앞 검사에서는 100 PASS·1 FAIL이었다. 실패는 기존 `test_ex42_d44_cells_cpu.py::test_d44_real_kit_parser_accepts_parent_argv_then_rejects_bad_env_count`가 이 셸의 `ISAACLAB_ROOT` 미설정 때문에 parser 전에 멈춘 것이다. 이 결과를 전체 통과로 바꾸어 적지 않았다. 환경 설정·EULA 변경은 하지 않았다.

**미확인:** Kit에서 첫 reset·실제 몸 yaw와 발 지지면·첫 정책 step·끝 영수증. 그 뒤 `read_evidence`로 숫자를 다시 계산하고 단계 어댑터가 그 영수증을 읽어야 실제 연결이 닫힌다. 실제 실행 시간·영상은 아직 없다. 이번 CPU 통과만으로 20,000회 자동 연속 학습 전체가 검증됐다고 주장하지 않는다.

## 6. 원문과 변경 이력

- [CG 고정 판](https://github.com/foothold-project/foothold-lab/blob/368d03e2061b505fc72ad73e9cd2527a766e7738/inbox/jay/20261026-experiments/CURRICULUM-GATES.md#L299)
- [작업 #673](https://github.com/foothold-project/foothold-lab/issues/673)
- [D44 칸 목록 #664](https://github.com/foothold-project/foothold-lab/pull/664)
- [방향별 메시·깃발 #668](https://github.com/foothold-project/foothold-lab/pull/668)

| 판 | 날짜 | 변경 |
|---|---|---|
| v0.1 | 2026-11-11 | 6개 배정 항목 CPU 구현, 시간·E 원점 결정 반영, 기하 시간표 고정, 실측과 미확인 분리 |
