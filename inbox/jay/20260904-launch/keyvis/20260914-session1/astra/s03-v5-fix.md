# s03 후보9 판정과 v5.1

## 판정: 후보9 미채택, 정체 미공개 구도만 유지

후보9 화면과 v5/S2_frontlegs.png, S1_L41_ground.png를 직접 확인했다. 전문은 s03_prompt_v5.txt를 읽었다. 아래는 내부 검토안이며 새 이미지 생성은 하지 않았다.

- `확인됨` 머리·몸통·후경 개체 없이 다리와 발만 보이며, 바닥·안개 중심 구도와 태양 원반 부재는 통과다. 화면 왼쪽 발이 돌에 닿는 것도 보인다. 다만 그것이 해부학적 오른앞발인지는 몸통이 없어 이미지 단독으로 검증할 수 없다.
- `확인됨` 먼 지면과 안개의 경계가 오른쪽 아래로 내려간다. 약 10°라는 관찰에 대체로 동의하지만 정확한 각도는 미측정이다. 실제 수평선이 선명하지 않으므로 이 경계만으로 회전각을 확정할 수는 없다. 요청한 평평한 분지의 수평 구도로는 미달이다.
- `추측` 하향 시선 지시를 화면 회전으로 해석했을 가능성은 있다. 원문은 정확히 “tilted 5 degrees down”이며, 이것이 단독 원인인지는 생성 결과 한 장으로 알 수 없다. 하향 시선과 롤을 분리해 명시하면 된다.
- `확인됨` 무릎이 안 보이는 긴 하퇴가 위로 잘리고, 특히 화면 오른쪽 다리가 길고 가늘게 읽힌다. 다만 몸통과 무릎이 없어서 실제 하퇴 길이는 측정할 수 없다. “무한정 연장”은 원인 설명이 아니라 인상에 가깝다. 발 폭 대비 길이와 무릎 위치를 함께 고정해야 한다.
- `확인됨` 화면 오른쪽 주 다리 뒤에 추가 하퇴와 검은 발끝이 보인다. 더 중요한 것은 S2_frontlegs 자체에도 같은 위치에 세 번째 검은 발끝과 하퇴가 있다는 점이다. 두 다리 정리판이라는 설명과 실제 참조가 다르다. 생성본의 추가 발을 부추겼다는 것은 강한 가설이지만 인과가 확정된 것은 아니다.
- `미확인` 왼쪽 돌 접지부의 작은 먼지와 관절의 미세한 눌림은 이 화면으로 확실하게 판정하기 어렵다. 화면 오른쪽 발 주변의 작은 먼지는 보인다. 추가로 긴 그림자가 화면 아래·오른쪽 전경으로 뻗어, 원문의 “멀어지는 그림자” 지시도 통과로 묶으면 안 된다.

## 참조 정책

v5.1에서는 S2_frontlegs를 제외한다. 현재 S2는 무릎이 잘려 있어 하퇴 비율의 기준으로 부적절하고, 추가 발까지 포함한다. 이번 첨부 순서는 **Ref 1 = S1_L41_ground, Ref 2 = S3_M39_nosun, Ref 3 = S4_T44_fine**이다. 원래 슬롯 이름의 숫자와 프롬프트의 참조 번호를 혼동하지 않는다.

우선 문장만으로 두 하퇴를 제어한다. 이후 형상 일관성이 부족할 때만, 원본에서 무릎부터 발끝까지 완전한 앞다리 두 개를 확보하고 뒤쪽 다리를 모두 제거한 참조를 만든다. 무릎이 없는 현재 S2를 다시 잘라서는 누락된 관절과 길이를 복구할 수 없다. 전신 이미지는 추가하지 않는다.

## v5.1 전문

아래 영어 본문은 줄바꿈 LF, 코드 울타리와 마지막 줄바꿈 제외 기준 `len(prompt) = 2847`이다. 참조 매핑, 수평·하향 시선, 무릎·하퇴 비율에 필요한 문장만 바꾸고 나머지는 원문을 유지했다. 약 4배는 이번 연출의 제약이며 실물 치수를 새로 확인한 값은 아니다. 원문의 전체 크기와 광학 수치도 기존 제작 지시를 계승한 것으로, 이번 검토에서 실측하지 않았다.

```text
Photoreal cinematic still, 16:9. An unidentified presence makes its first visible ground contact. Ground dominates; ONLY two cropped white lower front legs and small black rubber tips enter the view. Their upper portions continue beyond the top border. Do not reveal what carries them.

Ref 1: cleared terrain crop, low basin character only. Ref 2: sun-free haze crop, atmospheric color only. Ref 3: a cleared sand-and-gravel crop with large rock outlines removed; texture only, never stone size. No limb or full-body reference is attached.

Observe straight toward the approaching subject, not side-on. Locked viewpoint 22 cm above sand, 135 mm full-frame equivalent, about 2 m from the contact, looking 5 degrees below horizontal. Zero roll: the far-ground horizon is level and parallel to the top and bottom borders, never slanted. Frame from the knee joints down; each knee sits at the top border or immediately outside it. Keep every head, torso, underside, shoulder and sensor entirely above the image, with at least 15% of image height separating the upper border from the lowest projected body part. Never look upward or widen to reveal it. The short shins meet the top edge; the floor remains visible between them. Each foot tip spans about one tenth of image width, without changing its real proportions.

Preserve the approved scale: about 70 cm overall length and 40 cm standing height, although the body stays unseen. Small rounded black tips are approximately 5-6 cm wide in the production scale guide; each lower leg from knee to sole is about four foot-tip widths long, with consistent sturdy thickness, no elongated taper and no boot-like flare.

One broad, open, gently uneven dry basin: muted brown-gray compacted sand, embedded weathered stones, gravel and shallow grooves. Relief is only a few centimeters. The right forefoot, at screen left, has just seated on a broad partly buried stone about 3 cm above nearby sand; the other front foot supports lower sand. Read the contact seam, tiny contact shadow and slight joint yielding. This is continuing travel, not the final halt.

Pale sand-colored haze erases distant anatomy; only indistinct tonal traces remain above the far ground. Keep one low sun ahead-left in the robots' world, outside the view on the observer's side at screen right. Long shadows recede diagonally away. Bright diffuse haze separates the subdued pale shins from the background without adding a second sun. Fine lateral windblown grains and a tiny fresh contact puff stay below the foot edges.

Exclude full robots even in the distance, readable faces or markings, body-shaped shadows, sun discs, oversized feet, close wide-angle distortion, podium rocks, cliffs, smooth parade roads, hovering supports, detached or extra limbs, jumping, explosive dust, speed lines, weapons, neon, text and watermarks.
```

## 후보9 처리와 다음 판정

후보9는 실패 비교본으로 보존하고 최종 채택·영상화·다음 생성의 참조에서는 제외한다. 회전 보정만으로는 하퇴 비율과 추가 발이 해결되지 않으므로 v5.1로 재생성한다. 파일 삭제나 이미지 수정은 수행하지 않았다.

다음 결과에서는 먼 지면 경계의 수평, 검은 발끝 정확히 두 개, 상단 경계 부근 무릎, 발 폭 약 4배의 짧은 하퇴를 먼저 확인한다. 무릎이 화면 밖이면 전체 하퇴 길이 확인은 보류한다. 이어 정체 미공개, 왼쪽 돌 접지·국소 먼지, 그림자가 멀어지는 방향을 확인한다. 바닥을 더 보여주려다 무릎을 멀리 잘라내거나 다리를 길게 늘린 결과는 재차 미달이다.
