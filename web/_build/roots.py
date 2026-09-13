# -*- coding: utf-8 -*-
"""빌드가 어디에 사는지 한 곳에서 답한다.

**2026-09-13 이전까지** 이 빌드는 볼트(`MAI_UNIVERSE/03_PROJECTS/doyak-final/
05_deliverables/`) 안에 살았고, 형제 저장소를 `'..' x 4` 로 더듬어 찾았다.
그 깊이가 네 파일 열 곳에 손으로 박혀 있었다.

**지금은 `foothold-lab/web/` 안에 산다.** 그래서 더듬을 것이 없다.

    foothold-lab/web/_build/roots.py   <- 여기
    foothold-lab/web/                  <- VAULT (페이지 원본과 자산)
    foothold-lab/                      <- LAB   (문서 정본)
    인공지능사관학교/foothold-site/     <- SITE  (배포본)

옛 경로도 후보로 남긴다. 다른 기기나 옛 배치에서 부를 수 있기 때문이다.
**새 위치를 «맨 앞» 에 둔다.** 순서가 곧 우선순위다.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)                    # foothold-lab/web
LAB = os.path.dirname(VAULT)                     # foothold-lab
WS = os.path.dirname(LAB)                        # 인공지능사관학교


def _ok(p):
    return p if os.path.isdir(p) else None


def lab_candidates():
    """문서 정본이 있는 곳. 앞에서부터 먼저 본다.

    ★ `_lab-main` 을 «맨 앞에 두지 않는다.** 2026-09-13 에 그것 때문에
      26 커밋이 조용히 가려졌다. 빌드가 사흘 전 문서를 읽고 있었고
      아무 말도 하지 않았다.

      재현 빌드가 고정 입력을 원하면 `FOOTHOLD_LAB` 로 명시해 부른다.
      암묵적으로 옛 커밋을 읽는 일은 없어야 한다.
    """
    env = os.environ.get('FOOTHOLD_LAB')
    out = [env] if env else []
    out += [
        LAB,                                     # 이 빌드가 사는 저장소 그대로
        os.path.join(WS, 'foothold-lab'),
        os.path.join(WS, '_lab-main'),           # 고정 워크트리는 «마지막»
        os.path.expanduser(os.path.join('~', 'Desktop', 'jay',
                                        '인공지능사관학교', 'foothold-lab')),
    ]
    return [p for p in out if p]


def site_candidates():
    """배포본이 있는 곳."""
    env = os.environ.get('FOOTHOLD_SITE')
    out = [env] if env else []
    out += [
        os.path.join(WS, 'foothold-site'),
        os.path.join(os.path.dirname(WS), 'foothold-site'),
        os.path.expanduser(os.path.join('~', 'Desktop', 'jay',
                                        '인공지능사관학교', 'foothold-site')),
    ]
    return [p for p in out if p]


def lab():
    for p in lab_candidates():
        if _ok(p):
            return os.path.abspath(p)
    return None


def site():
    for p in site_candidates():
        if _ok(p):
            return os.path.abspath(p)
    return None


def workspace():
    return WS

# 02_team · 04_plan · 07_chosun 이 있는 곳.
#
# 옛 배치에서는 `doyak-final/` 이었다 (VAULT 의 부모). 이전 뒤에는 `web/`
# 안이다. 둘 다 본다. **먼저 찾은 것이 이긴다.**
def proj():
    for p in ([os.environ['FOOTHOLD_PROJ']] if os.environ.get('FOOTHOLD_PROJ') else []) + [
            VAULT,                               # web/02_team · web/04_plan
            os.path.dirname(VAULT)]:             # 옛 배치 doyak-final/02_team
        if os.path.isdir(os.path.join(p, '02_team')):
            return os.path.abspath(p)
    return VAULT


def chosun():
    """조선대 자료. 암호화 자산의 «원문» 이고 --skip-secure 면 안 읽는다."""
    for p in ([os.environ['FOOTHOLD_CHOSUN']] if os.environ.get('FOOTHOLD_CHOSUN') else []) + [
            os.path.join(VAULT, '07_chosun'),
            os.path.join(os.path.dirname(VAULT), '07_chosun'),
            os.path.join(WS, '..', 'MAI_UNIVERSE', '03_PROJECTS',
                         'doyak-final', '07_chosun')]:
        if os.path.isdir(p):
            return os.path.abspath(p)
    return None
