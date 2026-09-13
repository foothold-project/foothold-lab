# -*- coding: utf-8 -*-
"""웹에 ASCII 도식이 남아 있는지 검사  (빌드 [1.82] 단계)

  세션 규칙 2: 웹에 올리는 구조도는 ASCII 금지. SVG·이미지·표로 한다.
  그런데 규칙을 정한 뒤에도 flow 페이지에 10개가 남아 있었고 팀장이 발견했다(2026-08-11).
  사람이 "새로 만들 때만" 규칙을 지키고 이미 올라간 것은 잊었기 때문이다.
  그래서 기계가 매 빌드마다 전 페이지를 다시 훑는다.

  판정: <pre> 블록 안에 **도형 문자**(박스 그리기·화살표·트리 가지)가 있으면 도식으로 본다.
  코드 블록은 도형 문자를 쓰지 않으므로 걸리지 않는다. 코드에 흔한 화살표(->, =>)도 제외한다.
"""
import io, os, re

# 박스 그리기(U+2500~257F) · 블록(U+2580~259F) 만 도식의 증거로 본다.
#   화살표(→ ↓)는 제외한다. 측정 로그에 "보상 13.94 → 22.88" 처럼 정당하게 쓰이고,
#   그것까지 막으면 사람이 검사기를 끄게 된다. 막아야 하는 것은 **선으로 그린 그림**이다.
SHAPE = re.compile(r'[─-╿▀-▟]')
PRE = re.compile(r'<pre[^>]*>(.*?)</pre>', re.S)
TAG = re.compile(r'<[^>]+>')


def check_file(path):
    s = io.open(path, encoding='utf-8').read()
    hits = []
    for m in PRE.finditer(s):
        body = TAG.sub('', m.group(1))
        shapes = SHAPE.findall(body)
        if len(shapes) >= 3:                       # 한두 개는 본문 화살표일 수 있다
            line = s[:m.start()].count('\n') + 1
            head = (body.strip().split('\n') or [''])[0][:40]
            hits.append((line, ''.join(sorted(set(shapes)))[:10], head))
    return hits


GRAND = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'ascii_grandfather.txt')


def grandfathered():
    """아직 안 고친 빚. 규칙 면제가 아니라 «남은 일» 이다.

    이 파일에 적힌 페이지는 위반을 세되 배포를 세우지 않는다. 새로 생기는 것은
    그대로 막힌다. 명부가 길어지면 그만큼 일이 남은 것이고, 줄어들면 갚은 것이다.
    """
    if not os.path.exists(GRAND):
        return frozenset()
    out = []
    for line in io.open(GRAND, encoding='utf-8'):
        line = line.split('#')[0].strip()
        if line:
            out.append(line)
    return frozenset(out)


def main(vault, pages):
    # ★ 2026-09-05. 전에는 통과할 때 «아무 숫자도» 안 찍었다. 그래서 호출 자리의
    #   PAGES 가 아직 54장일 때 돌아도 화면은 성공과 구별되지 않았고, 못 본 55장
    #   안에 위반 3건이 살아 있었다. 본 장수를 찍으면 목록이 짧아진 것이 눈에 띈다.
    #   커널 원칙 2: 조용한 실패를 소리 나게 만든다.
    bad = []
    seen = 0
    # ★ 2026-09-10. PAGES 는 루트 페이지만 담는다. 하위 폴더(team-meang/)와
    #   assets/ 아래 페이지가 빠져 「검사했다」가 거짓이 된다.
    #   오늘 그 부류로 넷을 봤다 (감사 F-03 · 파비콘 주입·워드마크·검증).
    #   배포 전수의 정본은 searchbox.public_pages 하나다.
    import searchbox
    for f in sorted(searchbox.public_pages(vault, pages)):
        p = os.path.join(vault, f)
        if not os.path.exists(p):
            continue
        seen += 1
        for line, shapes, head in check_file(p):
            bad.append('%s:%d  도형문자[%s]  %s' % (f, line, shapes, head))
    old = grandfathered()
    owed = [b for b in bad if b.split(':')[0] in old]
    fresh = [b for b in bad if b.split(':')[0] not in old]
    if fresh:
        print('  검사 %d장 · ★ 웹에 ASCII 도식이 남아 있습니다 %d건 (세션 규칙 2)'
              % (seen, len(fresh)))
        for b in fresh:
            print('     %s' % b)
        return False
    if owed:
        print('  검사 %d장 · 새 위반 없음 · 유예 명부 %d건 (아직 안 고친 빚)'
              % (seen, len(owed)))
        for b in owed:
            print('     %s' % b)
        return True
    print('  검사 %d장 · ASCII 도식 없음' % seen)
    return True
