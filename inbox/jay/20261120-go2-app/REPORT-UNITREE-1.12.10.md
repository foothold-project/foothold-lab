# Unitree Go 1.12.10 분석과 앱 설계 인계

> 분류: 리서치
> 작성: 오흥재 · 2026-11-20
> 근거: 제공 APK 원본 · REA 6.10.1 MCP · craft-anything 0.6.1 Rust 빌드 · 원 WASM 합성 입력 시험
> 요지: 화면·연결·지도·동작 자산을 확인하고, 실제 제어기와 화면 재생을 구분한다.
> 상태: 정적 분석과 격리 WASM 시험 확인됨. 보호 코드의 내부 호출과 실기 실행은 미확인.
> 판: v1.0

분석 실행: analyst-lx. 원본 바이트·도구 응답·합성 입력 결과는 `확인됨`, 보호 코드의 호출 흐름과 실기 동작은 `미확인`으로 구분했다.

**앱의 화면용 동작과 Sport Mode의 실제 보행 제어기는 같은 것으로 취급하면 안 된다.** APK에는 Go2 모델과 사전 제작 애니메이션, 점군·복셀을 화면 자료로 바꾸는 WASM이 있다. 이 자료로 실기 보행 정책을 얻었다거나, 앱 화면에서 같은 정책을 돌린다고 결론 내릴 수는 없다. 실기·에뮬레이터·GPU는 실행하지 않았다.

app-design-lx가 참고할 핵심은 세 가지다. 연결 실패와 제어 점유 상태를 구분한다. 지도 표시 자료를 주행 가능성 판단 지도와 구분한다. 미리보기 애니메이션을 실제 로봇 상태의 증거로 쓰지 않는다.

## 1. 어느 APK를 무엇으로 읽었는가

| 항목 | 실제 확인값 | 근거 |
|---|---|---|
| 원본 | `/home/jay/mai/projects/tutorial-go2/UnitreeGo_1.12.10.apk` | 파일 원본 |
| APK SHA256 | `71c9a34b1ec972f944007d4d8474e1bc3391dca1192fa2b46bc7b19be02a9e27` | 파일 전체 재계산 |
| 크기 | 185,490,971 bytes | ZIP 원본 |
| package / version | `com.unitree.doggo2` / `1.12.10` / versionCode `144` | REA와 craft 별도 파서 일치 |
| SDK | min 29 · target 35 | 두 파서 일치 |
| 웹 묶음 표기 | `v1.2.44.12`, `2026-06-09 14:41:58` | `assets/dist/time.json` 평문. 빌드 시각을 외부에서 검증한 것은 아님 |
| ZIP | 2,557 entries · CRC 전체 검사 통과 | 원본 ZIP |
| native ABI | `arm64-v8a` 한 종류 · `.so` 20개 | 실제 멤버 목록 |
| 원 DEX | 4개 · class definition 합 21,051개 | DEX 헤더를 직접 읽은 값과 craft 일치 |
| manifest 구성 | activity 111 · service 9 · provider 9 · permission 42 | SDK 구성요소도 포함. 사용자 화면 111개라는 뜻 아님 |

수치는 [기계 생성 요약](evidence/evidence-summary.json)의 `apk`, `dex`, `components`에서 다시 읽을 수 있다. [재계산 스크립트](summarize.py)는 APK 해시와 두 파서의 버전·package·SDK가 다르면 멈춘다.

### 도구 설치와 검증

