> 분류: 리서치
> 작성: 오흥재 · analyst · 2026-11-02
> 근거: 공식 UnitreeGo 2.0.0 APK 재해시 · 복원 웹 자산 · REA 6.4.0 · unitree_sdk2 8e1b9275
> 요지: Sport_Mode 정책을 파일로 가져오는 경로는 확보하지 못했다. SDK 상태 기록은 가능한 대안이나 정책 action 정답과는 다르다.
> 상태: 읽기 분석 완료 · 실기 연결·명령 전송·정책 추출 없음 · 보드 내부 구현 미확인

# R2 · 공식 보행을 가져올 수 있는가

끝 · 정책 파일 취득 경로 미확인, 실기 모방 자료 수집안 작성 · 막음 0(분석 범위). 실기 수집은 별도 실행 결정 사항이다.

## 무엇을 확인했나

**현재 확보한 APK만으로 Sport_Mode 보행 정책·가중치·제어기를 추출해 시뮬레이션에 옮길 수 있다고 말할 근거는 없다.** 공식 앱은 sport API 명령을 보내고 상태를 받아 그리는 경로를 갖는다. SDK의 `Move(vx,vy,vyaw)`도 행동망의 가중치를 주는 API가 아니다.

| 조사 대상 | 이번 확인 | 한계 |
|---|---|---|
| 공식 APK | 2,589 ZIP 항목. SHA256 `7a36e9a847997ebea02d88fde6ccdd6e5c4c8d3f7e57619584b3c6718bfa2cf1`, 10/13 기록과 일치 | 최신 펌웨어·최신 앱 전수 분석 아님 |
| 흔한 모델 확장자 | onnx/pt/pth/tflite/pb/mnn/rknn/engine/weights/bin 검색에서 `DebugProbesKt.bin`만 후보 | 확장자 없는 자산·암호화·네이티브 내장·추가 다운로드까지 부재 증명하지 않음 |
| 앱 명령 | `main-LIOZh9o1.js:1134`는 api_id와 자료를 `SPORT_MOD`에 보냄. store 7132행은 `rt/api/sport/request`로 연결 | 정책 내부 계산은 이 경로에서 보이지 않음 |
| 화면 관절 | main 10929~10932행은 수신 `motor_state[0..11].q`를 화면 모델에 전달 | 보이는 보행은 정책 파일의 공개 증거가 아님 |
| 공식 SDK | `sport_client.hpp:31~76`: Move·Stand·보행 모드 API | 다운로드·가중치 export API는 이 헤더에 없음. 전체 펌웨어에 없다는 뜻 아님 |

APK 원본은 `C:/Users/AI-WS01/data/go2-app-study-20261013/astra10/downloads/UnitreeGo.apk`, 웹 원자료는 같은 뿌리의 `runtime-web/`에 있다. 이번 해시·검색 범위·REA 식별자는 [GO2-APK-evidence.json](GO2-APK-evidence.json)에 보존했다. 앱 원본·복원 소스는 남의 저작물이므로 이번 공개 커밋에 넣지 않았다.

기존 REA의 Android 결과는 `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20261013-go2-app-study/astra10/logs/rea-android-package.json`이며, 기존 보고서에는 DEX 보호로 핵심 네이티브 경로를 충분히 확보하지 못했다고 명시돼 있다. 이번에는 REA CLI로 실제 `runtime-web/js/robot/` 두 파일을 다시 정적 분석했다. Evidence `ev_5b52f98f222c5c082579b0b20caf68b1e36a1520ff62a42bc376c58a5113e634`, 산출 `_out/1102/rea-robot.json`. 의존성 밖 호출·동적 로딩·로봇 보드는 이 결과의 범위 밖이다. MCP 등록 drift는 확인했지만 설정을 고치지 않고 설치된 CLI를 사용했다.

## SDK로 모을 자료

공식 소스 기준은 [unitree_sdk2 8e1b927586712edd6a4c29d50dd52dff1e163439](https://github.com/unitreerobotics/unitree_sdk2/tree/8e1b927586712edd6a4c29d50dd52dff1e163439)다. 이번에 원문을 읽었으며 다음은 제공 자료형이지 우리 로봇의 실측 수신 결과가 아니다.

| 기록 | 원문 근거 | 용도·주의 |
|---|---|---|
| 관절 q, dq, ddq, tau_est | `include/unitree/idl/go2/MotorState_.hpp:23~32` | tau_est는 추정 토크이며 목표 토크나 정책 출력 아님 |
| IMU·motor_state·tick·발 힘 | `include/unitree/idl/go2/LowState_.hpp` | 실제 발행률·유효 필드는 펌웨어에서 확인 |
| 몸 위치·속도·yaw 속도·발 위치/속도 | `include/unitree/idl/go2/SportModeState_.hpp:24~44` | 추정값·좌표계·시각 의미를 별도로 검증 |
| 보낸 명령·모드·응답 | `include/unitree/robot/go2/sport/sport_client.hpp:39~76` | operator 로그와 실제 robot state를 둘 다 저장 |
| 저수준 상태 구독 | `example/go2/go2_low_level.cpp:16,101~103` | 이 예제는 lowcmd 발행도 포함한다. 통째 실행하지 않고 수집기는 구독 전용으로 분리 |

자료 계획:

1. 로봇 판·펌웨어·Sport_Mode·관절 이름/순서·센서 시각을 먼저 고정한다. ROS 2 또는 SDK DDS의 실제 토픽·QoS·발행률을 읽고, 로봇 시각과 수신 monotonic 시각을 함께 남긴다. 목표 기록률은 가정으로 100~500 Hz 범위, 실제 제공률을 잰 뒤 정하며 보간으로 높은 실측률처럼 꾸미지 않는다.
2. 기본 자세, 정지→전진→정지, 좌우 회전, 저속 횡·후진을 대칭 조건으로 모은다. 평지부터, 계단은 기본 수집 검증 뒤 별도 승인된 실기 작업으로 한다. 각 세션에 명령·접촉·자세·넘어짐·사람 개입·지형·배터리 상태와 동기 영상을 연결한다.
3. 빠진 표본·시계 점프·관절 순서 반전·정지 명령에도 잔여 운동 같은 답 아는 입력으로 수집기를 먼저 확인한다. 토크 부호·단위와 포화, 지지 중 발 속도, 질량중심 정보의 실제 제공 여부를 검증한다.
4. **목표 관절각·목표 토크를 수신하지 못하면**, 측정 q나 tau_est를 그대로 정책 action의 정답으로 쓰지 않는다. 상태 궤적 모방·동작 사전학습·보행 보상 기준으로 먼저 사용한다. 실제 desired q/dq/kp/kd/feedforward torque가 합법적으로 제공되고 시각 정렬이 될 때만 직접 행동 모방 자료로 승격한다.
5. 훈련/시험은 연속 프레임 무작위 분할 대신 실험 세션·지형·명령 묶음을 분리한다. 모방 뒤 성능 평가는 실제 명령 추종·좌우 대칭·접촉 위상·전이 동작에서 한다. 공식 제어기의 내부 상태를 볼 수 없으므로 하나의 관측에서 같은 행동이 나온다는 보장은 없다.

**권고:** 지금은 「공식 정책을 받았다」가 아니라 「공식 보행의 상태 궤적을 선생 자료로 모을 수 있는지 확인」을 R2로 계획한다. 정책 원본 제공은 Unitree의 별도 제공 범위 확인이 필요하다. 로봇 인증 우회·펌웨어 추출·저수준 제어 전환은 요청하지도 실행하지도 않았다.
