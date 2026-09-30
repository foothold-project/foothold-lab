# Go2 캐릭터 시트 Sunburst 요청

> 분류: 계획
> 작성: Codex · 2026-09-30 22:20
> 근거: 사용자 단일 재시도 지시 · Higgsfield 모델 설정과 사전 견적
> 요지: 공식 자료 3장을 입력해 Sunburst로 한 번만 요청한 프롬프트와 설정을 보존한다.
> 상태: 생성 완료 · 4방향 시트 후보 · 사용자 최종 승인 전

설정: GPT Image 2.5 · Sunburst · 2K · high · 3:2 · 1장. 사전 견적 2.75크레딧. 추가 생성은 승인되지 않았다.

## 결과와 직접 검토

[생성된 4방향 캐릭터 시트](assets/go2-reference/go2-character-sunburst-v1.png) · [공식 원본과 함께 보는 HTML](output/FOOTHOLD-Go2-character-sheet.html)

`확인됨` 정면·측면·후면·사선 전신이 한 장에 나왔다. 첫 Nano Banana 결과의 별도 머리와 중복 전면 센서 오류는 보이지 않는다. 완성 응답의 모델명도 요청과 같은 `gpt_image_2_5`다. 단, 실제 제품 형상 전체를 검증한 결과는 아니다. 발끝 마모와 후면 그릴 세부는 원본과 동일하다고 확인할 수 없어 생성 해석으로 관리한다. 한 건만 실행했고 추가 재시도는 하지 않았다.

## 입력 이미지 순서

1. [공식 측면 전신](assets/go2-reference/side-walk.png): 전체 비율과 다리 형태의 우선 기준.
2. [공식 정면 렌더](assets/go2-reference/front-render.jpg): 몸통 전면의 센서 배치. 별도 머리가 아님.
3. [공식 후면 보행](assets/go2-reference/rear-walk.png): 뒷몸통과 관절. 주변 인물·그래픽 제외.

## 복사용 프롬프트

```text
Create a faithful photographic product turnaround sheet of the EXACT real Unitree Go2 shown in the three official references. This is identity reconstruction of an existing manufactured robot, NOT designing a quadruped or adding features.

REFERENCE PRIORITY:
Reference 1 is the complete real Go2 SIDE VIEW and is the master for the entire silhouette, body-to-leg proportions, components and materials.
Reference 2 is the official FRONT product render, showing the front end of that SAME horizontal torso. It is a close-up, not a separate head or accessory.
Reference 3 is a real REAR walking view, used only to determine rear shell, hip housings and visible central rear details. Ignore the person, grass and colored sensor graphics.

CRITICAL REAL GO2 ANATOMY:
One low elongated horizontal gray torso, with the front camera/lamp panel integrated into its downward-curving FRONT END. There is NO head perched above the body, NO neck, NO additional upper sensor box, NO duplicate face.
The black rounded LiDAR housing is directly UNDER the front end of the torso, exactly as reference 1.
Four slim curved solid leg links with large round upper motor housings, small knee joints and small rounded black rubber foot tips. Match the real solid leg surfaces: no invented open trusses, no elongated exposed rods, no thick boots, no hooves. Preserve actual stance height and torso length; do not stretch it taller or make it toy-like.
No added modules, tail, backpack, arm or armor. Do not invent rear grille assemblies or dangling rear mechanisms. Refer to the actual rear photograph.

DELIVERABLE:
One landscape 3:2 reference sheet containing four clearly separated full-body views in a simple 2x2 layout: FRONT, LEFT SIDE (robot facing right as reference 1), REAR, FRONT THREE-QUARTER. The SAME robot in a neutral relaxed four-foot standing stance across all views, consistent physical scale and proportions, camera near torso height, long lens with minimal perspective distortion for front/side/rear, every foot visible. Render naturally occluded legs correctly, never add limbs to force all legs visible.
Plain warm light-gray seamless background, soft neutral studio illumination, subtle contact shadows. Real matte gray polymer/metal surface with restrained microtexture and realistic small fasteners, no chrome, HDR gloss or weathering.
Only four small English view labels. No detail insets, no specification text, no decorative interface, no arrows or dimension lines. Faithful real-product anatomy takes absolute priority over prettiness or invented detail.
```

작업 ID: `35542b56-3446-4bf4-8538-c738c3376e5b`. 요청 원문과 설정은 [JSON](assets/go2-reference/sunburst-generation.json)에 보존한다.

사용자가 웹의 Nano Banana Pro 가격을 2K 2크레딧, 4K 4크레딧으로 확인했다. 동일 해상도의 MCP 사전 견적과 같으므로 현재 확인한 조건에서는 경로별 가격 차이가 없다.
