# 세션 1 재설계 · 단일 분지, 작은 발, 같은 진행축

> 상태: 생성 전 내부 제작안. 기존 5장 모두 불통과. 새 이미지 생성·참조 편집은 수행하지 않음.
> 근거: session1-redesign-brief.txt 전체, 기존 스토리보드의 공통 규칙과 13개 b컷 전문, s03-fix.md·s03-compress.md, 아래 직접 열람 기록.
> 수치 구분: 공식 전체 치수 외 발 치수·지면 단차·카메라 값은 제작용 목표다. 결과 화면의 실제 길이·하중·속도를 측정한 값이 아니다.

**기존 5장은 모두 폐기 판정을 유지한다. 새 시도는 발 상세 참조를 빼고, 넓은 분지 전체를 공간 참조로 넣고, 카메라를 높여 뒤로 물린다.** 작은 디딤은 그대로 두되 발과 돌을 확대해 강조하지 않는다. 가까운 차체 전체와 넓게 이어지는 땅이 크기의 기준이 된다.

## A. 직접 열람 판정과 기존 분석 수정

파일 이름은 `keyvis/session1/results/` 아래다. 방향은 주 로봇의 머리 위치로 판단했다. 정지 화면이므로 실제 이동 방향·접지 하중·미끄러짐·첫발 시점은 확인하지 못한다.

| 결과 | 화면에서 확인한 문제 | 판정 |
|---|---|---|
| `s03_cand1_screen.jpg` | 머리는 왼쪽. 전경 발과 아래다리가 커 보이고 차체 상부가 잘렸다. 별도 원통 렌즈·매달린 장비, 지평선의 흰 울타리가 생겼다. 이 화면을 협곡이라고 부르면 부정확하다. | 불통과 |
| `s03_cand2_screen.jpg` | 머리는 왼쪽. 접지발이 두껍고, 작은 돌의 디딤 뒤로 큰 원형 함몰과 층진 턱이 이어진다. 발 주변만의 낮은 요철을 넘어 다른 지형이 됐다. | 불통과 |
| `s03_cand3_screen.jpg` | 주 로봇만 오른쪽. 접지발이 크게 부풀고 아래다리가 넓게 벌어진다. 발 옆 흰 속도선과 큰 함몰·층진 턱이 보인다. 후경 로봇은 왼쪽을 향해 주 로봇과도 엇갈린다. | 불통과, K03 승격 금지 |
| `s03_cand4_screen.jpg` | 머리는 왼쪽. 발끝 자체는 후보 2·3보다 작고 헤드만 하다고 보기 어렵다. 그러나 과장된 전경 차체, 깊은 구덩이와 큰 자갈 더미, 뒤의 단차가 남는다. | 불통과, K03 승격 금지 |
| `s15b_cand1_screen.jpg` | 주 로봇은 왼쪽. 전경 접지발이 다른 발보다 과대하며, 받침돌·층진 암반·깊은 함몰·높은 분지 벽이 공간을 갈라놓는다. 일부 후경 개체는 반대 방향이다. | 불통과 |

| 기존 분석 | 동의·수정 |
|---|---|
| ① 5장 모두 발끝이 헤드만 함 | **문제의 방향에는 동의, 일괄 크기 묘사는 수정.** 후보 3·s15b의 부풀림이 특히 분명하고, 후보 4는 발끝보다 구도·지형·방향 문제가 크다. 서로 다른 깊이의 발과 헤드의 화면 폭을 실물 치수비로 취급하지 않는다. S1 상세 이미지, 낮은 시점, 가까운 거리와 광각이 함께 크기 과장을 유도했을 가능성은 `추측`이다. 원인을 분리한 실험은 하지 않았다. |
| ② 단일 로케이션 스펙이 없었음 | **공간 불일치에는 동의, '없었다'는 수정.** 기존 스토리보드 0절에는 넓은 건조 분지·낮은 돌출·협곡 금지와 39/44 앵커가 이미 있다. 그러나 실제 입력은 M39 대기 조각과 T44 재질 조각뿐이었고, 전체 지형을 지정할 이미지 권한이 없었다. v2의 `rock shelves / hollows / gravel mounds`가 구덩이·단층으로 커졌다는 해석은 유력한 `추측`이다. 후보 1의 시설 울타리와 나머지 후보의 지질 과장을 구분한다. |
| ③ 5장 중 4장이 왼쪽 | **주 로봇의 방향 기준으로 확인됨.** 오른쪽은 후보 3뿐이다. 다만 텍스트가 언제나 무효라고 입증된 것은 아니다. 실제 S2_C-Q는 왼쪽을 향했고, 입력과 문장이 충돌했다. 오른쪽을 향한 정품 시점과 명시적인 앞·뒤 위치를 일치시키는 것이 이번 변경이다. |

