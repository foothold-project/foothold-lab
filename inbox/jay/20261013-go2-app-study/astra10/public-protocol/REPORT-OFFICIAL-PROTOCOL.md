> 분류: B/항법 · ROS2 · TF · SLAM · Nav2
> 작성: jay · 2026-10-13
> 근거: 공식 APK에서 확보한 로컬 평문 JS · 취득 manifest · 프레임 파서 오프라인 고정 입력 실행
> 요지: 공식 웹앱의 두 지도 route를 구분하고 WebRTC 프레임, uslam 지도 저장, 위치·경로·임무 명령의 실제 클라이언트 흐름을 확인
> 상태: 정적 코드와 제한된 파서 실행 확인됨 · 실기 통신과 실제 화면 동작 미확인

# 공식 APK 평문 JS의 지도 자료와 임무 프로토콜

이 보고서는 `runtime-web/`에 보관된 **공식 APK 출처의 평문 JS**만 근거로 한다. APK 취득·복호화 출처는 상위 조사에서 남긴 [runtime-web-manifest.json](../evidence/runtime-web-manifest.json)에 의존하며, 이 조사에서는 아래 세 파일의 바이트 수와 SHA-256이 manifest와 일치하는지 직접 재확인했다. community 코드 분석인 [REPORT-public-protocol.md](REPORT-public-protocol.md), [SUPPLEMENT-unitree-ui-reference.md](SUPPLEMENT-unitree-ui-reference.md)와 증거를 합치지 않았다. 공개 저장소와 공식 WASM이 같다는 주장은 이 보고서에 없다.

| 별칭 · 파일 | 직접 재확인한 바이트 수 | SHA-256 |
|---|---:|---|
| M · [main-LIOZh9o1.js](../runtime-web/assets/main-LIOZh9o1.js) | 11,785,671 | `cebfc3e7e2d7838cf8adf650d0a32edbf7fbd32df8ede486d7521f96afb6ab15` |
| S · [store.-Ml-K330.js](../runtime-web/js/store/store.-Ml-K330.js) | 1,387,923 | `fcd48d6ea8fe411fe9ca6ea639b70b86f8dd5be515005d06aa655d466e529884` |
| Q · [Slam.BsJuOfhQ.js](../runtime-web/js/slam/Slam.BsJuOfhQ.js) | 250,437 | `7970f500718ef578421e5553e2696f2a30d4caaa9f3e56c2780f4cbb164b4148` |

이하 행 번호는 보관된 평문 파일의 원래 줄바꿈 기준이다. 소스 전체 실행, 앱 UI 실행, WebRTC 연결, 로봇 명령 송신은 하지 않았다. 인증·signaling·비밀값은 조사 범위에서 제외했다.

## 지도 화면의 두 route

**`/lidarMapping`과 `/slam`은 별개 구현이다.** M 20058~20063의 route table에서 `/slam`은 Q를 lazy import하고, `/lidarMapping`은 M의 `LF` 컴포넌트를 사용한다. `LF`는 `mF`의 래퍼이고 `mF.__name`은 `LidarMapping`이다(M 19749~19752, 20028~20033). 따라서 파일 이름 `Slam`만 보고 두 화면의 자료 처리·정제를 같은 것으로 설명하면 안 된다.

M의 `App.setup`은 `sdk:routeChange` 이벤트를 받으며, URL이 `/lidarMapping` 또는 `lidarMapping`일 때 지도 이름과 파일명을 `lidarData`에 기록한다(M 658, 663~668). `kF()`의 페이지 진입 함수는 `lidarData.fileName`이 있으면 `loadLocalPcd`, 없으면 `startNewMap`을 부른다(M 19675~19687). **이 분기는 코드에서 확인했지만, 사용자에게 보였던 특정 화면의 실제 진입 URL은 미확인이다.**

| 구현 | 확인된 프로토콜 경계 | 해석 제한 |
|---|---|---|
| `/lidarMapping`, M의 `YF/GF/SF/JF/kF` | `rt/uslam/*` cloud·odom·path, 문자열 명령, 지도 파일 전송 | 아래 주요 분석 대상. 로봇에서 실제 수신·수행한 증거는 없음 |
| `/slam`, Q의 `Kh()` | `rt/qt_command`, `rt/pctoimage_local`, `rt/qt_notice`, `rt/lio_sam_ros2/mapping/odometry` | Q 4707~4709는 worker 결과의 `.data`를 평가만 함. Q 4725의 odometry 분기도 렌더 업데이트를 하지 않음. Q 4727~4737은 고정 좌표의 점선·화살표·원을 그림. 이 코드만으로 실제 2D 지도·항법 표시를 입증할 수 없음 |

