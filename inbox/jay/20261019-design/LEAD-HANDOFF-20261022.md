> 분류: 운영 · 인계
> 작성: 오흥재 (lead 세션 정리) · 2026-10-22
> 근거: #555 6336550565 · 6336845347 · 6338232352 · RESULT-EX11-12 · RESULT-EX14-16 · ASTRA-X14 · 팀장 채팅 10/22
> 요지: Claude 주간 한도(96 %)로 lead(Claude)가 멈출 수 있어 보행 문제 탐색을 lead_tmp(Codex)가 총괄하도록 넘긴다. 인사이트 · 진행 중 실험 · 판정 방법 · 세션 역할을 한 장에.
> 상태: 인계 · EX-21/22 준비 중(sonnet 코드) · lead 가 살아 있는 동안은 lead 가 계속, 멈추면 lead_tmp 가 이어 받음

# lead 인계 · 10/22 저녁

## 1. 지금 풀고 있는 문제 하나

**Go2 가 정상 보행(대각 trot, 몸을 세운 자세)을 하지 못한다.** 우리 S1/S2 환경에서 학습한 정책은 전부 기거나(EX-01/11/14), 네 발로 동시에 뛰거나(EX-15), 웅크려 서 있다(EX-16~20). 같은 Go2 를 NVIDIA 환경 · 보상으로 학습한 v1 · v2 는 50 update 만에 trot 로 걷는다.

## 2. 지금까지 확정된 인사이트 (데이터 근거 포함)

| 인사이트 | 근거 |
|---|---|
| est(추정 입력)는 원인이 아니다 | EX-11(est 0) ≈ EX-12(est 학습) · RESULT-EX11-12 |
| 보상 항 덧붙이기(발 공중 시간 · legged_gym A1 · MGDP)로는 trot 가 안 나온다 | EX-14/15 1500 회 위상도 · ASTRA-X14 가 원본 식으로 airtime · motion_trot 이 pronk 를 구별 못함을 CPU 로 확인 |
| 보상을 v2 와 똑같이 해도 우리 환경에서는 못 걷는다 → 원인은 환경 쪽 | EX-16 |
| **초기 뒤집힘 붕괴의 원인은 도메인 무작위화(DR)가 유력** | EX-16 50~100 회 뒤집힘 종료 94~99 % → DR 만 v2 와 같게(EX-19) 하면 18 % → 10 %. 우리 DR 은 마찰 0.2~1.2 · COM ±5 cm · PD/모터 0.9~1.1 를 학습 처음부터 최대로 넣음 |
| 뒤집힘이 없어져도 웅크린 채 서 있다 → 요인이 겹쳐 있다 | EX-19/20 300 회: 몸 높이 0.16~0.18 m, 제자리 |
| 몸을 낮추는 것은 「불안하니 무게중심을 낮춘」 생존 전략 | 팀장 해석, 위 두 줄과 일치 |
| 자세 차이의 실체: v2 는 hip 을 안으로 약 0.3 rad 모으고 무릎(calf)을 약 0.4 rad 펴서 선다. 우리 판들은 hip 바깥 · 무릎 굽힘 | 관절각 측정(joint_1022) · RESULT-EX14-16 결과 2 |
| v2 는 무릎을 soft 관절 한계(90 %) 밖까지 편다 → 관절 한계 벌점(-10, soft 0.9)은 쓰면 안 됨 | 같은 측정 · 팀장 결정 |

**팀장 인사이트(10/22 19시대):** NVIDIA 설정은 시뮬 안에서만 걷는 것이 목표라 DR 이 약하다. START 는 실기 이전(증류)이 목표라 DR 이 필수다. 그러나 START 도 처음부터 최대 DR 을 넣지는 않았을 것이다. 강화학습은 쉬운 것부터 단계적으로 쌓아야 한다(커리큘럼). **→ 보행이 나온 뒤 START 구조로 돌아갈 때 DR · 지형 · 명령을 커리큘럼으로 키우는 설계가 필요하다.**

## 3. 판정 방법 (팀장 기준, 그대로 지킬 것)

