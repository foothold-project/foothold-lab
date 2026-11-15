고칠 것: 승인값과 지문 누락 수정은 확인됐지만, 자식 PID 재사용에 따른 무관 프로세스 종료와 불명 부모의 후손을 놓치는 조기 lease 해제를 재현했으므로 현재 후보의 진단 기동과 승인 JSON 발급을 보류한다.
> 분류: A/평가 · ASTRA 17u 독립 검증
> 작성: 오흥재 (ASTRA 검증 세션) · 2026-10-15
> 근거: TASK-astra-17u 전문 · cmdr1043_eval_cand_17t 고정 37파일 · 등록 입력 38개 · CPU 독립 재실행 · 실제 과거 결과와 운영 실행기 소스
> 요지: 이전 반례 세 건의 지정 경로는 닫혔으나 종료 소유권의 다른 두 경계가 남았고 전체 실행 lease의 운영 참여도 확인되지 않았다
> 상태: 검증 완료 · 진단 보류 · 승인 JSON 없음

# ASTRA 17u

M은 s1043_manifest.py, D는 cmdr_eval_driver_s1043.py다. 줄 번호는 의뢰의 cmdr1043_eval_cand_17t 사본 기준이다. CPU 시험은 별도 Temp에서 수행했다. 기존 코드·원자료·운영 slot·동결 폴더를 변경하지 않았고 GPU·Isaac·운영 프로세스 종료·커밋은 하지 않았다. 이 저장소의 신규 산출물은 이 파일 하나다.

## 1. 이전 세 결함과 남은 종료 소유권 결함

**판정: 지정된 이전 반례는 막혔다. 그러나 부모 생성 시각 확인만으로 종료 대상 소유권이 증명되지는 않는다. 기동을 막는 두 반례가 남는다.**

**근거 · 확인됨:**

- 이전 100→110 관찰 후 110 재사용·새 자식 300 반례는 이제 300을 known에 등록하지 않고 신호도 보내지 않는다. 부모 소멸·자식 접근 거부는 보류한다. 정상 부모 대조군은 관찰된 자식을 정리한다.
- **P1-1 · D:722~749, 788~797:** `_ppid_map()`은 스냅샷이고 뒤의 `Process(pid).create_time()`은 다른 시각의 조회다. 정상 부모 110은 살아 있게 두고, 스냅샷에 있던 그 자식 300이 사라진 뒤 무관한 부모 900의 프로세스가 PID 300을 재사용하게 했다. 새 생성 시각 9는 부모 110의 시각 2보다 늦으므로 등록된다. STOP에서 **무관한 300에 kill이 호출됐다.** 자식의 현재 부모를 조회하지도 않았다. 종료 직전 새 300의 생성 시각이 등록값과 일치해도 그 등록 자체가 잘못됐다. 이전 반례의 부모 재사용을 막은 것이 이 자식 재사용까지 막았다는 뜻은 아니다.
- **P1-2 · D:715~724, 750~781 및 1002~1006:** 110의 생성 시각을 읽지 못해 unknown에 둔 상태에서, 다음 스냅샷에 300→110을 보이게 했다. 110이 known에 없으므로 300은 unknown으로도 전파되지 않는다. 루트와 110이 자연 종료하면 unknown 110이 제거되고 **300은 살아 있는데 wait_child_tree가 rc 0으로 반환했다.** 자식이 없는 자연 종료 대조군도 정상 반환하며, 110이 계속 접근 불명인 대조군은 계속 보류한다. 따라서 단순히 영원한 보류를 고친 것이 아니라, 후손을 놓친 조기 해제 경로도 만들었다. guarded의 finally 재감시도 known/unknown을 새로 만들기 때문에 이 누락을 복구하지 못한다.

위 신호는 후보 함수 본문에 가짜 psutil 프로세스 표와 시계만 넣어 관찰한 호출이다. 실제 무관 프로세스를 종료하지 않았다. 정상·기존 반례·새 반례의 동일 함수 대조이며, 실제 OS에서 PID 재사용을 유도한 시험은 아니다.

