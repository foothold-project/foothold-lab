# -*- coding: utf-8 -*-
"""용어 사전 보강: 백과(encyclopedia.html)의 용어 카드를 다듬는다.

  하는 일 세 가지
   ① 기존 카드에 앵커(id) 부여 → 커리큘럼 툴팁에서 링크로 넘어올 수 있게
   ② 각 카드에 「자세히」 접기: 더 긴 설명 + **공식 문서 링크**
   ③ 빠져 있던 용어 추가 (Isaac Gym · MuJoCo · PPO · ONNX · sm_XX 등)

  왜 필요했나. 카드가 20개인데 **외부 링크가 0개**였다.
  "더 알고 싶으면 공식 문서로" 가는 길이 없어서, 카드에서 지식이 끊겼다.

  ⚠️ 링크는 전부 2026-08-05 에 HTTP 200 + 리다이렉트 목적지까지 확인한 것만 넣었다.

  링크 점검 시 알아둘 것
    · tensorflow.org 는 curl 로 재면 302(구글 SSO 프로브)가 뜨지만 브라우저에서는 정상이다.
      끊긴 링크가 아니다. 지우지 말 것.
    · doi.org / IEEE / Semantic Scholar 는 봇 차단(202)이라 애초에 쓰지 않는다.
    · 위키는 200 만으로 부족하다. 리다이렉트 목적지를 반드시 본다 (DESIGN.md §11-3).
"""
import re

# ────────── 기존 카드에 붙일 앵커 slug ──────────
# 카드의 g1(한글/표기)을 키로 잡는다. 커리큘럼 툴팁이 이 slug 로 링크한다.
SLUGS = {
    '제로샷': 'zeroshot', '증류': 'distill', 'on-policy / off-policy': 'onpolicy',
    'GAE': 'gae', '액터–크리틱': 'actorcritic', 'TCN': 'tcn',
    'Isaac Sim vs Isaac Lab': 'isaac', 'PhysX': 'physx', 'TensorBoard': 'tensorboard',
    'rsl_rl': 'rslrl', 'sim2sim': 'sim2sim', 'URDF': 'urdf', '체크포인트': 'checkpoint',
    '준직접구동': 'qdd', 'ROS2': 'ros2', 'DDS': 'dds', 'MCF': 'mcf', 'IMU': 'imu',
    '이동 비용': 'cot', '외란': 'disturbance',
}

# ────────── 기존 카드에 덧붙일 「자세히」 ──────────
# slug → (더 긴 설명)
MORE = {
    'isaac': (
        '<b>Isaac Sim</b> 은 NVIDIA 의 로봇 시뮬레이터 본체다. 물리·렌더링·센서를 담당한다.<br>'
        '<b>Isaac Lab</b> 은 그 위에 얹는 <b>강화학습용 프레임워크</b>다. 환경 정의·병렬 실행·태스크가 여기 있다.<br>'
        'Go2 태스크(<code>Isaac-Velocity-Rough-Unitree-Go2-v0</code> 등)도 Isaac Lab 쪽에 들어 있어서, '
        '<b>Isaac Sim 만 깔면 Go2 가 자동으로 생기지 않는다.</b><br>'
        '우리는 <b>Isaac Lab v2.3.2 태그를 고정</b>해 쓴다. 기본 브랜치는 베타이고 험지를 지원하지 않는다.'),
    'physx': (
        'NVIDIA 의 물리 엔진. Isaac Sim 의 강체·접촉 계산을 담당한다.<br>'
        'Isaac Lab 에는 <b>Newton</b> 이라는 새 백엔드도 있지만 <b>험지 로코모션을 지원하지 않아</b> '
        '우리는 PhysX 를 쓴다.'),
    'rslrl': (
        'ETH 취리히 로봇시스템연구실(RSL)이 만든 강화학습 라이브러리. <b>PPO 구현체</b>다.<br>'
        '시뮬레이터에 의존하지 않아 Isaac Lab · legged_gym · MuJoCo Playground 등이 모두 이걸 쓴다.<br>'
        '우리 버전은 <b>3.1.2</b>: Isaac Lab v2.3.2 가 핀으로 고정한다.'),
    'tensorboard': (
        '학습 중 숫자를 그래프로 보여주는 도구. 보상 곡선·손실·항목별 로그를 여기서 읽는다.<br>'
        '⚠️ <b>곡선만 보면 속는다.</b> 보상이 올라도 로봇이 기어갈 수 있다. '
        '반드시 <b>영상과 함께</b> 본다 (커리큘럼 A9·A10).'),
    'urdf': (
        '로봇의 <b>몸 구조를 적어둔 파일 형식</b>. 링크(뼈대)·조인트(관절)·관성·충돌 형상이 들어 있다.<br>'
        '시뮬레이터는 이 파일을 읽어 로봇을 만든다. Isaac Sim 은 내부적으로 <b>USD</b> 로 변환해 쓴다.'),
    'ros2': (
        '로봇 소프트웨어들을 서로 이어주는 미들웨어. 노드끼리 토픽으로 메시지를 주고받는다.<br>'
        '⚠️ <b>우리 본선 경로에는 필수가 아니다.</b> 정책을 실기에 올릴 때는 '
        'Unitree SDK 로 직접 붙는 편이 더 짧다. 다만 모듈이 여러 개가 되는 시점(지도 작성 + 경로 계획 + 보행)에는 필요해진다.'),
    'dds': (
        'ROS2 밑에서 실제로 데이터를 나르는 통신 규격. Unitree 로봇도 이걸로 상태를 뿌린다.<br>'
        '⚠️ <b>네트워크 인터페이스 이름을 잘못 적으면 토픽이 아예 안 보인다.</b> '
        '에러가 안 나고 조용히 아무것도 안 오기 때문에 원인을 찾기 어렵다.'),
    'checkpoint': (
        '학습 도중 저장한 신경망 상태 파일. 여기서 이어 학습하거나, <b>학습 없이 재생만</b> 할 수 있다.<br>'
        'NVIDIA 가 Go2 험지 정책 체크포인트를 공개해 두어서, '
        '우리는 <b>첫날부터 걷는 로봇을 볼 수 있었다</b> (개발환경 구축 가이드 §6).'),
    'imu': (
        '<b>스마트폰에 든 그 센서다.</b> 폰을 기울이면 화면이 도는 것, 그게 IMU.<br>'
        '로봇이 <b>얼마나 기울었는지(자세)</b>와 <b>얼마나 빨리 도는지(각속도)</b>를 초당 500번 알려준다.<br>'
        '⚠️ <b>위치나 속도는 못 잰다.</b> 이 사실이 관측 설계 전체를 바꾼다 (커리큘럼 A12).'),
    'mcf': (
        'Unitree 가 내장한 보행 제어기. 켜져 있으면 로봇이 알아서 걷는다.<br>'
        '⚠️ <b>저수준 제어를 하려면 반드시 꺼야 한다.</b> 안 끄면 두 제어기가 동시에 살아 충돌한다.<br>'
        '그런데 <b>끄면 몸통 속도와 지형 높이맵도 함께 사라진다</b>: 그래서 우리는 그 값들 없이 걷는 정책을 만든다.'),
    'sim2sim': (
        '한 시뮬레이터에서 배운 정책을 <b>다른 시뮬레이터에서 돌려보는 것.</b><br>'
        '<b>실기에 올리기 전 마지막 관문</b>이다. 여기서 안 걸으면 하드웨어 문제가 아니라 정책·정합성 문제다.<br>'
        '선행 사례는 이 단계를 건너뛰었다가 몇 주를 잃었다 (커리큘럼 A6·A15).'),
}

