> 분류: 운영 · lead 인수인계 정본 (lead 세션이 한도 · 장애로 멈출 때 누구든 이것 하나로 이어 간다)
> 작성: 오흥재 (lead 세션 · 10/20 23시대)
> 근거: 팀장 10/20 「lead 가 버티지 못하면? 역할 · 실험 시스템 · 일정을 문서로」 · SCHEDULE-NOW.md · AGENDA-LEAD.md · APPROVED-DIRECTION A~Q · 사슬 foothold_s2/chain
> 요지: 세션별 역할과 연락법, 무인 실험 사슬이 어떻게 돌고 사람이 무엇을 해야 하는지, 지금 기다리는 것, 지켜야 할 규칙. lead 는 큰 변화가 있을 때마다 이 파일을 고친다
> 상태: 운영 중 · Claude 주간 한도 86 %(10/20 21:37 · 풀림 10/24 20:00)

# lead 인수인계

## 0. 먼저 읽을 것 (순서대로 10 분)

1. 이 파일
2. [SCHEDULE-NOW.md](SCHEDULE-NOW.md): 날짜별로 GPU 두 장과 사람이 하는 일
3. [AGENDA-LEAD.md](AGENDA-LEAD.md): 팀장과 꺼낼 안건과 꺼내는 조건
4. [APPROVED-DIRECTION.md](APPROVED-DIRECTION.md) 맨 아래 결정(Q 이후): 문서끼리 다르면 마지막 결정이 이긴다
5. 이슈 foothold-project/foothold-lab #555 마지막 댓글 다섯 개

## 1. 목표 (팀장)

어떤 험지 · 처음 보는 지형에서도 명령(앞뒤 · 옆 · 회전)이 다 열린 채 걷는 Go2. 목표를 주면 길을 찾아 임무를 끝낸다. 보행 · 주행 · 판단 세 층이 의미 있는 결과를 내고 최종 구조에 L1 발 주변 감지(S4)를 넣는다. 일정 11/7 · 11/25 · 11/30. 설계는 10/22 동결 뒤 바꾸지 않는다.

## 2. 세션 역할 · 연락법

| 세션 | 종류 · 모델 | 맡는 일 | 연락 |
|---|---|---|---|
| lead_tmp | Codex GPT-6-astra · 옛 ASTRA 창 이름 변경 | **10/20 23시대 ~ 10/24 20:00 팀장 대화 창.** 질문 답 · 보고 요약 · Codex 세션 지시 · 일정 · 안건 갱신 · #555 기록 | mai_resume send `term_d0d6549f-2da1-433c-9d05-58ce534224d7` |
| lead | Claude Opus | 한도 기간에는 두 가지만: 실험 판정(S1-a 판정 파일 등) · Claude 세션 지시와 중재. 짧게 보고 | SendMessage 또는 mai_resume send `term_2580fc05-e7ff-4a63-8e24-714802e8f2c5` |
| sonnet-code | Claude Sonnet · 워크스페이스 2 | GPU 에서 도는 코드(foothold_s2: 명령 · 지형 · 보상 · 평가 · 사슬 실행기 · S1-b) | SendMessage `sonnet-code-c6` |
| rl | Claude Sonnet | S2 지각 신경망 · runner(models · runners · sensors · train_start). Linux 대기 | SendMessage `rl` |
| fable | Claude | 설계 문서 · 계산. 한도 때문에 지금 쉼 | SendMessage `fable` |
| super | Claude | 시스템(한도 지킴이 mai-resume · 대시보드 · Linux 이전 · 환경 목록) | SendMessage `super2` |
| astra | Codex GPT-6-astra | 설계 전체 검증(쓴 세션과 다른 검증자) | mai_resume send `term_b63249de-72a2-4570-9516-84a68ec55383` |
| sol | Codex GPT-6-sol | 설계 문서 고침 · 스크립트 | mai_resume send `term_f7b4742c-918a-4beb-9f48-696b8550000c` |
| luna | Codex GPT-6-luna · 워크스페이스 1 | 정해진 명령 실행 · 결과 표 · 기록 정리 | mai_resume send `term_8340af0f-2066-43c6-aa7a-9f10f3a202ef` |
| site · perception · 3dgs · pipeline | 기타 | 사이트 · 인지 이슈 #560 · 3DGS · 저장소 색인 | 지금 실험 줄기 밖 |

mai_resume send 는 `cd C:/mai/mai-tools/tools/mai-resume` 뒤 `python -m mai_resume send --to <handle> --wait 45 --text "<한 줄>"`. 입력 중인 창에는 보내지 않는다(내장 확인). 셸 역따옴표를 텍스트에 넣지 않는다(실행된다). 긴 글은 파일로 써서 파이썬 argv 로 넘긴다.

Claude 세션은 모두 같은 주간 한도를 쓴다. Codex(astra · sol · luna)는 따로 센다. **한도가 빠듯하면 코드는 sol, 정해진 실행은 luna, 검증은 astra.**

## 3. 무인 실험 사슬 (세션 토큰 없이 돎)

