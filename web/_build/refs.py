# -*- coding: utf-8 -*-
"""논문 카드: 링크만 걸면 아무도 안 읽는다. 우리말 해설을 먼저 보여주고 원문으로 보낸다.

  구조: 한 문장 요약 → 왜 중요한가 → 핵심 수치 → 우리와의 관계 → 한계
  ⚠️ 수치는 원문에서 확인한 것만 넣는다. 확인 못 한 값은 아예 쓰지 않는다.
"""


def paper(pid, title, meta, url, one, why, nums, ours, limit=None, tag='논문'):
    """논문 카드 한 장. nums = [(항목, 값), ...]"""
    rows = ''.join(
        '<div class="pn-r"><span class="pn-k">%s</span><span class="pn-v">%s</span></div>' % (k, v)
        for k, v in nums)
    lim = ('<div class="p-lim"><span class="p-lk">한계</span>%s</div>' % limit) if limit else ''
    return f'''
<aside class="pref" id="ref-{pid}">
  <div class="p-top">
    <span class="p-tag">{tag}</span>
    <a class="p-title" href="{url}" target="_blank" rel="noopener">{title} <span class="p-ext">↗</span></a>
  </div>
  <div class="p-meta">{meta}</div>
  <p class="p-one">{one}</p>
  <div class="p-grid">
    <div class="p-why"><div class="p-h">왜 중요한가</div><p>{why}</p></div>
    <div class="p-num"><div class="p-h">논문이 보고한 숫자</div>{rows}</div>
  </div>
  <div class="p-ours"><span class="p-ok">우리와의 관계</span>{ours}</div>
  {lim}
</aside>
'''


# ══════════════════════════════════════════════════════════════
#  이 세션에서 원문 확인을 마친 것만 우선 수록. 나머지는 조사 결과로 채운다.
# ══════════════════════════════════════════════════════════════

PPO = paper(
    'ppo',
    'Proximal Policy Optimization Algorithms',
    'Schulman, Wolski, Dhariwal, Radford, Klimov · OpenAI · 2017',
    'https://arxiv.org/abs/1707.06347',
    '“새 정책이 옛 정책에서 <b>너무 멀리 가지 못하게 잘라내는</b>” 한 가지 장치로 학습을 안정시킨 방법입니다. '
    '지금 사족보행 학습은 거의 전부 이걸 씁니다.',
    '강화학습은 한 번에 크게 고치면 무너집니다. PPO 이전에는 "얼마나 고쳐야 안 무너지나"를 매번 손으로 맞췄는데, '
    'PPO는 그걸 <b>자동으로 제한</b>합니다. 우리가 쓰는 rsl_rl 도 PPO 구현입니다.',
    [('클리핑 폭 ε', '0.2'),
     ('클리핑 없앴을 때 점수', '-0.39'),
     ('ε=0.2 일 때 점수', '0.82'),
     ('알고리즘 계열', 'on-policy')],
    '<b>우리가 그대로 씁니다.</b> A8에서 개념을, A13에서 설정값을 봅니다. '
    '수식을 이해할 필요는 없고 <b>“한 번에 조금씩만 고친다”</b>는 성질만 알면 됩니다.',
    'on-policy 라 데이터를 많이 먹습니다. 그래서 실물이 아니라 <b>시뮬레이터가 필요</b>합니다.')


