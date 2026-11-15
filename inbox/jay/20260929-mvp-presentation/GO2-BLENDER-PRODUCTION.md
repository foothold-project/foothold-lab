# Go2 실제 USD 기반 설명 자산 제작

> 분류: 가이드
> 작성: 오흥재 · 2026-10-01 23:11
> 근거: 로컬 IsaacLab 설정, 원 USD, Blender MCP 실측
> 요지: 실제 학습 모델의 정면·턴테이블·강체 링크 분리·재조립·12관절 강조 첫 구간
> 상태: 첫 구간 제작·구조 검증 완료, 발표 HTML 통합 진행
> 판: v1.1

## 확보한 원본

`확인됨` 로컬 `C:/isaac/IsaacLab/source/isaaclab_assets/isaaclab_assets/robots/unitree.py`의 `UNITREE_GO2_CFG`가 참조하는 자산이다. 클라우드 루트는 `C:/isaac/IsaacLab/apps/isaaclab.python.headless.kit`에 기록된 Isaac 5.1 경로를 사용했다.

- [Go2 USD 원본](https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd)
- [메시 의존 USD](https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/IsaacLab/Robots/Unitree/Go2/Props/instanceable_meshes.usd)
- 보관: `assets/go2-blender/go2.usd`, `assets/go2-blender/Props/instanceable_meshes.usd`
- 회전 관절 12개, 고정 관절 6개. 원본 시각 메시 17개. 충돌용 형상은 렌더하지 않는다.
- 원본 체크섬: `go2.usd` SHA256 `ba171c972b987d8c8fb7157ccad2ba9c0c1fed105755d2d8af46bef96cc11c6d`; 메시 SHA256 `2902646d0f4c13c9ecae3ac9046e32c7d18902eef9679de9829f642a15c93fb5`.

## 연결과 제작 방식

Higgsfield `/Exploded-view`와 `/use-blender` 설치·검증 지침, `blender-scene` 및 `blender-camera-led-assembly` 스킬을 읽고 적용했다. npm 최신 `fnf-blender-mcp` 0.2.2를 사용자 LocalAppData에 설치하고 Codex `higgsfield-use-blender` 서버로 등록했다.

`확인됨` 로컬 stdio MCP 클라이언트 `assets/go2-blender/mcp_client.py`에서 실제 `bl_health`, `bl_get_scene_summary`, `bl_get_skill`, `bl_execute`를 호출했다. Blender 4.5.10 LTS, `background:true` 응답을 확인했다. 기존 데스크톱 Blender 창에 접속한 방식은 아니다. 현재 대화의 자동 도구 목록에 `bl_*`가 노출된 상태라고 주장하지 않는다. Codex 등록을 통한 자동 도구 발견은 새 대화에서 확인할 항목이다.

Blender 기본 USD 임포트에서 원본 UV/인스턴스 경고가 발생하여, USD 시각 메시의 정점·면·재질색·원본 법선과 관절 부착 위치를 직접 옮겼다. 원본 17개 메시의 정점·면 개수와 법선을 모두 보존했다. 조명과 거칠기는 발표용 스튜디오 환경으로 조정했다.

Exploded view는 부품을 연결 위치에서 벌려 구조를 읽게 하는 분해도 연출이다. 이번에는 **실제 USD에 존재하는 강체 링크**만 분리한다. 모터 내부 기어, 제어 보드, 장착 여부가 확인되지 않은 외장 장비를 만들어 넣지 않았다. 실제 분해 정비 순서나 내부 설계를 재현한 장면은 아니다.

## 파일과 재생 계약

모든 자산은 `assets/go2-blender/` 아래에 있다.

| 파일 | 용도 |
|---|---|
| `go2-presentation-v3.blend` | 편집 가능한 최종 첫 구간 씬 |
| `go2-front-v3.png` | 정면, 960×720, 투명 배경 |
| `go2-three-quarter-v3.png` | 턴테이블 종점 |
| `go2-exploded-v3.png` | 강체 링크 분리 |
| `go2-joints-v3.png` | 12개 회전 관절 표시. 가려진 관절은 다른 각도/추가 설명 필요 |
| `go2-spec-preview.mp4` | 전체 연속 프리뷰. 640×480, 24fps, 264프레임, 11초, 무음 |
| `web-frames/frame-0001.webp` 등 | 클릭 구간 제어용 투명 프레임 264장 |
| `go2-player.js` | Canvas 재생·정지·역방향 단계 이동 클래스 |
| `playback-manifest.json` | 프레임·재생 구간 계약 |
| `joint-screen-positions.json` | 정지 지점별 실제 관절 투영 좌표 |

