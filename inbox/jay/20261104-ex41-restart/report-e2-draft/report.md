# EX-42 E2 결과 보고서 · 초안
> 분류: 시뮬 결과 보고서 초안
> 작성: Claude 세션 (오흥재 지시, scripter-lx) · 2026-11-24
> 근거: [결정 원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv) · fee56fb2cf79c8a3eea7ec242a1787dc70182490
> 요지: 경계별 평가 근거를 모아 정식 보고서의 빈칸과 한계를 드러낸다
> 상태: 초안 · 발행 금지 · 원장 밖 숫자 미확인

이 문서는 보고서 구조와 원장 근거의 연결을 시험하는 초안이다. 인용은 원장 행에서 생성하며 재집계 결과가 아니다.

## 1. 목표와 평가 항목

| 항 | 임시 평가 항목 | 상태 | 근거 |
| --- | --- | --- | --- |
| 1 | 지킬 칸 | 확인된 범위만 | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2731) |
| 2 | 다음 지형 묶음 | 계획 · 실행 대조 필요 | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2758) |
| 3 | 평균대 지도 이득 | 두 경계 근거 있음 | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2766) |
| 4 | 깃발 방향 | 이 초안의 E2b 근거 미확인 | 미확인 |
| 5 | 카메라 자리와 복원 오차 | 경계별 근거 일부 있음 | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2738) |
| 6 | ONNX 실기 넘김 | 제한 근거 있음 | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2743) |
| 7 | 추가 목표 항목 가 | 정식 목표 문구 미확인 | 미확인 |
| 8 | 추가 목표 항목 나 | 정식 목표 문구 미확인 | 미확인 |
| 9 | 추가 목표 항목 다 | 정식 목표 문구 미확인 | 미확인 |
| 10 | 추가 목표 항목 라 | 정식 목표 문구 미확인 | 미확인 |

정식 목표 열 항의 문구와 번호는 이 초안에서 미확인이다. 위 항목명은 보고서 자리 표시이며 목표 달성 판정이 아니다.

## 2. 학습 줄기

| 칸 | 원장 원문 발췌 | 근거 |
| --- | --- | --- |
| START 기반 기준 저장본 | ★ 목표 1 빈칸 (planner 05:58): 정본 3 m15500 은 C/box L4 를 지도 이득 +34.7 로 넘던 저장본 (11/20 1450 행) · 지금 줄기 E2b m500 은 C/box L4 끝 생존 (공식 넘음 잣대 · ex42-prep.yaml 816) GT 4.5 \| PRED 12.0 \| 끔 7.0 /64 · 이득 -2.5 · L5 바닥 = E2 줄기에서 상자 능력 사라… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2758) |
| 이전 E 경계 저장본 | ★ m1250 E 전진 0.5 열 (목표 3 · 기록 · 192 대 · 시드 42~44 · 64 대당): 평균대 L2 넘음 정답 63.0 · 복원 63.7 · 끔 32.3 · 평지 지도 23.3 · 이득 +39.7 · 생존 63.3 (앞 값 NAXF m250 60.3 · XC m250 62.3 · 11/22 m500 41.0) / 평균대 L4 넘음 정답 60.0 · 복원 61.0 · 끔 13… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2695) |
| E2b 첫 경계 | ★ E2b m250 지킬 칸 (eval/keep/m250 · 시드 42~44 · 192 대 · planner 직접 셈 · GT \| PRED · 괄호 m1250 E): 끝 생존 192/192 · 수준 0 전진 0.1 0.101 \| 0.101 (0.100) · 0.2 0.208 (0.209) · 옆 ±0.2 0.198 · -0.198 · ±0.4 0.388 · -0.388 (0.387 · -0.… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2731) |
| E2b 다음 경계 | ★ 평균대 L5 공식 지도 이득 E2b m500 (mapgain_outcomes.json · 첫 창): 0.7 GT 64 \| PRED 64 · 평지 12.7 · 이득 +51.3 · GT 생존 64 대 끔 17.3 / 1.0 GT 64 \| PRED 64 · 평지 13.7 · 이득 +50.3 · 네 시험 참 · 판정기 verdict graduate (need 2 = 속도 둘 · 경계 둘 아님)… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2754) |
| E2b 최근 경계 | ★ 평균대 L5 공식 지도 이득 E2b m750 (둘째 창 · eval/mapgain/m750): 0.7 GT 64 \| PRED 63.7 · 평지 12.7 · 이득 +51.3 · GT 생존 64 대 끔 18.7 / 1.0 GT 64 \| PRED 64 · 평지 13.3 · 이득 +50.7 · 네 시험 참 → 평균대 L5 공식 지도 이득 두 경계 연속 (m500 · m750) 통과 = 목표 3… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2766) |

