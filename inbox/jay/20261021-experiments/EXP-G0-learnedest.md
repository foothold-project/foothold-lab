> 분류: 실험
> 작성: 오흥재 (sol 문서 반영) · 2026-10-22
> 근거: [#555 6319562769](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6319562769) · `VERIFY-astra-ex11-design.md` X1~X4 · lead가 전달한 팀장 승인
> 요지: EX-12에서 S2-G0 추정 입력 학습값 51칸을 actor에 넣고 EX-11의 0 가림과 비교한다.
> 상태: 결과 전 계약 등록 · 코드·실행·결과 미확인 · 본선 관문 승인 아님

# EX-12 · S2-G0 학습 추정 입력 진단

## 가설

현재 G0의 추정 입력 `est51`을 actor에 연결하면 같은 조건의 0 가림 [EX-11](EXP-G0-zeroest.md)과 초기 보행이 달라지는가. EX-12의 actor 입력은 `o45 + est51`이다. 지각 모듈의 forward·표집·감독 갱신·reset은 두 판에서 동일하다. 이 비교는 GRU·지각 갱신·START 구조 자체를 따로 판정하지 않는다.

## 설정

EX-11 카드의 3072 env·24 step·seed42·7종 23열 S1 이어진 지형·START 명령·깨끗한 critic 664·actor 잡음·B std 0.5·종료 여유 0.25·clip17·500/1500 update·manifest·계측·평가 계약을 그대로 적용한다. 허용한 차이는 actor로 들어가는 est51의 0 가림 여부와 run id뿐이다. 동일한 초기 actor/critic 가중치·optimizer SHA를 확인한다. 50열·sparse·깃발은 끄고 지각 경로는 두 판 모두 실행한다. 먼저 EX-10 z/action 네 조합을 평가하고, 코드·CPU 시험·lead 확인 뒤 병렬 학습한다. 기본은 두 판 모두 1500 update까지이며 둘 다 통과할 때만 같은 완료 update에서 일찍 멈출 수 있다.

## 검증

EX-11과 학습 수집·PPO 저장·평가의 est mask 차이 한 곳만 확인한다. 실제 import 파일 SHA·dirty diff·YAML·인자·mode·초기 가중치와 경험량을 manifest로 대조한다. 조건부 KL과 PPO KL, raw/clip 행동과 포화, PD target·토크를 기록한다. NaN·shape·명령 계약 위반·실행 중 코드 변경은 실행 무효다. CPU 시험·lead 확인·실행은 현재 미확인이다.

두 판의 평지·고정 rough 2행2열 영상을 같은 시드·명령·카메라로 전 프레임 기록한다. 전진 0.5·1.0과 회전 ±1.2의 순간 민감도 및 닫힌 고리 추종을 분리한다. z 평균/표집 × action 평균, 차이가 있으면 action 표집까지 본다. 41:133의 진행≥0.8·생존≥0.95·요 이탈≤0.1·회전 추종≥0.80은 임무 참고선이다. S1 관문과 폐기된 몸높이 0.30·발높이 3 cm·요 10° 합격선으로 쓰지 않는다.

## 결과

영상 없음 · 미확인. `미측정`: 완료 update·manifest/체크포인트 SHA·invalid 여부·네 조합·명령 반응·2행2열 영상·lead 판독은 실행 뒤 기록한다. 미수신을 실패나 0으로 해석하지 않는다.

## 다음

[EX-11 카드의 결과별 표](EXP-G0-zeroest.md#다음)를 결과 전에 공동 규칙으로 고정한다. EX-11만 걷는다면 frozen 추정기 또는 속도 oracle 중 로그가 지목한 하나, 둘 다 걷는다면 열린 명령 확장, EX-12만 걷는다면 EX-12 계열 명령 확장, 둘 다 못 걷는다면 첫 update KL·critic 오차·행동 포화·보상 분해 후 표준 runner 대조 또는 속도 oracle 중 하나다. 무효·미완료·모호는 결론 보류다. 본선 복귀 순서와 clip17 한정도 EX-11 카드와 같다.