Q 4713~4739는 `startBuildMap`에 `command_:3`, `loadMap`에 5, `endBuildMap`에 4, `queryNode/queryEdge`에 2와 서로 다른 `attribute_`를 연결한다. Q 4724~4725는 `SLAM_PC_TO_IMAGE_LOCAL` 자료를 `/assets/slam.worker-B9-NnJ09.js`에 전달한다. 이 파일에서 명시적 `subscribe()` 호출은 찾지 못했으므로, 이 경로의 구독 성립 여부도 미확인이다. 각 topic의 실제 문자열은 S 7132의 `Ie` enum으로 확인했다.

## WebRTC 수신 프레임과 메시지 경계

S의 `PD` 클래스에서 `channel.onmessage`는 문자열이면 `JSON.parse`, 바이너리면 `dealArrayBuffer`를 호출한 뒤 응답 resolver와 메시지 listener에 전달한다(S 7157~7164). **이 단계는 JSON과 바이너리 payload를 나누는 단계이며 LZ4 해제나 점군 정제는 하지 않는다.**

| `PD` 메서드 | 프레임의 바이트 배치 | 반환값 |
|---|---|---|
| `dealArrayBufferForNormal`, S 7187~7190 | 처음 2바이트를 `Uint16Array`로 JSON 길이 N 해석. JSON은 원 프레임 offset 4에서 N바이트, payload는 4+N 이후 | JSON 객체의 `data.data`에 payload `ArrayBuffer` 대입 |
| `dealArrayBuffer`, S 7183~7186와 `dealArrayBufferForLidar`, S 7191~7194 | 첫 두 `Uint16`이 각각 2와 0이면 앞 4바이트를 제거. 나머지의 첫 4바이트를 `Uint32Array`로 JSON 길이 N 해석. 원 프레임 기준 JSON offset 12, payload offset 12+N | 동일하게 `data.data` 대입 |

코드는 `DataView`의 명시적 endian 옵션 대신 typed array의 native endian을 사용한다. 이 Windows 실행 환경에서는 little endian이었다. 파서 세 메서드만 격리하여, JSON 122바이트와 payload `[128,1,255]`를 넣은 normal 129바이트 및 special 137바이트 프레임을 실행했다. 둘 다 예상 topic과 payload를 복원했다. [official-framing-fixtures.json](official-framing-fixtures.json)에 입력 길이·offset·결과를 보관했다. 이는 **클라이언트 프레임 분리 함수의 고정 입력 검증**이며, 실제 로봇 패킷 캡처나 decoder 검증은 아니다.

`subscribe/unsubscribe`는 채널이 open일 때 `{type,topic}`을 송신한다(S 7310~7324). `publish`와 `publishWithoutCb`의 기본 envelope는 `{type:"msg",topic,data}`다(S 7333~7346). 전자는 메시지 식별 필드를 기준으로 응답 resolver를 저장하고, 후자는 기다릴 callback을 저장하지 않는다. 아래 uslam 문자열 명령은 주로 `publishWithoutCb`를 사용하므로, 함수 반환만으로 로봇의 처리 완료를 뜻하지 않는다. 숫자 `api_id` 요청용 메서드는 별도로 존재하지만(S 7347~7361), 아래 uslam 문자열을 그 API 형식으로 바꾸어 해석하지 않았다.

## `/lidarMapping`의 자료 구독과 worker 전달

S 7132의 `Ie` enum은 M에서 `v`로 import된다. M 19677에서 지도 페이지가 `LIDAR_MAPPING_SERVER_LOG`를 구독하고 메시지·연결상태 listener를 등록한다. 메시지 listener `b`는 공통·신규 지도·미리보기 handler에 메시지를 전달한다(M 19702~19710).

| 목적 · enum | 공식 JS의 topic 문자열 | 실제 연결 지점 |
|---|---|---|
| 일반 실시간 LiDAR · `ULIDAR_ARRAY` | `rt/utlidar/voxel_map_compressed` | S `WC`, 8906 이후에서 구독. M `BA`, 10910~10933에서 메시지를 `/assets/three.worker-BhnsyeGz.js`로 전달. M 10879~10905는 `geometryData`를 `loadPointCloud`로 전달 |
| 새 지도 cloud · `LIDAR_MAPPING_CLOUD_POINT` | `rt/uslam/frontend/cloud_world_ds` | M `GF.r`, 18878~18881 구독. `newMap_rtc_listenLidarData`, 18986~18993에서 `pageType==new`이면 worker에 `{type:"newMap",data}` 전달 |
| 새 지도 pose · `LIDAR_MAPPING_ODOM` | `rt/uslam/frontend/odom` | 동일 `GF.r`에서 구독. M `GF.q`, 18970~18981에서 `pose.pose`를 이동 궤적에 사용 |
| 기존 지도 실시간 cloud · `LIDAR_LOCALIZATION_CLOUD_POINT` | `rt/uslam/localization/cloud_world` | M `SF.uA`, 19537~19569에서 worker에 `{type:"preview",data}` 전달 |
| 기존 지도 pose · `LIDAR_LOCALIZATION_ODOM` | `rt/uslam/localization/odom` | 동일 handler에서 navigationState 2이면 `SF.nA`에 `pose.pose` 전달 |
| 계획 경로 · `LIDAR_NAVIGATION_GLOBAL_PATH` | `rt/uslam/navigation/global_path` | 동일 handler에서 navigationState 2이면 worker에 `{type:"navigation-path",data}` 전달 |
| 명령·상태 | `rt/uslam/client_command`, `rt/uslam/server_log` | M의 `GF/SF/JF/GM`가 각각 `LIDAR_MAPPING_CMD`, `LIDAR_MAPPING_SERVER_LOG`로 사용 |

