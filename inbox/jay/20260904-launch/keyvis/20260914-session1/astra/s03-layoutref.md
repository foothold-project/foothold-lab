# s03 구도 참조 전환 검증 · v7

내부 제작 검토안이다. v6 화면, 감독 스케치, 기존 v5 참조 네 장을 직접 열어 비교했다. 새 이미지 생성 및 Isaac 렌더는 수행하지 않았다.

## 판정과 채택안

| 안 | 판정 | 적용 |
|---|---|---|
| A · 감독 스케치 | v7 채택 | Ref 1의 구도만 따른다. 선화·사람 신발 같은 윤곽·문자·테두리는 제외한다. |
| B · 신규 Isaac 구도판 | 이번 v7 미채택 | A의 실제 결과를 먼저 검증한다. 새 파일이라는 이유만으로 승인 블로킹이 되지는 않는다. 스케치와 투영 배치를 대조한 다음 사용할 수 있다. |
| C · 참조 순서와 수 | 역할을 명시해 채택 | 기본 4장, 질감 보강이 필요할 때만 5장으로 제한하는 제작 제안이다. 도구의 기술적 최대치나 순서별 가중치 보장은 아니다. |

`확인됨` v6에는 우상단의 밝은 하늘 조각, 기울어진 지면 경계, 상단 몸통 하부가 남았다. 앞 두 발도 스케치보다 오른쪽에 배치됐다. 원본 대신 UI가 포함된 화면을 보았으므로 픽셀 정밀 측정으로 주장하지 않는다.

`확인됨` 스케치 내부 사각형 기준 앞발 중심은 대략 가로 31%·69%, 세로 55~65% 부근이다. v6의 세로 75%와 ‘하단 1/3 접점’은 이를 따르는 조건이 아니므로 폐기한다. 아래 v7의 좌표는 육안 판독을 바탕으로 한 제작 목표이며 감독의 수치 지정은 아니다. 스케치 내부 화면은 16:9보다 좁으므로 상대 배치와 바닥 여백을 옮기고 다리 형태 자체는 늘이지 않는다.

`확인됨` 스케치의 왼발 아래에는 명확한 돌 형상이 없다. 낮은 돌 접지는 브리프에서 가져온 추가 조건이다. 스케치의 사람 신발 같은 선을 외형 참조로 삼으면 이미 해결한 사람 다리 문제가 돌아올 수 있다.

`추측` 다리 참조 상단에 남은 가로 구조가 몸통 하부 재현에 영향을 주었을 수 있다. 인과를 확인하지는 못했으므로 프롬프트에서 적용 범위를 관절·다리·발끝으로 좁힌다.

