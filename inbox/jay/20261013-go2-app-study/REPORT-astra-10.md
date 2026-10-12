> 분류: 리서치
> 작성: 오흥재 · ASTRA 분석 · 2026-10-13
> 근거: Unitree 공식 APK 2.0.0(202) · 앱 실행 중 제공된 웹 자산 · 추출 WASM 합성 입력 실행 · 공개 구현 고정 commit · APP-PLAN-facts.md
> 요지: 공식 앱의 깔끔한 표시는 복셀 표면·점 누적·높이색으로 설명되는 부분이 크다. 안전한 잡음 자동 삭제나 0.05 m 2D/3D 정합의 완성품을 발견한 것은 아니다.
> 상태: 공식 클라이언트 코드·제한된 함수 실행 확인됨 · 실기 지도·로봇 측 정제·성능 미확인 · 커밋·push 없음

# ASTRA 10 · Unitree Go 앱 분석과 FOOTHOLD 지도 설계

## 분석한 앱과 판

| 항목 | 확인한 값 |
|---|---|
| 공식 배포 안내 | [Unitree Go2 앱 페이지](https://www.unitree.com/cn/app/go2/)와 페이지가 불러오는 배포 설정 |
| 분석 주 대상 | [국제 배포 APK](https://global-fitness-static.unitree.com/robot/app/UnitreeGo.apk) |
| 로컬 원본 | [astra10/downloads/UnitreeGo.apk](astra10/downloads/UnitreeGo.apk), 191,452,888 bytes |
| SHA-256 | `7a36e9a847997ebea02d88fde6ccdd6e5c4c8d3f7e57619584b3c6718bfa2cf1` |
| Android manifest | package `com.unitree.doggo2`, versionName `2.0.0`, versionCode `202`, minSdk 29, targetSdk 35 |
| 취득 | 2026-10-13 00:50:39 KST. HTTP Last-Modified는 2026-08-03 03:41:19 GMT |
| 내장 웹 판 | `v1.2.44.81`, `2026-07-24 17:37:52`라는 time.json 값. APK 판과 다른 식별자 |
| 비교용 중국 배포본 | [공식 중국 URL](https://fitness-static.unitree.com/robot/app/UnitreeGo.apk), 191,839,281 bytes |
| 중국 APK SHA-256 | `c97b9784057e2391e3bc35715a1dda72f7b064160e210e6bbad9d99fd8b822ad` |

**공식 URL이 조사 시점에 제공한 판**이다. Google Play의 모든 지역·계정에 배포된 최신 판과 같다는 것은 미확인이다. 두 APK의 비교 대상 웹 자산 123개는 바이트가 같았다. [취득 기록](astra10/logs/UnitreeGo.apk.source.json), [지역본 비교](astra10/evidence/cn-international-comparison.json), [주요 파일 재해시](astra10/evidence/final-verification.json).

## 우리 앱의 세 질문에 대한 결론

[APP-PLAN-facts.md](APP-PLAN-facts.md)의 19개 화면 요약을 기준으로 했다. 원래 Claude artifact의 화면 19장과 canvas.json은 직접 열람하지 못했으므로 원 화면의 상세 동작까지 검증한 것은 아니다.

| 질문 | 공식 앱에서 확인한 것 | FOOTHOLD에 대한 판단 |
|---|---|---|
| 지우개를 자동화하는 특별한 정제가 있나? | 중복 key 억제·고정 용량 점 누적, 압축 복셀의 노출면 생성, 높이색. 조사한 worker에 SOR·바닥 분류·시간 기반 잡음 판정은 없음 | **지우개를 없앨 근거가 없다.** 표시용 축약과 지도 셀 삭제를 분리하고, 자동화는 삭제 후보 제시부터 시작한다 |
| 0.05 m 2D 격자와 3D 점군을 같이 그리는 완성 경로가 있나? | 3D 점군 렌더, PCD·PGM·TXT 묶음 저장. 별도 `/slam` 코드는 고정 그림·미완성 처리. 점 크기 `0.05`는 격자 해상도가 아님 | **우리 좌표 계약으로 구현해야 한다.** 같은 map 프레임·지도 판·시각을 공유하는 2D/3D 표시를 먼저 검증한다 |
| 위치·방향·시야·경로를 겹치는 법은? | odometry pose, 이동 궤적, 계획 경로, 목표 picking. 영상은 별도 UI. 보정된 시야 부채꼴은 해당 지도 경로에서 못 찾음 | 위치·경로 표현은 참고 가능. **카메라 내부·외부 보정과 영상 시각에 맞춘 FOV는 별도 작업**이다 |

초기 가정인 “보기 깔끔하므로 강력한 지도 정제가 앱에 있을 것”은 현재 증거로 성립하지 않는다. **렌더링의 정돈, 전송량 축소, 기하 정보의 신뢰성은 서로 다른 성질**이다. 로봇이 보내기 전에 수행하는 정제는 이번 APK에서 복원할 수 없었다. 공식 앱에 어떤 정제도 없다는 전역 부재 주장도 하지 않는다.

## 실제 앱을 어디까지 열었는가

앱은 Android 네이티브 shell과 WebView, Vue/Vite 웹앱, Three.js, Web Worker, WASM을 결합한다. 조사한 패키지에서 Flutter나 Unity를 주요 지도 엔진으로 확인하지 못했다.

REA 6.4.0을 설치했고, **답을 아는 Appium ApiDemos 6.0.18 APK**로 manifest 분석을 먼저 시험했다. Unitree APK의 REA 분석으로 패키지 판과 2,589개 ZIP entry를 확인했다. 그러나 Baidu 보호가 걸린 DEX를 JADX로 열었을 때 나타난 9,930개 class 대부분은 라이브러리였고, 실제 앱의 핵심 Java 로직을 확보한 것으로 볼 수 없었다. 암호화된 웹 자산을 REA JS 분석에 넣은 첫 시도도 유효한 앱 코드 분석이 아니었다.

그 뒤 별도 Android 30 에뮬레이터에서 공식 APK를 실행했다. 앱의 MainActivity와 자체 localhost HTTP 서버를 통해 앱이 제공하는 **평문 웹 자산 38개, 총 32,284,965 bytes**를 취득했다. 그중 27개는 APK 안의 암호화 자산과 바이트가 달랐다. 요청한 40개 중 vconsole 두 자산은 취득 실패했다. 지도 분석 핵심 파일은 확보됐다. 변조된 앱을 재배포하거나 로그인·로봇 연결·명령 전송을 하지는 않았다. 게스트 외부 통신을 차단하고 loopback 경로를 사용했다.

- 취득 스크립트: [recover_web_assets.py](astra10/recover_web_assets.py)
- 자산별 원 경로·크기·hash·APK 동일 여부: [runtime-web-manifest.json](astra10/evidence/runtime-web-manifest.json)
- 실제 앱 첫 화면: [시작 화면](astra10/evidence/emulator-first-screen.png), [MainActivity 화면](astra10/evidence/emulator-main-screen.png)
- REA manifest 결과: [rea-android-package.json](astra10/logs/rea-android-package.json), Evidence ID `ev_f61468cb2a558b478e7584df9002e41404e341cde00659cce1db447750521ba2`
- 복원한 worker 5개의 REA 분석: [rea-recovered-workers.json](astra10/logs/rea-recovered-workers.json), Evidence ID `ev_5ea5358eaff0a77ab0a3081cfd52bfb6f954e8ce5601dfe62b9899933ecba5e6`

**앱 홈 화면을 실행한 것과 실제 로봇 지도 화면을 검증한 것은 다르다.** 후자는 하지 못했다. REA의 CDP 웹 검사도 endpoint 오류로 실패했으며 성공으로 계산하지 않았다. 핵심 알고리즘은 확보한 공식 JS·WASM을 격리해 합성 입력으로 실행했다.

이하 소스 별칭은 아래 보관본을 뜻한다. 행 번호는 포맷 변경 전 파일 기준이다.

| 별칭 | 원문 파일 · SHA-256 |
|---|---|
| M | [main-LIOZh9o1.js](astra10/runtime-web/assets/main-LIOZh9o1.js), `cebfc3e7e2d7838cf8adf650d0a32edbf7fbd32df8ede486d7521f96afb6ab15` |
| S | [store.-Ml-K330.js](astra10/runtime-web/js/store/store.-Ml-K330.js), `fcd48d6ea8fe411fe9ca6ea639b70b86f8dd5be515005d06aa655d466e529884` |
| Q | [Slam.BsJuOfhQ.js](astra10/runtime-web/js/slam/Slam.BsJuOfhQ.js), `7970f500718ef578421e5553e2696f2a30d4caaa9f3e56c2780f4cbb164b4148` |

## 자료가 들어와 그림이 되는 세 경로

### 실시간 전방 복셀: `/operation`

**확인됨.** `rt/utlidar/voxel_map_compressed` 수신 → `three.worker-BhnsyeGz.js` → `libvoxel-doIu-r8s.wasm` → LZ4 해제 → bit voxel의 노출면 생성 → Three.js BufferGeometry.

WASM은 128 × 128 × 30 bit, 61,440 bytes의 복셀 배열을 순회한다. 한 복셀의 점 위치를 예쁘게 추정하는 대신, 점유 복셀의 바깥 면을 그린다. 이웃 복셀 사이의 내부 면을 생략하므로 조밀한 부위가 덩어리로 보인다. **내부 면 제거는 잡음 점 제거가 아니다.** 고립 복셀은 그대로 남는다.

| 알려진 입력 | 직접 실행한 결과 |
|---|---|
| 복셀 1개 | 노출면 6개 |
| 서로 붙은 복셀 2개 | 10개 |
| 꽉 찬 2 × 2 × 2 | 24개 |
| 꽉 찬 3 × 3 × 3 | 54개 |
| 고립 복셀 | 제거되지 않음 |

M 10086~10092의 `updateMeshesForData2`는 mesh에 `resolution` scale과 `origin` translation을 적용한다. 즉 `world = origin + resolution × voxelVertex`다. worker는 `Number(resolution) || 0.1`을 사용한다. **0.1은 fallback이지 실측 센서 해상도가 아니다.** width를 읽지만 WASM 순회 크기를 바꾸지는 않는다.

색은 높이에 따른 UV와 `/models/axisColor4.png`를 쓰는 방식이다. nearest sampling과 MeshBasicMaterial을 사용하며, 이 경로에서 surface normal 재구성·Poisson surface·기하 평활을 확인하지 못했다. M 10502, worker 문자 offset 6243·6416, [WASM 분석](astra10/wasm-analysis/REPORT-WASM.md).

M 10913은 처리 중인 worker가 있으면 새 자료를 넘기지 않는다. 화면 상태에 따라 150이라는 scheduling 인자를 쓰지만 이를 수신 주기 6.7 Hz로 단정할 수 없다. M 10609의 `loadPointCloud`는 점 수가 0이면 기존 mesh를 지우지 않는다. **빈 프레임을 받았는데 과거 형상이 계속 보일 수 있는 함수 동작**을 격리 fixture로 확인했다. 실제 앱에서의 발생 빈도는 미확인이다. [렌더 함수 검증](astra10/evidence/renderer-fixtures.json).

### 지도 생성·위치 추정: `/lidarMapping`

**확인됨.** 신규 지도는 `rt/uslam/frontend/cloud_world_ds` → `three.worker-VAdOurOh.js` → `libvoxel-Bqa6xB-f.wasm` → 현재 점과 누적 점 두 배열 → M의 `MF` 렌더러로 이어진다.

WASM은 XYZ를 uint16 세 개로 읽고 각 축 minimum에 `raw × 0.001`을 더한다. 여기의 1 mm 단위는 **부호화 단위이며 센서 정확도가 아니다.** 중복 key의 첫 점을 보존하고, capacity 1,000,000의 ring에 누적한다. centroid 기반 축약, SOR, 바닥/장애물 분류, 관측 시각 기반 소멸은 확인하지 못했다. 최대 bounds를 바꾼 시험에서도 clipping 동작은 나타나지 않았다.

현재 입력의 `directOutput`과 누적 `output`은 실제 main 호출에서 각각 다른 BufferGeometry로 들어가며 두 Points 모두 scene에 추가된다. 따라서 누적 WASM 결과는 사장된 코드가 아니다. M 18646~18648, 17935~17955. 누적 point size는 0.05, 현재 점 size는 0.1이다. **이 0.05는 PointMaterial의 크기이며 0.05 m OccupancyGrid를 만드는 코드가 아니다.**

높이색 shader `BF`는 z의 sin/cos 절댓값으로 R/G를 바꾸고 B는 기본 재질색에서 유지한다(M 17883). 이 색은 주기적이므로 낮음→높음으로 단조 증가하는 물리 높이 범례로 쓰면 틀린다. 렌더러의 antialias, bloom, camera/controls도 표현을 정돈한다. 이들이 점 위치나 SLAM 정확도를 개선하는 것은 아니다.

기존 지도 위 현재 점과 계획 경로는 별도 경로다. `preview`·`navigation-path` 메시지는 `point_step`, 앞 세 field offset을 이용해 float32 XYZ를 복사하며 WASM 누적기를 거치지 않는다. 저장된 PCD는 M 17967의 `loadPCD`에서 PCDLoader로 읽는다. 이 함수에도 별도 잡음 정제는 없다.

### 이름이 SLAM인 별도 화면: `/slam`

**실제 2D 지도 구현의 근거로 사용하면 안 된다.** Q 4707~4709는 worker 결과를 렌더 버퍼에 연결하지 않고, 4727~4737은 고정 좌표의 점선·화살표·원을 만든다. `slam.worker-B9-NnJ09.js`는 base64를 디코딩하고도 결과를 버리며 0으로 채운 배열을 반환한다. 알려진 입력 `[1,2,3,4,5,6]`도 `[0,0,0,0,0,0]`으로 돌아왔다.

S에 `rt/mapping/grid_map`이라는 topic 상수가 있다는 사실이나 Konva에 Mask/Blur/Noise 함수가 포함됐다는 사실은 이 화면의 지도 정제 구현 증거가 아니다. 확보한 nonlegacy 웹 코드에서 해당 grid enum의 실제 사용을 찾지 못했다. **이는 앱 전체의 2D 기능이 없다는 증명이 아니라, 이 코드 경로를 완성된 기능이라고 인용할 수 없다는 판정이다.**

## 그대로 가져오면 안 되는 동작

WASM 내부만 추정한 것이 아니라 **공식 worker 원문을 수정하지 않고 실행한 결과**다. 고정 입력의 내부 동작과 실제 로봇에서 발생한 결함을 구분한다.

| 확인한 동작 | 근거와 재현 | 우리 설계에 주는 의미 |
|---|---|---|
| 높이가 다른 점이 같은 누적 key로 합쳐짐 | 같은 XY에서 z=0 m, 4 m인 두 점. direct는 2점, 누적은 1점. WASM key의 z 항에 rawZ가 아니라 rawX가 재사용됨 | 정상적인 3D voxel downsampling이라고 이식하면 안 됨. 배관·천장·벽의 수직 구조를 보존하는 독립 구현 필요 |
| clear 뒤 중복 판정 일부가 남음 | worker의 `fill` 끝 인자가 pointer+length가 아닌 length. dict 뒤 567,128 bytes가 미삭제, key 배열은 end<start. `[51,0,0]`을 clear 후 재입력하면 direct 1, 누적 0 | 지도 판 전환 시 모든 상태의 수명 주기 검증 필요. 단순 카운터 reset을 지도 초기화로 취급하지 않음 |
| 빈 전방 복셀 출력에 과거 mesh 유지 | M의 실제 `loadPointCloud` 함수에 정상 입력 후 0점 입력. 이전 holder 유지 | `빈 관측`·`통신 정체`·`마지막 유효 자료`를 별도 상태로 표시해야 함 |
| 경로를 부드러운 곡선으로 다시 그림 | 이동 궤적에 XY 0.1 m 초과 이동 시 점 추가, CatmullRomCurve3 보간. 현재 공식 코드에서 공개 UI의 200점 제한은 못 찾음 | 기록 원자료와 표시 곡선을 분리. 곡선이 코너를 잘라도 통과 가능한 계획 경로라는 뜻이 아님 |

누적 점에서 빠진 점이 화면 전체에서 반드시 사라지는 것은 아니다. 같은 프레임의 direct 점도 그리기 때문이다. clear 문제도 모든 key에서 발생하지 않는다. 공식 앱의 실제 센서 분포·세션 수명에서 얼마나 재현되는지, 항법 지도 파일에 영향을 미치는지는 미확인이다. 이를 “로봇 지도 알고리즘 전체가 잘못됐다”로 확대하지 않는다.

원문 함수·offset·메모리 위치·재현 입력은 [REPORT-WRAPPERS.md](astra10/wasm-analysis/REPORT-WRAPPERS.md)에 있다. 점 WASM generate 함수의 바이너리 구간은 `0x1A8A..0x1CD4`, reset은 `0x1CD5..0x1CE7`; 복셀 WASM generate는 `0x1AC3..0x2457`이다. 끝 offset은 제외한다. 공식 배포 파일은 수정하지 않았다.

## 로봇과 앱의 책임, 자료와 명령의 연결

### 수신 계약

S의 `PD`는 문자열 JSON 또는 JSON header+binary payload 프레임을 분리한다. normal 프레임은 uint16 길이·JSON offset 4, special 프레임은 처음 uint16 두 값이 2·0일 때 uint32 길이·JSON offset 12다. endian은 native typed array에 의존한다. 이 Windows의 두 합성 입력에서는 little endian으로 정확히 복원됐다. 이것은 압축 해제와 별도 단계다.

| 자료 | 공식 웹 코드의 topic | 앱에서 하는 일 |
|---|---|---|
| 실시간 복셀 | `rt/utlidar/voxel_map_compressed` | LZ4·복셀 mesh·height UV |
| 새 지도 점군 | `rt/uslam/frontend/cloud_world_ds` | packed XYZ 복원·key 억제·점 누적·렌더 |
| 새 지도 자세 | `rt/uslam/frontend/odom` | 이동 궤적 |
| 저장 지도에서 현재 점군 | `rt/uslam/localization/cloud_world` | float32 XYZ 표시 |
| 위치 추정 자세 | `rt/uslam/localization/odom` | 모델 position·orientation |
| 계획 경로 | `rt/uslam/navigation/global_path` | 경로 점 렌더 |
| 명령·응답 로그 | `rt/uslam/client_command`, `rt/uslam/server_log` | 문자열 명령, 상태 전이 |

**로봇 쪽 확인 경계:** SLAM·localization·global path라는 산출물을 로봇이 보내고 앱이 받아 쓰는 클라이언트 계약은 확인됐다. 로봇 내부 SLAM 엔진의 종류, ground segmentation, outlier threshold, point deskew, loop closure 처리, 갱신 주기는 APK만으로 확인하지 못했다. `cloud_world_ds`의 이름에 ds가 있어도 실제 다운샘플 수식·해상도가 입증되지는 않는다.

### 지도 저장과 조작

| UI 또는 상태 | 공식 앱의 실제 연결 | 해석 |
|---|---|---|
| 새 지도 시작 | `mapping/start`, 관련 cloud·odom 구독 | 앱 내에서 SLAM을 새로 계산한다는 근거가 아님 |
| 지도 저장 | `mapping/stop` 후 `mapping/stop/success` 조건에서 `map.pcd`, `map.pgm`, `map.txt` 요청 | 결과 파일이 로봇에서 온다는 흐름 확인 |
| 휴대폰 저장 | `webSaveLidarData` bridge에 img/pcd/pgm/txt/name | PGM 해상도·정제식은 파일명만으로 모름 |
| 지도 재업로드 | 30 × 1024 크기 조각과 파일 상태 응답 | 손상 검증·실기 저장 완결성은 미검증 |
| 위치 맞추기 | x/y/yaw 전송 후 100 ms 예약으로 localization/start | UI delay가 정합 완료 증거가 아님 |
| 지도 목표 선택 | 카메라 ray와 투명 ground plane의 교점. 연결 callback이 목표 전송 | 우리 기획의 확인·경로 검사 단계를 그대로 충족하지 않음 |
| 목표 위치 | `navigation/set_goal_pose/x/y/0` | 이 경로의 도착 yaw는 고정 0. 우리 기획의 도착 방향은 별도 구현 |
| 순찰점 | yaw에서 π를 뺀 값과 x/y 전송. 점 사이 100 ms | 점별 로봇 처리 ACK를 기다리는 것과 다름 |

M 18638, 18886~18964, 19130~19190, 19408~19595에 근거한다. 전문은 [공식 프로토콜 보고서](astra10/public-protocol/REPORT-OFFICIAL-PROTOCOL.md).

앱의 mapping pose caller는 표시 z를 0으로 만든다(M 18970, 19520). 로봇 원자료의 z가 0이라는 뜻은 아니다. `/operation`의 quaternion에는 0.3 slerp가 있고, mapping의 `updateRobotOdom`은 받은 자세를 직접 적용한다. 공개 재구현의 0.15 smoothing을 현행 공식 mapping 동작으로 옮겨 쓰지 않았다.

카메라 영상은 `handleOpenVideo`로 별도 영역을 여닫고 canvas 크기를 맞춘다(M 18696). 카메라 intrinsics/extrinsics로 지도 위 픽셀을 등록하거나 시야 부채꼴을 계산하는 경로는 해당 renderer에서 발견되지 않았다. 연결 끊김 UI나 송신 함수의 반환만으로 STOP·귀환·충돌 회피가 보장되지 않는다.

## 공개 구현과 대조한 결과

| 저장소 | 고정 commit | 이번 조사에서의 역할 |
|---|---|---|
| [legion1581/unitree_webrtc_connect](https://github.com/legion1581/unitree_webrtc_connect) | `e0abc5780761539eff89a382a79319e5cf6ad1f4` | WebRTC 프레임·복셀 decoder·기원 링크 비교 |
| [abizovnuralem/go2_ros2_sdk](https://github.com/abizovnuralem/go2_ros2_sdk) | `b440609591a249e7bdd4bbc88e056a3660575447` | ROS 변환·점군 필터·저장 비교 |
| [VectorRobotics/unitree_webrtc_connect](https://github.com/VectorRobotics/unitree_webrtc_connect) | `cbf7c3f1e15dd4e8778637f3843f20663febe52e` | decoder 분기·빈 입력 처리 비교 |
| [phospho-app/go2_webrtc_connect](https://github.com/phospho-app/go2_webrtc_connect) | `b011298ce6b32b268c5596baf7e0928e8821ad03` | decoder·upstream·라이선스 파일 확인 |
| [legion1581/unitree_ui의 3D mapping branch](https://github.com/legion1581/unitree_ui/tree/8beafb4200965b33c64718e2717f975eff06d54e) | `8beafb4200965b33c64718e2717f975eff06d54e` | 이전 APK를 참조한 브라우저 구현과 공식 배포본 직접 비교 |

공개 UI의 `public/libslam.wasm` 7,410 bytes와 `public/libvoxel.wasm` 9,520 bytes를 직접 받아 공식 APK의 두 WASM과 대조했다. **둘 다 바이트 동일**하다. 각각 SHA-256은 다음과 같다.

- 점 누적: `df28d833bc3045e58e110926dd87c312538a2e5b60a964a4fc5e99ff06d39b9c`
- 복셀 mesh: `1ba27f065199954dc562b233aa38ea775ac687118cce77b5c71bc14e17e05542`

이는 이 두 바이너리에 한정된 동일성이다. UI 전체·센서 설정·로봇 펌웨어까지 같다는 뜻은 아니다. 공개 코드에 이미 노출된 동일 WASM을 이번에 공식 APK의 실제 호출부와 연결하고 합성 입력으로 검증한 것이다. 새 비공개 정제 알고리즘을 발견했다고 표현하면 과장이다. [직접 대조 기록](astra10/evidence/final-verification.json).

반면 ROS SDK의 SOR(이웃 20, std ratio 2 등의 설정), 높이/범위 필터, 저장용 voxel 축약은 그 공개 구현의 기능이다. **이를 Unitree 공식 앱의 필터 설정이라고 말하면 틀린다.** 공개 UI의 pose 0.15 보간, 최근 trace 200점, shader B=0.3도 이번 공식 웹 코드와 다른 부분이다.

4개 저장소의 상세 함수와 upstream 추적은 [공개 프로토콜 조사](astra10/public-protocol/REPORT-public-protocol.md), [UI 추가 대조](astra10/public-protocol/SUPPLEMENT-unitree-ui-reference.md)에 있다. 후자는 공식 평문 확보 전 작성돼 “공식 동등성 미확인”으로 남긴 항목이 있다. **그 문서의 당시 한계와 이번에 확인한 두 WASM 동일성을 구분한다.**

## FOOTHOLD에 적용할 구체 설계

아래는 **아직 구현·실기 검증하지 않은 설계 제안**이다. Unitree의 확인된 구현과 섞지 않는다. 상세 수식·고정 버전 근거는 [MAP-TRANSFER.md](astra10/map-transfer/MAP-TRANSFER.md).

### 지우개: 표시 정리부터 자동화하고, 주행 지도 삭제는 후보 검토로

우리가 필요한 것은 “적은 점으로 깨끗한 화면”뿐 아니라 “위험한 지하 공간에서 작은 장애물과 개구부를 잃지 않는 지도”다. 공식 앱의 key 억제는 후자를 보장하지 않는다.

| 층 | 자동화할 일 | 바꾸면 안 되는 다른 층 |
|---|---|---|
| 3D 화면 | 범위 제한·표시용 voxel·점 수 예산·선택적 이상점 숨김 | 원 점군, 2D 점유, 로봇 costmap |
| 저장 지도 편집 | 작은 군·낮은 반복 관측·재관측 차이를 잡음 후보로 강조. 원본과 비교·되돌리기 | 후보라는 이유만으로 occupied→free를 확정하지 않음 |
| 순간 장애물 | 별도 센서 관측을 marking·ray clearing에 사용 | 표시를 숨겼다는 이유로 실제 장애물 제거 금지 |
| 진입 금지·감속 | 지도 판에 연결된 polygon/mask와 서버 제어 규칙 | 그림 위 색칠만으로 제어 적용을 주장하지 않음 |

VoxelGrid는 대표점 축약이고 SOR는 이웃 거리의 통계적 이상점 제거다. 두 기법 모두 “관측이 성기지만 실제인 작은 물체”를 자동으로 안전한 바닥으로 바꾸는 근거가 아니다. [PCL VoxelGrid](https://pointclouds.org/documentation/tutorials/voxel_grid.html), [PCL SOR](https://pointclouds.org/documentation/tutorials/statistical_outlier.html).

Nav2 Jazzy의 DenoiseLayer도 대안 후보지만, 고립 장애물 제거 시 해당 칸을 `FREE_SPACE`로 바꾼다. 지우개 버튼 뒤에 기본 활성화할 기능으로 제안하지 않는다. 먼저 원자료와 후보 표시를 비교하고 실제 작은 장애물의 보존을 평가해야 한다. [공식 DenoiseLayer 소스](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_costmap_2d/plugins/denoise_layer.cpp).

**무반사·빈 angle bin·점이 없음은 바닥이 안전하다는 뜻이 아니다.** 특히 집수정 개구부는 수평 장애물 scan에서 빈 공간처럼 보일 수 있다. unknown을 유지하거나 별도 낙차 근거로 금지해야 한다. 자동 삭제의 성능은 삭제율이 아니라 실제 장애물 보존·근거 없는 free 생성·지도 정합 오차로 평가한다. 수치 목표는 원자료를 측정한 뒤 정하며 이번 조사에서 임의 통과 기준을 만들지 않았다.

```python
# 설계 의사코드. 현재 제품에 구현된 함수가 아니다.
raw = retain(cloud, acquisition_time, tf_history, calibration_id)
display = voxel_reduce_for_display(raw)
candidates = propose_noise(raw, repeated_observations, map_revision)
show(raw, display, candidates)  # 운영 점유 지도는 아직 바꾸지 않는다.
draft = review_cell_edits(candidates, before_values, evidence)
validate_replay_and_map_consumers(draft)
activate_versioned_bundle(draft)  # 임무 상태·적용 판 확인 후
```

### 0.05 m 격자 + 3D 점군

기획의 L1 점군을 slam_toolbox에 그대로 꽂는 연결은 성립하지 않는다. slam_toolbox는 LaserScan·odometry/TF를 전제로 한다. 3D 점군을 2D scan으로 투영할 높이 구간, 자세 보정, 각도별 coverage와 무반사 처리부터 필요하다. 단순 높이 절단으로 사족보행 roll/pitch와 스캔 내부 운동 왜곡이 모두 해결되는 것은 아니다. [slam_toolbox README](https://github.com/SteveMacenski/slam_toolbox/blob/02afdde003313a10b8d21461a92d9e5f4f0bc5f2/README.md), [pointcloud_to_laserscan 구현](https://github.com/ros-perception/pointcloud_to_laserscan/blob/595bc926f2df2e1a199e776c42d43ade868e3777/src/pointcloud_to_laserscan_node.cpp).

웹은 Three.js 한 scene에 XY 격자 평면·점군·자세·경로를 두고, 2D/3D 탭에서 카메라와 표시 층을 바꾸는 구조가 적합하다. 2D는 orthographic, 3D는 perspective를 쓸 수 있다. 복셀 표시와 ROS 좌표 사이에 반복 축 변환을 두지 말고 **ROS z-up**을 공통으로 쓴다. 로봇 모델 자체 축의 보정만 별도 부모 객체에 둔다.

메시지 최소 계약은 `map_id`, `revision`, `frame_id`, `stamp`, `encoding`, `resolution`, `width/height`, `origin`이다. 센서 calibration 판도 연결한다. 0.05 m는 지도 칸 크기이며 위치 정확도나 최소 검출 장애물 크기가 아니다. 46 × 27 m라면 920 × 540 = **496,800칸**이고 int8 원자료는 496,800 bytes, RGBA 표시 버퍼는 1,987,200 bytes다. 이는 산술이며 실제 성능 측정값이 아니다.

칸 (i,j)의 중심은 다음 식을 쓴다. φ는 지도 원점 yaw, r은 해상도다.

```text
index = i + width * j
world_xy = origin_xy + R(phi) * [r*(i+0.5), r*(j+0.5)]
grid_xy = R(-phi) * (world_xy-origin_xy) / r
Canvas pixel row = height-1-j
Canvas continuous y = height-grid_y
```

CSS 확대·DPR·pan/zoom 역변환도 클릭 좌표에 적용한다. Texture는 nearest로, Y 반전은 딱 한 곳에서 적용한다. ROS `OccupancyGrid`의 unknown(-1)과 Nav2 내부 costmap의 unknown(255)을 같은 배열 형식으로 취급하지 않는다. [OccupancyGrid 정의](https://github.com/ros2/common_interfaces/blob/a941f14bb318d8d904505ed935ccbb97f24a70a4/nav_msgs/msg/OccupancyGrid.msg), [Three.js DataTexture](https://github.com/mrdoob/three.js/blob/9b4a2ac29c63ccb43fd51c5661f2f873ac2c39b8/src/textures/DataTexture.js).

Nav2 Jazzy의 StaticLayer·AMCL은 분석한 변환에서 map origin의 x/y를 사용하지만 grid 자체 yaw를 반영하지 않는다. 웹만 회전 지도를 지원해 서로 다른 장소에 목표를 보내지 않도록 주행용 지도는 **origin yaw=0 계약**을 권장한다. 회전 import가 필요하면 점유 의미를 보존해 재격자화하고 모든 소비자에 같은 판을 배포해야 한다. 이는 해당 소스의 정적 확인이며 모든 ROS 판에 대한 일반화는 아니다. [StaticLayer](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_costmap_2d/plugins/static_layer.cpp), [AMCL](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_amcl/src/amcl_node.cpp).

3D 누적에는 추가 문제가 있다. loop closure로 과거 pose가 바뀌면 이전 TF로 붙인 점들이 중복 벽으로 남는다. keyframe과 graph 판을 보존해 재배치하거나 재생성해야 한다. 그 연결이 없으면 `정합된 저장 3D 지도` 대신 **최근 3D 관측**으로 표시한다.

PGM을 지워도 slam_toolbox pose graph가 편집되는 것은 아니다. graph에서 다시 지도를 만들면 지운 점유가 돌아올 수 있다. PGM/YAML·graph·display cloud·keepout/speed mask·waypoint를 판으로 묶고, 수정 내역과 소비자 적용 상태를 관리해야 한다. 이 판 확인 절차는 ROS 기본 ACK가 제공하는 기능이 아니라 우리 adapter에서 구현할 일이다.

### 위치·방향·시야·경로

`map → odom → base_link` 변환을 자료 시각에 맞춰 적용한다. 로봇 yaw 화살표와 카메라 heading을 같은 것으로 가정하지 않는다. mapping과 localization 모드에서 같은 TF를 서로 다른 노드가 동시에 소유하지 않도록 한다. [REP-103](https://github.com/ros-infrastructure/rep/blob/11ca24a41f31480dfb9562ba99f2a5b93d3ebda5/rep-0103.rst), [REP-105](https://github.com/ros-infrastructure/rep/blob/11ca24a41f31480dfb9562ba99f2a5b93d3ebda5/rep-0105.rst).

| 겹칠 정보 | 좌표·시간 기준 | 화면 동작 |
|---|---|---|
| 로봇 위치·방향 | 같은 stamp의 map 변환과 pose | 신선도·추정 불확실성 표시. 보기용 보간으로 원자료를 덮지 않음 |
| 카메라 부채꼴 | 해당 영상의 CameraInfo, base→camera 외부 보정, crop/resize 후 투영 | 보정이 없으면 `개략 시야` 또는 미표시. 벽 뒤도 보인다고 표현하지 않음 |
| 지나온 경로 | 각 pose의 stamp·map 판 | 계획 경로와 다른 선 종류. 원 궤적 보존 |
| 남은 계획 경로 | 현재 plan ID·map 판 | 실제 계획점을 사용. 미관상 곡선으로 안전 궤적을 변형하지 않음 |
| 측정값·발견물 | 측정/영상 시각의 pose·센서 위치·지도 판 | 최신 pose에 과거 측정값을 찍지 않음 |
| 목표와 도착 방향 | pointer 역변환·drag의 atan2 | 선택 → 경로/제약 확인 → 실행. 단순 클릭으로 이동하지 않음 |

중앙 대칭 pinhole의 수평 시야는 `2*atan(W/(2*fx))`지만, 실제 부채꼴은 활성 영상의 K/P와 양 끝 ray를 써야 한다. 광축이 body 방향과 다르거나 crop이 비대칭이면 위 단순식을 그대로 쓰면 안 된다. 실제 가시 영역은 깊이·가림 검사가 없는 부채꼴만으로 알 수 없다. [CameraInfo 정의](https://github.com/ros2/common_interfaces/blob/a941f14bb318d8d904505ed935ccbb97f24a70a4/sensor_msgs/msg/CameraInfo.msg).

D435i·XT-16은 기획에서 장착 미확인이다. 이 기기를 장착한 것으로 전제한 시야·점군 설계를 하지 않는다. 실기에서 사용할 L1·전방 카메라의 실제 토픽·보정·시각부터 확보한다.

## 검증 현황과 다음 구현 순서

### 직접 실행한 확인

| 범위 | 결과 | 결과가 보장하지 않는 것 |
|---|---|---|
| APK manifest 도구 | 알려진 ApiDemos 값 일치 후 Unitree 분석 | 난독화된 앱 전체 복원 |
| 공식 평문 자산 | 38개 크기·SHA-256 재확인 | native·firmware 전체 |
| WASM 단독 | 점 15건·mesh 13건의 알려진 입력 통과 | 실제 센서 분포·성능 |
| 공식 worker wrapper | 점 5건·mesh 2건·이미지 1건 통과 | main 전체와 GPU 픽셀 결과 |
| 렌더 함수 | 공식 메서드 추출 2건 통과 | 브라우저 전체 화면 |
| 수신 프레임 | normal/special 2건 통과 | 실제 WebRTC 패킷 전송 |
| 좌표 산술 | 회전 지도 6칸 왕복, 행 반전, 방향, 합성 FOV, 크기 계산 통과 | 실제 지도 정합·카메라 보정 |
| 공개 WASM | 공식 두 파일과 바이트 동일 | 공개 저장소 전체의 공식성 |

wrapper 부모 재실행 때 초기화 대기를 event-loop 12회로 둔 테스트 도구가 한 번 실패했다. **테스트 도구만** worker의 `check`/`ready`를 최대 5초 기다리도록 고친 후 다시 통과했다. 이 실패는 앱 알고리즘 실패로 집계하지 않았다. 원 worker와 WASM hash는 그대로다.

재현 명령은 저장소 루트 기준이다. 외부 로봇 접속이나 명령 전송 없이 수행한다. 마지막 Python 명령은 공개 GitHub의 두 WASM을 읽어 대조한다.

```powershell
node --max-old-space-size=128 --wasm-max-mem-pages=1536 inbox/jay/20261013-go2-app-study/astra10/wasm-analysis/fixtures.cjs points
node --max-old-space-size=128 --wasm-max-mem-pages=1536 inbox/jay/20261013-go2-app-study/astra10/wasm-analysis/fixtures.cjs mesh
node --max-old-space-size=128 --wasm-max-mem-pages=1536 inbox/jay/20261013-go2-app-study/astra10/wasm-analysis/fixtures-wrappers.cjs points
node --max-old-space-size=128 --wasm-max-mem-pages=1536 inbox/jay/20261013-go2-app-study/astra10/wasm-analysis/fixtures-wrappers.cjs mesh
node --max-old-space-size=128 --wasm-max-mem-pages=1536 inbox/jay/20261013-go2-app-study/astra10/wasm-analysis/fixtures-wrappers.cjs image
node inbox/jay/20261013-go2-app-study/astra10/renderer_fixtures.cjs
python inbox/jay/20261013-go2-app-study/astra10/finalize_evidence.py
```

결과는 [단독 점](astra10/wasm-analysis/fixtures-points.json), [단독 mesh](astra10/wasm-analysis/fixtures-mesh.json), [wrapper 점](astra10/wasm-analysis/fixtures-wrappers-points.json), [wrapper mesh](astra10/wasm-analysis/fixtures-wrappers-mesh.json), [wrapper 이미지](astra10/wasm-analysis/fixtures-wrappers-image.json), [프레임](astra10/public-protocol/official-framing-fixtures.json), [최종 해시·산술](astra10/evidence/final-verification.json)에 있다.

### 요청한 기술별 판정

| 항목 | 판정 · 추적 범위 |
|---|---|
| 압축·decoder·누적 | 확인됨. 프레임 parser, 두 worker, 두 WASM, 렌더 연결 |
| 실제 frame_id·수신률·점당 시각 | 미확인. topic·timer만 확인. 실제 패킷·bag 없음 |
| 잡음 제거 | 중복 억제는 확인됨. 통계적/의미적 정제는 조사 worker에서 발견 못 함. firmware 미확인 |
| 다운샘플·voxel | 입력 복셀과 출력 노출면 확인. 누적 key를 정상 3D voxel 축약으로 볼 수 없음 |
| 평활·보간 | 경로 곡선과 일부 자세 보간 확인. 점 위치 평활은 해당 경로에서 발견 못 함 |
| 높이색 | 두 경로 각각 확인. 바닥/장애물 의미 분류 근거 아님 |
| 바닥·장애물·낙차 구분 | 조사 클라이언트에서 분류 구현 못 찾음. robot-side는 미확인 |
| 오래된 점 제거 | capacity ring 교체 확인. 시간 기준 TTL/동적 물체 분류는 발견 못 함 |
| 렌더·카메라·모델·경로 | Three.js, Points/mesh, controls, pose, path 확인. 정밀 LOD 체계는 발견 못 함 |
| 영상 정합·FOV | 영상 UI 분리 확인. 보정된 map 등록·시야 계산은 해당 지도 경로에서 못 찾음 |
| 지도 파일·명령 | uslam 시작/종료/저장/위치/목표/순찰의 클라이언트 경로 확인. robot ACK·실제 수행 미검증 |

### 다음 단계의 우선순위

1. **실기 자료 계약 확보.** 짧은 같은 실행에서 원 점군·IMU·odom·TF·카메라 보정·영상 시각·실제 PCD/PGM/메타데이터를 확보한다. 펌웨어·앱 판과 센서 장착을 함께 적는다. 공식 앱과 ROS SDK가 같은 로봇 결과를 읽는지 먼저 확인한다.
2. **정제 없이 정합부터 통과.** 0.05 m 격자와 원 점군, 로봇 pose, 원 계획 경로를 같은 map에 얹는다. 비대칭 모서리 표식·음수 원점·90° 회전·DPR 2·클릭 좌표 왕복을 시험한다. 저장 후 Nav2에서 다시 읽은 셀 의미도 비교한다.
3. **표시 전용 축약 비교.** voxel 크기·점 예산별 화면과 원자료를 나란히 보고 실제 얇은 장애물·벽·문턱 보존을 측정한다. 공식 WASM을 제품 의존성으로 가져오는 대신 공개 라이선스 도구 또는 독립 구현을 쓴다.
4. **잡음 후보와 지우개 연결.** 작은 물체·개구부·가려진 벽·동적 사람·희소 반사를 포함한 재생 자료에서 후보를 검토한다. 자동 free 생성은 검증 전 활성화하지 않는다. 편집은 원본·이유·되돌리기·지도 판을 남긴다.
5. **관제 정보와 명령 연결.** 영상 시각의 FOV·측정값·통신 구간을 붙이고, 목표 확인·도착 방향·금지/감속·STOP의 실제 서버/로봇 적용을 확인한다. 이 단계는 이번 앱 분석으로 완료된 것이 아니다.

## 약관·재사용·로컬 보관 상태

Unitree 공식 [약관 페이지](https://www.unitree.com/terms/)가 제공한 [Product EULA](https://www.unitree.com/disclosure/protocol/Unitree%20Product%20End%20User%20License%20Agreement%20%28EULA%29.docx) §1.2의 금지 목록에는 다음 문구가 있다.

> “Reverse engineering, decompiling, disassembling, cracking, or tampering with the hardware, firmware, built-in software, or SDK of the Product”

이어 소스/알고리즘 취득 시도도 제한한다. 이것은 확인한 **Product EULA 문구**이며 Android 앱에 어떤 계약으로 적용되는지, 법적 예외가 있는지까지 판단한 것은 아니다. 원문은 [Unitree-EULA.docx](astra10/downloads/Unitree-EULA.docx), SHA-256 `bc664d6de5cde927d4e287eef686ed7a830de8b7cb1617e31341c410bba8dc97`로 보존했다.

REA는 MIT이나 앱·WASM·로봇 모델에 대한 재사용 허가를 대신하지 않는다. 공개 SDK도 일괄 MIT가 아니다. legion의 MIT와 파일별 고지, go2_ros2_sdk의 BSD 계열·하위 Apache 고지, 별도 LICENSE를 확인하지 못한 fork를 구분해야 한다. 공개 저장소에 APK 유래 WASM이 있다고 그 바이너리의 권리까지 공개 소스 라이선스로 확정되지는 않는다. [라이선스 대조와 출처](astra10/public-protocol/REPORT-public-protocol.md), [REA LICENSE](astra10/evidence/REA-LICENSE).

APK·SDK 설치본·복원 원문·raw tool dump는 `astra10/.gitignore`로 git 추가에서 제외했다. 보고서·hash·재현 스크립트·분석 결과는 별도로 남긴다. **원본을 NAS에 옮기거나 다른 곳에 게시하지 않았다.** 이 로컬 폴더를 삭제하면 해당 입력이 사라지므로 보고서만 보존하는 것과 완전 재현 보관은 다르다. 전체 앱 소스나 인증 관련 문자열을 보고서에 복사하지 않았다.

저장소 밖 변경과 남겨 둔 실행 환경은 다음과 같다.

- REA setup이 Orca Codex 홈 `C:/Users/AI-WS01/AppData/Roaming/orca/codex-runtime-home/home/config.toml`에 통합 설정을 추가했다. 원본 백업은 `.rea.backup` 접미 파일. 값은 보고서에 옮기지 않는다.
- REA skill은 `C:/Users/AI-WS01/.agents/skills/reverse-engineer-anything/`에 설치됐다. npm 도구 cache는 사용자 npm-cache 아래다.
- `C:/Tools/astra10-tools`는 이 작업의 `astra10/tools`를 가리키는 junction이다. Android SDK의 비 ASCII 경로 문제를 피하는 데 사용했다. 별도 시스템 Python 패키지 설치 대신 작업 폴더의 의존성을 사용했다.
- 격리 에뮬레이터 AVD `astra10_go2`, serial `emulator-5580`을 실행했다. PID 기록은 [emulator-owned.pid](astra10/logs/emulator-owned.pid). 종료를 실행하지 않았다. 재현 후 정리할 때 다른 세션의 emulator·ADB 서버를 일괄 종료하면 안 된다.
- adb localhost forward와 게스트 내 분석 보조 파일이 남을 수 있다. OS/SDK 도구가 만든 사용자 cache 전체는 전수 조사하지 않았다. 추가 변경이 전혀 없다고 주장하지 않는다.

남의 변경이 많은 공유 checkout에서 pull·merge·rebase·commit·push를 하지 않았다. 지정 조사 폴더에 신규 산출물과 재현 코드를 두었고 기존 연구·학습·웹 파일은 수정하지 않았다. 원격 로봇·학습·GPU 작업은 실행하지 않았다.