WALK_MIN = paper(
    'walk-minutes',
    'Learning to Walk in Minutes Using Massively Parallel Deep RL',
    'Rudin, Hoeller, Reist, Hutter · ETH Zurich · CoRL 2021',
    'https://arxiv.org/abs/2109.11978',
    '로봇 수천 마리를 <b>GPU 한 장 안에서 동시에</b> 걷게 해, 며칠 걸리던 학습을 분 단위로 줄였습니다.',
    '이 논문이 없었으면 우리 프로젝트는 5개월 안에 불가능했습니다. '
    '<b>우리 파이프라인의 개념적 뿌리</b>입니다. 다만 실행 스택은 legged_gym 이 아니라 <b>Isaac Lab</b> 입니다. '
    'legged_gym 은 저자(ETH RSL)가 유지보수 축소를 공식 선언했고, 기반인 Isaac Gym Preview 도 NVIDIA 가 legacy 로 지정했습니다. '
    '이 논문의 “게임식 지형 커리큘럼”은 Isaac Lab 에 그대로 계승돼 개념은 100% 유효합니다.',
    [('평지 정책 학습', '4분 미만'),
     ('험지 정책 학습', '약 20분'),
     ('병렬 로봇 수', '4096'),
     ('업데이트 횟수', '1500회'),
     ('필요 장비', 'RTX A6000 1장'),
     ('하드웨어 배포 속도 제한', '0.6 m/s')],
    '<b>우리 파이프라인의 뿌리입니다.</b> A9에서 첫 학습을 돌릴 때 이 구조 위에서 돕니다.',
    '저자들은 <b>실기 이관까지 했습니다.</b> 다만 지형 높이맵이 불완전해 시뮬↔실기 강건성이 떨어졌고, '
    '그래서 <b>하드웨어에서는 최고 명령속도를 0.6 m/s 로 낮춰</b> 돌렸다고 밝힙니다. '
    '“가장 강건한 정책을 얻는 것이 이 연구의 목적이 아니다”라고 스스로 범위를 좁힙니다. (A16 안전 절차와 직결)')


RMA = paper(
    'rma',
    'RMA: Rapid Motor Adaptation for Legged Robots',
    'Kumar, Fu, Pathak, Malik · UC Berkeley / CMU · RSS 2021',
    'https://arxiv.org/abs/2107.04034',
    '로봇이 <b>지금 밟고 있는 땅이 어떤 땅인지</b>를 최근 움직임만 보고 짐작해, 1초도 안 되어 걸음을 바꾸는 방법입니다.',
    '<b>우리 주제("미경험 지형 적응")의 직계 조상</b>입니다. '
    '지면 물성을 <b>측정할 수 없다</b>는 A12의 급소를 정면으로 다룬 최초의 실용적 답입니다.',
    [('시뮬 성공률 (적응 있음)', '73.5%'),
     ('시뮬 성공률 (적응 제거)', '52.1%'),
     ('적응 소요 시간', '1초 미만'),
     ('적응 모듈 / 기저 정책', '10 Hz / 100 Hz'),
     ('실기: 메모리폼·굴곡 폼', '100%'),
     ('실기: 15 cm 단차 내려서기', '80%')],
    '<b>우리가 참고하는 핵심 구조</b>입니다. A12를 읽은 직후에 보면 "왜 이런 걸 만들었나"가 바로 이해됩니다.',
    '저자 스스로 <b>눈이 없는 한계</b>를 명시합니다. 계단을 내려가다 크게 흔들리는 것 같은 큰 외란에서는 실패하고, '
    '믿을 만한 보행 로봇을 만들려면 결국 <b>온보드 시각이 필요</b>하다고 씁니다. '
    '또 2단계(선생–학생) 학습이라 파이프라인이 깁니다. 뒤에 나온 DreamWaQ 가 이걸 한 단계로 줄였습니다.')


DREAMWAQ = paper(
    'dreamwaq',
    'DreamWaQ: Learning Robust Quadrupedal Locomotion With Implicit Terrain Imagination',
    'Nahrendra, Yu, Myung · KAIST · ICRA 2023',
    'https://arxiv.org/abs/2301.10602',
    '지형을 <b>보지 않고</b>(카메라·라이다 없이) 다리 감각만으로 땅을 상상하게 만든 방법입니다. '
    '선생–학생 2단계를 <b>한 단계로</b> 줄였습니다.',
    '우리는 카메라·라이다를 정책 입력으로 쓰지 않기로 했습니다(A12 참조). '
    '<b>그 결정이 가능하다는 근거가 이 논문</b>입니다. 한국(KAIST) 연구라 자료 접근도 수월합니다.',
    [('외란 생존율 (DreamWaQ)', '95.23%'),
     ('외란 생존율 (비교군)', '20.51%'),
     ('견딘 충격 속도', '1.121 m/s (비교군 0.511)'),
     ('야외 코스 완주', '430 m')],
    '<b>우리가 채택한 구조의 원본입니다.</b> 구간 B·POLICY 에서 정독합니다.',
    '저자 자인: 적응이 <b>다리로 장애물을 먼저 때려봐야</b> 작동합니다. '
    '부딪히기 전에 미리 걸음을 계획하려면 결국 카메라·라이다 통합이 필요하다고 명시합니다.<br>'
    '⚠️ KAIST 공식 구현 공개는 확인되지 않습니다. 유통되는 것은 커뮤니티 재구현입니다.')