‘13장 실패로 모델의 구도 제어 한계가 증명됐다’는 결론은 과하다. 13장은 브리프의 누적 기록이며 이번에 전부 재검수하지 않았다. 현 작업에서 문장 수정의 효율이 낮아졌다는 제작 판단으로 A를 시험하는 것은 타당하다. 다중 이미지의 대상 요소를 참조하는 기능은 [Seedream 4.5 공식 설명](https://seed.bytedance.com/en/seedream4_5)에서 확인했지만, Ref 1 자동 우선권이나 구도 고정 보장은 제시되지 않는다.

B는 이번에 채택하지 않았으므로 실행용 수치표를 발행하지 않는다. 기존 0.7m·40도·60mm를 그대로 고정하면 폐기한 낮은 접점 배치를 다시 만들 수 있다. 추후 B를 진행할 때는 실제 charsheet 좌표 정의와 투영을 확인해 스케치의 발 위치부터 맞추고, 신규 파일명·자세·설정값·검토 결과를 함께 기록해야 한다.

## v7 첨부 순서

기준 폴더는 `../keyvis/session1/`이다. 기존 실패 후보 이미지는 첨부하지 않는다.

| 슬롯 | 파일 | 허용 역할 |
|---|---|---|
| Ref 1 | director_sketch_s03_firststep.png | 내부 사각형의 배치·발 위치·상단 진입 방향·바닥 여백 |
| Ref 2 | v5/S2_kneelegs4.png | 기계 다리 분절·관절 틈·작은 검은 발끝 비율 |
| Ref 3 | v5/S1_L41_ground.png | 건조한 바닥 재질 |
| Ref 4 | v5/S3_M39_nosun.png | 모래색 대기와 색조 |

`v5/S4_T44_fine.png`는 지면 참조와 겹치므로 기본 구성에서 뺀다. 구도가 통과했는데 미세 자갈 질감만 부족하면 Ref 5로 추가하고 다음 완결 문장만 뒤에 붙인다: “Ref 5 supplies fine gravel texture only; ignore its stone sizes, lighting and layout.” 이 경우에도 2,900자 이하다. 두 구도 참조를 동시에 넣어 권한을 충돌시키는 구성은 사용하지 않는다.

## s03 v7 영어 프롬프트 전문

LF 줄바꿈, 코드 울타리와 끝 줄바꿈 제외 `len(prompt) = 2573`이다. 지정 금지 단어와 긴 줄표가 없음을 검사했다. Ref 1의 역할을 첫 참조 문단에서 직접 선언하며, 슬롯 순서만으로 우선권이 생긴다고 가정하지 않는다.

```text
Photoreal cinematic still, 16:9, showing the first foot contact of one compact robotic quadruped.

Ref 1 is the sole composition reference. Follow the arrangement inside its black rectangle: two foreground legs enter through the top, with separated feet at left and right and open ground below. Transfer their relative positions to the wider frame without stretching the robot. Interpret the arrow as movement from the top toward the bottom. Remove the border, arrow, lettering and sketch strokes. Render realistic materials, never a drawing. Ref 2 defines mechanical leg anatomy and proportions only. Ref 3 defines dry ground material only. Ref 4 defines sand-colored haze and restrained color only. None of Refs 2-4 may change the composition of Ref 1.

Show an elevated frontal view looking down onto ground that fills all four corners. Keep the ground plane level, with no sky, horizon, distant ridge or bright horizontal band. Keep the head, torso, underside and all horizontal body structures outside the upper edge. Do not copy the gray background or upper crosspieces from Ref 2. The two front legs dominate, with smaller rear tips visible near the top as in Ref 1. All visible limbs belong to one robot. Preserve rigid white shell segments, mechanical joint gaps and compact rounded matte black rubber tips. Do not reproduce the human shoe-like outlines of the sketch.

Place the robot's right forefoot at image left, centered near 31 percent of image width and 60 percent of image height. Place the other front foot near 69 percent width and 57 percent height. Leave substantial visible ground between the front legs and below both feet. Keep each front rubber tip about 8-10 percent of image width; rear tips remain smaller. These placements replace the earlier low contact position.

Seat the leading right forefoot on a broad, partly buried weathered stone barely raised above the surrounding sand. The other front foot contacts lower sand. Show a tight contact seam, an attached shadow and a faint trace of settled dust. Use muted brown-gray compacted sand, fine gravel, shallow grooves and sparse embedded stones. Keep the surface flat overall, without cliffs or a raised platform.

A low light source outside the upper-right edge casts narrow leg shadows toward the lower left. Keep white shell edges readable and ground texture visible through faint warm haze. Exclude recognizable body silhouettes in the shadows, detached or extra limbs, human legs, boots, oversized feet, floating contact, explosive dust, distant robots, sun discs, text and watermarks.
```

## 합격 기준 · 세 줄

- 바닥이 네 모서리를 채우며 하늘·지평선·밝은 수평 띠·머리·몸통·하부 가로 구조가 없고, 다리는 상단에서 들어오는 배치다.
- 앞발 중심은 왼쪽 가로 26~36%·오른쪽 64~74%, 세로 52~66%에 있으며, 앞발 아래에는 충분한 바닥 여백이 남고 작은 뒤 발끝 둘이 상단 쪽에서 구별된다.
- 한 로봇의 기계 다리로 읽히며 앞발 폭은 각각 화면 가로 8~10%이고, 왼쪽 오른앞발은 낮게 묻힌 돌에 밀착하며 사람 신발·복제 다리·뜬 발이 없다.

위 범위는 이번 검수의 제안값이다. 정지 이미지의 상단 진입 배치는 볼 수 있지만 실제 이동 방향은 영상에서 확인해야 한다. v7 결과 합격 여부는 미확인이다.

