# C 묶음의 시작 위치와 reset 계약 정정

> 분류: 실험
> 작성: 오흥재 · 2026-11-11
> 근거: 01:38 장착 실패 원자료 · JEPLO 460e2272 · lead 01:44/01:50 결정 · CPU 재계산
> 요지: 중앙 원점과 실제 시작점을 혼동한 오류를 고치고, 세 종류의 안전 지지 패치와 열별 reset 선언을 제공한다
> 상태: CPU 확인됨 · PR #599 수정본 · 소비자 통합 뒤 Kit 장착 재측정 대기
> 판: v1.0

작성 보조: analyst-lx. GPU·Kit·학습은 실행하지 않았다. PR [#599](https://github.com/foothold-project/foothold-lab/pull/599).

## 원인과 실제 실패 범위

`확인됨`: 이전 생성기는 원본의 **타일 중앙값**을 정확히 재현했지만, 그 값을 로봇의 **시작점**으로도 썼다. JEPLO 원본은 gap · box · discrete_obstacles에서 첫 경유점으로 옮기고 XY·yaw 흔들림을 0으로 만든다. 우리 환경은 중앙 주변에서 XY ±0.5 m를 표본화했다. 한 점의 지형 높이가 맞아도 옆 발은 틈 위에 놓일 수 있었다.

| 항목 | 원자료로 확인한 값 | 뜻 |
|---|---|---|
| reset 0, env 50, C gap L0 | 몸통 z 0.38255 m, 발 아래 평균 지지 높이 −0.72504 m, 최대 발 clearance 1.55587 m | 틈 위에서 시작한 실패 |
| 원점 일치 | 세 reset 모두 env origin 대 terrain origin 차이 0 m | 장착 단계가 원점을 바꿨다는 증거 없음 |
| 원점 한 점 검사 | C 높이 오차 최대 0.00750 m, 통과 | 몸 전체·네 발의 안전성을 대신하지 못함 |
| reset 1, env 52, C box L1 | 네 발 clearance 0.22990 · 0.23045 · 0.24576 · 0.10295 m | 전역 최대 0.69103 m를 이 env의 값으로 붙일 수 없음 |
| 순수 CPU 반례, gap L0 seed 42 | 중앙 높이 −0.005 m지만 offset (0.5,−0.65625) 지지는 −0.70133 m | 몸 중심 한 점 검사만으로 놓치는 반례 |

원자료: `/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/mount_check_ACDE_cuda0.json`.
메시 manifest의 내용 해시 `5c89d00cef4ad04a5df1b0c792e07b3aaf1a3bd24fe4a44b9e4dfe98422973cc`와 NPZ 파일 바이트 SHA256 `f7f3bd4095c7e4c386cdc8a43d4cdd43d852da2ab9e20969982a4bdb028aa527`는 다른 해시 정의다. 서로 같다고 대조하지 않는다.

## 원본과 고친 접속

| 경로 | 원본 또는 수정 내용 |
|---|---|
| [원본 reset :47~69](https://github.com/ASIG-X/JEPLO/blob/460e2272907af053d6e66b57fec71fdbe6ca1774/training/go2_parkour/go2_parkour/tasks/go2_loco_events.py#L47) | waypoint 유형은 첫 목표에서 시작, XY·yaw 표본 0 |
| [원본 유형 :55~60](https://github.com/ASIG-X/JEPLO/blob/460e2272907af053d6e66b57fec71fdbe6ca1774/training/go2_parkour/go2_parkour/tasks/go2_loco_env.py#L55) | direct-command 4종은 중앙 origin |
| `foothold_s2/terrains/jeplo_preset.py`의 `spawn_origin` | 세 waypoint 종류의 실제 snapped mesh에서 앞쪽 지지 패치를 선택, 중앙값으로 fallback하지 않음 |
| 같은 파일 `RESET_RANGES` | gap · box · discrete_obstacles의 x/y/yaw가 모두 (0,0) |
| 같은 파일 `reset_ranges_by_column` | 실제 전역 열번호→종류 입력. C 7종 표 반환, 다른 가족은 입력에 넣지 않음 |
| `tile_function` | 참고 중앙 origin 대신 새 spawn_origin 반환 |
| sonnet `ex42_column_reset.py` 6603b0ae | 선언을 읽어 실제 열에 매핑. CPU로 해당 파일을 그대로 호출해 대조 |

지형 형상·높이·깊이·레벨 식은 바꾸지 않았다. `HeightTile.origin`은 원본 wrapper 대조용 참고 좌표로 남는다. 새 시작점은 원본 경유점 좌표를 복사한 것이 아니라 우리 코드가 찾는 지지 패치다. 원본의 이동 목표·waypoint 정책까지 이식했다는 주장이 아니다.

선택 직사각형은 길이 0.70 m · 폭 0.50 m, 허용 지면 높이 −0.10~0.15 m · 높이차 최대 0.15 m다. **근거 등급: 가정(시작점 지지 계약)**. 현재 Go2 기본 관절 자세·yaw 0을 전제로 한다. 현재 `robots/go2_params.py:27`의 joint reset scale은 (1,1), `tasks/s1_env_cfg.py:144~150`이 이를 소비한다. 초기 자세나 로봇 모양을 바꾸면 이 직사각형의 적절성도 다시 재야 한다. 지원되지 않는 후보는 생성 중 명시적으로 실패한다.

## 확인한 것과 남은 것

| 확인 | 결과 | 증거 |
|---|---|---|
| 알려진 삼각형 수직 교차 | 높이 0.8 m 재현 | `test_known_triangle_intersection` |
| CPU 회귀 시험 | 140 PASS | `test_jeplo_spawn_cpu.py`, `test_jeplo_preset.py`, `test_jeplo_measurement_cpu.py` |
| 수정 전 반례 | 새 spawn API 부재로 실패, 기존 중앙/옆 발 반례 별도 확인 | 같은 시험 파일 |
| 원본 높이장·mesh·참고 중앙 대조 | 420건 차이 0 | [oracle 요약](evidence/jeplo-spawn-oracle-summary.json) |
| 실제 실패 메시의 새 지지 패치 | 3종×10레벨 30칸, 1,470점, 최대 높이차 0.11917 m | [CPU 재계산](evidence/jeplo-spawn-mount-cpu.json) |
| sonnet 실제 소비 함수 | C 전역 7열 일치, 대상 96 env 표본의 pose offset 전부 0, A 기본값 유지 | [소비 계약](evidence/jeplo-spawn-consumer-cpu.json) |
| 설치 Isaac 설정 클래스 | 7종 cfg 검증·복사·직렬화·mesh 함수 호출 성공 | `/home/jay/mai/tmp/analyst-lx/jeplo-c-tests/native-cfg.json` · Kit generator 자체는 미실행 |
| 네 발의 실제 장착·접촉 | 미확인 | sonnet 연결 후 lead 장착 재실행 대상 |

**남은 장착 확인은 한 가지 묶음이다.** 새 메시의 원점과 reset 선언이 함께 소비되는지, reset마다 실제 terrain column과 적용 XY/yaw 범위를 남기고, 모든 C 열의 네 발 지지 hit·높이·clearance를 확인한다. 원점 한 점만 맞는 것으로 통과시키지 않는다. 다른 4종의 origin·흔들림은 변경하지 않았으므로 그 종류의 높은 레벨 접촉까지 이 CPU 결과로 보증하지 않는다.

재현:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 python -m pytest \
  foothold_s2/tests/test_jeplo_spawn_cpu.py foothold_s2/tests/test_jeplo_preset.py \
  foothold_s2/tests/test_jeplo_measurement_cpu.py -q -p no:cacheprovider
CUDA_VISIBLE_DEVICES='' python tools/verify_jeplo_spawn_mesh_cpu.py \
  --mesh /mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_ACDE/terrain_mesh.npz \
  --output /home/jay/mai/tmp/analyst-lx/new-spawn-audit.json
```

두 번째 도구는 **수정 전 중앙 origin의 합성 메시**를 입력으로 삼아 새 origin을 CPU에서 재계산한다. 수정한 새 메시의 Kit 장착 영수증을 만드는 도구가 아니다.

| 판 | 바뀐 것 |
|---|---|
| v1.0 | 중앙 원점과 reset 의미 차이 확인, 세 종류의 지지 패치·열별 범위, 실제 실패 메시 재계산 |