`new Go2SpecPlayer(canvas, '../assets/go2-blender')`로 생성한다. `await player.ready`는 첫 프레임 로드 완료다. `await player.stage(index, true)`로 해당 지점까지 재생한 뒤 멈춘다. `player.stage(index, false)`는 즉시 복원한다. 새로운 호출은 이전 재생을 취소한다. 슬라이드 키보드 이벤트는 메인 프레젠테이션에서 소유한다.

| 단계 | 프레임 | 의미 |
|---|---:|---|
| 0 | 1 | 정면 정지 |
| 1 | 96 | 한 바퀴에 가까운 턴테이블 후 설명 각도 정지 |
| 2 | 156 | 강체 링크 분리 완료 |
| 3 | 216 | 재조립 완료 |
| 4 | 240 | 회전 관절 12개 강조 |

웹 프레임은 검토용 640×480이다. 정적 이미지는 960×720이며, 전체 애니메이션의 고해상도 최종 렌더는 편집·연출 승인 후 같은 씬에서 가능하다. 이 영상은 설명용 키프레임 애니메이션이며 학습 정책의 보행 결과가 아니다.

## 검증과 남은 범위

`verification.json`, `reopen-audit.json`에 직접 검사 결과가 있다. 저장한 씬을 다시 열어 메시 17개의 정점·면 수 일치, 1~264 프레임 범위, 활성 카메라를 확인했다. 분리 전 120프레임과 재조립 후 216프레임의 원본 메시 월드 변환 최대 차이는 0이다. 3프레임 간격의 전체 카메라 경계 검사에서 클리핑이 없었다. 정면·사선·분리·관절 이미지도 열어 확인했다.

`player-browser-test.json`: Chrome에서 실제 WebP를 Canvas에 로드하고 정면 1프레임부터 턴테이블 96프레임까지 재생, 관절 240프레임 즉시 이동, 정면 1프레임 복원을 확인했다. 프리뷰 MP4를 다시 디코딩해 264프레임·24fps를 확인했다. 아직 발표용 고해상도 최종 영상 검수나 실기와의 외관 세부 대조를 마친 것은 아니다.

외장 Orin NX 16GB, D435i, HESAI-360은 이 USD에 없다. 별도 실물 모듈 자료와 정확한 장착 위치를 기준으로 다음 구간에서 만든다. 센서 데이터 흐름, 관절 회전축 시연, 명령 축 화살표, Actor·Critic, Isaac 동기 데이터는 이번 첫 구간에 포함하지 않았다.

원본/중간 씬과 렌더 프레임은 별도 검토 이력이다. `go2-imported-source.blend`, `go2-presentation-v1.blend`, `go2-presentation-v2.blend`, `frames/*.png`를 최종 배포 파일로 일괄 올리지 않는다. 필요한 최종 파일과 출처만 선택한다. 파일별 100MB 제한을 지킨다. 100MB가 넘은 중간 USD 텍스트 덤프는 제거했고 바이너리 원본은 보존했다.

| 판 | 변경 |
|---|---|
| v1.0 | 실제 USD 확보, MCP 등록·stdio 호출, 첫 구간 제작 및 재개방 검증 |
| v1.1 | U205에 따른 큰 정면, 한 다리 3축, 네 다리 관절 구동, 명령 방향 자산 추가 |

## U205 기술 설명 자산 추가 · 2026-10-02

기존 `go2-presentation-v3.blend`와 v3 프레임은 그대로 보존했다. 새 씬은 `assets/go2-blender/go2-technical-v4.blend`이다. 원 USD 메시를 변경하지 않고 관절축 표시와 설명용 움직임만 추가했다. 기본 USD에 없는 추가 모듈이나 내부 기어는 만들지 않았다.

### 큰 정면과 정지 자산

| 파일 | 설명 |
|---|---|
| `go2-front-v4.png` | 1600×1600 RGBA. 배경 투명. 동일 Go2가 이미지 높이의 약 77%를 차지한다 |
| `go2-three-axes-v4.png` | 1280×960. 전체 기체와 왼쪽 앞다리 축 |
| `go2-fl-leg-v4.png` | 1280×960. 한 다리 확대. 세 회전축을 구분하기 위한 시점 |
| `go2-twelve-axes-v4.png` | 1280×960. 네 다리의 12개 회전축 위치. 일부 뒤쪽 축은 기체에 가려진다 |
| `go2-hip-v4.png` 등 | 해당 구간 중간 자세. 동작 지시의 방향을 설명하는 포스터 |

`go2-front-v4.png`의 알파 경계는 x=221~1378, y=201~1427이다. 사각형 이미지 전체에 맞춰 라인 앵커를 놓고 CSS `object-fit:contain`으로 생긴 여백까지 계산해야 한다. 투명 여백을 임의로 크롭하면 아래 좌표가 달라진다.

### 관절과 명령 방향의 움직임

