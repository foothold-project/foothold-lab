> 분류: 리서치 · ASTRA10 공개 구현 비교
> 작성: 오흥재 조사 보조 · 2026-10-13
> 근거: 아래 4개 공개 저장소의 고정 commit 소스 · GitHub API · 합성 입력 검증
> 요지: 공개 구현은 압축 voxel 복원과 별도 ROS 정제를 보여 준다. 공식 앱의 잡음 제거 알고리즘이나 주기를 확인한 증거는 아니다.
> 상태: 공개 소스 확인됨 · 합성 함수 검증 완료 · 로봇/공식 앱 동작 미측정

# ASTRA10 · 공개 Go2 LiDAR 프로토콜과 지도 처리 비교

## 범위와 결론

`APP-PLAN-facts.md`의 지우개 자동화, 2D 0.05 m 격자와 3D 점군, 로봇 위치·방향·시야·경로 연결에 한정했다. 공식 APK, 로봇, 실시간 패킷은 이 조사에서 실행하거나 관찰하지 않았다. 아래의 모든 코드 동작은 공개 구현의 동작이다.

공개 코드가 직접 보여 주는 것은 **LZ4 압축 해제 → 비트 점유 voxel의 좌표 복원 → 뷰어 표시 또는 ROS 후처리**다. 이 복원 자체를 자동 잡음 제거라고 부를 근거는 없다. SDK에는 거리·높이·통계적 이상점 제거가 따로 있지만, 누적 지도의 오래된 점 삭제와 좌표계 처리에는 검토할 문제가 있다. 따라서 현 기획의 지우개를 바로 없애기보다, 정제 후보와 사용자 수정 기록을 나누고 실제 현장 자료로 효과를 확인할 필요가 있다. 이 마지막 문장은 적용 제안이다.

## 조사 revision과 재현 자료

