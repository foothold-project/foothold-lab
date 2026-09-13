# -*- coding: utf-8 -*-
"""윈도에서 파일 쓰기가 «가끔» 실패하는 것을 다시 해 본다.

**증상.** 빌드 도중 아무 페이지에서나 이렇게 죽는다.

    OSError: [Errno 22] Invalid argument: '...\\web\\hub-proposal.html'

2026-09-13 하루에 세 번 났고 매번 다른 파일이었다 (`index.html` ·
`roles.html` · `hub-proposal.html`). 죽은 뒤에 그 파일을 열어 보면 **안 잠겨
있다.** 동시에 도는 빌드도 없었다.

**원인.** 윈도에서 방금 쓴 파일을 검사기(바이러스 검사 · 색인기 · 동기화
클라이언트)가 잠깐 잡는다. 그 찰나에 다시 열려 하면 `Errno 22` 나 `Errno 13`
이 난다. 우리 코드가 틀린 것이 아니라 **잠깐 기다리면 되는 것**이다.

**왜 이렇게 막나.** 쓰는 자리가 빌드 전체에 흩어져 있어 한 곳씩 고치면
다음번에 또 다른 자리에서 난다. 부류로 막는다 (커널 원칙: 개별 사례가 아니라
부류로).

`build.py` 맨 위에서 `safewrite.install()` 을 한 번 부른다.

**조용히 넘기지 않는다.** 다시 해서 됐으면 그 사실을 찍는다. 세 번 다 실패하면
원래 오류를 그대로 올린다. 「가끔 되는 빌드」를 「늘 되는 빌드」로 착각하면
안 된다.
"""
import builtins
import io
import time

RETRY = (22, 13, 32)          # Invalid argument · Permission denied · 공유 위반
TRIES = 4
WAIT = 0.35

_orig_open = io.open
_installed = False
_retried = []


def _is_write(mode):
    return any(c in mode for c in ('w', 'a', 'x', '+'))


def _open(file, mode='r', *a, **k):
    if not _is_write(mode):
        return _orig_open(file, mode, *a, **k)

    last = None
    for i in range(TRIES):
        try:
            f = _orig_open(file, mode, *a, **k)
            if i:
                _retried.append((str(file), i))
                print('  (다시 해서 됐습니다 %d번째: %s)'
                      % (i + 1, str(file).rsplit('\\', 1)[-1]))
            return f
        except OSError as e:
            if e.errno not in RETRY or i == TRIES - 1:
                raise
            last = e
            time.sleep(WAIT * (i + 1))
    raise last                                  # 여기 오지 않는다


def install():
    """한 번만 건다. 두 번 걸면 재시도가 겹쳐 기다리는 시간이 곱이 된다."""
    global _installed
    if _installed:
        return False
    io.open = _open
    builtins.open = _open
    _installed = True
    return True


def report():
    """다시 해서 된 것이 있었나. 빌드 끝에 한 줄 찍으라고 있다."""
    return list(_retried)


def _selftest():
    """알려진 답으로 시험한다. 이 방어가 «진짜로 다시 하는지» 본다."""
    calls = {'n': 0}
    global _orig_open
    keep = _orig_open                 # ★ «진짜» 열기를 먼저 붙잡는다.

    def flaky(file, mode='r', *a, **k):
        # keep 을 부른다. _orig_open 을 부르면 그것이 곧 자기 자신이라
        # 무한 재귀가 된다 (실측: 이 시험이 그 실수를 잡았다).
        if _is_write(mode):
            calls['n'] += 1
            if calls['n'] < 3:
                raise OSError(22, 'Invalid argument')
        return keep(file, mode, *a, **k)

    globals()['_orig_open'] = flaky
    try:
        import tempfile
        import os
        p = os.path.join(tempfile.gettempdir(), 'safewrite-selftest.txt')
        with _open(p, 'w', encoding='utf-8') as f:
            f.write('ok')
        got = _orig_open(p, encoding='utf-8').read()
        os.remove(p)
        assert calls['n'] == 3, '세 번째에 성공해야 한다 (지금 %d)' % calls['n']
        assert got == 'ok'

        # 다시 해도 안 되는 것은 «올려야» 한다. 조용히 삼키면 안 된다.
        calls['n'] = -99
        try:
            _open(p, 'w', encoding='utf-8')
        except OSError:
            pass
        else:
            raise AssertionError('끝내 실패한 것을 안 올렸다')

        # 우리가 막는 것이 아닌 오류는 «그대로» 올린다.
        def other(file, mode='r', *a, **k):
            raise OSError(2, 'No such file')
        globals()['_orig_open'] = other
        try:
            _open(p, 'w')
        except OSError as e:
            assert e.errno == 2, '다른 오류를 바꿔치기했다'
        return True
    finally:
        globals()['_orig_open'] = keep


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print('  자기시험 통과' if _selftest() else '  자기시험 실패')
