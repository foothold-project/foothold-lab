# -*- coding: utf-8 -*-
"""최근 실행 기록에서 실패를 골라 텔레그램 본문을 만든다. 없으면 아무것도 안 쓴다.

월요일에는 실패가 없어도 한 줄 보낸다. 그래야 「알림이 안 온 것」과 「감시 자체가
죽은 것」이 구별된다. 조용한 성공은 도는지 모르는 상태와 같다(커널 원칙 2).
"""
import datetime
import io
import json
import sys

WINDOW_H = 25          # 하루치 + 여유. 스케줄이 한 번 밀려도 빠지지 않게
KST = datetime.timezone(datetime.timedelta(hours=9))
NL = chr(10)


def build(runs, now):
    cut = now - datetime.timedelta(hours=WINDOW_H)
    recent = []
    for r in runs:
        when = datetime.datetime.fromisoformat(r['createdAt'].replace('Z', '+00:00'))
        if when >= cut:
            recent.append((when, r))
    bad = [(w, r) for w, r in recent if r.get('conclusion') == 'failure']
    monday = now.astimezone(KST).weekday() == 0

    out = []
    if bad:
        out.append('<b>[FOOTHOLD] 자동화 실패 %d건</b>' % len(bad))
        out.append('')
        seen = {}
        for w, r in sorted(bad, key=lambda x: x[0], reverse=True):
            seen.setdefault(r['name'], []).append((w, r))
        for name, items in seen.items():
            w, r = items[0]
            out.append('%s <b>%s</b> %d회'
                       % (w.astimezone(KST).strftime('%m-%d %H:%M'), name, len(items)))
            out.append(r['url'])
        out.append('')
        out.append('최근 %d시간 · 실행 %d건 중 실패 %d건'
                   % (WINDOW_H, len(recent), len(bad)))
    elif monday:
        out.append('<b>[FOOTHOLD] 자동화 정상</b>')
        out.append('')
        out.append('최근 %d시간 실행 %d건 · 실패 없음' % (WINDOW_H, len(recent)))
        out.append('이 줄이 안 오면 감시 자체가 죽은 것입니다.')
    return NL.join(out) + NL if out else ''


def main(path):
    runs = json.load(io.open(path, encoding='utf-8'))
    sys.stdout.write(build(runs, datetime.datetime.now(datetime.timezone.utc)))


if __name__ == '__main__':
    main(sys.argv[1])
