> 분류: A/평가 · EX-41 소비자·기록기 통합 준비
> 작성: analyst · 2026-11-03
> 근거: lead 03:2x·03:3x · analyst9256788e · runner1d3c4da4 · 실제 model_10/예행 원기록 · 설치 Isaac Lab API
> 요지: W91·P4·소비자 고정 가지에 U10 모터 한계 출처 오류를 수정. 최종 로더 통합·26칸·모든 기록기 예행 증거는 runner 제공 뒤 검증
> 상태: CPU50 PASS · 실제 Kit/최종 통합 미확인 · 학습·GPU·실행원장 변경 없음

# EX-41 소비자와 U10 통합 준비

## 고정 HEAD의 범위

가지 `feature/analyst-ex41-score-name-1102-jay`, 사본 `D:/mai-wt/foothold-lab/analyst-ex41-score-name-1102`. 이번 고침의 부모는 `9256788ebbd45b418670742990fd6999b9818823`이다. W91(`7a2a1283`·`ac038f89`), P4(`9871663c`), 점수 시각·P3·최종 요청 소비자(`9256788e`)가 모두 이 가지에 있다.

runner `1d3c4da4`에는 W91 수집기·P4 histogram 모듈과 W86의 P4 연결13줄이 없다. 점수 watcher에는 runner 별도 고침이 있으므로 파일 통째로 덮지 말고 통합한다. `curriculum/ex41_scoring.py`는 두 고정판에서 같다. 실제 26칸 재평가와 최종 예행 이전에 이 소스 대조를 다시 한다.

W91 수집기와 점수 소비자는 CPU JSON/NPZ 소비자이고 정책을 직접 불러오지 않는다. 생산자인 `turn_probe`, `eval_map_modes`, `ex40_stand_eval`, `axis_v2_run`, `terrain_skill_v2_run`은 이미 `adapters.load_s2_runner`를 호출한다. runner가 소유하는 공통 로더를 고쳐 연결하고, 여기에 별도 정책 로더를 만들지 않는다. 최종 로더 HEAD와 실제 산출물이 아직 없으므로 입력 차원 호환성을 닫지 않는다.

## U10 분모 오류의 근거와 고침

`rewards/w86_runtime.py`의 기존 `PhysicalSource.__call__`은 `robot.data.joint_effort_limits`를 사용했다. 설치 Isaac Lab `actuators/actuator_base.py:55~71,174~175`는 명시적 모터의 실제 내부 제한 `effort_limit`와 PhysX용 `effort_limit_sim`을 구분한다. `assets/articulation/articulation.py:1772`는 후자를 `joint_effort_limits`에 쓴다. 명시적 모터의 미지정 sim 한계는10⁹이다.

- 실제 예행 `D:/mai-tmp/runner/s2_lab/ex41_rehearsal_20261103_025200/params/env.yaml:324~349`: 모터 한계23.5/45.43, `effort_limit_sim:null`.
- 기존 실제 EX-35 `C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_eval/m2000/turn16_eval_gt/probe_result.json:216~253`: sim 한계12개는10⁹, 모터 무릎 한계4개는45.43. **EX-41 예행은 그 분모 실값을 기록하지 않아 해당 실행의 직접 실측은 미확인**이다.
- 답 아는 생산자 입력: 모터45.43, sim10⁹. 수정 전 실제 `PhysicalSource` 호출이10⁹을 반환해 **1 FAIL**. 토크45라면 정상 모터 분모의 비는약0.9905지만 sim 분모는4.5e-8이므로0.9 한계근접을 놓친다. 이 계산이 예행 토크45가 관측됐다는 뜻은 아니다.

고침은 관절 ID 순서로 `robot.actuators[*].effort_limit`를 읽는다. slice·목록, env별 변경값을 지원하고 중복·누락·잘못된 shape·비유한 한계는 거절한다. **토크-속도에 따라 변하는 순간 포락선 비율이 아니라 모터 effort ceiling 대비 비율**이다.

