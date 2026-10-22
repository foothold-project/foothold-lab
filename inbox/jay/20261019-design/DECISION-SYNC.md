> 분류: 운영
> 작성: 오흥재 (lead_tmp 대조 · sol 후속) · 2026-10-22
> 근거: verify-v2 c6582009 · sol f4501f7b·118a2242/취합 a731e2b1·cbb2e5e2 · #555 6310259601 · 6319562769 · ASTRA-X11
> 요지: EX-17~25 결정과 기준을 실험 지도·카드·일정 및 승인 방향에 연결하고 과거 이력을 보존한다
> 상태: 지정 결정의 문서 반영 확인 · 실행·실측 미확인 · 봉인 gates 불변

# 결정 동기화 · 10월 22일 갱신

실험 번호 정본은 [EXP-MAP](../20261021-experiments/EXP-MAP.md)이다. EX-01 S1-a, EX-02 D1, EX-03 D2, EX-04 D2-s43, EX-05 D3, EX-06 S1a-Rx1, EX-07 C1-scan, EX-08 C2-blind, EX-09 diag-G0-open, EX-10 diag-G0-start, EX-11 G0-zeroest, EX-12 G0-learnedest, EX-13~EX-25는 [EXP-MAP](../20261021-experiments/EXP-MAP.md)의 관계표를 따른다. 파일명은 유지한다.

검사 계약 `exp-sync-v1`: 「바뀌는 자리별 점검표」의 `체크`는 모든 반영 자리를 직접 확인했을 때만 `[x]`, 그 전에는 `[ ]`이다. 이 표는 문서 반영 완료를 표시하며, 체크 변경은 해당 자리의 근거를 대조한 뒤에 한다. `[x]`는 실험·실측·승인 완료가 아니다. 미확인인 실험 사실은 그 상태대로 각 자리에 기록되어야 한다.

## 최신 결정 · EX-17~25와 811 동회차 기준

