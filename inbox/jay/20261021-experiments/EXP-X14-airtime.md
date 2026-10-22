> 분류: 실험
> 작성: jay · 2026-10-22
> 근거: [#555 6332758762](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6332758762) · [6333408008](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6333408008) · [6333740345](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6333740345) · 코드 cce2de44 · 영상 커밋 a1671095
> 요지: EX-11에서 발 공중 시간 항 하나만 바꾼 EX-14의 최종 결과는 lead 종합 문서 전까지 미측정으로 둔다.
> 상태: 기존 실행의 중간 기록 존재 · 최종 결과 대기

# EX-14 · 발 공중 시간 단일 항

## 가설과 결과 전 등록

> [선행] “EX-14 = EX-11 + 발 공중 시간 +1.0 하나만.” [#555 사전 등록](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6332758762)

EX-13의 묶음과 구별해 발 공중 시간 항 하나만으로 걸음 모양이 달라지는지 살핀다.

## 설정

| 항목 | 기록 |
|---|---|
| 환경 설정 계보 | `[코드] cce2de44`의 EX-14 설정은 EX-11 설정을 상속한다. 설정 상속은 체크포인트 계승을 뜻하지 않는다. 체크포인트 계승은 미확인이다. |
| 보상 변경 | MGDP 식의 `feet_air_time`만 `[코드] +1.0`. 수평 명령 크기 `[코드] 0.1` 초과 때 적용한다. EX-13의 `motion_trot`, `stand_still`, 합산 보상 clipping은 추가하지 않는다. |
| 학습 설정 | 카드 근거의 코드 설정은 `[코드] max_iterations=1501`, seed `[코드] 42`다. 전체 소비 설정과 PID는 미확인이다. |
| 실행 기록 | #555에 기존 실행의 중간 점검이 기록돼 있다. 이 문서는 해당 실행을 재개하거나 새 실행하지 않았다. |
| 관찰 자료 | `[코드] a1671095`에 [EX-14·EX-15 비교 영상](figs/mid-1022/compare_mid_1022.mp4), [EX-14 중간 위상 그림](figs/mid-1022/phase_ex14_500.png)이 있다. 이는 최종 판정이 아니다. |

## 판정 · 결과 전 등록

`[선행] 300회`와 `[선행] 500회`에서 걸음 위상을 확인한다. 영상에서 다리가 몸 아래로 펴지는지, 네 발이 번갈아 걷는지 보고 EX-11과 같은 명령 표를 비교한다. 새 수치 합격선은 두지 않으며 회전 결과는 자세와 분리한다. 세부 판정은 [#555 6332758762](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6332758762)와 lead 채팅 기록을 따른다.

## 결과

최종 수치와 판정은 `[미측정]`이며 lead 종합 결과 문서를 기다린다. 기존 중간 점검의 상세 수치는 카드에 옮기지 않는다. 중간 영상: [compare_mid_1022.mp4](figs/mid-1022/compare_mid_1022.mp4). 최종 보행 판정은 미확인이다.

## 다음

lead 종합 문서의 최종 값을 받은 뒤 EX-11 기준 및 EX-15 묶음과 구분해 기록한다. 중간 위상 그림을 전체 학습 결과로 확대하지 않는다.
