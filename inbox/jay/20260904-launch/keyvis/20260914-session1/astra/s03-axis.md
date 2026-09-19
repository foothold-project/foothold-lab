# s03 연출 축 판정과 v4 설계

> 상태: 내부 제작안. 정면 축 복원안을 작성했으며 v4 이미지·영상과 새 참조 마스크는 아직 만들지 않았다.
> 근거: s03-axis-brief.txt의 감독 확정 지시, 감독 스케치, 아래 직접 열람한 이미지 18장, 기존 제작 설계·스토리보드·세션 1 재설계.
> 수치: 로봇 외형·발 치수는 기존 스케일 바이블을 계승한다. 촬영 값·화면 점유율·돌 높이는 이번 설계 목표이며 결과 실측값이 아니다.

**감독의 정면 앤트 IN 컷이 맞다. s03 v3.1 후보6은 기술 시험의 성과로 남기되 최종 K03로 승격하지 않는다.** 내 기존 측면안은 확정 블로킹을 바꿀 근거가 없었다. 발이 커지는 문제를 해결하면서 시점을 높이고 옆으로 돌려 전신을 보여준 것은 기술적 편의를 위해 컷의 목적까지 바꾼 결정이었다. v4는 정면 접근·다리 중심 구도로 돌아가고, 원근 과장은 촬영 거리와 화각으로 해결한다.

## 판정 근거

아래 경로는 모두 다음 폴더를 기준으로 한다.

`C:/Users/AI-WS01/AppData/Local/Temp/claude/C--Users-AI-WS01-Desktop-jay----------foothold-lab/85e9e940-5633-48ed-a407-2d9aafc96e93/scratchpad/`

| 직접 연 이미지 | 확인한 내용 | 판정에 미치는 영향 |
|---|---|---|
| `keyvis/session1/director_sketch_s03_firststep.png` | 위에서 프레임 안으로 이어지는 두 다리, 낮은 발·지면 중심 구도, 아래쪽을 향한 IN 화살표와 발 주변 선. 몸통을 옆으로 길게 보여주는 그림이 아니다. | 축과 화면의 주인공이 이미 정해져 있다. 선 자체의 물리적 의미는 감독 브리프의 먼지 설명을 따른다. |
| `keyvis/previs_frames/s03_0.png`, `s03_1.png`, `s03_2.png` | 첫 프레임에 정면 센서와 앞다리가 보이고, 뒤 프레임으로 갈수록 다리·발이 가까워지며 몸통이 화면 위로 잘린다. 좌우 이동 성분도 있지만 측면 프로필 횡단으로 바뀌지 않는다. | 스케치와 같은 정면 접근 계열이다. 프레임의 평지 트롯·격자를 버리는 것과 이 축을 버리는 것은 다른 결정이다. |
| `keyvis/previs_frames/s02_1.png`, `s04_1.png` | 먼 대열이 지평선 쪽에 있고 s04에서 더 크게 보인다. 정면 접근이라는 방향 해석은 브리프의 확정 지시와 함께 판단했다. | 원경 접근, 근접 첫 접점, 조금 다가온 원경이라는 구성이 일치한다. 이 두 정지판만으로 실제 속도·거리·시간을 재지는 않았다. |
| `keyvis/session1/results/s03_cand6_v31_screen.jpg` | 머리가 화면 오른쪽인 넓은 측면상, 전신 중심, 박힌 돌 위 앞발, 뒤쪽의 측면 대열. 별도 장비·철망은 눈에 띄지 않고 열린 낮은 분지와 접점이 읽힌다. | 브리프의 기술 기준 통과와 양립하지만, 관객에게 다가오는 첫발이라는 연출 기준은 불통과다. 정지 화면으로 실제 보행·하중·미끄러짐까지 검증됐다고 하지 않는다. |

### 관측점 분리는 가능하지만 측면 전환은 필수가 아니다

기존 `production-design.md` §B의 A/B 분리 자체는 쓸 수 있다. A는 원경을 보는 자리이고 B는 같은 선두 가까이의 낮은 자리다. **B도 선두 앞에서 정면을 보면 된다.** A/B가 다르다는 사실은 B를 선두 옆에 두어야 할 근거가 아니다. 기존 제작 설계의 공간 설명을 후속 스토리보드의 횡단과 세션 1의 우측 전신상으로 구체화한 판단을 철회한다.

