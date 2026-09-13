# -*- coding: utf-8 -*-
"""문서가 어느 «작업 영역» 인지 정본에서 읽어 판정한다.

★ 왜 만드나 (2026-08-29)

  팀장이 물었다. 「앞으로 들어오는 문서에 맞춰서도 설계가 된 것인가」
  아니었다. 허브 묶음이 내가 손으로 적은 슬러그 목록이었다.
  오늘 하루 걷어낸 「손 관리 마스터」를 목업에서 다시 만든 것이다.

  그리고 팀장이 한 번 더 물었다. 「머리에 갈래를 추가하면 팀원이 분류를
  해서 줘야 하는 것 아닌가. 자동이 아니지 않나」 맞다. 그건 자동화가 아니라
  쓰는 사람에게 세금을 매기는 것이다.

  **그래서 사람에게 묻지 않고 문서를 읽어 판정한다.**

무엇이 정본인가

  `foothold-lab/docs/ROLES.md` §1 의 8갈래 표. 그 표의 「무엇을 하나」 칸이
  곧 이 분류기의 어휘다. **여기서 읽어 온다. 베껴 적지 않는다.**
  8갈래가 바뀌면 분류기도 저절로 따라간다. 표와 코드가 갈라질 자리를 없앤다.

무엇을 조심하나

  판정은 추측이다. 추측을 사실처럼 적지 않는다 (커널 원칙 4).
  그래서 점수와 **근거가 된 낱말**을 함께 돌려주고, 1등과 2등의 차이가
  작으면 «확인 필요» 라고 말한다. 조용히 아무 데나 넣는 것이 제일 나쁘다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 어휘 표에 안 적혀 있지만 그 영역을 사실상 가리키는 말.
# ★ 표를 대신하지 않는다. 표에서 읽은 낱말에 «덧붙이는» 것이고, 왜 덧붙였는지 적는다.
EXTRA = {
    'A/정책학습': ['정책', 'policy', 'rsl_rl', 'PPO', '체크포인트', 'checkpoint',
                 'reward', '학습', 'iter', 'fine-tune', '파인튜닝'],
    'A/지형씬제작': ['terrain', '지형', 'Isaac Lab', '씬', 'USD', '에셋'],
    'A/평가': ['벤치마크', 'benchmark', '통과율', '에피소드', '평가', '지표',
              '일반화', 'RoboGauge', '성공률'],
    'A/트윈렌더': ['3DGS', 'Path Tracing', '렌더', 'Omniverse', 'RTX',
                 'USD Composer', '트윈', '합성데이터'],
    'B/항법': ['ROS 2', 'ROS2', 'SLAM', 'Nav2', 'TF', '좌표계', 'rclpy',
              'cmd_vel', 'Go2', '실기', '항법'],
    'B/인지': ['LiDAR', '라이다', '카메라', '센서', '점군', '포인트클라우드', '인지'],
    'C/기록': ['회의록', '멘토링', '커리큘럼', '백과', '발표', '보고서', '전사',
              '다이제스트', '용어'],
    'C/운영': ['인프라', '자동화', 'GitHub', '워크플로', '예산', '일정', '배포',
              '빌드', 'Runpod', 'GPU', '서버', '관문', '저장소'],
}

STOP = ('무엇', '우리', '하나', '어떻게', '그리고', '이것', '있다', '한다')


def vocab(lab):
    """ROLES.md §1 표에서 영역과 어휘를 읽는다. (영역 -> [낱말])"""
    p = os.path.join(lab, 'docs', 'ROLES.md')
    if not os.path.isfile(p):
        return None
    t = io.open(p, encoding='utf-8', newline=None).read()
    out = {}
    for m in re.finditer(r'^\|\s*`([ABC]/[^`]+)`\s*\|([^|]*)\|', t, re.M):
        key = m.group(1).strip()
        words = [w.strip() for w in re.split(r'[·,]', m.group(2)) if w.strip()]
        words = [w for w in words if len(w) >= 2 and w not in STOP]
        out[key] = words + EXTRA.get(key, [])
    return out or None


def _weighted(text):
    """제목과 절 제목은 본문보다 무겁게 센다. 문서가 «무엇에 관한 글인가» 는
    본문 어딘가에 한 번 스친 낱말이 아니라 제목이 말한다."""
    h1 = ' '.join(re.findall(r'^#\s+(.+)$', text, re.M))
    hs = ' '.join(re.findall(r'^#{2,4}\s+(.+)$', text, re.M))
    yo = ' '.join(re.findall(r'^>\s*요지:\s*(.+)$', text, re.M))
    return ((h1 + ' ') * 6) + ((yo + ' ') * 4) + ((hs + ' ') * 2) + text


def judge(text, voc, margin=1.35, span=0.55):
    """문서의 작업 영역을 판정한다.

    돌려주는 것: (영역목록, 점수표, 근거낱말, 확신)

    ★ 영역은 **하나가 아닐 수 있다.** 이것이 실측에서 나온 사실이다.
      56장에 돌려 보니 15장이 1등과 2등 점수가 나란했다 (`REPORT` 는 항법 102
      대 정책학습 90). 처음에는 그것을 «애매하다» 고 봤는데, 열어 보니 애매한
      것이 아니라 **정말로 여러 영역을 다루는 글**이었다. 보고서와 회의록과
      다이제스트가 그렇다. 그런 문서에 영역 하나를 억지로 붙이면 거짓이 된다.

      그래서 1등의 `span` 배 이상인 영역을 **함께** 돌려준다.
      영역이 셋을 넘으면 그 문서는 «전체» 를 다루는 것이라 영역으로 안 가른다.

    확신이 아닌 경우: 신호가 아예 없거나(3점 미만) 영역이 넷 이상일 때.
    조용히 아무 데나 넣지 않는다.
    """
    hay = _weighted(text)
    low = hay.lower()
    score, why = {}, {}
    for area, words in voc.items():
        sc, hit = 0, []
        for w in words:
            k = low.count(w.lower())
            if k:
                sc += k
                hit.append('%s×%d' % (w, k))
        score[area] = sc
        why[area] = hit
    rank = sorted(score.items(), key=lambda kv: -kv[1])
    top = rank[0]
    if top[1] < 3:
        return [], score, [], False
    picked = [a for a, v in rank if v >= top[1] * span and v >= 3]
    sure = 1 <= len(picked) <= 3
    hits = []
    for a in picked:
        hits += why[a][:3]
    return picked, score, hits[:8], sure


def _kat(voc):
    """★ 답을 아는 입력으로 먼저 시험한다."""
    cases = [
        ('# Isaac Lab v2.3.2 지형 가이드: Go2 커스텀 험지 설계\n'
         '> 요지: 지형 생성 구조와 설정 방법. terrain 설정.\n'
         '## 1. 지형 종류\n지형 지형 terrain 씬', 'A/지형씬제작'),
        ('# 일반화 벤치마크: 미학습 지형 10종 실측\n'
         '> 요지: 통과율과 실패 지형 지도.\n'
         '## 1. 벤치마크\n벤치마크 통과율 에피소드 평가', 'A/평가'),
        ('# Runpod 팀 운용 가이드\n> 요지: 권한 결제 네트워크 볼륨.\n'
         '## 1. 인프라\nRunpod 인프라 예산 GPU', 'C/운영'),
        ('# ROS2 개발환경: TF 좌표계와 RViz2\n> 요지: TF 와 SLAM 준비.\n'
         '## 1. TF\nTF 좌표계 ROS 2 SLAM Nav2', 'B/항법'),
    ]
    for text, want in cases:
        got, sc, why, sure = judge(text, voc)
        if not got or got[0] != want:
            return False, '「%s…」 를 %s 로 봐야 하는데 %s (점수 %s)' % (
                text[2:16], want, got, sorted(sc.items(), key=lambda kv: -kv[1])[:3])
        if not sure:
            return False, '「%s…」 는 확신해야 하는데 확인 필요로 나옴' % text[2:16]
    # 아무 신호도 없으면 «모르겠음» 이라 말해야 한다
    got, _, _, sure = judge('# 오늘 점심\n김치찌개를 먹었다.', voc)
    if got or sure:
        return False, '신호 없는 글에 영역을 붙임: %s' % got
    # 여러 영역에 걸친 글은 여럿을 돌려줘야 한다
    both, _, _, bsure = judge(
        '# 트랙 A 학습 결과를 트랙 B 항법에 잇는다\n'
        '> 요지: 정책 학습 결과와 SLAM Nav2 항법을 함께 본다.\n'
        '## 1. 정책\n학습 정책 보상 관측 파인튜닝\n'
        '## 2. 항법\nSLAM Nav2 TF ROS 2 좌표계', voc)
    if len(both) < 2 or not bsure:
        return False, '두 영역에 걸친 글을 %s 로만 봄' % both
    return True, ''


def main(lab=None):
    if lab is None:
        import docs_pages
        lab = next((p for p in docs_pages.LAB_CANDIDATES
                    if os.path.isdir(os.path.join(p, 'docs'))), None)
    if not lab:
        print('  [!] foothold-lab 을 못 찾음')
        return False
    voc = vocab(lab)
    if not voc:
        print('  [!] ROLES.md 에서 8갈래 표를 못 읽었습니다')
        return False
    ok, why = _kat(voc)
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    print('  정본 ROLES.md 에서 %d갈래 · 낱말 %d개'
          % (len(voc), sum(len(v) for v in voc.values())))
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