PARKOUR = paper(
    'parkour',
    'Extreme Parkour with Legged Robots',
    'Cheng, Shi, Agarwal, Pathak · CMU · ICRA 2024',
    'https://arxiv.org/abs/2309.14341',
    '작은 로봇개가 <b>자기 키의 두 배</b> 높이를 뛰어오르고 넓은 틈을 건너뛰게 만든 연구입니다.',
    '“사족보행이 어디까지 갈 수 있나”의 현재 상한선입니다. '
    '우리 목표(모래·자갈 적응)와는 방향이 다르지만, <b>보상 설계가 얼마나 결과를 바꾸는지</b>를 보여주는 사례로 A10에서 봅니다.',
    [('점프 높이', '0.5 m (고관절 높이 26 cm 의 2배)'),
     ('건넌 틈 길이', '0.8 m (몸길이 40 cm 의 2배)'),
     ('오른 경사', '37°'),
     ('카메라', 'RealSense D435 · 10 Hz')],
    '<b>참고만 합니다.</b> 우리가 이걸 재현하려 하면 5개월이 부족합니다. A16 「자르는 순서」에서 제일 먼저 잘리는 축입니다.',
    '전방 카메라(시각)를 씁니다. <b>우리 blind 경로와는 전제가 다릅니다.</b>')


WILD = paper(
    'wild',
    'Learning robust perceptive locomotion for quadrupedal robots in the wild',
    'Miki, Lee, Hwangbo, Wellhausen, Koltun, Hutter · ETH / Intel · Science Robotics 2022',
    'https://www.science.org/doi/10.1126/scirobotics.abk2822',
    '지형을 보는 눈(라이다)과 다리 감각을 <b>섞어서</b>, 눈이 틀렸을 때 다리 감각으로 되돌아가게 만든 연구입니다.',
    '“센서를 믿을 수 없을 때 어떻게 하나”의 모범 답안입니다. '
    '실험실이 아니라 <b>실제 산과 지하</b>에서 검증했다는 점이 중요합니다.',
    [('알프스 등반', '2.2 km · 고도 120 m · 31분'),
     ('참고: 사람 권장 시간', '35분'),
     ('DARPA SubT 지하 탐사', '1,700 m 무낙상')],
    '<b>우리 평가 기준의 참고점</b>입니다. A15 「무엇을 성공이라 부를 것인가」에서 이 논문의 지표 설계를 봅니다.',
    'ANYmal(수억 원대)과 고성능 라이다 기준입니다. <b>Go2 체급에 그대로 오지 않습니다.</b>')


# ─────── A14 본문의 무출처 수치 2건(43N→22N, 1.1→0.9 m/s)의 원 논문 ───────
DR_REVISIT = paper(
    'dr-revisit',
    'Dynamics Randomization Revisited: A Case Study for Quadrupedal Locomotion',
    'Xie, Da, van de Panne, Babich, Garg · ICRA 2021',
    'https://arxiv.org/abs/2011.02404',
    '“도메인 랜덤화는 많이 걸수록 좋다”를 <b>실험으로 반박한</b> 논문입니다. '
    '흔들수록 정책이 소심해져 <b>성능이 떨어집니다.</b>',
    '<b>이 절에 적힌 두 숫자가 전부 이 논문에서 나옵니다.</b> '
    '“몸통 속도를 모르면 버티는 힘이 반토막”도, “불필요한 랜덤화로 최고 속도 18% 하락”도 여기 근거가 있습니다. '
    'A14를 읽을 때 이 카드를 같이 보면 그 표가 주장이 아니라 실측이 됩니다.',
    [('측면 밀기 저항 (기본)', '43 ± 2 N'),
     ('속도 피드백 제거 시', '22 ± 0 N'),
     ('거기에 랜덤화까지 더하면', '13 ± 5 N'),
     ('트로팅 최고속도 (랜덤화 없음)', '1.1 m/s'),
     ('트로팅 최고속도 (랜덤화 함)', '0.9 m/s')],
    '<b>우리 랜덤화 설계의 판단 기준</b>입니다. 항목을 하나 넣을 때마다 “무엇을 얻고 무엇을 잃었나”를 기록하는 근거가 됩니다.',
    '로봇이 Unitree Laikago 이고 시뮬은 Isaac Gym 입니다. Go2 에 숫자가 그대로 오지는 않습니다. '
    '<b>가져올 것은 값이 아니라 “흔들면 잃는 것이 있다”는 구조</b>입니다.')


