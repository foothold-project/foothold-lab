> 분류: A/정책학습 · ASTRA 의뢰 17ai · A3.4 뒤에 올 GPU 단회들의 허용 범위: 평가기 Kit 검증, 발 광선 Kit 확인, 탐색 short
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 20:38
> 근거: `VERIFY-astra-17af.md` 2~4절 · `17ag` 1~2, 6절 · `17ah` 전문 · sol step13 (평가기 CPU 코어, `night-tools-20261013/s2_step13/`) · step14 (평가 Kit 연결부, `s2_step14/`) · step15 (`feet_center_any9_v1`, `s2_step15/`) · step9 의 연장 없는 단회 short 요청 · lead 재실행 요약은 각 폴더와 #550
> 요지: A3.4 수집과 배관 재시도는 팀장의 직접 동의 대기이고 CPU 준비는 끝났다. 그 뒤의 단회들(평가기를 Kit 에서 처음 돌리는 학습 0 단회, 발 광선을 Kit 에서 처음 재는 학습 0 단회, 탐색 short)을 어떤 조건으로 허용할 수 있는지, 한 번의 직접 동의로 몇 개까지 이을 수 있는지 미리 닫아 GPU 가 또 판정에 걸려 놀지 않게 한다
> 상태: 의뢰 (GPU 둘 다 계산 0 · 승인 json 없음)

# ASTRA 17ai

비판적이면서도 냉정하고 현실적인 전문가로서 답해 주십시오. 분량 `VERIFY-astra-17ai.md` 한 파일, 첫 줄 한 문장 판정. 코드 수정 · GPU · Isaac · 커밋 금지, em dash 금지. 확인됨 / 추정 / 미확인을 나눠 주세요. 17af · 17ag · 17ah 에서 닫힌 것은 다시 보지 말고 아래만 봐 주세요.

## 사실 (lead 가 재실행으로 확인한 범위)

- step13: 평가기 CPU 코어 (`s2_eval_cases.py` · `s2_eval_driver.py` · `s2_eval_post.py`, 1043 `q_metrics.py` · `paired_ci.py` 바이트 동일 사본). lead 재실행 정상 16 PASS, 변이 14/14 CAUGHT. 결정값(결과 전 고정): 층별 짝 gap 20 · stones 20 · 평지 10 · stairs_up 10, 주 명령 1.0 m/s, 체크포인트 update 0 과 2,000, 결정적 추론, 짝 차이는 Tango 95%.
- step14: 평가 전용 단회 감독 계약(`s2_eval_scope.py` · `s2_eval_supervisor.py`), reset 직전 상태 훅(`s2_eval_pre_reset.py`), case 별 mesh 와 초기 상태 지문, Kit adapter, 평가용 USD 증거(`expect_conversions=any`, 상한 8). lead 재실행 정상 14 PASS, 변이 사전 8/8, step13 회귀 통과, 해시 1259/1259. Kit 안의 reset 직전 갱신 · tile face world 좌표 · RobotLab 물성 API · 여러 case 반복 생성 정리 · 첫 변환 횟수는 미확인.
- step15: `feet_center_any9_v1`(17ag 사양), `reward_variant=none|feet_center_any9_v1`, 36점 하향 광선 질의, 실제 RewardManager 항 영수증, 학습 0 Kit 확인 계약 `S2-FOOT-KIT-CHECK.md`(N ≤ 8, 최대 300 step), 5~10 update 판독 `S2-FOOT-UPDATE-READOUT.md`. lead 재실행 B 51/51 파일, 정상 39개 파일 356 PASS, 변이 단계 CAUGHT 84, 해시 1352/1352. (첫 인도본은 B 의 `test_s2_step5_smoke.py` 를 깨뜨렸고 lead 재실행과 sol 이 각각 잡아 고쳤다.)
- 짧은 A/B(step9): arm 마다 E1 에서 시작해 정확히 2,000 update, 연장 없음, 순차 GPU 0, 첫 10 update 참석 중간 확인. 요청 JSON 은 `exploratory_short=true`, `map_contract_verified=false` 로 봉인돼 있다.
- A3.4 수집 · 배관 재시도는 아직 실행 전이다(팀장 직접 동의 대기). 따라서 지도 계약 증거 일곱 항목(17ah 5절 표)은 A3.4 결과에 달려 있다.

## 질문

1. **평가기 Kit 첫 검증 단회.** 학습 0, update 0 체크포인트(E1 부모를 S2 형식으로 저장한 것)로 gap 2 + stones 2 case 를 평가기에 통과시키는 정보 수집 전용 단회를 허용할 수 있는가. step13 · 14 의 어떤 파일 · 줄을 더 봐야 하는가. 17ah 1.2절의 기동 조건(자산 폐쇄 해시 · USD 격리 · 변환 횟수 의미 · 시간 단계 기록)이 평가 범위에서 달라져야 하는 곳. `expect_conversions=any` 와 상한 8, 관찰 주기 중 상한 검사가 적절한가. 이 단회의 HOLD 분류와 성공 문구.
2. **발 광선 Kit 확인 단회.** 학습 0, N ≤ 8, 최대 300 step 의 단회(`S2-FOOT-KIT-CHECK.md`)가 17ag 2절의 요구를 채우는가, 빠진 것은. 평면 · 직선 절벽 · 대각 절벽 · 유한 깊이 구멍의 기하 허용치(meter)를 lead 가 정하기 전에 ASTRA 가 권하는 값의 근거.
3. **한 번의 직접 동의로 잇기.** A3.4 수집 → 배관 재시도 → (1) → (2) 처럼 네 단회를 이름으로 지정한 한 문장으로 묶어도 되는가, 몇 개까지인가. 각 단회 사이에 필요한 lead 검증 기록과 독립 관찰자 확인, 앞 단회가 어떤 결과일 때 뒤 단회를 막는지. 앞 단회의 코드가 뒤 단회와 다른 번들이라 각각 별도 해시 · 별도 manifest 가 된다는 전제.
4. **탐색 short 의 선행 조건.** (a) A3.4 가 17ah 5절 표의 어느 항목을 닫으면 「범위를 명시한 탐색 short」 로 갈 수 있는지, 닫히지 않으면 어떤 다른 증거로 대체 가능한지(결과를 보기 전에 정해야 하는 것) (b) 첫 10 update 참석 중간 확인에서 보는 것과 중단 기준 (c) 두 arm 순차의 시간 상한, 10/17 12:00 마감 전 N=1,024 실측으로 U 를 줄이는 규칙(양쪽 같은 U) (d) 학습 후 체크포인트를 평가기로 읽을 때 필요한 것(step13 · 14 가 Kit 에서 검증된 뒤라는 전제) (e) 발 보상 열(A1 · B1)은 이 short 가 끝난 뒤 별도 단회로 하는 것이 맞는지.
5. **지금 ASTRA 가 보기에 가장 막힐 곳.** 위 단회들 중 실제 Kit 에서 처음 열릴 때 막힐 가능성이 가장 높은 지점 셋과, lead 가 미리 CPU 로 줄일 수 있는 것.

## 하지 말 것

- 무인, 자동 재시도, 후속 학습, 200 update smoke 허용으로 읽히는 표현. 17z 무인 보류는 유지.
- 17af 의 2,000 update 계약 · 17ag 사양 · 17ah 조건을 다시 심사하지 말 것.