“멀리 있던 로봇이 갑자기 렌즈 앞에 도착한다”는 우려도 감독안을 뒤집지 못한다. 이 편집은 원경에서 세부로 거리를 건너뛰는 인서트로 읽히도록 설계할 수 있고, 컷 사이의 시간 생략도 허용할 수 있다. 이는 이번 편집에 대한 판단이며 모든 관객이 반드시 같은 식으로 읽는다는 실측 주장은 아니다. 특히 s03 뒤 s04가 다시 먼 원경이므로, “같은 촬영 지점까지 대군이 순식간에 와 버렸다”는 설명을 붙이는 것은 불필요하다. **같은 진행축의 가까운 관측점으로 컷하고 원경으로 돌아오면 된다.** 사건은 앞으로 진행하며, s04 대열의 변화량은 실제 연결에서 결정한다.

측면 인서트가 영화 문법상 언제나 틀리다는 뜻은 아니다. 다만 이 작품은 감독이 정면 IN을 확정했고, 실제 스케치와 프리비즈도 그 결정을 뒷받침한다. 이를 바꿀 새 연출 승인이나 필연적 공간 제약은 자료에서 찾지 못했다. 기술 통과가 감독 확정을 대신할 수 없다.

## s03 v4 구성

**프레임 안으로 걸어 들어오는 두 앞다리와 첫 접점이 주인공이다.** 전신 포스터를 만들지 않는다. 로봇 자신의 오른앞발은 정면에서 보는 관객에게 **화면 왼쪽**이다. 주 발의 접지점은 화면 가로 약 35%, 세로 약 75% 부근이며, 그 자리에 낮게 박힌 돌이 있다. 좌표는 발 중심이 아니라 발과 돌이 만나는 점의 기준이다. 반대 앞발은 조금 더 뒤의 낮은 모래를 지지하고, 구별되는 뒷다리 하나는 다음 지지를 향한 스윙 중이다. 두 앞발의 동시 점프 착지로 바꾸지 않는다.

두 앞다리의 연결을 따라갈 수 있게 상부 일부를 남기되 머리와 상체 윗부분은 화면 위로 잘라도 된다. 땅에 붙은 작은 검은 발끝·좁은 하퇴·약간 굽은 관절이 먼저 읽혀야 한다. 뒤의 Go2 대열은 같은 정면 방향으로 안개 속에서 이어지고, 선두의 양옆과 다리 사이로 일부 보인다. 대열을 보여주려고 선두를 측면으로 돌리거나 배경 개체를 횡단시키지 않는다.

영상으로 만들 때는 빈 근경 지면, 옆에서 먼저 흘러오는 얇은 먼지, 깊이 쪽에서 들어오는 다리, 오른앞발의 한 번 접지, 짧은 하중 흡수와 계속되는 전진 순으로 잇는다. 접점 자체에서 나오는 새 먼지는 닿은 뒤에만 발생한다. 대표 키비주얼은 이미 닿은 순간이므로 영상의 첫 프레임으로 그대로 잠그지 않는다. 접지 뒤에도 전진이 남아 있음을 보여주고, 로봇이 관측 지점에 도달하거나 지나치기 전에 s04로 컷한다. 확정 초수·보폭은 실제 동작 시험 전에는 적지 않는다.

### 낮은 시점과 정상 비율을 함께 지키는 값

| 항목 | v4 시작값·검수 방법 |
|---|---|
| 방향 | 선두의 정면. 진행축과 시선이 마주 보며, 화면 깊이에서 관객 쪽으로 접근한다. 촬영 중 옆으로 선회하지 않는다. |
| 높이·거리·초점거리 | 모래 기준 높이 **8cm**, 접지발까지 약 **1.4m**, 풀프레임 환산 **70mm**, 위로 약 **2도**. 거리는 머리나 몸통 중심까지가 아니라 대표 접지 순간의 발까지다. |
| 프레이밍 | 앞다리와 발 중심. 머리·상체 윗부분을 위에서 자르고, 발 앞에 약간의 지면을 남긴다. 발을 렌즈 쪽으로 뻗어 발바닥을 내보이지 않는다. |
| 발 크기 목표 | 가까운 앞발 끝의 가로폭 약 **화면 7~9%**. 5~6cm라는 바이블 값과 좁은 하퇴의 연결을 함께 본다. 실제 발의 물리적 크기는 네 개가 같다. |
| 원근 검수 | 서로 비슷한 깊이에 있는 두 앞발을 먼저 비교한다. 더 먼 뒷발이나 잘린 헤드와 화면 폭이 같아야 한다고 요구하지 않는다. 앞발 하나만 부풀거나 하퇴가 나팔처럼 벌어지면 탈락이다. |
| 과장 재발 시 | 높이·정면축을 유지하고 **1.7m·85mm**로 함께 옮겨 비슷한 프레이밍에서 깊이 방향의 확대 차이를 줄인다. 전신을 보이게 높이거나 측면으로 돌리는 해결은 금지한다. |

