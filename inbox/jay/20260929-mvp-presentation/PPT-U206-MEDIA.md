# U206 발표 어셋·영상 위치와 사용 판단

> 분류: 리서치
> 작성: 오흥재 · 2026-10-02 03:35
> 근거: 현재 HTML · MVP 정본 · 로컬 영상 디코딩 · 원본 기획발표 HTML · 3DGS PoC 결과
> 요지: 새로 만들기 전에 재사용할 실험·지형·트윈·클로징 원본을 확인
> 상태: 조사 완료 · 편집 미실행
> 판: v1.0

관련 작업 #490. 경로는 저장소 루트 기준이다. 새 이미지·영상 생성, 다운로드, HTML 수정은 하지 않았다. 아래 `확인됨`은 파일 존재, PyAV 메타데이터, 문서·코드 또는 지정 시점의 실제 프레임으로 확인한 범위를 뜻한다. 성공률은 보고서 값을 전부 재집계한 것이 아니다. 실제 프레임 검토는 메모리 안에서 수행했다.

## 1. 성과·실패를 보여줄 영상

공식 보고서: `docs/research/20260928-v2-mvp-report.md` §4-0, §13. 영상 정본 묶음은 `docs/assets/video/v2/`. 제출본은 `inbox/jay/20260929-mvp-submission/source/media/`에 있다. 아래 파일명의 `{nvidia,v1,v2}`는 세 파일을 각각 뜻한다.

| 용도 | 파일 | 무엇을 보여주는가 | 확인 범위·편집 판단 |
|---|---|---|---|
| NVIDIA부터 최종 정책까지 | `docs/assets/video/v2/hero-floatingring-v15-{nvidia,v1,v2}.mp4` | 같은 floating_ring·1.5 m/s. 보고서 100판 종합 성공률 0→87→99%. | 파일 길이 4.00 / 3.80 / 3.72초 실측. 현재28쪽 사용 중. 세 판의 개별 영상은 서로 다른 길이이므로 마지막 프레임 고정 또는 공통 타임라인 처리 필요. |
| ring 외에 직관적인 개선 | `docs/assets/video/v2/hero-pit-v15-{nvidia,v1,v2}.mp4` | pit·1.5 m/s. 보고서 0→100→100%. NVIDIA는 단차 가장자리에서 몸이 낮아지고 전진이 막히며, v2는 건넌다. | NVIDIA·v2의 0.2초, 약1.3초, 약2.5초, 마지막 직전 프레임 직접 확인. 길이4.00 / 3.74 / 3.68초. **추천 전체 0초부터 각 끝까지**. v1 이후 추가 향상 사례로 설명하지 않는다. |
| 실패가 다음 실험을 정한 이유 | `docs/assets/video/v2/lineage-gap-v1.mp4`, `lineage-gap-D-fail.mp4`, `lineage-gap-v2.mp4` | 명령을 연 후보 D에서 gap 능력이 퇴행한 계보. 정본의 전진거리5.68 / 0.99 / 5.87m와 연결된다. | 현재18~19쪽은 앞 두 파일 사용. 개별 컷이 100판 전체 성능을 대표하는 수치 자체는 아니다. 정확한 낙상 프레임은 이번 조사에서 미측정. |
| 어려움이 남은 지형 | `docs/assets/video/v2/hero-steppingstones-v10-{nvidia,v1,v2}.mp4` | stepping_stones·1.0 m/s. 보고서0→0→24%, v2는 평가시드에 따라0~24%. | v2의 길이6초. ‘v2가 성공하는 한 판’으로 쓰면 안 된다. 아래 실패 영상도 직접 확인. |
| 실패를 숨기지 않는 화면 | `docs/assets/video/v2/stepping-stones-v2.mp4` | 디딤돌에서 비틀리고 지지점을 잃는 단일판. 5.94초 프레임에서 몸이 크게 기울어져 있다. | 0.20 / 2.40 / 4.18 / 5.94초 프레임 확인, 길이6초. **추천0~6초 전체**. 정확한 낙상 판정 시작 시점은 미측정. |
| 통과와 종합 성공의 차이 | `docs/assets/video/v2/stepping-stones-v2-cross.mp4` | 일부 디딤돌을 건너는 화면. 정본은 전진3.26m이나 추종 기준 미달로 종합0%라고 설명한다. | 0.20 / 1.58 / 2.78 / 3.92초 확인, 길이4초. ‘종합 성공’ 캡션 금지. **추천0~4초 전체**. |
| 회귀를 해석하는 방법 | `docs/assets/video/v2/regress-stairsinv-d09-{v1,v2}.mp4` | 높은 난이도 역계단에서 통과해도 속도 추종에 문제가 남는 사례. | v2의0.20 / 1.58 / 2.78 / 3.92초 확인. 보고서의 빨간 추종 램프 설명과 실제 파일 프레임 대응은 추가 확인 필요. **검증 전 ‘이 순간 빨간X’ 타이밍 지정 금지**. |

