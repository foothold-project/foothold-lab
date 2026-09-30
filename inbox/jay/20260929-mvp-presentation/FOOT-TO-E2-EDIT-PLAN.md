# 발 통과 컷과 E2 연결 제작안

> 분류: 계획
> 작성: Codex · 2026-10-01 00:55
> 근거: 사용자 두 영상 직접 평가, 좌→우 발 통과와 블랙 연결 지시, 기존 O7 원화 직접 열람
> 요지: Seedance를 우선 후보로 두고 앞 발 컷·블랙·E2를 먼저 연결한다.
> 상태: 사용자 승인 대기. 추가 영상 생성·편집 미실행
> 판: v1.0

## 사용자 판단과 작업 선택

사용자는 두 원본을 확인했고 Seedance 2.5가 실제 Go2 보행에 거의 닮았으며 소리도 더 낫다고 평가했다. 이는 사용자 직접 감상이며 실제 로봇 보행 실측 검증을 의미하지 않는다. 다음 연결 시안의 E2 원본으로 Seedance를 우선 사용한다. 현재 조명·후반 전진에 대한 검토 의견을 최종 불합격으로 단정해 재생성을 반복하지 않는다.

앞 컷을 먼저 잇는다. 이번 구간의 목적은 첫발과 틈 통과가 어떻게 어둠 속 Go2 공개로 연결되는지 확인하는 것이다. 다음 Follow 컷은 이 연결의 리듬을 확인한 뒤 진행한다.

## 이번 승인 범위

1. 기존에 선택한 O7 발 접촉 구도와 승인 Go2 디테일 시트를 참조해 Seedance 2.5 발 통과 영상 **1편** 제작. 5초·480p·음향 포함. 새 이미지나 다른 모델 비교를 추가하지 않는다.
2. 발 통과 원본과 기존 Seedance E2를 편집해 **연결 시안 1편** 제작. E2 원본은 재생성하지 않는다.
3. 원본·연결본·요청·비용·검토 결과를 HTML과 Git에 기록하고 사용자에게 보여준다.

사전 모델 설정 견적은 **15크레딧**이다. 참조를 넣기 전 5초·480p·음향 포함 조건으로 조회했다. 실제 제출 시 기존 참조를 연결한 요청으로 재조회한다. 예산이 달라지면 임의 확대하지 않는다. 이번 단계에 새 음악 생성·1080p·자동 재생성은 포함하지 않는다.

## 발 컷 생성 문안

기존 원화는 `assets/opening-storyboard-v3.png`의 우하단 O7이다. 시트 전체를 시작 이미지로 보내지 않고 해당 컷만 사용한다. 다른 패널의 로봇이나 HUD를 참조로 섞지 않는다. 외형은 승인 캐릭터·디테일 참조로 보완한다.

```text
One continuous five-second close-up at ground level, camera locked. Match the approved foot-contact composition and the same Unitree Go2's slim leg links and rounded black rubber foot caps. The robot travels from SCREEN LEFT TO SCREEN RIGHT across this narrow gap. Show the front feet landing on the far concrete ledge first, then the hind feet clearing and landing as the body continues to the right. Show the feet sequentially in the close crop, not four feet squeezed into the frame at once. Coherent quadrupedal stepping and weight transfer, no simultaneous leap, sliding, extra legs or foot penetration. A few loose grains and small concrete chips crumble naturally from the ledge as the hind feet push off, falling down into the gap. Keep the load-bearing ledge intact. No large collapse or explosive dust. Hold the locked framing long enough to retain the last hind-foot exit and falling debris as editing handles. Same dark industrial environment, restrained highlights and uneven damp concrete, no glossy plastic or HDR. Generate synchronized rubber foot contacts, restrained motors, granular scraping and small falling fragments with the same cavernous room ambience. No speech, score, text, HUD or camera whip. Deliver clean footage without a baked wipe, fade or black frame; the left-to-right black transition will be matched in the edit.
```

## 연결 순서

| 구간 | 화면 | 소리 |
|---|---|---|
| 발 통과 | 카메라 픽스. 좌→우 진행. 앞발 두 개 통과 후 뒷발 이탈과 작은 파편 낙하 | 발 접촉음과 돌 부스러기의 마찰·낙하음 |
| 블랙 아웃 | 발이 지나가는 좌→우 방향을 받아 화면을 쓸어 완전 블랙. 마지막 뒷발을 가리기 전에 동작이 읽히게 함 | 낙하음과 공간 잔향을 블랙 너머에 남김. 큰 전환 효과음 추가 금지 |
| E2 진입 | 완전 블랙에서 승인 E2a의 어둠·고정광을 드러내고 느린 달리인과 Go2 접근으로 연결 | E2의 먼 발소리와 같은 공간음을 받음. 가까운 착지음을 중복하지 않음 |

블랙 유지와 해제 시간은 편집 제안값으로 약 0.2~0.4초부터 확인한다. 실제 발 이탈 타이밍과 E2 진입을 보고 조정한다. 영상 생성에 블랙을 강제하는 대신 편집에서 확실한 검은 프레임을 확보한다. E2 시작의 블랙 해제는 방 자체의 광원이 밝아지는 연출과 구분한다.

E2는 기존 원본에서 사용할 구간을 고른다. 후반의 틈 접근이 불필요하면 그 전에 끊는 편집을 먼저 검토한다. 조명 문제를 숨기거나 기존 영상이 요구를 완전히 충족했다고 기록하지 않는다.

## 확인하고 전달할 것

- 앞발·뒷발 순서, 좌→우 진행, 접촉과 파편 낙하, 다리·발 외형
- 블랙이 실제로 존재하고 화면 쓸기 방향이 맞는지
- 발 컷의 빠른 리듬에서 E2 원경으로 넘어갈 때 급하게 튀거나 오래 멈추지 않는지
- 오디오 끊김·중복 접촉음·레벨 급변 여부. 최종 영화 전체 음향은 별도 작업

마스터 연결 시안을 먼저 보여준다. 오프닝·엔딩 분리 상영본은 발 컷 후 블랙에서 오프닝을 닫고, 엔딩도 블랙에서 재진입하도록 사용한다. 발표 시간 동안 소리가 이어지는 것으로 만들지 않는다.

## 이력

| 판 | 날짜 | 변경 |
|---|---|---|
| v1.0 | 2026-10-01 | 사용자 Seedance 선호 반영, 앞 발 컷 1편과 기존 E2 연결 편집 승인안 |
