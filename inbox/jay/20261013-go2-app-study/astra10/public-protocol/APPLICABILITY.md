> 분류: 리서치 · ASTRA10 기획 적용 요약
> 작성: 오흥재 조사 보조 · 2026-10-13
> 근거: REPORT-public-protocol.md · SUPPLEMENT-unitree-ui-reference.md · 보관한 고정 commit 소스
> 요지: 잡음 정제는 보조 기능으로, 2D·3D는 좌표와 시간을 맞춰, pose·경로는 표시와 기록을 구분해 적용한다.
> 상태: community 소스 확인됨 · 아래 적용안은 제안 · 공식 앱 동등성 및 실기 효과 미확인

# FOOTHOLD 관제 기획에 적용할 것

이 문서는 **community 구현의 분석을 기획에 연결한 요약**이다. 공식 Unitree APK의 동작을 확인했다거나 공개 WASM이 공식 APK와 같다는 주장은 하지 않는다. 코드에 있는 설정값·주석을 실측 주파수나 펌웨어 알고리즘으로 해석하지 않는다.

## 잡음 지우개: 자동 정제 후보를 먼저 보여 주고 편집을 보존

**적용 제안:** 원본 지도, 자동 정제 결과, 사용자가 지운 영역을 분리한다. 거리·높이·통계적 이상점 필터를 선택적으로 적용하고, 원본과 비교한 뒤 채택·되돌리기할 수 있게 한다. 지우개를 없앨 정도로 효과가 입증되지는 않았다.

