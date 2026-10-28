> 분류: 보고 (planner → lead · analyst · verifier)
> 작성: 오흥재 (planner) · 2026-10-27 00:1x
> 근거: lead 의뢰 23:2x(연장 판정표 · 커리큘럼) · 보강 23:3x(A 보행 위상 · 지형별 · 회전 폭 / B 순서 검증 · 세분화) · 규칙 의뢰 RULES-AXES-LINEAGE 23:4x · analyst VERIFY-analyst-EX35-GATES(astra-25b, 23:45 중간본 + 00:0x 5~7 절) · 원자료(sb10_eval · hardlevel · 부모 env.yaml · EX-35 logs_gate · resume 실행 폴더) · 선행 원문(START · AME-2 · MOVE HTML · Rudin)
> 요지: 커밋 **a46a0103**(feature/fable-25a-jay, push 없음) 다섯 파일. 막음 **2**(아래). 규칙 초안(RULES-HUB 10 절 · EXPERIMENT-RULES 11 절) 위에 EX-35 연장 판정표 v0.7 · CURRICULUM v0.2 를 얹었다. analyst 지적 중 확인한 것은 전부 반영했고 숫자는 원자료 경로와 함께 적었다.
> 상태: analyst 반박 · verifier 검증 · 팀장 확인 전. GPU · 학습 · 코드 수정 없음. EX-35 는 cuda:0 에서 진행 중(23:24:46 기동, 23:56 it 1578, 24.1 s/회, m2001 약 02:46)

# REPORT planner 00:12 · RULES-AXES-LINEAGE 초안 + EX-35 v0.7 + CURRICULUM v0.2

## 1. 막음 (실행을 멈춰야 하는 것) 2

| 번호 | 막음 | 근거 | lead 가 정할 것 |
|---|---|---|---|
| 막음 1 | **A5 걸으며 돌기 기준선이 없다**: m1500 의 `walk_turn_left` · `walk_turn_right` 재측정(EX-35 §5 조건 5) 이 아직 없어 창 경계(m2000) 판정표의 A5 칸이 「미측」 이 되고, RULES-HUB 10.1 규칙으로는 **판정 불가 = 멈춤 · 보고** 다 | `impl-turncases/logs/sb10_eval/m1500/turn16_*/` 에 `arrays_walk_turn_*.npz` 없음(ls) · 10.1 첫 줄 | m2001(약 02:46) 전에 cuda:1 에서 m1500 두 경우 × 켬 · 가림 평가(승인 없이, 8.3) 를 누구에게 걸지 |
| 막음 2 | **A11 영상 칸은 연장 전 증거**(팀장 23:1x (원장) · analyst 1.5). v0.6 의 「연장은 영상을 기다리지 않는다」 를 철회했다. 밤사이 lead 가 칸을 못 채우면 m2000 에서 **멈춤 · 보고가 기본값**이고 GPU0 는 그때부터 논다 | EXP-EX35 v0.7 §4b.1 A11 · §4b.3 5b | 03:50 전후 lead 가 판독할 수 있는지, 없으면 멈춤을 받아들일지(사람 대기 관문이 아니라 증거 칸이라는 analyst 해석을 따름) |

## 2. 바뀐 파일 (a46a0103)

