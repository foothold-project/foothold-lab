> 분류: 실험
> 작성: jay · 2026-10-22
> 근거: [#555 6333065357](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6333065357) · [6333408008](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6333408008) · 코드 2e0fa180 · 영상 커밋 a1671095 · lead 채팅 10/22
> 요지: EX-11 환경에 legged_gym A1 보상 묶음을 적용한 EX-15의 최종 수치와 판정은 lead 결과 문서 전까지 미측정이다.
> 상태: 기존 실행 기록 존재 · 최종 결과 대기

# EX-15 · legged_gym A1 보상 묶음

## 가설과 결과 전 등록

> [선행] “둘 다 기는 자세가 남으면 다음 후보는 A1 묶음(torques -2e-4 · dof_pos_limits -10 · calf 충돌) 한 판.” [#555](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6333065357)

EX-14의 발 공중 시간 단일 변경에서 A1 기저 보상 항을 보태면 자세와 걸음 모양이 바뀌는지 비교한다. 이 변경만으로 START 모델 계보가 바뀌는 것은 아니다.

## 설정

| 항목 | 기록 |
|---|---|
| 환경 설정 계보 | `[코드] 2e0fa180`에서 EX-15 설정은 EX-14 설정을 상속하고 A1 보상 항을 더한다. 설정 상속은 체크포인트 계승을 뜻하지 않으며 체크포인트 계승은 미확인이다. |
| 보상 묶음 | EX-14의 `feet_air_time [코드] +1.0`에 `only_positive_rewards` 합산 하한 `[코드] 0`, 관절 토크 `[코드] -2e-4`, 관절 한계 `[코드] -10`(soft limit `[코드] 0.9`), calf 충돌을 추가한다. 충돌 가중치는 START의 `[코드] -10`을 유지한다. |
| 구분 | MGDP 고유 `motion_trot` 및 `stand_still`은 포함하지 않는다. EX-13의 불완전한 묶음을 이어 쓰지 않는다. |
| 기존 시작 기록 | `[실측·lead 기록] 14:21` GPU 0에서 시작했다고 #555에 기록됐다. 이 문서 작업에서는 학습을 시작하거나 이어서 돌리지 않았다. PID와 소비 설정 해시는 미확인이다. |
| 관찰 자료 | `[코드] a1671095`에 [EX-14·EX-15 비교 영상](figs/mid-1022/compare_mid_1022.mp4), [EX-15 중간 위상 그림](figs/mid-1022/phase_ex15_500.png)이 있다. 이는 최종 판정이 아니다. |

## 판정 · 결과 전 등록

`[선행] 300회`와 `[선행] 500회`에서 걸음 위상을 확인한다. 다리가 몸 아래로 펴지는지와 네 발 교대를 영상으로 보고, 자세·전진·회전 결과를 나눠 기록한다. EX-11과 같은 명령 표를 사용하고 새 수치 합격선을 만들지 않는다. 등록 조건은 [#555 6332758762](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6332758762) 및 [6333408008](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6333408008)이다.

## 결과

최종 수치와 판정은 `[미측정]`이며 lead 결과 문서를 기다린다. 기존 중간 영상: [compare_mid_1022.mp4](figs/mid-1022/compare_mid_1022.mp4). 최종 보행 판정은 미확인이다.

## 다음

lead 종합 결과를 받은 뒤 EX-14 단일 항과 A1 묶음의 차이를 분리해 기록한다. 중간 영상만으로 본 학습 승격이나 인과 결론을 내리지 않는다.
