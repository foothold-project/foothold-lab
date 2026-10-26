## 8. 이 결과로 다음 설계에서 무엇을 바꾸는가

- **S-B50 은 출발선이 아니다.** 출발선은 S-B10 m1500 (팀장 「우선 승인」, 원장 bba2fe52). S-B50 은 m1400 에서 좌회전 세 경우가 넘어져 (kept 10 · 11 · 11) 「연속 두 저장본 통과」 가 끊겼다 (planner OPINION v0.2). 규칙대로 고르면 m1300 이다.
- **끔 비율을 0.5 로 올릴 까닭은 없다.** S-B50 m1500 과 S-B10 m1500 은 모두 지도 가림에서 64/64 로 걷는다 (전진 1.0: 5.31 m · 5.44 m). 끔을 다섯 배 늘려도 「지도 없이 걷기」 는 더 나아지지 않았고, 켬 전진은 S-B10 이 길다 (5.43 대 5.32 m). 그래서 0.1 을 유지한다 (팀장 13:3x).
- **오래 도는 회전은 S-B50 이 더 고르게 유지한다.** m1500 독립 우회전 8 등분은 0.22~0.41 rad/s 로 끝까지 남고, S-B10 은 첫 1/4 뒤 0.05~0.22 로 떨어진다 (#555 6409865094). 이것은 출발선 고르는 점수가 아니라 회전 명령 과정 (다음 설계 둘째 단계) 의 비교 자료로 쓴다.
- 지도 쓰임은 S-B10 과 같이 연속 지형에서는 켬 − 가림 ≈ 0 이라 못 잰다. 듬성 지형 고정 칸 평가는 S-B10 다음으로 같은 칸에서 진행 중 (impl-eval-ef8c).
- 카드 4 절의 회전 「같음」 문턱 0.12 rad/s 는 한 경우가 0.1209 로 문턱 밖이다. 16 env Q 재측정 폭 (최대 0.115) 과 같은 크기라 「다름」 으로 읽지 않는다 (추정). 해석은 영상 · 위상 판독 전까지 미완.

## 9. 실제 완료와 재현 경로

- 학습: `C:\mai\wt\foothold-lab\impl-sb\logs\rsl_rl\foothold_s2_sb\2026-10-25_23-45-04_sb-main`, 10/25 23:44 GPU1 기동 · 10/26 09:54:42 rc 0, model_1500.pt (sha256 e6d8ba631f24e816). 코드 impl-sb 6309f67e.
- 평가: impl-turncases 7996823f 의 `foothold_s2/eval/post_train_eval2.sh` 사슬, 원자료 `C:\mai\wt\foothold-lab\impl-turncases\logs\sb50_eval\m*`. lead 표 `figs/startline/`.
- 이 문서의 숫자: `figs/ex33-34/gen_result.py` (isaac311 python, CPU), 시험 5 통과 (lead 재실행), 대조 16,012 건, 두 사본 바이트 같음.
- 영상: 릴리스 https://github.com/foothold-project/foothold-lab/releases/tag/research-sb-1500-20261026 · 로컬 `C:\Users\AI-WS01\s2_lab\video_25e\final\runner-26a_1026_final\`.