불명 PID가 계속 접근 불가하거나 같은 숫자의 무관 프로세스로 바뀌어 살아 있으면 무기한 보류도 가능하다. zombie/소멸 확인으로 PID 하나를 지우는 것은 후손 전체의 종료 증명이 아니다. 관찰 전에 재부모화된 자식은 더 근본적으로 빠진다. **공유 워크스테이션의 자동 종료를 허용하는 진단에서는 이 위험을 수용하지 않는다.** Windows Job Object 등 생성부터 종료까지 묶는 OS 소유 경계, 또는 동등한 소유·잔존 증명이 필요하다. 특정 API 이름만 붙이면 통과하는 것은 아니다. 시작 전에 편입, 후손의 경계 이탈 방지, 전체 종료 확인, 편입 실패 시 기동 거절을 함께 시험해야 한다. 현재 조회를 한 번 더 추가하는 것만으로 원자적 소유권이 생기지는 않는다.

**승인값 수정 · 확인됨:** M:277~296은 이름 길이·문자·대소문자 예약어, 단회 범위, 비교 규칙, 종료 정책 구조를 검사한다. D:1629~1635,1669~1672,1734는 승인된 동일 규칙을 적용한다. 제공 30개 거절 시험을 재실행했고, 별도 require_files=True 검사에서도 정상 통과, UNDECIDED·임의 규칙·false·null·list·dict·혼합 대소문자 예약어·51자 log·NaN/무한대/bool 유예는 거절됐다. 새 여섯 필드의 승인 후 변조는 모두 approval contract mismatch였다. B 22키와 외부 digest 결박은 유지된다. 이는 CPU 승인 fixture 시험이며 운영 승인 발급이 아니다.

**필수 지문 수정 · 확인됨:** D:1555~1606의 실제 validate/fingerprint/record를 타는 제공 시험을 재실행했다. 실제 원본 결과의 바이트 복사본에서 정상 valid → env_origins.npy만 누락하면 validate는 통과하지만 record는 held → 복구 valid였다. orig_repeat도 같은 누락을 held로 내렸다. main_diagnostic의 합성 시험에서는 누락이 held_incomplete로 이어져 완료를 막았다. 이 지정 결함은 닫혔다.

**남길 미확인:** 실제 Kit 생명주기의 소유 경계, OS PID 재사용 경주, 소유권 수정 후 전체 후손 종료 보장. 현 감시기의 시간상한은 불명 자식까지 반드시 시간 안에 종료한다는 보장이 아니다.

## 2. 시험의 분모와 신뢰 범위

**판정: 15개 재실행 통과와 코드 변이 9건의 검출은 재현됐다. 전체 기동 안전성이나 GPU 연결의 통과로 확대하면 틀리다.**

**근거 · 확인됨:** 고정 37파일과 등록 입력 38개가 일치했다. 작업자 전체 목록 SHA256은 dfdb76470970d22ce821aeebffe9d640d975d0c9e96979b3ea94f083c8c353e0이며 현재 파일 165/165도 일치했다. ASTRA는 isaac311-moects Python, -B, CUDA_VISIBLE_DEVICES=-1로 예정 15개를 전부 실행했다. exit 0은 15개, 미실행·skip·hold는 0개, 하위 스크립트 시간 합계는 **109.13초**다. 내부 변이 재실행 시간은 이미 포함돼 있다. lead의 사본 로그·summary와 해당 want도 대조했다. 과거 멈춘 첫 실행은 별도 실패 기록이지 이번 성공 분모의 일부가 아니다.

입력 변조는 로그의 want/got 12건이다. 코드 변이는 생성된 소스와 정상 소스의 실제 diff·해시·동일 시험의 정상/변이 로그까지 직접 대조했다. 9건 모두 한 지점 변경, 정상 exit 0, 변이 exit 1, 첫 FAIL 및 AssertionError가 지정 want와 일치했다.

