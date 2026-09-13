# -*- coding: utf-8 -*-
"""사실 주장 레지스트리: 틀린 정보를 "지금 맞다"가 아니라 "틀려지면 알려준다"로 막는다.

  왜 필요한가
    사이트가 커지면서 검증 가능한 사실 주장이 수백 개가 됐다.
    사람이 다시 읽어서 지키는 방식은 규모가 커지면 반드시 무너진다.
    실제로 오늘만 두 번 겪었다. 
      · DESIGN.md 에 적어둔 인쇄 규칙을 새 컴포넌트에 옮겨 적지 않아 그대로 재발
      · "Newton 험지 미지원" 을 근거 없이 단정형으로 써 놓고 반년을 방치

  이 파일이 하는 일
    ① 사이트에 나오는 **검증 가능한 주장**을 한 곳에 등록한다
    ② `python _build/claims.py --verify` 가 **실제 원본을 때려서** 아직 참인지 확인한다
    ③ 거짓이 되면 **실패로 끝난다**(빌드/CI 에서 잡힌다)
    ④ 각 주장에 확인일·출처를 달아, 웹에도 그대로 노출한다

  등록 기준: 아무거나 넣지 않는다
    ✅ 넣는다 : 남이 관리하는 것이라 **우리 모르게 바뀔 수 있는** 사실
                (라이브러리 최신 버전, 태그 존재, 공식 문서의 원문 문구, 지원 목록)
    ❌ 안 넣는다 : 우리가 잰 실측치(안 바뀐다) · 해석 · 의견 · 설계 결정

  실측치는 여기가 아니라 MEASURED 에 둔다. 검증이 아니라 **출처 표기**가 목적이다.
"""
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {'User-Agent': 'Mozilla/5.0 (compatible; FOOTHOLD-docs-check)'}
TIMEOUT = 30


def _get(url, as_json=False):
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=TIMEOUT).read()
    return json.loads(raw) if as_json else raw.decode('utf-8', 'replace')


# ══════════════════════════════════════════════════════════════
#  검증 대상 주장
#    (키, 사람이 읽는 주장, 출처 URL, 검사 함수)
#    검사 함수는 (통과여부, 실제로 관측된 값) 을 돌려준다.
# ══════════════════════════════════════════════════════════════

RELEASES = 'https://api.github.com/repos/isaac-sim/IsaacLab/releases?per_page=30'
REPO = 'https://api.github.com/repos/isaac-sim/IsaacLab'
NEWTON_DOC = ('https://raw.githubusercontent.com/isaac-sim/IsaacLab/v2.3.2/docs/source/'
              'experimental-features/newton-physics-integration/%s')


def _latest_stable():
    """prerelease 플래그를 믿지 않는다. NVIDIA 는 베타에도 prerelease=false 를 단다.
       그래서 태그 이름에 beta/rc/alpha 가 들어가는지로 판정한다."""
    rel = _get(RELEASES, as_json=True)
    for r in rel:
        t = r['tag_name']
        if not re.search(r'(beta|rc|alpha|dev)', t, re.I):
            return t, r['published_at'][:10]
    return None, None


def c_latest_stable():
    tag, date = _latest_stable()
    return tag == 'v2.3.2', '최신 안정판 = %s (%s)' % (tag, date)


def c_newer_are_beta():
    """v2.3.2 위로 나온 것이 전부 베타인가: 하나라도 정식이면 재검토 신호."""
    rel = _get(RELEASES, as_json=True)
    newer = []
    for r in rel:
        if r['tag_name'] == 'v2.3.2':
            break
        newer.append(r['tag_name'])
    bad = [t for t in newer if not re.search(r'(beta|rc|alpha)', t, re.I)]
    return not bad, ('v2.3.2 이후 %d개 전부 베타: %s' % (len(newer), ', '.join(newer))
                     if not bad else '★ 정식 릴리스 등장: %s' % ', '.join(bad))


def c_default_branch_is_beta():
    d = _get(REPO, as_json=True)
    b = d['default_branch']
    return 'beta' in b.lower(), '기본 브랜치 = %s' % b


def c_v232_tag_exists():
    try:
        d = _get('https://api.github.com/repos/isaac-sim/IsaacLab/releases/tags/v2.3.2',
                 as_json=True)
        return True, 'v2.3.2 존재 (%s)' % d['published_at'][:10]
    except urllib.error.HTTPError as e:
        return False, 'HTTP %s' % e.code


def c_newton_flat_only():
    """'평지 예제만 포함' 원문이 아직 그 문서에 있는가."""
    t = _get(NEWTON_DOC % 'index.rst')
    ok = 'flat terrain' in t and 'only a limited set' in t
    m = re.search(r'only a limited set[^.]*\.', t)
    return ok, (' '.join(m.group(0).split()) if m else '★ 원문 문구 사라짐')


def c_newton_no_rough_go2():
    """Newton 지원 태스크 목록에 우리가 쓰는 Rough Go2 가 없는가.
       ★ 이게 v2.3.2 고정의 가장 강한 근거다. 여기가 뒤집히면 정책을 다시 판단해야 한다."""
    t = _get(NEWTON_DOC % 'training-environments.rst')
    flat = 'Isaac-Velocity-Flat-Unitree-Go2-v0' in t
    rough = 'Isaac-Velocity-Rough-Unitree-Go2-v0' in t
    return (flat and not rough), 'Flat-Go2=%s · Rough-Go2=%s' % (flat, rough)


def c_isaacsim_requirements():
    """Isaac Sim 공식 최소 사양 페이지가 아직 RTX 4080 / 16GB 를 말하는가."""
    t = _get('https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html')
    ok = 'RTX 4080' in t
    m = re.search(r'RTX\s*4080[^<]{0,40}', t)
    return ok, (' '.join(m.group(0).split()) if m else '★ RTX 4080 표기 사라짐')


