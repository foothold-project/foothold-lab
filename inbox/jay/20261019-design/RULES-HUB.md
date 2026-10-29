> 분류: 운영 규칙
> 작성: 오흥재 (lead 정리) · 2026-10-25
> 근거: 팀장 10/25 〔원문 비공개〕 · EXPERIMENT-RULES 1.4 · LEAD-STYLE-AGENTS · mai-os AGENTS.md
> 요지: Claude · Codex 모든 세션이 처음 여는 규칙 입구. 세션 역할 · 운영 · 실험 · 영상 렌더 · 승인 원장을 여기서 찾아간다.
> 상태: v1.5 · 새 규칙은 이 문서나 아래 정본에 더하고, 같은 말을 두 번 하게 한 일은 「반복 지시」 표에 올린다

# 규칙 입구 (Claude · Codex 공용)

**읽는 순서**: 이 문서 → 맡은 일의 정본 한 장 → 작업. 둘이 다르면 더 엄격한 쪽. 시스템 전체 규칙은 mai-os `AGENTS.md` (이 기기 `C:/Users/AI-WS01/Desktop/jay/Claude/AGENTS.md`) 가 정본이다.

| 묶음 | 정본 | 무엇 |
|---|---|---|
| **실패 로그 (먼저)** | [FAILURE-LOG.md](FAILURE-LOG.md) | 반복 실수 R · 교훈 M, 지시 이해 · 운영 · 기술 세 갈래. 일 시작 · 다음 단계 걸기 전에 읽고 의뢰문 첫 줄에 번호 |
| **지금 할 일 · 결정** | [WORKLIST.md](../20261028-plan/WORKLIST.md) | W 작업 · R 요구 · D 확정 결정(묻기 전 decision_check) |
| **실험 한 판 흐름 (10/29~)** | [FLOW-experiment-cycle-1029.md](../20261028-plan/FLOW-experiment-cycle-1029.md) | 흐름 · 판단 세 단계 · 영상 세 층 · 평가 사다리 · 기준 축 · GPU 순위 · W50 |
| 영상 화풍 | 코드 `foothold_s2/eval/video_style.py` (브랜치 feature/w49-video-style-jay, main 합치기 전) | L4 · 채도 ×1.25 · 이름 규칙. 문서가 아니라 코드가 정본 |
| 실험 규칙 | [EXPERIMENT-RULES.md](EXPERIMENT-RULES.md) | 설계 · 실행 전 확인 · 판정 · 분석 · 기록 · 구현과 리뷰 손 나누기 (3.1 절) |
| 작업 방식 | [LEAD-STYLE-AGENTS.md](LEAD-STYLE-AGENTS.md) | 팀장 기준 · 돌았는지 세 줄 · 검증 · 보고 말투 |
| 실험 흐름 (옛 판, 10/23) | [EXPERIMENT-FLOW-20261023.md](EXPERIMENT-FLOW-20261023.md) · [EXP-MAP](../20261021-experiments/EXP-MAP.md) | 무엇을 묻고 무엇을 알았나 |
| 지금 설계 | [DESIGN-EX30-31.md](../20261025-experiments/DESIGN-EX30-31.md) 맨 위 한 장 요약 | EX-30 · 31 |
| 착안 · 출처 | [PROVENANCE-START-vs-OURS.md](../20261025-experiments/PROVENANCE-START-vs-OURS.md) | START 와 같은 것 · 다른 것 · 참고 논문 |
| 10/25 문답 | [QA-LEAD-20261025.md](../20261025-experiments/QA-LEAD-20261025.md) | 팀장이 묻고 이해를 확인한 내용 (실험 번호 · 창 1 · 문턱 · AdaSmpl · 노이즈 · 계단) |
| 실험 상황판 | https://ai-ws01.tail025053.ts.net/lab/ (tailnet 전용, 파일 C:/Users/AI-WS01/s2_lab/lab_status/index.html) | lead 가 20 분마다 갱신, 새 결과 때 텔레그램 |
| 개념 풀이 | [NOTE-start-learning-gt-1023.md](../20261023-experiments/NOTE-start-learning-gt-1023.md) | HMap GT · Pred · AdaSmpl 등 |

## 1. 세션 역할 (10/25 부터)

| 세션 | 도구 · 모델 | 맡는 일 | 하지 않는 일 |
|---|---|---|---|
| lead | Claude Opus | 총괄 · 설계 정리 · 결정 기록 · 팀장 보고 · GPU 기동 지시 | 남의 미커밋 커밋 |
| planner (옛 fable) | Claude Fable · effort high | 설계 반박 검토 · 다음 판 설계 초안 | 구현 · GPU |
| sonnet-code | Claude Sonnet | 구현 (고정 코드에서 분기한 새 worktree) · 승인된 실행 | push (lead 확인 전) |
| reviewer | Claude Opus | 구현 커밋 `/code-review` · `_out/review/REVIEW-<커밋>.md` | 코드 수정 (--fix 금지) · 커밋 |
| super2 | Claude | 시스템: mai-watch · 한도 지킴이 · 세션 기록 · Linux 이전 (Claude 쪽) | 실험 판단 |
| analyst (d0d6549f, 옛 lead_tmp) | Codex Astra max | 독립 분석 · 설계 반박 | 코드 수정 · GPU 기동 |
| verifier (b63249de, 옛 astra2) | Codex Astra | 숫자 재계산 · 결과 검증 | 코드 수정 |
| scripter (f7b4742c, 옛 sol) | Codex Sol | 분석 · 실행 스크립트 (CPU) | GPU 기동 (lead 요청 없이) |
| runner (8340af0f, 옛 luna) | Codex Luna | 정해진 명령 · 렌더 · 문서 동기 | 판단 |
| pipeline (6bc3da38) | Codex | Linux 이전 (Codex 쪽) | 실험 |

**사용 한도는 도구로 읽고 사실만 전한다 (10/27 00:4x 팀장 〔원문 비공개〕)**: 모든 세션 (Claude · Codex) 은 한도를 말하기 전에 `python C:/mai/wt/foothold-lab/lead_tmp-20261023/_out/tools/limits_now.py` 를 돌려 그 줄을 그대로 옮긴다. 정본은 ~/.mai/limits.json (창마다 사용 % · 다시 채움 시각). 상태 표시줄의 〔원문 비공개〕 「short」 「[>200%]」 는 지금 속도가 이어질 때의 **예측** 이라 사실처럼 말하지 않는다 (10/27 00:3x lead 가 sonnet-code 의 〔원문 비공개〕 을 「47 분 뒤 한도」 로 잘못 전함, 실제는 50 % 남음 · 03:00 KST 다시 채움). 예측을 말할 때는 「예측」 을 붙이고 근거 (표본 두 개의 기울기) 를 같이 적는다. Codex 는 표본에 주간 창만 있다 (5 시간 창 없음, 00:39 실측).

**일하는 중인 세션에 보낼 의뢰는 대기열로 (10/27 00:4x 팀장 〔원문 비공개〕)**: `python C:/mai/wt/foothold-lab/lead_tmp-20261023/_out/tools/dispatch_queue.py add --terminal <h> --title <제목> --spec-file <파일> [--worktree path:<경로>]` 로 넣으면 orca task-create 로 Task 가 먼저 생겨 Orca 안에 남는다. `dispatch_queue.py loop 60` 이 받는 세션의 화면에 진행 표시가 없고 끝나지 않은 Dispatch 가 없을 때만 worker-start --task 로 보낸다. 실패한 Dispatch 는 대기열로 되돌려 --retry-of 로 다시 보낸다. 한 세션에 한 의뢰씩. 이미 orchestration 의뢰를 받아 일하는 세션에 덧붙일 말은 새 의뢰가 아니라 `orca orchestration send --to dispatch:<그 세션의 dispatch>` (작업자가 확인 지점에서 읽음, 00:45 planner 에 첫 사용). lead 는 받은편지함 대기 (`_out/msgs/orch_wait.py`) 와 20 분 점검 둘 다에서 대기열을 훑는다. 00:42 실측: 바쁨 판별은 analyst · runner · planner 바쁨, reviewer 쉼으로 맞았으나, 쉬는 reviewer 에 보낸 의뢰가 agent_readiness timeout 으로 실패 (입력줄에 이전 keepalive 문장이 회색 제안으로 떠 있던 창, 원인 미확인). 고칠 때까지 같은 실패가 두 번이면 lead 가 그 창을 직접 보고 처리한다.

