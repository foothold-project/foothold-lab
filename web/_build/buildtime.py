# -*- coding: utf-8 -*-
"""빌드의 «시간» 입력을 한 곳으로 모은다 (mai-os#22 · 묶음 6.5).

  왜
    같은 소스로 빌드해도 결과가 매번 달랐다. 시각·날짜·파일 mtime 이 아홉 자리에서
    제각기 현재 값을 읽었기 때문이다. 그래서 「소스가 정본인가」를 물을 수 없었다.
    재현하려면 시간 입력이 한 곳에서 나와야 한다.

  이 파일이 통제하는 것 · 셋뿐이다
    now()        지금 시각 (timezone 있는 datetime)
    today()      오늘 날짜 (date)
    mtime(path)  파일 수정 시각 (float · epoch)

  ★ 통제하지 않는 것 · os.urandom()
    그것은 시간 입력이 아니라 **암호 난수**다. 결정론화하면 AES-GCM 의
    IV 유일성 요구를 깬다 (NIST SP 800-38D · RFC 8452).
    `secure_docs.py` 의 salt·nonce 는 앞으로도 os.urandom 이어야 한다.
    이 모듈은 그것을 대체할 함수를 **제공하지 않는다.**

  쓰는 법
    일반 빌드      python build.py
    재현 빌드      python build.py --repro --build-time 2026-09-02T12:00:00+09:00

    재현 모드는 canonical time 을 안 주면 **실패한다.** 기본값으로 현재 시각을
    쓰면 그것은 재현이 아니기 때문이다.
"""
import datetime
import os
import sys

_STATE = {'fixed': None, 'repro': False}

ENV_TIME = 'FOOTHOLD_BUILD_TIME'
ENV_REPRO = 'FOOTHOLD_REPRO'


class BuildTimeError(ValueError):
    """canonical time 이 없거나 형식이 틀렸다. 조용히 넘어가지 않는다."""


def parse(text):
    """ISO 8601 + timezone 을 요구한다.

    timezone 이 없으면 거부한다. 「2026-09-02T12:00:00」 은 어느 지역의 12시인지
    말하지 않으므로 재현 기준이 될 수 없다.
    """
    if text is None or not str(text).strip():
        raise BuildTimeError('canonical build time 이 없습니다. '
                             '--build-time 2026-09-02T12:00:00+09:00 형식으로 주세요')
    s = str(text).strip()
    if s.endswith('Z'):                       # 파이썬 3.10 이하는 Z 를 못 읽는다
        s = s[:-1] + '+00:00'
    try:
        dt = datetime.datetime.fromisoformat(s)
    except ValueError:
        raise BuildTimeError('ISO 8601 형식이 아닙니다: %r '
                             '(예: 2026-09-02T12:00:00+09:00)' % text)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise BuildTimeError('timezone 이 없습니다: %r. '
                             '어느 지역의 시각인지 없으면 재현 기준이 못 됩니다' % text)
    return dt


def configure(argv=None, env=None):
    """`--repro` 와 `--build-time` 을 읽어 상태를 정한다.

    argv 를 넘기면 그것만 본다 (자기시험용). 안 넘기면 sys.argv 와 환경변수를 본다.
    """
    argv = list(sys.argv if argv is None else argv)
    env = os.environ if env is None else env
    repro = ('--repro' in argv) or str(env.get(ENV_REPRO, '')).strip() not in ('', '0')

    given = None
    if '--build-time' in argv:
        i = argv.index('--build-time')
        given = argv[i + 1] if i + 1 < len(argv) else None
    elif env.get(ENV_TIME):
        given = env[ENV_TIME]

    if repro:
        _STATE['fixed'] = parse(given)        # 없으면 BuildTimeError 로 죽는다
        _STATE['repro'] = True
    else:
        _STATE['fixed'] = parse(given) if given else None
        _STATE['repro'] = False
    return _STATE['repro']


def is_repro():
    return bool(_STATE['repro'])


def now():
    """지금 시각. 재현 모드면 고정값."""
    if _STATE['fixed'] is not None:
        return _STATE['fixed']
    return datetime.datetime.now().astimezone()


def today():
    """오늘 날짜. 재현 모드면 고정값의 날짜."""
    return now().date()


def stamp(fmt='%Y-%m-%d %H:%M'):
    """화면에 찍는 갱신 시각 문자열."""
    return now().strftime(fmt)


def mtime(path):
    """파일 수정 시각.

    ★ 재현 모드에서는 파일시스템 mtime 을 쓰지 않는다. 같은 소스를 다른 폴더에
      풀면 mtime 이 달라지기 때문이다. canonical time 을 돌려준다.
    """
    if _STATE['fixed'] is not None:
        return _STATE['fixed'].timestamp()
    return os.path.getmtime(path)


def _kat():
    """★ 답을 아는 입력. 이 모듈이 하는 일이 셋뿐임을 여기서 못 박는다."""
    save = dict(_STATE)
    try:
        # 1) timezone 있는 정상 입력
        d = parse('2026-09-02T12:00:00+09:00')
        if d.utcoffset() != datetime.timedelta(hours=9):
            return False, 'timezone 을 잘못 읽음'
        # 2) Z 표기도 받는다
        if parse('2026-09-02T03:00:00Z').utcoffset() != datetime.timedelta(0):
            return False, 'Z 표기를 못 읽음'
        # 3) timezone 없으면 거부
        for bad in ('2026-09-02T12:00:00', '2026-09-02', 'not-a-time', '', None):
            try:
                parse(bad)
                return False, 'timezone 없는 입력을 통과시킴: %r' % bad
            except BuildTimeError:
                pass
        # 4) repro 인데 시각 미지정이면 실패해야 한다
        try:
            configure(argv=['build.py', '--repro'], env={})
            return False, 'repro 인데 시각 없이 통과함'
        except BuildTimeError:
            pass
        # 5) repro 모드는 고정 시각을 쓴다
        configure(argv=['build.py', '--repro', '--build-time',
                        '2026-09-02T12:00:00+09:00'], env={})
        if not is_repro():
            return False, 'repro 로 안 들어감'
        if now().isoformat() != '2026-09-02T12:00:00+09:00':
            return False, '고정 시각을 안 씀: %s' % now().isoformat()
        if today().isoformat() != '2026-09-02':
            return False, 'today 가 고정값을 안 씀'
        if mtime(__file__) != now().timestamp():
            return False, 'repro 에서 mtime 이 파일시스템을 봄'
        # 6) 일반 모드는 실제 시각을 쓴다
        configure(argv=['build.py'], env={})
        if is_repro():
            return False, '일반 모드인데 repro 로 잡힘'
        gap = abs((now() - datetime.datetime.now().astimezone()).total_seconds())
        if gap > 5:
            return False, '일반 모드가 실제 시각을 안 씀'
        if abs(mtime(__file__) - os.path.getmtime(__file__)) > 0.001:
            return False, '일반 모드에서 mtime 이 파일시스템을 안 봄'
        # 7) 환경변수로도 들어간다
        configure(argv=['build.py'], env={ENV_REPRO: '1',
                                          ENV_TIME: '2026-01-02T03:04:05+00:00'})
        if not is_repro() or today().isoformat() != '2026-01-02':
            return False, '환경변수 경로가 안 먹음'
        return True, ''
    finally:
        _STATE.clear(); _STATE.update(save)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    ok, why = _kat()
    print('자기시험 %s%s' % ('통과' if ok else '실패', '' if ok else ': ' + why))
    sys.exit(0 if ok else 1)