각 MP4는 960×720, 24fps, 무음이다. 웹용 투명 WebP 432장을 `v4-web-frames/`에 저장했다. 자산마다 `go2-<id>-v4.mp4` 프리뷰가 있다.

| id | 구간 | 내용 |
|---|---:|---|
| `hip` | 1~48 | 왼쪽 앞다리 외전·내전 축 회전 |
| `thigh` | 49~96 | 같은 다리의 고관절 굽힘·폄 |
| `calf` | 97~144 | 같은 다리의 무릎 굽힘·폄 |
| `fl`, `fr`, `rl`, `rr` | 각각 36프레임 | 각 다리 3개 관절을 함께 움직인 후 원위치. 해당 다리가 보이는 각도로 촬영 |
| `forward` | 289~336 | 몸체 기준 전후 명령 방향 |
| `lateral` | 337~384 | 몸체 기준 횡이동 명령 방향 |
| `yaw` | 385~432 | 수직축 회전 명령 방향 |

이는 **관절 구동과 명령의 뜻을 설명하는 키프레임 애니메이션**이다. 학습 정책이 명령을 받아 실제로 보행한 시뮬레이션 결과가 아니다. 특히 명령 세 구간은 기체 전체의 위치·방향으로 명령의 축을 가리키므로 발 접촉을 유지하는 보행 장면으로 설명하지 않는다. 실제 명령 추종 보행은 별도 실험 영상을 쓴다.

관절축은 원 USD `PhysicsRevoluteJoint`의 축 및 `localRot0`에서 가져왔다. `hip`은 몸체 좌표 x방향 회전축, `thigh`와 `calf`는 부모 링크 좌표 y방향 회전축이다. 부모가 움직이면 후속 축의 월드 방향도 함께 바뀐다. 축 표시 막대와 원은 설명용 그래픽이고 실제 부착 장비가 아니다.

### 센서 앵커의 근거와 한계

`v4-sensor-and-joint-anchors.json`에 정규화 화면 좌표를 기록했다. front 좌표는 `go2-front-v4.png` 전체 이미지 기준이다.

| 대상 | 화면 x, y | 근거 |
|---|---|---|
| 전면 카메라 | 약 0.500, 0.235 | 실제 USD 외관에 보이는 렌즈의 설명용 앵커. USD Camera prim이나 실기 보정값이 아니다 |
| 전면 LiDAR | 약 0.500, 0.391 | `/go2_description/base/radar`에 작성된 기준점 투영. 외장 HESAI가 아니다 |
| IMU | 약 0.500, 0.183 | `/go2_description/base/imu` 내부 기준점. 겉으로 드러난 모듈처럼 표시하면 안 된다 |

어느 것도 실기 센서 캘리브레이션을 검증한 결과가 아니다. USD의 `radar`라는 내부 이름만으로 레이더 센서라고 소개하지 않는다. LiDAR 세대, 센서 사양과 추가 장비의 정확한 장착 상태는 별도 실물 자료로 확인한다. Orin NX 16GB, D435i, HESAI-360의 가상 외관을 만들어 삽입하지 않았다.

### 로컬 HTML API

로컬 `file://`에서도 JSON fetch가 필요 없도록 `v4-manifest.js`를 먼저, `v4-player.js`를 다음에 읽는다. 발표 HTML의 키보드·리모컨 이벤트는 이 클래스가 등록하지 않는다.

```js
const p = new Go2TechnicalPlayer(canvas, '../assets/go2-blender', {initial:'front'});
await p.ready;
await p.setState('single_leg');
await p.playSegment('hip');
await p.playSegment('thigh');
await p.playSegment('calf');
await p.setState('twelve_axes');
await p.playSegment('fl');
await p.playSegment('forward');
await p.playSegment('hip', {reverse:true});
await p.setState('front');
```

정지 상태 id는 `front`, `three_axes`, `single_leg`, `twelve_axes`이다. 구간 id를 `setState()`에 주면 해당 포스터를 즉시 표시한다. `playSegment()`는 재생 후 마지막 프레임을 유지한다. 새 상태 호출은 이전 재생을 취소하며 `stop()`은 현재 프레임에 멈춘다. `current`와 선택적 `onFrame` 콜백으로 발표 단계와 동기화할 수 있다.

### 검증

`v4-scene-audit.json`: 저장 씬 재개방, 원본 17개 메시 정점·면 수 일치, 전체 432프레임의 카메라 경계 통과, 모든 회전 관절의 각도가 USD 관절 한계 안에 있음을 확인했다. `v4-video-verification.json`: MP4 10개를 각각 디코딩해 프레임 수와 24fps 확인. 실제 브라우저 동작 결과는 `v4-player-test.json`에 별도 저장한다.
