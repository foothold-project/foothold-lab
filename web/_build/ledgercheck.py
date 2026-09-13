# -*- coding: utf-8 -*-
"""원장이 낡았는지 본다. 누수 방지 장치가 누수되는 것을 막는다.

★ 2026-08-28. `LEDGER.md` 는 「그거 어떻게 됐어?」의 답으로 만든 문서다.
  스스로 이렇게 적어 두었다. **「갱신 책임 = 세션, 매 작업 턴마다」**

  그런데 실측해 보니 **최종 갱신이 2026-08-20 에 멈춰 있었다.** 8일치가 비었다.
  그 사이 이슈 30개가 열리고 결정이 여럿 바뀌었는데 원장은 몰랐다.

  **누수를 막으려고 만든 장치가 누수됐다.** 문서에 「매 턴마다 갱신」이라고
  적는 것으로는 안 지켜진다. 오늘 하루에만 같은 부류를 다섯 번 봤다.
  커널 철칙 4: 관문이 없는 자리에서 규칙은 조용히 무너진다.

무엇을 보나
  1. `LEDGER.md` 의 「최종 갱신」 날짜가 며칠 지났는가
  2. 열려 있는 이슈 중 원장이 **한 번도 언급하지 않은 것**이 있는가

왜 이 둘인가
  날짜만 보면 «갱신했다고 날짜만 고치는» 것을 못 잡는다.
  열린 이슈와 대조해야 «실제로 담고 있는가»를 본다.
"""
import datetime
import io
import os
import re
import subprocess
import sys
import buildtime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

STALE_DAYS = 3          # 사흘. 이 팀은 하루에도 여러 번 결정이 바뀐다
UPDATED = re.compile(r'최종 갱신:\s*(20\d{2}-\d{2}-\d{2})')


def _lab():
    import docs_pages
    for p in docs_pages.LAB_CANDIDATES:
        if os.path.isdir(os.path.join(p, 'docs')):
            return p
    return None


SECTION = '## 📋 열린 이슈 전수'


def roster(t):
    """원장의 「열린 이슈 전수」 절만 떼어 낸다.

    ★ 2026-08-28 감사에서 잡혔다. 처음에는 **파일 전체**를 훑어 `#번호` 를 셌다.
      그러면 「대기 큐」나 「오늘 남긴 것」에 한 번 스친 번호까지 「담았다」로 세어
      실제로는 전수 절이 낡아도 통과한다. 실제로 그랬다.
      #64 는 닫혔는데 전수 절에 열린 것으로 남아 있었고, #87 은 빠져 있었는데
      관문은 「원장이 지금을 담고 있습니다」를 찍었다.

      **검사한다고 말한 그 자리를 봐야 한다.** 파일 어딘가가 아니라.
    """
    i = t.find(SECTION)
    if i < 0:
        return None
    j = t.find(chr(10) + '## ', i + len(SECTION))
    return t[i:j if j > 0 else len(t)]


def _issues(lab, state):
    """해당 상태의 이슈. gh 가 없거나 인증이 없으면 None(검사 생략).

    ★ 2026-09-09. 번호만 받다가 `updatedAt` 을 함께 받게 바꿨다. 원장을 «봇이»
      쓰기 시작하면서(#328), 관문이 보는 어긋남에는 두 부류가 생겼다.
        · 봇이 아직 안 민 것   -> 20여초 뒤 저절로 맞는다. 세울 일이 아니다
        · 봇이 돌았는데도 없는 것 -> 진짜 결함이다. 세워야 한다
      그 둘을 가르려면 «이슈가 언제 바뀌었나» 가 필요하다.
    """
    try:
        r = subprocess.run(['gh', 'issue', 'list', '--state', state,
                            '--limit', '100', '--json', 'number,updatedAt'],
                           cwd=lab, capture_output=True, text=True,
                           encoding='utf-8', timeout=30)
        if r.returncode != 0:
            return None
        import json
        return {i['number']: i.get('updatedAt') or ''
                for i in json.loads(r.stdout or '[]')}
    except Exception:
        return None


def _utc(s):
    """ISO 문자열 -> UTC datetime. 못 읽으면 None (판단을 미룬다)."""
    if not s:
        return None
    try:
        d = datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except ValueError:
        return None
    if d.tzinfo is None:
        return d.replace(tzinfo=datetime.timezone.utc)
    return d.astimezone(datetime.timezone.utc)