# ────────── 새로 추가할 카드 ──────────
# (slug, 분류 h3, 배지종류, 배지문구, 한글/표기, 원어, 짧은 설명, 자세히)
#  ★ 링크는 여기 쓰지 않는다. 아래 LINKS 한 곳에만 쓴다
#  ★ slug 는 반드시 명시한다. 한글은 자동 slug 로 만들 수 없다
NEW = [
    ('ppo', '학습 관련', 'met', '방법론', 'PPO', 'Proximal Policy Optimization',
     '지금 사족보행 학습이 거의 전부 쓰는 알고리즘. <b>새 정책이 옛 정책에서 너무 멀리 가지 못하게 잘라내는</b> '
     '장치 하나로 학습을 안정시킨다.',
     '강화학습은 한 번에 크게 고치면 무너진다. PPO 이전에는 “얼마나 고쳐야 안 무너지나”를 매번 손으로 맞췄는데, '
     'PPO 는 그걸 <b>자동으로 제한</b>한다. 수식을 몰라도 되고 <b>“한 번에 조금씩만 고친다”</b>는 성질만 알면 된다.<br>'
     '우리가 쓰는 <code>rsl_rl</code> 이 이 알고리즘의 구현이다.'),

    ('domainrand', '학습 관련', 'met', '방법론', '도메인 랜덤화', 'domain randomization',
     '시뮬레이션 조건을 <b>매번 무작위로 흔드는 것.</b> 마찰·무게·모터 세기·지연을 판마다 바꾼다.',
     '한 가지 조건에만 맞춘 정책은 현실에서 무너진다. 여러 조건을 겪게 해 <b>강건하게</b> 만든다.<br>'
     '⚠️ <b>많이 걸수록 좋은 게 아니다.</b> 실측에서 불필요한 랜덤화를 더하자 '
     '측면 밀기 저항이 43 N → 13 N, 최고 속도가 1.1 → 0.9 m/s 로 떨어졌다.<br>'
     '<b>한 번에 하나만 넣고, 무엇을 잃었는지 적는다</b> (커리큘럼 A14.5).'),

    ('rewardhack', '학습 관련', 'met', '방법론', '보상 해킹', 'reward hacking',
     '정책이 <b>우리가 쓴 규칙의 빈틈</b>을 찾아, 원하지 않은 방식으로 점수만 올리는 것.',
     '로봇은 규칙을 어기지 않는다. <b>우리가 쓴 대로</b> 할 뿐이다. <b>우리가 원한 대로</b>가 아니라.<br>'
     '실제 사례: “발을 더 들어라” → 몸을 낮춤 · “미끄러지지 마라” → 발을 아예 안 뗌 · '
     '“덜 뜨겁게” → 오히려 더 뜨거워짐.<br>'
     '<b>지표가 결과이면 해킹당한다.</b> 원인에 벌점을 걸어야 한다 (커리큘럼 A10).'),

    ('curriculum', '학습 관련', 'met', '방법론', '커리큘럼 학습', 'curriculum learning',
     '쉬운 것부터 시작해 <b>통과하면 난이도를 올리는</b> 학습 방식.',
     '평지에서만 배우면 발을 들 이유가 없어 정책이 “발 붙이고 미끄러지기”에 갇힌다. '
     '지형을 점점 어렵게 만들면 발을 들 수밖에 없어진다.<br>'
     '통과율 <b>50~90%</b> 구간을 유지하는 것이 요령이다. 너무 쉬우면 안 배우고 너무 어려우면 포기한다.'),

    # ↓ 여기부터 6개는 강화학습의 가장 기본 낱말이다.
    #   커리큘럼 툴팁이 이 단어들을 잡는데 정작 사전에 카드가 없어서 갈 곳이 없었다.
    ('policy', '학습 관련', 'prin', '원리', '정책', 'policy',
     '<b>지금 상태를 보고 무엇을 할지 정하는 함수.</b> 우리 경우엔 신경망이다.',
     '입력은 관측(숫자 <b>42개</b>), 출력은 관절 목표 각도 <b>12개</b>.<br>'
     '“정책을 학습한다” = <b>“이 신경망의 가중치를 조정한다”</b>는 뜻이다.<br>'
     '학습이 끝나면 남는 산출물도 결국 이것 하나다. <code>.pt</code> 파일 한 개.'),

    ('reward', '학습 관련', 'prin', '원리', '보상', 'reward',
     '<b>잘했는지 못했는지를 알려주는 점수.</b> 매 순간 숫자 하나가 나온다.',
     '강화학습은 이 점수의 <b>합</b>을 최대로 만들려 한다. 그래서 <b>보상을 잘못 쓰면 엉뚱한 걸 잘하게 된다</b>.<br>'
     '⚠️ 보상은 “무엇을 원하는가”가 아니라 <b>“무엇에 점수를 주는가”</b>다. 이 차이가 '
     '<b>보상 해킹</b>을 만든다 (커리큘럼 A10).'),

    ('obs', '학습 관련', 'prin', '원리', '관측', 'observation',
     '<b>정책이 매 순간 보는 숫자들의 묶음.</b> 여기 안 들어간 정보는 정책이 절대 모른다.',
     '사람으로 치면 “지금 이 순간 내가 감지하는 모든 것”이다.<br>'
     '⚠️ 로봇은 <b>몸통 속도와 지형 높이맵을 모른다</b>(MCF 를 끄면 사라진다). '
     '그래서 관측 설계가 이 프로젝트의 급소다 (커리큘럼 A12).<br>'
     '실측 구성은 <b>47차원</b>: 명령 3 + 각속도 3 + 중력방향 3 + 관절각 12 + 관절속도 12 + '
     '직전 행동 12 + 여유 2.'),

    ('episode', '학습 관련', 'prin', '원리', '에피소드', 'episode',
     '<b>시작부터 끝까지 한 판.</b> 넘어지거나 시간이 다 되면 리셋된다.',
     '게임 한 판이라고 생각하면 된다. 학습은 이 판을 <b>수백만 번</b> 반복한다.<br>'
     '4096마리를 동시에 돌리므로, 한 번의 “업데이트”에 수천 판이 한꺼번에 들어간다.'),

    ('hparam', '학습 관련', 'prin', '원리', '하이퍼파라미터', 'hyperparameter',
     '<b>학습을 시작하기 전에 사람이 정해줘야 하는 설정값.</b> 학습률·배치 크기·에피소드 길이 같은 것들.',
     '학습으로 저절로 정해지는 값(<b>가중치</b>)과 구분된다. 가중치는 기계가 찾고, '
     '하이퍼파라미터는 <b>우리가 고른다</b>.<br>'
     '⚠️ 그래서 “왜 이 값인가”를 적어두지 않으면, 두 달 뒤 아무도 이유를 모른다.'),

    ('quat', '로봇 · 하드웨어', 'prin', '원리', '쿼터니언', 'quaternion',
     '<b>회전을 숫자 4개로 표현하는 방법.</b>',
     '각도 3개(롤·피치·요)로도 되지만, 그 방식은 특정 자세에서 축이 겹쳐 '
     '<b>계산이 무너지는 구간</b>(짐벌락)이 생긴다. 쿼터니언은 그 문제가 없다.<br>'
     '⚠️ <b>순서 규약이 도구마다 다르다.</b> <code>(w,x,y,z)</code> 와 <code>(x,y,z,w)</code> 를 '
     '섞어 쓰면 로봇이 조용히 이상하게 돈다. 에러는 안 난다.<br>'
     '뜻을 몰라도 쓸 수는 있지만, <b>순서만은 반드시 확인</b>한다.'),

    ('mujoco', '시뮬레이션 · 도구', 'tool', '도구', 'MuJoCo', 'Multi-Joint dynamics with Contact',
     '가벼운 물리 엔진. <b>CPU 로 돈다</b>: RT 코어도 큰 VRAM 도 필요 없다.',
     '우리는 <b>학습용이 아니라 검증용</b>으로 쓴다. Isaac Lab 에서 배운 정책을 '
     '실기에 올리기 전 <b>다른 엔진에서도 걷는지</b> 확인하는 자리다.<br>'
     '★ <b>GPU 가 약한 노트북에서도 돌아간다.</b> 그래서 커리큘럼 A6·A7 은 누구나 실습할 수 있다.<br>'
     '⚠️ 저자가 밝힌 한계: 속도를 위해 접촉 조건 일부를 <b>일부러 뺐고</b>, 그 결과 '
     '“떨어진 거리에서의 접촉”이 생긴다. MuJoCo 의 그 유명한 <b>말랑한 접촉</b>이 여기서 나온다.'),

    ('isaacgym', '시뮬레이션 · 도구', 'tool', '도구', 'Isaac Gym', '(legacy)',
     '<b>Isaac Lab 의 조상.</b> 물리와 학습을 둘 다 GPU 에 올린 최초의 도구.',
     '“로봇 4096마리를 GPU 한 장에서 동시에” 라는 방식이 여기서 나왔다. '
     '그 전에는 CPU 수천 코어 클러스터가 필요했다.<br>'
     '🔴 <b>우리는 쓰지 않는다.</b> NVIDIA 가 <b>legacy(지원 종료)</b> 로 지정했고 후속이 Isaac Lab 이다. '
     '게다가 RTX 50 시리즈(<code>sm_120</code>)용 커널이 없어 <b>우리 워크스테이션에서는 아예 안 돈다.</b><br>'
     '논문·블로그에서 자주 보이므로 <b>“이름은 알되 설치하지 않는다”</b>가 맞다.'),

    ('leggedgym', '시뮬레이션 · 도구', 'tool', '도구', 'legged_gym', '·',
     'ETH 가 공개한 사족보행 학습 코드. <b>지금 쓰는 방식의 원형</b>이다.',
     '“게임식 지형 커리큘럼”·“4096 병렬” 같은 개념이 여기서 나왔고 Isaac Lab 에 그대로 계승됐다.<br>'
     '🔴 <b>우리는 쓰지 않는다.</b> 저자(ETH RSL)가 <b>유지보수 축소를 공식 선언</b>했고, '
     '기반인 Isaac Gym 이 legacy 다. 게다가 Python 3.8 / PyTorch 1.10 이라는 2021년 스택에 묶인다.'),

    ('unitreerllab', '시뮬레이션 · 도구', 'tool', '도구', 'unitree_rl_lab', '·',
     'Unitree 가 공개한 <b>Go2 실기 배포 코드.</b> Isaac Lab 위에서 돈다.',
     'Isaac Lab 에는 <b>학습·재생</b>은 있어도 <b>실물 로봇에 올리는 코드</b>는 없다. 그게 여기 있다. '
     'C++ 컨트롤러 · 상태 기계 · 관절 매핑 · PD 게인 설정.<br>'
     '⚠️ <b>지금은 설치하지 않는다.</b> 실기에 올릴 때가 되면 붙인다. '
     '단 <b>Isaac Lab 2.3.x 를 요구</b>하므로 지금 v2.3.2 로 고정해 두는 것이 그때를 위한 준비다.'),

    ('onnx', '시뮬레이션 · 도구', 'tool', '도구', 'ONNX', 'Open Neural Network Exchange',
     '학습한 신경망을 <b>프레임워크에 상관없이 돌릴 수 있게</b> 만든 파일 형식.',
     '재생만 해도 <code>policy.onnx</code> 가 함께 나온다(1.1 MB). '
     '<b>Unitree 공식 실물 배포 경로가 ONNX</b> 이므로, sim2real 의 첫 단추가 이미 준비돼 있다는 뜻이다.'),

    ('arch', '로봇 · 하드웨어', 'tool', '도구', 'sm_XX · 연산 능력', 'compute capability',
     'GPU 세대를 나타내는 코드. PyTorch 가 <b>내 GPU 를 지원하는지</b>를 이걸로 판단한다.',
     'RTX 50 = <code>sm_120</code> · RTX 40 = <code>sm_89</code> · RTX 30 = <code>sm_86</code> · '
     'RTX 20 = <code>sm_75</code><br>'
     '<code>torch.cuda.get_arch_list()</code> 에 <b>내 GPU 코드가 있으면</b> 정상이다. '
     '“<code>sm_120</code> 이 있어야 한다”가 아니다. 그건 RTX 50 얘기다 (개발환경 가이드 §1.5).'),

    ('rtcore', '로봇 · 하드웨어', 'prin', '원리', 'RT 코어', 'ray tracing core',
     '빛의 경로를 계산하는 <b>전용 회로.</b> RTX 에는 있고 <b>GTX 에는 없다.</b>',
     '🔴 <b>Isaac Sim 은 RT 코어를 요구한다.</b> 그래서 GTX 계열은 드라이버나 VRAM 과 무관하게 '
     '<b>원천적으로 실행이 안 된다</b>: 하드웨어에 그 기능 자체가 없기 때문이다.<br>'
     '공식 최소 사양은 <b>RTX 4080 · VRAM 16 GB</b>. RTX 3060·4060 급도 최소 미달이다.'),

    ('torque', '로봇 · 하드웨어', 'prin', '원리', '토크', 'torque',
     '<b>돌리는 힘.</b> 미는 힘(N)과 다르다. 회전축을 중심으로 얼마나 세게 비트는가.',
     '문손잡이를 잡고 돌릴 때, 끝을 잡으면 쉽고 축 가까이를 잡으면 어렵다. 같은 힘인데 토크가 다르다. '
     '단위는 <b>N·m</b>. Go2 무릎은 <b>45.43 N·m</b> 까지 낸다.<br>'
     '⚠️ <b>Go2 에는 토크 센서가 없다.</b> 우리가 읽는 값은 <b>모터 전류로 추정한 것</b>이라 '
     '실제 토크와 오차가 있다. 보고서에는 “추정 토크”라고 적는다.'),

    ('dof', '로봇 · 하드웨어', 'prin', '원리', 'DOF · 자유도', 'degree of freedom',
     '독립적으로 움직일 수 있는 <b>방향의 개수.</b>',
     '문은 경첩 하나로 열리니 1자유도, 사람 어깨는 앞뒤·좌우·회전이 되니 3자유도다.<br>'
     'Go2 는 다리 4개 × 관절 3개 = <b>12 자유도</b>. '
     '참고로 Go2-W(바퀴형)는 12 관절 + 바퀴 4개 = <b>16 자유도</b>다.'),
]


