# -*- coding: utf-8 -*-
"""정보 구조: 모든 페이지가 어디 속하는지의 «유일한 표».

  ★ 2026-08-25 사고에서 배운 것.
    허브를 lab 문서(분류 메타가 있는 것)만 읽게 만들었더니, 볼트에서 생성하는
    페이지(자료실·백과·설치·커리큘럼·팀접근)가 **어느 허브에도 못 들어갔다.**
    그 상태로 표지 섹션을 걷어내서 자료실이 1클릭에서 3클릭으로 밀렸다.

    원인은 «분류가 없는 페이지가 조용히 빠지는 구조» 였다.
    그래서 이 표를 만든다. **표에 없는 페이지가 있으면 빌드가 선다.**
    분류를 못 정하면 배포도 못 한다. 조용히 빠지는 경로를 없앤다.

  구조 (팀장 확정 2026-08-26)
      맨 위 띠     주간 다이제스트
      바로가기     자료실 · 학습 커리큘럼 · 예산안 … (QUICK 이 정본)
      허브         기획 · 일정 · 회의 · 연구 · 기술 · 파이프라인 (HUBS 가 정본)
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)

# 허브. (키, 한글, 영문, 파일, 한 줄 설명)
HUBS = [
    ('proposal', '기획', 'Proposal', 'hub-proposal.html',
     '무엇을 왜 하는가. 밖에 보여주는 것'),
    ('schedule', '일정', 'Schedule', 'hub-schedule.html',
     '언제 무엇을. 주간 계획과 마일스톤'),
    ('meeting', '회의', 'Meetings', 'hub-meeting.html',
     '언제 무엇을 정했나. 최신이 위'),
    ('research', '연구', 'Research', 'hub-research.html',
     '우리가 돌린 실험과 밖에서 조사한 것'),
    # ★ 2026-09-13 팀장 지적: 「연구 페이지 가면 왜 전역바에 갤러리가 없나.
    #   갤러리를 들어가야 생기고 기본적으로는 없네」.
    #
    #   원인은 전역바를 만드는 자리가 «둘» 이었다. 여기가 정본인데 갤러리가
    #   없었고, `assets/gnav.html` 은 갤러리 페이지에서 «뽑아낸 사본» 이라
    #   거기에만 있었다. 그래서 갤러리 안에서만 보였다.
    #
    #   갤러리는 허브 «페이지» 가 아니라 폴더(`/gallery/`)다. 그래도 나머지와
    #   같은 줄에 서야 «평가 영상이 있다» 는 것이 첫 화면에서 보인다.
    ('gallery', '갤러리', 'Gallery', '/gallery/',
     '평가 영상 144컷 · 지형과 속도별로 눈으로 보기'),
    # ★ 2026-08-29 (#71). 여섯째 허브. 파이프라인(= 우리가 어떻게 일하는가)과
    #   기술(= 이 기술을 어떻게 하는가)은 답하는 질문이 다르다.
    ('tech', '기술', 'Tech', 'hub-tech.html',
     '이 기술을 어떻게 하는가. 명령 · 설정 · 개념'),
    ('pipeline', '파이프라인', 'Pipeline', 'hub-pipeline.html',
     '환경 구축 · 협업 규칙 · 자동화'),
]

# 표지 맨 위 띠
BANNER = ('digest', '주간 다이제스트', 'Weekly Digest')

# 바로가기. (파일, 이름, 영문, 한 줄)
QUICK = [
    ('chosun-materials.html', '팀 자료실', 'Materials', '조선대 강의 자료 · 암호 필요'),
    ('encyclopedia.html', '도메인 백과', 'Encyclopedia', '사족보행 로봇 용어와 개념'),
    ('curriculum.html', '학습 커리큘럼', 'Curriculum', '무엇을 어떤 순서로 배우는가'),
    ('budget.html', '예산안', 'Budget', '지원금 사용 계획 · 암호 필요'),
]

# 표지에 남는 것 (허브에 넣지 않는다)
#   허브 페이지 자체도 여기다. 허브가 허브에 들어가면 무한이 된다.
ROOT = ['index.html', 'questions.html'] + [h[3] for h in HUBS]

# ── 볼트 생성 페이지의 배정. lab 문서는 md 의 «분류» 를 쓰므로 여기 없다.
#    새 볼트 페이지를 만들면 여기 한 줄을 추가해야 한다. 안 하면 빌드가 선다.
VAULT_PAGE = {
    'project-report.html': ('proposal', '프로젝트 보고서', '한 장으로 보는 전체 계획'),
    # PRD §3 확정 (8/31): 「무엇을 어떤 순서로」는 기획의 심장. 파이프라인에서 이동.
    'flow.html': ('proposal', '프로젝트 전체 흐름', '두 트랙으로 무엇을 어떤 순서로 하는가'),
    'pitch.html': ('proposal', '프로젝트 소개 덱', '전체화면 발표용'),
    'brief.html': ('proposal', '프로젝트 브리핑', '외부에 짧게 설명할 때'),
    'team-intro.html': ('proposal', '팀 소개 · 킥오프', '팀과 역할'),
    'team-lead.html': ('proposal', '오흥재', 'Project Lead · Robotics Systems Integrator'),
    'team-lim.html': ('proposal', '임석헌', '강화학습 정책 · 모델 (A/정책학습)'),
    'team-lee.html': ('proposal', '이민우', '기록 · 문서 · 대외보고 (C/기록)'),
    'team-oh.html': ('proposal', '오현민', '일반화 평가 · 인지 (A/평가 · B/인지)'),
    'plan.html': ('schedule', '프로젝트 설계도', '흐름 · 퀘스트 · 결정 안건'),
    'setup.html': ('pipeline', '개발환경 구축', '팀 공통 세팅'),
    'team-access.html': ('pipeline', '워크스테이션 접속', '원격 접속과 운영'),
    'automation.html': ('pipeline', '자동화 지도', '무엇이 자동이고 무엇이 사람인가'),
    'research.html': ('research', '연구 기록 안내', '조사와 실측의 원본 기록'),
    'deliverables.html': ('schedule', '산출물 현황', '무엇을 언제까지 내는가'),
    'workflow.html': ('pipeline', '작업 흐름', '이슈부터 머지까지 한 장. 흐름의 정본'),
    'personal-plans.html': ('schedule', '개인 계획', '팀원이 스스로 세운 계획의 원본'),
    'decisions-20260827.html': ('meeting', '설계 결정 기록', '8/26~27 에 확정한 것 전부'),
    'roles.html': ('proposal', '역할 배치',
                   '작업 영역 8갈래와 주담당 · 사람별 강점. 발표 덱이 여기서 생성된다'),
    'ledger.html': ('schedule', '진행 현황',
                    '모든 요청이 지금 어디 있나. 열린 이슈 전수와 대기 큐'),
    'info-model.html': ('pipeline', '정보 모델',
                        '문서를 무엇으로 가르고 새 문서가 어떻게 제자리에 서나'),
    'research-taxonomy.html': ('pipeline', '연구 허브 분류 기준 (검토중)',
                               '연구 21장을 다섯 묶음으로. 팀장 컨펌 대기'),
    'doc-graph.html': ('pipeline', '문서 관계표',
                       '무엇이 무엇의 상위인가. 표지 노출 기준의 근거 (#76)'),
    'decisions-log.html': ('meeting', '결정 로그',
                           '무엇을 언제 왜 정했나. 뒤집은 것은 취소선으로 남는다'),
    'runpod-setup.html': ('pipeline', 'RunPod Isaac Lab 환경 구축',
                          '네트워크 볼륨 · 템플릿 · 첫 실행. 마운트는 /data 여야 한다'),
    'ros2-01-setup.html': ('tech', 'ROS 2 개발환경 구축',
                           'Ubuntu 24.04 + Jazzy. 명령마다 토큰별 뜻까지 (오현민)'),
    'ros2-02-python.html': ('tech', 'ROS 2 Python 프로그래밍',
                            'rclpy 노드 · colcon 패키지 · 커스텀 인터페이스 (오현민)'),
    'ros2-03-tf-rviz2.html': ('tech', 'ROS 2 TF 좌표계와 RViz2',
                              '로봇이 자기 몸과 주변의 위치 관계를 아는 법 (오현민)'),
    # ★ #72 1단계: foothold-wiki 이식 4쪽 (원저자 오현민 · md 정본화는 2단계).
    'tech-ros2-ref.html': ('tech', 'ROS 2 레퍼런스',
                           '큰 그림 · 통신 4형제 · rclpy · 패키지 · 디버깅. 1~3편의 심화 레퍼런스'),
    'tech-rl.html': ('tech', '시뮬레이션 RL 레퍼런스',
                     'Isaac Lab 선택 근거 · 험지 RL 표준 레시피 · 핵심 논문 5편'),
    'tech-slam-nav.html': ('tech', 'SLAM · Nav2 레퍼런스',
                           'Go2 와 ROS 2 연동 · SLAM 2D 메인 · Nav2 차동구동 설정'),
    'tech-cv.html': ('tech', '컴퓨터 비전 교재',
                     '이미지의 정체부터 YOLO 실측 · ROS 2 이미지 파이프라인까지 12절'),
    # ★ 2026-08-29 (#73). 팀 공지는 표지 배너에 이미 나간다. 허브에도 두면
    #   같은 글이 두 번 보인다. 허브에서 뺀다 (페이지는 그대로 있다).
    'notice-latest.html': ('_quick', '팀 공지', '지금 무엇이 바뀌었나'),
    # 날짜 공지는 회의 허브의 «언제 무엇을 알렸나» 축에 선다 (팀장 9/2)
}

# lab 문서의 «분류» 를 허브로 보내는 규칙
KIND_HUB = {
    '회의록': 'meeting', '현장': 'meeting',
    '실험': 'research', '리서치': 'research', '결정': 'research',
    # ★ 팀장 지적 (9/1): 「8/18 험지RL 학습 계획」은 개인 일정이지 연구가 아니다.
    #   연구 허브는 «우리가 무엇을 알아냈나» 이고, 계획은 «언제 무엇을» 이다.
    #   분류=계획 은 일정 허브로 보낸다.
    '계획': 'schedule',
    '운영': 'pipeline', '가이드': 'pipeline',
}

# ★ 2026-08-29. 허브 묶음이 «분류» 하나에서만 나왔다. 그래서 `분류=리서치` 11장이
#   통째로 「조사」 한 묶음이 됐고, 그 이름은 아무것도 안 걸러 줬다.
#   이제 «작업 영역» 축을 함께 쓴다. 영역은 `_build/docgraph.py` 가 매 빌드마다
#   본문에서 판정해 `docs/ops/doc-graph.json` 에 넣는다. 손 목록이 아니다.
_AREAS = {}


def _load_areas(lab):
    """관계표에서 문서별 작업 영역을 읽는다. {docs 기준 경로: [영역]}"""
    global _AREAS
    if _AREAS or not lab:
        return _AREAS
    p = os.path.join(lab, 'docs', 'ops', 'doc-graph.json')
    if not os.path.isfile(p):
        return _AREAS
    try:
        import json
        for d in json.load(io.open(p, encoding='utf-8')):
            if d.get('areas'):
                _AREAS[d['path']] = d['areas']
    except Exception:
        pass
    return _AREAS


# 영역 -> 묶음 이름. 「무엇을 하나」가 아니라 「무엇을 물으러 왔나」로 읽히게 쓴다.
AREA_GROUP = {
    'A/정책학습': '정책을 어떻게 학습시키나',
    'A/평가': '얼마나 걷나 · 평가와 지표',
    'A/지형씬제작': '지형과 씬을 어떻게 만드나',
    'A/트윈렌더': '트윈과 렌더',
    'B/항법': '실기 항법 · ROS 2 와 SLAM',
    'B/인지': '센서로 무엇을 보나',
    'C/기록': '기록 · 대외보고',
    'C/운영': '인프라 · 자동화 · 예산',
}

# ★ 2026-08-29 실측. 같은 갈래라도 허브가 다르면 묶음 이름이 달라야 한다.
#   `C/운영` 문서가 연구 허브에서는 「인프라 · 자동화 · 예산」(GPU·비용·측정)이지만,
#   파이프라인 허브에서는 「우리가 일하는 방법」(협업 규칙 · 전체 흐름)이다.
#   한 이름을 두 허브에 쓰면 한쪽은 반드시 어긋난다.
AREA_GROUP_BY_HUB = {
    'pipeline': {'C/운영': '운영 규칙',
                 'C/기록': '기록 · 대외보고'},
}

# 묶음 한 줄 설명. 제목만으로는 무엇이 들었는지 모른다 (팀장 지적 2026-08-28).
#   ★ 8갈래에서 온 묶음은 ROLES.md 의 「무엇을 하나」 칸을 그대로 쓴다.
#     여기 베껴 적지 않는다. 표가 바뀌면 설명도 따라간다.
GROUP_LEDE = {
    '계획과 결정': '갈림길에서 무엇을 고르고 무엇을 버렸는가.',
    'ROS 2 학습 (조선대 수업 정리)': '조선대 수업을 우리 말로 다시 쓴 것.',
    '환경 세우기': '처음 오는 사람이 손을 움직이려면 무엇부터 하나.',
    '자동으로 도는 것': '사람이 안 눌러도 도는 것들.',
    '운영 규칙': '문서를 무엇으로 가르고 어떻게 굴리는가.',
    '무엇을 정했나': '회의에서 확정한 것. 최신이 위.',
    '안내': '',
}

def group_lede(name, lab=None):
    """묶음 한 줄 설명. 8갈래 묶음은 정본 표에서 읽는다."""
    if name in GROUP_LEDE:
        return GROUP_LEDE[name]
    for area, g in AREA_GROUP.items():
        if g != name:
            continue
        try:
            import areas
            voc_src = areas.vocab(lab) if lab else None
        except Exception:
            voc_src = None
        return _AREA_WHAT.get(area, '')
    return ''

# ROLES.md 8갈래 표의 「무엇을 하나」 칸. 빌드가 채운다 (손으로 안 적는다).
_AREA_WHAT = {}


def load_area_what(lab):
    if _AREA_WHAT or not lab:
        return
    p = os.path.join(lab, 'docs', 'ROLES.md')
    if not os.path.isfile(p):
        return
    t = io.open(p, encoding='utf-8', newline=None).read()
    for m in re.finditer(r'^\|\s*`([ABC]/[^`]+)`\s*\|([^|]*)\|', t, re.M):
        _AREA_WHAT[m.group(1).strip()] = m.group(2).strip() + '.'


# 영역으로 다시 가르는 허브. 회의는 시간순이 맞으므로 여기 없다.
AREA_HUBS = ('research', 'pipeline')

# 허브 안에서 다시 나누는 갈래
KIND_GROUP = {
    '실험': '실측 · 우리가 돌린 것',
    '리서치': '조사 · 밖에서 찾은 것',
    '결정': '계획과 결정',
    '계획': '계획',
    '회의록': '회의록',
    '현장': '현장 기록',
    '운영': '일하는 규칙',
    '가이드': '일하는 규칙',
}

VAULT_GROUP = {
    'proposal': {'project-report.html': '대외 산출물',
                 'pitch.html': '대외 산출물',
                 'brief.html': '대외 산출물',
                 'team-intro.html': '내부 문서',
                 # ★ 9/1 팀장 지적: 「기획 내부 문서에 오흥재 나만 있을 필요가
                 #   있냐」. 오늘 넷이 되면서 이름이 다섯 줄로 늘었다. 그건 더
                 #   나쁘다. 사람 페이지는 «팀 소개·킥오프» 에서 이름을 눌러
                 #   들어가는 것이 원래 설계다 (teamprofiles 주석).
                 #   허브에서는 한 줄로 묶는다.
                 'team-lead.html': '사람',
                 'team-lim.html': '사람',
                 'team-lee.html': '사람',
                 'team-oh.html': '사람',
                 # ★ 2026-08-29 실측. 여기 없어서 「아직 안 갈린 것」에 홀로 있었다.
                 'roles.html': '내부 문서',
                 'flow.html': '내부 문서'},
    # ★ 2026-08-29. 「설계도 / 주간」 둘뿐이라 원장·산출물현황·개인계획 3장이
    #   「아직 안 갈린 것」으로 떨어졌고 그 묶음이 목록 «중간» 에 박혔다.
    #   묶음 이름을 「무엇을 물으러 왔나」로 다시 쓴다.
    'schedule': {'ledger.html': '진행 현황',
                 'deliverables.html': '제출 산출물',
                 'plan.html': '계획',
                 'plan-weekly.html': '계획',
                 'personal-plans.html': '계획'},
    # 결정 로그 두 장은 회의 허브로 옮겼다 (#73). 「무엇을 정했나」가 회의의 산물이다.
    'meeting': {'decisions-log.html': '무엇을 정했나',
                'decisions-20260827.html': '무엇을 정했나'},
    'pipeline': {'setup.html': '환경 세우기', 'team-access.html': '환경 세우기',
                 'automation.html': '자동으로 도는 것',
                 # ★ 2026-08-29 (#73). 「아직 안 갈린 것」에 7장이 쌓여 있었다.
                 #   볼트 페이지라 md 의 «분류» 가 없어 아무 묶음도 못 받았다.
                 'workflow.html': '운영 규칙',
                 'info-model.html': '운영 규칙',
                 'doc-graph.html': '운영 규칙',
                 'research-taxonomy.html': '운영 규칙'},
    'research': {'research.html': '안내'},
    # #71: ROS 2 3편은 「우리가 일하는 규칙」이 아니라 「기술을 배우는 것」이다.
    'tech': {'ros2-01-setup.html': 'ROS 2 기초',
             'ros2-02-python.html': 'ROS 2 기초',
             'ros2-03-tf-rviz2.html': 'ROS 2 기초',
             'tech-ros2-ref.html': 'ROS 2 기초',
             'tech-rl.html': '트랙 A · 시뮬 학습',
             'tech-slam-nav.html': '트랙 B · 실기 항법',
             'tech-cv.html': '트랙 B · 실기 항법'},
    # ★ 2026-08-29 실측. 여기 'encyclopedia.html': '낱말 찾기' 가 있었는데
    #   백과는 QUICK(바로가기)에서 먼저 잡혀 이 줄에는 영원히 안 닿았다.
    #   «닿지 않는 줄» 은 지운다. 백과를 허브에도 두면 같은 글이 두 번 보인다
    #   (#73 에서 팀 공지를 뺀 것과 같은 이유).
}

LAB_DIRS = ('research', 'meetings')


def _lab_root():
    """lab 경로는 docs_pages.LAB_CANDIDATES 하나만 쓴다.

    ★ 2026-09-09. 여기에 자기만의 후보 목록이 따로 있었다. 그래서 빌드 입력을
      고정 워크트리(_lab-main)로 옮겼을 때 docs_pages 는 그쪽을 보는데 이 파일은
      옛 경로를 봤다. 결과: 승격된 문서 8장이 원본을 못 찾아 «배정되지 않은
      페이지» 로 잡혀 배포가 섰다. 문서는 멀쩡한데 길이 둘이라 갈렸다.
      같은 규칙이 두 자리에 살면 한쪽을 고쳐도 다른 쪽이 옛 경로를 본다 (철칙 4).
    """
    import docs_pages
    for c in docs_pages.LAB_CANDIDATES:
        if os.path.isdir(os.path.join(c, 'docs')):
            return c
    return None


def _meta(path):
    t = io.open(path, encoding='utf-8').read()
    out = {}
    for f in ('분류', '작성', '요지', '자리'):
        m = re.search(r'^>\s*%s\s*:\s*(.+)$' % f, t, re.M)
        if m:
            out[f] = m.group(1).strip()
    m = re.search(r'^#\s+(.+)$', t, re.M)
    mv = re.search(r'^>\s*판\s*:\s*(v[\d.]+)', t, re.M)
    out['판'] = mv.group(1) if mv else ''
    out['제목'] = m.group(1).strip() if m else os.path.basename(path)
    return out


def catalog(site_pages):
    """(배정, 미배정) 을 돌려준다. 미배정이 있으면 배포하면 안 된다."""
    lab = _lab_root()
    assigned, orphan = {}, []

    for p in sorted(site_pages):
        if p in ROOT:
            assigned[p] = ('_root', '표지', p, '', '')
            continue
        if p.startswith('digest-'):
            assigned[p] = ('_banner', '주간', '주간 다이제스트', '', '')
            continue
        # 날짜 공지. 이름 규칙으로 배정한다 (손 목록이면 다음 공지에 또 빠진다)
        m_no = re.match(r'^notice-(\d{4})(\d{2})(\d{2})\.html$', p)
        if m_no:
            _d = '%s-%s-%s' % m_no.groups()
            _md = os.path.join(lab or '', 'docs', 'notices', _d + '.md')
            _m = _meta(_md) if os.path.isfile(_md) else {}
            assigned[p] = ('meeting', '팀 공지',
                           '%s 공지' % _d, _m.get('요지', ''), '', '')
            continue
        # 산출물 문서. 「산출물 현황」과 같은 일정 허브에 둔다.
        #   목록은 deliverables_docs 가 유일 원본이다. 여기서 다시 세지 않는다.
        if p.startswith('deliverable-'):
            try:
                import deliverables_docs as _dd
                info = next((d for d in _dd.DOCS
                             if _dd.PREFIX + d[1] + '.html' == p), None)
            except Exception:
                info = None
            if info:
                # ★ 2026-08-29 실측. 제목이 파일명 슬러그(`nav-report`)로 나갔다.
                #   화면에 영문 슬러그가 뜨면 「무엇에 관한 글인지」를 못 읽는다.
                #   정본 md 의 제목을 쓴다. 없을 때만 슬러그로 떨어진다.
                _dlab = _dd.lab_root()
                src = os.path.join(_dlab, *info[0].split('/')) if _dlab else ''
                m = _meta(src) if src and os.path.isfile(src) else {}
                assigned[p] = ('schedule', '제출 산출물',
                               m.get('제목') or p[len('deliverable-'):-5],
                               m.get('요지') or info[2], info[2],
                               m.get('판', ''))
                continue
        if p in [q[0] for q in QUICK]:
            q = next(x for x in QUICK if x[0] == p)
            assigned[p] = ('_quick', '바로가기', q[1], q[3], '')
            continue
        if p in VAULT_PAGE:
            hub, title, lede = VAULT_PAGE[p]
            grp = VAULT_GROUP.get(hub, {}).get(p, '')
            assigned[p] = (hub, grp, title, lede, '')
            continue
        # lab 문서
        base = p[:-5]
        cand = []
        if base.startswith('research-'):
            cand.append(('research', base[len('research-'):]))
        if base.startswith('meeting-'):
            cand.append(('meetings', base[len('meeting-'):]))
        cand.append(('.', base.upper()))
        cand.append(('.', base.replace('-', '-').upper()))
        src = None
        if lab:
            for d, nm in cand:
                f = os.path.join(lab, 'docs', d, nm + '.md')
                if os.path.exists(f):
                    src = f
                    break
        if not src:
            orphan.append(p)
            continue
        m = _meta(src)
        hub = KIND_HUB.get(m.get('분류'))

        # ★ 2026-09-13 팀장 지적: 「이 문서는 전역바에서 파이프라인이
        #   클릭되어 있네」 (평가 프로토콜 정본).
        #
        #   그 문서는 `분류: 가이드` 라 `KIND_HUB` 가 pipeline 으로 보냈다.
        #   그런데 **문서는 연구 허브 목록에 있다.** 있는 곳과 전역바가 켜는
        #   곳이 달라 읽는 사람이 헤맨다.
        #
        #   분류는 «글의 성격»(가이드·실험·계획)이고 폴더는 «무엇에 관한
        #   글인가» 다. `docs/research/` 에 있으면 연구다. 폴더가 이긴다.
        #   지금 이 규칙에 걸리는 것은 둘이다 (`20260911-eval-protocol-v2` ·
        #   `20260909-eval-harness-diagram`). 둘 다 평가를 설명하는 연구 문서다.
        rel_src = src.replace(os.sep, '/')
        if '/docs/research/' in rel_src:
            hub = 'research'

        if not hub:
            orphan.append(p)
            continue
        group = KIND_GROUP.get(m['분류'], '')
        # 영역 축이 있으면 그것으로 가른다. 여러 영역이면 첫째(점수 1등)로 놓는다.
        #   한 문서를 여러 묶음에 중복해 놓으면 같은 글이 두 번 보인다.
        if hub in AREA_HUBS:
            rel = os.path.relpath(src, os.path.join(lab, 'docs'))
            ar = _load_areas(lab).get(rel.replace(os.sep, '/'))
            if ar and AREA_GROUP.get(ar[0]):
                group = (AREA_GROUP_BY_HUB.get(hub, {}).get(ar[0])
                         or AREA_GROUP[ar[0]])
        # 회의록은 「자리」로 다시 가른다. 멘토에게 받은 조언과 팀이 스스로 정한
        # 결정이 같은 줄에 있으면 「누가 정한 것인가」를 매번 되짚어야 한다.
        if hub == 'meeting' and m.get('자리'):
            group = {'팀내부': '팀 내부에서 정한 것',
                     '멘토링': '멘토에게 받은 것',
                     '운영진': '운영진과 맞춘 것',
                     '조선대': '조선대와 맞춘 것'}.get(m['자리'], group)
        # 판(버전)을 함께 싣는다. 「이 글이 몇 판인가」가 카드에서 보여야
        # 옛 판을 붙잡고 있는지 알 수 있다 (판 체계 2026-08-28).
        assigned[p] = (hub, group, m['제목'], m.get('요지', ''),
                       m.get('작성', ''), m.get('판', ''))
    return assigned, orphan


def ghost_pages():
    """VAULT_PAGE 에 등록됐는데 파일이 없는 것 (#74-6 · 2026-08-28 사고 재발 방지).
    plan-weekly.html 이 등록만 된 채 존재하지 않아 아무도 몰랐다."""
    return [f for f in VAULT_PAGE if not os.path.isfile(os.path.join(VAULT, f))]


def _kat():
    """★ 배정 규칙이 실제로 «빠뜨린 것»을 잡는지 본다."""
    a, o = catalog(['index.html', 'chosun-materials.html', 'zzz-unknown.html'])
    if 'zzz-unknown.html' not in o:
        return False, '모르는 페이지를 미배정으로 안 잡음'
    if a.get('chosun-materials.html', ('',))[0] != '_quick':
        return False, '바로가기 배정 실패'
    return True, ''


# 볼트에만 있고 배포하지 않는 원본. 배정 대상이 아니다.
#   kickoff.html 은 merge_deck.py 가 팀소개와 합칠 때 쓰는 재료다.
NOT_DEPLOYED = ('kickoff.html',)


def main(site_dir=None, pages=None):
    """pages 를 주면 그것만 본다(빌드의 PAGES 목록). 없으면 폴더를 훑는다."""
    site_dir = site_dir or VAULT
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return None
    if pages is None:
        pages = [f for f in os.listdir(site_dir) if f.endswith('.html')]
    pages = [p for p in pages if p not in NOT_DEPLOYED]
    assigned, orphan = catalog(pages)
    from collections import Counter
    c = Counter(v[0] for v in assigned.values())
    print('  자가검증 통과 · 페이지 %d개 배정' % len(assigned))
    print('  띠 %d · 바로가기 %d · 표지 %d · %s'
          % (c.get('_banner', 0), c.get('_quick', 0), c.get('_root', 0),
             ' · '.join('%s %d' % (h[1], c.get(h[0], 0)) for h in HUBS)))
    if orphan:
        print('  ★ 어느 칸에도 안 들어가는 페이지 %d개:' % len(orphan))
        for p in orphan:
            print('      %s' % p)
        print('      -> ia.py 의 VAULT_PAGE 에 한 줄 추가하거나, lab md 에 «분류» 를 다세요.')
        return None
    return assigned


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