위 점유율은 설계값의 대략적 정합을 확인했다. 센서 가로 36mm, 16:9 유효 높이 20.25mm를 가정한 투영 근사에서 1.4m·70mm의 접지 깊이 화면 폭은 `1.4 × 36 / 70 = 0.72m`, 높이는 약 0.405m다. 따라서 5~6cm 발은 가로 약 6.9~8.3%에 해당한다. 1.7m·85mm도 폭은 약 0.72m다. 피치·실제 광학·크롭을 단순화한 근사이며, 생성 모델이 이 값을 물리적으로 재현한다는 보장은 아니다. **긴 렌즈만 쓰고 발 옆으로 바짝 붙는 방식은 원근 해결이 아니다.**

로케이션·스케일 바이블의 영문 두 문단은 아래 전문에 그대로 넣었다. 70cm는 몸통 외피만의 길이가 아닌 전체 길이이며, 40cm 높이·5~6cm 발·하퇴 약 1/4 관계는 기존 바이블의 기준이다. 발 치수와 3cm 돌출은 제조사 실측으로 새 인증한 숫자가 아니다. 돌은 넓은 보행면에 낮게 박혀 있어야 하며 받침대·협곡·원형 함몰로 커져서는 안 된다.

주광은 기존 월드 기준 “로봇 진행 전방 왼쪽의 낮은 태양 하나”를 유지한다. 정면에서 마주 보는 v4에서는 그 광원이 관측점 뒤쪽의 화면 오른쪽 방향에 놓인다. S1·S3의 태양 원반 위치를 배경으로 복제하지 않는다. 시점이 달라졌는데 태양을 이전 측면 화면의 같은 배경 위치에 놓으면 광원 연속성이 깨진다.

### 입력 슬롯

| 순서 | 사용할 파일 | 허용 권한·준비 상태 |
|---|---|---|
| S1 / Ref 1 | `keyvis/lib_thumbs/41-1548-seedance-03_lead_0.jpg` | 열린 낮은 분지의 큰 공간 구조만. 로봇 자세·배치·촬영 방향·태양 위치는 복제하지 않는다. 기존 v3 공간 앵커를 계승한다. |
| S2 / Ref 2 | 원본 `launch_render/charsheet3/front.png`에서 만들 **`keyvis/session1/S2_C-F.png` 예정판** | 정면 Go2의 외형·전체 비율·센서·다리 연결만. **현재 만들어졌다고 간주하지 않는다.** 하늘·격자·접지 그림자를 제거한 전신 마스크가 생성 전 조건이다. |
| S3 / Ref 3 | `keyvis/session1/S3_M39.png` | 대기색과 산란만. 태양 위치 권한은 없다. |
| S4 / Ref 4 | `keyvis/session1/S4_T44.png` | 모래·돌 표면만. 크롭 확대율을 돌 크기로 옮기지 않는다. |

S2의 원본 `front.png`를 직접 열었다. 머리부터 네 발끝까지 한 장에 있어 정면 외형과 작은 발 비율을 함께 전달할 수 있다. 원본 로봇 픽셀과 외곽을 보존하고, 다리 사이 배경도 지운 중성 단색 배경 판을 준비한다. 발끝이나 센서 돌출부를 깎지 않으며, 발 타이트 크롭·좌우 반전·몸통 늘이기는 하지 않는다. 원본의 정지 포즈는 동작 권한이 없다. 완성 마스크와 원본을 겹쳐 외곽·발끝·다리 사이를 검수한 뒤 첨부한다.

`launch_render/charsheet3/head_front.png`는 실제로 발끝이 잘려 있어 이번 S2로 부적절하다. 머리만 커지는 구도 유도도 불필요하다. `keyvis/session1/S2_C-QR.png`는 오른쪽을 향한 사선상이라 정면 지시와 충돌하므로 제외한다. C-foot 상세도 재투입하지 않는다. 후보6 역시 구도 입력으로 넣지 않는다. 기존 네 슬롯을 유지하고 S2만 정면 전신판으로 교체하며, 감독 스케치·프리비즈는 우선 옆 비교 자료로 쓴다.

### s03 v4 영문 전문

기존 세션의 16:9 정지 이미지 제작용 원고다. 본문·네거티브를 합한 **Python `len()` = 2797자**이며 공백·내부 줄바꿈·마지막 LF 한 개를 포함한다. 코드 펜스는 제외한다. 금지된 영문 두 단어는 네거티브를 포함해 0회다. 별도 공통 네거티브를 뒤에 더 붙이지 않는다.

