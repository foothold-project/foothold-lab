# 공식 국제판 2.0.0과 1.12.10의 차이

> 분류: 리서치
> 작성: 오흥재 · 2026-11-20
> 근거: 공식 다운로드 응답 전체 SHA · 두 APK 원본 · REA MCP · craft-anything · 10/13 분석 기록
> 요지: 최신 공식 다운로드 파일의 실제 차이는 장치 관리·음성·사용 제한 문구와 AS2 자산이며, Go2 모델과 지도 WASM은 같다.
> 상태: 정적 차이 확인됨 · 활성 기능과 보호 코드의 동작은 미확인
> 판: v1.0

분석 실행: analyst-lx. app-design-lx의 21:40 전달 요청에 따라 [1.12.10 분석](REPORT-UNITREE-1.12.10.md)에 추가했다. 아래 파일·문구 차이는 `확인됨`, 실제 기기 지원과 앱 실행 중 호출은 `미확인`이다.

**이번 공식 주소의 파일은 10월 13일에 분석했던 2.0.0과 바이트가 같다.** 이름만 같은 새 빌드가 아니다. 그렇지만 1.12.10과 비교하면 공통 장치 관리와 다른 로봇 모델 지원 자료가 늘었다. 이를 우리 Go2 X 보행이나 지도 알고리즘의 새 기능으로 바로 옮겨 말할 수는 없다.

## 1. 공식 파일을 직접 다시 확인