| 공개 저장소 | 고정 commit | commit 날짜 UTC | 역할 |
|---|---|---|---|
| [legion1581/unitree_webrtc_connect](https://github.com/legion1581/unitree_webrtc_connect/tree/e0abc5780761539eff89a382a79319e5cf6ad1f4) | `e0abc5780761539eff89a382a79319e5cf6ad1f4` | 2026-08-17 | WebRTC 프레임 분리, native/libvoxel decoder, Three.js 예제 |
| [abizovnuralem/go2_ros2_sdk](https://github.com/abizovnuralem/go2_ros2_sdk/tree/b440609591a249e7bdd4bbc88e056a3660575447) | `b440609591a249e7bdd4bbc88e056a3660575447` | 2026-07-13 | ROS 변환, 누적, 필터, SLAM/Nav2 설정 |
| [VectorRobotics/unitree_webrtc_connect](https://github.com/VectorRobotics/unitree_webrtc_connect/tree/cbf7c3f1e15dd4e8778637f3843f20663febe52e) | `cbf7c3f1e15dd4e8778637f3843f20663febe52e` | 2025-06-02 | 과거 native/libvoxel 구현 비교 |
| [phospho-app/go2_webrtc_connect](https://github.com/phospho-app/go2_webrtc_connect/tree/b011298ce6b32b268c5596baf7e0928e8821ad03) | `b011298ce6b32b268c5596baf7e0928e8821ad03` | 2025-08-22 | 별도 fork의 같은 복원 방식 비교 |

각 저장소 디렉터리의 `metadata.json`에 API로 받은 commit, license 분류, 파일 목록을 보관했다. 선택적으로 내려받은 파일과 SHA-256은 `source-manifest.json`에 있다. `source/`는 위 고정 revision의 원문이며, 인증·암호화 구현과 자격증명 값은 조사 대상으로 삼지 않았다. `libvoxel.wasm` 바이너리는 내려받거나 실행하지 않았다.

## 압축과 좌표 복원

| 질문 | 공개 코드에서 확인한 내용 | 근거 |
|---|---|---|
| binary 프레임 구분 | `WebRTCDataChannel.deal_array_buffer`는 앞의 little-endian uint16 두 개가 `(2,0)`이면 앞 4바이트를 넘기고 LiDAR용 파서로 보낸다. LiDAR용 파서는 uint32 JSON 길이를 읽고 내부 offset 8 이후 JSON, 그 뒤 binary를 분리한다. 원래 전체 프레임 기준 JSON 시작은 12이다. 일반 프레임은 uint16 길이와 offset 4를 사용한다. | [webrtc_datachannel.py L126-L163](https://github.com/legion1581/unitree_webrtc_connect/blob/e0abc5780761539eff89a382a79319e5cf6ad1f4/unitree_webrtc_connect/webrtc_datachannel.py#L126-L163) |
| 압축 | native `decompress`는 `lz4.block.decompress`에 메시지 `src_size`를 전달한다. | [lidar_decoder_native.py L25-L30](https://github.com/legion1581/unitree_webrtc_connect/blob/e0abc5780761539eff89a382a79319e5cf6ad1f4/unitree_webrtc_connect/lidar/lidar_decoder_native.py#L25-L30) |
| voxel 비트 배열 | 바이트 인덱스 n에서 `z=n//2048`, `y=(n%2048)//16`, `x_base=(n%16)*8`. 각 바이트를 MSB부터 펼쳐 켜진 비트에 점을 놓는다. 즉 x 128칸, y 128칸으로 읽는 구현이다. | [bits_to_points L32-L58](https://github.com/legion1581/unitree_webrtc_connect/blob/e0abc5780761539eff89a382a79319e5cf6ad1f4/unitree_webrtc_connect/lidar/lidar_decoder_native.py#L32-L58) |
| 실제 좌표 | 출력은 `index_xyz * resolution + origin`. 0.05는 함수 기본값이다. 실제 `decode` 호출은 수신 메시지의 `resolution`을 명시적으로 넘긴다. 항상 5 cm라는 실기 결론은 낼 수 없다. | [decode L60-L68](https://github.com/legion1581/unitree_webrtc_connect/blob/e0abc5780761539eff89a382a79319e5cf6ad1f4/unitree_webrtc_connect/lidar/lidar_decoder_native.py#L60-L68) |
| libvoxel 경로 | wrapper는 wasm export `e`를 호출해 positions, UV, indices, face/point count를 돌려받는다. origin.z/resolution의 내림값도 전달한다. wrapper만으로 내부 denoise나 원본 APK와의 동일성을 확인할 수 없다. | [lidar_decoder_libvoxel.py L119-L160](https://github.com/legion1581/unitree_webrtc_connect/blob/e0abc5780761539eff89a382a79319e5cf6ad1f4/unitree_webrtc_connect/lidar/lidar_decoder_libvoxel.py#L119-L160) |
| 기본 decoder | `UnifiedLidarDecoder` 기본값은 `libvoxel`, native를 별도로 선택할 수 있다. 반환 구조도 native의 `points`와 wasm의 `positions/uvs/indices`가 다르다. | [lidar_decoder_unified.py L5-L30](https://github.com/legion1581/unitree_webrtc_connect/blob/e0abc5780761539eff89a382a79319e5cf6ad1f4/unitree_webrtc_connect/lidar/lidar_decoder_unified.py#L5-L30) |

VectorRobotics와 phospho의 native decoder도 같은 비트 순서와 좌표식을 쓴다. legion은 이를 NumPy로 벡터화하고 빈 배열 반환을 처리한다. 알려진 합성 입력에서 세 구현 모두 같은 5점을 복원했다. 빈 voxel 입력은 legion이 `(0,3)` 모양으로 반환했고 두 fork는 `ValueError`를 냈다. 이것은 공개 함수의 합성 검증 결과이며 실제 수신 데이터 호환성 검증은 아니다. [Vector L32-L59](https://github.com/VectorRobotics/unitree_webrtc_connect/blob/cbf7c3f1e15dd4e8778637f3843f20663febe52e/go2_webrtc_driver/lidar/lidar_decoder_native.py#L32-L59), [phospho L31-L60](https://github.com/phospho-app/go2_webrtc_connect/blob/b011298ce6b32b268c5596baf7e0928e8821ad03/go2_webrtc_driver/lidar/lidar_decoder_native.py#L31-L60), 로컬 `synthetic-verification.json`.

## 표시가 정제를 뜻하지 않는 사례

legion의 `plot_lidar_stream.py`는 `positions`를 셋씩 묶고 `np.unique`로 중복을 줄인 다음, x축 π/2와 z축 π 회전, y 구간 자르기, 매 메시지 평균 중심 빼기를 한다. 해당 수신 경로에서는 가져온 origin을 좌표에 더하거나 resolution으로 스케일하지 않는다. 이 예제 화면을 세계 좌표 지도나 실거리 측정 UI로 그대로 옮기면 안 된다는 판단이 가능하다. [상수 L51-L55](https://github.com/legion1581/unitree_webrtc_connect/blob/e0abc5780761539eff89a382a79319e5cf6ad1f4/examples/go2/data_channel/lidar/plot_lidar_stream.py#L51-L55), [수신 처리 L165-L205](https://github.com/legion1581/unitree_webrtc_connect/blob/e0abc5780761539eff89a382a79319e5cf6ad1f4/examples/go2/data_channel/lidar/plot_lidar_stream.py#L165-L205).

`filter_points`는 입력을 그대로 반환한다. 색은 재중심화한 점의 유클리드 거리로 만든 scalar를 HSL hue에 넣는다. 새 데이터마다 이전 Three.js pointCloud/voxelMesh를 제거하고 새 객체로 교체한다. 이 예제에서는 높이 색상, 시간 누적 지도, 시간 경과 잡음 소거를 확인하지 못했다. 뷰어 `PerspectiveCamera(60,...)`의 60은 화면 카메라 값으로, 로봇 전방 카메라 FOV 근거가 아니다. [filter L104-L106](https://github.com/legion1581/unitree_webrtc_connect/blob/e0abc5780761539eff89a382a79319e5cf6ad1f4/examples/go2/data_channel/lidar/plot_lidar_stream.py#L104-L106), [뷰어 L334-L335, L390-L433](https://github.com/legion1581/unitree_webrtc_connect/blob/e0abc5780761539eff89a382a79319e5cf6ad1f4/examples/go2/data_channel/lidar/plot_lidar_stream.py#L334-L433).

SDK의 `update_meshes_for_cloud2`는 positions에 메시지 resolution과 origin을 적용하고, UV 두 값의 최솟값을 `intensity`라고 부른다. 임계값보다 큰 XYZI만 남기고 동일 XYZI를 중복 제거한다. 호출부 임계값은 0이다. UV 유래 값이 실제 LiDAR 반사 강도라는 실증은 없으므로 화면에 이를 센서 반사강도로 확정해 쓰지 않는다. 합성 함수 검증에서 0 제거와 중복 제거를 확인했다. [lidar_decoder.py L19-L65](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/go2_robot_sdk/infrastructure/sensors/lidar_decoder.py#L19-L65), [ros2_publisher.py L191-L211](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/go2_robot_sdk/infrastructure/ros2/ros2_publisher.py#L191-L211).

RViz 설정도 `Axis: Z`가 있다는 이유만으로 높이 색상이라고 읽으면 틀린다. 같은 블록의 실제 `Color Transformer`는 `Intensity`, 표시 형태는 `Boxes`, 크기는 약 0.05 m이고 `Enabled: false`다. 설정에 0.05가 있는 사실과 공식 앱의 표현을 혼동하지 않는다. [single_robot_conf.rviz L241-L274](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/config/single_robot_conf.rviz#L241-L274).

## 잡음 지우개 자동화 후보와 제한

SDK의 C++ `PointCloudAggregatorNode`는 유한 좌표 검사, XY 거리 구간, z 높이 구간, PCL StatisticalOutlierRemoval을 적용한다. SOR 설정은 이웃 20개와 표준편차 배수 2.0이며, 점이 100개를 넘을 때 적용한다. 이는 공개 SDK의 명시적 후처리 후보이지 로봇 내부나 공식 앱의 알고리즘 증거가 아니다. [pointcloud_aggregator_node.cpp L11-L30, L41](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/lidar_processor_cpp/src/pointcloud_aggregator_node.cpp#L11-L41), [applyFilters L146-L186](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/lidar_processor_cpp/src/pointcloud_aggregator_node.cpp#L146-L186).

누적과 삭제는 다음처럼 구분해야 한다.

| 구현 | 실제 코드 | 기획에 주는 제한 |
|---|---|---|
| C++ `PointCloudAggregator::addPoints` | 0.001 단위 반올림 후 set에 추가. 한도를 넘으면 원점에서 가까운 점을 남긴다. 주석의 oldest와 달리 timestamp 순 삭제가 아니다. | 움직이는 사람, 과거 유령점, 로봇에서 멀어진 점을 정확히 제거하는 로직으로 볼 수 없다. |
| C++ 저장 | `saveMapCallback`의 PLY 저장 직전에 VoxelGrid 적용. | 저장용 다운샘플과 실시간 지도 필터를 구분해야 한다. |
| 후단 C++ aggregator | 최근 cloud를 `publish_rate * 10`개 남긴다. 현재 코드는 수신 timestamp로 나이를 재지 않는다. | 주석의 10초는 실제 보존시간 측정값이 아니다. 입력이 누적 cloud이므로 이전 점이 여러 cloud에 반복해 들어갈 수 있다. |
| 후단 frame | 입력 포인트를 그대로 합한 뒤 header.frame_id를 `base_link`로 지정. | 앞단 `odom` 점군에 대한 TF 변환 없이 이름이 바뀌는 경로다. 위치가 바뀌는 실제 주행에서 확인·수정이 필요하다. |

근거: [addPoints L16-L48](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/lidar_processor_cpp/src/lidar_to_pointcloud_node.cpp#L16-L48), [saveMapCallback L248-L260](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/lidar_processor_cpp/src/lidar_to_pointcloud_node.cpp#L248-L260), [후단 cloud 유지 L112-L138](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/lidar_processor_cpp/src/pointcloud_aggregator_node.cpp#L112-L138), [출력 frame L198-L223](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/lidar_processor_cpp/src/pointcloud_aggregator_node.cpp#L198-L223).

Python 후단에는 `now().to_msg()`의 반환값에 곧바로 `frame_id`를 붙이는 코드도 있다. 정상 ROS Header 생성과 다른 형태라는 정적 검토 결과이며 ROS 실행은 하지 않았다. [pointcloud_aggregator_node.py L212-L218](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/lidar_processor/lidar_processor/pointcloud_aggregator_node.py#L212-L218).

적용 제안: 유한값·거리·높이 제거와 SOR를 각각 켜고 끌 수 있게 하고 원본/정제본을 같은 좌표계에서 비교한다. 얇은 난간·개구부 가장자리·낮은 문턱을 보존하는지는 실측해야 한다. 오래된 3D 점군 소거에는 관측 timestamp, pose, 자유공간 관측을 가진 별도 설계가 필요하다. 확인한 코드에는 이것을 완성된 형태로 제공하는 근거가 없다. 2D 지우개는 원본 지도 덮어쓰기보다 되돌릴 수 있는 편집층으로 남기는 방안이 맞는다.

## 2D 0.05 m와 3D, pose와 경로 연결

SDK mapping launch는 점군 처리 후 `pointcloud_to_laserscan`으로 `/scan`을 만들고 `slam_toolbox`의 online async launch를 포함한다. mapper 설정은 `odom`, `map`, `base_link`, `/scan`과 `resolution: 0.05`를 명시한다. **2D 격자 해상도 0.05는 WebRTC voxel 메시지 resolution과 독립된 설정**이다. 수치가 같아도 같은 지도나 동일 정제 알고리즘이라는 뜻은 아니다. [mapping.launch.py L88-L137](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/launch/mapping.launch.py#L88-L137), [L202-L219](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/launch/mapping.launch.py#L202-L219), [mapper_params_online_async.yaml L12-L32](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/config/mapper_params_online_async.yaml#L12-L32).

Nav2 설정은 local/global costmap에 `/scan` 계열 입력의 `marking`과 `clearing`, raytrace 범위를 적어 둔다. 이는 costmap의 장애물 관측/소거 설정이고, 3D 저장 점군의 영구 삭제나 2D SLAM 지도 지우개 구현이라는 뜻은 아니다. [nav2_params.yaml L189-L265](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/config/nav2_params.yaml#L189-L265).

| 기획 요소 | 공개 코드 근거 | 확인 한계와 연결 방향 |
|---|---|---|
| 로봇 위치·방향 | topic `rt/utlidar/robot_pose`; message `pose.position`과 quaternion `pose.orientation` 추출. ROS publisher는 `odom → base_link`와 odometry로 변환하고 z에 0.07을 더한다. | 이 보정값의 실제 장비 적합성은 미확인. 2D/3D overlay는 `map → odom → base_link`의 같은 timestamp 변환을 써야 한다는 것은 적용 제안이다. |
| 점군 | `rt/utlidar/voxel_map_compressed`; `origin/resolution/stamp/src_size` 메타데이터. ROS publisher는 cloud를 `odom`으로 표기하고 stamp는 현재 ROS 시각으로 설정한다. | 센서시각 보존과 pose 동기화는 별도 확인 대상이다. |
| 지도·SLAM API 이름 | `rt/mapping/grid_map`, `rt/qt_command`, `rt/qt_add_node`, `rt/qt_add_edge`, `rt/qt_notice`, `rt/pctoimage_local`, `rt/lio_sam_ros2/mapping/odometry`. | 상수 이름 존재만 확인했다. command payload, ID 의미, 공식앱 호출 연결, 펌웨어에서 실제 지원되는지는 미확인이다. 이름에 lio_sam이 있어도 내부 SLAM 전체를 확정할 수 없다. |
| 경로와 목표 | RViz Path에 `/transformed_global_plan`, 초기 위치 `/initialpose`, 목표 `/goal_pose`, Nav2 GoalTool이 설정되어 있다. Path는 disabled 상태다. | 실제 publisher와 연결 결과는 미측정. 공식앱 목표 명령 API와 같다는 근거는 없다. |
| 전방 시야 부채꼴 | URDF `front_camera_joint`와 camera calibration 파일이 있다. | 이 조사에서 실제 장비 FOV나 공식앱 부채꼴 구현은 확인하지 못했다. 카메라 내부·외부 파라미터와 실제 스트림 crop을 검증한 뒤 부채꼴을 계산해야 한다. |

근거: [webrtc_topics.py L17-L41](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/go2_robot_sdk/domain/constants/webrtc_topics.py#L17-L41), [robot_data_service.py L27-L34, L47-L84](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/go2_robot_sdk/application/services/robot_data_service.py#L27-L84), [ros2_publisher.py L54-L95](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/go2_robot_sdk/infrastructure/ros2/ros2_publisher.py#L54-L95), [L191-L211](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/go2_robot_sdk/infrastructure/ros2/ros2_publisher.py#L191-L211), [single_robot_conf.rviz L383-L450](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/config/single_robot_conf.rviz#L383-L450), [go2.urdf L136-L140](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/urdf/go2.urdf#L136-L140), [front_camera_720.yaml](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/calibration/front_camera_720.yaml).

## 재사용 약관 확인

법적 결론이 아니라 저장소에 적힌 고지의 확인이다.

| 대상 | 확인한 고지 | 재사용 전 처리 |
|---|---|---|
| legion 루트 | MIT. 저작권·허가 고지 포함 조건. | 루트 MIT와 가져온 파일의 별도 고지를 함께 추적한다. |
| legion·Vector·phospho native/libvoxel wrapper | 파일 머리에 소스/바이너리 재배포 조건과 면책문이 있다. | 파일별 고지를 보존한다. wrapper 고지가 wasm 바이너리의 출처·권리까지 증명하지 않는다. |
| Vector·phospho 저장소 전체 | 조사 commit의 tree에서 LICENSE/COPYING/NOTICE 파일을 찾지 못했고 API license 값도 null. | 전체 저장소를 일괄 MIT 등으로 분류하지 않는다. |
| ROS2 SDK | 루트 BSD-2-Clause, 다수 소스 머리 SPDX는 BSD-3-Clause, `go2_robot_sdk/LICENSE`는 Apache-2.0. | 고지가 혼재한다. 가져올 파일별 권리·고지 관계를 확인해야 하며 루트만 보고 일괄 적용하지 않는다. |

근거: [legion LICENSE](https://github.com/legion1581/unitree_webrtc_connect/blob/e0abc5780761539eff89a382a79319e5cf6ad1f4/LICENSE), [native 파일 고지](https://github.com/VectorRobotics/unitree_webrtc_connect/blob/cbf7c3f1e15dd4e8778637f3843f20663febe52e/go2_webrtc_driver/lidar/lidar_decoder_native.py#L1-L20), [SDK 루트 LICENSE](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/LICENSE), [SDK 하위 LICENSE](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/LICENSE), [SDK 파일 SPDX](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/lidar_processor_cpp/src/pointcloud_aggregator_node.cpp#L1-L2).

## 검증 기록과 남은 질문

`synthetic-verification.json`에 알려진 점 5개를 LZ4 block으로 압축한 입력과 예상/실제 복원 좌표를 기록했다. 3개 native decoder의 5점 결과와 빈 cloud 처리를 실제 실행했다. SDK 함수 하나는 AST로 분리해 NumPy만 주입했고 UV 최소값·threshold·duplicate 처리의 알려진 입력을 확인했다. ROS 노드, wasm, Three.js 화면, 로봇 연결은 실행하지 않았다. 소스 파일 무결성은 manifest SHA-256로 재확인했다.

미확인 항목은 공식 앱의 노이즈 자동 제거 단계, 로봇 송신 전처리, 실제 voxel resolution, 실제 주파수/지연/보존시간, 움직이는 물체 제거, 센서 반사강도 의미, 공식앱 높이 색상, 지도 목표 API의 전체 payload, firmware 버전별 지원, 장비별 좌표/FOV 보정이다. 설정의 timer나 README 수치를 실측 Hz로 바꾸어 보고하지 않았다.