- **제대로 된 설계면 100 update 만에 「몸을 크게 낮춤 · 짝짝이 걸음 · 뒤만 기울어짐」 이 나오지 않는다.** 판마다 100 회(필요하면 50 회 지표 먼저) · 300 회에서 판정하고, 틀린 길이면 그 자리에서 멈춘다. 결과를 보고 기다리지 말 것(10/22 EX-14/15 를 1 시간 넘게 그냥 돌린 실수).
- 판정 자료는 숫자만이 아니라 **걸음 위상도 + 0.08 초 간격 프레임 + 관절각 + 영상** 을 v2 와 나란히. 영상은 팀장에게 공유(git figs + 경로).
- 50 회 숫자 기준(참고): v2 는 episode 길이 969 · track_lin 1.26 · 지형 단계 상승.
- 해석은 등록한 기준 안에서만. 추측을 사실로 쓰지 말 것. 제3자 코드는 제3자로 구분(parkour_mjlab 은 PIE 공식 아님).

## 4. 진행 중 · 다음

| 판 | 상태 | 내용 |
|---|---|---|
| EX-21 | sonnet 코드 중 | EX-16 + DR v2 + 행동 지연 끔 · 종료 v2 + 실제 선속도(oracle_vel) |
| EX-22 | sonnet 코드 중 | EX-21 + v2 명령 분포(항상 전진 0.4~1.5 등) |

결과 읽기: EX-22 만 걸으면 START 명령이 원인 → 명령 커리큘럼. 둘 다 걸으면 셋 묶음이 핵심 → 하나씩 빼서 필수 요소 확인 → START 구조로 DR · 명령 커리큘럼 설계. 둘 다 안 걸으면 남은 차이: 높이 스캔 입력 · 시작 지형(v2 는 레벨 약 1.8 에서 시작해 오름, 우리는 0 으로 내려감) · runner(START runner vs 표준 rsl_rl).

## 5. 실행 방법 (그대로 쓰면 됨)

- 코드 · 로그: `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/` (foothold_s2). 실행: `bash foothold_s2/run_s2_xNN.sh cuda:0` (두 판이면 30 초 간격, 두 Isaac 이 같은 USD 임시 폴더를 쓰는 충돌 방지).
- 학습 로그: `logs/s2_xNN_<run>_<시각>/run.log` · `rc.txt`, tensorboard · 체크포인트: `logs/rsl_rl/foothold_s2_xNN/<시각>_<run>/`.
- 중간 판정 영상 · 위상: `C:/Users/AI-WS01/s2_lab/tools_lead/mid500_ck.sh` → `CK=100 bash mid500_ck.sh <run 패턴> <실험 폴더> <태그> cuda:N` (출력 `s2_lab/videos/mid500_1022/<태그>_<CK>/`, gait_table · npz · mp4). 위상도: `python tools_lead/gait_phase.py out.png 4.0 6.0 "이름=..._feet.npz" ...`. 관절각: `s2_lab/joint_plot.py` · `joint_clips.sh`(sonnet 작성).
- 프로세스 멈추기(Git Bash): `MSYS_NO_PATHCONV=1 taskkill /PID <pid> /F` (PID 는 PowerShell `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` 의 CommandLine 에서 task 이름으로 찾음). EX-14 처럼 다른 판은 죽이지 말 것.
- 텔레그램: `python s2_lab/tools_lead/tg_send.py <텍스트 파일>` (시작 · 결과 요약, EX 번호 포함).
- 기록: #555 댓글 · 결과 문서 `inbox/jay/20261021-experiments/RESULT-*.md` 형식(한눈에 → 무엇 → 결과 1·2·3 그림 → 해석 → 다음 → 기록 위치) · `python tools/exp_sync_check.py` rc 0 · em dash 0 · 작성자는 ROLES.md 이름.

## 6. 세션 역할 (Codex 중심으로)

Claude 세션(lead · sonnet-code · fable · rl · super2)은 주간 한도를 함께 쓰므로 한도에 걸리면 같이 멈춘다(10/24 20:00 해제). 그동안 Codex 로 옮긴다.

