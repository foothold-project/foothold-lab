> 분류: A/정책학습 · Codex Worker 작업서 (sol) · 노드 1 실제 실행에서 나온 USD 상태 저장 불일치 고치기 (step18)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-17 10:55
> 근거: 노드 1 실제 실행 `s2_stage0_first_collection/attempt5_20261017_1049/` (10/17 10:49:34, 44 초, HOLD) · `NIGHT-PLAN-20261014.md` 「노드 1 지도 점검 결과」 · step12 `usd_isolate_run_v3.py` (SHA `30dc2ea9…`) · step16/17 번들 `usd_isolate_run_v3.py` (SHA `97da75f5…`) · `s2_a34_provenance.py:61`
> 요지: 처음으로 실제 Kit 에서 돌린 A3.4 가 256 걸음을 모두 기록했고 PhysX 검사도 통과했지만, 변환 증거 읽기에서 `ProvenanceHold('usd_isolation_state')` 로 멈췄다. 래퍼가 변환 횟수를 올린 뒤 `isolate_state.json` 을 다시 쓰지 않아 증거 읽기가 `conversions == 1` 을 못 본다. CPU 시험이 이 저장 시점을 재현하지 못했다. 이 결함과 같은 유형이 다른 노드에 있는지까지 닫는다
> 상태: 작업 지시 (CPU 만 · GPU · Isaac 기동 금지 · 승인 json · 동의 파일은 만들지 않는다)

# sol 작업서: USD 상태 저장 불일치 (step18)

## 0. 지킬 것

step17 과 같다. 새 사본 `codexE/s2_step18/` (step17 을 복사해 시작). `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I -B`. 정상 먼저, 변이는 지정 첫 FAIL, 정상 PASS 와 변이 단계 선행 PASS 를 합쳐 쓰지 않는다. 해시 목록 CR 없이, 번들 안에 닫히게. 인도 때 B 전체 회귀(깨끗한 복사본)와 새 시험을 같이 낸다. 설치된 `C:/isaac/...` 파일은 고치지 않는다(읽기만). 팀장은 「이 실험 GPU 실행은 앞으로 매번 묻지 말고 설계대로 진행」이라고 했으므로, 고친 뒤 lead 재실행과 ASTRA 확인이 끝나면 노드 1 을 다시 띄운다.

## 1. 실제 실행에서 나온 사실

- `usd/isolate_state.json`: 쓴 시각 10:49:54, `conversions: 0`, `expect_conversions: "1"`, `blocked: []`, `warnings: []`.
- `usd/assigned.jsonl`: 10:50:02 에 `kind: assigned` 1줄 (`usd_dir` 가 attempt 루트 안, `cfg_class: UnitreeUrdfFileCfg`). 즉 변환은 1번 일어났다.
- `s2_connect_diag_17v.py:500` 가 `usd_evidence()` 를 부르고 `s2_a34_provenance.py:61` 이 `state.get("conversions") != 1` 로 `usd_isolation_state` 를 올린다. 이 시점에 환경은 이미 만들어졌다 (`environment_created=True`).
- 기동기 `s2_attended_launch_a34.py:44` 는 설치본 `ISOLATE = C:/isaac/ext/go2_rl_robotlab/_eval/usd_isolate_run_v3.py` (SHA `30dc2ea9…`, step12 와 같음)를 쓴다. 그 파일에서 `_save_state()` 호출은 패치(191 행) · 차단(100 행) · 경고(114 행) 때뿐이고, 변환 진입(`__init__` 안 `_STATE["conversions"] += 1`)에서는 부르지 않는다. step16/17 번들 래퍼(SHA `97da75f5…`)는 변환 처리 안(182 행)에 `_save_state()` 가 있다.
- 그 밖: `failure.json` 의 `cleanup` 은 `app_closed false`, `provider_closed false` (4차 때도 `pending` 이었음). 정리 관찰자 HOLD 의 이유 둘은 제 폴링 셸 `bash.exe` 였고 관찰자 코드는 이번 일에서 건드리지 않는다.

## 2. 할 일

1. **반례 먼저.** 실제 래퍼 코드(step12 설치본 복사본)를 자식 프로세스로 돌려, 가짜 변환 클래스의 `__init__` 이 한 번 불린 직후 `isolate_state.json` 의 `conversions` 를 읽는다. 지금은 0 이어서 `usd_evidence` 가 `usd_isolation_state` 로 실패하는 것을 첫 FAIL 로 보인다 (실제 `usd_evidence` 함수와 실제 래퍼의 저장 시점을 쓴다. 상태 파일을 시험이 직접 쓰지 않는다).
2. **고치는 방향.** 기동기가 가리키는 래퍼를 번들 안 래퍼(핀한 SHA)로 바꾸는 방안과, 번들 래퍼가 변환 직후 저장하는지(182 행) 확인한 방안 중 `usd_evidence` 요구(`conversions == 1`, `blocked == []`, `warnings == []`, 루트 일치)와 `s2_train_contract` 의 고정 SHA 와 모두 맞는 쪽을 고른다. 설치본은 덮어쓰지 않는다. step16 에서 바뀐 「entry 와 success 별도 계수」가 상태 파일 필드를 바꿨다면 증거 읽기를 그에 맞춘다.
3. **같은 유형 점검.** `isolate_state.json` 을 읽는 모든 곳(`s2_zero_supervisor.py`, `s2_train_launch.py`, 평가기 · 발 광선 · 배관 경로)에서 읽는 시점이 저장 시점보다 앞서는 곳이 있는지 코드로 확인하고 결과를 표로 낸다. 이미 맞는 곳과 고친 곳을 나눈다.
4. **A3.4 전체 경로 시험.** 가짜 변환을 한 번 거친 뒤 `usd_evidence` 가 통과하고, 두 번째 변환은 거절되며, 변환이 0 번이면 실패하는 시험을 실제 래퍼 + 실제 읽기 함수로 낸다.
5. 관찰자 · 정리 · `app_closed false` 는 이번 작업 밖이다. 다만 `app_closed false` 가 네 번 연속 같은 값이라는 사실만 보고서에 한 줄로 적는다(원인 추정 금지).

## 3. 끝나면

`REPORT-s2-step18.md` (반례 첫 FAIL → 고침 → 양성 대조, 변경 파일과 줄, 같은 유형 점검 표, 시험 수 · 변이 CAUGHT/전체, 미확인), `S2-STEP18-SHA256SUMS.txt` (CR 없이, 번들 안에서 닫힘), #550 댓글 초안(미게시). lead 가 재실행한다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
