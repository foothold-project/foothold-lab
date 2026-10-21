> 분류: 실험
> 작성: 오흥재 (sol 문서 반영) · 2026-10-22
> 근거: [#555 6319562769](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6319562769) · `VERIFY-astra-ex11-design.md` X1~X4 · lead가 전달한 팀장 승인
> 요지: EX-11에서 S2-G0 추정 입력 51칸을 actor에 넣을 때만 0으로 가리고 EX-12와 비교한다.
> 상태: 결과 전 계약 등록 · 코드·실행·결과 미확인 · 본선 관문 승인 아님

# EX-11 · S2-G0 추정 입력 0 진단

## 가설

현재 G0의 추정 입력 `est51`을 actor에 연결한 것이 초기 보행을 방해하는지 EX-12와 한 변수 대조로 묻는다. EX-11의 actor 입력은 `o45 + 0×est51`이다. 지각 모듈의 forward·표집·감독 갱신·reset은 EX-12와 똑같이 실행한다. 이 비교는 GRU·지각 갱신·START 구조 자체의 효과를 분리하지 않는다.

## 설정

| 항목 | 결과 전 계약 |
|---|---|
| 순서 | 먼저 [EX-10의 z/action 네 조합 평가](EXP-G0-start.md). 그 뒤 EX-11/12 코드·CPU 시험·lead 확인, 이후 두 판 동시 학습 |
| 학습 | 처음부터 학습. 3072 env · rollout 24 · seed 42 · PPO epoch/minibatch 수 동일 · 500 update 점검 · 1500 update 상한. 기본은 양쪽 모두 1500까지. 둘 다 평가를 통과하면 같은 완료 update에서 함께 종료 가능. 한 판만 걷는다는 이유로 다른 판을 중단하지 않음 |
| 지형 | S1 이어진 지형 7종, 23열 배정·초기 레벨·승급·reset 원점까지 동일. 50열·sparse 재배정·깃발 공급자 끔 |
| 명령 | START `vx ~ U[0,1.5]`, `vy=0`, 표집 `vx<0.3`이면 실행 `vx=0`, `wz ~ U[-1.2,1.2]`. 이동 구간 세부는 실제 cfg 확인 |
| 관측 | actor 잡음 유지. critic은 깨끗한 52 + 지도 512 + 발 지도 100 = 664. EX-11은 actor 연결에서만 est51을 0으로 가림. 학습 수집·PPO 저장·평가에 같은 mask 적용 |
| 보상·종료·행동 | EX-10의 B 추종 커널 std 0.5, `foot_below_ground` 여유 0.25, clip 17 공통. Rx1 std 0.25는 상속하지 않음. clip 100·무제한 clip·4096 env는 채택하지 않음 |
| 통제 | 초기 actor·critic 가중치 SHA와 optimizer SHA 동일, EX-12와 허용 차이는 est mask·run id뿐. 실제 import 파일 SHA·dirty diff·YAML·인자·패키지 버전·자산/지형/평가 코드·mask/critic/clip/z/action 모드·초기 weight SHA·경험량을 시작 manifest에 보존. 비밀 환경값은 기록하지 않음 |
| 계측 | 같은 history·hidden·epsilon에서 지각 갱신 전후 조건부 KL, PPO KL 별도. raw/clip 후 행동·포화율·관절별 연속 포화·PD target·토크 포화 기록 |

## 검증

CPU에서 학습 수집·PPO 저장·bootstrap·평가 mask 일치, 지각 업데이트·reset 유지, 초기 가중치·optimizer SHA 동일성, 7종·23열·reset origin·명령·664칸·clip17·경험량의 두 판 일치를 확인한다. `completed_updates`·`total_env_steps`·optimizer step 수를 checkpoint 라벨과 구분해 남긴다. `NaN/Inf`·shape 오류·명령 계약 위반·실행 중 코드 변경은 승패가 아니라 실행 무효다. 첫 500회의 기존 PPO KL·episode 길이·NaN 계약을 채택하는지 실행 전 명시하며 새 지각 KL을 PPO KL 문턱에 섞지 않는다. 구현·시험·lead 확인은 미확인이다.

2행2열 영상의 행은 EX-11/EX-12, 열은 평지/고정 rough다. 같은 시드·명령·카메라와 전체 프레임을 보존하고 lead가 본다. 전진 0.5·1.0 및 제자리 회전 ±1.2에서 순간 행동 민감도와 닫힌 고리 추종을 따로 본다. z 평균/표집 × action 평균, 차이가 있으면 action 표집도 본다. 진행≥0.8·생존≥0.95·요 이탈≤0.1·회전 추종≥0.80은 41:133의 임무 참고선이며 이 진단의 S1 관문이 아니다. 몸 높이 0.30·발 높이 3 cm·요 10° 폐기 합격선은 되살리지 않는다.

## 결과

영상 없음 · 미확인. `미측정`: 학습·평가·판독 결과를 아직 받지 않았다. 완료 update, manifest/체크포인트 SHA, invalid 여부, 네 조합·명령 반응·2행2열 영상 경로, clip 포화·KL·critic 오차·보상 분해, lead 판독을 실행 뒤 채운다. 미수신을 실패나 0으로 적지 않는다.

## 다음

| EX-11 | EX-12 | 제한된 해석 | 다음 한 걸음 |
|---|---|---|---|
| 걸음 | 못 걸음 | 이 조건에서 현재 est 연결이 해로움. 세부 원인은 미분리 | 로그가 지목하는 frozen 추정기 또는 속도 oracle 중 하나 |
| 걸음 | 걸음 | 초기 보행에 est가 필수는 아님 | START 명령 유지, 열린 명령 확장 단계 등록 |
| 못 걸음 | 걸음 | est 경로가 도움 | EX-12 계열에서 명령 확장 |
| 못 걸음 | 못 걸음 | est 제거만으로 해결되지 않음 | 첫 update KL·critic 오차·행동 포화·보상 분해 후 표준 runner 대조 또는 속도 oracle 중 하나 |
| 무효·미완료·모호 | 어느 상태든 | 승패 결론 보류 | 원인과 두 결과를 보존해 lead 판정 |

본선 복귀는 쉬운 지형 보행 → 열린 명령 → 깃발·물러나기·듬성한 지형 → G0/G1/G3 본선 비교 → 목표 추종 순서다. 진단 성적을 본선 G0 비교나 열린 명령·S1 관문 통과로 자동 승격하지 않는다. 모든 결론은 clip 17 조건에 한정한다.