지도 worker는 M `YF.n`, 18650~18652에서 `/assets/three.worker-VAdOurOh.js`로 생성된다. 결과 handler `YF.q`는 `newMap`이면 `updatePointCloud(output,directOutput)`, `preview`이면 `updateLaserPointCloud(points)`, `navigation-path`이면 `updateNavPathPointCloud(points)`로 나눈다(M 18646~18648). **일반 voxel worker와 지도 worker는 URL과 입력·출력 계약이 다르다.** 압축 복원·누적·색칠·지우개 알고리즘은 이 수신 프로토콜 조사만으로 판정하지 않으며 별도 renderer·worker 분석과 연결해야 한다.

`GRID_MAP = rt/mapping/grid_map`과 `LIDAR_MAPPING_PCD_FILE = rt/uslam/cloud_map`은 S 7132 enum에 있다. 확보된 nonlegacy JS에서 이 두 enum 멤버의 추가 참조는 찾지 못했다. 따라서 **이 앱이 `rt/mapping/grid_map`을 구독해 0.05m 2D 지도를 그린다거나, 저장 PCD를 `rt/uslam/cloud_map` 구독으로 받는다고 말할 근거가 없다.** 이 검색은 확보된 웹 JS에 한정되며 native 코드 전체의 부재를 뜻하지 않는다.

## 새 지도 생성과 저장

`GF.startNewMap`은 순찰 상태를 확인한 후 정지 명령들과 구독 설정을 거쳐 `mapping/start`를 보낸다(M 18886~18895). worker에 `"clear"`를 보내고 화면 이동 궤적도 지운다. 정지 명령들의 결과를 모두 확인하는 일괄 트랜잭션으로 해석하지 않았다.

지도 이름을 입력받은 `handleSave`는 `mapping/stop`을 송신하고 저장 UI timeout을 설정한다(M 18897~18918). 서버 로그가 정확히 `mapping/stop/success`이며 페이지·이름 상태 조건도 맞으면 파일 취득 함수 `T()`를 호출한다(M 18986~18993). 즉 stop 명령 송신 직후 곧바로 완성 PCD를 받는 구조가 아니다.

파일 목록은 `map.pcd`, `map.pgm`, `map.txt`다(M 18638~18642). `GF.b()`는 각 파일에 `rtc_inner_req` 타입, `req_type:"request_static_file"`, `related_bussiness:"uslam_final_pcd"`, `file_path`를 넣어 병렬 요청하고 `response.info.file.data`를 꺼낸다(M 18950~18964). S 7403~7424는 static-file 조각들을 모아 문자열로 합친다. M 18919~18949는 PCD 로딩·스크린샷과 함께 `webSaveLidarData` native bridge에 `img/pcd/pgm/txt/name`을 전달하고 callback의 지도 식별자를 처리한다.

기존 지도를 로봇에 전달할 때에는 `SF`가 `uploadFile`에 조각 크기 30×1024를 전달한다(M 19351~19362). S 7428 이후의 upload 구현은 base64 문자열을 나누어 `push_static_file` 요청으로 전송하고 각 응답의 파일 상태를 확인한다. **다운로드 파일과 native 저장 bridge, 재업로드 요청이 확인된 것이며, PGM 해상도·장애물 판정식·PCD 내부 정제는 여기에서 확인되지 않았다.**

## 위치·목표·계획 경로·순찰