## B. 단일 로케이션 바이블

44는 낮은 보행면에 전경 큰 돌이 일부 있고, 39는 넓은 바닥과 대열 사이 통로가 보인다. 42에는 가까운 얕은 홈, 43에는 낮게 박힌 돌과 이어지는 대열이 있다. 41은 이들을 묶는 넓은 분지 바닥을 가장 명확히 보여주며, 46은 같은 계열의 낮은 기복과 먼 대열을 보여준다. **고립된 큰 돌이나 먼 낮은 능선까지 지우는 것이 아니라, 그것들을 연결해 거대한 벽·원형 함몰·계단식 암반을 만드는 것을 막는다.**

모든 b컷에 아래 **세 문장 전체를 그대로 삽입**한다. s12·s13의 폭풍은 이 장소에서 대기 가시성만 바꾸는 사건이다. 해당 컷의 먼지 문장이 가까운 가시성을 추가로 규정해도 땅과 광원 방향은 바꾸지 않는다.

```text
Use one broad, open, gently uneven dry basin with a continuous walkable floor of muted brown-gray compacted sand, embedded weathered stones, scattered gravel and shallow grooves; keep only low distant ridges. Local relief under the robots is a few centimeters, expressed by unequal foot contact heights and slight rigid-body pitch, never canyon walls, cliffs, craters, terraces or bedrock shelves. Pale sand-colored haze thickens with distance beneath one low warm sun, giving long textured shadows and neutral white highlights.
```

접지석은 **주변 지면에서 약 3cm만 드러난 박힌 돌**을 이번 s03·s15b의 목표로 삼는다. 여러 접점의 높이 차와 작은 차체 피치가 보이면 충분하다. 이 3cm는 연출 설계값이며 라이브러리에서 실측한 수치가 아니다. 거대한 발판이나 매끈한 길 하나를 만들지 않고, 모래·자갈·작은 돌이 실제 발 사이와 중경에 이어져야 한다.

빛은 같은 월드 진행축 +X, 진행 전방 왼쪽의 낮은 태양 하나로 고정한다. s03·s15b의 우측 관측에서는 화면 오른쪽 위, s12~14의 후방 추종에서는 전방 왼쪽으로 보이게 한다. 모든 시점에서 태양을 화면의 같은 쪽에 억지로 붙이지 않는다.

## C. 스케일 바이블과 참조 교체

