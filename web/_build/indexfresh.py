# -*- coding: utf-8 -*-
"""색인이 «지금 페이지» 를 담고 있는가. 색인 뒤에 글자가 늘어난 것을 잡는다.

★ 2026-09-09 실측에서 나왔다. 홈의 현황 띠(기간 5주차 · 다음 마일스톤 D-21 ·
  미결 안건 6건 · 설계도 5절)를 검색하면 0건이었다. 화면에는 있는데.

  원인은 순서였다. `[1.8986]` 이 색인을 만든 «뒤» 에 `[1.899] 자기 참조 사실
  집계` 가 그 띠를 페이지에 쓴다. 색인은 그 전 모습을 담고 있었다.

  이 저장소가 반복해서 겪은 부류다. PAGES 는 빌드 도중 늘어나고, 앞 단계가 본
  것은 뒤 단계가 바꾼다. 그때마다 «재주입» 을 하나 더 붙여 막아 왔는데,
  **재주입을 붙였는지 아무도 검사하지 않았다.** 그래서 또 났다.

  개별 단계를 금지하는 조항은 쓸모가 없다. 다음번엔 다른 단계가 같은 일을 한다.
  그래서 결과를 본다. 「화면에 있는 글자가 색인에 있는가」 하나만 본다.

무엇을 세지 않나
  빌드 도장(<!--stamp:v1-->)은 뺀다. 모든 페이지에 같은 글이 붙어 검색을 흐린다.
  일부러 안 담는 것이고, 담기면 오히려 그게 결함이다.


★ 이 관문이 «못 잡는 것»
  - 색인의 «내용이 맞는가» 는 안 본다. 지금 페이지를 담고 있는지만 본다.
    본문이 통째로 틀려도 색인에 그 글자가 있으면 통과한다.
  - 배포본에만 있는 페이지는 `searchbox.FROM_SITE` 가 담당한다.
  - 도장(stamp)은 일부러 뺀다. 그것만 바뀐 것은 «안 바뀐 것» 으로 본다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

STAMP = re.compile(r'<!--stamp:v1-->.*?<!--/stamp:v1-->', re.S)
RUN = 24        # 이만큼 연달아 없으면 «빠진 것» 으로 본다


def _norm(s):
    return re.sub(r'\s+', '', s)


def missing_runs(visible, indexed, run=RUN):
    """화면 글자 중 색인에 없는 구간. 둘 다 «공백 없앤» 문자열이어야 한다.

    ★ 경계를 조심한다. 색인은 절마다 나뉘므로 절 경계를 걸친 창은 어느 한
      레코드에도 통째로 들어 있지 않다. 그래서 레코드를 «순서대로 이어 붙인»
      문자열과 맞대야 한다. 이걸 안 하면 멀쩡한 페이지가 유실로 잡힌다.
      (처음에 이 실수를 해서 index.html 이 113자 유실로 보였다.)
    """
    out = []
    i = 0
    n = len(visible)
    while i <= n - run:
        if visible[i:i + run] not in indexed:
            j = i
            while j <= n - run and visible[j:j + run] not in indexed:
                j += 1
            out.append(visible[i:j + run])
            i = j + run
        else:
            i += run // 2
    return out


def _kat():
    """알려진 답으로 먼저 시험한다."""
    vis = '가나다' * 30
    if missing_runs(vis, vis):
        return False, '같은 글을 빠졌다고 함'
    if not missing_runs(vis + 'ZZ' * 40, vis):
        return False, '뒤에 붙은 40자를 못 잡음'
    # 절 경계. 색인이 둘로 나뉘어도 이어 붙이면 연속이다.
    a, b = '가나다' * 20, '라마바' * 20
    if missing_runs(a + b, a + b):
        return False, '절 경계를 유실로 봄'
    # 도장은 검사 대상이 아니다
    t = ('<div class="wrap"><p>본문</p>'
         '<!--stamp:v1--><div>이 페이지 갱신 2026-01-01</div><!--/stamp:v1-->'
         '</div>')
    if '갱신' in STAMP.sub(' ', t):
        return False, '도장을 못 걷어냄'
    return True, ''


def main(vault, pages):
    import searchbox
    import json
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False

    p = os.path.join(vault, 'assets', 'search-index.json')
    if not os.path.isfile(p):
        print('  [!] 색인이 없습니다')
        return False
    idx = json.load(io.open(p, encoding='utf-8'))
    per = {}
    for e in idx:
        per.setdefault(e['p'], []).append(e['x'])

    bad = []
    seen = 0
    for f in sorted(searchbox.public_pages(vault, pages)):
        fp = os.path.join(vault, f)
        if not os.path.isfile(fp):
            continue
        raw = STAMP.sub(' ', io.open(fp, encoding='utf-8',
                                     errors='replace').read())
        m = re.search(r'<div class="wrap">(.*)', raw, re.S)
        vis = _norm(searchbox.strip_tags(m.group(1) if m else raw))
        got = _norm(''.join(per.get(f, [])))
        seen += 1
        runs = missing_runs(vis, got)
        if runs:
            bad.append((f, sum(len(x) for x in runs), len(vis), runs[0]))

    if bad:
        bad.sort(key=lambda r: -r[1])
        print('  [!] 색인이 «지금 페이지» 를 안 담고 있습니다 (%d장):' % len(bad))
        for f, lost, tot, sample in bad[:6]:
            print('      %s · %d자 / %d' % (f, lost, tot))
            print('         빠진 글: %s' % sample[:90])
        print('      색인을 만든 «뒤» 에 그 글자를 쓴 단계가 있습니다.')
        print('      그 단계 뒤로 검색 재주입을 옮기거나 하나 더 붙이세요.')
        return False
    # ★ 2026-09-09. 「대상에 닿지 못한 것」과 「위반이 없는 것」은 다른 사실인데
    #   같은 «통과» 를 내고 있었다. 빈 볼트로 돌려 보고 알았다.
    #   관문이 0개를 검사하고 통과하면, 목록이 비는 순간 조용히 무력해진다.
    if seen == 0:
        print('  [!] 공개 페이지를 한 장도 못 봤습니다. 검사가 헛돌았습니다')
        return False
    print('  자기시험 통과 · %d장 전부 색인이 지금 모습을 담고 있습니다 (도장 제외)'
          % seen)
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main(os.path.dirname(HERE), []) else 1)