**세션 지시 · 보고 (v2 · 10/27 01:1x 팀장 확정 〔원문 비공개〕)**

| 할 일 | 방법 | 실측 근거 |
|---|---|---|
| 작업 세션 (runner · reviewer · verifier · scripter · sonnet-code · rulecheck · planner) 에 지시 | `orca terminal send --terminal <h> --text "..." --enter --wait-submit 20`. 회색 제안 문장이 있어도 보낸다. 일하는 중이면 대기 입력으로 들어가 다음 turn 에 읽힌다 | 01:00 scripter 즉시 시작 · 00:52 일하는 runner 입력줄에 들어감 |
| 사용자가 치는 중일 수 있는 창 (lead · analyst · super2 · pipeline 등 관리자 창) 에 지시 | `python -m mai_resume send --to <h> --text "..." --wait 600` (C:/mai/mai-tools/tools/mai-resume, 파이썬 isaac311-moects). 치는 중이면 기다렸다 보낸다. rc 4 면 나중에 다시 | PR #33 (01:15 병합) 뒤: 힌트 빈 창 · 대기 메시지 표시 → 보냄, 친 글 → 막음 |
| 작업 세션의 보고 | `orca orchestration send --run <run> --to run:<run> --type status --subject "[이름] 끝 · 커밋/경로 · 막음 n" --body "..."`. orchestration worker-start 로 받은 일이면 그 preamble 의 `worker_done`. 어느 창에도 치지 않는다 | worker_done 은 진행 중 Dispatch 없이는 거절 (01:00 scripter, task id 를 붙여도) · status 는 도착 |
| 관리자 세션이 보고 받기 | 받은편지함 알림 (Claude Code 가 창 밖 메시지로 띄움, 입력줄에 치지 않음 · 01:0x 팀장 확인) → `orca orchestration check --run <run> --types "worker_done,escalation,question,status"` 로 꺼내 읽고 원자료 대조 뒤 `--ack <delivery>`. 배경 대기는 `_out/msgs/orch_wait.py` (status 포함, keepalive 줄 거름) | 00:13 이후 8 건 수신 |
| orchestration worker-start | 쉬는 창에만. 일하는 창은 기본 60 초 뒤 Dispatch failed (15 분으로 늘려도 실패). 보낸 뒤 2 분 안에 받는 창에 의뢰 문장이 실제로 들어갔는지 lead 가 읽어 본다. 안 들어갔으면 위 orca cli 로 보낸다 | 00:26 runner · 00:33~00:48 analyst · 00:42 reviewer 실패 |

지금 Run: `run_abb2e12cee32` (lead 가 coordinator). 한도는 `_out/tools/limits_now.py` 로만 말한다 (아래). 이 표는 Linux 로 옮긴 뒤에도 같은 순서로 다시 잰다 (super2 · pipeline 정리).

