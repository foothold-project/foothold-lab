# EX-42 E2 종류별 도착선 측정
> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 (scripter-lx 반영) · 2026-11-11 17:04
> 근거: REVIEW-9dd845d2.md · c333 메시 원자료
> 요지: 공통 7.0 m 도착선을 없애고 종류와 레벨의 저장된 메시에서 도착선을 잰다.
> 상태: CPU 확인됨 · Kit 미실행

원자료: `/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333/mesh_manifest.json` · SHA256 `820dec9f4dbff33fa8b49ad0e2907a412024f09539f7b7fabc2ca290b2a5581d`.

도착선은 저장 메시 삼각형을 아래로 광선 측정해 구한다. 중심과 좌우 0.4 m 세 줄에 출발 높이보다 0.05 m 이상 낮지 않은 지지면이 끝까지 연속한 첫 x를 택한다. x는 각 타일 원점 기준이다. 기준선도 영수증에 메시 해시와 함께 남긴다.

| 종류 | L0 도착선 m | L3 도착선 m |
|---|---:|---:|
| stepping_stones_low | 6.50 | 6.50 |
| stepping_stones_high | 6.50 | 6.50 |
| balance_beams | 6.50 | 6.50 |
| stepping_beams | 6.50 | 6.50 |
| gaps | 5.10 | 5.25 |

CPU 답을 아는 입력: 지지면 시작 5.6 m인 합성 gaps 타일은 원점 기준 5.1 m, 시작 7.0 m인 stepping 타일은 6.5 m로 읽는다. 메시 SHA가 다르면 거절한다. `test_ex42_kind_completion_cpu.py`와 `test_ex42_kind_cell_cpu.py` 합계 10 passed. 실제 정책 성공률은 이 변경으로 다시 측정하지 않았다.
