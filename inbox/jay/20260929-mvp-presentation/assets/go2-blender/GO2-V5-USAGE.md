# Go2 v5 연속 기술 설명 자산

> 분류: 계획
> 작성: 오흥재 · 2026-10-02
> 근거: Go2 원본 USD · Blender 4.5.10 LTS 로컬 렌더 · 프레임·씬 검사
> 요지: 동일 기체의 턴테이블, 네 다리 분리·재조립, 측면 지면 격자를 클릭 단위로 재생한다.
> 상태: 로컬 제작 완료 · 슬라이드 연결은 별도 작업
> 판: v1.0

기존 v3·v4는 보존했다. 원본 메시와 관절은 `go2-technical-v4.blend`에서 이어 쓰며, 새 모델 생성·유료 API를 사용하지 않았다. 공통 원본 [Unitree Go2 USD](https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd).

## 산출물

| 파일 | 내용 |
|---|---|
| `go2-continuous-v5.blend` | 카메라·네 다리 위치·격자 공개를 키프레임으로 저장한 편집 가능한 장면 |
| `go2-front-v5.png` | 투명 정면. 이전 페이지에서도 이 파일을 쓰면 첫 영상 프레임과 구도가 일치 |
| `go2-three_quarter-v5.png` | 턴테이블 종료, 전방 사선 |
| `go2-four_legs-v5.png` | 네 다리를 연결된 묶음으로 벌린 상태. 네 다리 모두 보이는 높은 카메라 |
| `go2-assembled-v5.png` | 재조립된 상태 |
| `go2-side_grid-v5.png` | 머리가 화면 왼쪽인 측면, 몸체 중심 지면 격자 |
| `go2-scan-v5.png` | 같은 측면의 선택 표본 강조 |
| `go2-continuous-v5-preview.mp4` | 전체 확인용 약 12.04초, 24fps, 960×720. 종이색 배경과 무음 |
| `go2-{segment}-v5-preview.mp4` | 아래 다섯 구간 각각의 확인용 MP4 |
| `v5-web-frames/` | 실제 HTML 합성용 투명 WebP 289장, 총 약 8.25MB |
| `v5-manifest.js`, `v5-player.js` | `file://`에서 불러오는 플레이어·정지점 정의 |
| `v5-frame-anchors.js` | 선택 사항. 프레임별 관절·지면점의 화면 좌표 |

정지 PNG는 1600×1200, 연속 프레임은 960×720이다. 모두 4:3 구도이며 플레이어 Canvas는 1600×1200으로 고정된다. WebP는 투명하다. MP4의 종이색 배경은 확인용이며 투명 합성에 쓰지 않는다.

## 클릭 구간

| segment | 프레임 | 목표 상태 |
|---|---|---|
| `turntable` | 1~97 | `three_quarter`. 정면에서 한 바퀴와 45° 회전한 시점 |
| `four_legs` | 97~145 | `four_legs`. hip/thigh/calf/foot가 연결된 네 묶음 분리 |
| `assemble` | 145~193 | `assembled`. 원래 부착 좌표 복원 |
| `to_side` | 193~241 | `side_grid`. 카메라가 측면으로 이동하며 격자 등장 |
| `scan` | 241~289 | 표본 열을 차례로 강조. 끝 프레임 정지 |

`states`는 `front`, `three_quarter`, `four_legs`, `assembled`, `side_grid`, `scan`이다. 정지 `scan` 포스터는 중간 강조 시점 265프레임이므로 구간 끝 289프레임과 강조 열은 다르다. 재생 종료 뒤 포스터로 자동 교체하지 않는다.

```html
<script src="../assets/go2-blender/v5-manifest.js"></script>
<!-- 움직이는 설명선이 필요할 때만 아래 앵커를 함께 로드 -->
<script src="../assets/go2-blender/v5-frame-anchors.js"></script>
<script src="../assets/go2-blender/v5-player.js"></script>
```

```js
const player = new Go2V5Player(canvas, '../assets/go2-blender', {
  initial: 'front',
  onFrame: ({state, frame, anchors}) => {
    // anchors.joints[name] = [정규화 x, 정규화 y, 카메라 깊이]
    // anchors.sensors[name].screen도 같은 좌표 규칙이다.
    // 화면 좌표는 현재 Canvas의 CSS 영역에 투영한다.
  }
});
await player.ready;
await player.playSegment('turntable');
await player.playSegment('four_legs');
await player.playSegment('assemble');
await player.playSegment('to_side');
await player.playSegment('scan');
// 이전 상태 복원 또는 역재생
await player.setState('front');
await player.playSegment('to_side', {reverse:true});
player.stop();
```

각 호출은 해당 동작 종료까지 기다린다. 페이지 전환 시 `stop()`으로 재생을 중단한다. 새 호출이 기존 호출을 취소한다. 플레이어는 키보드나 발표 리모컨 이벤트를 등록하지 않는다. 메인 슬라이드의 클릭 단계에서 위 API를 호출한다. 프레임 캐시는 기본 110개로 제한한다.

## 격자와 물리 설명 범위

17×11, 0.1m 간격, 몸체 중심 x±0.8m·y±0.5m다. 기체의 앞은 +X이고 측면 카메라에서 화면 왼쪽이다. 격자는 동일 Blender 카메라로 투영되므로 로봇과 바닥의 원근이 맞는다. 앞쪽의 작은 단차와 뒤쪽 낮은 면은 높이 표본을 설명하기 위해 만든 기하 도식이다. 실제 실험에서 기록한 187채널 값이나 정책 보행 영상은 아니다. 로봇 관절은 이 구간에서 기준 자세를 유지한다.

앵커 `grid` 배열은 x를 바깥 반복, y를 안쪽 반복으로 만든 **도형 배열**이다. 저장 설정의 `ordering: xy`와 Torch meshgrid flatten 순서를 연결하려면 `tensor_index = y_index*17+x_index`, `anchor_index = x_index*11+y_index`로 대응시킨다. 화면 점의 단순 배열 순서를 Actor 입력 순서로 오인하지 않는다.

스캔 강조는 표본을 설명하기 위한 선택 애니메이션이다. 스캔 열이 움직이는 것을 실제 LiDAR 기계 스캔 주기나 50Hz RayCaster 출력 주기로 설명하지 않는다. 외부 LiDAR 하우징은 움직이지 않는다. 추가 모듈 메시·내부 기어·브래킷은 생성하지 않았다.

## 검증 및 재생성

`v5-audit.json`: 289프레임의 기체 경계가 모두 화면 안에 있음, 187개 표본, 원본 17개 메시 정점·면 개수 보존, 관절 회전값 유지, 재조립 위치 복원 확인.

`v5-reopen-audit.json`: 저장한 Blender 장면을 다시 열어 6개 정지 상태의 12관절 화면 좌표를 재계산했다. 렌더 기준과의 최대 정규화 오차는 약 0.0000005다.

`v5-video-verification.json`: 전체 MP4와 다섯 구간 MP4를 디코드해 프레임 수 확인. `v5-player-test.json`은 브라우저 검증 결과를 기록한다.

재생성 순서: Blender에서 `build_v5.py` 실행으로 정지 이미지·편집씬 생성, 같은 스크립트에 `--sequence`를 전달해 연속 프레임 생성, Python `package_v5.py`로 WebP·MP4·manifest 생성. 검사는 `verify_v5_scene.py`와 `verify_v5_player.py`를 사용한다.

## 판 이력

| 판 | 날짜 | 변경 |
|---|---|---|
| v1.0 | 2026-10-02 | 실제 USD 연속 자산, 재생 API, 격자 배열 매핑과 검증 기록 |