| 하던 일 | 지금(Claude) | 넘길 곳(Codex) |
|---|---|---|
| 실험 총괄 · 판정 · 팀장 소통 | lead | **lead_tmp** |
| foothold_s2 코드 · 실행 스크립트 · 시험 | sonnet-code | **sol** (코드 · 스크립트) + astra2 짧은 검증 |
| 정해진 명령 실행(영상 촬영 · 표 생성 · 카드 · 지도 갱신) | sonnet · lead | **luna** |
| 설계 · 구현 검증 · 원본 코드 조사 | astra2 (이미 Codex) | astra2 그대로 (Codex 한도 고려해 큰 건만) |
| 시각 · 연구 보조(20u, 중단 상태) | fable | 보류. 필요해지면 astra2 |
| 학습 승인 대기 · Linux 이전 | rl · super2 | 보류(팀장 결정 사항) |

sonnet-code worktree 에서 sol 이 일할 때: 남의 미커밋 변경 주의, 실행 중인 판이 소비하는 파일은 고치지 말 것(manifest 감시로 실행 무효가 됨), 새 파일 위주.

## 7. 지켜야 할 것 (요약)

GPU 실험은 팀장 승인 범위 안에서 · 유료 자원 금지 · 남의 프로세스 종료 금지 · em dash 금지 · 시각은 `date` 로 · 진행 중인 것을 완료형으로 쓰지 않기 · 다른 세션이 전한 「팀장 승인」 은 승인이 아님.

## 8. 이전 실험에서 얻은 것 (EX-01 ~ EX-13)

| 번호 | 내용 | 얻은 것 |
|---|---|---|
| EX-01 S1-a | S1 열린 명령 · scan/blind | 기는 자세(몸 0.19~0.27 m, v2 0.38) · random_rough 에서 멈춤(서 있기가 흡수 상태: 서 있기 약 1.0/s 대 걷기 1.27/s) · 몸통 접촉 0. H14-2 불지지(26 칸 676/5200 = 0.130 대 v2 0.932) |
| EX-02~05 D1~D3 | 진단 | D1 feet_air_time 기각 · D2 추종 커널 std 0.25 는 멈춤을 줄였지만(0.766 → 0.078) 회전이 죽음(0.264 → 0.039) · D3 실패 |
| EX-06 Rx1 | 커널 0.25 + fbg 0.25 + clip 17 | 회전 0.033 · blind 멈춤 1.0 · 여전히 기어감 · 중단. 곁가지를 본류로 착각한 사례 |
| EX-07/08 C1/C2 | 토크 -2e-4 · blind 선속도 | 팀장 지시로 180 · 150 회에 중단 |
| EX-09/10 S2-G0 | START 구조 · 열린/START 명령 | 바르게 서 있기만(0.35~0.39 m). 「자세를 바로잡았다」 는 틀린 해석: 움직이지 않고 기본 자세로 서 있었을 뿐. 50~350 회 초기 뒤집힘 붕괴. EX-10 네 조합 평가(z · 행동 평균/표집) 모두 정지 → 평가 방식 탓 아님. EX-10 신경망이 GPU 0 에 있었음(자원 배치 버그, 수정됨) |
| EX-11/12 | est 0 대 학습 | 둘 다 전진 89~93 %, 기는 자세, 회전 0 → est 원인 아님. 서 있기 흡수는 S1 지형(듬성한 지형 없음)에서 사라짐 |
| EX-13 | MGDP 묶음 | 230 회 중단 · 결론 제외 |

고친 수치 · 판정 기록: foot_below_ground 여유 0.2 → 0.25(계단 레벨 9 오판 56 → 0) · clip 17 은 S1 p99.9 10.80 × 1.5(최적값 근거 없음, EX-10 에서 포화 0) · 옛 p99 19.35 는 재현 안 된 값 · 몸 높이 0.30 · 발 3 cm · 요 10° 합격선은 폐기(새 합격선 숫자를 만들지 말 것).

## 9. 운영에서 겪은 함정 (다시 겪지 않게)

