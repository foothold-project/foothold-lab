# ROS 2 개발환경 구축 정리 (Ubuntu 24.04 · Jazzy)

> 분류: 가이드
> 작성: 오현민 · 2026-08-27 12:20
> 근거: 조선대 ROS 2 수업 1편 「ROS2 개발환경 구축」(2026-08-22 배포, 자료 원본은 저장소에 넣지 않음) + ROS 2 Jazzy 공식 설치 문서 대조
> 요지: ROS 2 Jazzy 개발환경을 Ubuntu 설치부터 turtlesim 4대 통신까지 명령 순서 그대로 재구성하고, 강의 자료의 apt 저장소 등록 방식이 현재 공식 문서와 다르다는 점을 확인해 대체 절차를 함께 적었다.
> 상태: 확정
> 판: v1.0
>
> 원본: `inbox/oh/20260826-ros2-01-개발환경구축.md` (PR #63, 2026-08-27 머지). 팀장이 `docs/` 로 승격하며 머리글 형식만 정리했고 본문은 손대지 않았다.

## 0. 이 문서를 읽는 법

수업 자료를 다시 열지 않고 이 문서만 보고 순서대로 칠 수 있게 쓴 노트입니다.
슬라이드를 옮겨 적은 것이 아니라, 「개념 → 왜 필요한가 → 명령 → 토큰별 뜻」 순서로 제가 다시 짠 것입니다.

**증거 표기 기준.** 아래 명령은 수업에서 시연된 순서 그대로이지만, **제 노트북에서 처음부터 끝까지 재실행해보지는 않았습니다.** 그래서 명령의 동작 결과는 전부 `미확인`으로 답니다. `확인됨`을 단 것은 제가 직접 원문 페이지를 열어 대조한 공식 문서 내용뿐입니다.

**환경 전제.** Ubuntu 24.04 LTS (Noble) + ROS 2 Jazzy Jalisco. 팀 표준이 이것이고, 금요일 수업도 이 조합을 기준으로 진행됩니다.

## 1. 왜 하필 Ubuntu 24.04 + Jazzy 인가

먼저 용어부터 정리합니다. 이 문서에서 처음 나오는 것들입니다.

| 용어 | 뜻 |
|---|---|
| 배포판(distribution) | 리눅스 커널에 패키지 관리자·데스크톱 환경 등을 묶어 배포하는 단위. Ubuntu 가 그중 하나 |
| LTS | Long Term Support. 5년간 보안·기능 업데이트가 보장되는 장기지원판 |
| ROS 2 | 로봇 소프트웨어를 노드 단위로 쪼개 서로 통신시키는 미들웨어 프레임워크. 운영체제가 아님 |
| 배포판(ROS 2 쪽) | ROS 2 도 자체 버전 이름을 가짐. Humble · Jazzy · Kilted 같은 것들 |
| apt | Ubuntu 의 패키지 관리자. Advanced Package Tool |

**ROS 2 배포판과 Ubuntu 버전은 1:1로 묶여 있습니다.** Jazzy 의 Tier 1 대상 플랫폼은 Ubuntu 24.04 (Noble) amd64·arm64 뿐이고, deb 패키지도 Noble 용만 제공됩니다. `확인됨` ([ROS 2 Jazzy 지원 플랫폼](https://docs.ros.org/en/jazzy/Releases/Release-Jazzy-Jalisco.html), [Jazzy deb 설치 문서](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html))

그래서 22.04 에 Jazzy 를 얹거나 24.04 에 Humble 을 얹는 조합은 apt 로는 애초에 길이 없습니다. 팀 표준을 24.04 로 고정한 실질적인 이유가 이것입니다.

> **팀에 걸리는 지점.** Go2 커뮤니티 자료(`unitree_ros2` 등)는 상당수가 Humble(22.04) 기준입니다. Jazzy 에서 그대로 도는지는 별도 검증이 필요합니다. `미확인`

설치를 마치고 가장 먼저 치는 명령입니다.

```bash
sudo apt update && sudo apt upgrade -y
```

| 토큰 | 뜻 |
|---|---|
| `sudo` | superuser do. 이 한 줄만 관리자 권한으로 실행 |
| `apt update` | 패키지 **목록**만 갱신. 설치된 패키지는 안 건드림 |
| `&&` | 앞 명령이 성공(종료코드 0)했을 때만 뒤 명령 실행. `;` 는 실패해도 실행하므로 다름 |
| `apt upgrade` | 갱신된 목록을 근거로 실제 패키지를 최신으로 올림 |
| `-y` | yes. 「계속할까요?」 확인 질문에 자동으로 예 |

`update` 없이 `upgrade` 만 치면 옛 목록을 보고 올리므로 의미가 없습니다. 항상 짝입니다.

## 2. 터미널과 기본 앱

수업은 Terminator(창 분할 터미널)와 Chrome 을 깔면서 리눅스 기본 명령을 익히는 순서로 갑니다.

```bash
sudo apt update
sudo apt install terminator -y
```

| 토큰 | 뜻 |
|---|---|
| `apt install <이름>` | 저장소에서 해당 패키지를 내려받아 설치 |
| `terminator` | 한 창을 여러 칸으로 쪼개 쓰는 터미널. ROS 2 는 터미널을 3~4개씩 동시에 쓰므로 사실상 필수 |

Chrome 은 apt 저장소에 없으므로 .deb 파일을 직접 받아 설치합니다.

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome*.deb
sudo apt --fix-broken install -y
```

| 토큰 | 뜻 |
|---|---|
| `wget` | web get. URL 을 현재 폴더로 내려받음 |
| `dpkg` | Debian package. .deb 파일 하나를 직접 설치하는 저수준 도구 |
| `-i` | install |
| `*` | 셸 와일드카드. `google-chrome` 으로 시작하고 `.deb` 로 끝나는 파일 이름을 셸이 대신 채워줌 |
| `--fix-broken install` | `dpkg` 는 의존성을 자동으로 안 채움. 빠진 의존 패키지를 apt 가 뒤이어 메움 |

`dpkg -i` 뒤에 `--fix-broken install` 이 따라붙는 이유가 여기 있습니다. **순서가 바뀌면 안 됩니다.** `미확인`

리눅스 기본 명령 넷입니다.

| 명령 | 원말 | 하는 일 |
|---|---|---|
| `pwd` | print working directory | 지금 어느 폴더에 있는지 출력 |
| `ls -al` | list · all · long | 숨김 파일(`.` 로 시작)까지 상세 목록 |
| `cd ~` | change directory · `~`=홈 | 홈 디렉터리로 이동 |
| `mkdir dev_ws` | make directory | 새 폴더 생성. `ws` 는 workspace |

## 3. Python 가상환경과 PEP 668

**왜 이 단계가 여기 있는가.** ROS 2 자체는 시스템 파이썬을 씁니다. 하지만 Jupyter·numpy·YOLO 같은 것을 시스템 파이썬에 직접 깔면 OS 가 관리하는 패키지와 충돌합니다. Ubuntu 24.04 는 아예 그것을 막아뒀습니다.

| 용어 | 뜻 |
|---|---|
| venv | virtual environment. 프로젝트마다 독립된 파이썬 패키지 공간을 만드는 표준 도구 |
| pip | 파이썬 패키지 설치 도구 |
| PEP 668 | 「외부에서 관리되는 환경」을 표시해 시스템 파이썬에 pip 설치를 막는 규약. Ubuntu 24.04 부터 적용 |

시스템 파이썬에 그냥 설치하면 이 에러가 납니다.

```
error: externally-managed-environment
x This environment is externally managed
```

이건 고장이 아니라 **의도된 차단**입니다. 해결책은 venv 를 만드는 것이지, `--break-system-packages` 로 뚫는 것이 아닙니다.

준비(최초 1회):

```bash
sudo apt update && sudo apt install python3-pip -y
sudo apt install python3.12-venv -y
```

| 토큰 | 뜻 |
|---|---|
| `python3-pip` | pip 본체 |
| `python3.12-venv` | venv 모듈. **버전 번호가 붙습니다.** 24.04 의 기본 파이썬이 3.12 라서 3.12 |

`python3 -V` 로 실제 버전을 먼저 확인하고 숫자를 맞추는 것이 안전합니다.

가상환경 생성·활성화·해제:

```bash
python3 -m venv ~/venv/robot_venv
source ~/venv/robot_venv/bin/activate
pip install --upgrade pip
deactivate
```

| 토큰 | 뜻 |
|---|---|
| `-m venv` | module. 설치된 `venv` 모듈을 스크립트처럼 실행 |
| `~/venv/robot_venv` | 만들 위치. 경로일 뿐이라 어디든 되지만 수업은 이 경로로 통일 |
| `source` | 스크립트를 **새 셸이 아니라 현재 셸에서** 실행. 그래야 PATH 변경이 지금 터미널에 남음 |
| `activate` | PATH 앞에 가상환경의 `bin` 을 끼워 넣는 스크립트 |
| `deactivate` | 그것을 되돌림 |

활성화되면 프롬프트 앞에 `(robot_venv)` 가 붙습니다. **이게 붙어 있는지 눈으로 확인하는 습관이 실습 내내 가장 많은 오류를 막아줍니다.** 수업은 `test_venv` 로 한 번 연습한 뒤 `robot_venv` 하나를 끝까지 재사용합니다.

## 4. Jupyter Notebook

**왜 여기서 Jupyter 인가.** ROS 2 노드를 처음부터 패키지로 만들면 코드 한 줄 고칠 때마다 빌드를 다시 해야 합니다. 셀 단위로 굴려보는 단계를 먼저 두는 것이 2편(Python 프로그래밍)의 전제입니다.

```bash
source ~/venv/robot_venv/bin/activate
pip install jupyter
mkdir -p ~/dev_ws/robot
cd ~/dev_ws/robot
jupyter notebook
```

| 토큰 | 뜻 |
|---|---|
| `mkdir -p` | parents. 중간 폴더가 없으면 같이 만들고, 이미 있어도 에러를 내지 않음 |
| `jupyter notebook` | 로컬 서버를 띄우고 브라우저를 자동으로 엶 (`http://localhost:8888/tree`) |
| `Ctrl + C` | 터미널에서 서버 종료 |
| `pip list` | 현재 환경에 설치된 패키지 목록 |

셀 실행은 `Shift + Enter`. 첫 셀에 `print('Hello, Jupyter!')` 를 넣어 출력이 나오면 성공입니다. `미확인`

## 5. VSCode

```bash
sudo dpkg -i code_*.deb
sudo apt --fix-broken install -y
cd ~/dev_ws/robot && code .
```

| 토큰 | 뜻 |
|---|---|
| `code .` | 현재 폴더(`.`)를 VSCode 로 엶 |
| `&&` | `cd` 가 성공했을 때만 `code` 실행. 폴더가 없는데 여는 사고를 막음 |

설치 중 「Microsoft 저장소를 추가할까요?」에 Yes 를 누르면 이후 apt 로 업데이트됩니다.
설치 직후 `code` 명령이 안 먹히면 **터미널을 새로 여십시오.** PATH 환경변수는 새 셸 세션부터 반영됩니다.

VSCode 에서 노트북을 쓸 때 자주 나는 오류는 `ModuleNotFoundError` 인데, 원인은 대개 **커널이 robot_venv 가 아닌 것**입니다. 하단 상태바의 인터프리터를 먼저 확인하고, 그래도 없으면 그 환경 안에서 설치합니다.

```bash
source ~/venv/robot_venv/bin/activate
pip install numpy
```

## 6. ROS 2 Jazzy 설치 (여기서 공식 문서와 갈립니다)

### 6-1. 로케일과 universe 저장소

```bash
sudo apt update && sudo apt install locales software-properties-common -y
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
sudo add-apt-repository universe
```

| 토큰 | 뜻 |
|---|---|
| `locale` | 언어·문자 인코딩 설정. UTF-8 이 아니면 ROS 2 메시지 출력이 깨질 수 있음 |
| `locale-gen` | 지정한 로케일 데이터를 생성 |
| `update-locale` | 시스템 기본 로케일 환경변수를 기록 |
| `software-properties-common` | `add-apt-repository` 명령을 제공하는 패키지 |
| `universe` | Ubuntu 의 커뮤니티 관리 저장소. ROS 2 가 의존하는 패키지 다수가 여기 있음 |

이 두 가지는 **ROS 2 저장소를 등록하기 전에** 끝나 있어야 합니다. 공식 문서도 같은 순서입니다. `확인됨` ([Jazzy deb 설치 문서](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html))

### 6-2. 저장소 등록: 수업 방식과 현재 공식 방식이 다릅니다

**수업에서 시연된 방식** (GPG 키를 직접 내려받아 apt 소스 목록을 손으로 씀):

```bash
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list
```

토큰 해부는 나중에 저 줄을 다시 볼 때를 위해 남겨둡니다.

| 토큰 | 뜻 |
|---|---|
| `curl` | URL 로 데이터를 주고받는 도구 |
| `-sSL` | `-s` 진행표시 숨김 · `-S` 그래도 에러는 표시 · `-L` 리다이렉트 따라가기 |
| `-o <경로>` | output. 받은 내용을 그 파일로 저장 |
| GPG 키 | 저장소가 진짜 ROS 배포처에서 온 것인지 검증하는 서명. 이게 없으면 apt 가 거부 |
| `\` (줄 끝) | 줄바꿈 무효화. 긴 한 줄 명령을 여러 줄로 나눠 쓰는 표시 |
| `$(...)` | 명령 치환. 괄호 안 명령을 먼저 실행하고 그 출력을 그 자리에 끼워 넣음 |
| `dpkg --print-architecture` | `amd64` 같은 CPU 아키텍처 문자열 출력 |
| `. /etc/os-release` | `.` 은 `source` 의 축약. OS 정보 파일을 읽어 변수로 만듦 |
| `$UBUNTU_CODENAME` | 위에서 읽힌 변수. 24.04 면 `noble` |
| `\|` | 파이프. 앞 명령의 출력을 뒤 명령의 입력으로 넘김 |
| `tee <파일>` | 입력을 파일에 쓰면서 화면에도 출력. `>` 대신 쓰는 이유는 `sudo` 가 필요한 파일이기 때문 |

`echo ... > /etc/apt/...` 로 쓰면 리다이렉트(`>`)는 sudo 권한을 받기 전의 셸이 수행하므로 권한 오류가 납니다. `sudo tee` 를 쓰는 이유가 이것입니다.

**현재 공식 문서의 방식**은 위 두 단계를 `ros2-apt-source` 패키지 하나로 대체합니다. `확인됨` ([Jazzy deb 설치 문서](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html), [ros-apt-source 저장소](https://github.com/ros-infrastructure/ros-apt-source/))

```bash
sudo apt update && sudo apt install curl -y
export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F'"' '{print $4}')
curl -L -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo ${UBUNTU_CODENAME:-${VERSION_CODENAME}})_all.deb"
sudo dpkg -i /tmp/ros2-apt-source.deb
```

| 토큰 | 뜻 |
|---|---|
| `export` | 셸 변수를 자식 프로세스도 볼 수 있게 환경변수로 내보냄 |
| `grep -F "tag_name"` | fixed string. 정규식으로 해석하지 않고 문자 그대로 찾음 |
| `awk -F'"' '{print $4}'` | `"` 를 구분자로 잘라 4번째 조각(버전 문자열)만 출력 |
| `${VAR:-대체값}` | VAR 이 비어 있으면 대체값을 씀 |
| `ros2-apt-source` | 키와 소스 목록을 한꺼번에 넣어주는 패키지. 키가 교체돼도 이 패키지 업데이트로 따라감 |

**어느 쪽을 쓸지에 대한 제 판단.** 수업 방식도 지금 동작할 가능성이 높지만 `미확인`이고, 서명 키가 바뀌면 `NO_PUBKEY` 계열 에러로 조용히 깨지는 쪽입니다. 실제로 ROS 측이 apt 소스 관리를 패키지로 옮긴 이유가 그것입니다. **팀 환경 구축 문서를 쓸 때는 공식 방식을 기본으로 두는 편이 낫다고 봅니다.** `추측` (근거: 공식 문서가 이 방식만 안내하고 있음)

### 6-3. 설치와 동작 확인

```bash
sudo apt update
sudo apt install ros-dev-tools -y
sudo apt install ros-jazzy-desktop -y
source /opt/ros/jazzy/setup.bash
```

| 토큰 | 뜻 |
|---|---|
| `ros-dev-tools` | colcon·rosdep 등 빌드/개발 도구 묶음 |
| `ros-jazzy-desktop` | ROS 2 본체 + RViz2 + demo 노드 + turtlesim 등이 포함된 큰 묶음 |
| `/opt/ros/jazzy/setup.bash` | ROS 2 환경변수를 현재 셸에 심는 스크립트 |
| `source` | **새 터미널마다 다시 해야 합니다.** 안 하면 `ros2` 명령을 못 찾습니다 |

터미널 두 개로 통신을 확인합니다. **각 터미널에서 각각 source 가 필요합니다.**

```bash
# 터미널 A
ros2 run demo_nodes_cpp talker
# 터미널 B
ros2 run demo_nodes_py listener
```

A 가 보낸 문자열이 B 에 찍히면 설치가 정상입니다. C++ 노드와 Python 노드가 아무 설정 없이 통신한다는 점이 요지입니다. 언어가 달라도 메시지 타입만 같으면 붙습니다. `미확인`

## 7. bashrc · alias · ROS_DOMAIN_ID

| 용어 | 뜻 |
|---|---|
| shell | 명령을 해석해 실행하는 프로그램. `echo $SHELL` 로 확인 (보통 `/bin/bash`) |
| `.bashrc` | 홈 디렉터리에 있는 설정 파일. 터미널을 열 때마다 자동 실행 |
| `source` | 파일 내용을 현재 셸에 즉시 반영 |
| DDS | ROS 2 의 통신 미들웨어. 발행/구독을 실제로 나르는 계층 |
| ROS_DOMAIN_ID | 같은 ID 끼리만 통신하도록 나누는 숫자. 다른 사람 토픽과 섞이는 것을 막음 |

매번 `source /opt/ros/jazzy/setup.bash` 를 치는 것이 번거로우므로 `.bashrc` 맨 아래에 등록합니다.

```bash
code ~/.bashrc
```

파일 맨 마지막에 두 줄을 추가합니다.

```bash
echo "ROS2 Jazzy is activated!"
source /opt/ros/jazzy/setup.bash
```

`echo` 문구를 같이 넣는 이유는 **터미널을 열 때 눈으로 확인하려는 것**입니다. 저 문구가 안 보이면 환경이 안 잡힌 것이므로 원인 찾기가 빨라집니다.

```bash
source ~/.bashrc
```

별칭과 도메인 ID:

```bash
alias jazzy="source /opt/ros/jazzy/setup.bash"
alias sb="source ~/.bashrc"
alias
export ROS_DOMAIN_ID=13
alias ros_domain="export ROS_DOMAIN_ID=13"
```

| 토큰 | 뜻 |
|---|---|
| `alias 이름="명령"` | 긴 명령에 짧은 이름을 붙임. **등호 앞뒤에 공백을 넣으면 안 됩니다** |
| `alias` (인자 없이) | 등록된 별칭 전체 목록 |
| `export ROS_DOMAIN_ID=13` | 이 셸과 자식 프로세스에만 적용. 영구 적용하려면 `.bashrc` 에 넣어야 함 |

> **팀에 걸리는 지점.** 수업에서 같은 네트워크의 다른 사람 turtlesim 이 내 명령에 반응하는 상황이 생길 수 있습니다. Go2 실기를 여러 명이 같은 Wi-Fi 에서 만질 때 특히 문제가 되므로, **팀 차원에서 담당별 ROS_DOMAIN_ID 를 미리 나눠 정해두는 편이 낫다고 봅니다.** `추측`

## 8. turtlesim 으로 4대 통신 체득

| 용어 | 뜻 |
|---|---|
| ROS 2 그래프 | 실행 중인 노드들과 그 사이 연결(토픽·서비스·액션)을 합쳐 부르는 말 |
| 노드(Node) | 하나의 기능을 담당하는 실행 단위 프로그램 |
| turtlesim | 학습용 거북이 시뮬레이터 노드 |

```bash
source /opt/ros/jazzy/setup.bash
ros2 run turtlesim turtlesim_node
```

| 토큰 | 뜻 |
|---|---|
| `ros2` | ROS 2 통합 CLI. 뒤에 오는 첫 단어가 하위 명령 |
| `run` | 「패키지 안의 실행 파일을 돌려라」 |
| `turtlesim` | 패키지 이름 |
| `turtlesim_node` | 그 패키지 안의 실행 파일 이름 |

### 8-1. 노드 조회

```bash
ros2 node list
ros2 node info /turtlesim
```

`node list` 는 실행 중인 노드 이름만, `node info` 는 그 노드가 구독·발행하는 토픽과 제공하는 서비스·액션까지 보여줍니다. **모르는 로봇 패키지를 처음 만질 때 가장 먼저 치는 명령이 `node info` 입니다.**

### 8-2. 서비스: 요청 → 응답의 1:1 동기 통신

| 용어 | 뜻 |
|---|---|
| 서비스(Service) | Request 를 보내면 Response 가 돌아오는 1:1 단발성 통신 |
| namespace | `/turtle1/set_pen` 처럼 특정 이름 아래 묶인 계층. `/reset` 처럼 없는 것도 있음 |

```bash
ros2 service list
ros2 interface show turtlesim/srv/TeleportAbsolute
ros2 service call /turtle1/teleport_absolute turtlesim/srv/TeleportAbsolute "{x: 2, y: 2, theta: 1.57}"
ros2 service call /reset std_srvs/srv/Empty {}
ros2 service call /spawn turtlesim/srv/Spawn "{x: 1, y: 1, theta: 0, name: ''}"
```

| 토큰 | 뜻 |
|---|---|
| `interface show` | 그 타입이 어떤 필드를 요구하는지 정의를 출력. `---` 위가 Request, 아래가 Response |
| `service call <이름> <타입> "{...}"` | 세 조각이 전부 필요. 이름만으로는 부족 |
| `"{x: 2, y: 2, theta: 1.57}"` | YAML 문법. 셸이 중괄호를 해석하지 않도록 따옴표로 감쌈 |
| `1.57` | 라디안. 3.14/2 이므로 90도 |
| `{}` | Empty 타입이라 채울 필드가 없다는 뜻 |

**우리 프로젝트에서 다시 나오는 곳.** 카메라 노드를 켜고 끄거나 지도를 저장하는 것 같은 단발 명령이 전부 서비스입니다.

### 8-3. 토픽: 발행 → 구독의 비동기 다대다 스트리밍

```bash
ros2 topic list -t
ros2 topic echo /turtle1/pose
ros2 topic pub --once /turtle1/cmd_vel geometry_msgs/msg/Twist "{linear: {x: 2.0}, angular: {z: 1.8}}"
rqt_graph
```

| 토큰 | 뜻 |
|---|---|
| `-t` | type. 토픽 이름 옆에 메시지 타입까지 같이 표시 |
| `echo` | 그 토픽에 흐르는 메시지를 터미널에 계속 출력 |
| `pub` | publish. 터미널에서 직접 발행 |
| `--once` | 한 번만 발행하고 종료 |
| `--rate 1` | 초당 1회씩 계속 발행. 위 값으로 주면 원을 그림 |
| `Twist` | 속도 메시지 타입. `linear.x` 는 전진 속도, `angular.z` 는 회전 속도 |
| `2.0` | **소수점을 꼭 붙입니다.** float 필드에 `2` 를 주면 타입 오류가 납니다 |
| `rqt_graph` | 노드와 토픽 연결을 그림으로 보여주는 GUI |

**우리 프로젝트에서 다시 나오는 곳.** 카메라 이미지, LiDAR 스캔, 속도 명령이 전부 토픽입니다. CV 담당 입장에서는 「이미지 토픽을 구독해서 탐지 결과 토픽을 발행한다」가 작업의 기본 골격입니다.

### 8-4. 액션: 목표 → 피드백 → 결과

| 용어 | 뜻 |
|---|---|
| 액션(Action) | Goal 을 주면 Feedback 이 계속 오다가 마지막에 Result 가 오는 통신. 중간 취소 가능 |

```bash
ros2 action send_goal /turtle1/rotate_absolute turtlesim/action/RotateAbsolute "{theta: 3.14}"
ros2 run turtlesim turtle_teleop_key
```

**우리 프로젝트에서 다시 나오는 곳.** Nav2 의 목표점 이동(`NavigateToPose`)이 정확히 액션입니다. 「목표 좌표를 주고, 남은 거리를 피드백으로 받고, 도착하면 결과를 받는」 구조가 그대로 대응됩니다. 그래서 이 단계에서 액션을 대충 넘기면 Nav2 에서 다시 막힙니다.

### 8-5. 세 통신 비교

| 통신 | 방식 | 예 | 언제 쓰나 |
|---|---|---|---|
| 토픽 | Pub/Sub 비동기 다대다 | `/turtle1/cmd_vel`, 카메라 이미지 | 계속 흐르는 데이터 |
| 서비스 | Req/Res 동기 1:1 | `/spawn`, `/reset` | 즉시 끝나는 단발 요청 |
| 액션 | Goal/Feedback/Result | `RotateAbsolute`, Nav2 이동 | 오래 걸리고 진행상황이 필요한 작업 |

## 9. 막혔을 때 먼저 볼 것

| 증상 | 원인 후보 |
|---|---|
| `ros2` 명령을 못 찾음 | 그 터미널에서 `source /opt/ros/jazzy/setup.bash` 안 함 |
| `turtlesim` 이 없음 | `sudo apt install ros-jazzy-turtlesim` |
| 토픽을 발행해도 안 움직임 | 토픽 이름 또는 메시지 타입 불일치. `ros2 topic list -t` 로 대조 |
| 다른 사람 거북이가 반응함 | `ROS_DOMAIN_ID` 가 겹침 |
| `externally-managed-environment` | 시스템 파이썬에 pip 설치 시도. venv 안에서 하십시오 |
| 긴 명령 오타 | Tab 자동완성을 쓰십시오. 타입 이름은 특히 길어서 손으로 치면 거의 틀립니다 |

## 10. 출처

- ROS 2 Jazzy 설치 문서(공식): https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html
- ROS 2 Jazzy 릴리스·지원 플랫폼(공식): https://docs.ros.org/en/jazzy/Releases/Release-Jazzy-Jalisco.html
- ros-apt-source 저장소: https://github.com/ros-infrastructure/ros-apt-source/
- REP 2000 (배포판별 대상 플랫폼 규정): https://reps.openrobotics.org/rep-2000/
- turtlesim 기반 CLI 튜토리얼(공식): https://docs.ros.org/en/jazzy/Tutorials/Beginner-CLI-Tools.html
- 조선대 ROS 2 수업 1편 「ROS2 개발환경 구축」: 조선대 저작물이므로 저장소에 넣지 않았습니다. 원본은 팀 자료실에 있습니다.

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-08-27 | 처음 씀 | 이전 이력은 git 에 |