def ledger_written_at(lab):
    """원장이 «마지막으로 쓰인» 시각. 머리말 날짜가 아니라 그 파일의 커밋 시각이다.

    머리말은 날짜뿐이라 20초짜리 경합을 가릴 수 없다. 커밋 시각은 봇이 실제로
    민 순간이고, 사람이 손으로 고쳐도 같은 뜻이 된다.
    """
    try:
        r = subprocess.run(['git', '-C', lab, 'log', '-1', '--format=%cI',
                            '--', 'docs/LEDGER.md'],
                           capture_output=True, text=True, timeout=20,
                           encoding='utf-8')
        if r.returncode == 0:
            return _utc((r.stdout or '').strip())
    except Exception:
        pass
    return None


def verdict(issue_at, ledger_at):
    """이 어긋남이 «봇 대기» 인가 «진짜 결함» 인가.

    이슈가 원장보다 «뒤에» 바뀌었으면 봇이 아직 안 민 것이다.
    원장보다 «앞에» 바뀌었는데 없으면 봇이 돌았는데도 빠진 것이고 결함이다.
    시각을 하나라도 못 읽으면 결함 쪽으로 본다. 관문은 모를 때 느슨해지면 안 된다.
    """
    a, b = _utc(issue_at), ledger_at
    if a is None or b is None:
        return 'real'
    return 'pending' if a > b else 'real'



def _open_issues(lab):
    return _issues(lab, 'open')


def _kat(today):
    """★ 답을 아는 입력으로 먼저 시험한다."""
    old = '> 최종 갱신: 2026-08-01'
    m = UPDATED.search(old)
    if not m:
        return False, '갱신일을 못 읽음'
    d = datetime.date.fromisoformat(m.group(1))
    if (today - d).days < STALE_DAYS:
        return False, '오래된 날짜를 낡지 않았다고 봄'
    if UPDATED.search('갱신한 적 없음'):
        return False, '없는 날짜를 읽었다고 함'

    # ★ 절을 «떼어 내는가». 처음에 이걸 안 시험해서 파일 전체를 훑는 코드가
    #   통과했다. 다른 절에만 있는 번호는 세면 안 된다.
    n = chr(10)
    doc = ('# 원장' + n +
           '> 최종 갱신: 2026-08-28' + n +
           '## 🔧 대기 큐' + n +
           '여기서 #999 를 한 번 스쳤다' + n +
           SECTION + ' (3건)' + n +
           '#11 #22' + n +
           '## 📌 오늘 남긴 것' + n +
           '여기서 #888 을 스쳤다' + n)
    sec = roster(doc)
    if sec is None:
        return False, '전수 절을 못 찾음'
    got = sorted(int(x) for x in re.findall(r'#(\d{1,4})', sec))
    if got != [11, 22]:
        return False, '절 밖 번호까지 셌다: %s (11·22 만 세야 한다)' % got
    if roster('절이 없는 글') is not None:
        return False, '없는 절을 있다고 함'

    # ★ 2026-09-09. «봇 대기» 와 «진짜 결함» 을 가르는 그 판정을 먼저 시험한다.
    #   이걸 안 시험하면, 전부 대기로 보는 코드도 조용히 통과한다.
    #   그러면 관문이 살아 있으나 아무것도 안 막는 상태가 된다.
    lw = _utc('2026-09-09T01:00:00Z')
    if verdict('2026-09-09T01:00:20Z', lw) != 'pending':
        return False, '원장보다 뒤에 바뀐 이슈를 결함으로 봄 (봇을 기다려야 한다)'
    if verdict('2026-09-09T00:59:40Z', lw) != 'real':
        return False, '봇이 돌고 난 뒤에도 빠진 것을 대기로 봄 (이건 막아야 한다)'
    if verdict('', lw) != 'real' or verdict('2026-09-09T01:00:20Z', None) != 'real':
        return False, '시각을 모를 때 느슨해짐'
    # 시간대가 섞여도 같은 순간이면 같게 본다. KST 로 온 값이 UTC 를 이기면 안 된다.
    if verdict('2026-09-09T10:00:20+09:00', lw) != 'pending':
        return False, 'KST 표기를 못 맞춤 (10:00:20+09:00 = 01:00:20Z 다)'
    if verdict('2026-09-09T10:00:00+09:00', lw) != 'real':
        return False, '같은 순간을 «뒤» 로 봄 (10:00+09:00 = 01:00Z 그 자체다)'
    if _utc('말이 안 되는 값') is not None:
        return False, '못 읽는 시각을 읽었다고 함'
    return True, ''


