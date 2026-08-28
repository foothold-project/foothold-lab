# ROS 2 Python 프로그래밍 정리 (rclpy · colcon · 커스텀 인터페이스)

> 분류: 가이드
> 작성: 오현민 · 2026-08-27 12:20
> 근거: 조선대 ROS 2 수업 2편 「ROS2 Python 프로그래밍」(자료 원본은 저장소에 넣지 않음) + rclpy·ROS 2 Jazzy 공식 문서 대조
> 요지: rclpy 로 토픽·서비스·액션·파라미터 노드를 직접 작성하고 colcon 패키지로 옮기는 전 과정을, 노트북 실험에서 패키지로 넘어가는 이유와 함께 명령·코드 순서 그대로 재구성했다.
> 상태: 확정
> 판: v1.0
>
> 원본: `inbox/oh/20260826-ros2-02-python프로그래밍.md` (PR #63, 2026-08-27 머지). 팀장이 `docs/` 로 승격하며 머리글 형식만 정리했고 본문은 손대지 않았다.

## 0. 이 문서를 읽는 법

1편(개발환경 구축)에서는 `ros2` 명령으로 **남이 만든 노드를 부렸습니다.** 2편은 그 노드를 **직접 쓰는 단계**입니다.

전체 흐름은 이렇게 두 번 꺾입니다.

| 단계 | 무엇을 | 왜 그 순서인가 |
|---|---|---|
| 1~2 모듈 | Jupyter 노트북에서 rclpy 로 구독·발행·서비스 호출 | 빌드 없이 셀 단위로 굴려야 통신 개념이 손에 붙음 |
| 3~4 모듈 | 같은 코드를 colcon 패키지로 옮기고 커스텀 타입 정의 | 노트북 코드는 배포·재사용이 안 됨 |
| 5~7 모듈 | 액션 서버 · 파라미터 · 디버그 도구 | 「돌아가는 노드」를 「운용 가능한 노드」로 만드는 층 |

**증거 표기 기준.** 명령과 코드는 수업에서 다룬 순서 그대로이나 **제 환경에서 재실행하지 않았으므로 동작은 전부 `미확인`** 입니다. `확인됨` 은 제가 직접 원문을 열어 대조한 공식 문서 내용에만 답니다.

**환경 전제.** Ubuntu 24.04 + ROS 2 Jazzy. 워크스페이스는 수업 기준 `~/dev_ws/ros`, 가상환경은 `~/venv/robot_venv` 입니다.

## 1. 준비: Jupyter 커널에 가상환경 연결

| 용어 | 뜻 |
|---|---|
| rclpy | ROS 2 Client Library for Python. 파이썬에서 노드를 만들고 통신하게 해주는 라이브러리 |
| 커널(kernel) | Jupyter 가 실제로 코드를 실행시키는 파이썬 프로세스 |

```bash
source ~/venv/robot_venv/bin/activate
pip3 install jupyter ipykernel
python -m ipykernel install --user --name ros --display-name ros
```

| 토큰 | 뜻 |
|---|---|
| `ipykernel` | 특정 파이썬 환경을 Jupyter 커널로 등록해주는 패키지 |
| `--user` | 시스템 전체가 아니라 내 계정에만 등록 |
| `--name ros` | 내부 식별자 |
| `--display-name ros` | 노트북 커널 선택 목록에 보이는 이름 |

> **여기서 제가 걸린다고 보는 지점.** `rclpy` 는 venv 안에 pip 로 설치되는 패키지가 아니라 `/opt/ros/jazzy` 아래에 설치되어 있고, `source /opt/ros/jazzy/setup.bash` 가 `PYTHONPATH` 에 그 경로를 넣어주는 방식으로 잡힙니다. 즉 **venv 를 켰더라도 그 터미널에서 ROS 2 환경을 source 해야 `import rclpy` 가 됩니다.** 그리고 venv 의 파이썬 버전이 ROS 2 가 빌드된 버전(24.04 기준 3.12)과 어긋나면 경로가 맞아도 못 찾습니다. `추측` (근거: setup.bash 가 PYTHONPATH 를 설정하는 구조. 직접 재현해보지는 않았습니다)
>
> `import rclpy` 가 실패하면 커널 문제인지 source 문제인지부터 가르는 것이 빠릅니다.

## 2. 토픽 구독 (Subscriber)

**흐름상 위치.** turtlesim 이 발행하는 `/turtle1/pose` 를 파이썬으로 받아보는 것이 첫 실습입니다. 1편에서 `ros2 topic echo` 로 했던 일을 코드로 하는 것입니다.

| 용어 | 뜻 |
|---|---|
| 콜백(callback) | 메시지가 도착했을 때 ROS 2 가 대신 불러주는 함수. 내가 부르는 것이 아님 |
| spin | 콜백을 처리하는 이벤트 루프를 계속 도는 것 |
| QoS | Quality of Service. 통신 신뢰성·버퍼 깊이 설정. 숫자만 주면 큐 크기로 해석 |

```python
import rclpy as rp
from turtlesim.msg import Pose

rp.init()
test_node = rp.create_node('sub_test')

def callback(data):
    print('X:', data.x, 'Y:', data.y)

test_node.create_subscription(Pose, '/turtle1/pose', callback, 10)
rp.spin(test_node)
```

| 요소 | 뜻 |
|---|---|
| `rp.init()` | ROS 2 통신 컨텍스트 초기화. 노드를 만들기 전에 반드시 한 번 |
| `create_node('sub_test')` | 그래프에 올라갈 노드 이름. `ros2 node list` 에 이 이름이 뜸 |
| `create_subscription(타입, 토픽명, 콜백, QoS)` | 인자 넷의 순서와 의미. 타입과 토픽명이 발행 쪽과 정확히 같아야 붙음 |
| `Pose` | `turtlesim.msg` 의 메시지 타입. 어떤 필드가 있는지는 `ros2 interface show` 로 확인 |
| `10` | QoS 큐 깊이. 처리가 밀릴 때 몇 개까지 쌓아둘지 |
| `rp.spin(node)` | 콜백이 계속 불리도록 블로킹하며 대기. **이걸 안 부르면 콜백이 한 번도 안 불립니다** |

노트북에서 멈추려면 Stop 버튼을 누릅니다. `KeyboardInterrupt` 가 뜨는 것은 고장이 아니라 정상 종료입니다.

## 3. 토픽 발행 (Publisher)

```python
import rclpy as rp
from geometry_msgs.msg import Twist

rp.init()
test_node = rp.create_node('pub_test')
pub = test_node.create_publisher(Twist, '/turtle1/cmd_vel', 10)

msg = Twist()
msg.linear.x = 2.0
pub.publish(msg)
```

| 요소 | 뜻 |
|---|---|
| `create_publisher(타입, 토픽명, QoS)` | 구독과 대칭. 콜백 자리가 없다는 것만 다름 |
| `Twist()` | 빈 메시지 객체를 만들고 필드를 채워 넣는 방식 |
| `msg.linear.x = 2.0` | **`2` 가 아니라 `2.0`.** float 필드에 int 를 넣으면 타입 오류 |
| `publish(msg)` | 한 번 발행. 계속 보내려면 타이머가 필요 |
| `create_timer(초, 콜백)` | 주기 발행용. 콜백 안에서 `publish` 를 부르는 것이 정석 |

**막히면 볼 것.** 콜백이 안 불리면 (1) `spin` 을 불렀는지 (2) 토픽 이름·타입이 양쪽에서 같은지, 이 둘입니다. `rqt_graph` 로 선이 이어졌는지 눈으로 보는 것이 가장 빠릅니다.

## 4. 서비스 클라이언트

**흐름상 위치.** 1편에서 `ros2 service call` 로 했던 순간이동을 코드로 부릅니다. 토픽과 달리 **응답을 기다려야 한다**는 점이 새로 나오는 개념입니다.

| 용어 | 뜻 |
|---|---|
| Request / Response | 서비스의 요청 메시지 / 응답 메시지 |
| `.srv` | 서비스 타입 정의 파일. `---` 위가 Request, 아래가 Response |
| Future | 비동기 호출의 결과를 담을 「아직 안 채워진 상자」. 나중에 값이 들어옴 |

```python
import rclpy as rp
from turtlesim.srv import TeleportAbsolute

rp.init()
test_node = rp.create_node('client_test')
cli = test_node.create_client(TeleportAbsolute, '/turtle1/teleport_absolute')

req = TeleportAbsolute.Request()
req.x = 1.
req.y = 1.
req.theta = 3.14

while not cli.wait_for_service(timeout_sec=1.0):
    print('Waiting for service')

future = cli.call_async(req)
while not future.done():
    rp.spin_once(test_node)

print(future.done(), future.result())
```

| 요소 | 뜻 |
|---|---|
| `create_client(타입, 서비스이름)` | 서비스 쪽 연결 객체 |
| `타입.Request()` | 요청 메시지 객체. 타입 안에 중첩 클래스로 들어 있음 |
| `1.` | `1.0` 과 같은 float 표기 |
| `wait_for_service(timeout_sec=1.0)` | 서버가 준비될 때까지 대기. 준비되면 True |
| `call_async(req)` | 비동기 호출. 즉시 Future 를 돌려주고 블로킹하지 않음 |
| `spin_once(node)` | 대기 중인 콜백을 **한 번만** 처리. `spin` 은 무한 루프라 이 자리엔 못 씀 |
| `future.done()` | 응답이 도착했는지 |
| `future.result()` | 도착한 Response 객체 |

출력은 `False None` 이었다가 `True turtlesim.srv.TeleportAbsolute_Response()` 로 바뀝니다. `done()` 이 True 가 되는 순간에 `result()` 가 채워집니다. `미확인`

**왜 `spin_once` 루프를 도는가.** `call_async` 는 요청만 보내고 끝납니다. 응답 수신은 콜백 처리 과정에서 일어나므로, 누군가 spin 을 돌려주지 않으면 Future 는 영원히 `done()` 이 False 입니다. 「호출이 안 끝난다」는 증상의 대부분이 이것입니다.

## 5. 패키지 만들기 (여기서 노트북을 벗어납니다)

**왜 이 단계가 필요한가.** 노트북 코드는 다른 사람이 `ros2 run` 으로 실행할 수 없고, launch 파일에도 못 올리고, 로봇에 배포할 수도 없습니다. 재사용 가능한 단위로 옮기는 것이 이 모듈입니다.

| 용어 | 뜻 |
|---|---|
| 패키지(package) | 노드·설정·의존성을 묶어 배포·재사용하는 ROS 2 의 기본 단위 |
| 워크스페이스 | 패키지들을 모아 한꺼번에 빌드하는 상위 폴더. 안에 `src/` 를 둠 |
| colcon | 여러 패키지를 한 번에 빌드하는 빌드 도구 |
| ament_python | 순수 파이썬 패키지용 빌드 타입 |

```bash
cd ~/dev_ws/ros/src
ros2 pkg create --build-type ament_python my_first_package --dependencies rclpy
```

| 토큰 | 뜻 |
|---|---|
| `pkg create` | 패키지 뼈대(폴더·`package.xml`·`setup.py`)를 자동 생성 |
| `--build-type ament_python` | 파이썬 패키지로 만들라는 지정 |
| `my_first_package` | 패키지 이름. **폴더 이름·파이썬 모듈 이름·`ros2 run` 첫 인자가 모두 이 이름입니다** |
| `--dependencies rclpy` | `package.xml` 에 의존성을 미리 적어줌 |

생성되는 구조입니다.

| 경로 | 무엇 |
|---|---|
| `my_first_package/my_first_package/` | 실제 파이썬 소스가 들어가는 곳 (`__init__.py` 포함) |
| `my_first_package/package.xml` | 패키지 메타정보와 의존성 |
| `my_first_package/setup.py` | 설치 규칙. **`entry_points` 를 여기서 고칩니다** |
| `my_first_package/resource/` | 패키지 인덱스 마커 |

### 5-1. Node 클래스 상속이 정석 구조

노트북에서는 `create_node` 로 노드 객체를 받아 썼지만, 패키지에서는 `Node` 를 상속합니다. 상태(`self.total_dist` 같은 것)를 콜백들이 공유해야 하기 때문입니다.

```python
import rclpy as rp
from rclpy.node import Node
from turtlesim.msg import Pose

class TurtlesimSubscriber(Node):
    def __init__(self):
        super().__init__('turtlesim_subscriber')
        self.subscription = self.create_subscription(
            Pose, '/turtle1/pose', self.callback, 10)

    def callback(self, msg):
        print('X:', msg.x, 'Y:', msg.y)

def main(args=None):
    rp.init(args=args)
    node = TurtlesimSubscriber()
    rp.spin(node)
    node.destroy_node()
    rp.shutdown()

if __name__ == '__main__':
    main()
```

| 요소 | 뜻 |
|---|---|
| `super().__init__('turtlesim_subscriber')` | 부모 Node 에 노드 이름을 넘김 |
| `self.create_subscription(...)` | 노드 객체 자신의 메서드가 됨 |
| `self.callback` | 괄호 없이 함수 자체를 넘김. `self.callback()` 은 결과값을 넘기는 것이라 틀림 |
| `main(args=None)` | `ros2 run` 이 부를 진입점 |
| `destroy_node()` / `shutdown()` | 자원 정리. 없어도 돌지만 정석 |
| `if __name__ == '__main__':` | 파일을 직접 실행했을 때만 main 을 부르는 파이썬 관용구 |

### 5-2. entry_points 등록 없이는 `ros2 run` 이 못 찾습니다

`setup.py` 의 `entry_points` 를 고칩니다.

```python
entry_points={
    'console_scripts': [
        'my_subscriber = my_first_package.my_subscriber:main',
        'my_publisher = my_first_package.my_publisher:main',
    ],
},
```

| 조각 | 뜻 |
|---|---|
| `my_subscriber` (등호 왼쪽) | **`ros2 run` 에 칠 실행 파일 이름** |
| `my_first_package.my_subscriber` | 모듈 경로 (패키지.파일) |
| `:main` | 그 모듈 안에서 부를 함수 이름 |

### 5-3. 빌드하고 실행

```bash
cd ~/dev_ws/ros
colcon build
source install/setup.bash
ros2 run my_first_package my_subscriber
ros2 run my_first_package my_publisher
```

| 토큰 | 뜻 |
|---|---|
| `colcon build` | **워크스페이스 최상위(`src` 의 부모)에서** 실행. `src` 안에서 치면 안 됨 |
| `install/setup.bash` | 방금 빌드한 패키지 경로를 현재 셸에 심는 스크립트 |
| `source` | 새 터미널마다 다시 필요. `/opt/ros/jazzy/setup.bash` 와는 별개의 두 번째 source |

**가장 자주 나는 사고 세 가지입니다.**

| 증상 | 원인 |
|---|---|
| 실행 파일을 못 찾음 | `entry_points` 등록 누락, 또는 등록 후 재빌드 안 함 |
| 코드를 고쳤는데 반영이 안 됨 | `colcon build` 를 다시 안 함 |
| 새 터미널에서 import 에러 | `source install/setup.bash` 를 안 함 |

셋 다 「고쳤으면 빌드하고 source 한다」 한 줄로 정리됩니다. 이걸 alias 로 묶어두면 편합니다.

## 6. 커스텀 메시지·서비스 정의

**왜 별도 패키지가 필요한가.** 기본 제공 타입(`Twist`, `Pose` 등) 밖의 타입을 쓰려면 정의 파일을 코드로 생성해야 하는데, **`ament_python` 패키지는 그 생성을 못 합니다.** 그래서 `ament_cmake` 로 별도 `_msgs` 패키지를 하나 더 만듭니다.

```bash
cd ~/dev_ws/ros/src
ros2 pkg create --build-type ament_cmake my_first_package_msgs
```

`.msg` 는 필드만 나열합니다.

```
string name
int64 id
float32 pose_x
float32 pose_y
```

`CMakeLists.txt` 에 등록합니다.

```cmake
find_package(rosidl_default_generators REQUIRED)
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/MyFirstMsg.msg"
)
```

| 요소 | 뜻 |
|---|---|
| `rosidl` | ROS Interface Definition Language. `.msg`/`.srv`/`.action` 을 각 언어 코드로 변환하는 계층 |
| `rosidl_generate_interfaces` | 나열한 정의 파일을 실제 파이썬·C++ 클래스로 생성하는 매크로 |
| `${PROJECT_NAME}` | CMake 변수 참조. 패키지 이름이 들어감 |

```bash
colcon build && source install/setup.bash
ros2 interface show my_first_package_msgs/msg/MyFirstMsg
```

정의한 필드가 그대로 출력되면 생성 성공입니다. `미확인`

쓸 때는 기본 메시지와 완전히 같습니다.

```python
from my_first_package_msgs.msg import MyFirstMsg

msg = MyFirstMsg()
msg.name = 'turtle1'
msg.id = 1
msg.pose_x = 5.5
msg.pose_y = 5.5
self.publisher.publish(msg)
```

**`package.xml` 에 `my_first_package_msgs` 의존성을 추가하는 것을 잊으면** 빌드 순서가 꼬여서 「타입을 못 찾는다」로 나타납니다.

`.srv` 는 `---` 로 Request 와 Response 를 가르는 것만 다릅니다.

```
float32 x
float32 y
---
float32 dist
```

```python
def callback(self, request, response):
    response.dist = (request.x**2 + request.y**2) ** 0.5
    return response

self.srv = self.create_service(MyFirstSrv, 'my_first_srv', self.callback)
```

| 요소 | 뜻 |
|---|---|
| `create_service(타입, 이름, 콜백)` | 서버 쪽. 클라이언트의 `create_client` 와 대칭 |
| 콜백 인자 `(request, response)` | 미리 만들어진 빈 response 를 받아 채워서 **반환**해야 함 |
| `** 0.5` | 제곱근. 유클리드 거리 |

### 응용: 거북이 원형 배치

`/spawn` 서비스를 반복 호출해 거북이 N 마리를 원 위에 배치하는 예제입니다.

```python
import math
N = 8
for i in range(N):
    theta = 2 * math.pi * i / N
    x = r * math.cos(theta) + cx
    y = r * math.sin(theta) + cy
    req = Spawn.Request(x=x, y=y)
    spawn_cli.call_async(req)
```

**이 예제의 요점은 삼각함수가 아닙니다.** 서비스 호출을 루프에서 여러 번 비동기로 던지는 패턴 자체가 요점입니다.

## 7. 액션 서버 만들기

| 용어 | 뜻 |
|---|---|
| Goal / Feedback / Result | 목표 / 중간 진행상황(여러 번) / 최종 결과(한 번) |
| `.action` | 액션 타입 정의 파일. `---` **두 번**으로 Goal, Result, Feedback 3단 구분 |
| goal_handle | 현재 처리 중인 목표의 상태를 다루는 핸들 |

```python
from rclpy.action import ActionServer
from my_first_package_msgs.action import DistTurtle

class DistTurtleServer(Node):
    def __init__(self):
        super().__init__('dist_turtle_action_server')
        self.total_dist = 0
        self.action_server = ActionServer(
            self, DistTurtle, 'dist_turtle', self.execute_callback)
```

```python
def execute_callback(self, goal_handle):
    feedback_msg = DistTurtle.Feedback()
    while True:
        self.total_dist += self.calc_diff_pose()
        feedback_msg.remained_dist = (goal_handle.request.dist - self.total_dist)
        goal_handle.publish_feedback(feedback_msg)
        if feedback_msg.remained_dist < 0.2:
            break
    goal_handle.succeed()
    return DistTurtle.Result(total_dist=self.total_dist)
```

| 요소 | 뜻 |
|---|---|
| `ActionServer(node, 타입, 이름, 콜백)` | 인자 넷 |
| `execute_callback` | 목표가 들어오면 자동 호출됨. **이 함수가 끝날 때까지가 한 목표의 수명** |
| `goal_handle.request.dist` | 클라이언트가 보낸 Goal 필드 |
| `publish_feedback(msg)` | 진행상황 전송. 루프 안에서 반복 호출 |
| `goal_handle.succeed()` | 성공으로 종료 표시. **이걸 빠뜨리면 목표가 안 끝납니다** |
| `return 타입.Result(...)` | 최종 결과 반환 |

```bash
colcon build && source install/setup.bash
ros2 run my_first_package dist_turtle_action_server
# 다른 터미널에서
ros2 action send_goal dist_turtle my_first_package_msgs/action/DistTurtle '{linear_x: 2., angular_z: 2., dist: 2.}'
```

**서버와 `send_goal` 은 반드시 다른 터미널입니다.** 서버를 켜둔 채 목표를 여러 번 바꿔 보내며 실험할 수 있습니다.

정상이면 `Feedback: remained_dist` 가 반복해서 찍히다가 `Result: total_dist` 와 `SUCCEEDED` 로 끝납니다. `미확인`

> **우리 프로젝트에서 다시 나오는 곳.** Nav2 의 `NavigateToPose` 가 정확히 이 구조입니다. 목표 좌표를 Goal 로 주고, 남은 거리를 Feedback 으로 받고, 도착 여부를 Result 로 받습니다. 이 예제의 `remained_dist` 가 Nav2 의 `distance_remaining` 에 그대로 대응됩니다. `추측`

## 8. 파라미터

**왜 필요한가.** 임계값 하나를 바꾸려고 코드를 고치고 다시 빌드하는 것은 낭비입니다. 파라미터는 노드를 켜둔 채 값을 바꾸게 해줍니다.

터미널에서:

```bash
ros2 param list
ros2 param get /turtlesim background_g
ros2 param set /turtlesim background_r 250
ros2 param dump /turtlesim > ./turtlesim.yaml
ros2 param load /turtlesim ./turtlesim.yaml
```

| 토큰 | 뜻 |
|---|---|
| `param list` | 노드별 파라미터 이름 목록 |
| `get` / `set` | 조회 / 변경. `set` 하면 turtlesim 창 색이 즉시 바뀜 |
| `dump` | 현재 값을 YAML 형식으로 표준출력에 뱉음 |
| `>` | 리다이렉트. 표준출력을 파일로 씀 (덮어쓰기. `>>` 는 이어붙이기) |
| `load` | YAML 파일의 값을 노드에 적용 |

**노드를 재시작하면 초기값으로 되돌아갑니다.** 영구 보존은 YAML 담당입니다. `param load` 가 실패하면 대개 상대경로 문제입니다.

코드에서:

```python
self.declare_parameter('quantile_time', 0.75)
self.declare_parameter('almost_goal_time', 0.95)
(qt, agt) = self.get_parameters(['quantile_time', 'almost_goal_time'])
self.quantile_time = qt.value
self.add_on_set_parameters_callback(self.parameter_callback)

def parameter_callback(self, params):
    for param in params:
        if param.name == 'quantile_time':
            self.quantile_time = param.value
    return SetParametersResult(successful=True)
```

| 요소 | 뜻 |
|---|---|
| `declare_parameter(이름, 기본값)` | **선언해야 터미널·rqt 에 보입니다.** 선언 없이 쓰면 안 잡힘 |
| `get_parameters([...])` | Parameter 객체 리스트를 돌려줌. 실제 값은 `.value` |
| `add_on_set_parameters_callback` | 값이 바뀔 때마다 호출될 함수 등록 |
| `SetParametersResult(successful=True)` | 「이 변경을 받아들이겠다」는 응답. 검증 로직을 넣어 거부할 수도 있음 |

**`set` 했는데 동작이 그대로**인 증상은 거의 항상 이 콜백을 등록하지 않은 것입니다. 선언만 해두면 값은 바뀌지만 노드 내부 변수는 갱신되지 않습니다.

rqt 슬라이더로 조정하려면 범위를 지정합니다.

```python
from rcl_interfaces.msg import ParameterDescriptor, FloatingPointRange

desc = ParameterDescriptor(floating_point_range=[
    FloatingPointRange(from_value=0.0, to_value=1.0, step=0.01)])
self.declare_parameter('quantile_time', 0.75, desc)
```

범위를 안 주면 rqt 에서 텍스트 입력창으로만 나옵니다. rqt 의 Plugins > Configuration > Dynamic Reconfigure 에서 노드를 고르면 보입니다.

## 9. 디버그 도구와 launch

### 9-1. 로깅

```python
self.get_logger().info('메시지')
```

`print` 대신 쓰면 **노드 이름·시각·레벨이 함께 기록**되고 rqt Console 에서 레벨별로 걸러볼 수 있습니다. 노드가 5개쯤 돌기 시작하면 `print` 는 누가 찍은 건지 알 수 없어 쓸모가 없어집니다.

```bash
sudo apt install ros-jazzy-rqt* -y
ros2 run turtlesim turtlesim_node
rqt
```

| 토큰 | 뜻 |
|---|---|
| `ros-jazzy-rqt*` | 이름이 `ros-jazzy-rqt` 로 시작하는 rqt 플러그인 패키지를 전부 설치. 셸이 아니라 **apt 가 직접 이 패턴을 해석**합니다 |
| rqt | 플러그인을 끼워 쓰는 ROS 2 GUI 도구 모음 |

거북이가 벽에 부딪히면 rqt Console 에 이렇게 남습니다.

```
[WARN] [turtlesim]: Oh no! I hit the wall! (Clamping from [x=11.12, y=5.54])
```

| 플러그인 | 하는 일 |
|---|---|
| Logging > Console | 로그를 레벨별로 필터링 |
| Visualization > Plot (`rqt_plot`) | 토픽의 수치 필드를 실시간 그래프로 |
| Topic Monitor | 토픽 값과 수신 주기(Hz) 관찰 |
| Message Publisher | GUI 로 값을 채워 토픽 수동 발행 |

### 9-2. rosbag

```bash
# 터미널 A: 토픽 발행
ros2 topic pub --rate 1 /turtle1/cmd_vel geometry_msgs/msg/Twist '{linear: {x: 2.}, angular: {z: 1.8}}'
# 터미널 B: 기록 (Ctrl+C 로 종료)
ros2 bag record -o turtle_test -a
# 나중에 재생
ros2 bag play turtle_test
```

| 토큰 | 뜻 |
|---|---|
| `bag record` | 흐르는 토픽을 파일로 기록 |
| `-o turtle_test` | output. 저장할 폴더 이름 |
| `-a` | all. 모든 토픽 기록 |
| `bag play` | 기록한 토픽을 그때의 타이밍 그대로 재생 |

> **우리 프로젝트에서 가장 크게 쓰일 도구가 이것입니다.** Go2 실기를 만질 수 있는 시간은 짧고 나눠 써야 합니다. **실기가 있는 동안 카메라·LiDAR 토픽을 rosbag 으로 통째로 기록해두면, 이후 탐지 알고리즘 개발과 튜닝은 로봇 없이 재생만으로 할 수 있습니다.** CV 담당 입장에서 실기 접근 시간의 제약을 가장 크게 줄여주는 수단이라고 봅니다. `추측`

### 9-3. launch

노드를 하나씩 터미널마다 켜는 것은 3개를 넘어가면 무리입니다.

```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package='turtlesim', executable='turtlesim_node'),
        Node(package='my_first_package', executable='my_publisher'),
    ])
```

| 요소 | 뜻 |
|---|---|
| `generate_launch_description()` | ROS 2 가 찾는 고정된 함수 이름. 바꾸면 안 됨 |
| `LaunchDescription([...])` | 실행할 것들의 목록 |
| `Node(package=, executable=)` | `ros2 run <package> <executable>` 과 같은 두 인자 |

```bash
colcon build
source install/setup.bash
ros2 launch my_first_package turtlesim_and_teleop.launch.py
```

**launch 파일도 `setup.py` 의 `data_files` 에 등록해야 설치 폴더로 복사됩니다.** 등록하지 않으면 파일은 있는데 `ros2 launch` 가 못 찾는 상태가 됩니다. launch 구조를 바꿀 때마다 재빌드와 재 source 가 필요한 것도 같습니다.

## 10. 우리 프로젝트로의 연결

| 이 수업에서 배운 것 | FOOTHOLD 에서 대응되는 곳 |
|---|---|
| 토픽 구독·발행 | 카메라 이미지 구독 → 탐지 결과 발행. CV 노드의 기본 골격 |
| 커스텀 `.msg` | 탐지 결과(클래스·박스·신뢰도)를 담을 자체 메시지 타입 |
| 액션 | Nav2 `NavigateToPose` 목표 이동 |
| 파라미터 | 탐지 임계값·카메라 해상도를 재빌드 없이 조정 |
| rosbag | 실기 접근 시간이 제한될 때 데이터를 떠와서 오프라인 개발 |
| launch | 카메라 + 탐지 + Nav2 + RViz 를 한 번에 띄우는 데모 실행 |

## 11. 출처

- rclpy 공식 API 문서: https://docs.ros.org/en/jazzy/p/rclpy/
- ROS 2 Jazzy 튜토리얼 (클라이언트 라이브러리): https://docs.ros.org/en/jazzy/Tutorials/Beginner-Client-Libraries.html
- 커스텀 msg·srv 만들기(공식): https://docs.ros.org/en/jazzy/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.html
- 파이썬 액션 서버·클라이언트(공식): https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Writing-an-Action-Server-Client/Py.html
- launch 시스템(공식): https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Launch/Launch-Main.html
- rosbag2 기록·재생(공식): https://docs.ros.org/en/jazzy/Tutorials/Beginner-CLI-Tools/Recording-And-Playing-Back-Data/Recording-And-Playing-Back-Data.html
- 조선대 ROS 2 수업 2편 「ROS2 Python 프로그래밍」: 조선대 저작물이므로 저장소에 넣지 않았습니다. 원본은 팀 자료실에 있습니다.

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-08-27 | 처음 씀 | 이전 이력은 git 에 |