```text
Photoreal cinematic still, 16:9: first right-forefoot contact in a frontal approach.

Ref 1: open basin/low relief only, not robots/viewpoint. Ref 2: frontal Go2 anatomy/proportions, not pose/background. Ref 3: haze color only. Ref 4: soil texture, not rock size. Preserve white housing, flush black front sensor strip and compact black lower sensor unit.

Use one broad, open, gently uneven dry basin with a continuous walkable floor of muted brown-gray compacted sand, embedded weathered stones, scattered gravel and shallow grooves; keep only low distant ridges. Local relief under the robots is a few centimeters, expressed by unequal foot contact heights and slight rigid-body pitch, never canyon walls, cliffs, craters, terraces or bedrock shelves. Pale sand-colored haze thickens with distance beneath one low warm sun, giving long textured shadows and neutral white highlights.

Keep adult Go2 proportions: about 70 cm overall length and 40 cm standing height, not a 70 cm chassis alone. Use small rounded black foot tips about 5-6 cm wide, roughly one quarter of a lower leg's length and much narrower than the head; all four feet have the same physical size.

Frontal ant-height viewpoint ahead of the lead, 8 cm above sand, 70 mm full-frame lens, 1.4 m from the landing foot, 2 degrees upward tilt. Legs and feet dominate; upper head/body crop at the top. Keep both connected forelegs visible. Travel is from depth toward the viewer, never sideways. The robot's right forefoot is at screen left; its ground contact is about 35% across and 75% down; each front tip spans about 7-9% of image width. No sole thrust toward the lens. Preserve markings without mirroring. Sun stays ahead-left in robot space, behind the viewpoint toward screen right.

The right forefoot has just seated on an embedded stone rising 3 cm above adjacent sand, with a clear contact edge, no gap or penetration. The other forefoot supports lower sand slightly farther back; a separate rear leg is mid-swing. The rigid body continues advancing over this support, not stopping or landing from a jump. A thin lateral windblown veil and a tiny fresh puff beside contact leave the foot readable. Behind the lead, same-facing Go2 rows approach through haze, visible between and beside its legs, never crossing sideways.

Exclude: tripods, photographic props, wire mesh, racks, cargo frames, fences, barriers; oversized/swollen/boot-like feet, flared lower legs, giant robot, macro feet, ultra-wide distortion; cliffs/pits/terraces/rock pedestal/parade road; extra/merged limbs, detached feet, altered/extra sensors; hovering, penetration, airborne contact foot; speed lines, sparks, trails, explosive dust, pre-contact eruption; weapons, victory poses, neon, glowing eyes, armor; added text/logos, watermarks, collage.
```

전문은 정면 접근·이미 닿은 오른앞발·진행 중인 몸통을 한 순간에 고정한다. 실제 운동 합격은 영상에서 따로 판정한다. 소품·철망은 별도 촬영 물건, 삼각대, 금속 망, 적재 프레임 등의 구체적 금지 표현으로 유지했다.

## s15b 판정과 수정 범위

**s15b도 정면 계열이 맞다.** s03과 닮게 만들기 위한 기계적 통일이 아니라, 직접 연 `keyvis/previs_frames/s15_1.png`와 `s15b_0.png`·`s15b_1.png`·`s15b_2.png`가 모두 전면 센서를 보이며 접근하는 대열을 보여주기 때문이다. 기존 s15b는 화면 오른쪽 가까운 다리가 잘리고 중심 대열도 크게 보이는 넓은 구도다. 이 프레임은 원하는 발 타이트나 마지막 정지가 완성됐다는 증거는 아니지만 정면 계열이라는 축은 분명하다.

v4 수정 방향은 s15의 감속을 정면에서 이어받아 같은 로봇의 마지막 오른앞발을 낮은 정면 타이트로 좁히는 것이다. 착지 직후 흡수가 끝나면 발·몸통·대열이 정지하고 낮은 잔먼지만 움직인다. s03은 디딘 뒤 계속 들어오고, s15b는 디딘 뒤 안정되어 남는다. 동일 접지를 앞뒤 컷에서 두 번 재생하지 않는다. 타이트 바깥 지지발의 상태는 s15와 후속 넓은 화면에서 확인한다.

기존의 “s15·s15b 우측, 머리 오른쪽”을 정면 계열로 바꾼다. S2 역시 정면 전신판을 쓰는 방향이며, 정확한 크롭·관절 위상·촬영 수치와 전문은 s03 v4 통과 후 결정한다. 별도의 고립된 받침돌을 엔딩 상징으로 추가하지 않는다.

