# -*- coding: utf-8 -*-
"""웹 팔레트 ↔ brand 토큰 정본 대조  (빌드 [1.76] 단계)

  foothold-brand/tokens/foothold.tokens.json 이 색의 단일 진실이다.
  darkmode.py 가 주입하는 라이트/다크 팔레트가 그 정본과 한 글자라도 다르면 빌드를 멈춘다.

  왜 자동 검사인가: "브랜드 값과 같게 맞췄다"는 기억은 다음 수정에서 조용히 깨진다.
  DESIGN-GUIDE 에 적어두는 것만으로는 안 지켜진다는 것을 이미 한 번 겪었다(brandvar.py 주석 참조).

  토큰 파일이 없으면(브랜드 레포 미클론) 경고만 하고 통과: 빌드가 남의 레포에 인질이 되지 않게.
"""
import io, json, os

# 웹 CSS 변수 ← 브랜드 토큰 이름 (공개 인터페이스는 CSS 변수 쪽 이름을 유지한다)
P = 'primitive.color.'
MAP = {
    '--paper':     P + 'paper',
    '--paper-2':   P + 'paper-secondary',
    '--card':      P + 'card',
    '--ink':       P + 'ink',
    '--ink-2':     P + 'ink-secondary',
    '--ink-3':     P + 'ink-caption',
    '--rule':      P + 'rule',
    '--brand':     P + 'teal-brand',
    '--dim':       P + 'teal-brand',
    '--dim-soft':  P + 'teal-soft',
    '--note':      P + 'amber',
    '--note-soft': P + 'amber-soft',
    '--stop':      P + 'red',
    '--stop-soft': P + 'red-soft',
}

CANDIDATES = [
    r"C:\Users\AI-WS01\Desktop\jay\인공지능사관학교\foothold-brand\tokens\foothold.tokens.json",
    os.path.expanduser(r"~\Desktop\jay\인공지능사관학교\foothold-brand\tokens\foothold.tokens.json"),
    os.path.expanduser(r"~\OneDrive\Desktop\인공지능사관학교\foothold-brand\tokens\foothold.tokens.json"),
]


def load_tokens():
    for p in CANDIDATES:
        if os.path.exists(p):
            return p, json.load(io.open(p, encoding='utf-8'))
    return None, None


def flatten(d):
    """전체 경로 → (light, dark).

    이름의 마지막 마디만 쓰면 primitive.color.card 와 semantic.surface.card 가
    충돌해 엉뚱한 값(별칭 문자열)을 집는다. 실제로 그렇게 한 번 틀렸다.
    """
    out = {}

    def walk(o, path=''):
        if not isinstance(o, dict):
            return
        if '$value' in o:
            dark = o.get('$extensions', {}).get('foothold', {}).get('mode', {}).get('dark')
            out[path] = (o['$value'], dark)
            return
        for k, v in o.items():
            if not k.startswith('$'):
                walk(v, (path + '.' + k) if path else k)
    walk(d)
    return out


def norm(c):
    """#fff → #ffffff (같은 색을 다른 표기로 써서 생기는 거짓 불일치 방지)"""
    c = (c or '').strip().lower()
    if len(c) == 4 and c.startswith('#'):
        return '#' + ''.join(ch * 2 for ch in c[1:])
    return c


def main(light, dark):
    path, raw = load_tokens()
    if raw is None:
        print('  [!] brand 토큰 파일 없음. 대조 건너뜀 (foothold-brand 미클론)')
        return True
    tok = flatten(raw)
    bad = []
    for var, tname in MAP.items():
        if tname not in tok:
            bad.append('%s: 토큰 %s 없음' % (var, tname))
            continue
        tl, td = tok[tname]
        if norm(light.get(var)) != norm(tl):
            bad.append('%s light %s ≠ 정본 %s' % (var, light.get(var), tl))
        if td and norm(dark.get(var)) != norm(td):
            bad.append('%s dark  %s ≠ 정본 %s' % (var, dark.get(var), td))
    print('  정본: %s' % os.path.basename(path))
    if bad:
        print('  ★ 브랜드 정본과 불일치 %d건' % len(bad))
        for b in bad:
            print('     %s' % b)
        return False
    print('  팔레트 %d종 · 라이트/다크 모두 정본과 일치' % len(MAP))
    return True