**'몸통 길이 약 70cm'를 '서 있는 Go2의 전체 길이 약 70cm'로 고친다.** 공식 제품 페이지는 서 있는 전체 외형을 70 × 31 × 40cm로 제시한다. 이를 몸통 외피만의 길이로 지시하면 긴 차체가 만들어질 수 있다. [Unitree Go2 공식 기계 사양](https://www.unitree.com/go2/)

발 지름 5~6cm와 하퇴 길이의 약 1/4은 **이번 브리프가 제시한 제작용 근사값**으로 쓴다. 공식 제조 치수나 이번 실측값으로 인증하지 않는다. 원근을 줄인 참조에서 보이는 작은 둥근 끝, 좁은 하퇴와의 연결, 헤드보다 훨씬 작은 비율을 함께 확인한다.

```text
Keep adult Go2 proportions: about 70 cm overall length and 40 cm standing height, not a 70 cm chassis alone. Use small rounded black foot tips about 5-6 cm wide, roughly one quarter of a lower leg's length and much narrower than the head; all four feet have the same physical size.
```

- **S1_C-foot.png는 이번 v3의 두 컷에서 모두 제외한다.** 기존에도 'shape only'라고 썼는데 과장이 반복됐다. 상세 이미지의 큰 화면 점유율을 문장 하나로 무효화할 수 있다고 가정하지 않는다.
- 향후 발 형태만 따로 고쳐야 할 때의 제한 문구는 `Shape only, tiny scale: retain the rounded rubber-tip contour, but derive every dimension from the full-body Go2 reference; never inherit this crop's magnification.`이다. 이번 두 전문에는 이 이미지를 첨부하지 않으므로 이 문구도 넣지 않는다.
- 스케일 네거티브는 `oversized, swollen, bulbous, boot-like or head-sized feet; flared lower legs; giant robot; macro foot view; ultra-wide distortion`로 통합한다. 올바른 발도 화면 가까이 오면 커질 수 있으므로, 네거티브와 함께 **높이 30cm·65mm·약 2.3m 거리**를 적용한다. 렌즈 이름만 바꾼 채 발 옆 초근접 거리를 유지하지 않는다.
- v3는 원래 발 타이트보다 넓은 범위에서 머리·차체·연결된 다리를 함께 보여준다. 더 타이트한 편집이 필요해도 이 정상 비율이 통과한 뒤 다룬다. 이번 확대 억제값은 생성 성공을 보장하는 물리 카메라 설정이 아니라 이미지 모델에 줄 구체적 설계다.

### 두 컷 공통 S1~S4

이 표의 슬롯 번호와 D절의 Ref 번호가 일치한다. 네 장을 아래 순서로 넣는다. S1을 비워 첨부 순서가 당겨지는 방식은 쓰지 않는다.

| 슬롯 | 정확한 기존 파일 | 이번 권한 |
|---|---|---|
| S1 | `keyvis/lib_thumbs/41-1548-seedance-03_lead_0.jpg` | 분지 전체의 개방감·낮은 바닥 기복. 로봇 외형·자세·배치·카메라는 복제하지 않는다. 발 상세 슬롯을 실제 공간 앵커로 교체한다. |
| S2 | `keyvis/session1/S2_C-QR.png` | Go2 전체 비율·센서·실제 오른쪽을 향한 외형. 아래 마스크 복구 조건을 충족한 판을 사용한다. 자세·회색 배경은 복제하지 않는다. |
| S3 | `keyvis/session1/S3_M39.png` | 대기색과 산란. 태양의 화면 좌우는 이 크롭을 복제하지 않고 컷의 월드 광원으로 정한다. |
| S4 | `keyvis/session1/S4_T44.png` | 모래·자갈·돌의 표면 성질. 이 조각의 확대율을 돌의 크기로 옮기지 않는다. |

위 모든 상대 경로의 기준은 아래다.

`C:/Users/AI-WS01/AppData/Local/Temp/claude/C--Users-AI-WS01-Desktop-jay----------foothold-lab/85e9e940-5633-48ed-a407-2d9aafc96e93/scratchpad/`

S1은 실제 존재하는 **640×360 확인용 프레임**이므로 공간의 큰 구조에만 쓴다. 최종 납품 이미지나 로봇 세부 증거로 쓰지 않는다. 이전 '41은 사람 비교만' 정책을 이번에는 공간 권한에 한해 변경한다. 44/39/42/43의 지질을 버리고 41의 모든 것을 복제하는 변경은 아니다.

**S2_C-QR 방향은 채택, 현재 마스크는 복구 후 사용.** 원본 `launch_render/charsheet3/q34r.png`와 마스킹판을 각각 열어 머리가 오른쪽이며 측면 표식이 기존 왼쪽 참조의 단순 반전과 다름을 확인했다. 다만 마스킹판의 등 윗선과 후부 패널 일부가 회색 배경으로 깎여 원본의 온전한 실루엣이 남지 않았다. 생성 담당자는 원본 로봇 픽셀을 보존해 **같은 지정 파일 S2_C-QR.png**의 마스크를 복구하고 재대조한 다음 사용한다. 결함 있는 마스크를 'intact'라는 프롬프트로 고치게 하지 않는다. 원본 전체의 격자·접지 그림자를 대신 업로드하지 않는다. 이번 워커는 이 파일을 수정하지 않았다.

브리프가 말한 Isaac 렌더 yaw 315와 비반전 제작 과정은 제공 정보다. 여기서는 두 이미지의 외형과 방향을 확인했으며 렌더 로그·카메라 변환값까지 재검증한 것은 아니다.

## D. s03·s15b v3 전문

각 블록 하나에 본문과 모든 네거티브가 들어 있다. B·C의 영문을 이미 포함했으므로 밖에서 다시 붙이지 않는다. 모델·화면비는 기존 세션의 Seedream 4.5·16:9를 유지하는 제작 지시이며 현 웹 UI의 지원 한도는 이번에 재검증하지 않았다. S2 마스크 복구는 아래 입력의 실행 전 조건이다.

### s03 v3 · 첫 지지, 아직 진행 중

```text
Photoreal cinematic still, 16:9: the first right-forefoot contact during continued walking.

Ref 1 sets basin openness and low relief only, not robots or camera. Ref 2 sets intact Go2 proportions, sensor anatomy and right-facing orientation, not its standing pose or gray background. Ref 3 sets haze color; Ref 4 sets soil texture only, not rock size. Keep the white housing, flush black front sensor strip and black cage beneath.

Use one broad, open, gently uneven dry basin with a continuous walkable floor of muted brown-gray compacted sand, embedded weathered stones, scattered gravel and shallow grooves; keep only low distant ridges. Local relief under the robots is a few centimeters, expressed by unequal foot contact heights and slight rigid-body pitch, never canyon walls, cliffs, craters, terraces or bedrock shelves. Pale sand-colored haze thickens with distance beneath one low warm sun, giving long textured shadows and neutral white highlights.

Keep adult Go2 proportions: about 70 cm overall length and 40 cm standing height, not a 70 cm chassis alone. Use small rounded black foot tips about 5-6 cm wide, roughly one quarter of a lower leg's length and much narrower than the head; all four feet have the same physical size.

Camera on the robot's right, 30 cm high, 65 mm full-frame lens, about 2.3 m away, near side view with slight front visibility. Keep the head, rigid body and all connected legs in frame; the robot occupies roughly half the image width. Head and front sensor at screen right, rear at screen left; preserve real right-side markings, never mirror. Keep the near right forefoot beneath the front body, away from the lens. Sun at upper right, ahead-left in the robots' world.

The small right forefoot has just seated on a partly buried stone rising 3 cm above nearby sand. A second connected foot supports the lower sand; leg flexion and slight body pitch match this modest difference. Show a clean contact edge with no gap or penetration. The body is advancing over this support; another foot is mid-swing. A thin lateral windblown veil and a smaller fresh puff beside the planted foot leave the contact visible. Distant Go2s continue rightward; no final halt.

Exclude: oversized, swollen, bulbous, boot-like or head-sized feet; flared lower legs; giant robot; macro foot view, ultra-wide distortion; left-facing principal robot, mirrored markings; cliffs, craters, layered ledges, deep pits, isolated rock pedestal, flat parade road; fences, white barriers; extra or merged limbs, disconnected feet, changed sensors, added cameras; hovering supports, rock penetration; speed lines, sparks, motion trails, dust explosion, opaque dust; weapons, victory poses, neon, glowing eyes, armor; text, invented logos, watermarks, collage. No airborne principal foot, pre-contact dust or whole-body landing.
```

문자 수: **2839자**. Python `len()`으로 공백·내부 줄바꿈·마지막 LF 1개를 포함해 계산했다. 코드 펜스와 이 설명은 제외했다.

### s15b v3 · 마지막 제동 뒤 안정

```text
Photoreal cinematic still, 16:9: the final braking contact has settled into quiet support.

Ref 1 sets basin openness and low relief only, not robots or camera. Ref 2 sets intact Go2 proportions, sensor anatomy and right-facing orientation, not its standing pose or gray background. Ref 3 sets haze color; Ref 4 sets soil texture only, not rock size. Keep the white housing, flush black front sensor strip and black cage beneath.

Use one broad, open, gently uneven dry basin with a continuous walkable floor of muted brown-gray compacted sand, embedded weathered stones, scattered gravel and shallow grooves; keep only low distant ridges. Local relief under the robots is a few centimeters, expressed by unequal foot contact heights and slight rigid-body pitch, never canyon walls, cliffs, craters, terraces or bedrock shelves. Pale sand-colored haze thickens with distance beneath one low warm sun, giving long textured shadows and neutral white highlights.

Keep adult Go2 proportions: about 70 cm overall length and 40 cm standing height, not a 70 cm chassis alone. Use small rounded black foot tips about 5-6 cm wide, roughly one quarter of a lower leg's length and much narrower than the head; all four feet have the same physical size.

Camera on the robot's right, 30 cm high, 65 mm full-frame lens, about 2.3 m away, near side view with slight front visibility. Keep the head, rigid body and all connected legs in frame; the robot occupies roughly half the image width. Head and front sensor at screen right, rear at screen left; preserve real right-side markings, never mirror. Keep the near right forefoot beneath the front body, away from the lens. Sun at upper right, ahead-left in the robots' world.

The near right forefoot rests on a partly buried stone rising 3 cm above adjacent sand. All four feet are grounded, with separate readable legs and support edges at slightly different local heights. Joint flexion matches the terrain; the rigid body has settled with only slight pitch. No continued stride or swing. Behind it, two or three separate Go2s and farther rows have also settled, all facing right. Low residual dust lies beside planted feet. Collective stillness conveys weight.

Exclude: oversized, swollen, bulbous, boot-like or head-sized feet; flared lower legs; giant robot; macro foot view, ultra-wide distortion; left-facing principal robot, mirrored markings; cliffs, craters, layered ledges, deep pits, isolated rock pedestal, flat parade road; fences, white barriers; extra or merged limbs, disconnected feet, changed sensors, added cameras; hovering supports, rock penetration; speed lines, sparks, motion trails, dust explosion, opaque dust; weapons, victory poses, neon, glowing eyes, armor; text, invented logos, watermarks, collage. No descending principal foot, lifted supports, synchronized landing, continuing trot, kneeling or damage.
```

문자 수: **2878자**. 계산 기준은 s03과 같다. 두 블록 모두 2,900자 이하이며 별도 네거티브를 덧붙이지 않는다.

s03은 이미 닿은 오른앞발을 중심으로 다음 지지로 진행하는 순간이고, s15b는 네 발의 지지가 끝난 순간이다. 같은 정상 비율과 지질을 쓰더라도 발의 사건은 합치지 않는다. s15·s15b는 같은 최종 접점·주변 열로 맞추며, s16·s1718의 실제 군집 구역과의 대응이 확인되기 전에는 **룩·동작용 잠정판**이다.

## E. 나머지 b컷 11개에서 교체할 문장

전문 재작성은 하지 않는다. 공통으로 기존의 지형·빛 설명을 B의 동일 영문으로 교체하고, 로봇이 나오는 컷에는 C를 넣는다. C-foot 참조와 해당 Ref 역할을 제거할 때에는 실제 첨부 순서에 맞춰 번호를 다시 매긴다. 표의 문장은 컷별 추가 교체분이다.

**방향 공통:** 같은 월드 +X를 유지하되 우측 관측에서는 화면 오른쪽, 후방 추종에서는 카메라에서 멀어지는 방향, 정면 원경에서는 카메라 쪽 접근으로 보인다. 모든 컷을 'screen right'로 통일하지 않는다. 정면은 C-F, 후면은 C-B, 우측 사선은 복구한 C-QR처럼 실제 뷰를 맞추고, 이미지 반전으로 바꾸지 않는다.

| 컷 | 교체·추가할 문장과 적용 위치 |
|---|---|
| s01 | `Look across the continuous low basin floor, with scattered embedded stones and only low distant ridges; show no robots.`로 'look across a low rock shelf', 'geological scale', 모래 능선 강조를 교체한다. B를 넣되 C의 로봇 치수 문장은 넣지 않아 빈 땅을 유지한다. 공간 참조는 새 자유 지형이 아니라 위 라이브러리 분지를 따른다. |
| s02 | `The distant formation approaches the camera along the shared world axis; preserve tiny silhouettes rather than enlarging feet for detail.`을 추가한다. 기존 0.5~1.5% 원경 기능은 유지하고, K01이 B에 맞지 않으면 공간 참조로 넘기지 않는다. |
| s04 | `Preserve K02's exact camera, foreground stones and low basin horizon; advance along the same approach axis without zooming or changing geology.`로 같은 원경 복귀를 고정한다. K02 자체가 B·C에 통과한 경우만 계승한다. |
| s06 | `Show the formation approaching obliquely along the shared axis; near supports differ by only a few centimeters over embedded stones and shallow grooves.`로 'low bedrock lips'를 교체한다. 정면에 가까운 사선과 원래 넓은 대열 구도를 유지하고, 큰 앞발로 험지 반응을 보충하지 않는다. |
| s10 | `Observe from outside the legs at 25-30 cm height, with a 50-65 mm lens and enough distance to retain connected body proportions; one foot rests on a small embedded stone while another clears a shallow groove.`로 'ant-height', 5~8cm·24~28mm, 'bedrock lip'을 교체한다. 우측 관측·머리 오른쪽을 명시하고 발 상세 슬롯은 전체 로봇과 공간 앵커로 바꾼다. |
| s10b | `Stay on K10's right-side camera axis at 25-30 cm height with a 50-65 mm lens; keep the passing limb at the outer edge without enlarging its foot.`로 8~12cm·28~35mm 문장을 교체한다. 스윙발은 작은 돌을 넘고 별도 지지발은 낮은 모래에 남으며, K10의 수정된 스케일·지형·방향만 계승한다. |
| s11 | `Orbit the camera around the same straight-moving formation; keep robot headings fixed in world space and preserve the low continuous basin floor.`를 추가한다. 'sand ridges'는 낮은 자갈·얕은 홈으로 교체하고, 카메라 선회를 로봇들의 제각각 방향 전환으로 번역하지 않는다. 선택한 시점에 맞는 실제 뷰의 참조를 쓴다. |
| s12 | `Keep the lens foreground clear in the same low basin; R-A moves away along +X, L-A remains a low embedded stone on the left, and the sun stays forward-left.`로 공간·방향을 고정한다. 원래의 유한한 먼지 띠와 접근 전 맑은 지면을 유지하며 돌의 크기로 폭풍의 위협을 키우지 않는다. |
| s13 | `Inside that same band, preserve K12's basin, R-A, L-A, camera and heading; the dust gap reveals small unequal support heights, not a new trench or rock wall.`로 가시성 문장을 보강한다. 후면 외형과 앞왼쪽 산란광을 유지하고, 새 분지·새 폭풍·정면 주인공을 만들지 않는다. |
| s14 | `Continue away along the same corridor with R-A ahead and L-A on the same side; shorten the stride over centimeter-scale relief before the final forefoot contact.`로 감속을 한정한다. 중앙 한 줄과 주변 보조열, 폭풍 출구의 기존 지질을 유지한다. 완전 정지나 거대한 발판을 앞당기지 않는다. |
| s15 | `Match the approved K15b right-side camera, 30 cm height, 65 mm lens, body scale and same partly buried stone; the small right forefoot is beginning its final short swing toward that still-empty contact.`로 기존 15~25cm·35~50mm와 발 타이트 문장을 교체한다. 머리 오른쪽·앞왼쪽 월드 광원·미래 접점의 먼지 없음, s16·s1718 구역 대응 조건을 유지한다. |

## F. 재사용 금지와 다음 판정

**후보 3의 속도선을 지우거나 후보 4의 방향만 고쳐 K03로 승격하지 않는다. 두 장 모두 K03 아님. 기존 5장 전부 캐릭터·스케일·지형·무드·후속 컷의 이미지 참조로 재사용하지 않는다.** 불통과 이유를 비교하는 검토 증거로만 남긴다. 일부 룩이 마음에 들더라도 승인 참조는 원래의 39/44 계열에서 가져온다. 현재 승인 K03·K15b가 생겼다고 기록하지 않는다.

다음 생성은 복구한 S2와 D절로 s03·s15b를 한 장씩 확인하는 순서다. 접촉선만 보지 말고 다음 항목을 함께 판정한다.

- 같은 분지의 바닥이 전경부터 중경까지 이어지는가. 깊은 함몰·층진 턱·고립된 받침대가 생기면 탈락.
- 같은 로봇의 다른 발과 비교했을 때 전경 발 하나만 부풀거나 하퇴가 나팔처럼 벌어지는가. 헤드와의 단순 화면 폭만으로 실물 비율을 재지 않는다.
- 주 로봇과 주변 로봇의 앞·뒤가 같은 진행축에 맞고 실제 오른측 외형이 남는가. 표식 반전·추가 센서·잘린 마스크 외곽이 생기면 탈락.
- s03의 진행 중 지지와 s15b의 정지 완료가 구별되는가. 정지 그림만으로 실제 보행·하중 검증이 끝났다고 쓰지 않는다.

### 이번 직접 확인 범위

이미지 도구로 개별 파일 **17장**을 열었다: 결과 5장, 기존 S1_C-foot·S2_C-Q·S3_M39·S4_T44 4장, 새 S2_C-QR와 원본 q34r 2장, 라이브러리 44·39·42·43·41·46의 브리프 지정 프레임 6장이다. 라이브러리 프레임은 제공된 축소 JPG이며 이번에 원본 MP4를 디코드하거나 정상속도 재생하지 않았다.

산출물은 지정된 이 Markdown 하나다. 새 폴더·저장소·참조 이미지를 만들거나 수정하지 않았다. 이번 저장소 수정 금지 지시에 따라 git pull·이슈 생성·브랜치 작업도 하지 않았다. 남은 제작 작업은 S2 마스크 복구, 실제 v3 생성, 감독의 결과 판정과 결말 구역 정합 확인이다.

### 독립 검증 기록

`codex exec --model gpt-6-astra -c model_reasoning_effort=high`로 읽기 전용 검증을 두 차례 수행했다. 1차는 브리프·본문과 이미지 17장을 직접 대조하고 A~F 충족·차단 지적 없음으로 판정했으며, s10의 발과 돌 관계를 나타내는 영어 한 곳을 고치라고 권고했다. 이를 `rests on`으로 수정한 뒤 2차가 실제 문장을 다시 읽고 수정 여부, 두 전문의 2,839자·2,878자, B·C 동일 삽입, E의 11컷을 직접 재계수해 **최종 내부 제작안 전달 가능·차단 지적 없음**으로 판정했다. 2차는 문구 수정과 문서 구조 검증이며 이미지를 다시 열지는 않았다. 이 검증은 실제 v3 이미지의 성공이나 S2 복구 완료를 뜻하지 않는다.
