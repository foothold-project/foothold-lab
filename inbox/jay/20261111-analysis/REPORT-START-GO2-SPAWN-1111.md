# EX-42 A 시작 발판 · reset 계약

> 분류: A/지형씬제작 · 구현 검증
> 작성: verifier-lx · 2026-11-11
> 근거: lead-lx 02:16 · 02:20 · 02:21 의뢰, mount_check_ABCDE_v3_cuda0 원자료, C RESET_RANGES 계약
> 요지: 실패한 A 네 kind에 x/y/yaw 0을 선언하고 실제 메시 0.70×0.50 m 지지를 검사, A 소비자 연결
> 상태: CPU 확인됨 · Kit reset 재실측 미확인 · E2 노출 전 실물 확인 필요

## 범위 · 실제 원인

원본 장착 검사 `/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/mount_check_ABCDE_v3_cuda0.json`을 직접 읽었다. 304건 중 실패 26, 그중 A 200건 중 16건이며 실패 kind는 `stepping_stones_low`, `stepping_stones_high`, `balance_beams`, `stepping_beams`다. 기준 원점은 타일 좌표 `(0.5,4,0)`이고 출발 발판 x=0~1, y=0~8은 그대로 있었다. 원점에서 ±0.5 m reset을 하면 앞발 지지 영역이 x>1 구덩이로 나간다. CPU 답 아는 반례에서도 평균대 L9의 원점 높이 0, 원점 + `(0.85,0.25)`의 메시 지면은 −0.2 m 미만이다.

실제 Go2 관절·접촉·낙하를 CPU 기하로 대체 판정하지 않았다. 여기서 확인한 것은 지정된 reset 영역의 지지면이며, Kit 발 간격 재측정은 별도다.

## 변경

| 자리 | 변경·보존 |
|---|---|
| `foothold_s2/terrains/start_go2_v2.py` `RESET_RANGES` | 네 kind만 x/y/yaw `(0,0)` 명시. gaps·flat·연속 kind의 기존 범위는 유지 |
| `spawn_origin` | 기존 출발 원점을 실제 출력 메시 삼각형으로 검사. 위를 향한 z=0 면을 0.70×0.50 사각형으로 잘라 합계 0.35 m²인지 확인. 겹침 면적으로 빈 곳을 숨기지 못하게 겹친 면적도 거부. 완전 지지가 없으면 오류, 구덩이·도착 단 fallback 없음 |
| `_tile_function` · `SideTable.bind` | 출력할 메시와 캐시 재구성 모두 안전 원점 검사를 소비. 원점·지형 치수 자체를 이동·변경하지 않음 |
| `foothold_s2/terrains/ex42_column_reset.py` | `kind_ranges_of` 모듈표의 **A 연결 한 줄**. 기존 C·B·D·E 처리·기본 범위·실제 reset 함수는 보존 |
| 새 CPU 시험 | C의 인터페이스를 따라 actual column→kind를 검사. A 50열 중 22열만 선언 적용, 나머지 28열은 기본값. 실제 reset 함수까지 CPU 대역 env로 내려가 위치·yaw 0 오프셋 확인 |

새 물리 치수·난이도·성공 문턱은 만들지 않았다. 0.70×0.50은 이번 지시의 reset footprint이며 보행 졸업선이 아니다. 부동소수 연산 오차 허용만 사용한다. 최초 원점이 이미 충분한 발판 위이므로 다른 후보 검색이나 지형 변경은 필요하지 않았다.

## 원본 메시 독립 재계산

입력은 `seed42_ABCDE_v2/terrain_mesh.npz`이며 이름은 v2지만 장착 검사 v3 JSON의 geometry SHA와 **직접 계산하여 동일함**을 확인했다.

| 항목 | 실측 |
|---|---|
| NPZ 파일 SHA256 | `f1697a4bc0ad2e8f352d003a9bd41f9077bea808a605f8e1f911062b874d09c2` |
| 원 vertices+faces 바이트 SHA256 | `eafbada6c431fdc37b2a0e20094a404f0caad96d58cb2bcaca761629acf0b01d` |
| 장착 검사 JSON SHA256 | `dc132372c8e50d731a527656f625234ad3718bdcbd40f65b562cfe56212649be` |
| A 검증 대상 | 네 kind의 실제 **22열 × 레벨 0~9 = 220칸** |
| 지지면 확인 | 각 칸 삼각형 면적 전체 검사 + 별도 수직선·삼각형 교점 **165점**, 합 **36,300점** |
| 지지면 높이 | 전부 **z=0**, 최대 절대 z **0.0 m** |
| geometry 변경 | A sparse 6종×10레벨, 변경 전후 box 바이트 SHA **60/60 동일** |

재현 도구 `tools/verify_start_go2_spawn_mesh_cpu.py`, 결과 `inbox/jay/20261111-analysis/evidence/start-go2-spawn-mesh-cpu.json`. 독립 수직선 교점 계산은 기울어진 삼각형의 알려진 입력 `(0.2,0.3) → z=0.8`을 먼저 통과했다. raw의 실패 열 kind 순서도 선언과 대조했으며, 이름으로 열 번호를 추측하지 않았다. 원자료·원영수증은 수정하지 않았다.

## CPU 시험

isaac311, `CUDA_VISIBLE_DEVICES=''`, `PYTHONDONTWRITEBYTECODE=1`, cacheprovider 끔. 새 시험은 변경 전 **48 failed, 2 passed**로 계약 누락을 확인했다. 최종 관련 7개 시험 파일은 **149 passed**. 원출력 `/home/jay/mai/tmp/verifier-lx/a-spawn-final.log`.

- 모든 4종×10레벨: 실제 출력 trimesh에서 footprint 지지 검사.
- 구덩이 바닥만 남기기·출발 메시 삭제·모서리와 중심만 지지하면서 내부에 1 cm 틈을 둔 반례는 거부.
- 소비자 A 연결 제거·reset jitter 되살림·면적 검사 제거·callback의 검사 우회 돌연변이는 각각 pytest rc1로 검출. 스크립트와 원출력 `/home/jay/mai/tmp/verifier-lx/a_spawn_mutants.py`, `a-spawn-mutant-*.log`.
- 기존 `eval/start_sheet.py` SHA `15e830bd…`, `terrains/sparse_terrains.py` SHA `5f296cf7…`는 PR #603 이전과 동일. EX-41 경로·기본 reset 범위는 바이트 그대로다.

## 가지 · 적용 경계

02:21 지시에 따라 **PR #600의 3ecac51d 위에** `verifier/ex42-a-reset-1111` 가지를 기존 verifier-lx worktree에서 만들었다. 그 부모에는 `start_go2_v2.py`가 아직 없어 이미 병합된 **본인 PR #603 d0bd5a03**을 의존 커밋 `61cb808a`로 옮겼다. 남의 파일을 사본에서 복사하지 않았다. PR base는 `sonnet-code/e0-runtime-1110`; #600 병합 뒤 통합 가지로 바꾸면 #603의 기존 변경은 통합 정본에 이미 있다.

**이번 범위 구현 막음 0.** 소비자 A 연결까지 포함했다. E0 무노출 허용 여부를 새로 판정하거나 E2 시작을 승인하지 않는다. E2 첫 징검돌 노출 전에는 새 소스의 reset 표가 실제 env에 적용되는지 Kit 장착 검사로 되읽어야 한다. 이번 작업은 GPU/Kit을 실행하지 않았다.
