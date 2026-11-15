> 분류: A/정책학습 · Codex Worker 작업서 (sol) · (1) PhysX 질의 전부 miss 와 자세 편차 판별 도구 (2) S2 체크포인트 고정 평가 경로 설계
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 15:50
> 근거: `REPORT-s2-step10.md` 의 4차 HOLD 원인 조사(PhysX 103,224 표본 전부 miss · env 6 quat x 성분 step 7 부터 허용 초과) · `REPORT-s2-step9.md` 의 평가 경로 항(기존 `cmdr_eval_driver_s1043.py` 가 S2 형식 체크포인트를 읽는다는 근거 없음) · `VERIFY-astra-17af.md` 4절(고정 체크포인트 평가 기준) · `VERIFY-astra-17ag.md`
> 요지: step10 이 CPU 에서 닫혔다. 이어서 두 가지를 CPU 에서 만든다. (1) 학습 0 의 판별 도구: A3.3 과 같은 환경 구성으로 8 env × 16 step 만 돌며 PhysX 질의의 호출 형식 · 반환 원형 · 필터와 첫 16 step 의 발 접촉력 · root 각속도를 기록 (2) 짧은 A/B 결과를 읽는 데 필요한 S2 체크포인트 평가 경로의 설계와 CPU 에서 가능한 부분의 구현
> 상태: 작업 지시 (CPU 만 · GPU · Isaac 기동 금지 · 승인 json 은 만들지 않는다 · foot reward 작업서(`TASK-codex-worker-s2-2-foot-reward.md`)는 이 일 뒤)

# sol 작업서: 판별 도구와 평가 경로 (step11)

## 0. 지킬 것

step10 과 같다. `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I -B`. 새 사본 `codexE/s2_step11/` (step10 의 두 묶음을 복사해 시작, step10 · 저장소는 고치지 않는다). 정상 먼저, 변이는 지정 첫 FAIL. em dash 금지. 첫 실패도 보고서에. A3.3 의 지도 모듈 바이트는 바꾸지 않는다.

## 1. 판별 도구 `s2_physx_probe_diag.py` (A3.3 에 섞지 않고 형제 도구로)

- 환경 구성은 A3.3 의 `configure_env` 를 그대로 재사용한다(RobotLab-Go2-v0, 8 env, 8 case). 16 step 만 돌고 optimizer 0.
- 기록:
  1. 알려진 지면 3광선(평지 env 0 의 월드 좌표, 시작점 +0.4 m 위 · 방향 -z)을 물리 step 전과 후에 PhysX scene query 로 질의. 호출 형식 변형 둘 이상(`carb.Float3` 와 튜플 · 다른 최대 거리 단위)을 모두 시험하고 각 반환 원형(타입 · 필드 · hit 여부)과 사용한 scene path 를 기록. 변형 이름을 결과에 명시.
  2. 같은 광선을 RayCaster 의 hit 과 비교.
  3. 첫 16 step 의 4발 접촉력(env 6 을 포함해 8 env 모두) · root 각속도 · root_quat_w 전 성분.
- 판정 문구는 만들지 않는다(원자료 기록 전용). 정보 수집 전용 표기를 4차와 같게 유지.
- **CPU 증거:** PhysX 인터페이스와 센서를 가짜로 대신해 알려진 답으로 시험하는 계약 시험(호출 형식 변형 둘 모두 호출되는지, 반환 원형이 그대로 기록되는지, 광선 시작점이 이중으로 더해지지 않는지, 기록 파일의 해시 계약). 변이: 변형 하나 누락, 반환 원형을 가공해서 기록, 시작점에 +20 m 중복, 접촉력 기록 누락. 지정 첫 FAIL.
- 실행 계약(감독기 · lease · USD 잠금 · 가족 정리 · 관찰자)은 A3.3 의 것을 쓴다. 새 계약 항목이 필요하면 막힌 줄만 적는다.

## 2. S2 체크포인트 고정 평가 경로 (설계 + CPU 부분 구현)

- 먼저 읽고 보고: (a) `s2_runner_17v.py` 가 쓰는 체크포인트 형식(`s2-17v-checkpoint-only`)의 키 · shape · dtype (b) 기존 평가기(`cmdr_eval_driver_s1043.py` 와 `q_eval_cmdr.py`, `_eval` 은 읽기만)가 policy 를 부르는 접점과 필요한 입력(관측 열 · 지도 입력 두 팔 A/B) (c) 접점 하나하나에 대해 변경 위치와 크기.
- 설계 문서 `S2-EVAL-DESIGN.md`: ASTRA 17af 4절 5항(같은 지형 mesh/seed · 난이도 · 초기 pose · 명령 · 마찰 · 시간 상한 · 성공/추락/정체 정의의 case 목록, 학습 seed 와 다른 평가 목록, 추론 방식 고정, gap · stones 와 기존 능력 퇴행을 볼 대조 지형, 분자 · 분모 · 짝 결과 · 누락 공개)을 만족하는 평가 계획의 필드 목록과 case 수 후보. case 수는 정하지 말고 근거와 선택지만.
- CPU 에서 만들 수 있는 부분: S2 체크포인트 strict load 후 알려진 입력의 action/value 가 학습 경로와 같은지(정책 forward 한 번), A/B 지도 입력 생성의 알려진 답 시험. Kit 안 평가(case 실행)는 이번에 만들지 않는다.

## 3. 끝나면

`REPORT-s2-step11.md` (1절 도구와 시험 수 · 변이 CAUGHT/전체 · 2절 읽은 사실과 접점 표 · `S2-EVAL-DESIGN.md` · 첫 실패 · 미확인), `S2-STEP11-SHA256SUMS.txt`(CR 없이), #550 댓글 초안(미게시). 깨끗한 복사본 `-I` 전체 회귀(step10 시험 전부 + 새 것). lead 가 재실행한다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