## 3. 평균대와 지킬 칸

| 칸 | 원장 원문 발췌 | 근거 |
| --- | --- | --- |
| 공식 지도 이득 첫 창 | ★ 평균대 L5 공식 지도 이득 E2b m500 (mapgain_outcomes.json · 첫 창): 0.7 GT 64 \| PRED 64 · 평지 12.7 · 이득 +51.3 · GT 생존 64 대 끔 17.3 / 1.0 GT 64 \| PRED 64 · 평지 13.7 · 이득 +50.3 · 네 시험 참 · 판정기 verdict graduate (need 2 = 속도 둘 · 경계 둘 아님)… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2754) |
| 공식 지도 이득 다음 창 | ★ 평균대 L5 공식 지도 이득 E2b m750 (둘째 창 · eval/mapgain/m750): 0.7 GT 64 \| PRED 63.7 · 평지 12.7 · 이득 +51.3 · GT 생존 64 대 끔 18.7 / 1.0 GT 64 \| PRED 64 · 평지 13.3 · 이득 +50.7 · 네 시험 참 → 평균대 L5 공식 지도 이득 두 경계 연속 (m500 · m750) 통과 = 목표 3… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2766) |
| 단계 평가 | ★ E2b m750 P1 공식 (사슬 · 게이트 6.8 · 07:41:59~08:10:39 · rc 0 · Traceback 0): 평균대 L5 GT 성공 32/32 생존 32 (끝 선 다시 분류 13) \| PRED 성공 30/32 생존 30 (12) · 기준 성공 26 · 생존 30 = PASS (PRED 생존 여유 0) · first_window_pass true · 판정 HOLD (지킬… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2769) |
| 깨끗이 건넘 | E2b m500 남은 칸 (planner · EMA 76adac096eee · GT \| PRED): 평균대 L4 깨끗이 (128) 0.852 [0.780, 0.903] \| 0.805 (m250 0.922 · 구간 겹침) · ★ L5 깨끗이 (128 · 처음) 0.406 [0.325, 0.493] \| 0.383 · 완주 0.852 · 0.867 · 발 빠짐 57 · 62 = 공식 지도 이득 (… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2760) |
| 지킬 칸 첫 경계 | ★ E2b m250 지킬 칸 (eval/keep/m250 · 시드 42~44 · 192 대 · planner 직접 셈 · GT \| PRED · 괄호 m1250 E): 끝 생존 192/192 · 수준 0 전진 0.1 0.101 \| 0.101 (0.100) · 0.2 0.208 (0.209) · 옆 ±0.2 0.198 · -0.198 · ±0.4 0.388 · -0.388 (0.387 · -0.… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2731) |
| 지킬 칸 최근 경계 | E2b m750 지킬 칸 · 지도 이득 끝 (07:31:53~08:11:53 · rc 0 · Traceback 0) · 지킬 칸 C/box L2 (192 · 끝 생존 /64 · GT \| PRED \| 끔) 61.7 \| 58.7 \| 60.3 · x>=3.3 64 \| 64 \| 63 (m500 훑기 L2 63 \| 64 \| 61.5 와 같은 자리) · 나머지 지킬 칸 채점 planner · GPU0… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2770) |

공식 지도 이득과 깨끗이 건넘은 서로 다른 지표다. 최근 경계의 깨끗이 판정은 미확인이다.

## 4. 지연 처치

