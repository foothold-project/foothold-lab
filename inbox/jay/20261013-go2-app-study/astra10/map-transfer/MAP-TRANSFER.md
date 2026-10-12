> 분류: 리서치
> 작성: ASTRA10 map-transfer 조사 세션 · 2026-10-13
> 근거: APP-PLAN-facts.md · ROS REP-103/105 · ROS 2 메시지 정의 · Nav2 Jazzy 공식 소스 · slam_toolbox · PCL · Three.js 공식 소스
> 요지: 2D·3D 지도와 자세 표시는 전용 좌표 계약으로 구현 가능하지만, 잡음 제거와 주행 자유 공간 생성은 분리해야 하며 지도·pose graph·costmap의 판 일치를 확인해야 한다.
> 상태: 공식 문서·소스 확인됨 · 수식 합성 입력 확인됨 · Go2 공식 앱 구현과 실기 성능 미확인 · 웹앱 구현 설계 제안

# ASTRA10 · FOOTHOLD 지도 기능 전용 설계 근거

이 문서가 확인한 것은 ROS/Nav2의 공개 형식과 구현이다. Unitree 공식 Go2 앱이 아래 알고리즘을 쓴다는 증거는 아니다. [APP-PLAN-facts.md](../../APP-PLAN-facts.md)의 L1·0.05 m 격자·slam_toolbox·AMCL·2D/3D 탭·잡음 지우개·시야 표시 요구를 읽었다. 원래 [기획 artifact](https://claude.ai/artifact/9q2JtTgeitsnhFTGHTVPgw)는 웹 도구가 접근하지 못했고, 이 조사에서 화면 19장·원 프롬프트·canvas.json은 직접 열람하지 못했다. 기획 요구의 출처는 로컬 요약이며 원 화면 재검증은 미완료다.

## 판단

**먼저 구현할 수 있는 범위는 같은 `map` 좌표에 올린 2D 격자, 3D 점군, 로봇 자세, 경로 표시다.** 잡음 지우개를 자동화하려면 표시만 정리하는 단계부터 시작해야 한다. 지도에서 점이 사라지는 효과가 주행 안전성의 근거가 되지는 않는다.

실제 소스에서 드러난 제약은 다음과 같다.

| 기획과 연결되는 판단 | 확인한 근거 | 구현에 주는 의미 |
|---|---|---|
| L1 점군을 slam_toolbox에 바로 넣는 연결은 성립하지 않는다 | slam_toolbox 입력은 `LaserScan`, 출력은 `OccupancyGrid` [S5] | 점군의 프레임·높이·각도별 투영과 odometry/TF 공급이 필요하다 |
| 0.05 m는 지도 칸 크기다 | `MapMetaData.resolution` [S2] | 위치 오차 5 cm, 장애물 검출 최소 크기 5 cm를 보증하지 않는다 |
| 회전된 지도 원점은 웹과 Nav2에서 다르게 해석될 수 있다 | map loader는 yaw를 보존하지만 StaticLayer와 AMCL의 변환은 x/y만 사용한다 [S7][S8][S9] | 웹은 yaw를 지원하고 주행용 배포는 yaw=0 계약을 권장한다 |
| 지우개 자동화와 닮은 공개 구현이 실제로 있다 | Nav2 `DenoiseLayer`는 작은 연결 군을 제거한다 [S11] | 소스는 제거 칸을 FREE_SPACE로 바꾼다. 표시 필터로 취급하면 안 된다 |
| PGM 편집은 pose graph 편집이 아니다 | slam_toolbox는 image 저장과 graph 직렬화를 별도로 제공한다 [S5] | 이후 graph에서 지도를 다시 구우면 편집 전 장애물이 다시 나타날 수 있다 |
| 지도 적재 성공만으로 판 일치가 증명되지 않는다 | AMCL `first_map_only`, StaticLayer 버퍼와 별도 필터 구독 [S8][S9][S14][S15] | 각 소비자가 실제 적용한 판을 확인하는 앱 프로토콜이 필요하다 |

## L1 입력에서 2D·3D 화면까지

다음은 **설계 제안**이다. 기기에서 나오는 L1 토픽명, frame_id, 점당 시각, 압축 여부, 포인트 속도는 이 조사에서 미확인이다. 실제 장착된 센서와 배포 ROS 버전부터 확인해야 한다.

| 처리 갈래 | 입력과 처리 | 산출물 |
|---|---|---|
| 보관 | 원 점군·IMU·odom·TF·센서 설정을 시각과 함께 보존 | 재처리 가능한 원자료 |
| 2D 정합 | 로봇 자체 점 제거, 자세 보정, 검증한 높이 구간, 각도별 최근접 거리, LaserScan | slam_toolbox의 지도·graph |
| 3D 표시 | 시각에 맞는 TF 적용, 표시용 voxel 축약, 최대 점 수·보관 시간 제한 | Three.js 점군 |
| 주행 장애물 | 별도 검증된 PointCloud2/scan을 obstacle 또는 voxel layer로 공급 | 순간 장애물을 반영한 costmap |
| 낙차·개구부 | 바닥 관측·높이 변화·경계 근거를 별도로 판정 | unknown 또는 명시적 진입 금지 영역 |

`pointcloud_to_laserscan`은 높이 범위와 `target_frame`을 제공하고, 각 각도 구간에서 가까운 점을 택한다. 점 하나도 들어오지 않은 각도는 기본적으로 `+inf`가 된다. 따라서 드문 샘플링, 높이 필터로 제거된 점, 실제 최대거리 무반사를 같은 자유 공간 관측으로 간주해서는 안 된다. 후속 노드의 `inf_is_valid`, scan 범위 처리와 관측 coverage를 함께 검증해야 한다. [공식 변환기](https://github.com/ros-perception/pointcloud_to_laserscan/blob/595bc926f2df2e1a199e776c42d43ade868e3777/src/pointcloud_to_laserscan_node.cpp) [S6]

사족보행의 roll/pitch와 움직이는 한 스캔 내부 왜곡은 별개다. 메시지 전체를 단일 시각 TF로 옮겼다고 deskew가 끝나지 않는다. 점당 시각이 있으면 해당 시각의 자세를 쓰는 보정이 후보이며, 없다면 해당 한계를 남겨야 한다. 수평 투영 프레임의 원점은 실제 또는 검증된 가상 센서 원점과 연결한다. 이동한 원점에서 만든 광선이 원 센서의 가려짐 관계까지 보존한다는 가정도 재검증한다. **이 단락은 투영 구조에서 도출한 설계 제약이며 L1에 적용해 측정한 결과가 아니다.** [PointCloud2 정의](https://github.com/ros2/common_interfaces/blob/a941f14bb318d8d904505ed935ccbb97f24a70a4/sensor_msgs/msg/PointCloud2.msg) [S18]

```text
on_cloud(cloud):
    require_known_schema_and_valid_time(cloud)
    retain_raw(cloud, tf_history, calibration_id)
    compensated = transform_at_acquisition_times(cloud)
    publish_display(voxel_for_display(compensated), frame, stamp)
    scan, observed_bins = project_validated_height_band(compensated)
    publish_mapping_scan(scan, validated_no_return_policy(observed_bins))
    publish_navigation_observations(separately_validated_observations)
```

위는 동작을 설명하는 의사코드다. 재생·TF·필터 노드는 구현하지 않았다. pointcloud_to_laserscan 자체가 `observed_bins`를 반환한다는 뜻도 아니다. 그 정보는 별도로 설계해야 한다.

3D를 현재 점군으로 표시하는 일과 누적된 정확한 3D 지도를 만드는 일도 구분한다. 2D graph의 loop closure가 과거 자세를 바꾸면, 과거 점군을 매 프레임 당시 TF로 붙여 놓은 3D 누적 화면에는 벽이 겹쳐 남을 수 있다. **제안:** 누적 점군은 keyframe과 graph 판을 보존하고 재배치하거나 다시 생성한다. 그 연결이 없다면 UI 명칭을 `최근 3D 관측`으로 두고 저장된 정합 3D 지도라고 부르지 않는다. [slam_toolbox의 graph 기반 지도 생성](https://github.com/SteveMacenski/slam_toolbox/blob/02afdde003313a10b8d21461a92d9e5f4f0bc5f2/README.md) [S5]

기획의 46 × 27 m가 정확히 지도 외곽 크기라면 0.05 m 칸에서는 920 × 540 = **496,800칸**이다. int8 원자료는 496,800 bytes, RGBA 표시 버퍼는 1,987,200 bytes다. 이는 산술 결과이며 실제 지도 크기·압축률·프레임 속도 측정값이 아니다. 지도는 판이 바뀔 때, 자세는 별도 스트림으로 갱신하고 점군은 표시 예산을 따로 둔다.

## 격자·화면·로봇의 좌표 계약

ROS의 일반 몸체 좌표는 x 전방, y 왼쪽, z 위이며 오른손 좌표계다. `map`은 보정으로 도약할 수 있고 `odom`은 연속적이지만 누적 오차가 가능하다. `map → odom → base_link` 변환의 제공자는 실행 모드마다 한 곳으로 정한다. mapping에서 slam_toolbox와 localization의 AMCL이 동시에 같은 TF를 발행하게 두지 않는다. 건물 안의 map x축을 검증 없이 동쪽이라고 표시하지 않는다. [REP-103](https://github.com/ros-infrastructure/rep/blob/11ca24a41f31480dfb9562ba99f2a5b93d3ebda5/rep-0103.rst), [REP-105](https://github.com/ros-infrastructure/rep/blob/11ca24a41f31480dfb9562ba99f2a5b93d3ebda5/rep-0105.rst) [S3][S4]

`OccupancyGrid.data`는 x가 먼저 증가하는 row-major이며 `index = i + W*j`다. 원점은 (0,0)칸의 좌하단 모서리다. 다음 식은 planar origin을 가정한다. roll/pitch가 유의미하면 2D 지도 import를 거부하거나 별도 정의가 필요하다. [OccupancyGrid](https://github.com/ros2/common_interfaces/blob/a941f14bb318d8d904505ed935ccbb97f24a70a4/nav_msgs/msg/OccupancyGrid.msg), [MapMetaData](https://github.com/ros2/common_interfaces/blob/a941f14bb318d8d904505ed935ccbb97f24a70a4/nav_msgs/msg/MapMetaData.msg) [S1][S2]

칸 크기 r, 지도 원점 o=(ox,oy), 원점 yaw φ, 회전행렬 R이라 하면:

```text
cell center in map = o + R(φ) · [r(i+0.5), r(j+0.5)]
grid coordinates g = R(-φ) · (world_xy - o) / r
cell index = [floor(gx), floor(gy)]
valid iff 0 <= gx < W and 0 <= gy < H
Canvas continuous coordinate = [gx, H-gy]
Canvas center of cell(i,j) = [i+0.5, H-j-0.5]
Canvas pixel-row index = H-1-j
```

`H-gy`는 연속 좌표용이고 `H-1-j`는 정수 행 배열용이다. 둘을 섞으면 한 칸 또는 반 칸 어긋난다. Canvas pointer는 먼저 CSS 크기·devicePixelRatio·pan/zoom 역변환을 거쳐 위 식의 역변환을 적용한다. 픽셀 좌표에서 그냥 r을 곱해 목표점을 만들지 않는다. 로봇과 경로가 다른 프레임이면 먼저 해당 시각에 map으로 변환한다.

원점 quaternion과 로봇 quaternion은 정규화 후 yaw를 얻는다.

```text
yaw(q) = atan2(2*(qw*qz + qx*qy), 1 - 2*(qy*qy + qz*qz))
robot direction in map = [cos(θ), sin(θ)]
robot direction on unrotated grid Canvas = [cos(θ-φ), -sin(θ-φ)]
```

화살표 원본이 위를 향하는지 오른쪽을 향하는지는 별도 그림 자산 오프셋이다. 화면의 회전·줌은 전체 좌표 행렬에 적용한다. 도착 방향도 클릭 뒤 drag한 끝점을 map으로 역변환해 `atan2(dy,dx)`로 계산한다. 단일 클릭만으로 목표 실행을 만들지 않는 기획은 유지한다.

**Nav2 호환 제약:** Jazzy의 `map_io.cpp`는 YAML `origin=[x,y,yaw]`를 읽고 orientation으로 저장한다. 그러나 `StaticLayer::processMap`, `Costmap2D::worldToMap`, `AmclNode::convertMap`은 격자를 x/y축에 맞춘 형태로 취급한다. 웹에서만 회전돼 보이고 planner/AMCL은 다른 지형을 읽는 상황을 피하려면, **주행 지도와 필터 mask의 origin yaw=0을 입력 계약으로 제한**하거나 회전된 점유 셀의 면적을 보수적으로 재격자화해 모든 소비자에 동일하게 배포한다. 이미지의 bilinear 회전은 unknown/occupied 경계 의미를 바꾸므로 사용하지 않는다. 이는 해당 소스에 대한 정적 확인이며 모든 ROS 배포판에 대한 주장이나 실행 재현은 아니다. [Map IO](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_map_server/src/map_io.cpp), [StaticLayer](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_costmap_2d/plugins/static_layer.cpp), [AMCL](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_amcl/src/amcl_node.cpp), [Costmap2D](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_costmap_2d/src/costmap_2d.cpp) [S7][S8][S9][S10]

### Three.js에서 z-up 유지

Three.js의 기본 up은 (0,1,0)이다. 선택지는 데이터 전체를 한 고정 회전으로 변환하거나 ROS z-up을 그대로 쓰는 방식이다. **제안은 후자**다. 객체 생성 전에 `THREE.Object3D.DEFAULT_UP.set(0,0,1)`을 정하고 카메라·controls도 맞춘다. `up` 변경은 기존 mesh 정점이나 가져온 로봇 모델을 자동 회전시키지 않는다. ROS map 평면은 XY에 놓고 점군 좌표와 quaternion을 그대로 쓴다. 모델의 축 보정은 자산 부모 객체 한 곳에서만 적용한다. [Object3D](https://github.com/mrdoob/three.js/blob/9b4a2ac29c63ccb43fd51c5661f2f873ac2c39b8/src/core/Object3D.js) [S19]

`DataTexture`는 기본 `flipY=false`다. ROS 데이터의 j=0 행을 그대로 넣고 uv의 v=0을 grid y=0에 연결하면 수동 행 반전이 필요 없다. Canvas/PGM처럼 위에서 아래로 만든 이미지 데이터를 쓰면 반전이 필요하다. **데이터 행 반전과 texture.flipY를 동시에 적용하지 않는다.** 네 모서리의 서로 다른 표식으로 확인한다. 점유 격자는 nearest sampling으로 렌더하고, 색 보간 결과를 주행 데이터로 되쓰지 않는다. [DataTexture](https://github.com/mrdoob/three.js/blob/9b4a2ac29c63ccb43fd51c5661f2f873ac2c39b8/src/textures/DataTexture.js) [S20]

## 로봇 시야와 경로 겹치기

카메라 optical frame은 z 전방, x 오른쪽, y 아래다. 몸체 heading과 카메라 광축은 같다고 가정하지 않는다. `CameraInfo`의 K[0]=0은 보정 안 됨을 뜻할 수 있고, rectified 영상은 K가 아니라 P의 내부 파라미터를 기준으로 삼아야 한다. crop·resize·binning도 화면 영상과 일치시킨다. [CameraInfo 정의](https://github.com/ros2/common_interfaces/blob/a941f14bb318d8d904505ed935ccbb97f24a70a4/sensor_msgs/msg/CameraInfo.msg) [S16]

**제안:** 보정된 영상의 경계 픽셀에서 광선을 역투영한 뒤 `T_map_camera(t)`로 돌려 그린다. 화면과 동일한 distortion 처리를 사용한다. 단순한 대칭 pinhole에서만 수평각을 `2*atan(W/(2*fx))`로 줄일 수 있다. 실제 cx가 중앙이 아니면 좌우 각도가 다르다. 일반 경우에는 카메라 모델의 `unproject`를 사용한다.

```text
ray_map = R_map_optical(t) · unproject(pixel, active_camera_model)
frustum_point = camera_position_map + λ * ray_map
ground intersection λ = (ground_z - camera_z) / ray_map.z
accept ground hit only when ray_map.z < 0 and λ > 0
```

부채꼴의 반경은 검출거리 증거가 없으면 임의 표시 거리라고 표기한다. 바닥이 평평하지 않거나 광선이 수평 위를 향하면 바닥 교점이 없다. 벽 뒤 가림도 단순 frustum은 설명하지 못한다. 카메라 보정과 외부장착 TF가 미확인이면 `방향 표시 · 시야 미보정`으로 표시하고 안전 확인 범위로 사용하지 않는다. 위 수식은 직접 도출한 렌더링 설계이며 카메라 실측 결과가 아니다.

경로는 최소 세 종류를 구분한다.

| 표시 | 출처 | 갱신·판 처리 제안 |
|---|---|---|
| 계획 경로 | planner `nav_msgs/Path` | `goal_id + plan_revision + map_revision`, 새 계획은 이전 것 교체 |
| 실제 지나온 경로 | 시각별 추정 pose | 재위치 추정 도약 구간은 선을 끊거나 별도 표시, odom 기록도 보존 |
| 순찰/측정 기록 | 당시 pose와 측정 시각 | `mission_id + floor_id + map_revision + localization_epoch`, 다른 판 지도에는 자동 덧씌우지 않음 |

`Path`는 Header와 `PoseStamped[]`이며 남은 거리, 완료 지점, map 판을 자동으로 보장하지 않는다. 앱 계약으로 추가한다. 전역 경로와 local controller 궤적도 다른 것으로 표시한다. pose가 늦었는데 위치만 부드럽게 움직여 최신처럼 보이게 하지 않는다. `stamp`·TF 시각·통신 시각을 기록하고 UI에 나이를 노출한다. [Path](https://github.com/ros2/common_interfaces/blob/a941f14bb318d8d904505ed935ccbb97f24a70a4/nav_msgs/msg/Path.msg), [REP-105](https://github.com/ros-infrastructure/rep/blob/11ca24a41f31480dfb9562ba99f2a5b93d3ebda5/rep-0105.rst) [S17][S4]

## 잡음 정리에서 지우면 안 되는 의미

`OccupancyGrid` 메시지 자체는 값 의미가 애플리케이션에 달린다고 명시한다. Nav2 지도 계약에서는 일반적으로 free=0, occupied=100, unknown=-1을 쓴다. 내부 costmap의 free=0, lethal=254, unknown=255와 혼합하지 않는다. 한쪽 raw 배열을 다른 쪽 팔레트에 넣지 말고 payload에 encoding을 붙인다. [OccupancyGrid](https://github.com/ros2/common_interfaces/blob/a941f14bb318d8d904505ed935ccbb97f24a70a4/nav_msgs/msg/OccupancyGrid.msg), [Nav2 cost 값](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_costmap_2d/include/nav2_costmap_2d/cost_values.hpp) [S1][S13]

unknown은 관측 근거 부족이고 free는 정해진 센서 모델로 빈 공간이라는 근거가 있다는 뜻이다. 단순히 `점이 없음`은 자유 공간 관측이 아니다. 특히 **집수정 개구부·낙차는 바닥 지지가 없는 위험**이다. 수평 scan에 장애물 점이 안 찍힌다는 이유로 통과 가능한 바닥이 되지 않는다. 이 결론은 위 센서 투영·격자 의미에서 도출한 판단이며, 이 조사에서 낙차 검출률은 재지 않았다.

| 자동화 후보 | 실제로 하는 일 | 이 기획에서 허용할 첫 범위 |
|---|---|---|
| VoxelGrid | 같은 voxel의 점을 대표점으로 줄임 [S21] | 3D 표시 부하 감소. 지도 정확도 향상으로 표현하지 않음 |
| StatisticalOutlierRemoval | 이웃 거리 통계에서 벗어난 점을 제거 [S22] | 삭제 후보와 원본 비교. 가는 기둥·멀리 있는 희소 물체 제거 가능성 확인 |
| 연결 군 크기 필터 | 작은 점유 군 제거 [S11] | 지우개 후보 강조. 실제 작은 장애물일 수 있음 |
| 동적 관측 갱신 | sensor marking과 raytrace clearing [S12] | 관측이 재확인된 공간의 순간 장애물 처리 |
| 시간에 따른 제거 | 오래된 후보의 보관 또는 소멸 정책 | 가려진 고정 장애물과 움직이는 사람을 단순 시간만으로 구분하지 않음 |

Nav2 DenoiseLayer의 `removeSinglePixels`는 제거 칸을 FREE_SPACE로 쓴다. `minimal_group_size`는 칸 개수이고, 문턱·기둥·멀리 있는 작은 물체의 안전 중요도를 알지 못한다. 이를 기본 활성화하는 것은 제안하지 않는다. UI 필터는 운영 지도에 반영되지 않는 별도 display layer로 시작한다. [공식 DenoiseLayer](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_costmap_2d/plugins/denoise_layer.cpp) [S11]

ObstacleLayer의 `observation_persistence`는 관측 버퍼 보관과 관련되며 지도 칸 전체의 TTL이라고 보면 안 된다. Jazzy 소스는 marking과 clearing 관측을 따로 취합하고 광선으로 free space를 갱신한다. 지도에 박힌 일시 장애물을 제거하는 것과 현재 앞에 있는 사람을 표시하지 않는 것은 다른 문제다. **제안:** 정적 지도 후보에서는 시간·다시 관측한 근거를 사용하되 순간 장애물 layer는 별도 유지한다. [ObstacleLayer](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_costmap_2d/plugins/obstacle_layer.cpp) [S12]

편집 UI는 `표시 잡음 숨기기`, `지도 셀 수정`, `진입 금지`를 서로 다른 동작으로 둔다. 지도 수정의 최소 단위에는 이전 값·새 값·원자료 참조·이유·편집자·판을 보존한다. unknown으로 되돌리는 편집도 소비자가 unknown을 통과하지 못하도록 구성되어야 효과가 있다. StaticLayer는 `track_unknown_space=false`이면 unknown을 free로 바꿀 수 있다. UI 회색만 유지했다고 주행 위험을 막은 것이 아니다. [StaticLayer::interpretValue](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_costmap_2d/plugins/static_layer.cpp) [S8]

## 저장 지도·위치 추정·금지/감속 구역의 판 관리

PGM과 YAML은 한 묶음이다. negate·mode·free/occupied 임계값·해상도·원점을 함께 해석하고, 임의 이미지 편집기의 회색·투명·안티앨리어싱을 점유 의미와 혼동하지 않는다. Jazzy AMCL은 0을 free, 100을 occupied로 바꾸고 나머지는 내부 unknown으로 처리한다. 연속 점유 확률 이미지를 저장했다고 AMCL이 그 확률을 그대로 사용하지 않는다. [Map IO](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_map_server/src/map_io.cpp), [AMCL::convertMap](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_amcl/src/amcl_node.cpp) [S7][S9]

**제안:** 불변 `MapBundle`을 만든다. 구성은 image/YAML, occupancy hash, frame·origin·resolution, parent revision, pose graph hash, 생성 소스 판, display cloud 판, keepout/speed mask 판, 편집 내역이다. graph를 직접 수정하지 않은 PGM 파생판은 `graph-derived + raster-edits`로 표시한다. 재매핑 때 raster 편집을 조용히 보존했다고 가정하지 말고 충돌 검토 또는 재적용을 수행한다. 좌표계가 변했으면 waypoint·측정점·mask도 정합 검증 대상으로 묶는다.

```text
save_draft(base_revision, cell_edits, masks)
validate_bundle_semantics_and_replay(bundle)
activate_when_mission_idle(bundle.revision)
require_applied_revision(map_server, localizer, global_costmap, local_costmap, masks)
require_localization_valid_for(bundle.revision)
invalidate_old_plan_and_request_new_plan()
publish_active_revision_to_web()
```

이것은 앱에서 만들 배포 절차다. ROS의 기본 토픽이 이 원자적 전환이나 `applied_revision` 응답을 제공한다는 뜻은 아니다. AMCL `first_map_only`와 각 노드의 구독·라이프사이클을 구성하고, adapter가 실제로 받아 적용한 자료와 상태를 검증해야 한다. 메시지 수신 ACK만으로 플래너 반영까지 확인했다고 처리하지 않는다. 위치 맞추기의 `initialpose`는 추정 초기값이지 정합 성공 증거가 아니다. 입자 모양·공분산·scan 정합·동일 시각 TF의 재생 검증이 필요하다. [AMCL 소스](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_amcl/src/amcl_node.cpp) [S9]

진입 금지는 점유 지도를 하얗게 지우는 기능과 분리한 keepout mask로 관리한다. Jazzy KeepoutFilter는 mask의 unknown을 건너뛰므로 mask의 회색 칸이 자동 금지를 뜻하지 않는다. 필터 범위·좌표·전역/로컬 적용을 검증하고 polygon이 몸체 중심만 막는지 실제 footprint·여유 거리까지 막는지 확인한다. 직접 조종 경로가 Nav2를 우회하면 해당 필터만으로 금지가 강제되지 않는다. 이 마지막 사항은 제어 경로에 대한 설계 판단이다. [KeepoutFilter](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_costmap_2d/plugins/costmap_filters/keepout_filter.cpp) [S14]

감속 mask는 절대속도 모드에서 `limit = base + multiplier * value`를 쓸 수 있다. 예를 들어 base=0, multiplier=0.01이면 값 20·30을 0.2·0.3 m/s로 표현할 수 있으나 이는 **설정 예시**다. 값 0은 감속 없는 영역이고 unknown은 유효한 감속 값이 아니다. SpeedFilter는 제한 메시지를 발행하며 실제 준수는 controller·명령 중재·로봇 하위 제어의 연결 문제다. 화면에 0.2가 보이는 것만으로 실기 속도 제한을 확인했다고 기록하지 않는다. [SpeedFilter](https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_costmap_2d/plugins/costmap_filters/speed_filter.cpp) [S15]

## 이번에 확인한 것과 남은 검증

답을 아는 합성 입력으로 Python 계산을 실행했다. 외부 로봇과 ROS 노드는 실행하지 않았다.

| 입력 | 예상·실제 결과 | 상태 |
|---|---|---|
| W=3,H=2,r=0.05,origin=(10,20),yaw=90° | 6칸 중심의 world→grid 왕복이 원 칸과 일치 | 확인됨 |
| 위 지도의 cell(2,1) | world=(9.925,20.125) | 확인됨 |
| ROS rows `[0,100,-1,50,0,100]` | Canvas 위→아래 `[50,0,100,0,100,-1]` | 확인됨 |
| 로봇 yaw=180°,지도 yaw=90° | Canvas 방향=(0,-1) | 확인됨 |
| 중앙 pinhole W=640,fx=320 | 대칭 수평 FOV=90° | 수식만 확인됨 |
| 46 × 27 m,0.05 m | 920 × 540=496,800칸 | 산술 확인됨 |
| 브라우저 실제 렌더·mouse picking·카메라 실측 | 실행 안 함 | 미확인 |
| ROS/Nav2 실행·PGM round-trip·실제 robot map 일치 | 실행 안 함 | 미확인 |

구현 검증에서 필요한 고정 시험은 다음과 같다. 아래는 **시험 제안이며 아직 통과한 결과가 아니다.**

- 비대칭 모서리 표식 지도, 음수 원점, yaw=0/90°, CSS 확대·DPR=2에서 표시·클릭·내보내기 위치 일치.
- 지도 저장 후 Nav2 loader로 다시 읽어 free/occupied/unknown 칸과 원점·해상도 재비교. UI 미리보기만으로 판정하지 않음.
- 가느다란 기둥·고립 물체·개구부·문턱·가려진 벽·움직이는 사람·빈 angle bin을 포함한 기록 재생. 삭제 후보 수보다 실제 장애물 보존과 근거 없는 free 생성 여부를 평가.
- 지도 판 교체 중 AMCL 또는 filter mask 하나만 늦게 갱신되는 경우 임무 재개가 막히는지 확인.
- loop closure와 재위치 추정 도약 뒤 2D·3D·실제 경로·가스 측정점의 판 및 시각 일치.
- 보정 없는 카메라·crop된 영상·늦은 TF에서 UI가 시야를 확정값처럼 그리지 않는지 확인.

## 출처 범위와 재현 정보

조회일은 2026-10-13이다. ROS/Nav2 동작은 주로 Jazzy branch를 조회했고, 공개 GitHub API에서 아래 commit을 직접 확인했다. 본문에 링크한 고정 commit 파일 20개를 branch URL과 각각 다시 받아 byte 비교한 결과 20개 모두 일치했다. L1 펌웨어·Unitree 공식 앱 소스와 배포 Nav2 버전은 미확인이다. 계산과 파일 확인 기록은 [VERIFICATION.md](VERIFICATION.md)에 있다.

| 표기 | 공식 원자료 | 조회 기준 |
|---|---|---|
| S1·S2·S16·S17·S18 | ros2/common_interfaces의 OccupancyGrid·MapMetaData·CameraInfo·Path·PointCloud2 | jazzy `a941f14bb318d8d904505ed935ccbb97f24a70a4` |
| S3·S4 | ros-infrastructure/rep의 REP-103·105 | master `11ca24a41f31480dfb9562ba99f2a5b93d3ebda5` |
| S5 | SteveMacenski/slam_toolbox README | jazzy `02afdde003313a10b8d21461a92d9e5f4f0bc5f2` |
| S6 | ros-perception/pointcloud_to_laserscan README·node 소스 | rolling `595bc926f2df2e1a199e776c42d43ade868e3777` |
| S7~S15 | ros-navigation/navigation2의 위 각 파일 | jazzy `645abd95f2be02a13ca539b29c2ddc065db34f89` |
| S19·S20 | mrdoob/three.js Object3D·DataTexture | master `9b4a2ac29c63ccb43fd51c5661f2f873ac2c39b8` |
| S21 | [PCL VoxelGrid tutorial](https://pointclouds.org/documentation/tutorials/voxel_grid.html) | 공식 문서 조회 |
| S22 | [PCL StatisticalOutlierRemoval tutorial](https://pointclouds.org/documentation/tutorials/statistical_outlier.html) | 공식 문서 조회 |

docs.ros.org와 ros.org REP 페이지는 접근 제한 응답을 받아 공식 GitHub 원문으로 대조했다. 일부 구 Nav2 문서 URL은 열리지 않아 Jazzy 공식 소스로 확인했다. 인용된 소스의 기능을 Go2 앱 내부 구현으로 일반화하지 않았다.