공개 ROS2 SDK의 `PointCloudAggregatorNode::applyFilters`는 유한값 검사, XY 거리, z 높이 구간, PCL StatisticalOutlierRemoval을 적용한다. 반면 LiDAR native decoder는 LZ4와 비트 점유 배열을 좌표로 복원한다. **복원·중복 제거·다운샘플·색칠만으로 고립 잡음 제거가 되었다고 판정할 수 없다.** [SDK applyFilters, b440609·L146-L186](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/lidar_processor_cpp/src/pointcloud_aggregator_node.cpp#L146-L186), [native decompress/bits_to_points/decode, e0abc5·L25-L68](https://github.com/legion1581/unitree_webrtc_connect/blob/e0abc5780761539eff89a382a79319e5cf6ad1f4/unitree_webrtc_connect/lidar/lidar_decoder_native.py#L25-L68).

누적 점 삭제는 새로 설계할 부분이다. SDK `addPoints`는 한도 초과 시 원점에서 가까운 점을 남기며, 후단은 timestamp 대신 cloud 개수로 보관량을 제한한다. 움직이는 물체나 오래된 유령점 제거라고 부를 근거가 없다. 얇은 난간·문턱·개구부 가장자리까지 필터로 사라지는지 확인해야 한다. 이는 향후 검증 항목이며 이번 조사에서 측정하지 않았다. [addPoints, b440609·L16-L48](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/lidar_processor_cpp/src/lidar_to_pointcloud_node.cpp#L16-L48), [pointcloudCallback, b440609·L112-L138](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/lidar_processor_cpp/src/pointcloud_aggregator_node.cpp#L112-L138).

## 2D 0.05 m와 3D: 같은 장소를 같은 기준으로 표시

**적용 제안:** 2D 격자와 3D 점군의 해상도·원점·좌표계·관측시각을 각각 보존한다. 2D는 계획한 0.05 m/칸을 사용하되, 3D는 수신 메시지의 resolution을 적용한다. 탭 전환 시 위치·목표·편집 영역은 공통 map 좌표에 유지한다.

SDK `mapper_params_online_async.yaml`은 SLAM 해상도 0.05와 `map/odom/base_link`를 명시한다. native `decode`의 resolution은 메시지에서 온다. **두 값은 독립**이다. 공개 `VoxelMap.applyGeometry`는 resolution으로 scale하고 origin으로 이동시키므로 표시 구현의 참고가 된다. 다만 SDK 후단 `publishCallback`에는 변환 없이 입력 점에 `base_link`라는 frame 이름을 붙이는 경로가 있어 그대로 가져오면 좌표 정합을 보장할 수 없다. [SLAM 설정, b440609·L12-L32](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/config/mapper_params_online_async.yaml#L12-L32), [applyGeometry, 590baf·L86-L128](https://github.com/legion1581/unitree_ui/blob/590baf6ab580d27890c7a7575c138a9080d7d516/src/ui/scene/voxel-map.ts#L86-L128), [publishCallback, b440609·L198-L223](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/lidar_processor_cpp/src/pointcloud_aggregator_node.cpp#L198-L223).

3D는 누적 지도와 현재 스캔을 별도 표시하는 구성을 참고할 수 있다. community mapping UI는 worker의 `output`과 `directOutput`을 서로 다른 cloud로 보낸다. 높이색 shader는 sin/cos 순환 함수여서 높이가 달라도 비슷한 색이 반복될 수 있다. 기획에는 단위가 있는 높이 범례와 범위 표시를 따로 정하는 편이 맞다. [worker 결과 분기, 8beafb·mapping-page.ts L342-L363](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/components/mapping-page.ts#L342-L363), [createHeightMaterial, 8beafb·slam-scene.ts L10-L34](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/scene/slam-scene.ts#L10-L34).

## Pose·FOV·경로: 화면 보간과 임무 기록, 목표 실행을 분리

**위치·방향 적용 제안:** quaternion에서 얻은 방향과 위치를 공통 좌표계로 옮겨 로봇·발견물·통신 구역을 겹친다. 화면 표시에는 부드러운 보간을 쓸 수 있지만 기록에는 원래 pose와 timestamp를 남긴다. community UI는 target pose를 저장하고 화면에서 lerp/slerp를 적용한다. 이것은 표시 보간이며 위치 추정 정확도가 향상되었다는 근거가 아니다. [updateRobotPose, 8beafb·slam-scene.ts L201-L222](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/scene/slam-scene.ts#L201-L222), [animate, 같은 파일 L608-L614](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/scene/slam-scene.ts#L608-L614).

**FOV 적용 제안:** 부채꼴은 실제 전방 카메라의 내부 파라미터·장착 변환·스트림 crop을 확인한 뒤 계산한다. SDK에는 `front_camera_joint`와 calibration 파일이 있지만 우리 장비에 맞는지는 미확인이다. Three.js 관찰용 카메라의 시야각을 로봇 카메라 시야각으로 쓰지 않는다. [front_camera_joint, b440609·go2.urdf L136-L140](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/urdf/go2.urdf#L136-L140), [camera calibration, 같은 commit·L1-L26](https://github.com/abizovnuralem/go2_ros2_sdk/blob/b440609591a249e7bdd4bbc88e056a3660575447/go2_robot_sdk/calibration/front_camera_720.yaml#L1-L26).

**경로·목표 적용 제안:** 계획 경로, 실제 이동 기록, 화면에 남기는 짧은 궤적을 구분한다. community UI는 0.1 m 넘게 움직이면 trace를 추가하고 최근 200점만 남기므로 보고서용 전체 경로의 저장소로 쓸 수 없다. 특히 `handlePoseSet`은 목표를 놓을 때 navigation을 자동 시작하는 코드다. 기획의 「지도에서 목표 선택 → 경로 검사 → 실행 확인」에 맞추려면 선택 이벤트와 이동 명령을 분리해야 한다. [handleOdom, 8beafb·mapping-page.ts L2111-L2124](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/components/mapping-page.ts#L2111-L2124), [addTracePoint/updateNavPath, 같은 commit·slam-scene.ts L238-L269](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/scene/slam-scene.ts#L238-L269), [handlePoseSet, 같은 commit·mapping-page.ts L990-L1027](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/components/mapping-page.ts#L990-L1027).

이 적용안은 기획 검토용이다. 실기 정제 효과, 좌표·시간 정합, FOV 정확도, 전체 경로 보존과 목표 확인 전 무이동은 아직 검증하지 않았다. 재사용 파일별 라이선스 고지는 본 보고서의 약관 표를 함께 확인한다. 추가 외부 조회·로봇 실행 없이 기존 자료만 요약했다.
