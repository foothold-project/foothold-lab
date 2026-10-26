## 8. 이 결과로 다음 설계에서 무엇을 바꾸는가

- **출발선은 S-B10 m1500 이다** (sha256 4d987818c7e25b89). 팀장 10/26 「출발선: S-B10 m1500을 권합니다. => 우선 승인」 (RULES-HUB 원장 bba2fe52). planner OPINION v0.2 (fable-25a af3a87f3) 와 analyst v0.2 (사본 60c2baa5) 가 서로 안 보고 같은 권고를 냈다. m1200 (지도 켬 전진 5.96 m, 오래 도는 우회전 유지) 은 대안으로 보존만 한다.
- **끔 비율 0.1 은 그대로 둔다** (팀장 13:3x). 학습 중 지도 끔은 연속 7 종과 평지에서만 뽑고, 듬성 지형에서는 끄지 않는다 (결정 9, 팀장 미결). 10% 는 허용 지형 안에서 센다 (lead 권고, 팀장 미결). 지금 통합 코드는 허용 50,000 중 4,959 (9.918%) 로 이미 그렇게 동작한다 (analyst VERIFY-integ-demotion).
- **회전은 출발선 고르는 점수에서 뺀다.** 16 env 독립 회전의 뒤 절반 평균은 m1200 우 0.84 · 좌 0.11, m1500 우 0.13 · 좌 0.38 로, 저장본마다 오래 버티는 방향이 바뀐다 (#555 6409875635). 「돌 때 16 중 14 이상 생존」 은 관문 바닥 조건으로 남긴다 (팀장 「관문에 있어야하는 건 맞는 것 같아」). 회전 학습은 다음 설계의 둘째 단계다.
- **전진은 m1200 → m1500 에서 0.53 m 줄었다** (켬 5.96 → 5.43 m, 가림 5.94 → 5.44 m). 생존 60/64 이상 칸의 B1500 재측정 차 최대 0.0096 m 보다 훨씬 크다. 다음 단계의 유지선은 m1500 × 0.9 = 4.885 m 다 (analyst, 유지선이지 완성선이 아니다).
- **지도 쓰임은 연속 지형으로는 못 잰다.** 레벨 0~2 · 6 · 9 에서 켬 − 가림 ≈ 0 이다 (hardlevel_table 39fe6643). 듬성 지형 고정 칸 (50 열 중 23..47) 이 다음 첫 평가다. B1500 레벨 0 첫 결과는 켬 · 가림 모두 도착 단 0/64 이고, 건넘 지표는 reviewer 고침 1 · 2 로 고치는 중이다. S-B10 듬성 평가는 고정 worktree impl-eval-ef8c 에서 진행 중.
- **바꾸는 순서는 팀장 확정** (「analyst 순서로 확정」, 원장 26b904aa): 지형 강등 오판 차단 확인 (analyst 막음 0 · 고침 2) → 회전 명령 과정 → 복원 지도 사용 → 듬성 지형 · 추가 DR. 한 판에 한 축만 바꾼다.
- 카드 4 절의 회전 「같음」 문턱 0.12 rad/s 는 여섯 경우 중 한 경우가 0.1207 로 문턱 밖이다. 16 env Q 재측정 폭 (최대 0.115) 과 같은 크기라 「다름」 으로 읽지 않는다 (추정). 해석은 영상 · 위상 판독 전까지 미완.

## 9. 실제 완료와 재현 경로

- 학습: `C:\mai\wt\foothold-lab\impl-sb\logs\rsl_rl\foothold_s2_sb\2026-10-26_01-17-47_sb-main`, 10/26 01:17:35 GPU0 기동 · 11:20 rc 0, model_1500.pt. 코드 impl-sb 6309f67e. 첫 update 실현 끔 0.0951, 전체 평균 0.0988 (3 절).
- 평가: impl-turncases 7996823f 의 `foothold_s2/eval/post_train_eval2.sh` 사슬, 원자료 `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval\m*`. 회전 열 · 출발선 표 · 어려운 칸 표는 lead `figs/startline/` (rot_series · startline_table · hardlevel_table).
- 이 문서의 숫자: `figs/ex33-34/gen_result.py` (isaac311 python, CPU), 시험 `test_gen_result.py` 5 통과 (lead 재실행), 원자료 · lead 표 대조 16,012 건, 깨끗한 두 사본 바이트 같음.
- 영상: 릴리스 https://github.com/foothold-project/foothold-lab/releases/tag/research-sb-1500-20261026 · 로컬 `C:\Users\AI-WS01\s2_lab\video_25e\final\runner-26a_1026_final\` (SHA256SUMS.txt). 머리글은 runner-26a 7d49fafc · 범례는 b64892f9 판.
- 판정 코드: 통합 브랜치 feature/judge-mapratio-integ-jay (impl-integ), planner JUDGE-SPEC v0.6.
