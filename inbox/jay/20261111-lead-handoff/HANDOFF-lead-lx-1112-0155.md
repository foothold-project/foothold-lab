(01:55) lead-lx 인계 · 11/11 19:59 ~ 11/12 01:55

분류: 인계 · 작성: lead-lx · 근거: 원장 decisions.tsv (feature/verify-v2-mvp-jay) · run 받은편지함 · PR 기록
요지: E1 관문 FAIL 의 원인을 발 미끄러짐으로 좁혀 foothold_slip −0.15 재학습 1000 회를 띄우고, 끝나면 재측정 → 관문 → E1F 로 자동 이어지게 걸어 둠
상태: E1 재학습 진행 중 (01:36 기동 · ~08:00 끝)

## 목표
EX-42 를 20,000 회 (지금 정책 계보 기준) 까지 사람 없이 이어 학습 · 평가. 팀장: 숫자보다 Go2 보행 성능.

## 결과 (숫자는 원자료)
- 끝난 E1 (11:45 · b379eb98) 관문 FAIL: 실패 칸은 D44 정지 → 재출발 하나. 나머지 PASS.
- D44 새 정의 (팀장 21:15 ⑤ · #718): m1000 gt 36/64 · pred 55/64 · 부모 m13000 gt 22 · pred 13. 회전 모두 64.
- 원인: 오름 중 디딘 앞왼발 옆 미끄러짐 (부모 FL −0.050 · E1 −0.104 m/s) → 꼭대기에서 옆 0.3 m · 발이 계단참 밖 (gt 실패 28 중 25). foot_slip 항 가중 0 (E1 params/env.yaml:2443).
- 재학습 (나) 승인 (팀장 23:48): 끝난 E1 과 같은 사본 b379eb98 + foot_slip 한 줄. 50 회 점검 −0.25 벌점 몫 10.93 % FAIL → −0.15 (67d2506d) 7.06 % · 추종 100.4 % PASS.
- 1000 회: run /home/jay/data/foothold/s2_lab/ex42_main_20261112_013611/main/EX-42-B-E1-slip1000_20261112_013611 · 로그 /home/jay/mai/tmp/runner/E1_slip1000_20261112_013611 · setsid nohup (첫 시도는 torchrun 이 셸과 같이 죽어 rank 가 TCPStore 대기로 멈췄음).
- 재측정 대기: PID 3290831 (통합 6b8762dd #731) · 상태 /home/jay/mai/tmp/verifier-lx/remeasure-live-1112/wait.log · 학습 끝 → 아홉 (부모 m13000 · 끝난 E1 m250~1000 · 재학습 m250~1000) 마찰 0.8/0.6 재측정 → 관문 → PASS 면 E1F 자동 · FAIL/HOLD 면 받은편지함 알림.

## 팀장 결정 (원장)
bd8960ba ⑤ D44 정의 · fecfd1e8 (나) 재학습 · 2f92425e 부재 중 검토 PASS PR 병합 · Isaac 권한 상시 · 024b12dd −0.15 확정. lead 결정: 예산 = E0 250 + 재학습 E1 1000 = 1250 (0 단계 · 버린 첫 E1 은 따로) · 축 순서는 정본에 고정 (planner).

## 병합 (19:59 이후)
#708 #710 #711 #712 #713 #716 #717 #718 #720 #721 #726 #727 #730 #731. 통합 최신 6b8762dd 뒤 #730.

## 남은 것 · 담당
- E2 이후 출구 판정: E3 scripter (진행) · E4/E5 analyst · E6a/E6b verifier · M verifier.
- E1F → 다음 단계 launcher 인자 · BUDGET_USED 생산자: verifier PR 진행.
- E3: 노출 영수증 #732 (sonnet · 덮어쓰기 막음 고치는 중) · 깃발 명령 15 % (CG:281) 가 prep E3 행 · 학습 코드에 없음 (scripter 01:54 발견 · 담당 미정).
- E2 메시 M0~M3 #735 (analyst) · M2/M3 Kit 측정은 학습 끝난 뒤 lead.
- 축 순서 · 정본 E3 '네 종/다섯' 문구: planner.
- HiPAN: 계획 v2 (feature/fable-25a-jay eb37e668) · PR-1~3 병합 · 정할 것 여섯 (§9) 은 팀장에게 묶어서.
- 영상: RULES-HUB 4 절 v3.4 합성 경로 연결 (runner) · 다음부터 VLC 재생목록 같이.
- 문서 동기화는 scribe 상시 역할 (WORKLIST · CG · LINEAGE · FAILURE-LOG).

## 교훈
머리 시각을 짐작으로 여러 번 적음 (date 로 재기 전 쓰지 말 것) · 감시 파이프의 cut 이 줄 버퍼를 막아 30 분 무신호 · 영상 규칙 4 절을 의뢰문에 안 넣음 · 인계를 저장소 밖에 씀.