`axis2-stop-v1.mp4`, `axis2-turn-v1.mp4`, `regress-stairsinv-d09-v2.mp4`는 docs와 제출본의 SHA256을 직접 비교했고 각각 동일했다. 파일명이 같다는 이유만으로 다른 모든 사본도 동일하다고 간주하지 않는다.

### 실제로 학습하지 않은 지형의 추가 성공 시연

`sim/eval/results/20260928-v2-gallery/gallery.html`은 **v2g2-feetair01 iter3000**, 난이도0.5·측정규격2·50fps라고 명시한다. 아래 세 영상은 0.2초·40%·70%·끝 직전 프레임을 직접 확인했고 전진하며 마지막 HUD에서 통과 표시가 보인다.

| 파일 | 실제 길이 | 화면과 사용 목적 |
|---|---:|---|
| `sim/eval/results/20260928-v2-gallery/web/discrete_obstacles-v1.5.mp4` | 3.70초 | 크기가 다른 낮은 장애물 사이를 전진. 무조건 모든 장애물을 밟고 넘는 장면이라고 설명하지 않는다. |
| `sim/eval/results/20260928-v2-gallery/web/repeated_boxes-v1.5.mp4` | 3.58초 | 반복 상자 지형에서 보행 유지. ring 다음에 짧게 다양성을 보일 후보. |
| `sim/eval/results/20260928-v2-gallery/web/wave-v1.5.mp4` | 3.68초 | 물결형 굴곡에서 보행 유지. 형상 차이가 상대적으로 잘 보인다. |

추천 인·아웃은 각각 **0~3.70 / 0~3.58 / 0~3.68초 전체**. 이미 지형 구간까지 잘린 영상이므로 더 자르지 않아도 짧다. 세 지형은 정본 §1의 ‘어느 판도 학습 안 한 8종’에 포함된다. 다만 반복 평가·모델 선택에 사용한 사실과 별개의 **독립 최종 시험**이라고 말하지 않는다. 갤러리 표에는 별도900판 요약도 섞여 있으므로 그 수치를 MVP의100판×속도3종 값과 혼용하지 않는다.

## 2. 축2의 정지·회전, 횡이동 여부

| 파일군 | 길이·이벤트 | 발표 사용 |
|---|---|---|
| `docs/assets/video/v2/axis2-stop-{nvidia,v1,v2}.mp4` | 세 파일10초. `_stop_profile`은 **4.0초에 vx1.0→0.0**, 이후6초 관찰. v1·v2 0.20/3.48/6.48/9.92초 프레임 확인. | 전진 상태→정지 명령→후속 자세까지 보여야 해서 **0~10초 전체 권장**. 정지 직후1초만으로 결론내리지 않는다. |
| `docs/assets/video/v2/axis2-hold-{nvidia,v1,v2}.mp4` | v1 길이20초 직접 확인. 처음부터 끝까지 명령0. | 멈추라는 명령과 멈춰 있는 능력을 구분하는 후보. 이번 조사에서 전 프레임 이벤트 시점 검증은 하지 않았다. |
| `docs/assets/video/v2/axis2-turn-{nvidia,v1,v2}.mp4` | v1 6.50초, v2 18초. `wz`는1.5/4.5/7.5/10.5/13.5초에 각각-1/-0.5/0/+0.5/+1,16.5초부터0. | v1·v2 샘플 프레임 확인. v1 종료점 이후 v2만 계속 재생하면 비교 시간 차이를 밝혀야 한다. 특정 방향 미달을 보일 땐 해당 명령 구간 전체 사용. |
| `docs/assets/video/v2/axis2ext-turnrest-{nvidia,v1,v2}.mp4` | 회전 구간 사이1.5초 쉬기. v1 파일5.38초 실측. | 순서 누적효과 진단 후보. 정확한 파일 내 낙상 프레임은 미측정. |
| `docs/assets/video/v2/axis2ext-turnrev-{nvidia,v1,v2}.mp4` | 회전 순서를 뒤집음. v1 파일16.10초 실측. | 회전 방향과 순서의 영향을 분리하는 후보. |
| `docs/assets/video/v2/axis2ext-slow{010,020,030,040}-{nvidia,v1,v2}.mp4` | 저속0.10/0.20/0.30/0.40 m/s. slow010-v1은20초 직접 확인. | ‘안 넘어졌다’와 ‘명령 속도로 걸었다’가 다른 이유를 설명할 때 사용. |

