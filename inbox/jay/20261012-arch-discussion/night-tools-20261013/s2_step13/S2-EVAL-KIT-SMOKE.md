# S2 Kit 평가기 첫 단회 계약
> 분류: A/평가
> 작성: Codex · 2026-10-16
> 근거: step13 작업서 · 1043 Q 평가 계약 · A3.4 감독기 정적 코드 · step13 CPU 가짜 환경 시험
> 요지: 학습 없이 update 0의 gap 2짝과 stepping stones 2짝으로 평가기 접속만 확인한다.
> 상태: 제안 · CPU 계약만 확인됨 · Kit 실행 미확인

## 범위와 순서

1. lead가 결과를 보기 전에 평가 seed 4개, 학습 seed 전체, 지형 소스와 기하 SHA, 지형 난이도, 마찰, `fwd03` 또는 `fwd10` 명령을 고른다. `s2_eval_cases.py --phase smoke --gap-pairs 2 --stepping_stones-pairs 2 --flat-pairs 0 --stairs_up-pairs 0`으로 한 case 목록을 봉인한다. 이 문서는 값이나 승인 JSON을 미리 만들지 않는다.
2. E1 부모에서 S2 형식으로 저장한 **update 0** A/B 체크포인트를 사용한다. 학습 update는 0이다. 둘 다 부모 E1 SHA `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8` 및 agent.yaml SHA `9b8149ddc6101f92966d2ffdef326f44fa0fb46553678d8f092bcf624dc3173b`를 검사한 뒤 `s2_eval_cpu.strict_load`를 거친다. checkpoint 이름에서 iteration을 추론하지 않는다.
3. 각 case를 A 다음 B에 동일하게 적용한다. 실행 전 지형 mesh, 초기 상태, 명령, 마찰 및 두 dt의 물리 지문을 비교한다. reset 영수증의 case ID·seed·episode ID·이전 sensor generation을 첫 packet과 대조한다. 매 step 같은 observation과 RayCaster의 갱신된 atomic packet을 검증하고 `training_map`으로 374열을 만든 다음 `act_inference`만 부른다. A의 map은 0, B는 같은 학습 경로의 높이와 mask다.
4. 4짝의 episode 원자료와 누락 이유를 기록한다. 이 단회는 **정보 수집**만 한다. `comparison_ready=false`, `performance_verified=false`를 유지한다. 이 영수증의 직접 검토 전에는 2,000 update 체크포인트 평가를 만들지 않는다.

## 새 manifest의 필수 항목

| 묶음 | 필드 |
|---|---|
| 신원 | `scope=s2_eval_kit_smoke_once`, `chain_id`, `attempt`, 단회 `claim_id`, `observer_mode=attended`, `retry_count=0` |
| 입력 | job JSON 경로와 SHA, case JSON 경로와 파일 SHA 및 내부 `cases_sha256`, E1 부모 경로와 SHA, agent.yaml 경로와 SHA, A/B update 0 체크포인트 경로와 SHA, S2 코드 및 1043 채점 코드 SHA |
| 조건 | `phase=smoke`, `update=0`, `inference=act_inference`, `training_updates=0`, gap 2짝, stones 2짝, 평가 seed 4개와 학습 seed 집합, 기하 및 마찰과 명령, `geometry_tolerance_m` |
| 자원 | GPU UUID와 index, 기존 lease 경로, USD 잠금 경로, 분리된 USD root, 겹치지 않는 출력 및 로그 경로, 가족 Job Object owner, 독립 관찰자 영수증 경로 |
| 시간 | 관찰 가능한 절대 마감과 단조 시계 상한, `max_wall_s=900`, 재시도 0 |

승인 범위는 별도 직접 확인이 필요하다. 기존 A3.4 승인 또는 학습 승인을 이 단회로 이월하지 않는다. 감독기는 자체 소유 가족만 닫고 lease 및 USD 잠금 해제를 영수증에 확인한다. 기존 `s2_zero_supervisor.py`, `s2_resource_lease.py`, `s2_job_owner.py`, `s2_hard_watchdog.py`, `s2_stage0_prelaunch.py`의 경계를 새 scope에서 재사용한다.

## 영수증 필드

`claim_id`, manifest/approval/job/case SHA, 실행 코드 SHA, GPU UUID, Kit·Isaac·torch·driver 판, 자식 PID와 가족 수, lease 및 USD 잠금 획득·해제 시각, USD 전환 결과, 시작·종료·마감 시각, 자식 종료 코드, 가족 정리 확인, 네 case의 A/B mesh·초기 상태·명령·마찰 지문, episode 파일 SHA, 누락 사유, `comparison_ready=false`, `performance_verified=false`, `information_only=true`, 관찰자 독립 기록 SHA를 남긴다. 원자료 파일을 읽어 다시 해시하고 결과 영수증의 해시와 대조한다.

## Kit 연결에 필요한 변경 위치와 미확인 호출

| 위치 | 필요한 변경 |
|---|---|
| `s2_train_entry_17v.IsaacS2Env` | 현재 `step()`은 Isaac wrapper가 자동 reset한 뒤의 상태만 돌려준다. 평가 전용 `step_recorded()`에서 **reset 이전**의 최종 물리 상태를 잡는 검증된 Kit hook이 필요하다. 해당 hook은 정적 소스만으로 확정되지 않았다. 없으면 드라이버가 `physical_state_before_reset_missing`으로 멈춘다. |
| `s2_eval_driver.py`의 adapter factory | 기존 Q evaluator의 `RobotLab-Go2-v0` 생성 및 고정 case reset, reset 영수증, 지형 source/mesh와 초기 pose fingerprint, 명령 고정, `AtomicPacket` 공급, 마지막 물리 상태 공급을 구현한다. 현재 CPU 코어는 이 프로토콜만 검증했다. 실제 Kit adapter와 지형 접근·zone 산출 호출은 미확인이다. |
| A3.4 `s2_zero_supervisor.py:62~105`, `:127~288` 및 `s2_stage0_contract_a2.py:48~115` | A3.4는 진단 자식 파일과 256 step argv를 고정하므로 평가기 경로를 끼워 넣을 수 없다. 별도 scope, 자식 allowlist, 정확한 argv, 네 case 출력, 900초 상한 및 판정기를 가진 평가 전용 감독 계약이 필요하다. 기존 파일은 고치지 않는다. |
| `s2_stage_gate_17v.py` | 접속 성공은 정보 영수증의 완결성과 네 짝의 동등성 및 가족 정리만 판정한다. 성능 합격으로 바꾸지 않는다. |

Kit adapter와 감독 계약을 독립 CPU 시험한 뒤에만 단회 실행 요청을 만들 수 있다. 현재 GPU·Isaac 실행은 하지 않았다.
