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


def _dedupe(paths):
    """같은 트리를 가리키는 후보를 하나로 줄인다. 순서는 지킨다.

    ★ 2026-09-14 site 세션이 집었다. 세 후보가 전부 같은 곳으로
      풀렸다 (`WS/foothold-lab` · `~/Desktop/.../foothold-lab` · `LAB`).
      첫 후보만 보는 자리는 무해했지만 **후보를 전부 도는 자리** 는
      같은 트리를 세 번 읽었다. 기기마다 다른 트리로 풀리면 그때는
      섞인다. `realpath` + `normcase` 로 묶는다 (윈도우는 대소문자를
      안 가리고, 심볼링크도 같은 곳을 다른 이름으로 가리킨다).
    """
    seen, out = set(), []
    for p in paths:
        if not p:
            continue
        try:
            key = os.path.normcase(os.path.realpath(p))
        except OSError:
            key = os.path.normcase(os.path.abspath(p))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def lab_candidates():
    """문서 정본이 있는 곳. 앞에서부터 먼저 본다.

    ★ 2026-09-13. `_lab-main` 을 맨 앞에서 «맨 뒤» 로 내렸다. 맨 앞이라
      26 커밋이 조용히 가려졌고, 빌드가 사흘 전 문서를 읽으며 아무 말도
      안 했다. 「고쳤는데 화면이 안 바뀐다」로 나타났다.

    ★ 2026-09-14 팀장 확정: **목록에서 아예 뺐다.**

      뒤로 내려도 새는 자리가 남았다. 대부분의 소비자는 `next(...)` 로 첫
      후보만 보지만, **후보를 전부 도는 자리**가 있어서 거기로 옛 트리가
      섞여 들어왔다. 실제로 site 세션 빌드가 이것 때문에 멈췄다 ·
      문서는 `foothold-lab`(미커밋)에서, 빌드 코드는 `_lab-main`(옛것)에서
      와서 한 빌드가 서로 다른 판의 입력을 섞어 썼다.

      팀장 판단은 이렇다. 「`_lab-main` 은 우리가 쓰는 게 아니고, 배포는
      `foothold-site` 에서만 한다」. 정본은 `foothold-lab` 하나다.

      **뒤에 두고 조심하는 것보다 목록에서 없애는 것이 낫다.** 뒤에 있으면
      «언젠가 도는 자리» 가 하나만 생겨도 다시 샌다.

      `_lab-main` 안에서 빌드를 돌리는 경우는 그대로 된다. `LAB`(이 빌드가
      사는 저장소)이 맨 앞이라 자기 트리를 읽는다. 고정 입력이 필요하면
      `FOOTHOLD_LAB` 로 «명시해» 부른다. 암묵적으로 옛 커밋을 읽는 길은 없앤다.
    """
    env = os.environ.get('FOOTHOLD_LAB')
    out = [env] if env else []
    out += [
        LAB,                                     # 이 빌드가 사는 저장소 그대로
        os.path.join(WS, 'foothold-lab'),
        os.path.expanduser(os.path.join('~', 'Desktop', 'jay',
                                        '인공지능사관학교', 'foothold-lab')),
    ]
    return _dedupe(out)


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
    return _dedupe(out)


def lab():
    for p in lab_candidates():
        if _ok(p):
            return os.path.abspath(p)
    return None


def warn_if_stray(say=print):
    """이 빌드가 `foothold-lab` 이 아닌 트리에서 돌면 알린다.

    ★ 2026-09-14. `_lab-main` 을 후보에서 빼는 것으로는 반쪽만 막혔다.
      그 안에서 빌드를 돌리면 `LAB` 이 계속 제 트리를 가리켜 실행은
      되고, 문서는 옆 트리에서 오는 섞임이 그대로 남는다. 그것을
      막을 수는 없어도 (재현 빌드는 그렇게 돌려야 한다) **조용히 둘 수는
      없다.** 2026-09-13 사고가 정확히 «아무 말도 안 해서» 26 커밋을
      사흘간 가렸다. 멈추지는 않고 이름을 댄다.
    """
    name = os.path.basename(LAB)
    if name == 'foothold-lab' or os.environ.get('FOOTHOLD_LAB'):
        return None
    msg = chr(10).join([
        '  [!] 이 빌드가 «%s» 안에서 돕니다. 문서 정본은 '
        '`foothold-lab` 입니다.' % name,
        '      지금 읽는 곳: %s' % lab(),
        '      의도한 것이 아니면 `foothold-lab` 에서 돌리거나 '
        'FOOTHOLD_LAB 로 명시하십시오.',
    ])
    say(msg)
    return msg


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