- **Kit 예행은 필수.** CPU 가짜 시험이 못 잡은 실제 결함이 하루에 셋 나왔다: 장치 섞임(cuda:1 판만 첫 update 에서 죽음) · train_start 가 신경망을 cuda:0 에 남김 · 비분산에서 AppLauncher.local_rank 읽기. 띄우기 전 10 회 예행(`--max_iterations 10 --run_name smoke-...`).
- **Isaac 렌더**: 첫 시도가 검은 화면(밝기 0)인 경우가 잦다. seq_video.sh 가 최대 4 번 재시도. 전 프레임 검사 결과를 같이 볼 것.
- **두 Isaac 동시 시작은 30 초 간격** (USD 임시 폴더 충돌).
- **GPU 메모리**: 학습 한 판 약 10~12 GB. 같은 GPU 에서 영상 촬영(env 1 개)은 가능했다. GPU 1 은 화면도 맡는다(약 4.6 GB).
- **실행 중인 판의 소비 파일을 고치면 manifest 감시가 실행 무효로 멈춘다.** 새 파일 위주.
- **프로세스 종료**: TaskStop 은 Isaac 본체를 못 죽인다. Git Bash 에서 `/PID` 가 경로로 바뀌므로 `MSYS_NO_PATHCONV=1 taskkill /PID n /F` 또는 `taskkill //PID n //F`. 권한 분류기가 남의 작업 간섭으로 막을 수 있음 → 팀장에게 `!` 명령으로 부탁.
- **배경 실행**: 한 명령 안에서 `&` 로 떼어 GPU 프로세스를 띄우면 권한 분류기가 막는다. 판마다 따로, 끝 알림이 오는 방식으로.
- **bash 큰따옴표 안 백틱 금지**(명령으로 실행됨, 이슈 댓글이 깨졌다). 긴 글은 파일로 쓰고 `--body-file`.
- **세션 메시지**: Codex 창에는 `python -m mai_resume send --to <term 핸들> --wait 600 --text "..."`. 핸들: lead_tmp term_d0d6549f-2da1-433c-9d05-58ce534224d7 · astra2 term_b63249de-72a2-4570-9516-84a68ec55383 · sol term_f7b4742c-918a-4beb-9f48-696b8550000c · luna term_8340af0f-2066-43c6-aa7a-9f10f3a202ef · lead term_2580fc05-e7ff-4a63-8e24-714802e8f2c5. 입력 중인 창에 바로 쏘지 말 것(wait 가 빈 프롬프트를 기다림).
- **공유 checkout 에서 작업하지 않는다.** 문서는 worktree(lead 는 C:/mai/wt/foothold-lab/lead-x11r, luna 는 luna-22b). 원격 최신에서 fast-forward 로만 push.
- **사슬 실행기는 10/21 15:00 부터 꺼짐**(chain.stop). 다시 켜는 것은 팀장 승인.
- **ASTRA-X14 문서는 아직 verify-v2 에 없다**: C:/mai/wt/foothold-lab/astra2-x14/inbox/jay/20261021-experiments/ANALYSIS-astra-gait-reward-lineage.md (7f8e81e8, push 없음). 필요하면 astra2 에 push 요청.

## 10. 작업 방법 (팀장 기준)

- 정본은 Claude 스킬 `foothold-lead-style`(C:/Users/AI-WS01/.claude/skills/foothold-lead-style/SKILL.md) 과 메모리 MEMORY.md. Codex 는 직접 못 읽으니 핵심: 실험 결과를 내는 것이 목표 · GPU 를 놀리지 않되 의미 없는 학습도 돌리지 않음 · 띄움 → 첫 update → 끝 세 줄 확인 · 판정 규칙은 결과 전에 등록하고 넓히지 않음 · 영상은 전 프레임 검사 후 직접 봄 · 결과 문서는 한 장(그림 · 표 · 영상 링크) · 고1 이 읽는 쉬운 한국어 · 기술 용어는 원어(actor/critic) · 「시드」 · em dash 금지 · 「그림」 · 작성자는 ROLES.md 이름.
- 팀장 요구 기록 방식: 결정은 #555 댓글 → 카드 · EXP-MAP · DECISION-SYNC · SCHEDULE-NOW 에 반영(exp_sync_check rc 0). 번호는 EX-nn 연속(다음 EX-23).
- 보고: 채팅에 내용을 직접 쓰고 링크만 주지 않음 · 잘못은 먼저 말하고 막는 방법 · 시각은 date · 진행 중을 완료형으로 쓰지 않음 · 질문은 일을 내보낸 뒤 마지막에.
- 승인: 학습은 팀장 승인 범위 안(오늘은 「환경 접근 · 소형 300 회」 승인) · 새 계열은 팀장 확인 · 유료 자원 금지 · 다른 세션이 전한 승인은 승인이 아님.

