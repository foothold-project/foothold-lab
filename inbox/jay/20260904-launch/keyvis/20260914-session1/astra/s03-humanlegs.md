# s03 v5.2 · 네 다리 기계 실루엣 복원

## 판정과 수정

내부 제작 검토안이다. 결과 그리드와 참조 네 장을 직접 열어 확인했다. 새 이미지는 생성하지 않았다. 이전 후보는 모두 미채택이며 다음 생성의 참조로 사용하지 않는다.

- `확인됨` 그리드 상단 첫 이미지에는 발목 주름과 앞으로 돌출된 흰 신발 형태가 보인다. 두 번째도 길고 매끈한 두 다리와 신발 같은 발 형상으로 읽힌다. 사람 다리 문제에 동의한다.
- `추측` 다리 참조 제외와 모호한 흰 하퇴 표현이 사람 해석을 유도했을 가능성이 있다. 이 비교만으로 원인을 확정하거나 모델의 일반적인 일관성 부족을 입증할 수는 없다.
- 네 다리 실루엣 허용, 기계 다리 명시, 무릎 참조 복원에 동의한다. 두 다리만 요구하던 조건과 다리 참조를 배제하던 문장은 폐기한다. 앞다리 두 개가 주가 되고 뒤쪽 두 발도 구별되는 구도로 바꾼다.
- `확인됨` S2_kneelegs4.png에는 검은 발끝 네 개와 분절된 흰 외장, 무릎 부근 기계 구조가 보인다. 다만 상단에 가로 구조 잔여물이 있어 ‘몸통 0’은 보증하지 않는다. 이 참조는 무릎부터 발끝의 형상에만 사용하고 상단 가로 구조와 회색 배경을 복제하지 않도록 명시했다. 원본은 수정하지 않았다.
- 기계식 네발 보행체라는 범주는 공개된다. 머리·몸통·로고를 숨겨 기종 공개를 늦추는 연출은 유지하되, 다리만으로 Go2를 알아보지 못한다고 보장하지 않는다.
- 하퇴 길이 약 네 배라는 임의 비율 대신 참조의 실제 비율을 우선한다. 무릎은 경계 밖으로 숨기지 않고 상단 바로 안에 보이게 한다. 전체 크기와 발 폭 등 숫자는 기존 제작 지시이며 실물 실측값으로 주장하지 않는다.

## 참조 첨부 순서

기준 폴더: `../keyvis/session1/v5/` (이 문서 위치 기준).

| 첨부 순서 | 파일 | 적용 범위 |
|---|---|---|
| Ref 1 | S1_L41_ground.png | 건조한 분지 바닥의 성격 |
| Ref 2 | S2_kneelegs4.png | 네 다리의 분절 외장·관절·발끝 형상과 비율 |
| Ref 3 | S3_M39_nosun.png | 모래색 안개와 색조 |
| Ref 4 | S4_T44_fine.png | 모래·자갈 표면 질감만 |

`확인됨` Ref 4에는 돌 윤곽이 남아 있다. 돌이 제거된 이미지라고 설명하지 않으며, 돌 크기·배치를 따르지 않도록 제한한다. 기존 세 장 체계의 참조 번호는 사용하지 않는다.

## 영어 프롬프트 전문

LF 줄바꿈, 코드 울타리 및 마지막 줄바꿈 제외 기준 `len(prompt) = 2811`이다. 길이 제한과 금지 단어 부재를 코드로 검사했다. 모든 문장은 끝까지 수록했다.

