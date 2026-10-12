> 분류: 인계 (밤샘 Top-down · 세션이 끊겨도 이어 가기용)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 01:17
> 근거: 팀장 10/13 01:10 「제안 · 권고대로 진행 · 세션 한도가 차면 9 분 뒤 문제없게 이어서」 · #546 댓글 · 이 밤의 커밋
> 요지: 지금 무엇이 돌고, 언제 무엇을 확인하고, 다음에 무엇을 하는지. 세션이 새로 열리면 이 파일부터 읽는다
> 상태: 진행 중 (갱신될 때마다 머리 시각을 date 로)

# 밤샘 인계 (10/13)

## 지금 도는 것 (세션과 무관하게 계속 돈다)

| 자원 | 무엇 | 출력 · 끝나는 때 (추정) |
|---|---|---|
| GPU 0 | `_eval/branch/night_20261012_cmdr.sh` (고치지 말 것) · off 군 → on 군 · 군당 4,000 update | 로그 `_eval/out/branch/cmdr_s1042_{off,on}_u4000.log` · `night_20261012_cmdr.out`. 01:15 에 off 21,338 · 5.5 s/iter → off 22,000 ≈ 02:16 · 24,000 ≈ 05:20 · on 22,000 ≈ 08:25 · on 24,000 ≈ 11:30 |
| GPU 1 | `_eval/unseen_driver.py` (미경험 지형 · 하위 작업) → 끝나면 `_eval/cmdr_eval_driver.py` v3 (CMD-R 평가 · 00:19 부터 대기 · `--until 2026-10-13 14:00`) | 미경험: `out/unseen_driver.log` (01:15 에 69/100) → 평가 ≈ 02:00 · 영상 ≈ 04:30. CMD-R: `out/cmdr_eval_driver.out` · `.json` · 시험 넷 → 본 평가 |
| CPU | RoboGauge 큐 (하위 작업 · `_eval/robogauge/run_queue.sh` · 8 프로세스) | `out/robogauge/queue.log` (01:15 에 5 번째 e1_model_20499) ≈ 02:00 |
| ASTRA | 의뢰 10 · Go2 앱 리버스 (rea) · 00:39 시작 | `inbox/jay/20261013-go2-app-study/REPORT-astra-10.md` |
| 하위 조사 둘 | star 저장소 연쇄 · 논문 인용 연쇄 (01:15 시작) | `inbox/jay/20261012-arch-discussion/SURVEY-repo-graph.md` · `SURVEY-citation-graph.md` |

## 세션이 새로 열리면 다시 걸 감시 (이전 세션의 대기 셸은 사라진다)

1. on 군 bundle 이 생기면 (≈ 05:20) `python _eval/cmdr_bundle_compare.py` → 종료 0 이 SAME. 결과 `out/branch/cmdr_bundle_compare__cmdr_s1042_off_u4000__cmdr_s1042_on_u4000.json`. DIFFERENT 면 on 군 평가는 드라이버가 스스로 막는다. 원인 확인 전 on 군 학습을 보류할지 판단 (프로세스 정리는 팀장 허용 범위 · `process-cleanup-allowed-in-topdown`).
2. `out/cmdr_eval_driver.out` 에 `tests passed` · `TESTS FAILED` · `PINS CHANGED` · `DEADLINE` · `Traceback`. 시험 실패면 `out/cmdr_eval_driver.json` 의 tests 를 보고 고친 뒤 다시 띄운다 (실행 중 파일 수정 금지 · 멈춘 뒤에).
3. `inbox/jay/20261013-go2-app-study/REPORT-astra-10.md` 가 생기면 읽고 #546 · 채팅 보고.
4. 미경험 지형 · RoboGauge 하위 작업이 보고하면 숫자를 lead 가 원자료로 다시 잰 뒤에만 인용.

## 아침 보고 (팀장 지시: 아티팩트를 갱신해서 보고)

- E1 · E2 페이지 (https://claude.ai/artifact/BYuAVDuVJuRWVkAs5mGJSN) 5판. 틀: job tmp `e12page/` (`assemble_v4.py` 다음 판 · `v5_cmdr.html` · `facts5_cmdr.py` 준비됨). 점검표 = 메모리 `artifact-report-skill`.
- 넣을 것: 밤사이 한 일과 시각 · 미경험 지형 성적과 실패 영상 (전 프레임 검수) · RoboGauge 점수 (저자 정책 0.6953 재현 확인 포함) · CMD-R 비교 (`out/cmdr_post.py` → `CMDR-tables.md`) · 구조 논의 (논문 + ASTRA 9 + lead · **v2 와 견줘 왜 새로 접근하고 무엇을 얻나**) · 관제 UI 기획과 RL 의 연결 · 팀장 질답.
- 게시 뒤 1920 × 1080 · 1366 × 768 · 390 렌더 확인.

## 오늘 밤 정해진 것

- ASTRA 7 「권고」 컨펌 (팀장). 2(c) 판정선은 lead 제안대로 (팀장 01:10 「제안 · 권고대로 진행」): 목표 세 칸은 칸마다 500 판 · 세 칸 모두 95 % 구간 하한 > 0 이고 평균 +10 %p 면 「개선」 · 퇴행은 100 판으로 훑어 점추정 −5 %p 이하 칸만 500 판으로 다시 재서 판정 · 기본 계약 (생존 95 % · 통과 90 %) 은 별도 · 최종 24,000 · CMD-R 은 비퇴행이면 「규약 교정」 으로 채택 가능, 「성능 개선」 은 시드 1043 반복 뒤.
- 구조: ASTRA 9 (고친 판) 권고 = 지형을 안 보는 MoE-CTS 를 주력으로 더 오래 학습하거나 expert 를 늘리지 않는다. 다음 주력 실험은 **A/B** (같은 gap · 징검다리 학습 · A 는 지도 자리에 상수 · B 는 실제 지도 · teacher → student 모방 없이 PPO · critic 만 privileged). 이것이 원래 P1 의 자리. G1 은 따로 하지 않고 A 군이 그 구실. 그 뒤 발 디딤 보상 on/off → 센서 현실화 → AME-2 는 마지막. ASTRA 11 로 이 설계와 넓힌 조사를 반박 검증받는다.
- Linux: 실험은 foothold-lab · 최종본은 foothold-go2 · go2_rl_robotlab 은 외부 의존 코드 · `FOOTHOLD_GO2_RL_ROOT=~/isaac/ext/go2_rl_robotlab` · `FOOTHOLD_DATA=~/data/foothold` · 순서 1-2 백업 (super) → 설치 → lab 이전 → 같은 숫자 시험 → 학습 재개 · 마감 목 10/15 · 마지노선 토 10/17.
- Go2 앱: 제약 없이 실제 앱 확보 · rea 분석 (ASTRA 10).