# ══════════════════ 출처 등급 · 링크 표 ══════════════════
#
#  이 분야에는 위키피디아 같은 **단일 정본이 없다.** 그 역할을 하던
#  Papers with Code 의 Methods 백과는 2025-07-24 에 폐쇄됐고,
#  후속(Hugging Face Trending Papers)은 용어 백과가 아니라 논문 피드다.
#
#  그래서 "한 사이트로 통일"이 아니라 **등급으로 통일**한다.
#  링크마다 아래 다섯 중 하나를 붙여, 읽는 사람이 **정본인지 해설인지 알고 읽게** 한다.
#  (우리는 이미 블로그 수치를 논문 수치로 착각한 적이 있다.)
#
#  적용 순서: 위에서부터 있는 것을 쓴다
#    공식 → 교재 → 논문 → 해설 → 백과
#
TIER = {
    'off':  ('off',  '공식'),   # 그 도구·규격을 만든 곳의 문서. 버전이 바뀌면 여기가 먼저 바뀐다
    'book': ('book', '교재'),   # 표준 교재·강의의 무료 공개본. 개념이 흔들리지 않는다
    'pap':  ('pap',  '논문'),   # arXiv abs 영구링크. 숫자를 인용할 때는 반드시 여기
    'exp':  ('exp',  '해설'),   # 정평 난 해설(Spinning Up · Lil'Log). 빠르지만 정본은 아니다
    'wiki': ('wiki', '백과'),   # 영문 위키피디아. 물리·수학 일반 용어에만
}

