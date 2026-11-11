> 분류: A/정책학습
> 작성: verifier-lx · 2026-11-11
> 근거: 팀장 E1F 승인 0b51913fced4eb6b34d39ebdd95548c190cb3018 · lead 11:58/12:02 의뢰 · planner REVIEW-EX42-E1F-E2-ENTRY-1111 §1 · CG 69e5ac6b:188~189,237~269
> 요지: E1F 정식 승인과 빈 증거 셋을 분리하고 E2 미승인 초안·검사기 등록·깃발 몫 선언을 준비
> 상태: CPU 88 통과 · reviewer 전 · 기동 불가(빈 증거 3 + 단계별 관문 소비 미완) · #639 위 PR

# E1F 승인과 E2 초안

## 승인 범위

처음 의뢰는 둘 다 초안이었으나 12:02 팀장 결정 원본을 읽고 E1F만 정식 `approved: true`로 바꿨다. `approval_statement: E1F 승인`, decision_source는 `0b51913fced4eb6b34d39ebdd95548c190cb3018`이다. 기본 750회·연장 false·250회마다 멈춤/평가/이어 가기·부모 E1 졸업본·이후 단계 false를 적었다. E2는 1500회 기본의 미승인 초안이며 승인 문장·ID·시각·승인자·결정 커밋은 null이다. E1F 승인으로 E2를 열지 않는다.

| 아직 비어 있는 E1F 증거 | 저장 위치 | 현재 동작 |
|---|---|---|
| E1 졸업 부모 SHA | scope.parent_sha256 | null이면 거부 |
| landing 평가 메시 SHA | prerequisites.predecessor_exit.evaluation_mesh_sha256 | null이면 거부 |
| W09 깃발 기준선 | prerequisites.flag_baseline.path/sha256 | 비었으면 거부 |

기준선 이후 고정해야 할 깃발 문턱도 `exit_gate.thresholds: null`이다. 가정 값을 측정 완료 값으로 채우지 않았다. `missing_evidence_policy: reject_launch_then_fill_and_repin`으로 이후 실측을 채울 때 승인 파일 SHA와 계획 pin을 다시 고정하게 했다. 지금 승인 SHA는 `5cac70d865161ce48e6db2e107e928e0d1dc38e941e7267dd2baf13384ae0068`, 계획 SHA는 `f3e9be90b08fabca1e35196729a8d3baf9509ae3c859b189e16d3a98f07a5955`다. 지금 도는 E1 고정 사본에는 쓰지 않았다.

## 정본 선언과 검사기

prep E1F의 shares는 CG:245의 깃발 0.10·전진 0.17·좌우 제자리 회전 각 0.07, 그 외 부모 몫 유지로 합계 1.0이다. 공여 비율은 정본의 가정 등급을 주석에 남겼다. 정지·후진·옆 몫에서 떼지 않는다. `terrain.exposure_at_E1F: same_as_E1_end`는 CG:242/244의 연속 100%·E1 실제 종료 상한(5 또는 6) 승계를 나타내며, 고정 5를 다시 박지 않았다. 이 선언을 실제 명령/노출 실행기에 연결하는 작업은 이번 승인 검사기와 별개다.

`validate_stage_e1f_authorization`, `validate_stage_e2_authorization`은 승인 SHA·명시 승인·결정 출처·부모·정본 회차/축·연장 금지·평가 간격·이전 단계 PASS 조건·landing/깃발 기준선 pin·DR 1.0을 확인한다. E2에는 정본 E.1의 M0~M3 영수증 pin도 빈칸으로 남겨 확인한다. E1F critic mirror는 planner 초안의 E1 상태 상속으로 적었으며 D174의 최초 활성화 boundaries [E1]은 바꾸지 않았다. E2 해당 결정은 null이다.

자동 승인 validators에 E1F/E2를 등록했다. 다만 **공통 26칸 PASS는 E1의 D44 졸업이나 E1F의 깃발 두 창 통과 증거가 아니다.** 현재 새 validator는 승인 기록만 검사하고 `entry_gate_adapter_ready: false`를 반환한다. 자동 승인 함수는 이 상태를 명시적으로 거부한다. 이는 새로운 팀장 승인 관문이 아니라 아직 없는 단계별 점수 소비자의 구현 경계다. 세 빈칸이 채워져도 이 소비 연결을 완성하기 전에는 자동 기동되지 않는다. 추후 소비자는 실제 부모 파일과 단계별 평가 증거를 대조해야 한다. 이 PR은 그 빈자리를 True로 대신하지 않는다.

E1F/E2 실제 기동 CLI·부모 복원·단계말 평가 생산자·깃발 기준선 계산·GPU 배정·프로세스 실행은 이 PR에서 구현하거나 실행하지 않았다. #640 등 운영 소비자 담당에게 이 경계를 전달한다.

## 검증

isaac311, CUDA 숨김, GPU/Kit 없음. 새 검사기 import가 없는 상태에서 시험 실패를 먼저 확인했다. 첫 묶음 실행은 basetemp 상위 디렉터리 누락으로 62 setup error였고, 임시 디렉터리를 만든 뒤 재실행했다. 코드 실패로 잘못 세지 않는다. 최종 원출력:

```text
88 passed in 8.08s
```

범위: future_approval·scoped_auto·e1_entry·e1_approval_pin·v016_contract·prep CPU 시험 여섯 파일. 승인 없는 E2, 부모/landing/기준선의 개별 누락, 잘못된 부모, 재고정 누락, 승인 문장 누락, 연장 확대, 평가 간격 변경, E0/E1 기존 갈래, 단계별 관문 미연결 차단을 확인했다. 최종 로그 `/home/jay/mai/tmp/verifier-lx/e1f-e2-draft-1111/cpu.log`.

## 병합과 남은 것

base는 #639 가지의 f180a80e다. #639 자체는 lead 지시로 E1 종료까지 보류 중이다. 이번 PR도 운영 E1을 교체하지 않는다. reviewer가 승인 범위·null 거부·정본 몫·등록 뒤에도 누락된 단계별 관문이 조용히 통과하지 않는지를 본다. 부모/landing/기준선 실물 확보와 단계별 관문 소비 연결이 남아 있다. 기동 불가를 승인 미취득으로 혼동하지 않는다: E1F 팀장 승인은 이미 기록됐다.