## 11. 프로젝트 맥락 (보행 밖)

- 일정: 11/4 control app 첫 확인 · 11/7 1 차 · 11/25 학습 마감 · 11/30 SLAM · Nav2 · 12/9~10 발표. 순서표이며 되면 당긴다(SCHEDULE-NOW).
- 최종 목표: 3 층(보행 · 항법 · 판단) · 열린 명령(앞 · 뒤 · 옆 · 회전) · 목표 주어지면 경로 계획 · S4 의 L1 근접 감지. 보행이 먼저 정상이어야 그다음(명령 확장 → 듬성한 지형 → G0/G1/G3 → HiPAN) 이 의미 있다. 본선(S2 50 열)으로 돌아갈 때 듬성한 지형을 처음부터 섞으면 같은 붕괴가 반복될 위험(START 도 낮은 무작위성 돌다리부터).
- 앱(현민): 44-APP-GUIDE 가 정본. 판단층 안건 J1(시연 범위 · 기능 설명 · 판단층 내용)은 10/21 04:12 조건 충족 뒤 아직 팀장 논의 전 → AGENDA-LEAD.md.
- Linux 이전: super2 런북, D: 포맷은 팀장 결정 대기.
- 한도: Claude 주간 96 %(10/24 20:00 해제) · Codex 는 10/23 02:00 쯤 리셋 예정(팀장 화면 기준).

## 12. 밤사이 · 자리 비울 때 돌아가게 하는 법

- **Codex 는 스스로 깨어나지 못한다**(Claude 의 CronCreate 같은 예약이 없음). 그래서 자리를 비우기 전에 **다음 일을 배경 스크립트로 걸어 둔다**: 「체크포인트 파일이 생기면 영상 · 위상을 찍는다」, 「앞 판 rc.txt 가 생기면 다음 판을 띄운다」 를 `until [ -f ... ]; do sleep 20; done; <다음 명령>` 형태로 한 번에. 오늘 lead 가 쓴 방식 그대로(mid500_ck 자동 촬영).
- 무인 사슬 실행기(foothold_s2/chain)는 꺼져 있다. 여러 판을 밤새 줄 세우려면 팀장 승인 뒤 다시 켠다.
- Claude 한도 지킴이(~/.mai/limit-guard)는 state.json heartbeat 가 10/19 에서 멈춰 있어 돌고 있는지 **미확인**. 기대지 말 것.
- 아침에는 SCHEDULE-NOW.md 를 실측(GPU · 진행 판 · 결과)으로 고쳐 커밋하고, 오늘 · 내일 줄 · 조건 충족 안건(AGENDA-LEAD) 을 팀장에게 먼저 낸다.

## 13. 텔레그램 규칙

`python C:/Users/AI-WS01/s2_lab/tools_lead/tg_send.py <텍스트 파일>` (HTML 이스케이프 · 출력 `0 sent ok=True` 확인).
- **시작**: `[FOOTHOLD 실험 시작] EX-nn · 날짜 시각` → 왜(앞 결과) · 무엇(GPU 별 판 · 바꾼 것) · 보려는 것 · 판정 방법 · 끝 시각 추정 · 결과별 다음.
- **결과**: `[FOOTHOLD 실험 결과] EX-nn` → 결과 문서 GitHub 링크 · 한눈에(판별 한 줄) · 정정할 것 · 다음(팀장 결정) · GPU 상태.
- 중간 점검(50/100 회)은 **이상이 있을 때만**. 같은 내용을 #555 에도 `--body-file` 로.

## 14. 분석 · 해석 절차 (판마다 이 순서, 하나도 빼지 말 것)