- [REA](https://github.com/morluto/rea) npm `rea-agents@6.10.1`을 `/home/jay/.local/share/rea-mcp`에 설치했다. Codex의 `mcp_servers.rea`를 등록하고, stdio MCP의 initialize·tools/list·실제 Android 분석 호출을 확인했다. 노출 도구 263개. 현재 대화에서는 [MCP 클라이언트](mcp_probe.py)로 실제 서버에 연결했다. 현재 대화의 내장 도구 목록이 자동으로 갱신되었다는 주장은 아니다.
- [craft-anything](https://github.com/storytold/craft-anything) `73771bfacf520a159764ea9f8dd85d9bdf09c86b`를 Rust 1.97.0으로 `cargo build --locked --release -p craft-anything-cli` 빌드했다. 결과 0.6.1, 명령 `/home/jay/.local/bin/craft-anything`. 빌드는 4분 17초에 종료 코드 0이었다.
- REA는 내용이 알려진 Electron fixture의 IPC `fixture:echo`와 bridge `fixtureApi`를 찾아야 통과시켰다. craft는 알려진 ZIP 두 파일의 개수·길이·해시를 대조했다. **craft는 오류 JSON을 내면서 종료 코드 0을 반환한 경우가 있어 JSON의 `error`도 검사했다.**
- REA 이외의 Codex 설정은 전후 구조 비교가 같다. Java/JADX/apktool은 기존 설치를 재사용했다. JADX JAR 해시도 대조했다. [설치 영수증](evidence/installation.json), [재실행 안내](README.md).

### 서명 관찰의 한계

REA는 APK v2 digest 일치와 signer 자기 일관성을 보고했다. craft는 `signature_valid=valid`, `digest_matches=true`를 보고하면서 상위 `verified=false`와 `incomplete required fields`를 함께 남겼다. 따라서 이 보고서에서는 **완전한 서명 검증 통과나 Unitree 공식 배포처 진위 확인이라고 쓰지 않는다.** 인증서 SHA는 `881f31ba2993103ede4b98122ca28dd69150c5be6aab94edd4b0ecc86c7a6a37`이다. 원본 파일을 식별하는 해시 검증과 배포처 신뢰는 별개다.

## 2. 확인된 구성과 보이지 않는 부분

| 층 | 확인됨 | 아직 말할 수 없는 것 |
|---|---|---|
| Android 진입 | `com.sagittarius.v6.StubApplication`, Unitree activity 선언, BLE service | 보호된 실제 activity 구현의 제어 흐름 |
| 웹 진입 | 평문 `index.html`, `simulator.html`가 별도 JS entry를 참조. 제목 `Vite + Vue + TS`와 Vite loader 존재 | 각 화면의 실제 라우트와 네이티브 bridge 호출 |
| 웹 자산 | `store`, `PCDLoader`, `Programming`, `Bluetooth`, `slam`, `three.worker`, `videoTransform.worker`, `ammo` 이름의 파일 | 이름만으로 어느 코드가 실행되거나 실제 물리를 계산한다고 확정할 수 없음 |
| 렌더 모델 | Go2 계열 GLB 4개, 충전 표시와 환경 GLB 각 1개 | 실기 관절 상태와 모델 관절의 변환식·지연 |
| 지도 처리 | 두 WASM의 export·메모리·입출력 동작 재현 | 1.12.10 JS가 어느 출력을 화면·항법에 쓰는지 |
| 통신·음성 기반 | OkHttp, iFlytek, MMKV class 및 native FFmpeg/iFlytek 라이브러리 | 현재 앱의 WebRTC/MQTT 채널·서버 선택·재연결 경로 |

**분석 경계:** JS 26개 모두 strict UTF-8 텍스트로 읽히지 않았다. 보호된 콘텐츠의 해제는 하지 않았다. 읽을 수 있는 원 DEX에서 `com.unitree` 정의 검색은 0개였고, JADX는 `com.unitree.doggo2.R` 한 개를 목록에 보였다. JADX의 package class 수 9,611과 raw DEX definition 수 21,051도 다른 기준이다. 이를 곧바로 도구 오류나 앱 코드 부재로 단정하지 않는다. R 목록을 실제 업무 로직의 디컴파일 성공으로 세지 않았다.

`baiduprotect` 관련 자산·라이브러리와 stub이 있는 사실, 본문을 읽을 수 없는 사실은 확인했다. 구체적인 보호 알고리즘이나 정상 실행 중의 복호화 과정은 이번 분석 범위 밖이다. 이름에 `.js`가 있다는 것만으로 분석 도구가 JavaScript를 읽었다고 표시하지 않았다.

## 3. 화면과 상태 설계에 넘길 근거

아래는 실제 manifest와 resource key의 교차 근거다. **선언·문구가 있다는 뜻이며, 우리 Go2 X에서 버튼이 활성화되는지 확인했다는 뜻은 아니다.** 전체 activity 목록은 [COMPONENTS.tsv](evidence/COMPONENTS.tsv), 선정한 83개 resource key의 기본 언어·중국어 대조 166행은 [UI-EVIDENCE.tsv](evidence/UI-EVIDENCE.tsv)에 있다.

| 기능 묶음 | 실제 자료 | 앱 설계에서 읽을 점 |
|---|---|---|
| 연결·네트워크 | `ConnectActivity`, `ApConnectActivity`, `WifiSTAActivity`, `BluetoothService`; `wifi_connecting`, `wifi_success`, `app_change_wifi_tip` | 탐색·연결 중·연결 성공·AP 전환을 별도 상태로 표현할 근거 |
| 제어 점유 | `app_have_been_reconnected`는 다른 단말이 연결한 경우를 안내 | 통신 끊김과 다른 조종자의 점유를 같은 오류로 합치지 않기 |
| 동작·모드 | `SwitchSportActivity`; General / Advanced / AI 문구; `app_sport_not_support`, `app_sport_close_failure` | 요청한 모드, 장치가 보고한 모드, 실패 사유를 구분 |
| 정지 | `app_dog_stop`, `pet_stop`, 동작 제어 종료 실패 문구 | 화면 버튼의 눌림과 로봇이 정지를 확인한 상태를 구분해야 한다는 설계 권고. ACK 계약 자체는 미확인 |
| 지도·위치 | `Map3DActivity`, `app_map_3d_title`, `app_main_slam`, `app_save_point` | 3D 지도 보기, 항법, 지점 저장의 기능 명칭이 존재 |
| 시뮬·프로그래밍 | `app_main_simulator`, `ProgramWorkshopActivity`, `ProgrammeListActivity`, 별도 `simulator.html` | 미리보기와 실기 실행을 명확하게 구분할 근거 |
| 진단 | 배터리 전압·온도·주기, LiDAR 상태, Body/Thigh/Shank/Wheel motor 문구 | 원자료 시각과 단위를 함께 표시하는 상태 화면의 근거. Wheel 문구는 Go2 X 바퀴 장착 증거가 아님 |
| 보정·적재 | `StandardLegActivity`, `StandardImuActivity`, `LoadActivity`, `OffsetActivity`; mass·COM·inertia·offset torque | 정상 운용과 보정 화면을 분리할 근거. 보정값을 읽거나 변경하지 않았음 |
| 음성·오디오 | `SpeechRecognizeActivity`, `DogAudioActivity`; voice assistant·volume·wake-up words | 음성 입력, 음량, 깨우기 문구가 존재. 실제 한국어 명령 인식이나 로봇 음성 엔진의 실행 위치는 미확인 |
| UWB 동반 | `DogFollowActivity`, 거리·방향·태그 IMU 문구 | 다른 모델까지 들어 있는 공통 APK의 자료. 우리 Go2 X의 지원 기능으로 포함하지 않음 |

기본 문자열 1,401개, 중국어 1,066개, 한국어 145개가 추출되었다. 별도 `en` table은 없고 기본 table이 영어 문구를 포함한다. 위에서 선정한 앱 기능 key 83개는 기본·중국어에만 있으며 한국어 table에는 없었다. 따라서 **한국어 리소스가 조금 있다는 이유로 앱 전체 한국어 지원을 확정하지 않는다.** 웹 내부 번역은 보호 코드 때문에 별도 미확인이다.

## 4. 지도 WASM: 이번 APK 바이트로 다시 확인한 것

두 파일 모두 10/13의 2.0.0 분석본과 SHA256이 같다. 파일명만 비교한 것이 아니다. [기존 fixture](../20261013-go2-app-study/astra10/wasm-analysis/fixtures.cjs)를 변경하지 않고 이번 APK에서 추출한 파일에 실행했다. point 15건, mesh 13건, 합 28건의 단언이 통과했다.

| 모듈 | SHA256 | 실제 기능 |
|---|---|---|
| `libvoxel-Bqa6xB-f.wasm` · 7,410 B | `df28d833bc3045e58e110926dd87c312538a2e5b60a964a4fc5e99ff06d39b9c` | 6바이트 좌표 복원 · 중복 키 억제 · ring 누적 |
| `libvoxel-doIu-r8s.wasm` · 9,520 B | `1ba27f065199954dc562b233aa38ea775ac687118cce77b5c71bc14e17e05542` | LZ4 raw block 복원 · 점유 비트맵의 노출면 메시 생성 |

### 화면이 깔끔해지는 것과 지도 정확도가 좋아지는 것은 다르다

메시 모듈은 이웃 voxel이 가린 내부 면을 출력하지 않는다. 고립 voxel 한 개는 면 6개로 그대로 남고, 인접 두 개는 면 10개, 꽉 찬 2×2×2는 면 24개, 3×3×3은 면 54개가 나왔다. **고립점 제거·바닥 분할·통과 가능성 판단을 했다는 근거는 아니다.** 실험 입력 격자는 128×128×30 bits였다. 이를 공식 앱이 항상 같은 크기·해상도로 수신한다는 주장으로 늘리지 않는다.

점 모듈의 direct 출력은 `min + uint16 × 0.001`이었다. `[1000,2000,3000]`에 minima `[10,20,30]`을 주면 `[11,22,33]`이 나온다. 이는 저장 형식의 간격이며 센서 정확도가 1 mm라는 뜻이 아니다.

중요한 반례도 다시 통과했다. 입력 `[1000,2000,0]`, `[1000,2000,4000]`은 direct 출력에 `[1,2,0]`, `[1,2,4]` 둘 다 남지만, 누적 출력에는 하나만 남았다. 10/13 분석에서는 key의 세 번째 축에 rawZ 대신 rawX를 다시 쓰는 명령을 확인했다. 이번에는 같은 바이트와 같은 반례를 재현했다. **이 누적 경로를 올바른 3차원 downsampling으로 그대로 옮기면 안 된다.** 현재 공식 앱이 direct 출력과 누적 출력 중 무엇을 쓰는지는 미확인이다.

reset 함수만 부르면 dictionary가 지워지지 않는 반례도 재현했다. 따라서 새 지도를 열 때 화면 비우기와 누적 상태 초기화는 별도 검증 대상이다. 앱이 이 문제를 이미 우회했는지는 보호된 호출부를 읽지 못해 알 수 없다.

근거: 로컬 `wasm-fixtures/fixtures-points.json`, `fixtures-mesh.json`; 저장소의 [시험 요약](evidence/wasm-fixture-results.json). 자세한 기존 함수 위치는 [10/13 WASM 보고서](../20261013-go2-app-study/astra10/wasm-analysis/REPORT-WASM.md). 기존 문서가 가리키는 큰 원자료 링크는 옛 보관 경로일 수 있으며, 이번 원자료는 §9 경로를 쓴다.

## 5. 화면의 Go2는 어떤 동작 자료를 갖고 있는가

GLB의 JSON chunk를 직접 읽었다. 네 모델이 갖는 노드·skin·animation 수는 다음과 같다.

| 파일 | 노드 | skin | animation |
|---|---:|---:|---:|
| `Go2.glb` | 51 | 0 | 1 (`Playing`) |
| `Go2Root.glb` | 49 | 1 | 16 |
| `Go2JXRoot.glb` | 48 | 1 | 16 |
| `Go2JX.glb` | 48 | 1 | 17 |

Go2Root의 16개는 `CrossWalk`, `Damp`, `Dance1`, `FingerHeart`, `FrontJump`, `FrontPounce`, `HandStand`, `Hello`, `MoonWalk`, `Scrape`, `SideWalk`, `Sit`, `StandDown`, `StandUp`, `Stretch`, `Wallow`다. 로봇의 FL/FR/RL/RR·hip·thigh·calf·foot에 대응하는 이름의 노드가 있다. [기계 요약](evidence/evidence-summary.json)의 `models`에 clip 시간 범위와 채널 수도 남겼다. 모델 원좌표의 단위를 실기 미터로 가정하지 않았다.

이것으로 확인된 것은 **동작 미리보기에 쓸 수 있는 사전 애니메이션이 APK에 들어 있다는 사실**이다. 실제 화면이 어느 상황에서 clip을 재생하는지, 관절 telemetry로 표시하는지, `ammo` 자산으로 별도 물리 시뮬레이션을 하는지는 확인하지 못했다. 애니메이션 이름이 `FrontJump`인 것과 Go2 X가 실기에서 그 동작을 지원하는 것은 별개다.

Sport Mode 정책을 APK에서 추출한 결과는 없다. 인벤토리에서 인식 가능한 ONNX/PT/TFLite 같은 정책 파일은 발견되지 않았지만, 보호된 콘텐츠나 원격 취득 파일까지 없다고 증명한 것은 아니다. 공개 [Unitree SportClient](https://github.com/unitreerobotics/unitree_sdk2/blob/main/include/unitree/robot/go2/sport/sport_client.hpp)는 Move·StopMove·StandUp 같은 명령 API를 제공하고, [Sport API](https://github.com/unitreerobotics/unitree_sdk2/blob/main/include/unitree/robot/go2/sport/sport_api.hpp)는 서비스명 `sport`를 정의한다. 이것은 **공개 SDK 근거이며 1.12.10 APK의 호출 경로를 추출한 근거가 아니다.**

따라서 우리 앱의 미리보기 모델과 로봇 agent의 보행 실행기는 역할을 나누는 것이 타당하다. 실기 보행의 선생 데이터를 원한다면 SDK 상태 기록은 별도 실기 과제이며, 이번 분석에서 로봇으로부터 데이터를 받지는 않았다.

## 6. 통신·음성에서 확인된 것과 미확인

| 관찰 | 근거 등급 | 해석 범위 |
|---|---|---|
| Bluetooth 연결·scan·Wi-Fi·nearby devices·network permission 선언 | 원본 manifest | 권한 요청 가능성. 실제 허용 상태나 통신 성공은 아님 |
| `BluetoothService`, AP 연결·STA 설정 activity | 원본 manifest | BLE·AP·STA 관련 UI/서비스 선언 |
| OkHttp class 333개 | craft DEX 검색 | 라이브러리 포함. 특정 endpoint·인증 방식은 미확인 |
| iFlytek class 330개와 `libmsc.so` | DEX·native 파일 | 음성 SDK 포함. 실제 호출·오프라인/클라우드 구분·지원 언어는 미확인 |
| MMKV class 16개와 `libmmkv.so` | DEX·native 파일 | 로컬 KV 저장 라이브러리 포함. 저장된 사용자 데이터는 읽지 않음 |
| FFmpeg 계열 native 라이브러리 | 원본 ZIP | 미디어 처리 구성요소 포함. WebRTC와 동일하다는 뜻 아님 |
| `org.webrtc`, Paho, HiveMQ 이름의 DEX 검색 0 | 보이는 DEX 검색 | 해당 이름의 Java class를 찾지 못함. 보호 JS/다른 구현 때문에 WebRTC·MQTT 부재 결론은 불가 |
| `usesCleartextTraffic=true` 선언 | manifest | 허용 선언만 확인. 실제 평문 통신 발생이나 취약성 판정은 아님 |

이전 2.0.0 조사나 설명 영상의 WebRTC·MQTT·로컬 bridge 내용을 이번 1.12.10에서 직접 확인한 것처럼 합치지 않았다. 패킷 주기, 명령 타임아웃, 왕복 지연, disconnected 때 로봇의 최종 동작도 **미측정**이다.

## 7. app-design-lx에 넘기는 적용안

다음은 **우리 앱에 대한 설계 제안**이다. Unitree 앱 내부 구현을 확정한 문장이 아니다.

| 우선 적용할 항목 | 근거와 목적 | 확인 시험 |
|---|---|---|
| 연결·점유·기능 지원·실행 결과를 분리 | APK에 서로 다른 상태 문구가 실제 존재 | 단절·다른 제어자·미지원 모드·응답 실패를 각기 주입해 UI가 구분하는지 |
| 시뮬 미리보기와 실기 telemetry를 분리 | GLB 사전 동작과 별도 simulator entry 존재 | telemetry가 끊겼는데 미리보기만 움직일 때 실제 로봇이 움직인 것으로 표시하지 않는지 |
| 화면 지도와 주행 판단 지도를 분리 | 확인된 WASM은 표시용 좌표·메시 처리이며 통과 가능성 판정 근거가 없음 | 표시용 점 감소가 장애물 삭제로 전파되지 않는지 |
| xyz 중복 키·지도 reset 시험 | 이번 원 WASM에서 서로 다른 높이의 점 병합·dictionary 잔존을 재현 | 같은 xy·다른 z 점을 모두 보존, 지도 교체 뒤 이전 점 0개 |
| Go2 X capability에 따른 메뉴 | 공통 APK에 UWB·wheel·여러 모델 자산이 섞임 | 우리 기기에서 확인하지 않은 기능을 지원한다고 표시하지 않는지 |
| 명령의 단위·좌표계·확인 시각을 계약으로 | 이번 APK에서는 그 변환·주기를 확인 못함 | 명령 vx/vy/wz와 관측 pose/joint를 고정 입력으로 대조 |

우리 앱의 SLAM·위치 추정·보행 정책 선택을 이 APK만으로 결정할 수는 없다. 특히 지도 WASM의 이름에 `slam`이 보인다는 이유로 그 모듈이 위치 추정이나 loop closure를 수행한다고 설명하지 않는다.

## 8. 이전 분석과 이번 분석의 관계

| 자료 | 다루는 판 | 이번에 재사용한 범위 |
|---|---|---|
| [10/13 종합 분석](../20261013-go2-app-study/REPORT-astra-10.md) | APK 2.0.0 | 과거 결과의 위치 안내와 비교 기준 |
| [10/13 WASM 분석](../20261013-go2-app-study/astra10/wasm-analysis/REPORT-WASM.md) | 동일 SHA WASM 두 개 | fixture를 그대로 다시 실행하여 동작 확인 |
| `/home/jay/mai/projects/tutorial-go2/analysis/TUTORIAL-GO2.md` | 설명 영상·문서·1.12.10 목록 | 기존 조사 위치. 영상 설명을 현재 APK 런타임 증거로 대체하지 않음 |
| app-design-lx의 `/home/jay/data/app-design-1119/apk/APK-ANALYSIS.md` | 병행 독립 분석 | 상대 작업은 읽기만. 이번 자료를 비교·설계용으로 공유 |
| 이 문서 | 해시 고정 APK 1.12.10 | 새 도구 설치·실제 분석·GLB·resource·WASM 재현 |

같은 WASM을 쓴다는 사실은 JS 전체, 프로토콜, 모든 UI, 로봇 제어기가 두 버전에서 같다는 증거가 아니다.

## 9. 원자료와 남은 확인

큰 원자료 뿌리: `/home/jay/data/go2-app-study-20261120/`.

- `evidence/rea-*.json`: MCP 요청·응답 원본과 evidence ID. `rea-package.json`, `rea-resources.json`, `rea-signature.json`.
- `evidence/craft-*.json`: 독립 manifest 파서·DEX 검색·WASM 검사·구성 graph. graph의 filename 추론과 package 파서의 실제 manifest 해석을 구분한다.
- `extracted/assets/dist/`: 이번 APK의 원 자산. git에 원 모델·코드·APK를 넣지 않았다.
- `wasm-fixtures/`: 변경하지 않은 시험 스크립트와 새 실행 결과.
- `logs/`: 설치·빌드 로그. `craft-target/`: 직접 빌드한 실행 파일.
- 저장소 [자료 해시](evidence/RAW-EVIDENCE-SHA256SUMS), [선정 자산 해시](evidence/ASSET-HASHES.tsv), [설치 영수증](evidence/installation.json), [재현 안내](README.md).

남은 확인은 보호 코드 호출 경로, 실제 패킷·주기·지연, Go2 X별 capability, 화면이 clip과 telemetry를 전환하는 조건이다. 별도 권한과 실제 앱·기기 관찰이 필요한 범위이며, 이번 정적 분석에서 확인했다고 쓰지 않았다. 비밀번호·토큰·키 값은 공유 산출물에 포함하지 않았다.

## 변경 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v1.0 | 2026-11-20 | 1.12.10 해시 고정 · 두 도구 설치와 실제 분석 · WASM 28건 재현 · 앱 설계 인계 |
