# -*- coding: utf-8 -*-
"""모든 페이지 맨 아래에 «이 웹이 언제 것인가» 를 박는다.

★ 2026-08-27. 팀원이 링크를 열었을 때 그 페이지가 **어제 것인지 오늘 것인지**
  알 방법이 없었다. 결정이 자주 바뀌는 시기라 이건 실질적인 문제다.
  회의에서 「웹에 그렇게 안 적혀 있던데요」가 나올 때, 서로 다른 판을 보고
  있었는지 아닌지를 가릴 수 있어야 한다.

판 번호
  `SITE_VERSION` 을 손으로 올린다. 자동으로 올리지 않는다. 판이 바뀌었다는 것은
  **사람이 판단하는 일**이고, 빌드 횟수와는 관계가 없다.

  v1.9  8갈래 작업 영역 · 마일스톤 4개 · md 게시 체계까지 (2026-08-27)
  v2.0.0  전면 리빌드 (2026-09-01) · 기획발표 판
          허브 6 + 표지 재설계 · 전역바 고정 · 테마 토글 정합 · NEW 배지
          WBS 를 그림으로 · 이슈 출처 표기 · 커리큘럼을 백과와 같은 틀로
          기술 4쪽 위키 흡수 완료 (하단 위키 네비·푸터 제거)
  v2.0  기획발표(9/4) 시점의 구조 개편 · 네비 재설계 -> 그때 올린다
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)

SITE_VERSION = 'v2.0.0'
A, B = '<!--stamp:v1-->', '<!--/stamp:v1-->'

CSS = '''<style id="stamp-css">
/* ★ 실측 (팀장 8/31): 푸터 폭이 944 / 995 / 1100 / 1136 로 제각각이었다.
   페이지마다 다른 --w 를 따라갔기 때문. 본문과 같은 1040 한 값으로. */
/* ★ 9/1 팀장 지적 「페이지 넘어갈 때마다 위아래로 흔들리지 말고 고정하자」.
   실측: 문서 높이가 678(기획) ~ 2514(연구) 로 제각각이라 짧은 허브에서는
   푸터가 화면 «중간» 에 떴다. body 를 세로 flex 로 세우고 푸터에 margin-top:auto
   를 주면, 내용이 짧아도 푸터가 늘 화면 바닥 같은 자리에 선다. */
body{min-height:100vh;display:flex;flex-direction:column}
body>.bstamp{margin-top:auto}
/* ★ 9/1 두 번째 실측 · 팀장 지적 「brief 컨텐츠가 1040 으로 안 늘어난다」.
   내가 만든 회귀다. body 를 flex 로 세우면 margin:0 auto 를 가진 자식은
   «내용 크기» 로 줄어든다. 푸터에만 width:100% 를 줬고 본문 컨테이너는
   안 쓸었다 (brief 938 · hub-tech 944 · 나머지는 내용이 넓어 우연히 1040).
   flex 아이템이 되는 모든 블록 컨테이너에 같은 처방을 준다. */
body>.wrap,body>main,body>.shell,body>section,body>article{width:100%}
body>*{flex-shrink:0}
/* ★ 9/1 두 번째 실측: body 를 flex 로 세우자 푸터가 «내용 크기» 로 줄었다
   (1040 -> 605). flex 아이템에 margin:auto 를 주면 그렇게 된다.
   width:100% 로 먼저 채우고 max-width 로 자른다. */
.bstamp{width:100%;max-width:1040px!important;box-sizing:border-box;
  margin:40px auto 22px;
  padding:12px 18px 0;
  border-top:1px solid var(--line,#e5e2dc);display:flex;flex-wrap:wrap;gap:6px 14px;
  align-items:baseline;font-size:.74rem;color:var(--ink-3,#8a8580);line-height:1.7}
.bstamp b{color:var(--ink-2,#57534e);font-weight:600}
.bstamp .sv{font-variant-numeric:tabular-nums;letter-spacing:.02em}
.bstamp .gap{flex:1}
/* ★ 2026-09-09 실측. width:100% 에 좀은 화면용 좌우 마진 14px 을 더하니
   띄가 본문보다 28px 커졌다. tech-* 네 장이 390px 에서 가로로 30px 밀렸다.
   (다른 페이지는 .wrap 안이라 드러나지 않았다. 생김새가 가린 결함이다.)
   좀은 화면에서는 width 를 다시 auto 로 돌려 마진이 폭을 «빼가게» 한다. */
@media (max-width:640px){.bstamp{width:auto;margin:28px 14px 18px}}
</style>'''


def _bar(when):
    return (A + '<div class="bstamp">'
            '<span><b>FOOTHOLD</b> 프로젝트 웹 <span class="sv">%s</span></span>'
            '<span>이 페이지 갱신 <span class="sv">%s</span></span>'
            '<span class="gap"></span>'
            '<span>바뀐 내용은 <a href="notice-latest.html">팀 공지</a>와 '
            '<a href="decisions-log.html">결정 로그</a>에</span>'
            '</div>' + B) % (SITE_VERSION, when)


def _kat(when):
    """★ 답을 아는 입력으로 먼저 시험한다. 두 번 붙여도 하나만 남아야 한다."""
    doc = '<html><body><p>x</p></body></html>'
    once = apply_text(doc, when)
    twice = apply_text(once, when)
    if once != twice:
        return False, '두 번 돌리면 결과가 달라짐(중복 누적)'
    # 「bstamp」 는 CSS 선택자에도 여러 번 나온다. 띠의 개수는 «마커»로 센다.
    if once.count(A) != 1:
        return False, '띠가 %d개' % once.count(A)
    if SITE_VERSION not in once or when not in once:
        return False, '판 번호나 시각이 안 박힘'
    return True, ''


def apply_text(t, when):
    # 앞의 공백까지 함께 걷어내야 «두 번 돌리면 줄바꿈이 하나 는다». 그 한 줄이
    # 자기시험에 걸렸다. 눈에 안 보이는 차이라 손으로는 못 잡았을 것이다.
    t = re.sub(r'\s*' + re.escape(A) + r'.*?' + re.escape(B), '', t, flags=re.S)
    # ★ 9/1: 여기가 «이미 있으면 건너뛴다» 였다. 그래서 표지에는 옛 도장 CSS
    #   (.bstamp{max-width:var(--w,1100px)}) 가 박제돼, 새 규칙을 고쳐도 반영이
    #   안 됐다. ia-css 와 똑같은 부류다 (철칙 4). 통째로 갈아끼운다.
    t = re.sub(r'<style id="stamp-css">.*?</style>\s*', '', t, flags=re.S)
    if True:
        if '</head>' in t:
            t = t.replace('</head>', CSS + '\n</head>', 1)
        else:
            m = re.search(r'</style>', t)
            t = (t[:m.end()] + '\n' + CSS + t[m.end():]) if m else (CSS + '\n' + t)
    bar = _bar(when)
    if '</body>' in t:
        return t.replace('</body>', bar + '</body>', 1)
    return t.rstrip() + bar + '\n'


def main(when):
    ok, why = _kat(when)
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    n = 0
    import hubgen as _hg
    for f in sorted(os.listdir(VAULT)):
        # ★ 팀장 9/1: 커리큘럼은 화면마다 푸터가 따라붙어 보인다.
        #   한 화면씩 넘기는 뷰어라 덱과 같은 성격이다. 도장을 안 찍는다.
        if f == 'curriculum.html' or f in _hg.DECK_PAGES:
            continue                      # 전체화면 덱은 도장이 슬라이드를 덮는다
        if not f.endswith('.html'):
            continue
        p = os.path.join(VAULT, f)
        t = io.open(p, encoding='utf-8', newline=None).read()
        io.open(p, 'w', encoding='utf-8', newline='\n').write(apply_text(t, when))
        n += 1
    print('  자가검증 통과 · 판 %s · %s · %d개 페이지' % (SITE_VERSION, when, n))
    if n == 0:
        print('  [!] 한 장도 못 찍었습니다.')
        return False
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main('2026-01-01 00:00') else 1)