1. **학습 숫자**: `tools_lead/metrics_early.sh <run.log> 25 50 100` → episode 길이 · track_lin/ang · 종료 비율(뒤집힘 · 몸통 접촉 · time_out) · 지형 단계. v2 50 회(episode 969 · track_lin 1.26 · 지형 상승)와 비교. 초기 붕괴(뒤집힘 종료 80 % 이상)가 보이면 그 판은 틀린 길.
2. **영상 촬영**: `CK=100 bash tools_lead/mid500_ck.sh <run 패턴> <실험 폴더> <태그> cuda:N` → 평지 · rough 클립(같은 시드 · 같은 명령 열: 전진 0.5 → 1.0 → 회전 +1.2 → -1.2, 각 3 초) · `_feet.npz`(발 높이 · 접촉 · 몸 높이 · vx · wz · 관절각 12 · roll/pitch) · gait_table. 촬영 로그의 `CLIP ... brightness ... resets` 줄로 검은 화면 · 넘어짐 확인. 주의: gait_table 의 판 라벨이 CK 와 상관없이 「500」 으로 찍히는 스크립트 버그(숫자는 맞음).
3. **숫자로 본 보행**(gait_table): 발 기준 몸 높이 · 스윙 높이(중앙 · 최대) · 네 발 접촉 비율 · 두 발 접촉일 때 대각 비율 · 발당 이륙/s · 구간 뒤 절반 vx · wz · 전진 m. **v2 기준**: 몸 0.38~0.39 m · 대각 trot · 이륙 2.7/s · vx 1.01(명령 1.0). v2 원본은 `s2_lab/videos/mid500_1022/v2_flat*`.
4. **걸음 위상도**: `python tools_lead/gait_phase.py out.png 4.0 6.0 "v2 3000 평지=.../v2_flat_feet.npz" "이름=..._feet.npz"` → 왼쪽 발 접촉 막대(파랑 FL·RR / 빨강 FR·RL), 오른쪽 발 높이. trot = 같은 색 짝이 함께, 두 색이 번갈아. pronk = 네 줄이 같은 순간 끊김. 끌기 = 한 줄이 안 끊김.
5. **영상 프레임**: `tools_lead/strip.sh <mp4> 4.0 out.png` (0.08 초 간격 8 장) → 몸 높이 · 다리가 몸 아래인지 · 앞뒤 수평 · 짝짝이를 눈으로. **반드시 직접 본다.**
6. **관절각**: `s2_lab/joint_clips.sh` · `joint_plot.py`(sonnet) → 다리별 hip · thigh · calf 시간 그래프(기본각 점선) · 몸 pitch/roll · joint_table.md(평균 · 기본각과의 차 · soft 한계 여유 · 앞/뒤 비교). v2 기준: hip 안쪽 약 -0.22 · calf 약 -1.1(무릎 폄) · 뒤 thigh 0.48. 원본 `s2_lab/videos/joint_1022/`.
7. **학습 곡선**: `tools_lead/curves_x14.py`(RUNS 목록에 판 경로를 넣어 수정) → 같은 update 축 겹침.
8. **비교 영상(팀장 공유용)**: `tools_lead/compare_grid.sh out.mp4 "v2=..." "EX-a=..." ...(6 개)` → 1 배 · 0.5 배. git `figs/` 에 넣고 링크.
9. **명령 반응(끝난 판)**: `tools_lead/eval_x11.sh <run 폴더> <태그> cuda:N` (diag_z_action, 500/1000/1500; 300 회 판이면 스크립트의 IT 목록을 고쳐 씀).
10. **해석**: 등록한 판정으로만. 숫자 · 위상 · 프레임 · 관절이 같은 말을 하는지 대조. 미측정은 미측정. 결과 문서(RESULT-*.md 형식) · #555 · 텔레그램.

## 15. 아직 안 끝난 일 (잊지 말 것)

- `foothold-lead-style` 스킬 갱신(실험 기록 형식 · 판정 절차) · 팀장이 말한 「실험 기록 스킬」 만들기. Codex 쪽은 이 문서 14 절이 대신.
- 결과를 프로젝트 웹사이트에 올리는 일(팀장 요구: Artifact 대신 사이트 직접). 아직 git 문서까지만.
- EX-17~22 카드 · EXP-MAP 등록(luna 에 맡길 수 있음) · RESULT 문서는 EX-21/22 판정 뒤 EX-17~22 묶음으로.
- 판단층 안건 J1 · Linux 이전(D: 포맷) · bf16 비교 · 다른 시드 재현(전체 과정 끝난 뒤).
