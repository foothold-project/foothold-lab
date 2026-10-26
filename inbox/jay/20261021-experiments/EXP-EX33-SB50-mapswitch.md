> 분류: 실험
> 작성: 오흥재 (lead 정리) · 2026-10-26
> 근거: 팀장 22:5x 승인 · impl-sb 6309f67e · RULES-HUB 8 절 · DESIGN-NEXT-draft v0.3 11 절
> 요지: 에피소드마다 지도를 켜고 끄며 처음부터 배우면, 한 정책이 지도 있을 때는 B 만큼, 지도 없을 때는 G0-B 만큼 걷는다.
> 상태: 학습 끝 · 평가 끝 · 결과 문서 RESULT-EX33-SB50-1026.md (10/26 17:3x) · 해석 미완 (영상 · 위상 판독 전) · 출발선 아님 (m1400 연속 끊김)
> 판: v0.1

# EX-33 · S-B50 (지도 켜고 끄기 p 0.5, 처음부터)

## 가설

에피소드마다 지도를 켜고 끄며 처음부터 배우면, 한 정책이 지도 있을 때는 B 만큼, 지도 없을 때는 G0-B 만큼 걷는다. 반반 (p 0.5) 이면 두 쪽을 다 충분히 배운다.

## 설정

- 설정: B (EX-28) 와 같고 하나만 다르다. env 마다 reset 때 확률 0.5 로 지도 끔, 에피소드 끝까지 유지, 끔은 지도 토큰을 attention 키에서 뺌 (0 높이로 넣지 않음). critic 은 B 와 같음 (끔 env 도 정답 지도).
- 코드: impl-sb feature/sb-switch-jay fbad5342 · 6309f67e (reviewer 막음 0 두 번). 첫 update EX33_MAP_SWITCH realized 0.5049, 24.5~25.6 초/회.
- 학습 로그: `C:/mai/wt/foothold-lab/impl-sb/logs_gate/sb_main_20261025_234449/run.log`.

## 판정 (결과 전 고정, 10/26 00시)

같은 잣대로 B1500 · G0-B · S-B50 · S-B10 넷을 잰다 (RULES-HUB 8 절). 저장본 m1500 기준, 16 env 값은 평균 (재측정 폭 평균 0.11).
- 지도 켬 (eval_gt) 64 env 고정 칸 c3884d68: 전진 1.0 6 초 거리가 B1500 (5.65 m) 의 0.9 배 이상이면 「지도 켬 유지」.
- 지도 가림 (probe_prop_only, 지도 없는 판은 none) 64 env: 전진 1.0 6 초 거리가 G0-B m1500 의 0.8 배 이상이면 「지도 없이 걷기 있음」. 생존 수도 같이 적는다 (선 채로 산 것과 걸어서 산 것을 나눈다).
- 회전: 16 env 여섯 경우, 지도 켬 · 가림 각각. 회전 속도와 네 발 동시 접촉 비율. 차이가 0.12 rad/s 안이면 「같음」.
- 셋째로 영상 (단일 + 비교, 회전 구간이 거친 땅 위인지 확인, R17) 과 학습 곡선 (켬 · 끔 따로) 없이 해석하지 않는다.
- 역할 (팀장 10/26 00:2x): **출발선 후보는 B1500 · S-B50 · S-B10**. G0-B 는 지도 입력이 아예 없어 출발선이 아니라 「지도 없이 걷기」 의 기준선이다 (가림 기준 0.8 배의 분모). 지도 켬 유지 + 지도 없이 걷기 있음을 둘 다 만족하는 S-B 판이 있으면 그 판, 둘 다면 회전 여섯 경우가 나은 판. 없으면 B1500.
- B1500 짝 판 (reviewer 26716fb8 고침 1): B1500 도 eval_gt · probe_prop_only · eval_pred 세 모드, 두 번 (재실행 폭) 같은 꼴로 잰다. 배포 모드 eval_pred 는 S-B m1500 에도 잰다.

## 결과

결과 문서: [RESULT-EX33-SB50-1026.md](https://github.com/foothold-project/foothold-lab/blob/feature/verify-v2-mvp-jay/inbox/jay/20261026-experiments/RESULT-EX33-SB50-1026.md) (9 절, 숫자는 figs/ex33-34/gen_result.py). 영상: https://github.com/foothold-project/foothold-lab/releases/tag/research-sb-1500-20261026 · 로컬 C:\Users\AI-WS01\s2_lab\video_25e\final\runner-26a_1026_final\. 대표 영상: C:\Users\AI-WS01\s2_lab\video_25e\final\runner-26a_1026_final\CMP-B1500-G0B-SB50-SB10-m1500_mapmasked_rough_seq_1x.mp4 (네 판 지도 가림 비교) · C:\Users\AI-WS01\s2_lab\video_25e\final\runner-26a_1026_final\EX33-SB50-m1500_mapmasked_rough_seq_1x.mp4 · C:\Users\AI-WS01\s2_lab\video_25e\final\runner-26a_1026_final\EX33-SB50-m1500_mapgt_rough_seq_1x.mp4. 카드 판정: 지도 켬 유지 · 지도 없이 걷기 PASS, 회전 켬 · 가림 같음 5 · 다름 1. 이후 결정: 회전은 출발선 고르는 점수에서 뺀다 (팀장 10/26 16시, 원장 bba2fe52). 위 판정 절의 회전 우선 문장은 그 결정으로 대체된다 (결과 전 고정 문장이라 지우지 않고 남김).

## 다음

판정의 출발선 후보가 나오면 그 판에서 회전 명령 과정 (걷기 → 걸으며 돌기 → 제자리 회전, verifier 막음 D1~D4 반영) 을 잇는다. 다른 시드는 전체 과정 끝에 한 번.
