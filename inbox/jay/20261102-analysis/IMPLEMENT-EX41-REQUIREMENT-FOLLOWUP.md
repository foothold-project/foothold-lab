> 분류: A/정책학습 · EX-41 요구 등록부 후속
> 작성: analyst · 2026-11-02
> 근거: 0e85c3d7 EX41-REQUIREMENT-REGISTER · lead 18:2x 분담
> 요지: U6·U10·U12·U15·U16·U17·P3·P7·P8을 소비 경로와 알려진 입력으로 확인한다.
> 상태: 항목별 진행 · GPU/Kit/라이브 변경 없음 · 미연결은 완료로 세지 않음

# EX-41 요구 등록부 후속

## U6 · 전역 오류와 reset 실패

W86 생산부는 `FatalTrainingFault(ValueError)`와 `ex41_fatal.jsonl`을 제공한다. 전역 정책 NaN, env 단위가 아닌 관측/전이 NaN, 모든 env 행동 무효, reset 예외, reset 뒤 관측 무효를 env 격리 성공으로 처리하지 않고 현재 rollout에서 예외를 낸다. 정상 env가 있는 국소 오류는 기존 격리·PPO valid mask 경로를 보존한다.

영수증 계약: format=`ex41-fatal/1`, event=`fatal_training_fault`, step, reason, stop_requested=true, resumable_checkpoint_written=false, required_action=`preserve_last_verified_checkpoint_and_stop_before_update`. reset 실패에는 env_ids·error_type을 덧붙인다. 기록 I/O 실패도 typed exception을 유지하며 receipt_write_error를 포함한다. 손상 모델을 정상 checkpoint로 쓰지 않는다.

**미연결**: 실행기 소유 scripter가 이 예외와 전역 loss/parameter 오류를 안전한 저장·중단 경계에 연결하고, 마지막 검증 저장본 SHA와 알림을 기록해야 한다. 잘못된 상태로 다음 정기 저장(50회)을 기다리며 학습을 계속하는 의미가 아니다. 알림 운송은 runner의 U3 경로다. 따라서 생산부 CPU 통과만으로 U6 전체를 닫지 않는다.

실측: 수정 전7 FAIL(2.66초), 수정 뒤 U6와 기존 W86 19 PASS(4.91초). 원자료 D:/mai-tmp/analyst/u6-red-1814.log, u6-green-1816.log. 실행기·학습 프로세스·원장 변경 없음.

## 남은 항목

U10 무릎 한계 비율·점수 칸, U12 실제 소비·분포, U15 모든 링크 접촉, U16 foot_slip/W53, U17 기존8실패 처분, P3 승인 거울 경로, P7 최종 T0′·졸업, P8 실제 지형 승급. P3는 자동 거울 끔 결정을 유지하며 수동 승인 경로와 관찰 후보를 구분한다. P7 문턱은 planner 정본 확인 뒤 연결한다.
