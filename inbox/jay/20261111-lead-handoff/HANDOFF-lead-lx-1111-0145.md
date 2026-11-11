(01:45) lead-lx 인계 · 11/10 오후 ~ 11/11 01:45 (Linux 첫날 · L · M · E0 메시)

**목표:** EX-42 를 Linux 에서 두 장으로 띄울 수 있게. 오늘 밤 E0 까지.

**결과 (실측)**
- L1: 공식 Go2 두 장 1.56 배 · NCCL_SHM_DISABLE=1 필요 (~/gpu-check). L2: 같은 코드에서도 Linux 가 Windows 보다 한쪽으로 밀림 → 조건부 통과 (decisions ac35f794). 기준선: m12000 Linux 유지 통과 (Windows 와 같음), m13000 첫 기준 (PR #596).
- M (두 장 속도): M1 한 장 20.18 s/회 (1.38 배) · M2 1536x2 11.46 (2.43 배) · M3 3072x2 20.95 (6144 env, 처리량 2.65 배) · M4 반복 20.31 · 20.48 · 두 장 10.95. M4 평가: 두 장 = 한 장 (생존 차 ≤ 2/64, 한 장끼리 ≤ 1). 같은 저장본 GPU0 대 GPU1 평가 차 ≤ 1. 원자료 /mnt/win-d/mai/data/foothold/s2_lab/ex42_speed_probe_20261110_234123.
- EX-42 전용 평가기 (PR #598, GPU0 허용 c2e7c17e): m13000 관리 9/11 측정 · 판정 HOLD (기준선 · 반복 폭 없음).
- E0 메시: B (#601 scripter) · C (#599 analyst) · D (#602 analyst, wall 1.20 / 0.80 팀장 위임 추정) · A 축척 · E L0 (#603 verifier) · 측정 · 합치기 · 장착 (#597 · #600 sonnet). 39 종 76 열 메시 01:40 생성 7.3 초 · 0.91 GiB (ex42_mesh_1111/seed42_ABCDE). 장착 확인: 환경 생성 · 스캔 오차 4e-6 m 통과, 실패 = C gap 시작점이 틈 위 (analyst 고치는 중 · 원인 = 어댑터가 타일 중앙을 ±0.5 m reset 에 넘김).

**결정 (팀장 lead 창)**: 재고정 74ae601e · PR 593 병합 · EULA · L2 조건부 · M 미리 승인 (f6ca4516) · 지형 지금 만들기 (7d736649) · E0 입구 졸업 → 팀장 채택 갈음 · M3 6144 확정 (285348de) · 조용한 점검 채팅 0 · 시각 훅 (super) · 서기 scribe-lx · 세션 전달 규칙 (messaging-rule-lx-1110.md).

**도는 것 (01:45)**: M3_50 (두 장 · 6144 · 50 회, 6144 도 같은 학습인지) 01:43 첫 회 25.0 s · ~/gpu-check/m3_50.sh. 끝나면 model_50 을 EX-42 평가기로 재서 M4 a · b 와 비교.

**남은 것 (E0 까지)**: C 시작점 고침 → 39 종 메시 다시 · 장착 확인 통과 / B rough 되돌림 (20° 는 3 m 굴곡 경사, 거칠기 0→0.16 m 별도 · SPEC-ame2-go2:144) / 종별 선언 (planner ex42-declarations-1111.json, B · D 추가) → 종별 영수증 → terrain_manifest.json / calibration (m13000 을 E0 메시에서 같은 시드 2 + 시드 바꿔 3) / 6144 로 ex42-prep · EX-42.yaml · 정본 D159 고침 + 승인 해시 재고정 + E0 승인 칸 / PR 병합 #594~#603 / 출발 막음 26 / N1 Kit 예행.

**기다리는 것**: 팀장: PR 병합 · 재고정 · N1. planner: 가정 다섯 값표 · v0.17. analyst: C 시작점. scripter: B rough. reviewer: #600 · #603.