def c_checkpoint_alive():
    """사전학습 체크포인트가 아직 그 주소에 있는가 (본문을 안 받고 헤더만)."""
    url = ('https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/'
           'Isaac/IsaacLab/PretrainedCheckpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/'
           'checkpoint.pt')
    req = urllib.request.Request(url, headers=UA, method='HEAD')
    r = urllib.request.urlopen(req, timeout=TIMEOUT)
    size = int(r.headers.get('Content-Length', 0))
    return r.status == 200 and size > 1_000_000, 'HTTP %d · %.2f MB' % (r.status, size / 1e6)


def c_pwc_dead():
    """Papers with Code 가 아직 죽어 있는가 (사이트에 '폐쇄됐다'고 써 뒀다)."""
    req = urllib.request.Request('https://paperswithcode.com/', headers=UA)
    r = urllib.request.urlopen(req, timeout=TIMEOUT)
    dest = r.geturl()
    return 'huggingface.co' in dest, '→ %s' % dest


CLAIMS = [
    ('isaaclab-latest-stable',
     'Isaac Lab의 최신 안정판은 v2.3.2다',
     'https://github.com/isaac-sim/IsaacLab/releases', c_latest_stable),

    ('isaaclab-newer-all-beta',
     'v2.3.2보다 위는 전부 베타다 (v3.0.0-beta 계열)',
     'https://github.com/isaac-sim/IsaacLab/releases', c_newer_are_beta),

    ('isaaclab-default-branch-beta',
     '기본 브랜치가 베타라서 그냥 clone하면 베타를 받는다',
     'https://github.com/isaac-sim/IsaacLab', c_default_branch_is_beta),

    ('isaaclab-v232-exists',
     'v2.3.2 태그가 실재한다',
     'https://github.com/isaac-sim/IsaacLab/releases/tag/v2.3.2', c_v232_tag_exists),

    ('newton-flat-only',
     'Newton 통합은 "평지 로코모션 예제만 포함"이라고 공식 문서가 밝힌다',
     NEWTON_DOC % 'index.rst', c_newton_flat_only),

    ('newton-no-rough-go2',
     'Newton 지원 태스크 목록에 우리가 쓰는 Rough Go2 태스크가 없다',
     NEWTON_DOC % 'training-environments.rst', c_newton_no_rough_go2),

    ('isaacsim-min-rtx4080',
     'Isaac Sim 공식 최소 사양은 RTX 4080 / VRAM 16GB다',
     'https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html',
     c_isaacsim_requirements),

    ('go2-checkpoint-available',
     'NVIDIA Go2 험지 사전학습 체크포인트를 아직 받을 수 있다',
     'https://omniverse-content-production.s3-us-west-2.amazonaws.com/…/checkpoint.pt',
     c_checkpoint_alive),

    ('paperswithcode-dead',
     'Papers with Code는 폐쇄됐고 Hugging Face로 넘어간다',
     'https://paperswithcode.com/', c_pwc_dead),
]


# ══════════════════════════════════════════════════════════════
#  실측치: 검증 대상이 아니다. 출처를 밝히려고 적는다.
#    (키, 값, 언제·어디서 쟀나)
# ══════════════════════════════════════════════════════════════
MEASURED = {
    'train-throughput':   ('21,248 ~ 21,385 steps/s', '2026-08-05 · AI-WS01 · 험지 4096envs · RTX 5080 1장'),
    'train-iter':         ('4.4 ~ 4.6초 / iteration', '2026-08-05 · AI-WS01 · 수집 4.5s + 학습 0.12s'),
    'train-1500iter':     ('약 113분 (1시간 53분)', '2026-08-05 · 30 iteration 실측에서 선형 환산'),
    'gui-ram':            ('시스템 RAM 13.5GB · VRAM 약 9GB', '2026-08-05 · AI-WS01 · GUI 모드'),
    'laptop-spec':        ('GTX 1650 Ti 4GB · RAM 15.8GB', '2026-08-05 · 팀원 제공 nvidia-smi'),
    'zombie-process':     ('창을 닫아도 PID 66132가 GPU 9GB 점유 유지', '2026-08-05 · AI-WS01'),
    'ws-gpu':             ('RTX 5080 ×2 (각 15,979MB) · 드라이버 591.86', '2026-07-29 · AI-WS01'),
    'disk-total':         ('15.77 GB', '2026-07-29 · AI-WS01 · pip 캐시 8GB 포함'),
}


def verify(only=None):
    print('사실 주장 검증: 실제 원본을 조회합니다\n')
    bad = []
    for key, text, src, fn in CLAIMS:
        if only and only not in key:
            continue
        try:
            ok, seen = fn()
        except Exception as e:                       # 네트워크 실패와 주장 위반을 구분한다
            print('  ?  %-28s 조회 실패: %s' % (key, e))
            bad.append((key, '조회 실패'))
            continue
        print('  %s %-28s %s' % ('OK' if ok else '★ ', key, seen))
        if not ok:
            print('     └ 주장: %s' % text)
            print('     └ 출처: %s' % src)
            bad.append((key, seen))
    print()
    if bad:
        print('★ 어긋난 주장 %d건: 사이트 문구를 고쳐야 합니다:' % len(bad))
        for k, s in bad:
            print('   - %s : %s' % (k, s))
        return False
    print('전부 통과 (%d건)' % len([c for c in CLAIMS if not only or only in c[0]]))
    return True


if __name__ == '__main__':
    only = sys.argv[2] if len(sys.argv) > 2 else None
    sys.exit(0 if verify(only) else 1)