```text
Photoreal cinematic still, 16:9. First visible ground contact of a compact robotic quadruped machine. Show four mechanical lower legs: two front legs dominant, two rear legs partially visible behind them with distinct black tips. All belong to one machine whose body remains above the frame. Its make and model are concealed.

Ref 1: ground crop for dry basin character only. Ref 2: mechanical knee-to-tip geometry, white polymer shell segments, joint gaps and small rounded matte black rubber tips; preserve these shapes and proportions. Ignore its gray background and all horizontal structures along its upper edge. Ref 3: pale sand-colored haze and atmospheric color only. Ref 4: sand-and-gravel surface texture only, never rock size or layout.

View straight toward the approaching machine, not side-on, from 22 cm above sand, about 2 m from the contact, 135 mm full-frame equivalent. Look 5 degrees below horizontal. Zero roll; the distant ground boundary stays horizontal, parallel to the top and bottom borders. Ground dominates. Frame from the mechanical knees down, with front knee actuators visible just below the top edge. Keep the head, torso, underside, shoulders, sensors and markings wholly above the frame. No upward view or wider reveal.

Use rigid articulated machine limbs with white polymer shell segments and exposed mechanical knee actuators matching Ref 2, never invented humanoid anatomy. Maintain compact lower-leg proportions from Ref 2, without stretching or boot-like flares. Forelegs are separated by visible ground; rear legs sit farther back, partly occluded, with four distinct foot tips total. No detached or duplicated limbs. Production scale remains about 70 cm overall length, 40 cm standing height and 5-6 cm foot-tip width; the body stays unseen.

One broad open dry basin, gently uneven muted brown-gray compacted sand, embedded weathered stones, fine gravel and shallow grooves. Relief is only a few centimeters. The right forefoot at screen left has just seated on a broad partly buried stone about 3 cm above nearby sand. The other front foot supports lower sand. Show a clear contact seam, tiny contact shadow and slight mechanical joint flexion, suggesting continued travel rather than a final halt.

Pale haze erases all distant subjects. One low sun lies outside the view on the observer's side at screen right; long shadows recede diagonally away. Bright diffuse haze separates pale shells from the background. Fine lateral windblown grains and a tiny contact puff stay below the foot edges.

Exclude human legs, boots, trousers, skin, animal hooves, bipedal stance, full robots in the distance, body-shaped shadows, sun discs, oversized feet, wide-angle distortion, podium rocks, cliffs, hovering feet, jumping, explosive dust, weapons, neon, text and watermarks.
```

## 다음 생성의 합격 기준

| 항목 | 합격 조건 |
|---|---|
| 기계 다리 | 흰 외장의 단단한 분절, 관절 틈, 기계식 무릎 구조가 보인다. 살·옷 주름·장화 입구·길게 튀어나온 사람 신발 앞코가 없다. |
| 네 다리 배치 | 앞다리 두 개가 주가 되고 뒤쪽 두 다리가 일부 보인다. 검은 발끝 네 개를 각각 셀 수 있고 한 기체의 앞뒤 배치로 읽힌다. 다섯 번째 발·분리된 다리·이족 자세는 미달이다. |
| 무릎·비율 | 앞무릎이 화면 상단 안에서 확인된다. Ref 2의 짧고 분절된 형상이 유지되며 길게 늘어난 매끈한 기둥이 아니다. 무릎이 모두 잘리면 비율 판정을 보류하고 재생성한다. |
| 공개 범위 | 머리·몸통·하부 가로 구조·센서·로고가 보이지 않는다. 후경에도 전신 개체가 없다. |
| 구도 | 바닥 중심의 낮은 정면이다. 먼 지면 경계가 화면 가로축과 평행하고 기울어진 구도가 아니다. |
| 접지·스케일 | 화면 왼쪽 앞발이 낮고 일부 묻힌 돌에 닿는다. 나머지 발도 떠 있지 않다. 접촉선·국소 그림자·작은 먼지가 보이고 돌이 단상처럼 커지지 않는다. |
| 분위기 | 태양 원반 없이 옅은 안개가 다리를 분리한다. 긴 그림자가 화면 안쪽으로 멀어지고 먼지가 발 높이 아래에 머문다. |

한 장의 정지 이미지로 시간상 ‘첫’ 접지나 이동 지속을 증명할 수는 없다. 여기서는 접촉과 작은 먼지 등 시각 단서를 판정한다. 기계 다리·네 발·무릎·공개 범위 중 하나라도 실패하면 다른 분위기 항목이 좋아도 미채택한다. 재생성 결과의 합격 여부는 아직 미확인이다.