# 무료로 공개된 표준 교재: 사전 머리말에서 "더 깊이"로 안내한다
SHELF = [
    ('book', 'Sutton &amp; Barto · 강화학습 교과서 (2판 전문 PDF)',
     'http://incompleteideas.net/book/RLbook2020.pdf'),
    ('book', 'Modern Robotics · 로봇 기구학 교과서 (전문 PDF)',
     'https://hades.mech.northwestern.edu/images/7/7f/MR.pdf'),
    ('book', 'Underactuated Robotics · MIT 6.832 (보행 로봇 강의)',
     'https://underactuated.mit.edu/'),
    ('exp',  'OpenAI Spinning Up · 강화학습 입문',
     'https://spinningup.openai.com/en/latest/spinningup/rl_intro.html'),
]

# slug → [(등급, 문구, URL), ...]      ★ 링크는 전부 여기에만 쓴다
# 전 항목 2026-08-05 HTTP 200 실측. 위키는 리다이렉트 여부까지 확인했다.
LINKS = {
    # ── 학습 관련 ──────────────────────────────────────────
    'zeroshot': [
        ('wiki', 'Zero-shot learning', 'https://en.wikipedia.org/wiki/Zero-shot_learning'),
        ('pap', '시뮬 학습→실기 직행 사례 (Rudin, CoRL 2021)', 'https://arxiv.org/abs/2109.11978')],
    'distill': [
        ('pap', '원전 · Hinton 2015', 'https://arxiv.org/abs/1503.02531'),
        ('wiki', 'Knowledge distillation', 'https://en.wikipedia.org/wiki/Knowledge_distillation')],
    'onpolicy': [
        ('book', 'Sutton &amp; Barto 5.4~5.7절 (PDF)', 'http://incompleteideas.net/book/RLbook2020.pdf'),
        ('exp', 'Spinning Up · 알고리즘 분류',
         'https://spinningup.openai.com/en/latest/spinningup/rl_intro2.html')],
    'gae': [
        ('pap', '원전 · Schulman 2015', 'https://arxiv.org/abs/1506.02438'),
        ('exp', 'Spinning Up · 정책경사 (VPG)',
         'https://spinningup.openai.com/en/latest/algorithms/vpg.html')],
    'actorcritic': [
        ('book', 'Sutton &amp; Barto 13장 (PDF)', 'http://incompleteideas.net/book/RLbook2020.pdf'),
        ('exp', 'Spinning Up · VPG', 'https://spinningup.openai.com/en/latest/algorithms/vpg.html'),
        ('wiki', 'Actor-critic algorithm', 'https://en.wikipedia.org/wiki/Actor-critic_algorithm')],
    'tcn': [
        ('pap', '원전 · Bai 2018 (위키 문서는 없다)', 'https://arxiv.org/abs/1803.01271')],
    'ppo': [
        ('pap', '원 논문 · Schulman 2017', 'https://arxiv.org/abs/1707.06347'),
        ('exp', 'Spinning Up · PPO', 'https://spinningup.openai.com/en/latest/algorithms/ppo.html'),
        ('wiki', 'Proximal policy optimization',
         'https://en.wikipedia.org/wiki/Proximal_policy_optimization')],
    'domainrand': [
        ('pap', '원전 · Tobin 2017 (IROS)', 'https://arxiv.org/abs/1703.06907'),
        ('pap', '재검토 · Dynamics Randomization Revisited (ICRA 2021)',
         'https://arxiv.org/abs/2011.02404'),
        ('exp', 'Lil’Log · Domain Randomization 총정리',
         'https://lilianweng.github.io/posts/2019-05-05-domain-randomization/')],
    'rewardhack': [
        ('exp', 'Lil’Log · Reward Hacking 총정리',
         'https://lilianweng.github.io/posts/2024-11-28-reward-hacking/'),
        ('wiki', 'Reward hacking', 'https://en.wikipedia.org/wiki/Reward_hacking')],
    'curriculum': [
        ('wiki', 'Curriculum learning', 'https://en.wikipedia.org/wiki/Curriculum_learning'),
        ('pap', '지형 커리큘럼 실제 적용 (Rudin, CoRL 2021)', 'https://arxiv.org/abs/2109.11978')],

    'policy': [
        ('exp', 'Spinning Up · 핵심 개념 (정책·상태·행동)',
         'https://spinningup.openai.com/en/latest/spinningup/rl_intro.html'),
        ('book', 'Sutton &amp; Barto 3장 · 유한 MDP (PDF)',
         'http://incompleteideas.net/book/RLbook2020.pdf')],
    'reward': [
        ('book', 'Sutton &amp; Barto 3.2절 · 보상 가설 (PDF)',
         'http://incompleteideas.net/book/RLbook2020.pdf'),
        ('wiki', 'Markov decision process', 'https://en.wikipedia.org/wiki/Markov_decision_process')],
    'obs': [
        ('exp', 'Spinning Up · 상태와 관측',
         'https://spinningup.openai.com/en/latest/spinningup/rl_intro.html'),
        ('off', 'Isaac Lab · 관측을 정의하는 자리 (Manager 기반 환경)',
         'https://isaac-sim.github.io/IsaacLab/main/source/tutorials/03_envs/create_manager_rl_env.html')],
    'episode': [
        ('exp', 'Spinning Up · 궤적과 에피소드',
         'https://spinningup.openai.com/en/latest/spinningup/rl_intro.html'),
        ('wiki', 'Reinforcement learning', 'https://en.wikipedia.org/wiki/Reinforcement_learning')],
    'hparam': [
        ('wiki', 'Hyperparameter (machine learning)',
         'https://en.wikipedia.org/wiki/Hyperparameter_(machine_learning)')],
    'quat': [
        ('wiki', 'Quaternions and spatial rotation',
         'https://en.wikipedia.org/wiki/Quaternions_and_spatial_rotation'),
        ('book', 'Modern Robotics 3장 · 강체 운동 (PDF)',
         'https://hades.mech.northwestern.edu/images/7/7f/MR.pdf')],

    # ── 시뮬레이션 · 도구 ──────────────────────────────────
    'isaac': [
        ('off', 'Isaac Sim 문서', 'https://docs.isaacsim.omniverse.nvidia.com/latest/index.html'),
        ('off', 'Isaac Lab 문서', 'https://isaac-sim.github.io/IsaacLab/main/index.html'),
        ('off', 'Isaac Lab GitHub', 'https://github.com/isaac-sim/IsaacLab'),
        ('off', '제공 태스크 목록',
         'https://isaac-sim.github.io/IsaacLab/main/source/overview/environments.html'),
        ('off', '학습 스크립트 사용법',
         'https://isaac-sim.github.io/IsaacLab/main/source/overview/reinforcement-learning/rl_existing_scripts.html')],
    'physx': [
        ('off', 'PhysX SDK', 'https://developer.nvidia.com/physx-sdk')],
    'tensorboard': [
        ('off', 'TensorBoard 문서', 'https://www.tensorflow.org/tensorboard')],
    'rslrl': [
        ('off', 'rsl_rl GitHub', 'https://github.com/leggedrobotics/rsl_rl'),
        ('pap', 'PPO 원 논문', 'https://arxiv.org/abs/1707.06347'),
        ('exp', 'Spinning Up · PPO', 'https://spinningup.openai.com/en/latest/algorithms/ppo.html')],
    'sim2sim': [
        ('off', 'MuJoCo 문서', 'https://mujoco.readthedocs.io/en/stable/overview.html')],
    'urdf': [
        ('off', 'URDF 규격 (ROS)', 'https://wiki.ros.org/urdf')],
    'checkpoint': [
        ('off', 'Go2 험지 사전학습 체크포인트 (NVIDIA S3)',
         'https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/IsaacLab/PretrainedCheckpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt')],
    'mujoco': [
        ('off', 'MuJoCo 문서', 'https://mujoco.readthedocs.io/en/stable/overview.html'),
        ('off', '접촉·적분 계산 방식 (저자가 밝힌 한계)',
         'https://mujoco.readthedocs.io/en/stable/computation/index.html'),
        ('off', 'MuJoCo GitHub', 'https://github.com/google-deepmind/mujoco'),
        ('wiki', 'MuJoCo', 'https://en.wikipedia.org/wiki/MuJoCo')],
    'isaacgym': [
        ('off', 'Isaac Gym (legacy) 안내', 'https://developer.nvidia.com/isaac-gym'),
        ('pap', 'Isaac Gym 논문 (NeurIPS 2021 Datasets)', 'https://arxiv.org/abs/2108.10470'),
        ('off', '후속 · Isaac Lab', 'https://isaac-sim.github.io/IsaacLab/main/index.html')],
    'leggedgym': [
        ('off', 'legged_gym GitHub', 'https://github.com/leggedrobotics/legged_gym'),
        ('pap', '이 코드가 나온 논문 (Rudin, CoRL 2021)', 'https://arxiv.org/abs/2109.11978')],
    'unitreerllab': [
        ('off', 'unitree_rl_lab GitHub', 'https://github.com/unitreerobotics/unitree_rl_lab')],
    'onnx': [
        ('off', 'ONNX 공식', 'https://onnx.ai/'),
        ('wiki', 'Open Neural Network Exchange',
         'https://en.wikipedia.org/wiki/Open_Neural_Network_Exchange')],

    # ── 로봇 · 하드웨어 ────────────────────────────────────
    'qdd': [
        ('pap', 'QDD 모터 선정 기준 (오픈액세스)', 'https://arxiv.org/abs/2202.12365'),
        ('off', 'MIT Biomimetics · 이 방식을 만든 연구실', 'https://biomimetics.mit.edu/')],
    'ros2': [
        ('off', 'ROS 2 문서 (Humble)', 'https://docs.ros.org/en/humble/index.html')],
    'dds': [
        ('off', 'CycloneDDS', 'https://cyclonedds.io/'),
        ('off', 'unitree_sdk2', 'https://github.com/unitreerobotics/unitree_sdk2')],
    'mcf': [
        ('off', 'Unitree · 기본 운동 제어 (끄는 방법이 여기 있다)',
         'https://support.unitree.com/home/en/developer/Basic_motion_control')],
    'imu': [
        ('wiki', 'Inertial measurement unit',
         'https://en.wikipedia.org/wiki/Inertial_measurement_unit')],
    'cot': [
        ('wiki', 'Cost of transport', 'https://en.wikipedia.org/wiki/Cost_of_transport')],
    'disturbance': [
        ('wiki', 'Robust control · 외란을 견디는 제어',
         'https://en.wikipedia.org/wiki/Robust_control')],
    'arch': [
        ('off', 'NVIDIA · GPU별 연산 능력 표', 'https://developer.nvidia.com/cuda-gpus'),
        ('wiki', 'CUDA', 'https://en.wikipedia.org/wiki/CUDA')],
    'rtcore': [
        ('off', 'Isaac Sim 요구 사양',
         'https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html')],
    'torque': [
        ('wiki', 'Torque', 'https://en.wikipedia.org/wiki/Torque'),
        ('book', 'Modern Robotics · 힘과 토크 (PDF)',
         'https://hades.mech.northwestern.edu/images/7/7f/MR.pdf')],
    'dof': [
        ('wiki', 'Degrees of freedom (mechanics)',
         'https://en.wikipedia.org/wiki/Degrees_of_freedom_(mechanics)'),
        ('book', 'Modern Robotics 2장 · 배치 공간 (PDF)',
         'https://hades.mech.northwestern.edu/images/7/7f/MR.pdf'),
        ('off', 'Unitree Go2 제품 사양', 'https://www.unitree.com/go2')],
}


