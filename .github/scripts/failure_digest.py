# -*- coding: utf-8 -*-
"""최근 실행 기록에서 실패를 골라 텔레그램 본문을 만든다.

월요일에는 실패가 없어도 한 줄 보낸다. 그래야 「알림이 안 온 것」과 「감시 자체가
죽은 것」이 구별된다. 조용한 성공은 도는지 모르는 상태와 같다(커널 원칙 2).

★ 2026-09-09. 여기가 감시자 자신의 맹점이었다.
  전에는 실패가 없으면 빈 문자열을 돌려줬고, 워크플로는 그것을 보고
  「보낼 것 없음」을 찍고 exit 0 했다. 그런데 토큰 권한이 빠져
  `gh run list` 가 `[]` 를 주는 상황도 «같은 빈 문자열» 이었다.
  **「조회가 빈손으로 왔다」와 「깨진 것이 없다」가 7일 중 6일은
  화면에서 완전히 같았다.** 감시자가 자기 눈이 멀었는지를 못 본다.

  이제 셋을 가른다.
    · 조회가 0건        → 소리 낸다 · 종료코드 2 (본문은 그대로 내보낸다)
    · 창 안 실행이 0건  → 소리 낸다 · 종료코드 2 (매일 06:00 원장이 도는 저장소다)
    · 실패가 0건        → 조용 (월요일만 «정상» 한 줄)

  종료코드 2 는 «본문은 만들었으니 보내라 · 그리고 이 런을 빨간불로 만들어라»
  라는 뜻이다. 보내기 전에 죽으면 사람은 아무것도 못 듣는다.
"""
import datetime
import io
import json
import sys

WINDOW_H = 25          # 하루치 + 여유. 스케줄이 한 번 밀려도 빠지지 않게
KST = datetime.timezone(datetime.timedelta(hours=9))
NL = chr(10)

RC_OK = 0
RC_BLIND = 2           # 본문은 냈다 · 다만 조회가 못 미더우니 런을 빨간불로


def build(runs, now):
    """(본문, 눈이_멀었나) 를 돌려준다.

    본문이 빈 문자열이면 보낼 것이 없다는 뜻이고, 그때 눈이_멀었나 는 늘 False 다.
    """
    cut = now - datetime.timedelta(hours=WINDOW_H)
    recent = []
    for r in runs:
        when = datetime.datetime.fromisoformat(r['createdAt'].replace('Z', '+00:00'))
        if when >= cut:
            recent.append((when, r))
    bad = [(w, r) for w, r in recent if r.get('conclusion') == 'failure']
    monday = now.astimezone(KST).weekday() == 0

    #  눈이 먼 경우를 먼저 가른다
    # 실행 기록 조회가 통째로 빈손이면 그것은 «깨진 것이 없다» 가 아니다.
    # 토큰 권한 · API 오류 · 저장소 오지정 전부 여기로 떨어진다.
    if not runs:
        return NL.join([
            '<b>[FOOTHOLD] 감시가 눈이 멀었습니다</b>',
            '',
            '실행 기록 조회가 0건으로 왔습니다. 실패가 없는 것이 아니라',
            '<b>실패를 볼 수 없는 상태</b>입니다.',
            '',
            '볼 곳: Actions 토큰 권한(actions:read) · gh run list 응답',
            '이 상태에서는 다른 자동화가 깨져도 알림이 오지 않습니다.',
        ]) + NL, True

    # 원장 동기화가 매일 06:00 에 도는 저장소다. 창 안 실행 0건은 불가능한 값이다.
    # 전에는 이 값을 그대로 두고 제목만 «자동화 정상» 이라고 적었다.
    if not recent:
        return NL.join([
            '<b>[FOOTHOLD] 감시 결과가 이상합니다</b>',
            '',
            '실행 기록 %d건을 받았지만 최근 %d시간 안에 든 것이 0건입니다.'
            % (len(runs), WINDOW_H),
            '매일 06:00 에 도는 예약 작업이 있으므로 나올 수 없는 값입니다.',
            '',
            '볼 곳: 예약 워크플로가 전부 꺼졌는지 · 조회 범위(--limit)가 맞는지',
        ]) + NL, True

    #  여기서부터는 눈이 보이는 상태
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
    return (NL.join(out) + NL if out else ''), False


def main(path):
    runs = json.load(io.open(path, encoding='utf-8'))
    if not isinstance(runs, list):
        sys.stderr.write('실행 기록이 배열이 아니다: %r%s' % (type(runs).__name__, NL))
        return 1
    text, blind = build(runs, datetime.datetime.now(datetime.timezone.utc))
    sys.stdout.write(text)
    if blind:
        # 사람이 읽을 진단은 stderr 로. stdout 은 전송 본문 전용이다.
        sys.stderr.write('조회가 못 미덥다. 본문은 냈고 런은 실패로 표시한다.%s' % NL)
        return RC_BLIND
    return RC_OK


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