TAN2018 = paper(
    'tan2018',
    'Sim-to-Real: Learning Agile Locomotion For Quadruped Robots',
    'Tan 외 · Google Brain · RSS 2018',
    'https://arxiv.org/abs/1804.10332',
    '시뮬 물리를 실제 로봇에 맞춰 <b>먼저 고친 다음</b> 랜덤화를 얹어야 전이된다는 것을, '
    '자기들 실패 기록과 함께 보여준 논문입니다.',
    '두 가지 상식을 깹니다. ① <b>랜덤화를 세게 걸면 다 된다</b>는 틀렸습니다. 모터 모델과 지연이 틀려 있으면 아무리 흔들어도 안 넘어갑니다. '
    '② <b>정보를 더 주면 좋아진다</b>도 틀렸습니다. 관측을 4개에서 12개로 늘렸더니 실기 성능이 오히려 나빠졌습니다.',
    [('실측 제어 지연', '3 ms (PD) / 15~19 ms (상위)'),
     ('시뮬 지연 랜덤화 범위', '0 ~ 40 ms'),
     ('갤로핑 시뮬 → 실기', '1.34 → 1.18 m/s'),
     ('트로팅 시뮬 → 실기', '0.50 → 0.60 m/s'),
     ('학습 100개 중 실기 배포', '상위 3개')],
    '<b>A14에 적힌 “제어 지연 15~19 ms”가 이 논문의 숫자입니다.</b> 우리가 지연을 왜 랜덤화 항목에 넣는지의 근거입니다.',
    '저자 자인이 이 논문의 진짜 값어치입니다. 갤로핑은 <b>실기에서 즉시 넘어졌고</b>, '
    '트로팅은 <b>어떤 정책은 되고 어떤 건 안 되는 복불복</b>이었습니다. '
    '랜덤화로 학습한 정책은 평균 성능이 떨어지고 보수적으로 행동합니다.')


LEE2020 = paper(
    'lee2020',
    'Learning Quadrupedal Locomotion over Challenging Terrain',
    'Lee, Hwangbo, Wellhausen, Koltun, Hutter · ETH Zurich · Science Robotics 2020',
    'https://arxiv.org/abs/2010.11251',
    '카메라도 라이다도 없이 <b>다리 감각만으로</b> 진흙·눈·급류·수풀을 통과한 컨트롤러. '
    '시뮬 안에서만 아는 정답을 가진 <b>선생</b>을 한 단계 끼워 학습시켰습니다.',
    '<b>A12 급소의 원조 해법</b>입니다. 우리가 “시뮬엔 있고 실물엔 없다”고 정리한 네 가지(몸통 속도·지형 높이맵·마찰·강성)가 '
    '바로 이 논문이 말하는 <b>특권 정보</b>입니다. 그리고 <b>세상을 전부 시뮬레이션할 필요가 없다</b>는 것도 보였습니다. '
    '딱딱한 지형 몇 종류만 시뮬했는데 진흙·이끼·눈으로 그냥 일반화됐습니다.',
    [('학습 비용', '교사 12시간 + 학생 4시간'),
     ('사용 장비', '데스크톱 1대 (RTX 2080)'),
     ('DARPA SubT 60분 미션 4회', '실패 0'),
     ('이끼 위 속도', '0.452 vs 0.199 m/s'),
     ('학습에 없던 10 kg 짐을 지고', '13.4 cm 턱 통과')],
    '<b>읽되 그대로 쓰지는 않습니다.</b> 우리는 이 2단계 방식 대신 DreamWaQ 의 1단계를 씁니다. '
    '“왜 안 쓰는가”를 설명하려면 이걸 먼저 읽어야 합니다.',
    '저자 자인: 걸음걸이가 <b>트롯 하나뿐</b>이고, 무엇보다 <b>절벽으로 가라고 명령하면 그냥 갑니다.</b> '
    '눈이 없으니까요. 이 자기 고백이 정확히 「in the wild」(A15) 의 출발점입니다.')