**횡이동 명령 영상은 미확인.** 정본 §9-3과 `sim/eval/eval_command_response.py:157~261`을 직접 확인했다. 현재10개 프로필은 모두 `vy=0`이다. `sim/eval/results` MP4 경로에서 lateral/strafe/sideways/vy- 검색도0건이었다. 회전하거나 옆으로 밀리는 장면은 횡이동 명령 추종의 증거가 아니다.

**낙상 시각 인용 주의:** `sim/eval/results/20260929-axis2-fall/v1/{stop,hold,turn}/per_env.json`의 env8을 직접 읽으면 fell_at_s는8.78 /17.28 /3.70이다. 반면 정본은 turn 단일 영상6.5초를 설명한다. 입력 trace와 출력 영상의 env/종료 뒤 유지 구간 연결을 확정하지 않았으므로, raw 수치3.70초를 곧바로 발표 영상 인·아웃으로 사용하지 않는다. 본 문서는 확인하지 않은 프레임 시각을 만들어 적지 않았다.

## 3. rough6 2×3와 forward_gap

다음 여섯 파일은 실제로 열어 지형 형상을 확인했다. 공통 폴더 `sim/eval/results/20260928-terrain-shots/stills/`.

| 2×3 배치 후보 | 파일 | 화면 |
|---|---|---|
| 위 왼쪽 | `pyramid_stairs.png` | 올라가는 계단 |
| 위 가운데 | `pyramid_stairs_inv.png` | 내려가는 역계단 |
| 위 오른쪽 | `boxes.png` | 크기·높이가 다른 격자 상자 |
| 아래 왼쪽 | `random_rough.png` | 촘촘한 불규칙 요철 |
| 아래 가운데 | `hf_pyramid_slope.png` | 경사면 |
| 아래 오른쪽 | `hf_pyramid_slope_inv.png` | 역경사면 |

이름과6종 구성은 `sim/eval/rough6_env_cfg.py`의 sub_terrains와 대조했다. 항공 시점이라 두 경사 지형은 단차가 약하게 보일 수 있다. 화살표·짧은 라벨로 방향을 밝혀야 한다.

- `docs/assets/video/v2/posters/train-gap-forward.jpg`: 직선 도랑을 위에서 본 실제 포스터. 직접 열어 확인했다. 로봇이 작고 도랑이 얇게 보이므로 크게 사용해야 한다.
- `docs/assets/video/v2/train-gap-forward.mp4`:3초. 같은 직선 도랑의 영상.
- `docs/assets/video/v2/posters/train-gap-omni.jpg` 및 `train-gap-omni.mp4`:대응되는 omni 학습 지형. 영상3초 확인.
- `docs/assets/visual/eval-v2-gap-geometry.svg` 및 `.dark.svg`:forward_gap/omni_gap 형상 설명용 기존SVG. 파일 존재 확인, 이번 턴 화면 렌더 미확인.
- `stills/gap.png`는 평가용gap 스틸이다. 학습용forward_gap과 이름만 보고 같은 이미지로 바꾸지 않는다.

## 4. 3DGS PoC: 실촬영, 스플랫, 충돌 바닥

기준 폴더 `inbox/jay/20260916-3dgs-test/`. 아래 경로는 모두 실제 존재한다.