# 사전 머리말에 넣을 「링크 읽는 법」: 등급 뜻 + 무료 교재 + 죽은 출처 경고
def _shelf():
    tiers = ''.join(
        '<span class="lkt lk-%s">%s</span> %s<br>' % (TIER[k][0], TIER[k][1], d)
        for k, d in [
            ('off',  '그 도구를 <b>만든 곳</b>의 문서. 버전이 바뀌면 여기가 먼저 바뀐다.'),
            ('book', '표준 <b>교재·강의</b>의 무료 공개본. 개념이 흔들리지 않는다.'),
            ('pap',  '<b>논문 원전</b>(arXiv 영구링크). <b>숫자를 인용할 땐 반드시 여기.</b>'),
            ('exp',  '정평 난 <b>해설</b>. 이해는 가장 빠르지만 <b>정본은 아니다.</b>'),
            ('wiki', '영문 <b>위키피디아</b>. 물리·수학 일반 용어에만 붙였다.'),
        ])
    shelf = ''.join('<a class="lk-%s" href="%s" target="_blank" rel="noopener">'
                    '<span class="lkt">%s</span>%s</a>' % (TIER[t][0], u, TIER[t][1], txt)
                    for t, txt, u in SHELF)
    return (
        '\n  <div class="key gkey">\n'
        '    <div class="kl">링크 읽는 법. <b>이 분야엔 위키피디아 같은 단일 정본이 없다</b></div>\n'
        '    <p style="font-size:.78rem;line-height:1.85">%s</p>\n'
        '    <p style="font-size:.75rem;margin-top:.5rem;color:var(--ink-3)">'
        '⚠️ 그래서 <b>한 사이트로 통일하지 않고 등급으로 통일</b>했다. '
        'ML 용어 백과 노릇을 하던 <b>Papers with Code 는 2025년 7월 폐쇄</b>됐고(옛 링크는 전부 죽었다), '
        '위키피디아에는 <b>“domain randomization” 문서가 없다</b>: 검색하면 뜻이 다른 '
        '<i>domain adaptation</i> 으로 넘어가니 주의.</p>\n'
        '    <div class="kl" style="margin-top:.8rem">더 깊이: 전부 무료 공개본</div>\n'
        '    <div class="glinks">%s</div>\n'
        '  </div>\n' % (tiers, shelf))