# A트랙 절 → 붙일 논문
ACTION_SPACE = paper(
    'action-space',
    'Learning Locomotion Skills Using DeepRL: Does the Choice of Action Space Matter?',
    'Peng &amp; van de Panne · UBC · SCA 2017',
    'https://arxiv.org/abs/1611.01055',
    '“신경망이 <b>토크를 직접 낼까, 목표 각도를 낼까</b>”를 실험으로 비교한 논문입니다. '
    '답은 <b>목표 각도(PD 타깃)</b>였습니다.',
    '사족보행 강화학습이 왜 하나같이 <b>PD 제어기를 사이에 끼우는지</b>의 근거입니다. '
    '토크를 직접 내게 하면 학습이 훨씬 느리고 동작도 거칩니다. A4에서 “왜 굳이 PD를 거치나”가 여기서 풀립니다.',
    [('비교한 행동 공간', '토크 · PD 타깃 · 속도 등'),
     ('결론', 'PD 타깃이 학습 속도·안정성 우위')],
    '<b>우리가 PD 타깃을 쓰는 이유</b>입니다. A4를 읽고 “왜 신경망이 토크를 직접 안 내지?”가 남으면 이 카드를 보세요.',
    '보행 과제 중심의 비교이고, 로봇도 시뮬레이션 캐릭터입니다. '
    '결론의 방향은 이후 사족보행 연구가 계속 따랐지만 <b>수치를 그대로 인용하지는 마세요.</b>')


MUJOCO = paper(
    'mujoco',
    'MuJoCo: A physics engine for model-based control',
    'Todorov, Erez, Tassa · University of Washington · IROS 2012',
    'https://doi.org/10.1109/IROS.2012.6386109',
    '로봇 몸을 좌표가 아니라 <b>관절 각도</b>로 다루고 접촉을 볼록 최적화로 근사해, '
    '“보기 위한 시뮬레이터”가 아니라 <b>제어 계산을 실제로 돌릴 수 있는</b> 시뮬레이터를 연 엔진.',
    'A6에서 우리가 실제로 켜는 도구입니다. <b>가볍고 노트북에서 돕니다.</b> '
    '나중에 학습한 정책을 실기에 올리기 전 <b>다른 엔진에서도 걷는지 확인</b>하는 자리이기도 합니다.',
    [('동역학 평가 속도', '초당 약 400,000회'),
     ('실시간 대비', '약 5,000배'),
     ('접촉 6개일 때 감속', '약 3.4배')],
    '<b>A6에서 켭니다.</b> 학습용이 아니라 <b>검증용</b>이라는 위치를 기억하세요. 학습은 Isaac Lab에서 합니다.',
    '저자 스스로 밝힌 한계: 속도를 위해 접촉 조건 일부를 <b>일부러 뺐고</b>, 그 결과 '
    '“<b>떨어진 거리에서의 접촉</b>”이 생깁니다. MuJoCo의 그 유명한 <b>말랑한 접촉</b>이 여기서 나옵니다. '
    '접촉 정확도는 검증되지 않았다고도 적혀 있습니다.')