| 파일 | 판 | 바뀐 것 |
|---|---|---|
| `inbox/jay/20261019-design/RULES-HUB.md` | v1.6 초안 (lead 브랜치 79da1093 판을 fable-25a 로 복사해 고침. fable-25a 에는 이 파일이 없었음) | **10 절 신설**: 10.1 축 표 A1~A12 + 뒤 단계 A13~A17(정의 · 소비 코드 · 원자료 자리 · 잡음 폭 · 기준선 출처 · 상태; 축 빠지면 판정 불가) · 10.2 이전 학습 비중(앞 단계 합 ≥ 20 % · 되돌림 REVERT → 비율 내림) · 10.3 학습 조건 표 칸 ↔ 실행 기록 자리 표, 생성기 `train_cond_table.py`(구현 배정), 정본 채택 5 단계, **S-B10 「정본」 제안** · 10.4 계보 지도 첫 판(B1500 → S-B10 → EX-35, 가중치 계보 대 설정 계보 구분: S-B10 은 B1500 의 자식이 아님) · 10.5 용어 clock_scatter · episode_scatter. 7 절 **R20~R22**(의뢰문 축 누락 · 단계표 무검증 · lead 창 끼어듦). 8.1 표에 10.1 축 행. 9 절 S-B10 「정본 제안」 · B1500 · S-B50 「후보였음」 · 「흩기 b50」 → clock_scatter b50. 2 절 lead 창 송신은 `mai_resume send`(lead 00:0x 정정 2). 5 절 21:5x 줄의 lead 근거 「부모 kept 최소 14」 틀림 표시 |
| `inbox/jay/20261019-design/EXPERIMENT-RULES.md` | 1.5 초안 (lead 브랜치 판 기준) | 11 절(축 전부 · 비중 · 학습 조건 표 생성기 · 정본 절차 · 용어) · 2 절 「학습 조건 표는 생성기로」 |
| `inbox/jay/20261021-experiments/EXP-EX35-SB10-cmd-S2a.md` | v0.7 | §4b.1 을 축 A1~A12 로 다시 씀(아래 3 절) · §4b.2 평평 예시 정정(m2250 → m2500 → m2750, +0.115) · 기대 시각 실측(기동 23:24:46 · 24.1 s/회 · m2001 02:46 · 판정 03:50) · §4b.3 2(세 모드 + L9 + A1 그림) · 5b(A11 은 7a 전) · 6(결측 = 판정 불가) · 연장 소비기 필수 검사 5 개(analyst 7 절 반례) · §3 kept 14 근거 정정 · 용어 |
| `inbox/jay/20261026-experiments/JUDGE-SPEC.md` | v0.11 | 3 절 · 6.8.1 kept 14 근거 정정(부모 eval_gt 최소 **13**: m1250 fwd_then_left · m1350 fwd_then_right, probe m1350 right_then_left **10** · 13 · 13 → 6.8.1 kept_ok 두 저장본 False, HOLD) · 6.2 용어 |
| `inbox/jay/20261026-experiments/CURRICULUM-GATES.md` | v0.2 | §0 analyst 반박 반영 표 10 행 · §1 원칙(20,000 은 총량 목표 보존 + 듬성 노출 원래 목적) · §2a 팀장 여덟 자리 맞음/바꿈 표(바꿈 셋: DR 항목별 · 횡 · 후진 둘로 · 복원 지도 단계 추가; analyst 깃발 앞당김 제안) · §2b 21 단계(합 하한 14,500 · 중앙 21,000 · 상한 27,500) · §2c 순서 선택지 · §3 섞기 비율 표 · §4 되돌림 · §5 비용 · §6 analyst 요청 5 |

## 3. EX-35 v0.7 §4b.1 축별 요지 (숫자는 원자료 경로와 함께 카드에)

| 축 | 기준선(S-B10 m1500 실측) | 하한 · 등급 | 상태 |
|---|---|---|---|
| A1 보행 위상 | analyst baseline.json: GT fwd0.5 대각 쌍 사이 88.49° · C 0.149 · 주기 0.698 s / GT fwd1.0 167.03° · C 0.035 · 0.475 s / 가림 92.28° · 151.02° / R 0.29~0.57 | 문턱 **미정**(planner 임시안 ± 30° · ± 0.1 s · C + 0.10, 가정) · 0/180 일괄 기준 금지 | 기준선 있음 · 문턱 analyst |
| A2 지형별 전진 | hardlevel_table: L0~2 켬 5.428 · 가림 5.441 · pred 5.417(64) / L6 5.27 · 5.27 / L9 켬 5.01(59) · 가림 5.28(62) | 0.90 · −6(추정) · 종류별 7 종은 **미측 · 확장 지점** | 레벨 묶음으로 |
| A3 회전 16 env | 여섯 경우 Q · C · kept 좌우 따로 + 8 등분(analyst rotation_bins: indep_right 0~1 s 0.99 → 7~8 s 0.10 후반 정체 = 부모 한계) | §3 유지 조건 · 폭 **0.115**(RESULT-EX34 165 · 8.2; analyst 재계산 0.0987 재대조 중) | 있음 |
| A4 회전 64 env | 좌 0.195 · 우 0.302 · 64 · 64 | 0.10 · 0.102 · 48 | 있음 |
| A5 걸으며 돌기 | **미측**(막음 1) | 성공선 0.25 · 추세 +0.115 | 기준선 미측 |
| A6 생존 | kept 15~16 · 64; 부모 이력 최소 켬 13 · 가림 10 | kept < 14 기록 · 64 env 회전 < 48 멈춤 | 있음 |
| A7 기울기 | 여덟 경우(127 env) 5.33° · 9.28°, 회전 6 만(95 env) 5.81° · 10.06°(planner · analyst 일치) | ≤ 8.0° · 14°(가정 × 1.4) | 분모 오기 정정 |
| A8 접촉 링크 평면 속도(미끄럼 대용) | 0.070 · 0.232, 회전 6 만 0.060 · 0.203. 접촉력 **크기** > 1 N(`turn_probe.py:128` norm) | ≤ 0.12 · 0.40(가정) | 이름 · 정의 정정 |
| A9 학습 곡선 | m950~m1500 창 평균 범위(tb_stats) · EX-35 it 1578 kl 0.0154 | value > 0.072 · KL > 0.05 · entropy < 7.5 · bad_orientation > 0.25 두 창(가정) | 있음 |
| A10 지도 소비 모드 | eval_pred 5.417 | A2 하한 | 있음(평가) |
| A11 영상 1x | 기준 문장 ①~⑤(⑤ 대각 쌍 아닌 교대 추가) | 연장 **전** 증거(막음 2) | 사람 |
| A12 재현 | 1e-6 · 1e-3 · 해시 · sha · 시드 | 다르면 연장 불가 | 확장(64 env · A7 · A8) |

