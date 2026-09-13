# -*- coding: utf-8 -*-
"""판 번호를 빌드가 붙인다 (#112).

  무엇이 문제였나
    판은 md 머리의 «> 판: v2.0» 한 줄이고, 빌드는 그것을 **읽기만** 했다.
    본문을 열 번 고쳐도 그 줄을 안 건드리면 영원히 v1.0 이다.
    잊어서 안 올라가는 것이 아니라 **잊을 수 있는 구조**인 것이 문제다 (철칙 2).

  설계 (팀장 컨펌 2026-09-01)
    · md 를 건드리지 않는다. 빌드가 남의 저장소 파일을 편집하면 팀원 작업과 충돌한다.
    · 정본은 `docs/ops/versions.json` 원장이다.
    · md 의 «> 판:» 은 **사람이 선언하는 큰 판**(v1 -> v2)만 뜻한다.
    · 소수점은 빌드가 붙인다. 화면 표기는 «선언한 큰 판 + 자동 소수점».
    · 해시 범위는 본문 + 요지 + 상태. 판·날짜 줄만 뺀다.
      («상태: 초안 -> 확정» 은 내용이 안 바뀌어도 읽는 사람에게는 큰 변화다.)

  ★ 첫 실행은 «기록만 하고 올리지 않는다».
    그래야 문서 60여 장의 판이 한꺼번에 흔들리지 않는다. 지금이 기준선이 되고
    **다음에 내용이 바뀌는 문서부터** 소수점이 붙는다.
"""
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 판·날짜만 뺀다. 요지·상태는 내용으로 본다
SKIP_HEAD = re.compile(r'^>\s*(?:판|갱신|최종 갱신)\s*:.*$', re.M)
VER = re.compile(r'^>\s*판\s*:\s*(v[\d.]+)\s*$', re.M)


def body_hash(md):
    """본문 해시. 판·날짜 줄만 빼고 나머지를 다 센다."""
    t = SKIP_HEAD.sub('', md)
    t = re.sub(r'[ \t]+', ' ', t).strip()
    return hashlib.sha256(t.encode('utf-8')).hexdigest()[:16]


def major(md):
    """사람이 선언한 큰 판. 없으면 빈 문자열."""
    m = VER.search(md)
    return m.group(1) if m else ''


def _bump(ver):
    """v2.0 -> v2.1. 소수점만 올린다. 큰 자리는 사람 몫이다."""
    p = ver.lstrip('v').split('.')
    if len(p) == 1:
        p.append('0')
    try:
        p[1] = str(int(p[1]) + 1)
    except ValueError:
        p[1] = '1'
    return 'v' + '.'.join(p[:2])


def _kat():
    """★ 답을 아는 입력."""
    a = '# 제목\n\n> 판: v2.0\n> 상태: 초안\n\n본문'
    b = '# 제목\n\n> 판: v2.0\n> 상태: 확정\n\n본문'
    c = '# 제목\n\n> 판: v2.1\n> 상태: 초안\n\n본문'
    if body_hash(a) == body_hash(b):
        return False, '상태만 바뀐 것을 같다고 봄 (읽는 사람에게는 큰 변화다)'
    if body_hash(a) != body_hash(c):
        return False, '판 줄만 바뀐 것을 다르다고 봄'
    if _bump('v2.0') != 'v2.1' or _bump('v1') != 'v1.1' or _bump('v2.9') != 'v2.10':
        return False, '소수점 올리기가 틀림: %s' % _bump('v2.0')
    if major(a) != 'v2.0' or major('# 없음') != '':
        return False, '큰 판을 잘못 읽음'
    return True, ''


def main(lab=None, write=True):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return None
    if lab is None:
        import docs_pages
        lab = next((p for p in docs_pages.LAB_CANDIDATES
                    if os.path.isdir(os.path.join(p, 'docs'))), None)
    if not lab:
        print('  [!] foothold-lab 을 못 찾음')
        return None

    out = os.path.join(lab, 'docs', 'ops', 'versions.json')
    old = {}
    if os.path.isfile(out):
        try:
            old = json.load(io.open(out, encoding='utf-8'))
        except ValueError:
            old = {}
    first = not old

    now = {}
    bumped, seeded, kept = [], 0, 0
    roots = [os.path.join(lab, 'docs'), os.path.join(lab, 'deliverables')]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for d, _s, fs in os.walk(root):
            if os.path.basename(d).startswith(('.', '_')):
                continue
            for f in sorted(fs):
                if not f.endswith('.md'):
                    continue
                p = os.path.join(d, f)
                rel = os.path.relpath(p, lab).replace(os.sep, '/')
                md = io.open(p, encoding='utf-8', errors='replace').read()
                h, mj = body_hash(md), major(md)
                prev = old.get(rel)
                if prev is None:
                    # 처음 보는 문서. 지금을 기준선으로 삼는다. 안 올린다
                    now[rel] = {'ver': mj or '', 'hash': h, 'major': mj}
                    seeded += 1
                elif prev.get('major') != mj and mj:
                    # 사람이 큰 판을 올렸다. 그 선언이 이긴다
                    now[rel] = {'ver': mj, 'hash': h, 'major': mj}
                    bumped.append((rel, prev.get('ver', ''), mj, '사람'))
                elif prev.get('hash') != h:
                    nv = _bump(prev.get('ver') or mj or 'v1.0')
                    now[rel] = {'ver': nv, 'hash': h, 'major': mj}
                    bumped.append((rel, prev.get('ver', ''), nv, '자동'))
                else:
                    now[rel] = prev
                    kept += 1

    if write:
        io.open(out, 'w', encoding='utf-8', newline='\n').write(
            json.dumps(now, ensure_ascii=False, indent=1, sort_keys=True))

    if first:
        print('  첫 실행 · 기준선만 기록했습니다 (판을 올리지 않습니다): %d장' % seeded)
    else:
        print('  문서 %d장 · 그대로 %d · 새로 %d · 판 올림 %d'
              % (len(now), kept, seeded, len(bumped)))
        for rel, a, b, who in bumped[:12]:
            print('     %-46s %s -> %s (%s)' % (rel[:46], a or '-', b, who))
    return now


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() is not None else 1)