10/22 최신 반영은 환경·관측 진단 EX-17~22, START 본류 EX-23 G1 및 EX-25 G0, v2 scratch 지류 EX-24a/b다. 근거는 [#555 6336845347](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6336845347) · [6338232352](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6338232352) · [6339275508](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6339275508) · [6342115176](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6342115176) · [6342170646](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6342170646) · [6342453922](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6342453922) · [`LEAD-HANDOFF-20261022.md` §§17~25](LEAD-HANDOFF-20261022.md) · [BASELINE-0811](../20261021-experiments/BASELINE-0811.md) · [EXPERIMENT-RULES](../20261021-experiments/EXPERIMENT-RULES.md)다. EX-16~22의 100~300회 낮은 자세 단독 조기 실패 판단은 811 동회차 기준으로 뒷받침되지 않는다. 원 관찰은 남기고 판정 근거만 정정한다. 300회는 낮은 자세에서 선행 이동하는지 보는 경고 후보, 500회는 상승·전진, 1000회는 trot 기준이다. 관절 한계 벌점은 미사용이며 DR은 약한 커리큘럼 방향이다. 본류는 START 구조부터 보는 EX-23/25다. 설계 정본 14·52·53 및 봉인 gates는 이번 등록만으로 바꾸지 않는다.

EX-25는 댓글 6342453922와 handoff §25의 초기 1001 목표를 보존하고, 이후 lead가 1501회로 다시 띄웠다고 전달한 사실을 최신 계획으로 구분한다. SCHEDULE-NOW는 10/22 23:00 배정 스냅샷을 기록한다. 그 시각 실제 진행 update·완료·영상 판독은 미확인이다. luna는 GPU를 기동하지 않았다.

## 현재 결정 · S2-G0 두 판과 결과별 다음 코칭

### 10/22 후속 결정 · EX-11/12 추정 연결 진단

lead가 전달한 팀장 승인의 대상은 [#555 6319562769](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6319562769)이다. EX-10 z/action 네 조합 평가를 학습 없이 먼저 하고, EX-11/12 코드·CPU 시험·lead 확인 뒤 병렬 학습한다. EX-11 actor는 `o45+0×est51`, EX-12는 `o45+est51`이며 지각 경로는 모두 돈다. 공통 3072 env·24 step·seed42, S1 이어진 지형 7종 23열·START 명령·clean critic664·B std0.5·종료 여유0.25·clip17, 500 점검·1500 상한이다. 기본은 둘 다 상한까지, 둘 다 통과하면 같은 완료 update에서 함께 멈출 수 있다. 무효를 성능 실패로 세지 않는다. 결과별 네 갈래·모호함 보류와 복귀 순서는 [EX-11 카드](../20261021-experiments/EXP-G0-zeroest.md#다음)에 사전 등록했다. 기존 본선과 봉인 관문은 불변이다. 아래 10/21 EX-09/10 설명은 당시 결정 이력이다.

현재 대조 기준은 `feature/verify-v2-mvp-jay@c6582009`와 sol 취합 `a731e2b1`·`cbb2e5e2`이다. [#555 6310259601](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6310259601)은 10/21 16:11:07 KST 게시, 본문은 「15시대 결정」이다. 댓글 내용과 아래 기준 파일은 직접 읽어 확인했다. 다른 세션이 전한 결정을 기록한 것이며, 이 문서 작성이 GPU 재개 승인이나 실행을 대신하지 않는다.

**S1-a 결합 구성 실패 → START 구조·지도 없는 EX-09 diag-G0-open / EX-10 diag-G0-start → lead의 2행2열 영상 판정 → 결과별 코칭 → S2 본류**다. 각 1500회·seed42. 몸 크기 비율·3 cm·10° 합격선은 폐기하며 몸 높이·발 높이·요·멈춤·전진은 기록용이다. 기존 41·52·gates v1.1 등록 관문은 그대로 둔다. 다른 시드 검증은 전체 과정 뒤 같은 과정을 한 번에 한다.

| 바꿀 자리 | 이번 결정이 요구하는 연결 | 최신 취합·작업 사본 대조 | 후속 담당·종료 증거 |
|---|---|---|---|
| [14 명령](14-COMMAND-GENERATOR.md) | 열린 명령과 START 명령 두 판을 구별. START 판만 정상일 때 START부터 명령 범위를 넓힘 | **반영**. cbb2e5e2의 §0 진단 계약·§10 현재 경로. EX-09/10·사슬 키·명령 범위·실제 cfg 미확인 구분 | lead/sol: 두 명령 계약과 조건부 커리큘럼의 수정 커밋·소비 cfg 연결 |
| [52 S1](52-S1-OPEN-COMMAND.md) | 보행 자세를 먼저 다룸. 지형 비율·커리큘럼·종아리는 자세 회복 뒤 험지 저하가 남을 때. 둘 다 정상일 때 S1을 S2에 합침 | **반영**. a731e2b1의 §0·§3·§6에 현재 G0 지류·기존 갈래의 역사적 범위·반증 범위 연결. S1-b 자동 진행 아님 | lead/sol: 실패 갈래와 조건부 합류 문구 수정. 진단 결과 전부터 S1 폐기 완료로 적지 않음 |
| [53 S2](53-S2-PERCEPTION.md) | 지도 없는 G0의 1500회 두 진단과 본 학습을 구별하고 결과별 다음 판 연결 | **반영**. cbb2e5e2의 §0에1500회 진단과3072 env·20000회 본선 구분, 기존 Linux/S0-L 본선 전제와 진단의 관계 기록 | lead/sol: 진단 공통 cfg·초기화·명령 차이와 본선 복귀 조건을 같은 판에 기록 |
| [APPROVED](APPROVED-DIRECTION.md) | 이번 결정 출처·범위·폐기한 합격선·전체 과정 뒤 시드 검증을 연결 | **반영**. 이번 R·S·T 절에 EX-06 처방 이력·시작점 잠정 범위·EX-09/10 새 결정·번호·2행2열 연결 | lead: 결정 원문과 적용 범위의 후속 절 |
| [SCHEDULE](SCHEDULE-NOW.md) | 오늘 밤 두 판 약2h → 영상 판정 → 사전 등록한 다음 코칭 | **반영**. 이번 변경에서 계획과 실제 기동 미확인을 분리. 아침 Rx1 진행 표는 이력으로 격리 | lead_tmp: 이 변경 커밋. 실행 담당의 실제 시각·폴더·판독 결과 수신 뒤 갱신 |
| gates | 기존 41·52·v1.1 관문 유지. 새 자세 수치 합격선을 넣지 않음 | **유지**. `evidence/baselines/gates-v1.1-sealed.json`은 이 작업에서 수정하지 않음. 커밋 바이트·LF 정규화 SHA `dd31cebd651fb4d6b7a904abdfdde443f5b94c6a562d59092773099d7e45ca37` 확인 | 판정 담당: 기존 수치 관문과 영상 코칭을 구분. 짧은 영상 정상을 기존 관문 통과로 쓰지 않음 |
| #555 | 결과 전 결정과 후속 실행·영상·다음 판을 이어 기록 | **결정 반영**. 댓글 `6310259601`에 세 결과별 코칭·폐기 기준·시드 순서 등록. 실제 결과는 미확인 | lead: 실행 기록·영상 판독·선택한 다음 판의 후속 댓글 |
| [EXP-MAP](../20261021-experiments/EXP-MAP.md)·실험 카드 | S1-a 실패 뒤 지류 선언·복귀 규칙, 설정과 결과 분리 | **반영**. [G0-open](../20261021-experiments/EXP-G0-open.md)·[G0-start](../20261021-experiments/EXP-G0-start.md) 초안. 결과 칸 공란 | 실행 담당: 실제 cfg·커밋·폴더·영상·판독을 카드에 연결 |

두 판 모두 정상일 때 S2-G0 본선, START 판만 정상일 때 명령 커리큘럼, 둘 다 기면 Go2 보상 크기·PD 점검이 등록된 세 갈래다. **열린 명령 판만 정상·미완료·영상이 모호한 경우의 다음 처방은 미등록**이다. 두 결과를 보존해 lead에게 보고하며 임의로 세 갈래 중 하나로 바꾸지 않는다. 이것은 추가 합격 관문이 아니다.

이 후속은 지도·카드·일정·APPROVED·AGENDA와 sol 설계 수정의 취합을 포함한다. **14·53의 G0 후속도 cbb2e5e2로 취합·대조했다**. 체크는 직접 취합·대조한 문서에만 붙인다. 아래 밤 점검은 당시 기준의 이력이며, 현재 파일의 취합 상태나 실행 중이라는 뜻으로 읽지 않는다.

## 밤 점검 이력을 읽는 기준

명명 후속은 `e3d5da42` 위에 luna `a974cf8d`의 내용을 손으로 병합한 **ca4ab4f8**로 닫았다. 정식명은 S1a-Rx1, 실행 기록의 옛 이름은 S1a-v1.1(코드 690dd194·학습 폴더 foothold_s1a_v11), 설계 §52의 S1a-v1.1은 별개 heading 처방이다. 아래 다른 점검 행은 기존 기준 시점의 기록이며 명명 완료가 그 행의 취합·실행 완료를 뜻하지 않는다. 커밋 식별은 `git log -1 -- inbox/jay/20261021-experiments/EXP-S1a-Rx1.md`로 확인한다.

기준은 `feature/verify-v2-mvp-jay@bc9d4b25`다. 이 기준에서 새 브랜치 `feature/experiment-ledger-jay`를 만들어 대조했다. sol 수정본은 `feature/sol-20u-jay@0259d4d0`, 실행 코드는 sonnet 사본의 명시한 커밋으로 따로 표시한다. **수정본이 있어도 취합본이 옛 값이면 완료 표시를 하지 않는다.** 같은 이름의 파일도 브랜치와 해시를 붙여 읽는다.

| 표시 | 뜻 |
|---|---|
| 반영 | 지정한 기준 파일의 해당 문장을 직접 읽어 확인함 |
| 수정본 · 취합 대기 | 별도 브랜치에는 있으나 위 기준에 아직 없음 |
| 부분 | 값·결정 중 일부만 있거나 현재 상태가 낡음 |
| 미반영 | 필요한 연결 문구를 지정한 범위에서 찾지 못함 |
| 유지 | 이번 결정이 그 자리의 기준을 바꾸지 않음. 누락과 다름 |
| 미확인 | 원자료·실행·정확한 적용 범위를 확인하지 못함 |

표의 「반영」은 파일 내용이 `확인됨`이라는 뜻이다. 시험 성공이나 팀장 승인으로 바꾸어 읽지 않는다. 원문 결정과 결과 전 등록 문구는 [실험 지도](../20261021-experiments/EXP-MAP.md)에서 해당 카드로 이어진다.

## 결정과 적용 범위

| 결정 | 근거와 범위 | 코드·실행 증거 | 남은 해석 문제 |
|---|---|---|---|
| 추종 커널 lin·ang std 0.25 | D2 진단 등록 [D2], 처방 선택 [V], 이 창 직접 진행 답 [A]. 분모는 std²=0.0625, 가중치는 유지. 적용 대상은 이번 S1a 처방 | `87d71df7` D2, `690dd194:foothold_s2/tasks/s1a_v11_cfg.py` 처방. [RUN] | scan 진단을 blind에 적용한 것은 외삽. S2의 보상을 승인 없이 같이 바꾸지 않음 |
| 발 빠짐 종료 여유 0.25 m | 계단 오판 진단과 처방 묶음 [V]·[A]. 발 가장자리 보상 마스크 0.2 m와 다른 값 | `21fd5e2d:foothold_s2/robots/go2_params.py`. `diag_s1a/fbg2_sample*/fbg2.json` | 전역 상수를 쓰는 다른 작업의 적용 범위도 표시해야 함. 기존 결과를 새 문턱의 결과로 재명명하지 않음 |
| 행동 clip 17 | 행동 분포·발산 진단 [CLIP], 처방 묶음 [V]·[A] | `e6efed92:foothold_s2/tasks/agents/s1_ppo_cfg.py`, 학습·평가 wrapper. dry 평가 [DRY] | p99.9 배수로 정한 값은 경험적 선택. 특정 1100→1130 재학습의 안정성·장기 안정성은 별도 증거 필요 |
| 축 3 시작점 | N1d 높이차·발 바닥 여유, N1e 가장자리 여유 [N1D]·[N1E]. lead 기술 선택으로 보고됨 | `d1570ec9`·`41f3e409`, sonnet `74301117`, PD `8412a08b`. [PD] | 높이≥0.30 m 기준 오류로 높이는 판정 불가. 9칸은 잠정 통과, no_start 6은 주행 실패와 구별 |
| S1a-Rx1 회복 처방(실행 옛 이름 S1a-v1.1) | 위 세 변경 묶음. scan·blind 각 6000회, 중간 점검과 최종 평가 분리 [V]·[A] | 학습 `690dd194`, 사슬 `ceeb7eeb`·`db189ac3`·`6ec4e374`, 평가 라벨 `9327c97f` | 원인 분리 실험이 아님. 명명 충돌은 해소: Rx1 카드에 실행 별칭을 연결하고, 기존 heading 처방과 봉인 값은 보존 |

직접 진행 답은 이 창의 09:23 접수이고, 실제 시작 로그는 09:17이다. 다른 창의 승인 시점은 이 표에서 독립 확인하지 않았다. 두 시각을 소급해 합치지 않는다. 시작점 기술 선택을 이번 처방 직접 승인과 같은 사건으로 합치지도 않는다.

## 바뀌는 자리별 점검표

설계 파일 번호만 적은 칸은 `inbox/jay/20261019-design/`의 해당 문서다. 각 행은 수정 책임과 실제 취합 여부를 함께 적는다. 이 표를 만들면서 아래 원문 파일이나 gates를 대신 수정하지 않았다.

<!-- exp-sync:decision:v1 -->
| 체크 | 결정 | APPROVED-DIRECTION | 설계 문서 | SCHEDULE-NOW | AGENDA-LEAD | gates | #555 |
|---|---|---|---|---|---|---|---|
| [x] | EX-06 커널 0.25 | R에 직접 답·std²0.0625·S2 자동상속 금지 | sol f4501f7b → 이 브랜치 a731e2b1, 16 §3 처방 이력 직접 대조 | EX-06 중단·현재 EX-09/10, 아침 처방은 이력 | 현재 상태 표의 EX-06 처방 연결 | 유지. 보상 값은 성공 문턱 아님, 봉인 SHA 불변 | 6304758796·6304887684, 해당 R 링크 |
| [x] | EX-06 fbg 0.25 | R에 종료 여유·보상 마스크 구분·옛 결과 보존 | a731e2b1의17 §7·52 §3, 56→별도0 진단과 한계 | EX-06 중단, 당시0.25 계획 보존 | 현재 상태 표에 범위·미완주 | 유지. 평가 조건 fbg_margin_m, 새 성공 문턱 아님 | 6304758796·6304887684, R 링크 |
| [x] | EX-06 clip 17 | R에 행동 제한·단위·범위 | a731e2b1의17 §7·52 §3, 관측 되먹임·단기 안정 한계 | EX-06 중단, 당시17 계획 보존 | 현재 상태 표의 처방 연결 | 유지. clip_actions는 소비 조건, 기존 봉인 불변 | 6304310458·6304758796·6304887684 |
| [x] | 시작점 규칙 | S에 lead 기술 선택·PD높이0.30 판정 불가·9칸 잠정·no_start6 | a731e2b1의41 §4 N1d/e 계약·§5 R_body 구현 차이 직접 대조 | 현재 축3 문단에 잠정·잔여 증거·관문 보존 | 현재 상태 표에 동결/다음 사용 시 확인 항목 | 유지. 시작점 세부 계약 정본은41, 봉인 수치 불변. no_start를 성공/실패나 분모 삭제로 바꾸지 않음 | 6302409827·6302777151·6303243159, S 링크 |
| [x] | EX-06 S1a-Rx1 묶음·중간 점검 | R에09:17 시작과09:23 직접 답·중단, heading 처방 별개 | a731e2b1의52 §3, 1500 AND·3000 계획과 결과 미확인 구별 | EX-06 중단·EX-07/08 뒤 EX-09/10, 옛 사슬을 현재 지시로 쓰지 않음 | 현재 상태·처방 종료와 잔여 확인 기록 | 유지. heading/prescription_arm의 S1a-v1.1은 별개 미실행 heading 판 | 6304758796·6304887684·6309063175 |
| [x] | EX-09·EX-10 G0 지류·번호·영상 | T에두판·세갈래·시드순서·폐기기준·번호정본·2행2열 | 52현재경로는 a731e2b1, 14·53 §0·본선 구분은 cbb2e5e2로 반영·직접 대조 | 현재 표에두판약2h·영상·후속. 사슬키와번호 명시 | 현재 상태·다음 코칭 표. EX-11부터lead부여 | 유지. 짧은 영상 진단이41·52·봉인관문 통과를 뜻하지 않음 | 6310259601·번호는이창lead후속지시, 발행 후댓글 연결 |
| [x] | EX-11·EX-12 est51 연결 진단 | U에 승인 전달 대상·두 mask·공통값·500/1500·무효·복귀 범위 | 14 §1 앞 진단 명령·깃발 복귀, 52 §1 앞 S1 관문 밖, 53 §1 앞 G0 본선 밖 직접 대조 | 10/22 순서 1~4·실행 미확인·clip17 한정 | EX-11/12 안건 닫힘·새 선택 질문 없음·C1/C2 cancelled 대조 | 유지. sealed gates 미수정, 4096 env·clip100 미채택 | #555 6319562769·ASTRA-X11 X1~X4. EXP-MAP·EX-10 보충·EX-11/12 카드에 결과 전 규칙 등록 |
| [x] | EX-17~25 환경·관측 및 START 본류 · 811 판정 기준 정정 | V에 환경·관측 접근, 관절 한계 벌점 미사용, 약한 DR, Top-Down START-first, 300 경고 후보·500 상승·전진·1000 trot 기록 | 14·52·53 정본은 변경하지 않음. 진단 지류와 본류를 카드·MAP에서 구분 | 10/22 23:00 GPU0 EX-23 G1 · GPU1 EX-25 G0, 각각 1501 목표. 실제 update 미확인 | J1~J5 이력 유지. 이 등록을 실행 승인으로 읽지 않음 | 유지. 기존 봉인 기준 불변 | [#555 6336845347](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6336845347) · [6338232352](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6338232352) · [6339275508](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6339275508) · [6342115176](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6342115176) · [6342170646](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6342170646) · [6342453922](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6342453922); handoff §§17~25; BASELINE-0811·EXPERIMENT-RULES. EX-16~22의 낮은 자세 단독 조기 실패 판정은 철회, 관찰은 보존 |

gates 전체를 새 하이퍼파라미터 저장소로 바꾸는 제안은 아니다. 최종 판정 기준은 그대로 두고, 실행 조건·중간 점검·정책 식별의 정본 위치를 연결하면 된다. 등록 파일을 바꿔야 한다고 lead가 정하면 새 판과 해시를 남기고, 이미 사용한 봉인본은 보존한다.

## gates와 소비 실행의 정확한 판

| 구분 | 파일·키 | 직접 확인한 값 | 한계 |
|---|---|---|---|
| 기존 scan 판정 | `eval_new/s1a_scan/judge_scan_vs_v2.json` | gates SHA `752362ef43fc1a943803562e978842da40d8681686a4da0521b9de959e77990a` | 기존 판정 결과를 새 처방 평가로 바꾸지 않음 |
| v1.1 봉인 원본 | `1a9062cc:inbox/jay/20261019-design/evidence/baselines/gates-v1.1-sealed.json` | SHA `dd31cebd651fb4d6b7a904abdfdde443f5b94c6a562d59092773099d7e45ca37` | 봉인 원본 유지. heading 처방 이름과 Rx1 실행 별칭을 분리해 해석 |
| dry 소비 기록 | [DRY]의 `gates.sha256_lf`, `fbg_margin_m`, `clip_actions` | dd31cebd 전체 SHA 일치·0.25·17.0, v11 model_100 로드 경로 | 한 칸·6판의 실행 기록. full 평가나 blind·축 2/3 전체 검증으로 확대하지 않음 |
| 새 평가 표시 이름 | `9327c97f:foothold_s2/chain/chain_s1a_night.yaml` | `s1v11scan=s1scan=...`, `s1v11blind=s1blind=...` | 왼쪽은 결과 라벨, 가운데는 adapter 종류. 코드상 분리 확인이며 새 라벨로 끝난 평가 증거는 아직 미확인 |

dry manifest에는 `argv`의 episodes 6·envs 2와 `params`의 기본값 100·10이 함께 남고, 환경 문자열 읽기 오류도 있다. 원자료 6판과 DONE은 확인했으나 기록 정합성 보완은 별도다. `5571fa39`는 clip 기록 쓰기 오류 수정이며 이 다른 표시 오류까지 고쳤다고 쓰지 않는다. [REVIEW]

## 밤 점검 당시의 후속 자리 · 현재 반영 여부는 위 체크표 우선

| 남은 일 | 현재 증거 | 담당·종료 증거 |
|---|---|---|
| 승인 방향에 실제 처방을 연결 | APPROVED는 Q까지, 새 처방은 채팅·이슈·안건에 분산 | lead가 직접 답의 범위·시각·관련 문서를 연결. 새 승인 요구가 아니라 기존 결정 기록 |
| sol 16·17·52 취합 | `0259d4d0` 수정본 존재, bc9d4b25에 없음 | lead: astra2 F3 뒤 취합 계획. 취합 커밋·파일 대조 결과 |
| heading 처방과 회복 처방 이름 충돌 · **닫힘** | lead 요청·luna `a974cf8d`를 `e3d5da42` 위에 수동 병합. 정식명 S1a-Rx1, 옛 실행 이름 S1a-v1.1, §52 heading 판은 별개(lead 인계상 미실행) | **ca4ab4f8로 완료**: [Rx1 카드](../20261021-experiments/EXP-S1a-Rx1.md)로 파일명 변경·MAP 링크·첫 언급 대응 완료. 원자료 대조 보존. 기존 설계·봉인·실행 폴더는 보존하며 다른 동기화 미완료는 유지 |
| 일정·안건의 낡은 진행 상태 | SCHEDULE은 `066157c3` 취합으로 09:41까지 반영됨. 이후 500회 실측·dry 결과는 후속 대상. AGENDA의 기동 미확인 문구는 낡음 | lead_tmp는 verify-v2 최신을 기준으로 후속 정리. 취합 커밋 확인 |
| 시작점 규칙의 설계 연결·잠정 범위 | N1d/e 코드·인계와 PD 결과에는 있으나 41·gates 연결 미완료 | lead/sonnet/sol이 실제 적용 계약 연결, astra2 F3에서 값·no_start 분모·PD 한계 대조 |
| 영상·관측/reset 대조의 공백 | 밤 영상 없음. 관측 원소별·reset 분포 비교 미실시라는 lead 답 | 비교 영상 경로·촬영 조건·관찰자·판독 결과. 수치 결과는 별도 보존. 관측/reset 미확인을 근거 없이 완료로 바꾸지 않음 |
| 새 라벨·평가 metadata 일관성 | YAML 분리 커밋 있음, full 소비 결과 없음 | sonnet의 실제 명령·manifest·CSV·판정 입력이 동일 판을 가리키는 증거 |

위 목록은 동결 검토를 위한 정보다. 이 표의 미완료 항목을 이유로 실행 중 학습을 자동 중단하거나, 팀장이 이미 답한 진행 여부를 반복 질문하지 않는다. 학습 감시와 최종 판정은 별도 등록 기준을 따른다.

## 다음 결정부터 기록할 행

결정이 오면 「결정 원문과 출처·시각 → 적용 대상·바꾸지 않는 범위 → 변경 자리 → 담당 → 수정 커밋 → 취합 커밋 → 소비 파일/해시·실행 증거 → 미해결」 순서로 한 행을 더한다. 파일을 쓰기 전 원격 verify-v2 HEAD와 자기 기준을 비교한다. 표기 완료는 직접 파일을 대조했을 때만, 실행 완료는 실제 소비 기록까지 있을 때만 한다.

## 근거

- [D2] [#555 6299099683 · D2 결과 전 등록](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6299099683)
- [V] [6304758796 · D3 판정·처방 선택·중간 점검](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304758796)
- [A] [6304887684 · 이 창의 직접 진행 답과 정정](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304887684)
- [CLIP] [6304310458 · 행동 발산 진단](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304310458)
- [N1D] [6302409827 · 높이차·발 바닥 여유](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6302409827), [N1E] [6302777151 · 가장자리 여유·no_start](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6302777151)
- [PD-C] [6303243159 · 높이 기준 오류·잠정 판정](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6303243159)
- [SOL] [6305209430 · sol 0259d4d0 후속](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6305209430)
- [MORNING] [6305115297 · 기동·일정](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6305115297), [REVIEW] [6305631760 · 확정·가설·남은 위험](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6305631760)
- [RUN] `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/foothold_s1a_v11/2026-10-21_09-17-28_s1a_v11_scan/`·`2026-10-21_09-17-30_s1a_v11_blind/`의 `train_start_status.json`·params. 실행 코드와 폴더 근거는 [밤 보고](NIGHT-REPORT-1021.md).
- [DRY] `C:/Users/AI-WS01/s2_lab/eval_new/dry_v11_eval/scan3/run_manifest.json`, `axis1_raw.csv`, `run.log`.
- [PD] `C:/Users/AI-WS01/s2_lab/eval_new/n1f_pd_1021/` 네 조건의 `pd.json`.

## 보고 전 점검

앞으로 보고 직전에 `python tools/exp_sync_check.py`의 확인 수·누락 수·종료 코드를 함께 적는다. 기본 소비 사슬은 `C:/Users/AI-WS01/s2_lab/chain/chain_state.json`이다. 검사기는 문서 체크·카드 형식·사슬 이름 연결·일정 갱신 시각을 검사하며, 실제 프로세스 생존·영상 판독·과학적 타당성·실행 승인을 판정하지 않는다. 체크를 채우기 전 변경 자리의 원문과 취합 커밋을 직접 대조한다.

이번 대조: sol f4501f7b·118a2242를 a731e2b1·cbb2e5e2로 취합한 뒤 지정 문서 연결 확인. CPU 검사기 시험 7개 통과. 기존 gates 봉인 커밋 바이트와 LF 정규화 해시 dd31cebd 전체 일치. 결과 카드의 미확인과 EX-09/10의 공란을 유지했다. 최종 실행 출력·시각은 완료 보고에 붙인다.

10/21 16:48:43 KST 실행 결과: **확인 27 · 누락 0 · 종료 코드 0**. C1/C2 키는 여전히 running이라는 저장값으로 검사됐고 지도 연결만 통과했다. cancelled 보고와의 차이를 해결했다는 뜻은 아니다. 이 상태 파일과 GPU 프로세스는 수정하지 않았다.