ISAACGYM = paper(
    'isaacgym',
    'Isaac Gym: High Performance GPU-Based Physics Simulation For Robot Learning',
    'Makoviychuk 외 · NVIDIA · 2021',
    'https://arxiv.org/abs/2108.10470',
    '물리 시뮬과 신경망 학습을 <b>둘 다 GPU에 올려 CPU를 거치지 않게</b> 만들어, '
    '클러스터가 필요하던 학습을 GPU 한 장으로 끌어내린 도구.',
    '<b>“4096개가 기준선”이라는 숫자 감각의 출처</b>입니다. 예전엔 CPU 수천 코어가 필요하던 실험을 '
    '이제 우리 워크스테이션 한 대로 합니다. A11의 표에 나오는 값들이 여기서 왔습니다.',
    [('기존 CPU 시뮬 대비', '100 ~ 1000배'),
     ('ANYmal 학습 (A100 1장)', '2분 미만'),
     ('처리량', '초당 최대 70만 스텝'),
     ('병렬 환경', '4,096 ~ 16,384')],
    '<b>개념은 계승, 도구는 교체.</b> NVIDIA가 legacy로 지정했고 후속이 Isaac Lab입니다. 설치 대상이 아닙니다.',
    '저자 자인: <b>환경을 4096개보다 늘리면 이득이 없고 오히려 학습이 느려지며 어색한 걸음이 나옵니다.</b> '
    '“많을수록 좋다”가 아닙니다. 또 가장 화려한 비교 수치는 <b>베스트 시드</b> 기준입니다.')


BY_SECTION = {
    'A4':  [ACTION_SPACE],
    'A6':  [MUJOCO],
    'A8':  [PPO],
    'A9':  [WALK_MIN],
    'A10': [PARKOUR],
    'A11': [ISAACGYM],
    'A12': [LEE2020, RMA, DREAMWAQ],
    'A14': [DR_REVISIT, TAN2018],
    'A15': [WILD],
}


CSS = r"""
/* ═══ 논문 카드 ═══ */
.pref{margin:1.4rem 0;background:var(--dim-soft);border:1px solid var(--rule);
  padding:.95rem 1.1rem 1rem;max-width:var(--measure)}
.pref .p-top{display:flex;align-items:baseline;gap:.55rem;flex-wrap:wrap}
.pref .p-tag{font-size:.56rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;
  color:var(--dim);background:var(--dim-soft);padding:.14rem .42rem;flex:0 0 auto}
.pref .p-title{font-size:.88rem;font-weight:700;color:var(--ink);text-decoration:none;line-height:1.4}
.pref .p-title:hover{color:var(--dim);text-decoration:underline}
.pref .p-ext{font-size:.7em;color:var(--ink-3)}
.pref .p-meta{font-size:.68rem;color:var(--ink-3);margin:.3rem 0 .55rem}
.pref .p-one{font-size:.82rem;color:var(--ink);line-height:1.7;margin:0 0 .8rem;
  padding-bottom:.7rem;border-bottom:1px dashed var(--rule)}
.pref .p-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:1rem}
.pref .p-h{font-size:.58rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase;
  color:var(--ink-3);margin-bottom:.35rem}
.pref .p-why p{font-size:.78rem;color:var(--ink-2);line-height:1.65;margin:0}
.pref .pn-r{display:flex;justify-content:space-between;gap:.6rem;padding:.24rem 0;
  border-bottom:1px dotted var(--rule);font-size:.75rem}
.pref .pn-r:last-child{border-bottom:none}
.pref .pn-k{color:var(--ink-3);min-width:0}
.pref .pn-v{color:var(--dim);font-weight:800;text-align:right;white-space:nowrap}
.pref .p-ours{margin-top:.8rem;padding:.5rem .65rem;background:var(--dim-soft);
  font-size:.76rem;color:var(--ink);line-height:1.6}
.pref .p-ok{font-size:.56rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase;
  color:var(--dim);margin-right:.45rem}
.pref .p-lim{margin-top:.45rem;padding:.45rem .65rem;background:var(--note-soft);
  font-size:.74rem;color:var(--ink-2);line-height:1.6}
.pref .p-lk{font-size:.56rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase;
  color:var(--note);margin-right:.45rem}
@media (max-width:700px){
  .pref{padding:.8rem .85rem .85rem}
  .pref .p-grid{grid-template-columns:1fr;gap:.7rem}
  .pref .p-title{font-size:.82rem}
}
@media print{
  .pref{break-inside:avoid;page-break-inside:avoid}
  .pref .p-title{color:var(--ink)!important}
  .pref .p-title::after{content:' (' attr(href) ')';font-size:.62rem;color:var(--ink-3);font-weight:400}
  .pref .p-ext{display:none}
}
"""