def main(today=None):
    today = today or buildtime.today()
    ok, why = _kat(today)
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False

    lab = _lab()
    if not lab:
        print('  [!] foothold-lab 을 못 찾음. 원장 검사 건너뜀')
        return True
    p = os.path.join(lab, 'docs', 'LEDGER.md')
    if not os.path.isfile(p):
        print('  [!] LEDGER.md 가 없습니다')
        return False
    t = io.open(p, encoding='utf-8', newline=None).read()

    m = UPDATED.search(t)
    if not m:
        print('  [!] LEDGER 에 「최종 갱신: YYYY-MM-DD」 가 없습니다')
        return False
    age = (today - datetime.date.fromisoformat(m.group(1))).days

    bad = False
    if age > STALE_DAYS:
        print('  ★ 원장이 %d일 낡았습니다 (기준 %d일).' % (age, STALE_DAYS))
        print('    「그거 어떻게 됐어?」의 답이 낡으면 다음 세션이 같은 자리에서 못 잇습니다.')
        bad = True

    sec = roster(t)
    if sec is None:
        print('  ★ 「%s」 절이 없습니다.' % SECTION.lstrip('# ').strip())
        return False

    op = _open_issues(lab)
    cl = _issues(lab, 'closed')
    if op is None or cl is None:
        print('  갱신 %s (%d일 전) · 이슈 대조는 건너뜀 (gh 사용 불가)'
              % (m.group(1), age))
        return not bad

    cited = {int(x) for x in re.findall(r'#(\d{1,4})', sec)}
    missing = sorted(set(op) - cited)
    dead = sorted(cited & set(cl))
    print('  갱신 %s (%d일 전) · 열린 이슈 %d개 · 전수 절이 담은 것 %d개'
          % (m.group(1), age, len(op), len(cited & set(op))))

    # ★ 2026-09-09. 어긋남을 두 부류로 가른다 (팀 결정 · foothold-lab#346).
    #   #328 로 `ledger-sync` 봇이 이 절을 쓰기 시작한 뒤, 이슈가 열리거나 닫힌
    #   직후 20여초 동안은 관문이 «반드시» 어긋난 것을 본다. 봇이 아직 안 민
    #   것뿐인데 배포가 섰다. 2026-09-09 하루에 세 번 났고, 배포 한 번에 빌드를
    #   다섯 번 돌렸다.
    #   거짓 경보를 내는 관문은 진짜 경보도 무시되게 만든다. 그러면 관문이
    #   살아 있으나 아무것도 안 막는다.
    #   가르는 기준은 «시각» 이다. 워크플로 실행 상태를 따로 묻지 않는다.
    #   그 조회가 실패하면 판단이 안 서지만, 시각은 이미 받은 데이터에 있다.
    lw = ledger_written_at(lab)
    if lw is None:
        print('  [!] 원장이 마지막으로 쓰인 시각을 못 읽었습니다. 전부 결함으로 봅니다')

    def _split(nums, src):
        wait, real = [], []
        for x in nums:
            (wait if verdict(src.get(x), lw) == 'pending' else real).append(x)
        return wait, real

    m_wait, m_real = _split(missing, op)
    d_wait, d_real = _split(dead, cl)

    if m_wait or d_wait:
        it = ' '.join('#%d' % x for x in (m_wait + d_wait)[:12])
        print('  · 봇이 아직 안 민 것 %d개: %s'
              % (len(m_wait) + len(d_wait), it))
        print('    `ledger-sync` 가 곧 밉니다. 결함이 아니라 대기입니다')

    # ① 빠진 것. 하나라도 빠지면 「전수」가 아니다.
    #    처음에는 «절반 초과» 일 때만 잡았는데, 15개까지 빠져도 통과하는 기준은
    #    전수 명부의 기준이 아니다.
    if m_real:
        print('  ★ 열린 이슈 %d개가 전수 절에 없습니다: %s'
              % (len(m_real), ' '.join('#%d' % x for x in m_real[:12])))
        print('    봇이 «돌고 난 뒤에도» 없습니다. 손이 마커 밖을 안 고쳤거나 봇이 틀렸습니다')
        bad = True
    # ② 죽은 것. 닫힌 이슈가 열린 명부에 남아 있으면 다음 세션이 헛일을 한다.
    if d_real:
        print('  ★ 닫힌 이슈 %d개가 아직 전수 절에 있습니다: %s'
              % (len(d_real), ' '.join('#%d' % x for x in d_real[:12])))
        bad = True


    if bad:
        return False
    print('  원장이 지금을 담고 있습니다')
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