기존 제작 설계가 우려한 s14 후방과 s16 정면의 관계는 s14에서 s15로 넘어가는 실제 경계에서 해결해야 한다. 그 우려만으로 확정된 s15·s15b를 측면으로 바꿀 수 없다. `s16_0.png`도 열었으나 원거리 정지판 하나만으로 로봇 상태·경로·최종 대형 구역까지 승인하지 않는다. s15의 기준 로봇·최종 돌·주변 열과 s16·s1718 구역의 실제 대응 확인은 후속 제작 작업이다.

## 스토리보드 §E에 넣을 원칙

**추가한다. 다만 “구도 참조로만”이라는 표현이 축을 선택적으로 버릴 수 있다는 뜻으로 읽히지 않게 다음 문장으로 명확히 한다.**

> 감독이 확정한 스케치와 프리비즈의 블로킹에서 진행축·시선 방향·IN/OUT·컷 간 운동 관계를 먼저 고정한다. 프리비즈는 구도와 블로킹의 기준으로 사용하되 평지 격자·임시 재질·잘못된 보행 위상·자막은 생성 결과에 옮기지 않는다. 원본 프레임을 모델에 업로드하지 않는다는 방침은 축 변경 허가가 아니다. 축 변경이 필요하면 바뀌는 컷과 앞뒤 연결을 감독에게 제시해 별도 승인받는다.

§E의 s03 행은 “낮은 시점의 인상만”에서 **“정면 접근·다리 중심·화면 앞으로 들어오는 첫 디딤을 고정”**으로 바꾼다. s15·s15b 행의 “새 오른측 접점”은 **“기존 정면 계열을 유지한 최종 접점·정지 타이트”**로 바꾼다. 기존 컷표·참조 기록·영문 전문의 횡단·우측 고정 문장도 같은 기준으로 정정해야 한다. 이 문서에서는 정정안만 제시하며 해당 파일들은 수정하지 않았다. 다른 컷까지 모두 정면으로 바꾸자는 규칙은 아니다.

## 인계와 검수

v4 첫 판은 스케치와 s02·s04 사이에 놓고 **정면 IN과 발 중심 구도가 맞는지 먼저** 본다. 다음으로 앞발 해부학·전체 물리 비율, 낮은 박힌 돌과 접지, 같은 방향의 후경 대열, 분지·광원·금지 소품을 확인한다. 이 순서를 통과한 뒤에만 K03 후보로 두고, 영상에서 한 번의 접지·계속 전진·먼지 발생 순서를 검수한다. 기술 항목을 모두 만족해도 측면으로 돌아가면 즉시 불통과다.

직접 연 이미지 18장은 위 판정표의 7장, 참조 비교 6장(S1·S3·S4·front·head_front·C-QR), s15·s15b 4장, s16 시작 1장이다. 프리비즈는 제공된 PNG로 확인했고 원본 영상의 정상속도 재생·월드 변환값 재측정은 하지 않았다. `scenario_artifact.html`의 텍스트에서도 s03이 “첫 발걸음이 카메라로”라는 의도임을 확인했으며, 내장 영상은 재생하지 않았다.

산출물은 이 파일 하나다. 새 이슈·PR·참조 이미지·폴더는 만들지 않았다. 남은 실행은 S2 정면 마스크 준비, v4 생성과 감독 판정, 통과 후 s15b 전문 및 기존 설계 문서 정정이다.

### 독립 검증 기록

`codex exec --model gpt-6-astra -c model_reasoning_effort=high`로 읽기 전용 검증을 두 차례 수행했다. 1차는 이미지 18장과 원문을 직접 대조하여 제작 내용의 차단 지적 없음으로 판정했고, 접지점 좌표의 표현과 검증 범위 밖 작업 기록 두 곳을 보완 권고했다. 좌표를 한글·영문 모두 접점 기준으로 명확히 하고 해당 작업 기록을 삭제한 뒤 2차를 진행했다.

2차는 수정 주장을 믿지 않고 최종 파일에서 두 보완의 반영을 확인했으며, 영문 2,797자·금지 영문 두 단어 각각 0회·바이블 두 문단 각각 1회 동일 삽입·접점 세로 위치 약 74.45%를 직접 재계수해 **최종 차단 지적 없음·내부 제작안 전달 가능**으로 판정했다. 2차는 문구·수치 검증으로 이미지를 다시 열지 않았다. 두 판정 모두 실제 v4 생성 성공이나 영상 동작의 합격을 뜻하지 않는다.
