# 평가 메시 후속 · 짝 시드와 계단 면 회전

> 분류: A/지형씬제작
> 작성: 오흥재 · analyst-lx · 2026-11-11 12:12
> 근거: lead 12:05 의뢰 · REVIEW-94fb78c5 · CG @368d03e2:393~394 · prep:472~484
> 요지: 짝 비교를 실제 메시로 검증하고 기록용 계단 면 회전 열을 추가했다. D44 시작 배치는 평가 실행기가 구분해야 한다.
> 상태: CPU 63 통과 · 돌연변이 네 종류 검출 · Kit는 E1 뒤 lead 슬롯 대기

## 검토 항목

| 항목 | 처리 · 근거 |
|---|---|
| 변형 간 같은 terrain seed | 네 종류 × 세 변형에서 kind_seed, 실제 바닥 최저 높이, 구덩이 깊이, 첫 지지면 높이 비교. 돌은 첫 XY 무작위 변위를 명목 틈으로 나눈 값도 비교. seed 43 대조 포함. 지지면 수가 달라질 수 있어 전체 돌의 일대일 대응을 주장하지 않음 |
| 시험의 가르는 힘 | manifest kind_seed는 그대로 두고 실제 RNG만 변형 이름으로 바꾼 메모리 내 돌연변이: 네 종류 모두 실패. 소스 파일 변경 없이 실행 |
| 계단 면 회전 필요 여부 | CG:394와 ex42-prep.yaml:480~484에 기록용으로 명시됨. `eval_stair_surface_spin`, rise 0.15 m / run 0.25 m 추가. 판정 문턱 추가 없음 |
| 안전 시작점 | 기본 원점 [0.5,4,0]의 넓은 진입면. 좁은 0.25 m 디딤면에 로봇을 바로 생성하지 않음. 세 번째 단 중심 [1.625,4,0.45]까지 걸어간 뒤 회전은 실행기 몫이며 세 번째 단 선택은 배치 가정 |
| 기존 메시 보존 | 기존 20열 순서와 치수 그대로, 새 열은 끝에 추가. `--group surface`로 별도 생성. 학습 메시와 기존 평가 NPZ를 덮지 않음 |

## D44 실행기 계약 · scripter와 맞출 자리

`mesh_manifest.json`의 각 열 `anchors_local_m`은 **타일 로컬 좌표**다. 월드 좌표는 `tile_offset_m`를 한 번 더한다. z는 바닥 표면 높이이며 root 높이 오프셋은 로봇 reset 규칙에서 더한다.

| 과제 | 시작 · 진행 | 고정 치수 |
|---|---|---|
| 계단참 제자리 회전 좌/우 | `landing_center=[4,4,1.44]`에서 시작. 기본 terrain origin과 같음 | 참 bounds [3.4,4.6,3.4,4.6], 깊이 1.2 m |
| 계단 중간 정지 → 재출발 | `approach=[0.5,4,0]`에서 걸어 `stop_band_x=[1.6,1.9]` 도달 뒤 정지, 다시 걸어 참 도달. 꼭대기 원점에서 시작한 결과로 대체 금지 | 단 0.16 m, run 0.30 m. 정지 시간은 prep의 2 s |
| 계단 면 회전 기록 | approach에서 `stair_surface_center`까지 이동 후 회전. 좁은 디딤면으로 reset 금지 | 단 0.15 m, run 0.25 m |

scripter 사본 `scripter-ex42-e1-judge-1111/foothold_s2/ex42_e1_judge.py:12~40`은 `case_id=eval_stairs_landing_016`, `envs`, 성공·생존 수 및 원자료 SHA를 소비한다. 이는 배치 실행을 검증하는 함수가 아니다. 현재 읽은 코드에서는 시작 앵커 소비 경로가 확인되지 않았다. 실제 생성 실행기에 위 계약을 전달하고 경로를 대조해야 한다. run 보고 `msg_7045e36a5e2b`로 전달했고, scripter 작업 중이라 직접 입력하지 않았다. **기하 CPU 확인과 정책 평가 완료는 구분한다.**

## 결과 · 재현

CPU: eval_pairing + eval_terrains + mesh_rng + mesh_mount + mount_all_columns = **63 passed**, 16.58 s. 로그 `/home/jay/mai/tmp/analyst-lx/eval-followup-final.log`.

돌연변이: `/home/jay/mai/tmp/analyst-lx/eval-pair-mutation.py`, 로그 같은 이름 `.log`, 4 failed가 기대 결과다.

새 메시: `/mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/surface_seed42_v1/`.

- 기하 SHA256: `533cf6c149fae4e9dab66bdf262f6094ec29c8b097fe8242e21544360da88e4a`
- NPZ SHA256: `e3eb563b599963136f12d302e90f9ee9c1dd443d44786f223d84bb31e5abf7f0`
- CPU origin: 1개 · ray miss 0 · 높이 오차 0 m.
- Kit 장착, 실제 보행·회전은 미측정. 학습 중 GPU에 끼워 실행하지 않는다.
