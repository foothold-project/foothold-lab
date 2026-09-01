# ROS 2 TF 좌표계와 RViz2 시각화 정리

> 분류: 가이드
> 작성: 오현민 · 2026-08-27 12:20
> 근거: 조선대 ROS 2 수업 3편 「TF 좌표계 · RViz2 시각화」(자료 원본은 저장소에 넣지 않음) + ROS 2 Jazzy tf2 공식 문서 대조
> 요지: TF 좌표계 발행부터 lookup_transform 조회, Marker·Path 시각화까지를 코드 순서대로 재구성하고, 이 내용이 CV 담당의 「탐지한 물체를 지도 좌표로 옮기는」 작업에 그대로 대응된다는 점을 정리했다. 자료에 실린 15주 커리큘럼 표도 함께 옮겼다.
> 상태: 확정
> 판: v1.0
> 이슈: #63
>
> 원본: `inbox/oh/20260826-ros2-03-tf좌표계-rviz2.md` (PR #63, 2026-08-27 머지). 팀장이 `docs/` 로 승격하며 머리글 형식만 정리했고 본문은 손대지 않았다.

## 0. 이 문서를 읽는 법

1편은 환경 구축, 2편은 rclpy 로 노드 쓰기였습니다. **3편은 「로봇이 자기 몸과 주변의 위치 관계를 어떻게 아는가」입니다.** 자료 표지에도 「ROS2 심화과정 · TF 시리즈」로 적혀 있습니다.

**제 판단으로는 CV 담당인 저에게 지금까지 셋 중 가장 직접적으로 필요한 내용입니다.** 카메라가 「화면 좌표에서 사람을 찾았다」로 끝나면 로봇은 아무것도 못 합니다. 그 픽셀을 로봇 기준 좌표로, 다시 지도 기준 좌표로 옮겨야 Nav2 가 그쪽으로 갈 수 있는데, 그 변환을 담당하는 것이 정확히 TF 입니다.

**증거 표기 기준.** 아래 코드는 수업에서 다룬 핵심 조각을 순서대로 재구성한 것이고, **제 환경에서 실행하지 않았으므로 동작은 전부 `미확인`** 입니다. 자료에 전체 소스가 실려 있지는 않아서, 노드 골격(`__init__`, 타이머 생성 등)은 2편의 Node 클래스 패턴을 따라 채워야 합니다.

**환경 전제.** Ubuntu 24.04 + ROS 2 Jazzy. 자료 본문에도 「배포판 이름만 맞추면 명령은 Jazzy·Humble 동일」이라고 적혀 있습니다.

## 1. 용어부터

| 용어 | 뜻 |
|---|---|
| 좌표계(Frame) | 위치와 방향을 기술하는 기준축 하나. `world`, `base_link`, `camera_link` 같은 이름을 가짐 |
| TF (Transform) | 두 좌표계 사이의 이동(translation) + 회전(rotation) 관계 |
| tf2 | 그 변환들을 **트리로 관리하고 조회**하는 ROS 2 라이브러리 |
| TF 트리 | 부모-자식 관계로 이어진 좌표계 구조. 각 프레임은 부모 대비 상대 좌표만 알면 됨 |
| `/tf`, `/tf_static` | 변환이 실제로 흐르는 토픽. 움직이는 것과 고정된 것이 나뉨 |

**핵심 성질 하나.** 각 노드는 자기 부모에 대한 상대 관계만 발행하면 되고, 「카메라에서 본 점이 지도 기준으로 어디인가」 같은 여러 단계를 건너뛰는 질문은 tf2 가 트리를 따라 알아서 합성해 답합니다. 이 성질 때문에 로봇 소프트웨어가 좌표 변환 코드를 직접 쓰지 않아도 됩니다. `확인됨` ([tf2 개념 문서](https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Tf2.html))

## 2. 모듈 1: 좌표계를 발행한다 (Broadcaster)

**목표.** `world` 를 고정해두고, 반지름 2m 원을 도는 `moving_frame` 을 발행합니다.

| 요소 | 뜻 |
|---|---|
| `TransformStamped` | 변환 하나를 담는 메시지. **시각 + 부모 프레임 + 자식 프레임 + 이동 + 회전** |
| `frame_id` | 부모 프레임 이름 |
| `child_frame_id` | 자식 프레임 이름 |
| `TransformBroadcaster` | `/tf` 토픽으로 변환을 내보내는 객체 |
| Stamped | 「시각이 찍힌」이라는 뜻의 접미사. TF 는 항상 **언제의 관계인지**가 함께 있어야 함 |

```python
def timer_callback(self):
    self.t += 0.05
    x = 2.0 * math.cos(self.t)   # 반지름 2m 원 궤도
    y = 2.0 * math.sin(self.t)

    tf = TransformStamped()
    tf.header.frame_id = 'world'
    tf.child_frame_id = 'moving_frame'
    tf.transform.translation.x = x
    tf.transform.translation.y = y
    self.br.sendTransform(tf)
```

| 요소 | 뜻 |
|---|---|
| `self.t += 0.05` | 각도 누적. 타이머 주기(자료 기준 10Hz)와 곱해져 회전 속도가 정해짐 |
| `math.cos` / `math.sin` | 각도를 원 위 좌표로. `cos` 이 x, `sin` 이 y |
| `tf.header.frame_id` | **부모**가 들어갑니다. 이름이 `frame_id` 라 헷갈리기 쉬운 지점 |
| `sendTransform(tf)` | 발행. 타이머 콜백 안에서 주기적으로 불러야 살아 있는 변환이 됨 |

발행 주기는 10Hz, 궤도 반지름은 2m, 관계는 `world` → `moving_frame` 입니다.

RViz2 에서 확인할 때 **Fixed Frame 을 `world` 로 바꾸고 TF display 를 추가**해야 보입니다. 이걸 안 해서 「아무것도 안 나온다」가 되는 경우가 가장 흔합니다. 좌표축 색은 RGB 가 XYZ 에 대응합니다(빨강 x, 초록 y, 파랑 z).

## 3. 왜 Quaternion 인가 (위치만으로는 부족합니다)

위치만 발행하면 「그 점이 어디를 보고 있는지」가 없습니다. 자세(orientation)를 표현하는 방법이 둘입니다.

| 방식 | 표현 | 문제 |
|---|---|---|
| 오일러각 (Euler, RPY) | roll·pitch·yaw 세 각도 | **회전 순서에 따라 결과가 달라짐.** 특정 각도에서 축 둘이 겹쳐 자유도를 잃음 (Gimbal Lock) |
| 쿼터니언 (Quaternion) | x, y, z, w 네 값 | 임의의 회전축 기준 1회 회전으로 표현. Gimbal Lock 없음. **ROS 2 표준** |

Gimbal Lock 은 짐벌(회전 고리) 두 축이 같은 평면에 겹쳐 한 방향의 회전을 잃어버리는 현상입니다. 사람이 각도를 읽기엔 오일러각이 편하지만, **저장·전송·보간은 쿼터니언으로 합니다.** ROS 2 메시지가 전부 쿼터니언인 이유입니다.

`moving_frame` 의 x축(빨강)이 항상 `world` 원점을 향하게 만드는 코드입니다.

```python
yaw = math.atan2(-y, -x)
q = quaternion_from_euler(0.0, 0.0, yaw)
tf.transform.rotation.x = q[0]
tf.transform.rotation.y = q[1]
tf.transform.rotation.z = q[2]
tf.transform.rotation.w = q[3]
```

| 요소 | 뜻 |
|---|---|
| `atan2(y, x)` | 두 인자를 받는 아크탄젠트. `atan(y/x)` 와 달리 **사분면을 구분**하고 x=0 에서도 안전 |
| `atan2(-y, -x)` | 현재 위치의 **반대 방향**, 즉 원점을 향하는 각도 |
| `quaternion_from_euler(roll, pitch, yaw)` | 오일러각을 쿼터니언 4원소로 변환 |
| `q[0..3]` | 순서가 **x, y, z, w** 입니다. w 를 앞에 두는 라이브러리도 있어서 자주 틀리는 지점 |

> **여기서 제가 막힐 것으로 보는 지점.** `quaternion_from_euler` 는 rclpy 기본 제공이 아니라 `tf_transformations` 쪽 함수입니다. Jazzy 에서 이 파이썬 모듈이 기본 설치인지, `ros-jazzy-tf-transformations` 나 `transforms3d` 를 따로 깔아야 하는지는 아직 확인하지 못했습니다. `미확인` (수업 시간에 확인하거나 직접 설치해보고 이 문서를 갱신하겠습니다)

**막히면 볼 것.** 자세가 안 변하면 `rotation` 을 실제로 채워 발행하는지 보십시오. 위치만 채우고 회전을 비워두면 기본값이 그대로 나갑니다.

## 4. 모듈 2: Child Frame 을 붙여 트리로 만든다

**목표.** `moving_frame` 위에 `child_frame` 을 하나 더 얹습니다. 만들려는 트리는 `world` → `moving_frame` → `child_frame` 입니다.

자료의 비유가 좋아서 그대로 씁니다. **태양 · 지구 · 달** 관계입니다. 지구가 태양을 돌고, 달은 지구에 끌려다니면서 지구를 더 빠르게 돕니다.

```python
def timer_callback(self):
    self.t += 0.05
    angle = 2.0 * self.t          # moving_frame 의 2배 각속도
    x = 1.0 * math.cos(angle)     # 반지름 1m
    y = 1.0 * math.sin(angle)

    t = TransformStamped()
    t.header.frame_id = 'moving_frame'   # world 가 아닙니다
    t.child_frame_id = 'child_frame'
    t.transform.translation.x = x
    t.transform.translation.y = y
    self.br.sendTransform(t)
```

| 프레임 | 부모 | 반지름 | 각속도 |
|---|---|---|---|
| `moving_frame` | `world` | 2m | 1배 |
| `child_frame` | `moving_frame` | 1m | 2배 |

**이 모듈 전체의 요점 한 줄.** `frame_id='moving_frame'` 이므로 여기서 계산한 x, y 는 **`moving_frame` 기준 상대 좌표**입니다. `world` 기준 절대 좌표를 넣으면 완전히 엉뚱한 곳에 붙습니다. 「부모를 `world` 로 착각」이 이 단계에서 가장 흔한 실수입니다.

그리고 **부모 프레임을 발행하는 노드가 먼저 돌고 있어야 자식이 붙습니다.** `child_frame` 이 안 보이면 `moving_frame` 노드가 살아 있는지부터 봅니다.

### 4-1. 프레임이 늘어나면 노드를 늘리지 말고 헬퍼로 뺀다

프레임 하나에 노드 하나씩 만들면 터미널이 계속 늘어나고 발행 로직이 파일마다 복제됩니다. 발행 부분을 함수로 빼서 한 노드가 전부 발행하게 합니다.

```python
def send_tf(self, parent, child, x, y, z, yaw):
    t = TransformStamped()
    t.header.frame_id = parent
    t.child_frame_id = child
    # translation·rotation 채우기
    self.br.sendTransform(t)

def timer_callback(self):
    self.t += 0.05
    self.send_tf('world', 'moving_frame', ...)
    self.send_tf('moving_frame', 'child_frame', ...)
```

| 별도 노드 방식 | 통합 노드 방식 |
|---|---|
| 프레임당 노드 1개 | 노드 1개가 전부 관리 |
| 터미널 여러 개에서 실행 | 한 번에 실행 |
| 발행 로직이 파일마다 반복 | `send_tf` 호출 한 줄만 추가 |
| 타이머가 각각이라 미세하게 어긋남 | **같은 타이머라 동기화가 보장됨** |

마지막 줄이 실질적인 이유입니다. 프레임끼리 시각이 어긋나면 `lookup_transform` 이 예외를 던지거나 어긋난 값을 줍니다. 하나의 `TransformBroadcaster` 로 여러 TF 를 발행할 수 있으므로 굳이 나눌 이유가 없습니다.

## 5. 모듈 3: 발행된 TF 를 조회한다 (Listener)

지금까지는 **발행**만 했습니다. 발행된 TF 는 누군가 구독해서 써야 의미가 있습니다. tf2 의 두 축이 Broadcaster 와 Listener 입니다.

| | TF Broadcaster | TF Listener |
|---|---|---|
| 역할 | 변환 정보를 발행 | 변환 정보를 수신·조회 |
| 핵심 클래스 | `TransformBroadcaster` | `TransformListener` + `Buffer` |
| 핵심 함수 | `sendTransform()` | `lookup_transform()` |
| 예 | 로봇 관절 위치 브로드캐스트 | 두 프레임 사이 거리·각도 계산 |

조회에는 **항상 이 세 가지가 함께** 필요합니다.

| 요소 | 하는 일 |
|---|---|
| `tf2_ros.Buffer()` | 수신된 TF 를 일정 시간(기본 10초) 저장하는 캐시 |
| `TransformListener(buffer, node)` | `/tf`, `/tf_static` 을 구독해 Buffer 를 자동으로 채움 |
| `buffer.lookup_transform(target, source, time)` | Buffer 에서 두 프레임 사이 변환을 꺼냄 |

**Listener 를 만들어두고 아무 데도 안 쓰는 것처럼 보여도 지워선 안 됩니다.** Buffer 를 채우는 것이 그 역할입니다.

### 5-1. lookup_transform

```python
transform = self.tf_buffer.lookup_transform('world', 'child_frame', rclpy.time.Time())
```

| 인자 | 뜻 |
|---|---|
| `'world'` | target_frame. **기준이 되는 프레임** |
| `'child_frame'` | source_frame. **알고 싶은 프레임** |
| `rclpy.time.Time()` | 시각. 기본 생성자는 0 이고, 0 은 「가장 최근 데이터」를 뜻함 |
| 반환값 | `TransformStamped`. translation + rotation |

**인자 순서 `(target, source, time)` 를 외워두는 편이 낫습니다.** 뒤바꿔도 예외 없이 그냥 반대 방향 변환이 나오기 때문에, 값이 이상한데 에러는 안 나는 상태가 됩니다. 디버깅이 가장 오래 걸리는 종류의 실수입니다.

**`try-except` 가 사실상 필수입니다.** 프레임이 아직 발행되기 전이거나 요청한 시각이 Buffer 범위 밖이면 예외가 납니다. 노드가 막 켜진 직후에는 정상적으로 몇 번 실패합니다.

### 5-2. 거리 계산해서 새 토픽으로 발행

```python
x = transform.transform.translation.x
y = transform.transform.translation.y
z = transform.transform.translation.z
distance = math.sqrt(x**2 + y**2 + z**2)

msg = Float32()
msg.data = distance
self.dist_pub.publish(msg)
```

| 요소 | 뜻 |
|---|---|
| `transform.transform.translation` | `TransformStamped` 안의 이동 성분. `transform` 이 두 번 나오는 것은 메시지 구조 때문 |
| `math.sqrt(x**2+y**2+z**2)` | 3차원 유클리드 거리 |
| `Float32` | `std_msgs` 의 단일 실수 메시지 타입 |

`ros2 topic list` 로 새 토픽이 생겼는지, `ros2 topic echo` 로 값이 도는지 확인합니다. **TF 로 얻은 정보를 다시 토픽으로 내보내는 이 패턴이 실무에서 가장 많이 쓰는 형태입니다.** `추측`

**막히면 볼 것.** 거리가 계속 0 이면 target/source 프레임 이름 오타입니다(같은 프레임을 두 번 넣으면 0). 값이 안 변하면 `child_frame` 을 움직이는 노드가 실제로 돌고 있는지 봅니다.

## 6. 모듈 4: RViz2 에 그린다 (Marker · Path)

지난 모듈에서 거리를 **숫자**로 얻었으니, 이제 경로를 **그림**으로 그립니다.

| 메시지 | 패키지 | 하는 일 |
|---|---|---|
| `Marker` | `visualization_msgs.msg` | 점·선·화살표·텍스트 등 임의의 도형 표시 |
| `PoseStamped` | `geometry_msgs.msg` | 위치 + 방향 + 시각 |
| `Path` | `nav_msgs.msg` | `PoseStamped` 의 리스트로 구성된 경로 |

### 6-1. Marker 로 지나간 경로 그리기

```python
marker.type = Marker.LINE_STRIP
marker.scale.x = 0.02          # 선 두께
marker.color.r = 1.0           # 빨간색
marker.color.g, marker.color.b = 0.2, 0.2
marker.lifetime.sec = 0        # 0 = 영구 표시

marker.points = []
for pos in self.positions:
    p = Point()
    p.x, p.y, p.z = pos
    marker.points.append(p)

self.marker_pub.publish(marker)
```

| 요소 | 뜻 |
|---|---|
| `LINE_STRIP` | `points` 를 순서대로 이어 하나의 선으로 그림 |
| `scale.x` | LINE_STRIP 에서는 **선 두께**로 해석. 타입마다 scale 의미가 다름 |
| `color.r/g/b` | 0.0~1.0 범위. `color.a`(투명도)를 0 으로 두면 안 보이므로 주의 |
| `lifetime.sec = 0` | 0 은 「지우지 않음」. 값을 주면 그 초 뒤 자동 소멸 |

**Marker 가 안 보이면** `header.frame_id`, `ns`(namespace), `id` 를 확인하고 RViz2 에 Marker display 를 추가했는지 봅니다.

### 6-2. 슬라이딩 윈도우로 메모리 제한

경로 좌표를 계속 쌓으면 메모리가 무한정 증가합니다. 최근 N 개만 유지합니다.

```python
self.max_points = 50
if len(self.positions) > self.max_points:
    self.positions.pop(0)   # 가장 오래된 좌표 제거
```

| 요소 | 뜻 |
|---|---|
| `pop(0)` | 리스트 맨 앞 원소 제거. 뒤에서 append 하고 앞에서 pop 하면 고정 길이 창이 됨 |

**작은 예제라 사소해 보이지만 장시간 구동하는 로봇에서는 필수 패턴입니다.** 한 시간 돌리면 그냥 죽습니다.

### 6-3. Path + 실시간 거리 텍스트

```python
self.path_msg.poses.append(pose)
self.path_pub.publish(self.path_msg)
if len(self.path_msg.poses) > self.max_poses:
    self.path_msg.poses.pop(0)

marker.type = Marker.TEXT_VIEW_FACING
marker.text = f'Distance: {distance:.2f} m'
marker.scale.z = 0.3           # TEXT 에서는 글자 크기
```

| 요소 | 뜻 |
|---|---|
| `TEXT_VIEW_FACING` | 카메라를 항상 마주보는 텍스트 마커. 어느 각도에서 봐도 읽힘 |
| `marker.scale.z` | **TEXT 타입에서는 글자 크기입니다.** LINE_STRIP 의 `scale.x` 와 의미가 완전히 다름 |
| `f'{distance:.2f}'` | 파이썬 f-string. 소수점 둘째 자리까지 |

| Marker 방식 | Path 방식 |
|---|---|
| 자유도가 가장 높음 (선·점·도형·텍스트) | 네비게이션 전용 표준 경로 메시지 |
| `points` 에 append | `poses` 에 append |
| 커스텀 시각화용 | Nav2 등 다른 노드가 그대로 받아 씀 |

**둘 다 쓰는 이유가 있습니다.** Path 는 표준이라 다른 노드가 소비할 수 있고, Marker 는 표준에 없는 것(거리 텍스트 같은 것)을 그릴 수 있습니다.

## 7. 트러블슈팅 종합

| 증상 | 원인 후보 |
|---|---|
| RViz2 에 TF 가 안 보임 | Fixed Frame 이 `world` 가 아님 / TF display 미추가 |
| 자세가 안 변함 | `rotation`(쿼터니언)을 채우지 않고 발행 |
| 회전이 이상함 | 오일러 순서 문제 또는 Gimbal Lock. 쿼터니언으로 처리 |
| `child_frame` 이 안 보임 | 부모(`moving_frame`) 노드가 안 돌고 있음 |
| 프레임이 엉뚱한 데 붙음 | `frame_id` 에 부모가 아니라 `world` 를 넣음 |
| `lookup_transform` 예외 | 프레임 미존재 또는 시간 범위 밖. `try-except` 필수 |
| 거리가 0 만 나옴 | target/source 프레임 이름 오타 |
| Marker 가 안 보임 | `frame_id`·`ns`·`id` 확인, RViz2 에 display 추가 |
| 경로가 끊김 | `lifetime.sec` 이 0 인지, `points`/`poses` 가 계속 append 되는지 |
| 텍스트가 안 보임 | `scale.z` 가 0. TEXT 에서는 이게 글자 크기 |

## 8. FOOTHOLD 로의 연결 (제가 이 문서를 팀에 올리는 이유)

**CV 담당(작업 영역 `B/인지`, `nav/perception/`) 작업의 절반이 사실상 TF 문제입니다.** 대응 관계를 정리하면 이렇습니다.

| 수업 예제 | FOOTHOLD 에서 |
|---|---|
| `world` → `moving_frame` | `map` → `base_link` (지도 기준 로봇 위치. SLAM/Nav2 가 발행) |
| `moving_frame` → `child_frame` | `base_link` → `camera_link` (로봇 몸체 기준 카메라 장착 위치) |
| `lookup_transform('world','child_frame')` | 카메라에서 본 탐지 결과를 `map` 좌표로 환산 |
| 거리 계산 후 새 토픽 발행 | 「탐지한 대상까지 몇 m」를 토픽으로 내보내 Nav2 에 넘김 |
| Marker `TEXT_VIEW_FACING` | 데모에서 탐지 결과·거리를 RViz2 화면에 띄우기 |
| `Path` | Nav2 가 계획한 경로 표시 |

정리하면, **YOLO 가 「화면 왼쪽 위에 사람」이라고 답하는 것을 「지도상 (3.2, 1.7) 에 사람」으로 바꾸는 다리가 TF 입니다.** 이 변환이 없으면 탐지 결과를 자율주행에 연결할 방법이 없습니다.

실제로 붙일 때 추가로 확인해야 할 것들입니다.

- 카메라 내부 파라미터(초점거리·왜곡)를 알아야 픽셀을 각도로 바꿀 수 있습니다. 캘리브레이션이 선행됩니다. `미확인`
- 깊이 정보가 없으면 픽셀 하나로는 방향만 알 뿐 거리를 모릅니다. Go2 의 카메라가 깊이를 주는지 확인이 필요합니다. `미확인`
- `base_link` → `camera_link` 는 고정값이므로 `/tf_static` 으로 한 번만 발행하면 됩니다. 매 프레임 발행할 필요가 없습니다. `추측`

## 9. 자료에 실려 있던 15주 커리큘럼

<!--web:제외-->

3편 목차 슬라이드에 전체 수업 로드맵이 함께 실려 있었습니다. **PDF 텍스트 추출 결과에서 주차와 제목이 뒤섞여 나와 제가 순서를 복원한 것이라 배치가 틀렸을 수 있습니다.** `추측` (원본 슬라이드로 대조 확인 필요)

| 주차 | 주제 |
|---|---|
| 2 | 환경 설정 |
| 3 | ROS 2 첫걸음 |
| 4 | 서비스와 패키지 |
| 5 | 파라미터와 도구 |
| 6 | Go2 기본 조작 |
| 7 | PC 개발환경 세팅 |
| 8 | 연결과 시각화 |
| 9 | 센서와 알고리즘 |
| 10 | 맵 빌딩 |
| 11 | 자율주행 실습 |
| 12 | 파라미터 튜닝 |
| 13 | 영상 송출 |
| 14 | 심화 및 프로젝트 |
| 15 | 최종 프로젝트 |

같은 슬라이드에 `8/31 ~ 9/4` 라는 날짜가 함께 있었는데, 이번 회차의 실습 기간으로 보입니다. `추측`

**팀에 공유할 가치가 있다고 보는 부분이 이 표입니다.** 이 로드맵대로라면 수업만 따라가도 6주차에 Go2 실기를 만지고, 10주차에 맵 빌딩(SLAM), 11주차에 자율주행, 13주차에 영상 송출을 다룹니다. **제 개인 작업 순서 S3(시뮬 항법) · S4(시뮬 통합)와 수업 진도가 겹치므로, 수업 실습을 프로젝트 산출물로 바로 전용할 수 있는 구간이 있습니다.** 다만 위 표의 주차 배치가 제 복원이라, 팀 일정에 반영하기 전에 원본 슬라이드로 확인이 필요합니다. `미확인`

> **팀 관문과의 관계** (2026-08-27 덧붙임). 2026-08-27 에 재정의된 관문 `NAV · 실기 항법 11/7` 의 뜻이 「조선대 Go2 에서 SLAM 지도 + Nav2 경로가 한 번 돈다」입니다 `확인됨` (`docs/COLLAB.md` §2.5, `docs/decisions/20260826-27-design-session.md`). 위 표의 10주차(맵 빌딩) · 11주차(자율주행)가 이 관문과 직접 겹칠 가능성이 있으나, **주차와 실제 날짜의 대응을 제가 모르므로** `미확인` 입니다. 또한 SLAM · Nav2 는 작업 영역 `B/항법` 이고 **주담당은 오흥재님, 저는 부담당**입니다 `확인됨` (`docs/COLLAB.md` §2). 위 S3 · S4 는 제 개인 학습 순서이지 팀 산출물의 소유 선언이 아닙니다.
<!--/web:제외-->

## 10. 출처

- tf2 개념 문서(공식): https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Tf2.html
- tf2 튜토리얼 전체(공식): https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Tf2/Tf2-Main.html
- tf2 브로드캐스터 작성 (Python, 공식): https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Broadcaster-Py.html
- tf2 리스너 작성 (Python, 공식): https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Listener-Py.html
- RViz2 Marker 타입 설명(공식): https://docs.ros.org/en/jazzy/Tutorials/Intermediate/RViz/RViz-Main.html
- `visualization_msgs/Marker` 메시지 정의: https://docs.ros.org/en/jazzy/p/visualization_msgs/msg/Marker.html
- REP 105 (로봇 좌표계 표준 이름 규약: `map`, `odom`, `base_link`): https://www.ros.org/reps/rep-0105.html
- 조선대 ROS 2 수업 3편 「TF 좌표계 · RViz2 시각화」: 조선대 저작물이므로 저장소에 넣지 않았습니다. 원본은 팀 자료실에 있습니다.

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-08-27 | 처음 씀 | 이전 이력은 git 에 |
