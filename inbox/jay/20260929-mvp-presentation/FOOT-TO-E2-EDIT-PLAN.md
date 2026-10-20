# 발 통과 컷과 E2 연결 제작안

> 분류: 계획
> 작성: Codex · 2026-10-01 00:55
> 근거: 사용자 두 영상 직접 평가, 좌→우 발 통과와 블랙 연결 지시, 기존 O7 원화 직접 열람
> 요지: Seedance를 우선 후보로 두고 앞 발 컷·블랙·E2를 먼저 연결한다.
> 상태: 이미지 사용자 승인 완료. 영상 1편·연결 시안 제작 완료, 사용자 확인 대기
> 판: v1.2

## 사용자 판단과 작업 선택

사용자는 두 원본을 확인했고 Seedance 2.5가 실제 Go2 보행에 거의 닮았으며 소리도 더 낫다고 평가했다. 이는 사용자 직접 감상이며 실제 로봇 보행 실측 검증을 의미하지 않는다. 다음 연결 시안의 E2 원본으로 Seedance를 우선 사용한다. 현재 조명·후반 전진에 대한 검토 의견을 최종 불합격으로 단정해 재생성을 반복하지 않는다.

앞 컷을 먼저 잇는다. 이번 구간의 목적은 첫발과 틈 통과가 어떻게 어둠 속 Go2 공개로 연결되는지 확인하는 것이다. 다음 Follow 컷은 이 연결의 리듬을 확인한 뒤 진행한다.

## 이번 승인 범위

1. 사용자 후속 지시에 따라 **O7 이미지 한 장을 먼저 제작·확인**한다. 구도는 사용자가 고른 발 접촉 이미지, 외형은 승인 캐릭터·디테일 시트, 재질·분위기는 승인 E2a를 참조한다. Sunburst 2K high 견적 2.75크레딧. 이미지 승인 후 Seedance 2.5 발 통과 영상 **1편**을 제작한다. 5초·480p·음향 포함.
2. 발 통과 원본과 기존 Seedance E2를 편집해 **연결 시안 1편** 제작. E2 원본은 재생성하지 않는다.
3. 원본·연결본·요청·비용·검토 결과를 HTML과 Git에 기록하고 사용자에게 보여준다.

사전 모델 설정 견적은 **15크레딧**이다. 참조를 넣기 전 5초·480p·음향 포함 조건으로 조회했다. 실제 제출 시 기존 참조를 연결한 요청으로 재조회한다. 예산이 달라지면 임의 확대하지 않는다. 이번 단계에 새 음악 생성·1080p·자동 재생성은 포함하지 않는다.

## 발 컷 생성 문안

기존 원화는 `assets/opening-storyboard-v3.png`의 우하단 O7이며, 사용자가 직접 첨부한 단독 발 컷을 [구도 참조](assets/opening-o7-user-selected-reference.png)로 보존했다. 시트 전체가 아닌 이 단독 컷을 이미지 제작에 사용한다. 다른 패널의 로봇이나 HUD를 참조로 섞지 않는다. 외형은 승인 캐릭터·디테일 참조로 보완한다.

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

## 이미지 먼저 확인하는 순서와 재질 기준

사용자가 “응 진행해. 발컷은 근데 이미지 먼저 하고 진행 안해도 되?”라고 물었고, 발·관절 클로즈업은 외형과 디딤 위치를 먼저 확인하는 순서로 수정했다. 이어 HDR·재질의 일관성을 재강조했다. 현재 승인 범위는 발 이미지 한 장 제작이다. 생성 결과 승인 전에 발 영상·편집 작업을 시작하지 않는다.

기존 컷의 두꺼운 원통형 발을 그대로 복제하지 않고 승인한 작은 둥근 발고무와 가느다란 회색 링크를 반영한다. 회색 외장은 은은한 반사, 발고무는 무광. 콘크리트는 마른 먼지·어둡게 젖은 곳·작은 국소 반사를 구분한다. 과한 HDR, 강한 미세 대비, 지나친 선명도, 플라스틱 광택, 전체적으로 거울처럼 젖은 바닥을 금지한다. 임의로 상처를 늘리지 않는다.

실제 이미지 요청: [O7 Sunburst v1](assets/opening-o7-sunburst-v1.request.json). 구도·외형·재질 참조의 역할을 각각 명시했다. 이미지에서는 접촉 위치와 외형을 확인하며, 앞발 두 개 이후 뒷발이 통과하는 시간 순서는 영상에서 확인한다.

| v1.1 | 2026-10-01 | 사용자 지시에 따라 이미지 선확인 단계 복원, HDR·외형·재질 공통 기준 명시 |

## 제작 결과

2026-10-01 사용자가 O7 이미지를 승인했다. 이에 따라 Seedance 영상 1편과 기존 E2 연결 편집을 완료했다. 위 이미지 승인 대기 설명은 당시 제작 순서 기록이며 현재 승인 상태는 이 절을 따른다. [결과·미확인 항목](O7-VIDEO-AND-CONNECTION.md), [재생 페이지](output/FOOTHOLD-foot-to-E2.html).

| v1.2 | 2026-10-01 | O7 이미지 승인, 영상·블랙 연결 시안 제작 결과 반영 |