| 코드 변이 | 실제 의미 |
|---|---|
| original_field | 누락을 허용해야 할 원본까지 거절하는 회귀 |
| wall_enforcement | 활성 자식의 실행 시간상한 비활성화 |
| approval_ledger | 기존 claim을 허용해 단회 시작 제한 무력화 |
| retry_zero | 0 retry를 거절하도록 되돌리는 회귀 |
| byte_only_reason | JSON byte-only 차이를 의미 차이로 오표기 |
| common_allowlist | source_eval 내부 경로의 정확한 key/path 허용 조건 제거 |
| parent_identity | 새 자식 등록 시 부모 식별 실패 거절 조건 비활성화 |
| comparison_rule_gate | 문자열 타입 검사는 남기고 지원 규칙 집합 검사만 비활성화 |
| fingerprint_hold | 필수 증거 오류·누락의 valid→held 전환 비활성화 |

따라서 **입력 12건 · 기존 코드 변이 6건 · 신규 코드 변이 3건**이다. 17s code_mutants.json의 키 `code_check_disabled: 6`은 여전히 의미가 부정확하다. original_field·retry_zero는 과도한 거절 회귀, byte_only_reason은 보고 회귀다. 새 3건도 전체 함수 삭제가 아니라 표의 해당 조건을 끈 것이다.

가상화 범위는 유지된다. test_17s_original·test_17t_fingerprint는 실제 원본 파일과 validate/fingerprint를 쓰지만 slot·log_done·usd_check·py_traceback을 대체한다. test_17r_e의 validate/fingerprint는 성공 함수다. test_17s_runtime은 일부 gate/preflight를 대체한다. test_17t_diagnostic_contract의 지문·실행·검증은 합성 자료다. test_17t_ownership은 가짜 프로세스 표이며 1절의 새 두 경주를 포함하지 않는다.

**남길 미확인:** 실제 GPU slot→guard→isolate→Kit 연결, 물리 버퍼·peak, 실제 참가 실행기의 공통 lease, 실제 경주 빈도. 시험 통과가 없는 소유 경계를 만들어 주지는 않는다. 159개 백업의 보존 당시 동일성은 이번에 재측정하지 않았다.

## 3. 진단 계약과 결과 표현

**판정: 공통 지문·세 비교·비용 분리는 개선됐다. 고정 소스의 의도된 버퍼 차이는 통과하지만 eval_changes 전체 제외는 너무 넓고, 일부 보고 명칭은 보완해야 한다.**

**근거 · 확인됨:** D:1640~1661은 pairing 두 종류, 지형 메시·origins, env origins, N/T/cells, obs_shapes, UUID, layout, traj0의 12개 키를 비교한다. 실제 과거 `cq_test_8d384fcb_g0t141025p134176_ka_orig`, `ka_copy`, `ka_copy_default_buffers`를 CPU로 읽어 같은 함수에 넣었다. 공통 지문은 equal, orig 대 small/default의 의미·JSON 바이트·traj 바이트도 모두 equal이었다. 실제 형태의 동일 지문 대조군은 통과하고 env_origins만 바꾼 반례는 해당 키 mismatch였다. 이는 과거 자료에서의 오탐 확인이지 현재 후보 GPU 진단을 대신한 것이 아니다.

q_eval.py:203~273과 q_eval_cmdr.py:226~296의 changes 생성 코드를 대조했다. 현재 동일 flat 조건에서 의도된 변화는 기본 버퍼 run의 `physx buffers reduced ...` 항목 제외다. **eval_changes 전체를 ‘의도한 차이’라고 쓰는 것은 부정확하다.** reset·push·curriculum·episode length까지 들어 있다. 실제 형태의 지문에서 이 목록만 임의 reset/push 변경으로 바꿔도 현재 공통 비교는 equal이었다. 등록 소스·argv 고정과 별개로 이 비교기의 보증 공백이다. 버퍼 항목만 정규화하고 나머지는 비교하거나, 현 제외 범위를 명시적으로 한계로 남겨야 한다. evaluator_source는 각 실행의 등록 해시로, 버퍼 플래그는 실행별 승인값으로 따로 확인해야 한다.

