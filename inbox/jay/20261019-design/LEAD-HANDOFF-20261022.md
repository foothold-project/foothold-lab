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