[Unitree 공식 국제판 다운로드 주소](https://global-fitness-static.unitree.com/robot/app/UnitreeGo.apk)를 2026-11-20 21:43 KST에 직접 읽었다. 로컬에 중복 저장하지 않고 받은 전체 바이트의 해시를 계산했다.

| 항목 | 1.12.10 | 공식 URL의 2.0.0 |
|---|---|---|
| 파일 bytes | 185,490,971 | 191,452,888 |
| versionCode | 144 | 202 |
| package | `com.unitree.doggo2` | 동일 |
| min / target SDK | 29 / 35 | 동일 |
| 웹 묶음 자체 표기 | `v1.2.44.12`, 2026-06-09 | `v1.2.44.81`, 2026-07-24 |
| ZIP entries | 2,557 | 2,589 |
| native 라이브러리 | arm64 20개 | arm64 20개 |
| Android 구성요소 | activity 111 · service 9 · provider 9 | activity 105 · service 8 · provider 8 |

2.0.0 SHA256은 `7a36e9a847997ebea02d88fde6ccdd6e5c4c8d3f7e57619584b3c6718bfa2cf1`이다. HTTP 200, Content-Length 191452888, Last-Modified `Mon, 03 Aug 2026 03:41:19 GMT`였다. 이 해시는 전달된 로컬 파일 및 [10/13 종합 분석](../20261013-go2-app-study/REPORT-astra-10.md)의 해시와 같다. **이 시각의 해당 국제판 URL 응답**을 확인한 것으로, 다른 배포 채널·지역판까지 최신이라고 보증하지 않는다. [다운로드 대조 영수증](evidence/latest-2.0.0/official-download-verification.json).

새 APK에 REA의 `inspect_android_package`, `decode_android_resources`를 실제 MCP로 호출하고 craft의 `android-package-show`, `android-app-graph-build`를 실행했다. 두 파서의 package·version·SDK가 일치했고 ZIP CRC도 통과했다. 이전 도구 결과를 새 파일의 검사 결과로 가장하지 않았다.

## 2. 새로 생긴 화면 선언과 자원

| 묶음 | 새 원자료 | 판단과 한계 |
|---|---|---|
| 장치 관리 | `com.unitree.doggo2.ui.v2.device.DeviceActivity`; `device_title_info/net/motor/audio/peripheral/safe/server` | About Robot·Network·Motor·Audio·Peripheral·Security·Services 분류가 생김. 실제 화면 배치·전환은 미확인 |
| 연결 | `com.unitree.lib_ble.ui.netInput.BleNetActivity` | BLE 네트워크 입력 관련 activity 추가. 연결 방식 전체가 바뀌었다는 뜻은 아님 |
| 다른 로봇 진단 | `com.unitree.a2.ui.log.LogReportActivity`, `com.unitree.a2.ui.radar.As2RadarInfoActivity` | A2/AS2 이름의 로그·레이더 진단 화면 선언. Go2 X 전용 기능 아님 |
| 장치 설정 문구 | Robot Name·SN·IP·Connection Mode·OTA permission·Device log·Remote control function testing | 장치 식별·연결·업데이트 권한·진단 관련 자원 추가. 실제 주소·serial·사용자 값은 수집하지 않음 |
| 미성년자 모드 | `minor_btn_title`, `minor_over_limit_*`, 비밀번호 생성·확인 관련 resource name | 사용 제한과 잠금 UI의 자료가 존재. 시간 제한은 `%1$d minutes` 변수여서 실제 제한 분 수는 이 자료로 정할 수 없음 |
| 음성 방식 | `voice_offline`, `voice_type_1~4` | Offline Voice Playback·Wake-up Conversation·Keypad Conversation·Close·Develop Conversation 문구. 오프라인 재생 문구를 오프라인 음성 인식이나 LLM 지원으로 바꾸어 해석하지 않음 |
| 보정 명칭 | `app_title_leg_standard`: Legs → Body Calibration; `app_title_imu_standard` 추가 | 보정 화면 명칭 정비. 제어 파라미터·보정 알고리즘 변경 증거는 아님 |
| 리모컨·표정 명칭 | Remote Control → Remote Control Binding; 기본 언어의 표정 관리 문구가 중국어에서 영어로 변경 | 기존 기능 문구 변경. 새로운 운동 능력의 증거는 아님 |

기본 언어 table은 1,401 → 1,415개다. key 기준 **43개 추가·29개 삭제·4개 값 변경**이다. 중국어는 1,066 → 1,105개, 한국어 145개는 key와 값이 그대로다. 별도 `en` table은 두 판 모두 없고 기본 table에 영어가 있다. 웹 내부 번역·화면은 이 집계에 포함하지 않았다. [기계 대조 자료](evidence/latest-2.0.0/version-diff.json)의 `selected_ui_changes`, `resource_diffs`에 원 key와 확인값이 있다.

## 3. 로봇 모델 로딩이 확장된 흔적

새 파일로 `urdfDecompress.worker-*.js`, `js/robot/RobotModelLoader*.js`, `models/as2_description.tar.xz`가 들어 있다. 앞의 JS 본문은 보호되어 호출을 읽지 않았다. 이름만으로 loader가 동작한다고 확정하지 않는다.

압축 모델 자료는 보호 코드가 아닌 일반 tar.xz라 내용 목록과 URDF XML을 읽었다. 안에는 `as2_description/as2.urdf` 21,881 bytes와 `as2_description/lib.glb` 9,232,688 bytes 두 개가 있다. URDF robot name은 `as2`, link 18개, joint 17개다. joint 종류는 floating 1 · revolute 12 · fixed 4개다. 이는 실제 XML을 센 값이다.

**추측:** 고정 Go2 모델만 다루던 화면을 여러 로봇 설명 자료에 대응시키는 방향일 수 있다. 하지만 Go2 X에 AS2 모델을 쓰거나, 이 URDF를 실제 제어기의 관절·동역학 설정으로 가져오는 것은 이번 자료가 뒷받침하지 않는다. 우리 앱에서는 로봇별 모델·좌표계·관절 계약을 데이터로 분리하는 참고가 된다.

## 4. 바뀌지 않은 중요한 것

다음 여덟 파일은 1.12.10과 **SHA256까지 같다**.

- 지도 WASM 두 개: `libvoxel-Bqa6xB-f.wasm`, `libvoxel-doIu-r8s.wasm`.
- Go2 계열 모델 네 개: `Go2.glb`, `Go2Root.glb`, `Go2JX.glb`, `Go2JXRoot.glb`.
- 나머지 모델 두 개: `charge.glb`, `environment.glb`.

따라서 1.12.10에서 다시 실행한 28개 WASM 시험의 **동일 바이너리 수준 결과**가 2.0.0에도 해당한다. 서로 다른 높이의 점이 누적 출력에서 합쳐지는 반례와 reset dictionary 잔존도 같은 모듈의 동작이다. **2.0.0 앱이 그 경로를 실제로 쓰는지, JS에서 우회했는지는 별도 미확인**이다. 모듈이 같다는 이유로 지도 UI의 개선이 전혀 없다고 결론 내리지 않는다.

native 라이브러리 20개 중 같은 경로에서 바뀐 것은 `libbaiduprotect.so` 하나다. 나머지 native 바이트가 같아도 앱 전체의 동작이 같다는 뜻은 아니다. 새 JS는 29개이고 전부 strict UTF-8 텍스트로 읽히지 않았다. 보호 해독은 하지 않았다.

ZIP 경로 기준으로는 86개 추가·54개 삭제·627개 변경·1,876개 동일이다. Vite 파일명의 hash 부분이 바뀌면 추가/삭제로 잡히므로 **새 기능 86개라는 뜻이 아니다.**

## 5. 사라진 선언도 기능 삭제로 단정하지 않는다

manifest에서 Alipay 관련 activity, Unitree Pay·PaySuccess, WeChat Pay entry, XUpdate service/provider/activity 등 합 12개 선언이 사라졌다. 기본 언어의 삭제 key 29개도 Alipay·XUpdate 계열이다. `INSTALL_PACKAGES`, `REQUEST_INSTALL_PACKAGES`, `READ_MEDIA_IMAGES` 권한 선언이 빠졌다.

이것은 결제·앱 업데이트 구성요소가 이 APK에서 달라졌다는 근거다. 서비스가 무료가 되었다거나, 로봇 firmware OTA가 없어졌다고 말할 수는 없다. 오히려 OTA permission 문구는 새로 존재한다. 앱 설치 업데이트와 로봇 firmware 업데이트를 분리해서 봐야 한다.

## 6. 우리 설계에서 놓치지 않을 것

| 확인된 자료에서 얻은 질문 | 우리 앱의 설계 검토 항목 |
|---|---|
| 장치와 로봇 종류가 늘어도 화면이 맞는가 | 모델명·capability에 따른 메뉴·모델·관절 계약 분리. Go2 X에 없는 동반 모드는 지원으로 표시하지 않기 |
| 연결·기기 정보와 행동 제어가 뒤섞이지 않는가 | Network·Services·Security·Motor 상태를 서로 다른 의미로 표시. 명령 성공과 단순 연결 성공을 구분 |
| 미리보기와 실기 상태가 구분되는가 | 동일한 사전 애니메이션 자산이 있어도 실제 보행 정책이나 실기 pose의 증거로 사용하지 않기 |
| 음성 기능을 과장하지 않는가 | 깨우기·버튼 대화·재생을 구분하고, 인식·추론 위치와 오프라인 가능 범위를 우리 구현 근거로 명시 |
| 제어자 권한과 사용 제한이 필요한가 | 미성년자 모드를 그대로 복사하기보다, 우리 운영자의 권한·실기 시작/정지·세션 점유 계약으로 검토 |
| 표시 지도와 정책 입력 지도가 혼동되지 않는가 | 원 점군·표시 메시·높이맵·통과 가능성 지도를 구분. 지도 WASM의 반례를 그대로 이어받지 않기 |

이는 설계 참고이며 순정 앱을 그대로 만드는 안이 아니다. 로봇·계정·클라우드 접속, 보호 해제, craft의 유료 rebuild·코딩 에이전트 실행은 없었다. 네트워크 사용은 공개 자료·공식 APK를 읽는 데 한정했다.

## 재현과 원자료

```bash
python3 inbox/jay/20261120-go2-app/compare_versions.py \
  --old /home/jay/mai/projects/tutorial-go2/UnitreeGo_1.12.10.apk \
  --new /home/jay/mai/projects/tutorial-go2/UnitreeGo_2.0.0_global_20261120.apk \
  --data /home/jay/data/go2-app-study-20261120 \
  --output /home/jay/data/go2-app-study-20261120/latest-2.0.0/recomputed
```

스크립트는 추가·삭제·수정·동일이 모두 있는 알려진 입력을 먼저 대조하고, 두 APK SHA·CRC·두 manifest 파서 일치를 검증한다. 원자료는 `data/.../latest-2.0.0/evidence/`에 있고, 동료의 `app-design-1119/apk/latest/`는 수정하지 않았다. [자료 해시](evidence/latest-2.0.0/RAW-SHA256SUMS), [전체 비교 요약](evidence/latest-2.0.0/version-diff.json).

## 변경 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v1.0 | 2026-11-20 | 공식 응답 직접 대조 · 1.12.10 대비 정적 차이 · 앱 설계 검토 항목 |