## 4. analyst 지적 처리 (VERIFY-analyst-EX35-GATES 1 · 3 · 5 · 6 · 7 절)

| analyst | 확인(원자료) | 처리 |
|---|---|---|
| 1.1 START 20,000 아님 · 「최소 20,000」 을 상한으로 읽음 | :221 10,000 맞음 · 팀장 원문 「최소」 | CURRICULUM §1.4 보존 · APPROVED L 절 듬성 노출 목적까지 |
| 1.2 부모 kept 최소 14 아님(13 · 13) | 재측: eval_gt m1250 13 · m1350 13, probe m1350 10 · 13 · 13 | JUDGE-SPEC v0.11 · EX-35 §3 · RULES-HUB 5 절 줄 정정. 숫자 14 자체는 lead 권고 · 팀장 ok 로 유지 |
| 1.3 미끄럼은 대용 · 5 절 접촉력은 벡터 크기 | probe_result track_contact_points=false · turn_probe.py:128 norm | A8 이름 「접촉 링크 평면 속도」 · 「접촉력 크기」 |
| 1.4 · 7 절 consume 결측 CONTINUE · 같은 PASS 둘 EXPAND · 새 축 미검사 | judge_gate.py:647~668 읽음 | §4b 머리 · 세 갈래 「멈춤」 에 결측 · 소비기 필수 검사 5 개 |
| 1.5 영상 미확인 ≠ 통과 | 팀장 23:1x 원문 | A11 연장 전 증거(막음 2) |
| 3 절 종류별 기준선 없음 | map_modes.json 에 종류 없음 · hardlevel 은 레벨만 | A2 레벨 묶음 + 확장 지점 |
| 3 절 0.083 · +0.10 | RESULT-EX34 165 행 0.115 | A3 · A5 폭 0.115 통일(analyst 0.0987 병기) |
| 3 절 평평 예시 750 회 | 그대로 오류 | §4b.2 정정 |
| 3 절 PRED 전환 누락 · C3 두 축 동시 | DESIGN-NEXT 229 · 214 행 | A10 축 · C3a(소비) · C3b(가림) · C4(듬성) 분리 |
| 3 절 합 산술 · C0 L9 · MOVE · START 식 · 횡 후진 범위 · DR 부모 켬 | 전부 원자료 · 원문으로 확인(MOVE Table I 시뮬 · 부모 env.yaml 1292~1369 마찰 0.2~1.2 · 질량 −1~+3) | CURRICULUM §0 · §2a · §2b |
| 5 절 tilt/slip 분모(여덟 경우) | tilt_slip.py 가 8 npz 읽음 맞음 | A7 · A8 두 분모 병기 |
| 6 절 깃발 앞당김 · Rudin DR | 제안으로 §2a · §2c 에 | 팀장 결정 |

## 5. 가정(analyst 반박 대상) 과 lead 가 정할 것

- 가정: A1 임시 문턱 · A7 · A8 × 1.4 · A9 배수 · A5 폭 빌림 · 섞기 비율(≤ 15 % 입장 · ≥ 20 % 유지 · 전진 55/40 %) · 21 단계 예상 회차 전부 · 상한 m3000 · 평평 2 창.
- lead 가 정할 것: (1) 막음 1 평가 배정 (2) 막음 2 밤사이 A11 판독 가능 여부 (3) RULES-HUB 10 절을 lead 브랜치로 가져가는 방법(fable-25a a46a0103 cherry-pick, 파일은 lead 79da1093 판 기준이라 충돌 없음 예상 · 미확인) (4) 9 절 S-B10 「정본」 제안 팀장 확인 (5) 10.3 생성기 · 10.4 계보 지도 · §4b 확장 지점(gait_phase · level_forward · tilt · trend · curve_check · recompute · window_judge · extend) 구현 배정 (6) 「흩기」 저장소 전체 치환(lead_tmp inbox 13 파일 · DESIGN-NEXT 35 곳) (7) 5 절 21:5x 원장 줄의 lead 근거 정정 (8) CURRICULUM §2a 바꿈 셋 · analyst 깃발 앞당김 제안의 팀장 결정.

## 6. 재지 않은 것

A1 · A2 · A5 · A7 · A8 잡음 폭(같은 저장본 재평가 없음) · 종류별 7 종 전진 기준선 · 회전 6 만의 부모 범위(tilt · 접촉 속도) · 레벨 L9 평가 소요(추정 10 분) · lead 브랜치 cherry-pick 충돌 여부 · mai_resume send 실제 동작(이 보고 뒤 처음 씀).
