> 분류: A/정책학습 · ASTRA 의뢰 · 17aj · A3.4 여섯 번째 기동(노드 1 재실행) 허용 여부와 실제 5차 기록 읽기
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-17 11:15
> 근거: 5차 실제 실행 `night-tools-20261013/s2_stage0_first_collection/attempt5_20261017_1049/` · `NIGHT-PLAN-20261014.md` 「노드 1 지도 점검 결과」 · sol step18 (`TASK-codex-worker-s2-step18-usd-state.md` · `REPORT-s2-step18.md` · `S2-STEP18-SHA256SUMS.txt`) · `VERIFY-astra-17ai.md`
> 요지: 노드 1(A3.4)을 팀장 직접 동의 뒤 처음 실제로 돌렸다(10/17 10:49:34, 44 초). 256 걸음 기록과 PhysX 첫 16 걸음 검사는 기대대로였으나 USD 상태 저장 시점 불일치로 `usd_isolation_state` 보류가 났다. sol 이 기동 경로를 상태를 저장하는 번들 래퍼로 고정했다. 같은 설계로 여섯 번째 기동을 해도 되는지 좁게 묻는다
> 상태: 의뢰 (ASTRA 는 평생 탐구한 전문가로 · 비판적 · 냉정 · 현실적으로 · 팀장은 불필요한 지연을 싫어한다. 판정은 허용 · 보류와 이유를 먼저 쓰고 필요 조건만 짧게)

# ASTRA 17aj 의뢰

## 0. 알림

팀장이 10/17 채팅에 직접 쓴 한 줄(원문): 「진행해. NVIDIA 약관에 동의한다. 이 실험 GPU 실행은 앞으로 매번 묻지 말고 설계대로 진행해.」 참석은 문구로 쓰지 않았다(팀장은 채팅에서 실시간 응답 중, lead 가 끝까지 지킴). 이 한 줄이 이후 노드의 동의 인용이다. 무인 실행 · 학습은 아직 허용된 적이 없고 이 의뢰의 질문 밖이다(별도 판정).

## 0b. 시간 순서

물음 1 · 4 · 5 는 5차 원자료만으로 지금 시작할 수 있다. 물음 2 · 3 은 sol step18 최종본(`codexE/s2_step18/`: B 전체 회귀 결과와 `S2-STEP18-SHA256SUMS.txt`)이 아직 오는 중이다. 도착하면 lead 가 NIGHT-PLAN 과 #550 에 알린다. lead 가 지금까지 깨끗한 복사본에서 새 시험 둘을 재실행한 결과: USD 상태 시험 정상 2 PASS · 반례 1 CAUGHT · 대조 2 CAUGHT (설치본 래퍼는 변환 뒤 state=0 · assigned=1 로 5차와 같은 `usd_isolation_state` 재현), 기동 경로 5 PASS · 1 CAUGHT.

## 1. 물음 (좁게)

1. **5차 실제 기록 읽기.** 원자료(`out/physx_first16_check.json` · `capture_raw_before_checks.npz` · `usd/isolate_state.json` · `usd/assigned.jsonl` · `family_observation.json` · `summary.json`)에서 lead 의 읽기에 틀린 곳이 있는지. 특히 (가) PhysX 첫 16 걸음 검사 결과(평평 32/32 맞음 · 높은 곳 32/32 맞음 · 움푹 32/32 빗나감 · 양성 대조 32)의 의미 범위 (나) 보류 원인(설치본 래퍼가 변환 횟수를 올린 뒤 상태를 저장하지 않음)이 맞는지 (다) 정리 관찰자 HOLD 이유 둘이 lead 의 폴링 셸 `bash.exe` 라는 해석이 맞는지, 그렇다면 실행 중 lead 가 지킬 규칙.
2. **sol step18 수정이 충분한지.** 기동 사본 `launch/s2_attended_launch_a34.py` 의 변경은 세 가지다: `ISOLATE` 를 번들 래퍼(SHA `97da75f5…`, `s2_train_contract` 고정 SHA 와 같음)로, `build()` 시작 때 실제 SHA 확인, 시도 번호 6 과 5차 chain 기록. 번들 래퍼의 「conversions = 진입 횟수 · conversion_successes = 성공 횟수」가 A3.4 증거 읽기(`conversions == 1`)와 감독기 읽기에 모두 맞는지. 설치본(`C:/isaac/...`)은 고치지 않았다. 이 구성에서 새로 생길 결함이 있는지.
3. **여섯 번째 기동 허용.** A3.4 를 같은 조건(GPU 0 · 최대 900 초 · 재시도 0 · 참석 단회)으로 한 번 더 띄우는 것을 허용하는지, 조건이 있다면 최소로.
4. **사슬 분기.** USD 보류가 난 뒤 노드 2~4 를 멈추는 17ai 규칙은 지켰다. 노드 3(평가기 update 0)과 노드 4(발 광선)는 새 래퍼를 핀하는 별도 manifest 이고 A3.4 와 같은 결함 경로가 아니다(sol 점검표: 발 광선은 상태 파일을 직접 읽지 않고, 평가기는 자식 종료 뒤 최종 증거만 읽음). GPU 를 놀리지 않기 위해 노드 1 수정 중이나 재실행과 겹치지 않는 범위에서 노드 3 · 4 를 먼저 띄워도 되는지, 안 된다면 규칙의 근거.
5. **내가 놓친 것.** 이번 실제 5차 결과와 step18 보고에서 lead 가 읽지 못한 문제.

## 2. 하지 않을 것

재시도 자동화, 무인 기동, 학습, GPU 1, 정리 관찰자 코드 변경(HOLD 를 PASS 로 바꾸는 일).

## 3. 형식

`VERIFY-astra-17aj.md`. 맨 위에 허용 · 보류 한 줄, 이유, 기동 전 조건, 아래에 물음별 답. 읽지 못한 것은 미확인이라고 적는다.
