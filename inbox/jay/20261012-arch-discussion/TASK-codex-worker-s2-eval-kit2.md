> 분류: A/정책학습 · Codex Worker 작업서 (sol) · S2 평가기의 Kit 연결부 (step14, CPU 부분)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 19:12
> 근거: `REPORT-s2-step13.md` 3절(남은 미확인 셋: 평가 전용 scope/allowlist · 종료 전 마지막 물리 상태 훅 · case 별 mesh 와 초기 상태 지문 adapter) · `S2-EVAL-KIT-SMOKE.md` · `VERIFY-astra-17af.md` 4절 5항 · `VERIFY-astra-17ah.md` 1.2절(USD 격리 · 자산 폐쇄 해시)
> 요지: 평가기 CPU 코어는 있다. Kit 에서 실제로 돌리려면 셋이 더 필요하다. 이번 작업은 그 셋의 설계와 CPU 에서 닫을 수 있는 부분, 그리고 Kit 첫 검증 단회(학습 0)의 봉인 가능한 계약이다
> 상태: 작업 지시 (step13 확정 뒤 발송 · CPU 만 · GPU · Isaac 기동 금지 · 승인 json 은 만들지 않는다)

# sol 작업서: 평가기 Kit 연결부 (step14)

## 0. lead 결정값 (결과를 보기 전에 고정, 이후 바꾸지 않는다)

- 층별 case 수(짝): gap 20 · stones 20 · 평지 10 · stairs_up 10. 첫 Kit 검증 단회(smoke): gap 2 · stones 2 · 대조 0.
- 명령: 주 평가 `fwd10`(1.0 m/s), 시간이 허락하면 같은 case 에서 `fwd03`(0.3 m/s)를 보조로(사전에 이 분기를 표에 봉인; 결과를 본 뒤 고르지 않는다).
- 지형 소스: 1043 의 `unseen10` d0.5 gap · stepping_stones 와 같은 생성 규칙 · 기본 마찰(1043 계약의 값). 학습 seed 11 · 7 및 이후 학습 seed 와 서로소인 평가 seed.
- 체크포인트: update 0 과 update 2,000, 각각 arm A / B. 추론은 결정적 `act_inference`.
- 짝 차이 구간: step13 의 Tango 95%(한계를 보고서에 이미 적음).

## 1. 만들 것

1. **평가 전용 감독기 범위.** A3.4 의 `s2_zero_supervisor.py:80,95~105`(진단 자식 경로와 `--steps 256` 고정)와 `s2_stage0_contract_a2.py:91` 은 평가기를 그대로 넣지 못한다. 평가 목적의 별도 `purpose` / scope 와 allowlist(자식 경로 = `s2_eval_driver.py` Kit 진입, 고정 argv, 출력 이름과 해시, 마감, 정보 전용 영수증)를 가진 감독기 계약을 새로 정의한다. lease · OS 변환 잠금 · USD 격리 · 가족 정리 · 독립 관찰자 · 자산 폐쇄 해시(ASTRA 17ah 1.2절)는 A3.4 것을 같은 방식으로 쓴다. 기존 A3.4 코드 바이트는 바꾸지 않는다(새 파일로).
2. **종료 전 마지막 물리 상태 훅.** `IsaacS2Env.step()`(step 에서 자동 reset 이 일어나 관측은 reset 뒤 값)에서 case 별로 reset 직전의 root pose · 접촉 · 높이를 평가기가 읽을 수 있게 하는 평가 전용 래퍼. 학습 경로(`IsaacS2Env`)는 바꾸지 않고 평가용 서브클래스 / 래퍼로. Isaac Lab 의 reset 순서에서 어느 지점을 가로채는지 소스 줄로 근거를 적는다. 가짜 환경 시험: reset 직전 상태와 직후 상태가 섞이지 않는지, 한 env 의 reset 이 다른 env 의 기록을 바꾸지 않는지.
3. **case 별 mesh 와 초기 상태 지문 adapter.** 한 case 를 한 env 에 배정하는 방법(1043 평가기 / A3 의 TerrainGenerator curriculum 열 배정 방식을 읽고 재사용), env 별 지형 sub-mesh 해시, 초기 root pose · 관절 · 속도 · 명령 · 마찰 · dt 지문. 두 arm 이 같은 case 에서 같은 지문을 받는지 비교하는 코드.
4. **Kit 첫 검증 단회 계약 갱신** (`S2-EVAL-KIT-SMOKE.md`): 위 셋을 포함한 manifest 필드, 필요한 CPU 증거 목록, 이 단회가 실패했을 때 어느 HOLD 로 분류하는지.

## 2. 지킬 것 · 끝나면

step13 과 같다. 새 사본 `codexE/s2_step14/`, 해시 목록 CR 없이, 정상 PASS 와 변이 단계 선행 PASS 를 합쳐 쓰지 않는다. `REPORT-s2-step14.md` (코드 위치 · 시험 수 · 변이 CAUGHT/전체 · 첫 실패 · 미확인), `S2-STEP14-SHA256SUMS.txt`. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
