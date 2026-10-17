> 분류: A/평가 · Codex Worker 작업서 (sol) · A/B 최종 평가 경로 (step26)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-17 16:58
> 근거: `REPORT-s2-step24.md` 의 「평가 규모와 현재 경로」 표 · `evaluation_criteria_s2_ab.json` · `evaluation_seeds_s2_ab.json` (결과 전 등록, 이 작업이 바꾸지 않는다) · `S2-RESULT-PLAN.md` · 팀장 10/17 「반드시 실험의 결과를 내는 것이 목표」
> 요지: 학습은 A 가 19:07, B 가 21:40 쯤 끝난다. 그때 바로 A/B 의 update 0 · 2000 체크포인트를 60쌍(120 case-arm)으로 평가해 지도 효과 판정까지 내는 경로가 필요하다. 지금 봉인된 평가기는 smoke(4쌍)뿐이다
> 상태: 작업 지시 (CPU 만 · 또 Kit 시험은 lead 가 A→B 틈에 한다 · GPU · Isaac 은 sol 이 띄우지 않는다)

# sol 작업서: 최종 평가 경로 (step26)

## 0. 지킬 것

step24 와 같다(새 사본 `codexE/s2_step26/`, `-I -B` CPU, 정상 먼저, 변이는 지정 첫 FAIL, 해시 목록 CR 없이 번들 안에 닫기, B 전체 회귀). 컨텍스트가 적으면 `HANDOFF-step26-*.md` 로 진행 상태를 먼저 남겨라. 판정 기준과 seed 는 이미 등록한 파일을 읽기만 한다(값을 바꾸거나 새로 만들지 마라).

## 1. 필요한 것 (step24 표의 「필요한 변경」을 닫는다)

1. **완료 체크포인트 입력.** `s2_attended_launch_eval0.py` 계열(또는 새 `s2_attended_launch_evalfull.py`)에 A 와 B 의 update 2000 완료 파일(학습 run 의 `out/checkpoint_002000.pt`)을 SHA 로 봉인해 strict load 하는 인자. update 0 은 기존 생성기를 쓰되 A · B 를 같은 부모 · 같은 cfg(센서 `update_period` 0.0 포함)로. A 의 완료 영수증(`chain.receipt.json`)과 plan 해시를 대조해 다른 run 의 체크포인트가 섞이지 않게.
2. **60쌍 case 계획.** `evaluation_seeds_s2_ab.json` 의 층별 seed 와 `evaluation_criteria_s2_ab.json` 의 layer · 짝 수(gap 20, stepping_stones 20, flat 10, stairs_up 10)로 120 case-arm/체크포인트를 봉인. seed 가 60 개 고유이고 훈련 seed · smoke seed 와 서로소임을 봉인 때 재검사. 기본은 주 명령 fwd10 만(부차 fwd03 은 시간이 남을 때 별도).
3. **감독기와 예산.** full 범위의 시간 · 디스크 예산, 변환 상한(case-arm 당 1 변환이면 120 이상), 실패 영수증, 부분 완료 보존. 실행 단위: 한 프로세스에서 닫기가 되면 한 프로세스, 아니면 case-arm 당 자식. 어느 쪽이든 case-arm 1 개당 평균 시간을 노드 3 smoke 실측(첫 case-arm 125 step, Kit 시작 약 30 s)에서 가정으로 적고 총 시간 추정과 그 불확실성을 보고서에 적어라(미측정은 미측정이라고).
4. **집계와 판정.** `s2_eval_post.aggregate` 에 기준 JSON 의 판정을 연결: 층별 쌍 차(B − A)의 Tango 95% 구간, 목표층(gap, stepping_stones)의 하한 > 0 이고 평균 차 ≥ 10%p 이면 「지도가 좋다」, 아니면 「불명」 또는 「퇴행 감시 위반」. flat 과 stairs_up 은 퇴행 감시. 결측 쌍 처리(유효하지 않은 case-arm 은 쌍 전체 제외 후 개수 보고, 조용히 채우지 않기). update 0 대 2000 의 학습 효과(A 와 B 각각)도 같은 형식으로. `comparison_ready` 는 120/120 유효일 때만 true. 출력은 `S2-AB-RESULT.json` 과 사람이 읽는 표 md.
5. **성공 정의.** 기존 `s2_eval_post` / q_metrics 의 정의(기준선 도달 · 끝까지 생존)를 그대로 쓴다. 새로 만들지 마라. 정의가 코드에서 읽히면 보고서에 그대로 옮겨라.
6. **병행 불가.** 학습과 평가는 공통 USD 잠금 때문에 동시에 못 돈다(step24 확인). 이 작업은 그 잠금을 건드리지 않는다. 평가는 B 학습이 끝난 뒤 순서대로.

## 2. 끝나면

`REPORT-s2-step26.md` (층별 계획 표, 총 시간 추정과 가정, 반례 첫 FAIL, 변이, 미확인, lead 실행 명령 한 줄), `S2-STEP26-SHA256SUMS.txt`, #550 댓글 초안(미게시). 늦어도 B 학습이 끝나는 21:40 전에. 막히면 막힌 줄과 필요한 값을 적어라.