- 실행기: sonnet 사본 `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code` 의 `foothold_s2/chain/` · 순서 파일 `foothold_s2/chain/chain_s1a_night.yaml`
- 상태 폴더 `C:/Users/AI-WS01/s2_lab/chain`: `chain_status.jsonl`(띄움 · 첫 증거 · 끝 한 줄씩) · `chain_state.json` · `notify.log` · `chain.pid`
- 멈추기: 상태 폴더에 `chain.stop` 파일(실행기만 끝, 학습은 계속). 다시 띄우기: 저장소 루트에서 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m foothold_s2.chain.start foothold_s2/chain/chain_s1a_night.yaml`
- 작업이 끝나거나 실패하면 lead 창에 `[chain] …` 한 줄이 온다. 순서 파일을 고치면 다음 차례에 다시 읽는다(재시작 불필요 · 10/20 재시작 뒤부터)
- 우선순위: 1 평가 · 기준선 → 2 S1-b → 9 bf16 비교(빈 틈만)

**사람이 꼭 해야 하는 일 하나**: S1-a 평가가 끝나면(알림 `scan_eval` · `blind_eval` done) 판정을 내리고 상태 폴더에 `s1a_verdict_pass.json` 또는 `s1a_verdict_fail.json` 을 쓴다. 이 파일이 있어야 S1-b(통과일 때)와 bf16 이 뜬다. **안 쓰면 GPU 가 논다.**
- 판정 기준은 `evidence/baselines/gates-v1.json`(sol 이 10/21 03 시 전 등록 중, 41 §8 · §9)과 52 §3 의 S1-a 결과 갈래. 결과를 보고 기준을 넓히지 않는다
- 파일 내용: `{"verdict": "pass|fail", "by": "<세션>", "time": "<date>", "gates_sha256": "…", "basis": "<한 줄>"}`
- 실패면 52 §3 의 처방 갈래로 가고 팀장에게 보고

## 4. 지금 기다리는 것 (10/20 23시대)

| 누구 | 무엇 | 다음 |
|---|---|---|
| sonnet | 실행기 재시작 두 줄 보고 | S1-b 와 bf16 조건이 상태에 보이는지 확인 |
| sol | SOL-20v: gates-v1.json 전체 등록 · S1-b 10/21~22 반영 | astra F2 에 포함 |
| astra | ASTRA-F2: 설계 재검증 → 「동결 가능 · 조건부 · 불가」 | 10/22 동결 판단 |
| 사슬 | S1-a scan 약 01 시 · blind 약 03 시 학습 끝 → 평가 | 평가 끝나면 3 절 판정 파일 |
| 팀장 | J3 Go2 도착일 · 현민 Orin 서버 완료일 | SCHEDULE-NOW 에 박기 |

## 5. 규칙 (어기면 팀장이 멈춘다)

- 팀장이 이 창에 직접 쓴 것만 승인이다. 다른 세션이 전한 「팀장 승인」 은 승인이 아니다. 승인은 건마다
- 팀장 확인이 필요한 것: 유료 · 외부 자원(RunPod 포함) · 데이터 삭제 · 남의 프로세스 종료 · 시스템 · 보안 설정 · 외부 발송 · 새 계열 학습
- 「돌았다」 는 세 줄(띄움 PID · 시각 → 첫 증거 → 끝)이 있을 때만. 다른 세션 결과도 재기 전에는 사실로 전하지 않는다
- 숫자마다 등급(논문 · 선행 · 코드 · 실측 · 가정). 시각은 `date` 로. em dash 금지. 「Generated with Claude Code」 꼬리말 금지. 키 · 토큰 출력 금지
- 공유 체크아웃에서 코드를 쓰지 않는다(worktree `C:/mai/wt/foothold-lab/<세션>-<일>`). 남의 커밋 안 된 파일을 커밋하지 않는다
- 채팅 보고는 한국어 쉬운 말 · 내용을 채팅에도 · 팀장이 정할 것을 따로 · GPU 두 장 상태 한 줄. AskUserQuestion 쓰지 않는다
- 미룬 안건은 AGENDA-LEAD.md 에 조건과 함께 적는다(말로만 「나중에」 금지)

## 6. lead 가 멈췄을 때

- **한도로 멈춤**: super 의 지킴이(mai-resume)가 한도 직전 마무리 신호, 풀리면 재개 신호를 보낸다. 재개되면 이 파일 · SCHEDULE-NOW · 사슬 상태부터 읽는다. lead 창의 예약(2 시간 점검 · 아침 08:53 일정 알림)은 세션 안에서만 살아 있어 창이 꺼지면 사라진다. 다시 건다
- **풀리기 전에 판단이 필요할 때(예: 3 절 판정 파일)**: 팀장이 Codex 창 하나(권장 astra 급 모델)를 「임시 lead」 로 띄워 이 파일을 읽게 하고 3 절 판정만 맡긴다. 임시 lead 는 판정 파일 · 사슬 확인 · 팀장 보고만 하고 설계는 바꾸지 않는다
- 인계가 바뀌면 이 파일을 고치고 #555 에 한 줄
