# s03 v6 · 위에서 내려다보는 첫 접지

## 감독 방향 판정

가능하다. 내부 제작 검토안이며 새 이미지는 생성하지 않았다. 지정된 스케치와 v5.2 결과 화면을 직접 열어 비교했다.

- `확인됨` 스케치는 지평선 없이 바닥이 화면을 채우고, 앞다리 두 개가 상단 경계에서 내려온다. 위에서 아래로 들어오는 IN 방향이 핵심이다. 정확한 렌즈나 각도는 스케치에서 측정할 수 없다.
- `확인됨` v5.2는 네 개의 기계 다리와 검은 발끝을 보여 사람 다리 문제를 해소했다. 그러나 밝은 먼 지면 경계와 상단의 몸통 하부 가로 구조가 보인다. 브리프의 ‘정체 미공개 통과’를 완전한 몸통 은닉으로 해석하면 안 된다.
- `제작값` 높이 0.70m, 수평 기준 하향 40도, 풀프레임 환산 60mm, 롤 0도로 고정한다. 주 접점까지 지면상 전방 거리 약 0.70m, 직선 거리 약 1.0m로 수정한다. 기존 1.2m는 거리 정의가 없고, 하단 접점 배치와도 맞추기 어렵다.
- `계산 확인` 36mm 가로 센서를 16:9로 자른 단순 투영에서 세로 화각은 약 19.2도다. 평지 접점의 하향각 45도는 화면 높이 약 76%에 투영된다. 따라서 프롬프트의 75%는 반올림한 제작 목표다. 3cm 돌과 발의 좌우 위치로 실제 투영은 달라지므로 픽셀 위치를 우선한다. 수치는 실물 실측이나 생성 결과 측정값이 아니다.
- 하향 시점만으로 몸통이 자동으로 사라지지는 않는다. 몸통·하부 가로 구조를 상단 밖으로 자르는 조건을 별도로 유지한다. 기존 ‘무릎을 반드시 화면 안에’ 조건은 폐기한다. 무릎을 보이려다 다시 넓은 구도가 되는 것을 막는다.
- 네 발은 유지하되 앞 두 발이 주가 된다. 뒤 발은 상단 쪽에 작게 보인다. 네발 기계라는 범주는 이미 공개되며, 기종을 알아보지 못한다는 보장은 없다. 정지 이미지로 IN 동작을 입증할 수 없으므로 영상에서는 빈 바닥에서 시작해 상단으로부터 들어오게 한다.

## 참조 첨부 순서

v5.2의 네 장을 유지한다. 기준 폴더는 이 문서에서 `../keyvis/session1/v5/`다. 이번 검토에서 참조 원본 네 장을 다시 열지는 않았으며, 파일 순서와 역할은 기존 `s03-humanlegs.md`를 따른다.

| 순서 | 파일 | 적용 범위 |
|---|---|---|
| 1 | S1_L41_ground.png | 건조한 분지 바닥 |
| 2 | S2_kneelegs4.png | 기계 다리 분절·관절·검은 발끝과 비율 |
| 3 | S3_M39_nosun.png | 모래색 안개·색조 |
| 4 | S4_T44_fine.png | 미세한 모래·자갈 질감 |

v5.2 결과 이미지는 첨부하지 않는다. 낮은 시점과 몸통 노출을 다시 따라갈 위험이 있다. 빛은 화면 우상단 바깥, 투영 그림자는 접점에서 좌하단으로 통일한다. 기존 ‘그림자가 화면 안쪽으로 멀어짐’ 문장은 대체한다. 발끝 폭은 전경 앞발마다 화면 가로의 8~10%로 제한하고, 뒤 발은 원근에 따라 더 작게 둔다.

## s03 v6 영어 프롬프트 전문

LF 줄바꿈, 코드 울타리와 마지막 줄바꿈 제외 기준 `len(prompt) = 2794`다. 2,900자 이하, 지정 금지 단어 없음, 문장 완결을 검사했다.

```text
Photoreal cinematic still, 16:9. The first visible foot contact of one compact robotic quadruped advancing from the top toward the bottom of the image. Two front mechanical legs dominate; two rear legs are partly visible behind them, with four distinct black foot tips in total.

Ref 1 supplies dry basin ground character only. Ref 2 supplies mechanical knee-to-tip geometry, rigid white polymer shell segments, joint gaps and small rounded matte black rubber tips. Preserve its proportions; ignore its gray background and upper horizontal structures. Ref 3 supplies pale sand haze and color only. Ref 4 supplies fine sand-and-gravel texture, never rock size or layout.

Use an elevated frontal viewpoint 70 cm above local sand, looking downward 40 degrees, with a 60 mm full-frame-equivalent perspective and zero roll. The principal contact lies about 70 cm forward along the ground, about 1 m in direct distance. Fill the entire image with ground, including the top corners. No sky, horizon, distant landscape boundary or bright horizontal haze band. Show the upper surfaces of stones and rubber tips, with natural downward foreshortening.

Mechanical legs enter through the top border. Crop above the visible lower-leg segments; keep the head, torso, underside, shoulders, sensors, logos and every horizontal body structure completely outside the image. Partial mechanical joints may appear near the top, but never widen the view to reveal them. Separate the front legs with visible ground. Rear legs remain subordinate, with distinct smaller tips farther up the image. No detached, extra or humanoid limbs. Preserve compact machine proportions, with no elongated shin columns, fabric folds, boots or human shoe toes.

Place the robot's right forefoot at image left, contact centered near 36 percent of image width and 75 percent of image height. Each front rubber tip spans about 8-10 percent of image width. Seat the leading tip on a broad, partly buried weathered stone rising only 3 cm above nearby sand. The other front tip supports lower sand. Show a firm contact seam, tiny attached shadow, subtle joint compression and a small dust puff below tip height.

The surface is muted brown-gray compacted sand with fine gravel, shallow grooves and embedded stones, never a pedestal or rugged cliff. A single low light source outside the upper-right edge grazes the ground. Leg shadows extend diagonally toward the lower left from their contact points; keep them narrow, with no recognizable torso silhouette. Soft sand-colored airborne haze lifts shadows without obscuring ground texture. Maintain restrained warm highlights and readable white shell edges.

No full-body reveal, distant robots, sun disc, floating feet, oversized footwear, explosive dust, weapons, neon, text or watermarks.
```

## 합격 기준 · 세 줄

- 바닥이 네 모서리까지 채워지고 지평선·하늘·수평 안개 띠가 없으며, 다리는 상단에서 들어와 하향 원근으로 보인다. 머리·몸통·하부 가로 구조는 0이다.
- 앞 두 다리가 주가 되는 네발 기계로 읽히고 검은 발끝 네 개를 구별할 수 있다. 흰 외장 분절과 관절 틈이 보이며 사람 다리·장화·복제 다리가 없다.
- 화면 왼쪽 주 접점은 하단 1/3 안에 있고 앞발 폭은 각각 8~10%다. 낮게 묻힌 돌에 접촉선이 붙으며 그림자는 우상단 광원에 맞춰 좌하단으로 뻗는다.

## v5.2 후보 처리

v5.2 후보12는 최종 채택에서 제외하고 ‘기계 다리 형태 해결 참고, 구도 재작업’으로 보류한다. 원본은 삭제하거나 덮어쓰지 않는다. 생성 입력으로 재사용하지 않으며 v6 결과가 나온 뒤 위 세 줄을 직접 확인해야 한다. v6 합격 여부는 아직 미확인이다.