CSS = r"""
/* ═══ 용어 사전 보강 ═══ */
.gt{scroll-margin-top:70px;position:relative}
.gt:target{outline:2px solid var(--dim);outline-offset:6px;background:var(--dim-soft)}
.gt .gmore{margin-top:.5rem;border-top:1px dashed var(--rule);padding-top:.45rem}
.gt .gmore summary{cursor:pointer;font-size:.7rem;font-weight:800;letter-spacing:.06em;
  color:var(--dim);list-style:none;display:inline-flex;align-items:center;gap:.3rem}
.gt .gmore summary::-webkit-details-marker{display:none}
.gt .gmore summary::before{content:'▸';transition:transform .16s;display:inline-block}
.gt .gmore[open] summary::before{transform:rotate(90deg)}
.gt .gmore .gbody{margin-top:.45rem;font-size:.78rem;line-height:1.7;color:var(--ink-2)}
.gt .gmore .gbody b{color:var(--ink)}
/* 링크 칩: 앞머리에 출처 등급 배지를 단다 */
.glinks{margin-top:.5rem;display:flex;flex-wrap:wrap;gap:.35rem}
.glinks a{display:inline-flex;align-items:center;gap:.32rem;font-size:.68rem;font-weight:700;
  color:var(--ink-2);text-decoration:none;border:1px solid var(--rule);background:var(--card);
  padding:.16rem .45rem .16rem .2rem;border-radius:3px;transition:.14s;line-height:1.5}
.glinks a:hover{border-color:var(--ink-3);color:var(--ink)}
.glinks a::after{content:'↗';opacity:.45;font-weight:400}
.lkt{display:inline-block;font-size:.6rem;font-weight:800;letter-spacing:.04em;color:#fff;
  padding:.1rem .3rem;border-radius:2px;line-height:1.4;white-space:nowrap}
.lk-off  .lkt,.lkt.lk-off {background:#1b6b4a}   /* 공식 */
.lk-book .lkt,.lkt.lk-book{background:#1f4e79}   /* 교재 */
.lk-pap  .lkt,.lkt.lk-pap {background:#6b2d5c}   /* 논문 */
.lk-exp  .lkt,.lkt.lk-exp {background:#8a5a00}   /* 해설 */
.lk-wiki .lkt,.lkt.lk-wiki{background:#5a5a5a}   /* 백과 */
.gkey .lkt{margin-right:.15rem}
.gkey p b{color:var(--ink)}

@media print{
  /* ★ 접힌 <details> 는 자식에 display:block 을 줘도 안 열린다.
     크롬은 접힌 내용을 ::details-content 에 content-visibility:hidden 으로 감춘다.
     그래서 아래 CSS 와 함께 PRINT_JS 가 인쇄 직전 open 을 실제로 켠다. 둘 다 필요하다. */
  .gt .gmore{display:block!important}
  .gt .gmore>.gbody,.gt .gmore>.glinks{display:block!important}
  .gt .gmore::details-content{content-visibility:visible!important;opacity:1!important;
    block-size:auto!important;height:auto!important}
  .gt .gmore>summary{color:var(--ink-3)}
  /* 종이에서는 클릭이 안 되니 주소를 그대로 찍는다 */
  .glinks a::after{content:' ' attr(href);font-size:.82em;color:#666;word-break:break-all;opacity:1}
  .lkt{color:#000!important;background:none!important;border:1px solid #999;padding:0 .2rem}
}
@media (max-width:700px){
  /* 손가락으로 누르는 링크다. 24px 은 너무 작아서 옆 칩을 잘못 누른다.
     세로 여백을 키워 32px 이상 확보하고, 글자도 11px 아래로는 내리지 않는다. */
  .glinks{gap:.42rem}
  .glinks a{font-size:.7rem;max-width:100%;padding:.34rem .5rem .34rem .26rem}
  .lkt{font-size:.62rem}
}
"""