세션 사이 전달 (v1.2 · 팀장 10/25 05:0x 〔원문 비공개〕 · SendMessage 는 팀장 거절): orca-cli 순서로 보낸다. `orca terminal read --terminal <h>` 로 받는 창을 보고 → `orca terminal wait --terminal <h> --for tui-idle --timeout-ms 5000` → `orca terminal send --terminal <h> --enter --wait-submit 20 --text "..."` → 결과의 `turn_started` 로 전달 확인 (안 보이면 `--retry-request <id>` 로 같은 요청을 다시 보고, 새로 보내지 않는다). 팀장이 그 창에 치고 있을 수 있으면 보내지 않는다 (10/20 팀장 글 뒤에 붙은 사고, mai-os#51). **read · wait · send 를 한 명령 (&&) 으로 잇지 않는다. 입력줄의 「❯ 글」 은 작업 세션 창에서는 Claude Code 회색 제안 문장이니 보낸다 (팀장이 치는 곳은 lead 창뿐, R13). lead 창으로 보낼 때만 그 창 turn 이 끝난 뒤 보낸다** (10/25 20:5x planner 보고가 lead 창의 팀장 초안 〔원문 비공개〕 위로 들어간 재발). `mai_resume send` 는 받는 창의 회색 제안 문장에 15 분 넘게 막힌 일이 있어 보조로만 쓴다. (v1.1 의 〔원문 비공개〕 는 이 결정으로 바뀌었는데 15 시까지 고치지 않았다. 7 절 R3.) **lead 창 (팀장이 치는 창, term_2580fc05) 으로 보내는 보고는 `orca terminal send` 를 쓰지 않고 `python -m mai_resume send --to term_2580fc05-e7ff-4a63-8e24-714802e8f2c5 --text "..." --wait 600` 만 쓴다** (C:/mai/mai-tools/tools/mai-resume, 파이썬은 isaac311-moects). 입력줄이 비고 5 초 간격 두 화면이 같을 때만, 보내기 직전 한 번 더 보고 보낸다. 종료값 4 는 〔원문 비공개〕 이니 나중에 다시. 10/26 23:4x 팀장이 lead 창에 치는 중에 runner 보고가 끼어 팀장 글이 섞였다. 원인: 이 줄이 타이핑 감지 없는 `orca terminal send` 를 표준으로 적고 있었다 (10/20 에 만든 타이핑 대기 장치를 규칙이 우회). 23:56 실측 (Claude Code 2.1.310): 친 글이 있으면 감지해 rc 4 (맞음), 빈 입력줄에 회색 힌트가 보이는 창은 오검출로 계속 rc 4 (보내지 못하는 쪽, super2 고침 대상).

## 2. 운영 규칙 (무인 · 한도 · 깨우기)

- **lead 창 보고는 한 줄 (10/26 20:3x 팀장: 다른 세션 보고가 계속 들어와 읽던 화면이 밀려 내려간다)**: 〔원문 비공개〕 만. 전문은 산출 파일 맨 위나 `_out/reports/REPORT-<이름>-<시각>.md`. 막음만 두 줄까지. 이 한 줄 규칙은 다른 세션 → lead 창에만 적용한다. lead 가 팀장에게 하는 답은 채팅에 충분히 길게 쓴다 (팀장 10/26 21:0x 〔원문 비공개〕).
- **main 받기 (10/26 rulecheck G02 · 팀장 〔원문 비공개〕)**: 실험 브랜치 feature/verify-v2-mvp-jay 는 하루 한 번 origin/main 을 merge 해 받는다 (8185320e 첫 회: 충돌은 bot 이 만드는 deliverables/plan/wbs.xlsx 하나, main 판 채택). main 쪽으로 보내는 것은 PR 로, 팀장 확인.
- 한도 지킴이 = 예약 작업 **mai-resume** (vfxpedia/mai-tools `tools/mai-resume`, 상태 `~/.mai/resume/`). `~/.mai/limit-guard` 는 10/20 시제품이며 쓰지 않는다. 계기판이 쓴 `~/.mai/limits.json` 을 읽어 5 시간 93 % · 주간 98 % 에서 마무리 신호, 주간 85~97 % 는 계속 알림, 낡은 값은 알림만. 풀리면 멈춘 일만 재개 신호. Claude 창은 55 분 쉬면 캐시 유지 신호 (한도에 걸린 동안은 안 보냄). 대상은 `~/.mai/resume/targets.txt` (창 handle 앞 8 자리, 1 분마다 다시 읽음, 재시작 필요 없음). 창을 닫고 새로 열면 handle 이 바뀌니 다시 적는다. 새 세션은 super2 에게 부탁한다.
- lead 는 긴 일을 시작하면 20 분 안팎 반복 점검 예약을 건다. 점검은 GPU 두 장 · 실행 생존 · 회신 · 질문을 보고 바뀐 것이 없으면 한 줄로 끝낸다.
- mai-watch 대시보드는 `~/.mai/sessions/*.json` 중 24 시간 안에 갱신된 세션을 보여 준다. 세션 이름은 Claude 창은 `/rename` 이 정본이고, Codex 창은 세션 기록 파일의 name 을 super2 가 고친다.
- 무인 사슬 실행기는 팀장 지시로 꺼져 있다. 다시 켜는 것은 팀장 승인.
- GPU1 은 화면용 GPU 다. 촬영 GPU (10/26 하나로 정리, rulecheck V07): 화면용 GPU1 (cuda:1) 에서 찍되, GPU1 에서 학습이 돌고 있으면 cuda:0 (10/23 cuda:1 촬영이 학습을 480 초/회로). GPU1 에 학습을 띄우려면 **기동 전 여유 3 GB 이상**을 맞춘다. 모자라면 막지 말고 super2 가 비운다 (7 절 R5, 팀장 10/25 16시). 10/25 창 1 의 EX-31 (3072 env) 은 GPU1 15.2 / 16.3 GB 에서 메모리가 넘쳐 갱신 1 회가 34 초 → 226 초로 느려졌다 (Windows 의 GPU 메모리 페이징 추정, 10/23 480 초/회와 같은 모양).
- Claude · Codex 한도 숫자는 계기판 표시가 「실제 사용량」 과 「지금 속도면」 예측 둘이다. 보고에는 어느 것인지 밝힌다 (10/25 lead 가 예측값을 공식 경고처럼 말한 오류).

## 3. 실험 규칙 추가 (10/25)

정본은 EXPERIMENT-RULES. 여기 적힌 것은 거기 3.1 절과 같은 날 더한 것이다.

- **모든 링크 접촉 기록**: 진단 로그에는 발 · 종아리 · 허벅지 · 몸통 접촉을 모두 남긴다. 보상 · 종료로는 쓰지 않는다 (팀장 10/25 「기록해 앞으로는」).
- **승급은 회차가 아니라 성과로**: 새 명령 · 지형 · DR 은 점검의 성과 조건으로 연다. 한 번에 축 하나, 쉬운 과제는 남긴다 (DESIGN §5).
- **판정 문턱은 결과 전에 고정**: 64 합산 48 / 54, Wilson 하한 병기.
- **멈춤은 저장 경계에서만**: STOP · 마감은 50 회 경계에서 저장 뒤 정상 종료 (EX-29 229 회 중단 재발 방지, 10/25 aa63bffd).
- **평가는 학습 커리큘럼을 끄고**: 모드 비교 평가는 지형 · 명령 커리큘럼을 끄고 지형 해시를 단언한다 (10/25 리뷰 막음).
- **상황판은 보고 통로이고 기록이 아니다** (10/25): 새 결과 · 결정은 같은 점검 안에서 결과 문서 → EXP-MAP · SCHEDULE-NOW · DECISION-SYNC · AGENDA · 카드 → 승인 원장 → exp_sync_check rc 0 → push → #555 → 그 다음 상황판 · 텔레그램. 반복 점검 문장에 이 순서를 넣는다. 밤샘 9 시간 동안 상황판만 갱신한 실수에서 (팀장 〔원문 비공개〕).
- **START 와의 차이는 출처 문서에**: 새 설정은 PROVENANCE 의 「START / 다른 출처 / 우리 설계」 칸에 적는다.

## 4. 영상 렌더 규칙 (v2 · 10/25 21시 팀장 확정 〔원문 비공개〕)

- **단일 정책 (1920×1080)**: 왼쪽 장면 1280×720 (IsaacLab 초록 · 파랑 속도 화살표와 회전 호, 바닥에 정답 지도 초록 점 · 복원 지도 파랑 격자 · 2 cm 넘는 복원 오차 빨간 막대 · 발 아래 스캔 노랑 · attention 상위 주황, 발 궤적 1.5 초, 오른쪽 위 영어 범례, 오른쪽 아래 구간 · 배속) · 오른쪽 640 위에서 본 지도 세 칸 (정답 · 복원 「정책에는 0」 · 정책 입력 + attention 흰 상자, 같은 색 범위) 과 「Mean | Reconstructed - GT |」 곡선 (y 축 0 · 2 · 최대 cm) · 아래 띠 구간 타임라인 · vx · wz 명령 대 실제 · 발 접촉 막대. 코드 `C:/Users/AI-WS01/s2_lab/video_25e/` (record_25e.py · overlay_25e.py · compose_25e.py).
- **비교 (1920×1080)**: 판별 장면 2×2 (800×450) · 오른쪽 판별 현재 wz · vx 와 최근 3 초 발 접촉 · 아래 판별 wz 겹친 곡선 (흰 점선 = 명령). compose_compare_25e.py.
- 촬영 GPU (10/26 하나로 정리, rulecheck V07): 화면용 GPU1 (cuda:1) 에서 찍되, GPU1 에서 학습이 돌고 있으면 cuda:0 (10/23 cuda:1 촬영이 학습을 480 초/회로). 구간 (전체 · 좌 · 우 · 전진) × 배속 ×0.25 · 0.5 · 1 · 2. 전 프레임 검사.
- **촬영 조명 후보 셋 (10/27 00:2x 팀장 〔원문 비공개〕)**: record_25e.py (runner 6959a303) `--lighting-profile` 로 고른다. (L2) three_point 세기 100 · 방위 45/165/285 · 높이 45 · 각 12 도 · 그림자 켬, (L3) 같은 설정 그림자 끔, (L4) dome 0.05 + three_point 100 (그림자 켬). B1500 rough 6.0 s 평균 밝기 112.9 · 112.8 · 113.5 (지금 inherit 76.1, v2_flat 183.0). **확정 (10/27 01:1x 팀장 〔원문 비공개〕)**: 촬영 조명 L4 + 바닥 정보 그래픽 채도 ×1.25 (runner 7dc7e9e1 옵션). ×1.50 은 옵션으로만 기록. 근거 그림 C:\Users\AI-WS01\s2_lab\video_25e\lighting_probe_26l\stills_26l\ (overlay_saturation_3panel.png · stairs/boxes/slope/sparse_beam_inherit_vs_L4.png). **기본은 L4 (10/27 00:2x 팀장 〔원문 비공개〕)**. 순서: 정보 그래픽 채도 지금 · +25% · +50% 정지 화면 → 팀장 확인 → 앞서 낸 영상 전부를 L4 + 고른 채도로 같은 이름 · 같은 경로에 다시 렌더 (덮기 전 옛 파일은 archive 로 옮기고 sha256 전후 목록). 다른 지형 정지 화면도 같이 본다. 비교 그림 C:\Users\AI-WS01\s2_lab\video_25e\lighting_probe_26k\lead_cmp4_0010.png
- **배속은 1x 만 (10/26 20:3x 팀장, 0.25 · 0.5 · 2 배는 보류, 다시 지시할 때까지)**: 0.5x 는 같은 프레임을 두 번 넣은 것이라 끊겨 보인다 (진짜 느린 화면은 촬영을 더 촘촘히 해야 한다).
- **만드는 것과 전하는 것 (10/26 팀장)**: 만들기는 CMP (비교 조건별) 와 단독 판 각각 seq · forward · spin_left · spin_right × 1x. 팀장에게 전하는 것은 **CMP seq 1x 와 단독 seq 1x 만** (예 `CMP-B1500-G0B-SB50-SB10-m1500_mapmasked_rough_seq_1x.mp4` · `EX34-SB10-m1500_mapmasked_rough_seq_1x.mp4`). 구간 영상은 폴더에만 둔다.
- **바탕 렌더 대기열 (10/26 팀장 〔원문 비공개〕)**: GPU 가 학습 · 평가에 안 쓰일 때만 촬영 · 합성을 낮은 우선순위로 하나씩. 학습 · 평가가 뜨면 다음 건부터 멈추고 상태 파일에 대기 · 진행 · 끝을 남긴다 (runner 대기열 스크립트).
- **화면 정렬 (10/26 21:0x 팀장 원문 기준)**: 지도 칸 안 글은 칸 가로 가운데 선 기준 가운데 정렬. 아래 그래프 · 발 접촉 띠는 시작점을 왼쪽으로 당기고 이름 열 (vx · wz · FL~RR) 을 오른쪽으로 붙여 간격을 작고 일정하게. 3D 화면 위 명령 · 실제 화살표는 화면 끝에 붙지 않게 조금 아래로, 입체로 보이게. 오차 그래프 눈금 (0 · 2 · 4) 은 좌우 여백이 같아 보이게, 「cm」 은 그래프 아래 오른쪽. 팀장 그림 지시는 원문을 그대로 작업자에게 넘기고, 고친 뒤 전 · 후 정지 화면을 항목별로 대조해 확인한다.

### 이전 판 (v1 · 10/25)

- **이름**: `<실험들>-<지형>-m<회차>-<구간>-<배속>.mp4` 예 `ex30-ex31-rough-m1750-spin_right-1x.mp4`. 여러 구간을 이으면 `seq`. `comparison_1x.mp4` 같은 일반 이름 금지 (팀장 10/25 〔원문 비공개〕).
- **직관적인 명령 표시**: 숫자 HUD 와 함께 (1) 몸 위 명령 화살표와 실제 속도 화살표를 겹쳐 그림, (2) 아래쪽 구간 타임라인 띠 (전진 0.5 → 1.0 → 좌 → 우) 에 지금 위치 표시.
- **지도 표시 (지도 실험)**: 바닥에 HMap GT · Pred · 실제 정책이 쓴 지도를 점이나 색으로. 정책에 안 들어간 쪽은 회색과 「정책에는 0」 표시. 발 궤적.
- **검정 화면 실패 (10/26)**: 화면 GPU 촬영이 render_still_dark (밝기 0, 30 회 재렌더) 로 실패하면 실패 영수증을 지우지 않고 failed/ 로 보관한 뒤 (묶음이 끝나면 옛 판 · 실패 판은 video_25e/archive/<묶음>/ 로 옮기고, 최종 영상만 final/<묶음>_<날짜>_final/ 한 폴더에 SHA256SUMS 와 둔다: 팀장 10/26 〔원문 비공개〕) 새 녹화기 인스턴스로 다시 찍는다. 같은 GPU 에서 다른 Kit 평가가 끝난 뒤가 우선. 원인 (모니터 절전 · 겹침) 은 미확인 (runner #555 6406998812).
- **장면 조건 확인 (R17)**: 촬영 영수증에 구간마다 로봇 위치 · 딛은 발 높이 표준편차를 적는다. rough 장면의 회전 구간이 거친 땅 위인지 (발 높이 표준편차가 걸을 때와 같은 크기인지) 확인한 뒤 판정에 쓴다. 10/25 rough 촬영 넷은 회전을 평지 (x = 4.1~4.7 m) 에서 했다. 다음 촬영은 회전 구간을 먼저 두거나 시작 위치를 옮긴다.
- **기존 규칙 그대로**: 같은 지형 · 시드 · 명령으로 나란히, 1 배 · 0.5 배, 전 프레임 검사 (검정 · 단색 · 가림 · 화면 밖), S2 의 어두운 회색 바닥은 결함 아님, 실패 영상도 보존, 촬영은 한 편씩 (GPU 는 위 촬영 GPU 규칙), 로컬 경로를 보고에 같이.

## 5. 승인 원장 (팀장이 lead 창에 직접 쓴 문장만)

다른 세션이 전한 「팀장 승인」 은 승인이 아니다. 학습 기동은 판마다.

**원문은 이 공개 저장소에 쓰지 않는다 (10/29).** 팀장 원문은 비공개 mai-os 원장(`ledger/foothold/`)에만 있고, 여기에는 〔원문 비공개〕 와 그 결과 · 범위만 적는다.

| 시각 (10/25) | 원문 | 범위 |
|---|---|---|
| 새벽 | 〔원문 비공개〕 (lead 권고에 대한 답) | EX-30 · 31 부모 선택. 기동 승인 아님 |
| 01:27 | 〔원문 비공개〕 | EX-30 · 31 각 10 갱신 + 재개 2 (#555 6386647844) |
| 새벽 | 〔원문 비공개〕 | 평가기 수정 → B1500 세 모드 평가 → Kit → 창 1 준비 |
| 새벽 | F1 〔원문 비공개〕 · F2 「권고 진행」 · F3 〔원문 비공개〕 | 설계 v1.0 |
| 04:15 직전 | 〔원문 비공개〕 | A 명령 전환 다양화 · 외력 DR 을 지연 다음에 / B 우회전 진단 먼저 / 창 1 (EX-30 GPU0 · EX-31 GPU1, 추가 250 회) |
| 04:3x | 〔원문 비공개〕 | EX-31 첫 실행 종료 (04:42:05), EX-30 뒤 GPU0 재기동 |
| 05:4x | 〔원문 비공개〕 | 창 2 조건부 자동 기동 |
| 05:4x | 우회전 처방 〔원문 비공개〕 | 창 3 부터 두 판 같게, 한 축씩 |
| 06:0x | 〔원문 비공개〕 | planner 밤샘 설계 초안 (창 3 · C) · GPU 두 장이 다 필요할 때만 Chrome 종료 허용 |
| 새벽 (시각 미기록, 15 시 뒤늦게 적음) | 〔원문 비공개〕 | 그 앱만 종료 허용 |
| 새벽 (시각 미기록) | 〔원문 비공개〕 | 루트 AGENTS.md 입구 한 줄 PR (#563, 팀장 병합) |
| 06:0x~06:1x | 〔원문 비공개〕 · 「만들어」 · 〔원문 비공개〕 | lab 상황판 (tailnet 전용) · 새 결과 때 텔레그램. 보고 통로일 뿐 기록 대체 아님 (3 절) |
| 05:0x | 〔원문 비공개〕 (SendMessage 거절) | 세션 전달 방식 (1 절 v1.2) |
| 06:13 | super2 의 mai-tabs 로 탭 재우기 | super2 실행 (완료) |
| 16:0x | 〔원문 비공개〕 | GPU1 메모리 부족 때 학습을 막지 않고 super2 가 비운다 (7 절 R5) |
| 17:0x | 〔원문 비공개〕 | orchestration 한 건 시험 · Codex 네 세션 사용 (ASTRA-25b · SOL-25b 17:2x) |
| 10/26 13:3x | 「L-a 권고 승인」 · L-d 〔원문 비공개〕 · 복원 지도 p 권고 「동의」 · 〔원문 비공개〕 | Linux 2 차 준비 (시스템 설정 먼저 · 다리 세션 프롬프트 · L-b 표 · 놓친 범위 · L-d 기계 목록) super2 · pipeline. 브랜치 합치기 sonnet-code. 끔 비율은 0.1 유지 (MAPRATIO (b) 의 끔 낮추기는 보류). 출발선 의견 planner · analyst 따로. 회전 오르내림 S-B 열로 확인 (rot_series) |
| 10/26 15:3x | 〔원문 비공개〕 · 듬성 지형 고정 칸이 다음 첫 일 「동의」 · 〔원문 비공개〕 · 회전 〔원문 비공개〕 | L-b fork 로 런북 확정 (super2). 개발 부모 S-B10 m1500 (잠정, 「우선 현 시점」). 회전을 출발선 기준에서 빼는 것은 팀장 질문으로 열려 있음. 이전 묶음 목록은 super2 (값은 다루지 않고 자리 · 복사 절차만) |
| 10/26 16:0x | 〔원문 비공개〕 · 회전 〔원문 비공개〕 · super2 확인 〔원문 비공개〕 | 출발선 S-B10 m1500 (sha256 4d987818c7e25b89) 확정 (「우선」). PR #28 병합 1c0d3505. 회전은 출발선 고르는 점수에서 빼고, 〔원문 비공개〕 은 관문 바닥 조건으로 둔다. 바꾸는 순서는 analyst 안 쪽으로 기움 (확정 문장 대기). 한 폴더 이전 패키지 super2 · pipeline |
| 10/26 16:4x | 〔원문 비공개〕 · mai-resume 〔원문 비공개〕 | 바꾸는 순서 확정: 강등 오판 차단 확인 → 회전 명령 과정 → 복원 지도 사용 → 듬성 지형 · 추가 DR, 한 판에 한 축. mai-resume 캐시 유지는 멈춘 세션에만, mai-tools#30 병합 · 재시작 super2. 규칙 검사 agent 는 lead · verifier 의견 뒤 팀장 결정 |
| 10/26 11:1x | 〔원문 비공개〕 · 오늘 밤 GPU 는 planner · analyst · lead 논의 뒤 팀장이 검증해 결정 | 순서: S-B 평가 · 영상 · 과거 자료로 출발선 분석 먼저 → planner · analyst · lead 논의 → 팀장 결정. JUDGE-SPEC 구현 진행. 지도 비율 커리큘럼 진행 (끔 하한 0.1 → 유지 확인되면 0.05, 근간은 복원 지도). Linux 이전 준비 super2 · pipeline (기존 정본 mai-os#34 · #54 · NOTE-camera-ddp-linux-1024) |
| 10/26 10:2x | 〔원문 비공개〕 · 일정 (팀장 가정): 10/28~29 커리큘럼 실행 · 11/2 하위 보행 · 11/5~9 외부 일정 · 11/9 전후 Go2 EDU 한 달 · 11월 중순 마무리 · 11/30 발표 준비 | 판정 · 커리큘럼 관문을 코드로 옮길 정본 JUDGE-SPEC (planner PLAN-26b) → sonnet-code 구현 → 답을 아는 시험 → reviewer, 다음 학습 전에. 지도 비율 커리큘럼 설계 (끔 하한 · 켬 비율 올림 · 복원 지도 섞기, 한 번에 한 축) |
| 10/26 17:5x | 〔원문 비공개〕 | 규칙 검사 세션 rulecheck (Codex gpt-6.1-sol high, worktree C:/mai/wt/foothold-lab/rulecheck · feature/rulecheck-jay, 창 term_5710062f) 기동. 첫 지시문 RULECHECK-BRIEF.md: lead 규칙 준수만 PASS/FAIL, 증거 없음은 FAIL. mai-watch #29 병합 확인 (08:11:37Z) |
| 10/26 20:3x | 결정 9 「이해함, 확인」 · 끔 분모 〔원문 비공개〕 · 영상 〔원문 비공개〕 · G02 〔원문 비공개〕 | 결정 9 확정 (끔은 연속 7 종 + 평지, 듬성 0). 끔 분모 확정 (허용 지형 안 10%). 영상 1x 만 · 전달은 CMP seq · 단독 seq · 바탕 렌더 대기열 (runner). main 받기 8185320e. 결정 8 은 팀장 물음에 답하고 대기 |
| 10/26 21:0x | 〔원문 비공개〕 | 결정 8 확정: 지형 판정 보정을 기존 START 명령 포함 모든 명령에 켬 (planner · sonnet-code). lead 답은 채팅에 길게. 화면 정렬은 팀장 원문 그대로 runner 에 재지시 (runner-26e) |
| 10/26 21:2x | 〔원문 비공개〕 · 시드 반복 〔원문 비공개〕 | 화살표 그대로 (다음 촬영 때 한 장 먼저 컨펌). 듬성 칸 성공 · 실패 영상 (runner). 시드 반복 평가 멈춤 (B1500 s44 · S-B50 · G0-B s43 · s44 중단, 21:2x). 학습 · 판정 코드는 reviewer 뒤 verifier 두 겹 검토 |
| 10/26 21:5x | 〔원문 비공개〕 → 〔원문 비공개〕 | 16:0x 원문의 〔원문 비공개〕 숫자는 lead 가 쓴 말을 팀장이 옮긴 것이고 팀장이 짚은 것은 생존 관문 원칙. 숫자 14 는 lead 권고 (부모 S-B10 kept 최소 14) 로 팀장 21:5x 확인. JUDGE-SPEC v0.9 · EXP-EX35 v0.2 (planner 225345ac · 8e0abd53) 반영 |
| 10/26 23:1x | 〔원문 비공개〕를 승인한다. 다른 세션에서도 차질 없이 진행할 수 있도록 승인.」 · 밤사이 자동 연장 〔원문 비공개〕 · 듬성 지형 진단 판 GPU1 앞당김 〔원문 비공개〕 · 조명 〔원문 비공개〕 | EX-35 기동 승인 (조건: reviewer · verifier 두 겹 막음 0 + 10 update 짧은 확인 실행 통과, GPU0). m2001 뒤 연장은 판정표 (보행 유지 · 이전 능력 유지 · 발전, 숫자 · 그래프 · 영상 · 재현) 를 결과 전에 고정하고 통과할 때만 (planner 설계 · analyst 숫자 검증). 듬성 진단 판은 EX-35 평가 · 영상 확인 뒤. 커리큘럼은 성과 관문으로 단계 이동, 전체 20,000 회 목표. 레이아웃 549edfb4 확정 → 1x 재합성. |
| 10/27 11:2x | 〔원문 비공개〕 | 앞으로 지형 레벨 평가 · 부모 비교는 L0~2 · L3 · L6 · L9 (3 레벨 간격) 로 잰다. 지금까지 L3 은 미측. 이미 고정된 EX-35 카드(v0.9 A2 = L0~2 · L6 · L9)의 판정은 결과 전 고정이라 바꾸지 않고, 다음 카드부터 적용. 복원 지도 모드(eval_pred) 영상 · 복원 오차 축(|복원 − 정답|, 지형 · 레벨별) · 복원 손실 학습 곡선 셋을 만든다(아직 미착수 · 담당 runner · sonnet-code · scripter). 「건넘」 판정에 지지대 실제 밟음 추가 · 실험 순서 규칙 초안은 팀장 답 대기(지시 아님) |
| 10/27 13:1x | 〔원문 비공개〕 | 13:11:3x PID 147032 종료(종료 전 명령줄 대조 · 종료 후 잔존 확인을 하지 않음 · rulecheck O06 · 13:18 에 구 PID 부재 확인) · 새 PID 94184 · 첫 갱신 13:11:32 정상 |
| 10/27 11:3x | 〔원문 비공개〕 | 11:34:21 PID 133936 종료 · 같은 명령으로 숨김 재기동 PID 77388 · 첫 갱신 11:34:32. 11:45:43 lead 가 띄운 77388 을 같은 까닭(고친 모듈 미반영)으로 다시 띄움 PID 147032. 승인은 133936 건 하나다. 77388 종료는 승인 없이 한 규칙 위반(AGENTS 77 행 〔원문 비공개〕, 자기가 띄운 프로세스 예외 없음 · rulecheck G05 11:54). 팀장 소급 승인 대기. 앞으로 lead 가 띄운 프로세스도 끄기 전에 묻는다 |
| 10/27 10:0x | 「A11이 뭔데?」 · 〔원문 비공개〕 | 채팅 보고에 판정 항목 이름 (A11 등) 을 쓰면 바로 뜻을 풀어 쓴다 (A11 = 영상 1 배속 판독: 비교 · 단독 영상에서 미리 정한 다섯 항목 확인). 상황판 갱신 = 머리 시각이 아니라 「새 결과」 칸 맨 위가 최신 RESULT 문서 판의 핵심 (판정 행 · 정본 · 새 사실) 을 담고 「팀장이 정할 것」 이 AGENDA-LEAD 최신 절과 같을 때만 갱신으로 센다 (10/27 06:32~09:52 머리 · GPU 줄만 20 분 갱신, 결과 칸은 10/26 에서 멈춤). 20 분 갱신기는 결과 칸 · 정할 것 칸도 원자료에서 다시 만든다 (scripter). rulecheck 상황판 검사에 결과 칸 · 정할 것 칸 · 경로 실존을 넣는다 |
| 10/27 03:4x | 〔원문 비공개〕 | 다음 판 판정: 단계 넘김은 고정 최소 체류가 아니라 연속 저장본 평균 · 추세의 성과로 (최소 체류는 흔들림 오인 방지용 짧은 관찰 창만, 02:1x 의 「500 유지 권고」 철회). 회전 유지 기준선 = 부모 여러 저장본 평균 (Mean) · 흔들림 범위. 0.20 · 0.25 는 같은 저장본 재측정 폭 0.115 근거의 추정이라 저장본 간 흔들림 실측으로 다시 정함 (planner → analyst → verifier → sonnet-code). 촬영 GPU 규칙 확대 (lead 무단) 철회, 4 절 원문 유지. 전달 영상은 확정 레이아웃 합성본만 (촬영 원본 전달 금지) |
| 10/27 02:1x | 〔원문 비공개〕 | mai-os PR #61 병합 (02:10 lead). mai-resume 남은 위험 (대기 메시지 + 실제 입력 구별 못 함) 팀장 수용. 기동기가 평가 사슬 · 표식 감시기를 함께 띄우게 (sonnet-code X27l). 단계 최소 체류 500 은 planner · analyst · verifier 독립 의견 뒤 팀장 결정 (그때까지 500 유지, 결과 보고 바꾸지 않음). GPU 작업 관리판 P0 학습 · P1 판정 평가 · P2 진단 · P3 시드 잡음 · P4 렌더 (scripter SOL-27a). lead 결정 (planner 막음 (9)): 지형 종류별 필수 칸은 m2250 창부터 적용, m2000 창은 결과 전 고정한 v0.9 그대로 |
| 10/27 01:1x | 〔원문 비공개〕 | 조명 L4 + 채도 ×1.25 확정 (×1.50 옵션 기록) → 기존 영상 재렌더. 1 절 지시 · 보고 표 v2. 평가 축 논의 planner + analyst. mai-tools PR #33 병합 (01:15) |
| 10/27 00:4x | 〔원문 비공개〕 | 1 절: 한도는 limits_now.py 로만 · 표시줄 예측은 예측으로. 일하는 세션 의뢰는 dispatch_queue.py 대기열 · 덧붙임은 orchestration send |
| 10/27 00:2x | 〔원문 비공개〕 | 조명 후보 L2 · L3 · L4 를 4 절에 기록, 다른 지형 정지 화면 뒤 선택. 세션 의뢰 · 보고를 orchestration 으로 (1 절 첫 문단) |
| 10/26 23:2x | (23:1x 승인의 기동) | EX-35 GPU0 23:24:32 기동 (impl-ex35-07fc 고정 사본 07fc5e73, reviewer REVIEW-07fc5e73 막음 0 · verifier VERIFY-verifier-EX35-07fc5e73 막음 0 · smoke2 23:22 rc 0 TRAIN_START_STATUS done). 부모 sha 4d987818 일치. 첫 update 23:25:38: EPISODE_SCATTER ok (0~19.98 s) · CLOCK_SCATTER ok (0~4.0 s) · 지도 끔 실현 0.0889 · spin 0.20 · 27.6 초/회 (m2001 까지 약 3.9 시간). 기록 logs_gate/ex35_main_20261026_232432 |
| 00:2x | 〔원문 비공개〕 | 8.1 예외 (두 GPU 가 모두 학습이면 학습 뒤 같은 GPU 에서 몰아서 평가, 100 회 단위 먼저) · 10/26 밤 시간표 (NIGHT-PLAN-1026) 승인. 출발선 후보 = B1500 · S-B50 · S-B10, G0-B 는 「지도 없이 걷기」 기준선 (출발선 아님). B1100 · EX-23 측정 접음 |
| 23:5x | 〔원문 비공개〕 | EX-34 S-B10 (= planner C0, p_off 0.1) 승인. GPU0 사슬 night_1026_gpu0 (00:04 시작): G0-B 학습 끝 → G0-B 평가 끝 → m950 다시 → S-B10 기동. 카드 EX-32 · 33 · 34 (판정 결과 전 고정) |
| 23:4x | (22:5x 승인의 기동) | EX-33 S-B p_off 0.5 GPU1 23:44:49 기동 (impl-sb 6309f67e, reviewer fbad5342 막음 0 · 6309f67e 재검토 막음 0). 첫 update EX33_MAP_SWITCH realized 0.5049, 24.51 초/회. p 0.5 는 lead 권고값 (팀장 〔원문 비공개〕), C0 p 0.1 판은 팀장 승인 대기 |
| 22:5x | 〔원문 비공개〕 | EX-33 S-B 학습 승인 (B 설정 + env 마다 에피소드 단위 지도 끔, 처음부터 1501 회). sonnet-code SONNET-X25f 준비 23:01. 끄는 비율 p_off 는 팀장 확인 (lead 권고 0.5), reviewer 막음 0 · 짧은 Kit 뒤 기동 |
| 22:3x | 〔원문 비공개〕 | R13~R17 추가 (v1.4) · planner v0.3 의뢰 (지도 켜고 끄기를 처음부터 넣는 안을 본류 후보로 정식 비교 포함) · 결정 넷 (기준선 · wz 0.5 · 예산 · 출발선) 은 팀장 질문 〔원문 비공개〕 단계, 아직 승인 아님 |
| 21:3x | 〔원문 비공개〕 | 영상 규칙 v2 (4 절) · 회전 진단 여섯 경우 (R12) · 8 절 표준 절차 |
| 21:0x | 〔원문 비공개〕 (점검 50 회 · 판정 250 회 창 다섯 저장본 · 한 단계 최소 500 회) · 〔원문 비공개〕 | 다음 설계 결정 6 개 lead 권고대로 (제자리 회전 20 % 유지 · B1500 + 흩기 (G0-B 끝나면 같은 잣대) · 기준선 min(좌, 우) 중앙값 0.22 · 걸으며 돌기 + 지형 강등 오판 수정 선행 · 정답 지도로 명령 과정 먼저 · 예산 B1500→3000). verifier VER-DN25 검토 뒤 확정 |
| 20:3x | 「G0-B 승인」 (EX-25 설정 + 마찰 0.2~1.2, 처음부터 1501 회, B 와 같은 START 계약) | G0-B 학습 GPU0 20:37:29 기동 (impl-g0b c151db40 · 727d4773, reviewer 막음 0) |
| 20:0x | 〔원문 비공개〕 설계 논의 · 〔원문 비공개〕 | 다음 설계 v0.1: planner 초안 · analyst 반박 · lead 조율. 다른 시드는 전체 과정 끝 한 번 |
| 18:2x | 〔원문 비공개〕 | B1500 에서 50 회 두 판 (A 지금 방식 · B 명령 시계 흩기), EX-31 조건. sonnet-code SONNET-X25b 준비, 저장본 평가 sweep 끝나면 바로 기동 |
| 17:3x | Codex 세션 rename (팀장 직접): luna → runner · astra2 → verifier · sol → scripter · lead_tmp/astra → analyst | 1 절 표. super2 가 mai-watch 기록 이름 반영 (17:38) |
| 16:4x (super2 창) | 〔원문 비공개〕 (super2 의 〔원문 비공개〕 에 대한 답) | 부재 중 앱 · Chrome 종료 허용, 자리에 있으면 묻기. lead 가 super2 화면에서 원문 확인 |

## 6. 반복 지시 (팀장이 두 번 이상 말한 것)

| 지시 | 정본 자리 |
|---|---|
| em dash 금지 · 〔원문 비공개〕 꼬리말 금지 · 한국어 · 고1 이 읽는 말 | mai-os AGENTS · LEAD-STYLE §8 |
| 채팅으로 흘려보내지 말고 문서화 · 링크만 주지 말고 내용도 채팅에 | LEAD-STYLE §7 · §8 |
| 시드는 「시드」, 기술 용어는 원어 · 「그림」 (도해 아님) | LEAD-STYLE §8 |
| 근거는 실제 경로 · 행 번호, 숫자는 등급 (논문 · 실측 · 추정) | LEAD-STYLE §3 |
| 미확인 대신 웹에서 찾아 답 | LEAD-STYLE §3 |
| 영상은 실패 · 성공 모두 · 바로 공유 · 직관적으로 | 이 문서 4 절 |
| GPU 를 놀리지 않는다 · 돌았는지 세 줄로 | LEAD-STYLE §2 |
| 결정 · 설계는 팀장과 같이, 결정은 묻고 먼저 | LEAD-STYLE §8 · 이 문서 5 절 |
| START 는 근본 루트, 그대로 베끼지 않고 우리 설계로 넓힌다 | PROVENANCE · DESIGN §0 |

## 7. 반복 실수와 막는 장치 → [FAILURE-LOG.md](FAILURE-LOG.md)

10/29 부터 정본은 같은 폴더의 `FAILURE-LOG.md` 한 파일이다(R1~R23 과 lead 메모리 교훈을 옮김). 새 실수는 거기에 더한다.

## 8. 표준 절차 (v1 · 10/25 22시 팀장 〔원문 비공개〕)

이 절이 실행 순서의 정본이다. 각 줄은 「누가 · 언제 · 무엇을 · 어디에」. 어기면 7 절 반복 실수 표에 올린다.

### 8.1 평가 · 측정 (저장본마다 같은 묶음)
| 측정 | 조건 | 언제 | 어디 |
|---|---|---|---|
| 64 env 고정 칸 평가 | 레벨 0~2 칸 해시 c3884d68, eval_gt · eval_pred, 6 초, 전진 0.5 · 1.0 · 좌 · 우 | 50 회마다 저장본 (학습 중이면 다른 GPU) | `impl-t5/logs/onset_sweep/<판>_m<회차>/map_modes.json` · summarize.py |
| 16 env 회전 진단 | 칸 해시 7f49a1e9, 여섯 경우 (좌 · 우 독립, 좌 → 우, 우 → 좌, 전진 → 좌, 전진 → 우) + 단계에 들어온 명령 경우 (후진 · 정지 · 걸으며 돌기) | 같은 저장본, 창 경계는 반드시 | `<판>/probe_*/arrays_*.npz` |
| 영상 | 영상 규칙 v2 (4 절), 단일 + 비교, 구간 × 4 배속 | 창 경계 · 판단이 걸린 저장본 | `C:/Users/AI-WS01/s2_lab/video_25e/final/` |
| 학습 곡선 | 여러 지표 (보상 항목 · 길이 · 지형 레벨 · KL · std · value loss), 방향별 회전 기록이 생기면 함께 | 창 경계 | 결과 문서 6 절 형식 |
- **예외 (팀장 10/26 00:2x 승인)**: 두 GPU 가 모두 학습 중이면 학습 중 평가를 하지 않고 (같은 GPU 에 올리면 페이징, 10/25 23시 실측), 학습이 끝난 뒤 같은 GPU 에서 100 회 단위 저장본부터 몰아서 잰다 (post_train_eval.sh).
- 같은 저장본 재평가 (H4) 로 평가 잡음은 작다 (B1500 좌 0.873 → 0.870). 저장본 사이 차이는 정책 변화로 읽는다. 다른 시드는 전체 과정 끝에 한 번 (EXPERIMENT-RULES).

### 8.2 분석 · 판정
- 숫자는 스크립트가 원자료에서 만든 표로만 보고하고, 표는 빠짐없이 붙인다 (손으로 고른 숫자 금지, R1 · R12).
- 회전 판정은 최신 저장본의 경우별 값 + 직전 저장본 + 다섯 저장본의 같은 저장본 min(좌, 우) 를 함께 본다. 방향별 따로 낸 중앙값만으로 판정하지 않는다 (analyst 반례). 0.22 (B 11 저장본 min 중앙값) 는 「과거 약한 쪽 참조선」 이지 유지선이 아니다 (verifier VER-DN25 A3).
- 보행 주장 (발을 든다 · 비튼다 · 잘 돈다) 은 16 env 여섯 경우 + 영상이 모두 맞을 때만 (R12). 수치가 올라도 위상 · 영상 확인 전에는 「개선」 이라 쓰지 않는다 (R8).
- 판정 문턱은 결과 전에 문서에 고정하고 결과를 보고 넓히지 않는다.
- 회전 판정 통계는 16 env **평균**. 같은 저장본 재측정 폭: 평균 최대 0.11 · 중앙값 0.23 · env 하나 0.60 (결과 v2.3 0c). 문턱은 이 폭보다 크게, 차이 0.2 안팎이면 같은 저장본을 두 번 잰다.

### 8.3 운영 (띄우기 · 지키기)
- GPU 일은 프로젝트 실행기로만 (run_kit.sh · run_*.sh: conda PATH · OMNI_KIT_ACCEPT_EULA · CUDA_DEVICE_ORDER=PCI_BUS_ID · 숨김 창 · 로그 파일). PowerShell Start-Process 에는 스크립트 경로를 직접 넘기고 `-c '...'` 를 쓰지 않는다 (10/25 G0-B 첫 기동 실패).
- 「돈다」 는 띄움 (PID · 시각) → 2 분 안 첫 증거 (GPU 메모리 · 첫 update · 첫 결과 파일) → 끝 (rc + DONE 줄 + 산출물) 세 줄 뒤에만 (R10). Isaac rc 0 은 결과 파일로 다시 본다.
- 학습 기동은 판마다 팀장 승인 (승인 원장 5 절). 평가 · 진단 · 촬영은 승인 없이 빈 GPU 에서 바로 한다. GPU 가 비면 다음 측정을 바로 건다.
- 촬영 GPU (10/26 하나로 정리, rulecheck V07): 화면용 GPU1 (cuda:1) 에서 찍되, GPU1 에서 학습이 돌고 있으면 cuda:0 (10/23 cuda:1 촬영이 학습을 480 초/회로). 보호 장치가 검정 프레임으로 버리면 바로 다시 찍는다.
- 세션 전달은 1 절 순서 (read → wait → send → turn_started 확인, 작업 세션 창 입력줄의 글은 회색 제안 문장이라 보낸다 · R13), read · send 를 한 명령으로 잇지 않는다. 회신은 상대 창 끝까지 읽어 확인한다.

### 8.4 기록 (새 결과 · 결정 · 정정 때 같은 점검 안에서)
결과 문서 (RESULT-B1500-1024 9 절 형식, R8) → EXP-MAP · SCHEDULE-NOW · DECISION-SYNC · AGENDA-LEAD · 카드 → 승인 원장 (팀장 원문) · 그 결정이 바꾸는 규칙 문장 → 팀장이 묻고 배운 것은 QA-LEAD → exp_sync_check rc 0 → commit · push → #555 → 세션 상태 → lab 상황판 → 텔레그램 (문서 링크 + 로컬 그림 · 영상 경로 전부). 정정은 퍼진 곳 전부 (R2). 설계 문서는 정본 하나 (DESIGN-EX30-31) 에 판을 올리고 초안은 검토 이력으로만.

### 8.5 영상
4 절 v2 가 정본. 판단이 걸린 주장 (회전 · 지도) 에는 해당 구간 영상 경로와 확인한 프레임을 같이 낸다.

## 8b. 실험 카드 정본 자리 (Linux 런북 L-12 가 가리킴)

실험 카드는 `inbox/jay/20261021-experiments/EXP-*.md` (EX-30 · 31 · 32 · 33 · 34 등) 한 곳, 목록은 같은 폴더 `EXP-MAP.md` 의 「exp-sync:experiments」 표. 결과 문서는 날짜 폴더 `inbox/jay/2026MMDD-experiments/RESULT-*.md`, 밤 계획 · 실제 기록은 `NIGHT-PLAN-*.md`. 세션이 이어 붙은 뒤 처음 읽을 정본 순서: 이 RULES-HUB → EXP-MAP → SCHEDULE-NOW → 최신 NIGHT-PLAN → 카드.

## 8c. 지금 돌고 있는 실험의 실행 지도 (10/27 01:2x 팀장 〔원문 비공개〕)

판이 바뀔 때마다 lead 가 이 절을 고친다 (기동 · 사슬 · 판정 · 정본 채택 때). Linux 로 옮길 때는 이 트리 그대로 자리를 만들고, 각 자리의 sha256 · 커밋을 다시 대조한다. 경로는 Windows 기준 (`C:/mai/wt/foothold-lab/` = WT).

**EX-35 (S-B10 m1500 → m2001, 회전 명령 과정 첫 판 · 10/26 23:24 기동)**

```text
WT/impl-ex35-07fc/                       학습 실행 고정 사본 (07fc5e73, foothold_s2 깨끗해야 기동)
  foothold_s2/run_ex35.sh                기동 스크립트 (kind main|smoke2, 인자 영수증 · argv CR 가드)
  logs_gate/ex35_smoke2_20261026_232226/ 짧은 확인 실행 2 회 (rc 0)
  logs_gate/ex35_main_20261026_232432/   본 학습 영수증: launch_receipt.json · launch_args.txt · launch_argv_repr.txt · git_head.txt · run.log · rc.txt
WT/impl-sb/logs/rsl_rl/foothold_s2_sb/
  2026-10-26_01-17-47_sb-main/model_1500.pt            부모 S-B10 m1500 (sha256 4d987818c7e25b89)
  2026-10-26_01-17-47_sb-main_resume_20261026_232446_120476/
    model_1550.pt … model_2000.pt        EX-35 저장본 (50 회마다)
    params/env.yaml · params/agent.yaml  실제 학습 조건 (학습 조건 표의 원자료)
WT/eval-x27g/                            평가 하네스 고정 사본 (07fc5e73, 깨끗)
WT/impl-integ/                           작업 브랜치 (sonnet-code). 판정 코드 ex35_gate.judge_ex35 · 평가 사슬 foothold_s2/eval/ex35_eval_chain.sh (adad7d5e).
                                         reviewer 고침 2: 사슬 · 판정 코드도 고정 사본에서 읽게 바꾸는 중 (01:2x)
WT/impl-turncases/logs/
  sb10_eval/m1500/                       부모 기준선: turn16_eval_gt · turn16_eval_pred · turn16_probe_prop_only · map64 · turn16_walk_eval_gt · turn16_walk_probe_prop_only · walk_turn_summary.json
  ex35_eval/                             EX-35 저장본 평가 사슬 (cuda:1, 01:12 시작)
    chain.log · receipt.txt              사슬 기록 (ITEM m<N> start/done)
    m<N>/                                저장본마다: checkpoint_sha256.txt · git_head.txt · git_status.txt · rc.txt · turn16_* · map64_* · 판정 json · timing.txt
WT/fable-25a/                            planner 작업 사본: 카드 EXP-EX35 v0.9 · JUDGE-SPEC v0.13 · CURRICULUM-GATES v0.3 · RULES-HUB 10 절 초안 (30168082, verifier 검증 전 · 아직 lead 브랜치에 안 가져옴)
  _out/reports/REPORT-planner-*.md
WT/astra-25b/inbox/jay/20261026-experiments/  analyst · verifier 검토: VERIFY-analyst-EX35-GATES.md · VERIFY-analyst-RULES-AXES-LINEAGE.md · VERIFY-verifier-*.md
C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/_out/review/  reviewer 검토 REVIEW-<커밋>.md
```

**GPU 작업 관리판 (SOL-27a · lead 확인 전)**: `WT/lead_tmp-20261023/_out/tools/gpu_jobs/`의 `jobs.json`은 P0 승인 학습, P1 판정 평가, P2 진단, P3 시드 반복, P4 영상 렌더를 등록한다. `gpu_jobs.py status`는 두 GPU의 실제 PID · EX-35 `PRIORITY_BUSY` · `chain2.log` · runner 상태를 한 화면에 읽는다. `gate <id>`는 다음 한 건의 진입만 판정하고 프로세스를 띄우거나 멈추지 않는다. P1 감시기 `WT/impl-integ/foothold_s2/eval/ex35_priority_marker.py`(당시 PID 34976)는 평가 단계에 `PRIORITY_BUSY`를 쓰고, runner `render_queue_26d.py` e202543a는 매 렌더 건 앞에서 표식과 사슬 대기를 재확인한다. 낮은 작업은 현재 한 건을 끝낸 뒤 높은 작업에 비킨다. P3 시드 43 · 44는 현재 `turn_probe.py`에 시드 변경 CLI가 없어 실행 불가로 등록했고, runner는 아직 이 관리판의 P3 등록을 직접 읽지 않는다. 따라서 이 명부만으로 P3 우선권이나 새 작업 승인이 생기지 않는다. CPU 시험 경로는 같은 폴더의 `test_gpu_jobs.py`다.

**판정 흐름**: 저장본 생김 → 사슬이 최신부터 평가 (한 번에 Isaac 하나, cuda:1) → `judge_ex35` 가 저장본 상태 (MAINTAIN_FAIL 등) → 창 경계 m1750 · m2000 에서 마지막 두 저장본으로 consume → 판정표 (카드 v0.9 §4b, 필수 칸 하나라도 비면 HOLD_NO_DATA = 연장 불가) → 1x 영상 lead 판독 (A11) → 계속 · 다음 단계 · 멈춤. 멈춤 · 연장 기동은 lead 가 한다.

**영상 · 조명**

```text
C:/Users/AI-WS01/s2_lab/video_25e/
  final/runner-26k_1026_final/           1x 영상 32 편 (inherit 조명) → L4 + 채도 ×1.25 로 같은 이름 재렌더 예정, 옛 파일은 archive
  final/runner-26a_1026_final/runner-26i-previews/target_vs_result_aligned_26j.png   확정 레이아웃
  lighting_probe_26h/ · lighting_probe_26k/ · lighting_probe_26l/stills_26l/      조명 · 채도 시험 (L4 · ×1.25 확정 근거)
WT/runner-26a/inbox/jay/20261023-experiments/runner-26a/   촬영 · 합성 코드 (record_25e.py 7dc7e9e1, render_queue_26d.py, seq_video.py sparse18)
```

**운영 도구 (lead_tmp 사본 `WT/lead_tmp-20261023/_out/`)**

```text
tools/limits_now.py        한도 사실만 (정본 ~/.mai/limits.json)
tools/dispatch_queue.py    일하는 세션 의뢰 대기열 (orca task-create → 쉬면 worker-start)
msgs/orch_wait.py          받은편지함 배경 대기 (status 포함 · keepalive 거름)
msgs/*.txt                 보낸 의뢰 원문 (같은 의뢰를 다시 보낼 때 이것을 쓴다)
```
orchestration Run: `run_abb2e12cee32` (coordinator = lead 창 term_2580fc05). mai-resume: `C:/mai/mai-tools/tools/mai-resume` (PR #33 병합 01:15, super2 재시작 뒤 적용).

## 9. 이름 붙은 체크포인트 정본 (10/26 12시, Linux 이전 런북 L-3-2 가 가리킴)

Windows 자리 기준 (`C:/mai/wt/foothold-lab/` 아래, EX-23 만 `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/`). sha256 은 lead 가 10/26 12시에 다시 잼 (앞 16 자). Linux 로 옮긴 뒤 같은 값인지 먼저 대조한다.

| 이름 | 자리 | sha256 앞 16 | 역할 |
|---|---|---|---|
| B1500 (EX-28) | `lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main/model_1500.pt` | cb65ba5641ac7265 | 출발선 후보 · 비교 기준 (지도 늘 켬) |
| S-B50 (EX-33) m1500 | `impl-sb/logs/rsl_rl/foothold_s2_sb/2026-10-25_23-45-04_sb-main/model_1500.pt` | e6d8ba631f24e816 | 출발선 후보 (지도 끔 0.5) |
| S-B10 (EX-34) m1500 | `impl-sb/logs/rsl_rl/foothold_s2_sb/2026-10-26_01-17-47_sb-main/model_1500.pt` | 4d987818c7e25b89 | 출발선 후보 (지도 끔 0.1) |
| G0-B (EX-32) m1500 | `impl-g0b/logs/rsl_rl/foothold_s2_g0b/2026-10-25_20-37-41_g0b-main/model_1500.pt` | de3a29fb32e49837 | 지도 없이 걷기 기준선 |
| 흩기 b50 m1510 | `impl-stagger/logs/rsl_rl/foothold_s2_ex31r_stagger/2026-10-25_19-15-52_ex31r-b50/model_1510.pt` | 2a391afa83c88e81 | 회전 진단 (양방향 발 들기) |
| 흩기 b50 m1550 | 같은 폴더 `model_1550.pt` | 6d7cfa0812ae0a5b | 회전 진단 |
| EX-23 m1500 | `logs/rsl_rl/foothold_s2_x23/2026-10-22_21-52-26_ex23-g1/model_1500.pt` (sonnet-code 작업공간) | 4775fd35a4af9a61 | 지난 본류 기록 |

같은 폴더의 다른 저장본 (50 회 단위) 과 tfevents · map_switch.jsonl 도 같이 옮긴다 (평가 · 학습 곡선 원자료). 평가 원자료: `impl-turncases/logs/{g0b_eval,sb50_eval,sb10_eval,b1500_baseline,six_cases,fwd_then_left}`, `impl-t5/logs/` (onset_sweep · w3p1 · sol25b), 영상 `C:/Users/AI-WS01/s2_lab/video_25e/final/`.

| 판 | 날짜 | 내용 |
|---|---|---|
| v1.5 | 2026-10-26 | 9 절 이름 붙은 체크포인트 정본 (sha256), 영상 검정 화면 재촬영 규칙 |
| v1.4 | 2026-10-25 | R13~R17 (회색 제안 문장 · 잴 수 있는 것을 미확인으로 · 남의 지적 미확인 전달 · 결정 기록 누락 · 촬영 장면 조건), 판정은 16 env 평균, 영상 장면 조건 |
| v1.3 | 2026-10-25 | 8 절 표준 절차 (평가 · 측정 · 분석 · 운영 · 기록 · 영상), 영상 규칙 v2, R12 |
| v1.2 | 2026-10-25 | 1 절 세션 전달을 팀장 결정(orca-cli)으로 고침 · 승인 원장 06:0x 뒤 줄 보충 · 7 절 반복 실수와 막는 장치 R1~R7 |
| v1.1 | 2026-10-25 | super2 검토: 한도 지킴이 정정 (mai-resume) · orca 직접 넣기 금지 · Codex 이름 · GPU1 학습 메모리 조건 |
| v1.0 | 2026-10-25 | 첫 판. 세션 역할 · 운영 · 10/25 실험 규칙 · 영상 렌더 v1 · 승인 원장 · 반복 지시 |
