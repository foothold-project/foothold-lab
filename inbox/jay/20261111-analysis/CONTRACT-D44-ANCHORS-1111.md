# D44 평가 실행기: 확인된 앵커와 미확정 집계

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: analyst-lx · 2026-11-11 12:32
> 근거: CG 368d03e2:229·231·394·780~782, prep:472~484, landing_seed42_v2 manifest 직접 읽음
> 요지: 시간과 앵커는 확인됨. 세 과제를 열거한 본문과 출구의 네 칸이 불일치하므로 단일 성공 수 집계는 아직 확정할 수 없다.
> 상태: 실행기 연결 참고 · 판정 칸 구성과 추가 시간 한도 확인 대기

## 바로 쓸 수 있는 실제 파일

`/mnt/win-d/mai/data/foothold/s2_lab/ex42_eval_mesh_1111/landing_seed42_v2/mesh_manifest.json`

| 파일 또는 값 | SHA256 |
|---|---|
| manifest | `94e3fe3dae914968e0e41b7fb3505339fcad72dd38a650c0381a2855af06d55e` |
| 같은 폴더 terrain_mesh.npz | `86231d2f9ba85af18c89f6c10392498f609dba62ebfe530c7aa9ff5954088531` |
| manifest.mesh_sha256 (기하) | `baa59af3347c53c2cdeae674ddc873f26d4b9e38cffdbce4a4dc73cf94febb82` |

셋은 다른 해시다. CPU 생성과 원점 검증만 완료했고 Kit 장착 및 정책 평가는 lead 슬롯 대기다.

## 과제별 시간 · 시작점

| 과제 | 명령과 시간 | 시작과 성공 |
|---|---|---|
| 계단참 좌회전 | vx=vy=0, wz=+1.2 rad/s, 6 s | landing_center에서 시작. 생존 + 판 위 유지 + 명령 방향 누적 회전각 5.76 rad 이상 |
| 계단참 우회전 | vx=vy=0, wz=−1.2 rad/s, 6 s | 위와 같고 명령 방향 부호를 반영 |
| 계단 중간 정지 → 재출발 | 중간 단에서 2 s 명령 정지, 이후 vx=1.0 m/s | approach에서 걸어 stop_band_x에 진입한 뒤 정지하고 다시 걸어 꼭대기 도달. 접근 시간과 재출발 이후 제한 시간은 원문에 없음 |

위 시간과 80%는 [CG:229](https://github.com/foothold-project/foothold-lab/blob/368d03e2061b505fc72ad73e9cd2527a766e7738/inbox/jay/20261026-experiments/CURRICULUM-GATES.md#L229)의 값이다. 5.76 = 1.2 × 6 × 0.8은 계산이다. 6 s 명령은 7.2 rad로 한 바퀴를 넘으므로 시작과 끝 quaternion의 wrap된 yaw 차로 계산하면 안 된다. 스텝별 unwrap 누적 yaw에 명령 부호를 곱한다. 절댓값만 쓰면 반대 방향 회전도 통과한다.

| anchors_local_m 키 | 실제 값 (m) | 계약 |
|---|---|---|
| approach | [0.5, 4.0, 0.0] | 정지 재출발 과제의 접근 시작 |
| landing_center | [4.0, 4.0, 1.44] | 회전 시작 · 정지 재출발 도착 참의 중심 |
| stop_band_x | [1.6, 1.9] | 타일 로컬 x 범위. 순간이동시키지 않고 걸어서 진입 |
| landing_bounds_xy | [3.4, 4.6, 3.4, 4.6] | [xmin,xmax,ymin,ymax] |

좌표는 모두 타일 로컬이다. 실제 할당한 타일의 offset을 한 번만 더한다. z는 표면 높이이며 root 높이 오프셋은 로봇 reset 규칙에서 한 번 더한다. 이 한 열 파일의 tile_offset_m=[0,0,0], 기본 origin_world_m=[4,4,1.44], reset x/y/yaw 범위는 모두 0이다. 기본 origin만 사용하면 정지 재출발 과제도 꼭대기에서 시작하므로 잘못된 평가가 된다. 시작 자세를 바꾼 뒤 관측·이력·센서 초기화까지 완료하고 평가 시계를 시작해야 한다.

## 단일 success_count: 지금 확정할 수 없는 이유

- [CG:231](https://github.com/foothold-project/foothold-lab/blob/368d03e2061b505fc72ad73e9cd2527a766e7738/inbox/jay/20261026-experiments/CURRICULUM-GATES.md#L231)은 **D44 네 칸 각각 성공 52/64·생존 60/64, 두 창**이라고 읽힌다. 그러나 :229와 :782는 좌회전·우회전·정지 재출발 세 과제만 열거한다. 네 번째 과제 또는 지도 모드와의 조합은 확인되지 않았다.
- `eval_stair_surface_spin`은 :394와 prep:480~484에서 **기록용**이다. 임의로 네 번째 판정 칸에 넣을 근거가 없다.
- scripter `ex42_e1_judge.py:12~40`의 단일 수 소비 경로는 집계 정의가 아니다. 각 칸 64 env 결과를 합산·평균하거나 64 env를 여러 과제에 나눠 쓰면 기존 문턱과 다른 시험지가 된다.
- **연결 제안(미확정)**: 칸별 64 env 원자료와 success_count·survival_count를 보존하고 판정은 모든 필수 칸의 AND로 한다. 호환용 숫자가 꼭 필요하면 success_min_across_cells와 survival_min_across_cells를 별도 이름으로 둔다. 최솟값의 문턱 검사는 각 칸 문턱 AND와 같지만, 하나의 64개체 집단 성공 수나 신뢰구간으로 해석해서는 안 된다. 소비자도 필수 칸 목록·누락·분모·원자료 해시·집계를 다시 검증해야 한다.

lead/planner가 확정할 빈칸: (1) 네 칸의 정확한 task×map_mode 목록, (2) 접근·재출발 제한 시간과 settling 시간, (3) 판 위 유지가 몸통 투영인지 네 발 지지인지, 실제 정지 판독 문턱 및 꼭대기 도달 사건 정의. 원문에 없는 숫자를 기정사실로 넣지 않는다. 이 빈칸은 평가 판정 계약이며 진행 중 학습을 중단시키라는 뜻이 아니다.

## 보존할 원자료 · CPU 시험 제안

필수 칸별 checkpoint·manifest SHA, seed, 64개의 시작 pose, 실제 map_mode, step_dt, 상태 전환 시각, root XYZ·unwrap yaw, 명령, 최초 종료 이유, 성공/생존 mask를 남긴다. 반례는 반대 방향 회전, 2π 경계 통과, 참 이탈 뒤 복귀, 정지 재출발을 꼭대기에서 시작, 필수 칸 하나 누락, 한 칸 51/64인데 다른 칸 64/64인 집계다. 이는 시험 제안이며 이 문서 작성 중 GPU나 실행기 코드를 변경하지 않았다.