def _links(slug):
    items = LINKS.get(slug, [])
    if not items:
        return ''
    return ('<div class="glinks">' + ''.join(
        '<a class="lk-%s" href="%s" target="_blank" rel="noopener">'
        '<span class="lkt">%s</span>%s</a>' % (TIER[t][0], u, TIER[t][1], txt)
        for t, txt, u in items) + '</div>')


def _more(slug, body):
    links = _links(slug)
    if not body and not links:
        return ''
    return ('<details class="gmore"><summary>자세히</summary>'
            '<div class="gbody">%s</div>%s</details>' % (body, links))


def enrich(html):
    """기존 카드에 앵커·자세히를 붙이고, 새 카드를 추가한다."""
    added_anchor, added_more = 0, 0

    def fix(m):
        nonlocal added_anchor, added_more
        whole, g1, inner = m.group(0), m.group(2), m.group(3)
        slug = SLUGS.get(g1.strip())
        if not slug:
            return whole
        added_anchor += 1
        extra = ''
        if slug in MORE or slug in LINKS:
            extra = _more(slug, MORE.get(slug, ''))
            added_more += 1
        return ('<div class="gt" id="t-%s">%s%s</div>' % (slug, inner, extra))

    html = re.sub(r'<div class="gt">((?:(?!</div>\s*<div class="gt")[\s\S])*?<div class="g1">([^<]*)</div>'
                  r'[\s\S]*?)</div>\s*(?=<div class="gt"|</div>)',
                  lambda m: m.group(0), html)  # 구조 확인용 no-op

    # 카드 단위로 정확히 자른다 (gt 는 중첩되지 않는다)
    out, i, n = [], 0, len(html)
    while True:
        a = html.find('<div class="gt">', i)
        if a < 0:
            out.append(html[i:]); break
        out.append(html[i:a])
        d, j = 0, a
        while True:
            mm = re.compile(r'<(/?)div\b[^>]*>').search(html, j)
            if not mm:
                break
            d += -1 if mm.group(1) else 1
            j = mm.end()
            if d == 0:
                break
        card = html[a:j]
        g1 = re.search(r'<div class="g1">([^<]*)</div>', card)
        slug = SLUGS.get(g1.group(1).strip()) if g1 else None
        if slug:
            added_anchor += 1
            inner = card[len('<div class="gt">'):-len('</div>')]
            extra = ''
            if slug in MORE or slug in LINKS:
                extra = _more(slug, MORE.get(slug, ''))
                added_more += 1
            card = '<div class="gt" id="t-%s">%s%s</div>' % (slug, inner, extra)
        out.append(card)
        i = j
    html = ''.join(out)

    # ── 새 카드 추가: 각 h3 섹션의 .gloss 끝에 붙인다 ──
    added_new = 0
    for slug, h3, kind, badge, g1, g2, short, body in NEW:
        card = ('\n  <div class="gt" id="t-%s"><div class="kind %s">%s</div>'
                '<div class="g1">%s</div><div class="g2">%s</div>\n'
                '  <div class="g3">%s</div>%s</div>' % (slug, kind, badge, g1, g2, short, _more(slug, body)))
        # 해당 h3 뒤 첫 .gloss 블록의 끝을 찾는다
        hm = re.search(r'<h3>%s</h3>\s*<div class="gloss">' % re.escape(h3), html)
        if not hm:
            print('  [!] 용어 분류 못 찾음: %s' % h3)
            continue
        d, j = 1, hm.end()
        while d > 0:
            mm = re.compile(r'<(/?)div\b[^>]*>').search(html, j)
            if not mm:
                break
            d += -1 if mm.group(1) else 1
            j = mm.end()
        close = j - len('</div>')
        html = html[:close] + card + '\n  ' + html[close:]
        added_new += 1

    orphan = sorted(set(LINKS) - set(SLUGS.values()) - {n[0] for n in NEW})
    if orphan:
        raise SystemExit('[!] LINKS 에 있으나 카드가 없는 용어: %s' % ', '.join(orphan))

    # ── 사전 머리말에 「링크 읽는 법」 삽입 (첫 h3 바로 앞) ──
    gs = html.find('id="glossary"')
    h3 = html.find('<h3>', gs)
    if gs < 0 or h3 < 0:
        raise SystemExit('[!] 용어 사전 섹션을 못 찾음')
    html = html[:h3] + _shelf() + '  ' + html[h3:]

    nlink = sum(len(v) for v in LINKS.values())
    print('용어 사전  : 앵커 %d · 자세히 %d · 신규 %d개 · 링크 %d개(%d항목)'
          % (added_anchor, added_more, added_new, nlink, len(LINKS)))
    return html