| 자료 | 상대경로 | 직접 확인한 내용 |
|---|---|---|
| 스마트폰 원본 | `test_20260916_112122728.mp4` | 약1/5/10초 프레임 확인. 차도·인도·연석·수목·차량·사람이 있는 실제 촬영. |
| 원본/복원/메시 비교판 | `_out/viewer/compare_org-NuRec-3dgs-ground_mesh.png` | 실제 원본, NuRec, 스플랫 편집 화면, 바닥 메시의4분할. 직접 확인. 결과보고서에는 반입 경로 미확인으로 명시되므로 자동생성 검증 결과라고 쓰지 않는다. |
| 정합 비교 | `_out/nurec/compare_cam143.png` | 왼쪽 실촬영 프레임, 가운데 NuRec 렌더, 오른쪽 숨김 대조. 직접 확인. |
| 시각 스플랫 | `_out/splat/splat.ply`, `_out/nurec/splat.usdz` | 파일535.8MB /267.9MB. git에 새로 넣지 않는다. |
| 충돌 바닥 | `_out/mesh/ground.usd`, `ground.obj`, `ground_heightmap.png` | 스플랫과 별도의 물리 충돌 바닥. 높이맵·USD는 존재 확인. ‘강화된 바닥’이라는 별도 명명 자산은 미확인. 정확한 의미가 충돌 메시라면 이 자료가 해당한다. |
| 로컬 인터랙티브 뷰어 | `_out/viewer/index.html`, `data.js` | 파일 존재, 포인트·메시·카메라궤적 뷰어라는 결과보고서 설명. 이번 턴 브라우저 실행 미확인. |
| 실제 시뮬레이션 영상 | `_out/nurec/go2_B_mesh_hidden/run.mp4` | 12초,30fps. 약1/5/10초 확인. 복원된 거리 배경 안에서Go2 이동. 현재33쪽 사용. |
| 바닥 표시 비교 실행 | `_out/nurec/go2_B_mesh_visible/run.mp4` | 동일12초. 같은 위치에서 배경·Go2 확인. 샘플 화면에서 hidden판과 큰 시각차이가 드러나지 않아 ‘바닥이 선명하게 보인다’는 소개는 부적절. |
| 충돌 지형 위 보행 | `_out/go2/{A,B}/run.mp4` | B의약1/5/10초 확인. 회색 메시 지형 위 여러Go2. A=NVIDIA, B=v1이지만 성능 비교용 조건 통제가 아니다. |

결과 근거 `RESULTS-3dgs-terrain.md` §7:스플랫은 시각 전용, 충돌·height scan은 ground.usd 담당. NuRec 영상은 낙상과 재시작을 포함하는 연결 PoC이고 ‘실제 공간에서 안정 보행 성공’ 증거가 아니다. 복원 실제 오차도 미측정이다. **실촬영→스플랫→충돌 바닥→같은 배경의 보행**을 나란히 보여주는 데 쓸 수 있다.

## 5. LiDAR·SLAM·Nav2 기존 자료

- **최우선 원본:** `deliverables/plan/proposal-deck-presented.html`, `section[aria-label="슬라이드 12"]`. 내용은 인지(카메라·4D LiDAR)→ROS2→SLAM→Nav2→Go2 순정 보행. 현재Track B의 과제 분리를 설명하는 기반으로 적합하다. 문구와 DOM 직접 확인.
- **상세 기존 도식:** `web/tech-slam-nav.html` 내 `svg[role="img"]`, viewBox `0 0 800 350`. 센서/위치/비용지도/명령과48+187 정책입력을 구분한 도식. **XT-16·D455 잠정 센서, foothold-v1.pt 사용안을 담고 있어 현재 장비 및 순정Go2 항법 방침과 다르다. 그대로 복사하지 않는다.**
- `docs/research/20260929-locomotion-direction.md`:보행 연구·실기 방향 근거 문서. 이번 조사에서 별도 완성 이미지나 영상은 찾지 못했다.
- `docs/assets/visual/go2-back-lidar-20260814.jpg`:장비 후면 LiDAR 사진 경로 존재. 이번 턴 이미지 내용·최신 모듈 구성 일치 여부는 미확인.

## 6. 기획발표 마지막장: 그대로 가져올 위치

원본 `deliverables/plan/proposal-deck-presented.html`은19개의 `section.s`를 포함한다. 마지막은 `section[aria-label="슬라이드 19"]`. 배포 사본은 `web/assets/deliverables/proposal-deck-presented.html`.

