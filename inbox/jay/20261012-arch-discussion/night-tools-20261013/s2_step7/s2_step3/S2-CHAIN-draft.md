> 분류: A/정책학습 · S2 단계별 사슬 초안
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-s2-isaac-entry.md · REPORT-s2-step2.md · ce12/run_dump.py · isaac_slot_v3.py
> 요지: 접속 확인 → smoke A/B → 짧은 A/B를 단회 claim과 자동 보류 관문으로 연결한다
> 상태: 초안 · UNDECIDED · 실행 승인 아님

# S2 단계별 사슬 초안

`s2_chain_manifest.json`의 `null`은 미결정이며 기본값이 아니다. 승인 전에는 `approval.status=UNDECIDED`라 `s2_stage_gate.py`가 보류한다. 완료 자료를 보고 값을 바꿔 다음 단계로 넘기는 일을 막기 위해 입력과 관문 임계값을 사전에 함께 고정해야 한다.

| 단계 | 입력과 실행 | 합격 때만 넘기는 것 | 보류 조건 |
|---|---|---|---|
| 0 접속 확인 | 부모·환경·코드 해시, 네 지형과 회전 평지, 재시작 포함 원시 RayCaster. 예산: launch·wall·진단 step | `capture.npz`, `meta.json`, checker 결과의 파일 해시와 단계 판정 SHA | 비영 종료, Traceback, 누락·해시 불일치, 원점/리셋 센서 증거 부족, 불량 패킷, 187 순서·yaw·height·offset·평지·단차·gap·stones 불합격 |
| 1 smoke | 0의 PASS 판정 SHA와 같은 부모·환경·코드·A/B 규칙. A 다음 B를 한 번에 하나씩, 각 수백 update는 제안이며 확정 전 | 두 군 결과·로그·checkpoint 해시, 시간당 iteration·장치 peak/최저 여유, 관문 판정 SHA | 비영 종료, Traceback, NaN/고장·폐기, 지도 시점, PPO step 수, 미확인 조우·GPU 지표, STOP·마감·예산 초과 |
| 2 짧은 A/B | 1의 PASS 판정 SHA, 동결된 길이·환경 수·seed·지형·정책·평가 규칙 | 두 군 결과와 별도 평가 의뢰용 묶음 | smoke와 같은 자동 보류, 한 군만 이어받기, 미등록 재시작, 예산 초과 |

각 단계 record는 `stage`, 고유 `attempt`, 직전 PASS 판정 SHA, launch 수·wall, 종료 코드·Traceback, 부모/코드/환경 지문, 산출물 경로와 SHA256을 담는다. `s2_stage_gate.verdict`는 조건을 읽어 `PASS` 또는 이유가 담긴 `HOLD`를 반환하고, PASS에서만 다음 단계 인수를 낸다. `claim_once`는 단계와 attempt별 디렉터리 생성으로 재사용을 거절한다. 실제 GPU의 공통 lease와는 별개이므로 통합 검증 전에는 기동 금지다.

| 사슬 전체 승인 뒤 불변인 것 | 왜 |
|---|---|
| 부모 checkpoint와 agent YAML 해시, step2·step3 코드 해시, 환경 설정 해시 | 시작 상태와 지도·PPO 규칙을 같게 묶음 |
| A/B encoder_mode, schedule의 W/r, map seed, 학습 seed·명령·보상·지형 비율 | 한 변인만 지도 정보로 유지 |
| 세 단계 launch·wall·update·환경 수·rollout·epoch·minibatch 예산 | 결과 후 예산 확대 방지 |
| 접속 불합격 임계값, 고장·NaN·조우·VRAM·step 수 관문 | 사후 통과선 변경 방지 |
| GPU 번호, 공유 변환 lock·registry·공통 lease, STOP·마감, 출력 루트 | 실행 충돌·중단 경계 고정 |
| checkpoint 선택·독립 평가 seed·칸·명령, 단계 재시작 규약 | smoke와 최종 평가 분리 |

현재 연결 진단의 실제 env origin, RayCaster 센서 시각표, 드라이버 판은 승인된 도구에서 읽는 호출이 확인되지 않았다. 실제 학습 환경 state 복원과 지형 조우 이벤트도 마찬가지다. 코드는 이를 꾸며 넣지 않고 HOLD로 남긴다. 이 호출과 공통 lease를 ASTRA가 검토하기 전에는 0단계도 합격 판정할 수 없다. `night_s2_chain_draft.sh`는 시작 즉시 exit 99인 비실행 초안이다.