| 흐름 | 실제 코드 동작 | 파일 · 함수 · 행 |
|---|---|---|
| 초기 pose 설정 | 화면에서 얻은 x/y/yaw로 `localization/set_initial_pose/x/y/yaw` 송신 후 100ms 예약으로 `localization/start` 송신 | M `SF.k`, 19408~19428 |
| localization 성공 처리 | `[Localization] initialization succeed!` 로그와 현재 로딩 상태 조건이 맞으면 navigationState를 2로 바꾸고 localization cloud·odom·global path 세 topic 구독 | M `SF.uA`, 19537~19569 |
| 지도 위 목표 선택 | `locateIndicator`가 카메라 ray와 `groundPlane`의 교점을 찾아 x/y를 callback에 전달. `kF`가 이 callback에 `handleSendNavigation`을 연결 | M `locateIndicator`, 18373~18381; `kF`, 19673~19674 |
| 목표 명령 | 선택 task가 `"0"`이 아니고 좌표 길이가 2 이상이면 `navigation/set_goal_pose/x/y/0` 송신. 마지막 yaw는 이 경로에서 고정 0 | M `SF.l`, 19437~19442 |
| 항법 시작·종료 | `navigation/start`, 종료 시 `navigation/stop`과 표시 경로 정리. task 선택 handler가 항법·충전·순찰을 구분 | M `SF.H/z/kA`, 19433~19446, 19492~19519 |
| pose 표시 | 신규 mapping 궤적은 `[x,y,0]`와 받은 orientation 사용. localization 로봇 표시도 z=0으로 바꾸고 받은 orientation 사용 | M `GF.q`, 18970~18981; `SF.nA`, 19520~19537 |
| 계획 경로와 상태 | global path 메시지는 worker 경로 렌더 입력. `navigation/state_transition` 로그의 REACHED·NO_PATH·TIMEOUT·GOAL_OCCUPIED 등으로 UI 상태 변경 | M `SF.uA/yA`, 19537~19595 |
| 순찰점 업로드 | 필요 시 `patrol/start`, 전체 점 삭제, 점 목록 순회, 제한 설정 후 `patrol/go`. 각 점은 `patrol/add_patrol_point/x/y/(yaw-Math.PI)` 형식 | M `JF.y/r/u`, 19130~19158 |
| 순찰 완료 응답 | `patrol/go/success`, `pause/success`, `clear_all_patrol_points/success`, 각 제한 설정 success 로그를 resolver에 연결. 점 추가 루프의 100ms 대기는 점별 완료 응답 대기가 아님 | M `JF`, 19159~19190, 19206~19231 |

여기서 z=0은 **앱 표시용 pose 처리**다. robot odometry가 원래 평면 자료라거나 로봇의 localization/TF가 높이를 버린다는 뜻은 아니다. 코드에 있는 50·150·200ms scheduling 인자를 실측 수신률이나 화면 갱신률로 바꾸지 않았다. 목표 yaw 0, 순찰 yaw 변환도 해당 UI 명령 경로에 한정되며 다른 API 전체의 규칙으로 일반화하지 않는다.

페이지 이탈 시 상태 정리와 unsubscribe가 있으며, 순찰을 계속할지 묻는 분기에서는 일부 정지 명령을 생략한다(M 19602~19608, 19631~19647). 연결 복구 시 활성 상태에 맞춰 세 topic을 다시 구독한다(M 19597~19600). 공통 연결 handler의 15초 후 알림·이탈은 클라이언트 UI 처리다(M 18666~18679). **로봇의 통신 단절 정지·자율 귀환·충돌 회피 동작을 이 코드로 보장할 수 없다.**

## 기획에 직접 연결되는 판단과 남은 범위

- **잡음 지우개 자동화:** 수신 파서는 정제를 하지 않는다. 공식 화면이 신규 누적 지도, localization 실시간 cloud, 계획 경로를 별도 입력·표시 함수로 다루므로, 자동 삭제를 구현할 때 어느 층을 바꾸는지 먼저 구분할 근거는 있다. 이 보고서에는 공식 잡음 제거 알고리즘의 존재·효과를 입증한 내용이 없다.
- **2D 0.05m + 3D:** PCD·PGM·TXT를 함께 취득·저장하는 흐름은 확인됨. 하지만 `rt/mapping/grid_map` enum, PGM 파일명, `/slam` route만으로 공식 2D의 0.05m 해상도·3D와의 정합·완성된 실제 화면을 주장할 수 없다. 계획의 0.05m는 별도 요구·검증 항목으로 유지해야 한다.
- **pose/FOV/path:** 신규 이동 궤적, localization pose, global path의 출처와 표시 분기는 확인됨. 카메라 FOV·extrinsic과 지도 좌표의 정합, pose timestamp 동기화, 렌더 정확도는 미확인이다. 화면 목표는 ground plane 교점의 x/y이며 이 UI에서 목표 yaw는 0이다. 실제 실행 정책은 프로젝트의 별도 확인·실행 규칙으로 설계해야 한다.

프레임 고정 입력 두 건 외의 결과는 정적 소스 확인이다. 앱 버전·native 진입 화면·실기 상태를 바꿔도 같은 경로가 쓰이는지는 미확인이다. 공식 APK 자산의 존재를 오픈소스 재사용 허락으로 취급하지 않았으며, 공개 코드의 재사용 조건은 별도 community 보고서에만 정리했다.