공통 지문과 의미/JSON/traj 결과는 별도 칸에 남는다. 공통 불일치면 held_common_fingerprint, 실행·지문 불완전은 held_incomplete다. 승인된 반복이 같게 나와도 처음 불일치를 완료로 덮지 않는다. 세 별도 q 실행과 A_started=false가 유지되며 A 자동 진행 경로는 없다. JSON byte-only나 traj 파일 바이트 차이만으로 물리 비결정성을 확정하면 안 된다.

비용은 마지막 try, 모든 try 합, orig에 배분한 초기 준비, non_try, run 전체, attempt 전체를 구분한다. **non_try에는 배분된 초기 준비도 포함**되므로 startup을 다시 더하면 중복이다. run 사이 publish·비교 시간 등은 run 합계에 전부 들어가지 않으므로 전체 비용의 기준은 attempt_total_wall_s다. 기본 run이 미완료인데 repeat_status=repeat_not_needed, repeat_reason=base_incomplete가 함께 나오는 표기는 ‘불필요 판정’이 아니라 ‘판정 전 미실행’으로 고치는 편이 정직하다. 장치 전체 peak는 작업 전용 VRAM이 아니다.

**남길 미확인:** 새 후보의 실제 세 실행·버퍼 효과·재현성·비용. 지문 12키의 일치는 전체 물리 세계 동등성의 증명이 아니며 현재 비교 목록 밖 상태까지 보증하지 않는다.

## 4. 승인 B와 실제 결정 순서

**판정: 현 바이트는 제한된 진단 기술 승인 대상으로도 불충분하다. 팀장 값만 채우면 되는 상태가 아니다. 1절 소유권 수정과 5절 운영 참여 확인 뒤 다시 판단해야 한다.**

**근거 · 확인됨:** 승인 B는 M:86~105의 22키다. 아래는 책임·허용 범위이며 승인 자체가 아니다. 팀장 결정은 의뢰에도 전부 UNDECIDED라고 명시돼 있다.

| B 필드 | 책임과 허용 범위 |
|---|---|
| experiment | lead가 등록 실험 ID를 그대로 사용, ASTRA가 계약 일치 확인 |
| train_seed | 1043 고정, 다른 seed로 이 승인 재사용 금지 |
| contract_sha256 | lead가 최종 canonical contract 해시 산출, ASTRA 재계산 |
| stage | 팀장 진단 범위 결정, 이번에는 diagnostic만 |
| approval_id | lead가 새 미사용 ID 제안, 영숫자·_·- 1~64자, 예약어 금지 |
| attempt | lead가 새 실행 ID 제안, 같은 문자·길이 제한 |
| log_name | lead가 충돌 없는 이름 확인, 같은 문자로 1~50자 |
| restart_scope | 팀장 단회 정책 채택, 지원값 single_start_no_reuse만 |
| termination_policy | 팀장 위험 결정, 정확히 terminate_grace_s 양의 유한 수와 partial_result=held, 권고 5~10초 |
| comparison_pass_rule | ASTRA 기술 기준 제시·팀장 채택, semantic_and_json_bytes_and_traj_bytes만 |
| candidate_hashes | lead가 M·D·비교기·post·frozen 실행기 다섯 SHA256 산출, ASTRA 바이트 확인 |
| comparison_report_sha256 | lead가 최종 계약의 SAME 보고 바이트 고정, ASTRA 결과·해시 확인 |
| gpu_index | 팀장이 물리 0 또는 1 배정, lead가 현 장치와 대조 |
| gpu_uuid | lead 실측 UUID, 지정 index와 일치해야 함 |
| CUDA_VISIBLE_DEVICES | 지정 물리 index 문자열, 자식 내부 논리 CUDA는 0 |
| diagnostic_repeat_original | 팀장 bool 결정, 첫 진단 권고 false, true면 추가 launch 예산 필요 |
| deadline_epoch | 팀장 작업창의 구체 미래 시각, lead 변환·ASTRA 검토. 새 자식 시작 마감 |
| risk_limit | 팀장 launch·retry·전체 wall 결정. 정확한 세 키, 정수이며 retry만 0 허용 |
| convert_lock | lead가 전체 참가자의 실제 canonical 파일과 인자를 확인, ASTRA 경합 증거 확인 |
| run_lease | lead가 전체 실행 수명 동안 공유됨을 증명, ASTRA 확인. 새 파일 하나 생성으로 충족 불가 |
| registry | lead가 v3 참가자의 canonical registry 인자를 확인, ASTRA 버전 혼용 여부 확인 |
| python | lead가 실제 실행 해석기 절대경로·버전·모듈 판을 확인, ASTRA 고정값과 대조 |