| 요소 | 원본 선택자·구성 |
|---|---|
| 전체 | `section.s.night > .pad > .finis` |
| 로고 | `.lockup-hero > img.sym` + `img.wm`; **두 SVG 모두 data URI 내장**. 워드마크 SVG에기존skew가 적용돼 있으므로 글자로 다시 쓰지 않는다. |
| QR | `.finis img.qr`;data URI 내장 SVG, alt는foothold-project.vercel.app QR 코드 |
| 홈페이지 | `.finis .url` 텍스트 `foothold-project.vercel.app`. 원본은a태그가 아니다. |
| 이름 | `.names`:오흥재·임석헌·오현민·맹라현·이민우 |
| 소속 | `.org`:인공지능사관학교7기·AI Physical 실증2팀 |
| Q&A | **원본19장에는 없음**. 현재MVP HTML40쪽에Q&A가 따로 존재. |

복사할 CSS 핵심: `.finis`는flex-column·center·gap1.6cqw·text-align:center. 로고행gap은inline1.5cqw, `img.sym`높이9.5cqw, `img.wm`높이5.6cqw. QR11cqw×11cqw·padding0.7cqw·white. `.url`은1.5cqw·teal-lit(#3ec7b4), `.names`1.35cqw, `.org`1.22cqw. 배경night=#0d1117. `.pad`4cqw 5cqw, 중앙정렬inline속성 포함. `.s`는container-type:size라 cqw가슬라이드 기준이다.

**현재HTML로가져올때:** 마지막section 내용과 해당CSS를별도클래스범위로이식한다. 원본전체스타일시트를덧붙이면 `.pad`, `.s`, 프레젠테이션크기 규칙이충돌할수있다. 원본fallback은1280×720기준픽셀값으로뒤에다시정의돼있으므로 현재1600×900에그대로복사하지않는다. 원본날짜2026.07~2026.12.11은MVP최신내용과별개다.

## 7. 현재42쪽 HTML에 연결된 모든 영상

실제검사파일 `inbox/jay/20260929-mvp-presentation/output/FOOTHOLD-MVP-cover.html`. 아래상대경로는이HTML의output폴더기준이며각파일존재·길이를직접확인했다. 42쪽자체는자료목록이며영상이없다.

| 쪽 | 파일 | 길이(초) |
|---:|---|---:|
| 2 | `../assets/film-master-v8.mp4` |80.625|
|12|`../../20260929-mvp-submission/source/media/train-army.mp4`|41.28|
|15,17,20|`../../20260929-mvp-submission/source/media/train-gap-forward.mp4`|3.00|
|18,19|`../../20260929-mvp-submission/source/media/lineage-gap-v1.mp4`|6.00|
|18,29|`../../20260929-mvp-submission/source/media/axis2-stop-v1.mp4`|10.00|
|19|`../../20260929-mvp-submission/source/media/lineage-gap-D-fail.mp4`|6.00|
|20|`../../20260929-mvp-submission/source/media/train-gap-omni.mp4`|3.00|
|28|`../../20260929-mvp-submission/source/media/hero-floatingring-v15-nvidia.mp4`|4.00|
|28|`../../20260929-mvp-submission/source/media/hero-floatingring-v15-v1.mp4`|3.80|
|28|`../../20260929-mvp-submission/source/media/hero-floatingring-v15-v2.mp4`|3.72|
|29|`../../20260929-mvp-submission/source/media/axis2-stop-v2.mp4`|10.00|
|30|`../../20260929-mvp-submission/source/media/axis2-turn-v2.mp4`|18.00|
|31|`../../20260929-mvp-submission/source/media/stepping-stones-v2.mp4`|6.00|
|33|`../../20260916-3dgs-test/_out/nurec/go2_B_mesh_hidden/run.mp4`|12.00|
|39|`../../20260930-mvp-brand/_out/review/FULL_v6.mp4`|83.458|

총 video 태그는19개, 고유 src는15개다. Canvas 프레임 애니메이션과 CSS 스프라이트는 이 집계에 포함하지 않는다. 학습영상의 촬영600마리와 학습환경4096개는 서로 다른 수치다. 메인세션에서 U205 영상 단계 표시는 이미 구분했다고 확인했다.

| 판 | 날짜 | 변경 |
|---|---|---|
|v1.0|2026-10-02|U206로컬어셋재사용조사. 단일문서만작성|