원기록에 `control_dt_s`, 무릎별 `detail_valid_frames`, `mean_abs_applied_torque_nm`, `mean_effort_limit_nm`, `limit_source`를 추가했다. 세부 합계가 없는 옛 recorder state에서는0을 지어내지 않고 해당 세부 평균을null로 둔다. `knee_effort_margin` 가중은 기존0 그대로이며 새 보상·가중·명령·DR 변경은 없다. 이 사본을 실제 실행판에 연결하기 전 독립 검토와 최종 예행 실값 대조가 필요하다.

## 이번 CPU 시험

isaac311, CUDA 숨김, D: TMP/TEMP/basetemp, pytest cache 끔.

| 시험 | 결과·로그 |
|---|---|
| 기존 생산자에 모터45.43/sim10⁹ 입력 | 수정 전1 FAIL, `D:/mai-tmp/analyst/u10-source-red-1103.log` |
| 새 모터한계 계약·W86·W91 | 36 PASS, `D:/mai-tmp/analyst/u10-w91-green-1103.log` |
| U10 점수 소비·P4 histogram | 14 PASS, `D:/mai-tmp/analyst/u10-consume-p4-1103.log` |

모터 버퍼 변경, 순서·중복·누락, 비유한, 45Nm의0.9 문턱 및 로그 분모를 검사했다. 기존 W91의 깨진 NPZ·불변 영수증 회귀도 포함된다. 전체 EX41 시험을 이번에 다시 돌렸다고 하지 않는다. 이전9256788e의 독립242 PASS/4 SKIP 근거는 `D:/mai-tmp/verifier/VERIFY-9256788e.md`로 구분한다.

## 최종 예행 대기표

| 행 | 현재 확인 | 남은 최소 증거 |
|---|---|---|
| U6 | 기존 fatal/quarantine CPU·독립 증거 보존 | 최종 소비 코드와 실패표식·마지막 정상 저장본·경보 경로 연결 |
| U10 | 위 분모 오류 수정·CPU 검증 | 새 예행의 실제 모터 한계·토크·분모·시간·0가중 생산 |
| U12 | 기존 초기/경계 생산기 존재 | 최종 예행 슬롯/env/종류/레벨 실제 분모와 초기·경계 보존 |
| U15 | 기존 비최종 예행12행에19링크 이름·그룹 기록 | 최종 HEAD의 sensor body ID 순서·시간축·분모·원기록 대조 |
| U16 | 0가중 foot_slip 생산 필드 존재·기존 답 아는 시험 | 최종 접지 마스크·유효분모·단위, 링크 중심 XY 속도 대용치 한계 표시 |
| P4 | 모듈·hook·CPU 존재, 기존 예행에는 초기 histogram 파일 없음 | runner 통합 후 실제 초기/경계 histogram 및 D161 슬롯 대칭 |
| Q7 | 기존 독립 반례·제거변이 원출력 존재 | 최종 소비 코드 SHA별 연결, 새 U10 한정 독립 재검 |
| G2 | model_10의 actor98/critic666을 CPU로 직접 확인 | 초기 0열·Adam 이식 기존 독립 근거와 최종 공통 로더 성공·SHA 연결 |

이 표는 기동 승인표가 아니다. 신규26칸 숫자는 아직 없다. 기존 실패 score의 `evaluation_state=HOLD`, `metrics={}`와 rc0는26칸 통과 근거가 아니다. 후속 새 map64·stand의39칸 원수를 직접 세어 유지26·기록39·stand3모드와 SHA를 검산한 뒤 한 묶음으로 보고한다.

원자료 읽기 기록: `D:/mai-tmp/analyst/ex41-loader-audit-1103/existing-rehearsal-recorders.json`, 재생 스크립트 `audit-ex41-raw-recorders-1103.py`. 이전 예행을 최종 예행으로 대체하지 않는다.