**17t 권고값은 출발안으로 그대로 채택할 수 있으나 현재 기동 허용은 아니다.** 첫 묶음 launch 3, retry 0, repeat false, wall 1200~1800초, 유예 5~10초, 단회 시작, 엄격한 세 비교, GPU 하나·20~30분 작업창이다. 팀장은 범위가 아니라 정확한 초·시각·GPU를 결정해야 한다. 반복까지 원하면 4 launch/true를 사전에 선택한다. wall 안에는 준비·대기도 들어가며 불명 자식 수습의 완료 시각까지 보장하지 않는다. Windows terminate 유예를 정상 저장 종료 보장으로 설명하지 않는다.

팀장에게 남는 결정은 **실행 GPU와 다른 Isaac 기동을 막을 창, 구체 마감·wall, launch/retry/반복, 소유권 확인된 프로세스의 강제 종료·부분 결과 보류·실패 뒤 새 승인 정책, 통과선 채택**이다. 이름·해시·UUID를 팀장에게 계산시키지 않는다.

lead 측정 및 발급 순서는 다음과 같다.

1. 팀장 결정 초안을 받고, 참가 실행기·예약 기동·canonical lock/registry/lease를 먼저 조사한다. 이 조사와 runtime·등록 입력 38개 대조는 소유권 수정 검증과 병행 가능하다.
2. 소유권 수정 판 확정 및 해당 정상·경주 반례 검증 후 배치한다. Python/NumPy/torch/Isaac 판, 실행 파일·소스 경로, 실제 UUID/index와 매핑, 여유·동시 프로세스, 부모·양 군 완료/guard/slot/stamp 및 38개 바이트를 확인한다. 기동 직전 변할 수 있는 장치값은 다시 잰다.
3. 배치 경로·참가 근거·runtime·입력·팀장 결정을 채운 contract를 동결하고 canonical SHA256을 산출한다. 실제 등록 번들 사본의 SAME/변조 거절 대조 후 최종 SAME 보고를 동결한다.
4. 실제 배치된 코드 다섯 해시와 비교 보고 해시를 B에 결박한다. 코드가 바뀌면 관련 검증·해시를 다시 해야 한다. B 22키, 미사용 claim, 최종 결정·운영 근거를 ASTRA가 검토한다.
5. 그때 승인 가능할 경우에만 reviewed=B인 승인 파일을 발급하고 **그 파일의 바이트 SHA256을 외부 --approved_digest와 execution.approval_sha256에 함께 지정**한다. manifest 바이트도 최종 기록한다. 승인 후 값 변경·claim 삭제·같은 승인 재기동은 금지다.

**남길 미확인:** 실제 팀장 결정, 소유권 수정, 공유 lease의 운영 구현·배치, 실측 GPU/여유/runtime. 현재 bool 확인란을 true로 쓰거나 CPU fixture 값을 복사해 이 공백을 채울 수 없다.

## 5. 실제 공통 경로와 기동 전후 관문

**판정: 변환 lock·registry는 재사용 후보가 확인됐지만 전체 실행 lease는 조사한 참가자에 구현돼 있지 않다. ‘기존 공통 lease를 재사용하면 된다’는 17t의 일반 제안을 현 운영 사실로 읽으면 틀리다.**