| 칸 | 원장 원문 발췌 | 근거 |
| --- | --- | --- |
| 지연 없는 E2b | m1500E2 (본줄 · m1250 E raw 2e853a617eaa 에서 지연 없이 · 새 OUT EX-42-B-E2_20261124_012130 · 01:21:29 기동 · 코드 285ae63fa) 3b: 첫 update · Traceback 0 · RULE2 두 rank · CMD_WIDE 두 rank · DELAY_DR 0 줄 · X_FALL_DOWN_OFF 평균대 5/76 · 부모… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2709) |
| 지연 유지 DP | ★ fa1c66b35 · efbac4a3b 줄 (DP) 판정 = 적응 없음 (턱걸이 · 넓히지 않음): DP m250 EMA 89d70be77cab (m1500 D 에서 지연 0~20 ms 그대로 +250 · Pod) 깨끗이 0.7 (256 · GT \| PRED) L2 0.848 [0.799, 0.887] \| 0.852 · L3 0.770 [0.714, 0.817] \| 0.754 · 완주 1… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2745) |

## 5. 카메라와 ONNX

| 칸 | 원장 원문 발췌 | 근거 |
| --- | --- | --- |
| 카메라 자리 평가 | 목표 5 · 6 얼림 후보 E2b m250: 카메라 A R B 넘음 GT \| PRED 384/384 \| 384 · 384 \| 384 · 384 \| 383 · 끝 생존 1.000 · 지도 오차 A 1.22 \| 1.22 · R 1.97 \| 2.13 · B 1.61 \| 1.65 (m1250 E 와 같음 · R 복원만 1.99 → 2.13 · 모서리 6.56 → 7.04 · 192 대 한 번이라 방… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2738) |
| 복원 지도 테두리 사례 | 목표 5 B/beam L4 복원 지도 결함 덤프 (opus · E2b m500 · 카메라 A · 시드 42 · /home/jay/data/foothold/mapdump_bbeam_L4_1124/bbeam_L4_gt_vs_pred.png): (a) 몸 옆 깊게 꺼진 자리 (정답 -1.0 m · 바닥 자름) 를 복원은 -0.6 m 안팎으로 얕게 그림 = 옆 낭떠러지를 얕은 턱으로 봄 (b) 앞… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2767) |
| ONNX 산출 | 목표 6 E2b m250 ONNX 나옴: /home/jay/data/foothold/onnx/mapmask_e2b_m250_1124 start_step.onnx 46d2949b10a8 · start_actor.onnx 05b925571cff · sha256sum -c OK · 새 한 파일 대 옛 켬 · 끔 그래프 차 0.0 · torch 대 onnx (실기록 4 · 2400 틱) 켬 acti… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2739) |
| 실기 넘김 제한 | fb4c97b18 줄 판정 (opus · float64 참값 · 기록 4 x 600 스텝 x 8 대): E2b m250 = 등록 줄로 「결함」 (평지 켬 기록 하나: (b) onnx 최대 2.63e-5 = (a) torch32 1.10e-5 의 2.39 배 · p99 1.17 배 · ORT 최적화 끔도 2.23 배 · FR 종아리 한 관절만 튐) · 나머지 기록 셋 반올림 / m1250 E… | [원장](https://github.com/foothold-project/foothold-lab/blob/fee56fb2cf79c8a3eea7ec242a1787dc70182490/inbox/jay/20261104-ex41-restart/decisions.tsv#L2743) |

ONNX 산출과 실기 넘김 판정은 분리한다. 다른 카메라 자리의 모서리 오차와 실기 경로 확인은 미확인이다.

## 6. 못 한 것과 다음

- 열 목표의 승인 원문, 최근 경계 깨끗이 채점, 실기 넘김 여부는 미확인이다.
- 정식 원자료와 평가 영수증을 대조한 뒤 표와 그림을 채운다. 이 초안은 발행하지 않는다.

## 부록 A. 출처와 판 이력

- 원장 판: `fee56fb2cf79c8a3eea7ec242a1787dc70182490`
- v0.1 · 원장 근거 연결과 빈칸을 둔 보고서 뼈대.
