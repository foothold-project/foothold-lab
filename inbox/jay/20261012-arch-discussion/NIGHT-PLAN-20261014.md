> 분류: 운영 · 밤 작업 순서 (10/14 00:06 → 아침 보고)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 00:06
> 근거: #550 인계 6148371113 · VERIFY-astra-17c ~ 17e · AGENTS 7 절 (mai-os 0699447)
> 요지: 세션이 끊기거나 heartbeat 로 깨어나도 이 표의 위에서부터 「안 끝난 첫 줄」 을 이어 간다. 검증이 걸린 줄은 판정 파일을 직접 읽은 뒤에만 띄운다
> 상태: 진행 중 (줄마다 끝나면 이 파일에 시각 · 근거를 적는다)

| 순서 | 일 | 시작 조건 | 끝 판정 | 상태 |
|---|---|---|---|---|
| 1 | GPU 0: 1043 off 끝 → 스크립트가 검증 → on 갈래 | 스크립트가 알아서 | 콘솔 `cmdr_s1043_off_u4000 VALID` · on START | off VALID · on 00:18:20 시작 (끝 05:40 무렵 추정) |
| 2 | ASTRA 17f 판정 (v3 관문 · 같은 시험지 고침 · S2 판 2) | 의뢰함 23:53 | `VERIFY-astra-17f.md` 첫 줄 | 끝 00:17 · 고쳐서 기동 (b77106d2) |
| 2b | ASTRA 17f-2 보내기 (S2 encoder W · r 제안 검토 · `TASK-astra-17f2-s2-encoder.md`) → 판정을 팀장께 채팅 · #550 으로 | 17f 판정 파일이 나온 뒤 (ASTRA 는 한 번에 하나) | `VERIFY-astra-17f2.md` 첫 줄 | 00:21 보냄 · 검사 중 |
| 2c | ASTRA 17h 보내기: lead 의 읽기 · 컨텍스트 관리 규칙 검토 (`TASK-astra-17h-reading.md`) | 17f-2 판정 뒤 | `VERIFY-astra-17h.md` 첫 줄 | |
| 3 | GPU 1: 같은 시험지 CTS E1 20000 짧은 기록 (`ce12/run_dump.py --which cts` · v3 관문 · 별도 registry `isaac_usd_registry_v3.json`) | 17f 가 허용 | 수집 COLLECTED · `compare_native --recompute_action` · 승인 APPROVED 또는 PENDING 까닭 | 00:25 띄움 (registry v3 전용 · 시험 117/117 · 해시 고정 job tmp ce12_cts_launch_sha.txt) · APPROVED 채택 전 17f 4.2 ~ 4.4 고침 필요 |
| 4 | GPU 1: 같은 시험지 v2 기록 (예상 변환 0) | 3 승인 | 같음 | |
| 5 | 하위 작업 결과 lead 재실행: 미경험 v5 (17e 고침) · 무작위화 (17d 고침) | 보고 옴 | 시험 · 변이 숫자를 lead 가 다시 셈 | 무작위화 27/27 lead 확인 · 미경험 v5 보고 옴 (51/51 · 38/38 · 출력 out_uncr_v5 · --approval 파일 요구) lead 재실행 전 |
| 6 | ASTRA 17g (미경험 v5 · 무작위화) | 5 끝 | 판정 파일 | |
| 7 | GPU 1: 미경험 full (73 또는 75 실행) · 무작위화 smoke (`--stop_after_smoke`) → 장면 하나씩 | 17g 허용 · 3 · 4 와 겹치지 않게 | 재검사 valid · 영상 전 프레임 검사 | |
| 8 | 아침 7판: diag 7 칸 확정 문장 · 밤 결과 · 결정 목록 · Top-down · 팀원 PR (조각은 job tmp `e12page/`) → 빌드 → 1920 · 1366 · 390 · 라이트 · 다크 렌더 확인 → 게시 → #550 · #546 · 채팅 | 아침 | 렌더 확인 기록 | |
| 9 | super2 에 「GPU 1 out_* 실행 끝」 한 줄 (RL 백업 나머지 채우기용) | 7 끝 | 보냄 | |

**팀장 결정 대기:** Windows 업데이트 재부팅 대기 · 사용 시간 07 ~ 01 (01 ~ 07 자동 재부팅 위험 · 일시 중지 권고 · 00:24 채팅으로 물음) · S2 encoder 고정 구간 W 의 단위 (PPO iteration 또는 optimizer step) 와 W · r 값.

**읽기와 컨텍스트 (팀장 10/14 00:05 · 00:20 지적 · 00:22 고침):** 판단의 근거가 되는 글 (ASTRA 검증 · 하위 작업 보고 · 설계 문서) 은 **끝까지 읽는다.** 00:16 에 17f 를 절만 골라 읽었다가 1 · 2 절의 사실 (야간 셸 시험이 Windows 의 다른 bash 를 집음) 을 놓칠 뻔했다. 줄이는 것은 반복뿐이다: 끝난 작업 목록의 재주입 (지움) · 같은 파일을 두 번 읽기 · 통과한 시험의 줄 하나하나 (요약과 모든 FAIL 줄은 본다) · 렌더 확인이 아닌 그림. 이 규칙도 ASTRA 17h 로 검토받는다.
