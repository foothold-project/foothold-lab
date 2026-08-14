# -*- coding: utf-8 -*-
"""inbox 제출물 자동 검토: 승격 조건을 기계가 판정하고 승격안을 만든다.

  판정 4종은 docs/README.md 의 승격 조건 그대로다.
    h1 제목 · 증거 표기 · 원 출처 링크 · 웹 금지 요소(ASCII 도식·em dash)
  통과 여부와 무관하게 **무엇을 고쳐야 하는지**를 문장으로 돌려준다.
  사람이 파일을 열어보지 않고도 승격 여부를 정할 수 있게 하는 것이 목적이다.

  출력: JSON (stdout)  { files: [ {path, title, lede, checks{}, ok, slug, dest, fixes[] } ] }
"""
import io, json, os, re, sys


def review(path):
    md = io.open(path, encoding='utf-8').read()
    title = None
    m = re.search(r'^#\s+(.+)$', md, re.M)
    if m:
        title = m.group(1).strip()
    m = re.search(r'^>?\s*요지:\s*(.+)$', md, re.M)
    lede = m.group(1).strip()[:120] if m else ''

    evidence = len(re.findall(r'`(확인됨|검증됨|실측|추측|가설|미측정|미확인|코드확인)`', md))
    links = len(set(re.findall(r'https?://[^\s)]+', md)))
    ascii_art = len(re.findall(r'[─-╿▀-▟]', md))
    emdash = md.count('—')

    checks = {
        'h1 제목': bool(title),
        '증거 표기': evidence > 0,
        '원 출처 링크': links > 0,
        '웹 금지 요소 없음': ascii_art < 3 and emdash == 0,
    }
    fixes = []
    if not checks['h1 제목']:
        fixes.append('맨 위에 `# 제목` 추가')
    if not checks['증거 표기']:
        fixes.append('`확인됨`/`추측`/`미측정` 표기 부여')
    if not checks['원 출처 링크']:
        fixes.append('참고한 원 출처 링크 추가')
    if ascii_art >= 3:
        fixes.append('선으로 그린 도식 %d자를 표로 변환' % ascii_art)
    if emdash:
        fixes.append('em dash %d개 제거' % emdash)

    slug = re.sub(r'^\d{8}[-_]', '', os.path.basename(path)[:-3])
    slug = re.sub(r'[^a-z0-9-]+', '-', slug.lower()).strip('-') or 'submission'
    return {
        'path': path, 'title': title or '(제목 없음)', 'lede': lede,
        'lines': md.count('\n') + 1, 'bytes': len(md.encode('utf-8')),
        'evidence': evidence, 'links': links,
        'checks': checks, 'ok': all(checks.values()),
        'slug': slug, 'dest': 'docs/research/%s.md' % slug, 'fixes': fixes,
    }


if __name__ == '__main__':
    out = [review(p) for p in sys.argv[1:] if p.endswith('.md') and os.path.exists(p)]
    print(json.dumps({'files': out}, ensure_ascii=False))
