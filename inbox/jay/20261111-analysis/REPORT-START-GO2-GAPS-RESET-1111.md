# EX-42 A gaps reset 확장 · #609 병합 충돌 정리

> 분류: A/지형씬제작 · 구현 검증
> 작성: verifier-lx · 2026-11-11
> 근거: lead-lx 02:41 의뢰 · #609 reviewer PASS 전달 · 원본 장착 메시 CPU 재계산
> 요지: 통합 내용 보존 병합 뒤 gaps에도 x/y/yaw 0과 전체 지지면 검사를 적용
> 상태: CPU 확인됨 · GPU/Kit 미실행 · 실제 reset 재측정 별도

## #609 충돌 정리 완료

통합 **56870d24**를 #609 가지에 merge했다. 충돌 상대 `start_go2_v2.py` blob은 **bf3614d0289e44265e486e68589900a5c0a740da**로, 이미 병합된 본인 #603 원본과 동일했다. 이 위에 #609의 안전 원점 변경을 보존해 해결했다.

통합 tree의 모든 파일 blob을 merge index와 대조했다. 차이는 의도한 `start_go2_v2.py`와 `ex42_column_reset.py`의 A 연결 한 줄뿐이고, 다른 통합 파일 삭제·변경은 0이었다. CPU **85 passed** 뒤 병합 커밋 **adf4bac05607b1320f167289cabd9272fbee6098**을 force 없이 push하고 원격 SHA를 확인했다. run과 lead-lx에 보고했다. 이후 #609가 **45134310**으로 병합된 것을 되읽고, 새 gaps 가지를 그 통합 HEAD로 fast-forward했다.

## 이번 별도 PR 변경

- `RESET_RANGES`에 **gaps만** 추가: x/y/yaw 모두 `(0,0)`. 기존 네 kind, flat·연속 kind, EX-41 경로는 유지.
- 기존 `spawn_origin` 전체 삼각형 지지 검사와 mesh callback·캐시 경로가 gaps에도 적용된다. 0.70×0.50 m 영역의 지지가 없으면 오류이며 구덩이나 도착 단으로 바꾸지 않는다. 원점 `(0.5,4,0)`, 틈 치수, 메시 형상은 변경하지 않았다.
- 실제 A reset 소비 표의 선언 적용 열은 **22 → 25**(gaps 3열 추가), 기본값 유지 열은 **28 → 25**. CPU 실제 reset 함수까지 내려가 선언 열의 위치·yaw 오프셋이 0임을 확인했다.
- 원본 메시 재계산 도구의 예상 수를 **220 → 250칸**으로 확장했다. 이전 220칸 증거는 덮어쓰지 않고 새 evidence 파일에 썼다.

## 반례와 검증

reviewer의 「33%」는 lead가 전달한 수치이며 이번에 같은 표본으로 재집계하지 않았다. 직접 재현한 것은 gaps L9에서 옛 reset x=−0.5와 뒤쪽 footprint −0.35를 합치면 첫 타일 x=−0.35로 나가 **지지 삼각형이 없는** 반례다. 이를 전체 실패율이나 정책 실패로 확대하지 않는다.

| 검증 | 실측 |
|---|---|
| 변경 전 새 계약 시험 | **12 failed, 50 passed** |
| 변경 후 관련 7개 시험 파일 | **164 passed** |
| gaps 선언 제거 | 실제 A 소비 검사 **1 failed** |
| gaps 안전 원점 검사 우회 | 지지면 없는 반례 **1 failed**, 기존 4종 **4 passed** |
| 원본 NPZ 확인 | 장착 검사와 geometry SHA **eafbada6c431fdc37b2a0e20094a404f0caad96d58cb2bcaca761629acf0b01d** 동일 |
| 실제 메시 지지 | **25열 × 10레벨 = 250칸**, 전체 영역 면적 검사 및 독립 교점 **41,250점**, 높이 최대 절대값 **0.0 m** |

CPU 원출력 `/home/jay/mai/tmp/verifier-lx/a-gaps-final.log`; 제거본 `/home/jay/mai/tmp/verifier-lx/a_gaps_mutants.py`, `a-gaps-mutant-*.log`. 원본은 `seed42_ABCDE_v2/terrain_mesh.npz`와 `mount_check_ABCDE_v3_cuda0.json`; 원자료 이름의 판이 달라도 직접 SHA를 맞춰 사용했다. 전체 행과 파일 SHA는 `evidence/start-go2-gaps-spawn-mesh-cpu.json`에 있다. 재현 도구는 `tools/verify_start_go2_spawn_mesh_cpu.py`.

**구현 범위 막음 0.** CPU 기하·reset 소비 시험이며 Kit 발 접촉의 재검 통과를 주장하지 않는다. 원자료·운영 파일·학습 프로세스는 변경하지 않았다.