**근거 · 확인됨:** 실제 슬롯 코드는 `_eval/isaac_slot_v3.py`다. 의뢰의 `_eval/slot/isaac_slot_v3.py`는 없다. 이하 `_eval`은 C:/isaac/ext/go2_rl_robotlab/_eval이다.

| 항목·참가자 | 소스에서 확인한 실제 기본값·인자 |
|---|---|
| convert_lock 후보 | `_eval/slot/isaac_convert.lock` |
| registry 후보 | `_eval/slot/isaac_usd_registry_v3.json`을 명시적으로 전달 |
| 슬롯 기본값 주의 | isaac_slot_v3.py:420~421의 registry 기본값은 아직 구형 isaac_usd_registry.json. v3라는 파일명만 믿고 --registry를 생략하면 안 됨 |
| 미경험 v6 | unseen_driver_cmdr_v6.py:54~57,262에서 SLOT/isaac_convert.lock과 v3 registry 전달. SLOT 환경 override 확인 필요 |
| CE12 | ce12/run_dump.py:64~65,266에서 BASE/slot의 같은 두 파일 전달. BASE override 확인 필요 |
| RAND | rand_scenes/rand_lib.py:34,884~891에서 EVAL/slot의 같은 두 파일 전달 |
| 구형 v3.7 평가 | cmdr_eval_driver_v37.py:175,619~624는 `_eval/out/isaac_convert.lock`. 위 경로와 다름 |
| 전체 run_lease | 조사한 위 실행기들과 슬롯에는 후보 D의 전체 실행 lease 참여가 없음. `_eval/slot/isaac_run.lock`은 새 공통화 설계 후보일 뿐 검증된 기존 파일이 아님 |

슬롯은 scene_built 뒤 변환 lock을 풀고 나머지 실행을 기다린다(isaac_slot_v3.py:476~505). 따라서 변환 lock을 전체 run lease로 간주할 수 없다. registry 갱신은 registry.lock과 고유 임시 파일도 쓰므로 운영 쓰기 범위 설명에는 그 부수 파일을 포함해야 한다. allowlist의 세 키를 source_eval 전체 쓰기 허가로 넓히라는 뜻은 아니다.

현재 확인은 **소스 기본값·인자**다. 실제 실행 argv·환경 override·경로 별칭과 향후 예약 기동까지 확인했다는 뜻은 아니다. 전체 참가자를 공통 실행 관문에 연결하거나, 승인된 전용 창의 모든 실행 입구를 통제하고 그 근거를 남겨야 한다. 단순 ‘지금 GPU가 빈다’와 참가 확인 bool은 실행 중 충돌 방지가 아니다. 운영 확인 범위를 정하지 않은 채 모든 과거 도구가 참여한다고 쓰지 않는다.

배치 후 CPU에서는 정확한 allowlist/별칭, 실행 argv, 입력·코드 해시, 미결정 값 거절, 실제 38개 번들 SAME/변조 거절, 단회 claim 경쟁, **수정된 소유 경계의 정상·재사용·부모 소멸·접근 불가·잔존 후손**, 공통 lease 경합을 확인한다. 이 재검에서 운영 lock·registry에 시험 데이터를 쓰지 않는다.

첫 자식 직전에는 승인 digest·바이트·미사용 claim·STOP·마감·UUID/index/논리 CUDA 0·최저 여유 4096 MiB·동시 Isaac와 예약 기동·공통 lease 참여를 다시 확인한다. 입력 변화, 소유권 불명, STOP/시간/launch 한도, guard 중단, USD 참조·충돌·traceback, 지문 불완전·비교 불일치는 보류다. 소유권 불명에는 타 프로세스 신호를 보내지 않고 운영자에게 인계하며, 잔존 여부를 증명하기 전 다음 run이나 lease 해제로 넘기지 않는다.

보고 문구는 **‘예정 3회 중 실행/유효/보류/실패/미실행, 반복 여부와 사유, A 0회, 전체/try/준비 시간, 장치 전체 peak·최저 여유, 의미/JSON/traj/공통 지문 결과’**로 한다. 진단 한 묶음은 실측 전 10~20분 계획값, 작업창 20~30분이다. 과거 run 평균을 새 후보의 실측으로 전하지 않는다.

