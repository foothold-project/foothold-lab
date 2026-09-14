# -*- coding: utf-8 -*-
"""「판」을 「에피소드」로 바꾼다. 먼저 «바꿀 자리를 보여주고» 시킬 때만 쓴다.

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (고의 결함 주입 검출 시험 · `--selftest`)

## 왜 도구로 만드나

정규식 한 번으로 쓸면 안 된다. **같은 글자를 쓰는 다른 말**이 섞여 있다.

    발판 · 조판 · 간판 · 상판 · 밑판 · 판정 · 판별 · 판단 · 판례 · 재판 · 출판
    「판 v2.0」(문서 판 번호) · 「중간 판 A」(모델 판 번호) · 「다음 판에」

종합보고서(#413)에서 이 함정을 다 만났다. 숫자 뒤의 「판」만 겨누고, 위 낱말이
가까이 있으면 건너뛴다. 그리고 바꾼 뒤 **조사를 다시 센다.** 「에피소드가」
「에피소드는」 같은 것이 실제로 두 번 생겼다.

## 쓰는 법

    python tools/pan_to_episode.py <파일...>            보여주기만 한다
    python tools/pan_to_episode.py --write <파일...>    실제로 쓴다
    python tools/pan_to_episode.py --selftest           알려진 답 시험

## 안 하는 것

**남의 문서는 이 도구로도 바로 안 쓴다.** 작성자가 내가 아니면 `--write` 를
줘도 멈춘다. 고치려면 PR 로 올려 컨펌을 받는다 (팀장 규칙).
`--force-owner` 로 그 판정을 끌 수 있지만, PR 브랜치에서만 쓴다.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

ME = '오흥재'

# 「판」이 들어가지만 에피소드가 아닌 말. 앞 8자 · 뒤 6자 안에 있으면 건너뛴다.
KEEP = ('발판', '조판', '간판', '상판', '밑판', '철판', '유리판',
        '판정', '판별', '판단', '판례', '재판', '출판', '판매', '한판',
        '판 이력', '판 번호', '중간 판', '다음 판', '이번 판', '판이 바뀌',
        '승제', '승부', '판을 벌', '판이 커')

# 숫자(쉼표 포함) 뒤에 붙은 「판」. 「판정」 같은 말은 뒤 글자로 뺀다.
# ★ `\s` 는 «줄바꿈» 도 먹는다. 그래서 앞 줄이 숫자로 끝나고 다음 줄이 「판」으로
#   시작하면 두 줄이 한 줄로 붙는다. 2026-09-14 에 표 머리줄이 실제로 그렇게
#   앞 줄 CSV 뒤에 들러붙었다. 같은 줄 안의 공백만 본다.
PAT = re.compile(r'(?P<num>[0-9][0-9,]*)(?P<sp>[ 	]*)판(?![정별단례])')

# 「에피소드」 뒤에 오면 안 되는 조사. 받침이 없으므로 이쪽을 쓴다.
#   ★ 두 글자짜리를 먼저 본다. 「20판으로」 -> 「20 에피소드로」.
#     한 글자만 보면 «으» 가 안 걸려 「에피소드로」가 된다 (전수로 세다 찾았다).
#   의 · 씩 · 만 · 에서 · 뿐 · 에는 은 받침과 무관해 그대로 둔다.
FIXPOST2 = {'으로': '로', '이라': '라', '이며': '며', '이가': '가'}
FIXPOST = {'이': '가', '은': '는', '을': '를', '과': '와'}
# ★ 「100판이고」 의 «이» 는 주격 조사가 아니라 계사다. «가» 로 바꾸면
#   「100 에피소드가고」 라는 말이 안 되는 글이 된다. 2026-09-14 에 실제로
#   문서 한 줄을 그렇게 망가뜨렸다. 뒤에 서술어 어미가 오면 «이» 를 남긴다.
COPULA = re.compile(r'^(?:고|다|며|라|지만|어서|니까|었|므로|든|기에|나)')


def author_of(text):
    m = re.search(r'작성[:：]\s*([^·\n]+)', text)
    return m.group(1).strip() if m else ''


def convert(text):
    """반환: (바뀐 글, [(자리, 전, 후)])."""
    out, hits, last = [], [], 0
    for m in PAT.finditer(text):
        # 뒤쪽 창이 좁으면 「3판 2승제」의 «승제» 를 못 본다 (자기시험이 잡았다)
        seg = text[max(0, m.start() - 8):m.end() + 6]
        if any(k in seg for k in KEEP):
            continue
        out.append(text[last:m.start()])
        rep = m.group('num') + ' 에피소드'
        # 바로 뒤 조사를 고친다. 「100판이」 -> 「100 에피소드가」
        j = m.end()
        post2 = text[j:j + 2]
        post = text[j:j + 1]
        if post2 in FIXPOST2:
            rep += FIXPOST2[post2]
            j += 2
        elif post == '이' and COPULA.match(text[j + 1:j + 3]):
            pass                      # 계사 «이» 다. 건드리지 않는다
        elif post in FIXPOST:
            rep += FIXPOST[post]
            j += 1
        out.append(rep)
        hits.append((m.start(), text[m.start():m.end() + 1], rep))
        last = j
    out.append(text[last:])
    return ''.join(out), hits


def selftest():
    """알려진 답. 바꿔야 할 것과 «절대 건드리면 안 되는 것»."""
    cases = [
        ('100판을 돌렸다', '100 에피소드를 돌렸다'),
        ('14,400 판이 분모다', '14,400 에피소드가 분모다'),
        ('실패 52판 가운데 27판은', '실패 52 에피소드 가운데 27 에피소드는'),
        ('지형마다 100 판.', '지형마다 100 에피소드.'),
        ('20판으로 쟀다', '20 에피소드로 쟀다'),
        ('100판의 절반', '100 에피소드의 절반'),
        ('50판씩 돌린다', '50 에피소드씩 돌린다'),
        ('30판에서 나왔다', '30 에피소드에서 나왔다'),
        # 건드리면 안 되는 것
        ('발판이 0.75 m 다', None),
        ('판 v2.0 이다', None),
        ('중간 판 A 와 비교', None),
        ('휴대폰에서 조판이 무너진다', None),
        ('네 축의 판정이다', None),
        ('3판 2승제', None),
        # 앞 줄이 숫자로 끝나고 다음 줄이 「판」으로 시작해도 붙이면 안 된다
        ('0.7523' + chr(10) + '        판  종합', None),
        # 계사 «이» 를 주격 조사로 잘못 보면 말이 안 되는 글이 된다
        ('같은 100판이고, 다음은', '같은 100 에피소드이고, 다음은'),
        ('100판이 분모다', '100 에피소드가 분모다'),          # 「한판」 부류는 아니지만 숫자+판이라 잡힌다
    ]
    ok = 0
    for src, want in cases:
        got, hits = convert(src)
        if want is None:
            good = (got == src)
            mark = 'OK ' if good else '[X]'
            print('  %s 안 건드림  「%s」%s' % (mark, src, '' if good else ' -> ' + got))
        else:
            good = (got == want)
            mark = 'OK ' if good else '[X]'
            print('  %s 바꿈       「%s」 -> 「%s」%s'
                  % (mark, src, got, '' if good else '  (기대 ' + want + ')'))
        ok += good
    # 조사가 새로 틀리지 않았나
    bad = 0
    for src, want in cases:
        got, _ = convert(src)
        if re.search(r'에피소드(?:이(?!고|다|며|라|지만|어서|니까|었|므로|든|기에|나)|은|을|과|으로)', got):
            bad += 1
            print('  [X] 조사 틀림: %s' % got)
    print('  %d/%d · 조사 오류 %d' % (ok, len(cases), bad))
    return ok == len(cases) and bad == 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    write = '--write' in sys.argv
    force = '--force-owner' in sys.argv
    if '--selftest' in sys.argv:
        return 0 if selftest() else 1
    if not args:
        print(__doc__.split('## 쓰는 법')[1].split('## 안 하는 것')[0].strip())
        return 2
    total = blocked = 0
    for p in args:
        if not os.path.isfile(p):
            print('  [!] 없는 파일: %s' % p)
            continue
        t = io.open(p, encoding='utf-8').read()
        new, hits = convert(t)
        if not hits:
            continue
        who = author_of(t)
        mine = (who == ME) or (who in ('자동 수집', ''))
        tag = '' if mine else '   <- %s 의 문서. PR 로 컨펌받는다' % (who or '작성자 미상')
        print('  %-56s %3d곳%s' % (p.replace(os.sep, '/'), len(hits), tag))
        total += len(hits)
        for _, a, b in hits[:3]:
            print('        %-18s -> %s' % (a.strip(), b.strip()))
        if len(hits) > 3:
            print('        ... %d곳 더' % (len(hits) - 3))
        if write:
            if not mine and not force:
                blocked += 1
                continue
            io.open(p, 'w', encoding='utf-8', newline='\n').write(new)
            # 쓴 «뒤» 에 되읽어 조사를 다시 센다
            back = io.open(p, encoding='utf-8').read()
            wrong = re.findall(r'에피소드(?:이(?!고|다|며|라|지만|어서|니까|었|므로|든|기에|나)|은|을|과|으로)', back)
            if wrong:
                print('        [!] 조사가 틀렸습니다 %d곳' % len(wrong))
    print('  합계 %d곳%s' % (total, ' · 남의 문서라 안 쓴 파일 %d개' % blocked if blocked else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