PRINT_JS = r"""
<script>
/* 인쇄 직전 「자세히」를 전부 펼친다.
   CSS 만으로는 안 된다. 접힌 <details> 의 내용은 ::details-content 에
   content-visibility:hidden 으로 감춰져 있어서, 자식 display 를 바꿔도 종이에 안 찍힌다.
   (그래서 초판 PDF 에는 링크 79개 중 26개만 나왔다.)
   인쇄가 끝나면 우리가 연 것만 도로 접는다. 사용자가 직접 편 것은 건드리지 않는다. */
(function () {
  var SEL = 'details.gmore';
  function openAll() {
    document.querySelectorAll(SEL).forEach(function (d) {
      if (!d.open) { d.open = true; d.setAttribute('data-auto-open', '1'); }
    });
  }
  function restore() {
    document.querySelectorAll(SEL + '[data-auto-open]').forEach(function (d) {
      d.open = false; d.removeAttribute('data-auto-open');
    });
  }
  window.addEventListener('beforeprint', openAll);
  window.addEventListener('afterprint', restore);
  if (window.matchMedia) {                    /* 헤드리스 인쇄는 beforeprint 를 안 쏠 수 있다 */
    var m = window.matchMedia('print');
    var on = function (e) { e.matches ? openAll() : restore(); };
    if (m.addEventListener) m.addEventListener('change', on);
    else if (m.addListener) m.addListener(on);
    if (m.matches) openAll();
  }
})();
</script>
"""


def apply(html):
    html = enrich(html)
    if '</style>' in html and '.gt .glinks' not in html:
        html = html.replace('</style>', CSS + '\n</style>', 1)
    if '</body>' in html and 'data-auto-open' not in html:
        html = html.replace('</body>', PRINT_JS + '</body>', 1)
    return html