A는 별도 승인이다. 현재 D tests의 시작 시험 8회와 A 45회로 최소 53 launch, 조건부 원본 반복 한 번까지 54다. 진단 3회를 했다고 A 시작 시험 8회를 빼지 않는다. retry 추가 예산, A 시간창·GPU·새 B/claim, 과학 기준을 별도 검토한다. A의 세 칸 모두 95% 구간 하한 >0 및 동일 가중 평균 ≥10%p 기준은 유지하며 목표 세 칸을 96칸이나 22,000 checkpoint 전체로 확대하지 않는다.

**남길 미확인:** 실제 전체 참가 입구와 배정된 운영 창, OS 소유 경계·배치 후 CPU 결과, 현재 GPU·peak·실제 진단 및 A 비용. 본 감사에서는 운영 경로를 바꾸거나 잠금을 잡지 않았다.

## 6. 남은 시간과 재현 자료

**판정: 작업자의 24분 수정과 약 110초 시험에서 ‘이제 즉시 진단 가능’을 도출할 수 없다. 소유 경계와 실제 공통 lease 참여가 병목이다.**

**추정:** 소유 경계 수정·정상 및 경주 시험 1~3시간, 독립 영향 재검 0.5~1시간, 참가 실행 관문·배치·동결 0.5~1시간으로 **진단 시작까지 2~5시간과 팀장 결정 대기**를 계획 참고값으로 둔다. OS 편입과 Kit의 호환 문제나 여러 기동 입구의 변경이 필요하면 더 걸릴 수 있다. 완료 시각을 보장하는 견적은 아니다. 이전 1.5~3.5시간에서 이미 쓴 24분을 차감하는 방식은 맞지 않다.

팀장 GPU/창/위험 결정, lead의 참가자·runtime·입력 조사는 수정과 병행할 수 있다. 최종 배치 해시·contract·SAME 보고·B·승인 발급은 검증된 바이트 뒤의 순서를 지켜야 한다. 수정 중인 판으로 먼저 기동하고 나중에 승인받는 병행은 하지 않는다. 검토는 새 두 반례와 수정 영향에 한정하되, 다른 경로가 같은 종료 함수를 쓰는지는 함께 본다.

**확인됨 · 재현 자료:** `C:/Users/AI-WS01/AppData/Local/Temp/astra17u_cpu_7f8_m6b2/`

- `sources-before.json`: 후보 37개·등록 입력 38개와 초기 상태.
- `evidence_17t/run_20261015_015522_120600/`: 예정 15개 실행, 입력 변조 12건, 코드 변이 6+3건의 정상/변이 로그와 생성 소스.
- `ownership-independent.py`, `ownership-independent.json`: 후보 함수 본문의 정상·이전 PID 재사용·새 자식 PID 재사용·불명 부모 잔존 후손·자연 종료·계속 보류 대조.
- `evidence-audit.py`, `evidence-audit.json`: 165개 실제 해시, 9개 실제 diff/실패 위치, 독립 승인값·결박 검사, 읽은 운영 실행기 해시.
- `historical-common.py`, `historical-common.json`: 과거 실제 세 결과의 지문·세 비교, 동일 지문/한 키 변경 대조, eval_changes 전체 제외의 한계.
- `final-source-check.json`: 산출물 작성 후 고정 파일·등록 입력·운영 실행기 불변성 및 신규 파일 확인.

시험 코드 사본은 그대로 사용했고 manifest의 시험 출력 경로만 Temp로 옮겼다. CPU 승인·장치 fixture는 기동 승인이나 장치 실측 자료가 아니다. 임시 반례의 가짜 신호는 실제 프로세스 종료가 아니다.

**남길 미확인:** 수정 난이도와 운영 연결 비용, 팀장 결정 대기, 실제 GPU 시간. 이 판정은 ‘조건을 대충 채우면 허용’이 아니라 **현 후보의 기동 보류**다.
