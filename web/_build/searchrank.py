# -*- coding: utf-8 -*-
"""검색 «순위» 관문. 화면에 나가는 그 JS 를 그대로 떼어 node 로 돌린다.

★ 2026-09-09 라이브 실측에서 나왔다. 「rails」 를 치면 12칸이 전부
  a~d 로 시작하는 페이지로 찼고, 정작 rails 진단 문서 셋은 하나도 없었다.
  「pit」 은 반대로 한 문서의 절 여섯이 화면을 채워 다른 문서를 밀어냈다.

  원인은 점수가 «어느 칸에 있나» 만 보고 «몇 번 쓴 글인가» 를 안 본 것이다.
  본문 일치는 전부 1점이라 동점이었고, 동점은 색인 순서로 풀려 파일이름 순이 됐다.

왜 node 로 «그 코드» 를 돌리나
  순위 규칙을 파이썬으로 한 번 더 적으면 두 벌이 되고, 두 벌은 갈라진다.
  tablefix 가 렌더러와 다른 규칙으로 세다가 멀쩡한 표를 막은 것이 바로 그 부류다.
  그래서 규칙은 searchbox 의 fhRank 하나뿐이고, 여기서는 그것을 «떼어» 돌린다.

node 가 없으면
  조용히 통과시키지 않는다. 건너뛴다고 «소리 내어» 적는다.


★ 이 관문이 «못 잡는 것»
  - 순위가 «쓸 만한가» 는 안 본다. 알려진 답 네 개로 «뒤집히지 않았나» 만 본다.
    사람이 찾는 말로 실제 결과를 보는 것은 대신 못 한다.
  - node 가 없는 기기에서는 건너뛴다. 그때는 이 관문이 «없는» 것이다.
    조용히 넘기지 않고 소리 내어 적지만, 검사는 안 돈 것이다.
  - 색인에 «무엇이 빠졌나» 는 [1.8995] 가 본다. 여기는 순위만 본다.
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

BEGIN = '/* fh-rank:시작'
END = '/* fh-rank:끝 */'


def extract(js):
    """화면에 나가는 JS 에서 fhRank 만 떼어 낸다. 못 떼면 None."""
    i = js.find(BEGIN)
    j = js.find(END, i + 1)
    if i < 0 or j < 0:
        return None
    return js[i:j]


def _rec(p, a, t, h, x):
    return {'p': p, 'a': a, 't': t, 'h': h, 'x': x}


# ★ 알려진 답. 낱말은 색인에 우연히 없는 것을 골랐다 (실제 색인과 안 섞이게).
CASES = [
    {
        'name': '많이 쓴 글이 스친 글보다 위',
        'q': 'zeta',
        'idx': [_rec('a.html', '', '가', '가', 'zeta 를 한 번 스쳤다'),
                _rec('b.html', '', '나', '나', 'zeta zeta zeta 세 번 썼다')],
        'want': ['b.html', 'a.html'],
    },
    {
        'name': '제목 일치는 빈도를 이긴다',
        'q': 'zeta',
        'idx': [_rec('a.html', '', '가', '가', 'zeta zeta zeta zeta 네 번'),
                _rec('b.html', '', 'zeta 제목', '나', '본문에는 없다')],
        'want': ['b.html', 'a.html'],
    },
    {
        'name': '한 문서가 칸을 다 먹지 않는다',
        'q': 'zeta',
        'cap': 2, 'lim': 4,
        'idx': ([_rec('big.html', 's%d' % k, '큰글', 'zeta 절 %d' % k, 'zeta zeta')
                 for k in range(1, 6)]
                + [_rec('c.html', '', '다', '다', 'zeta'),
                   _rec('d.html', '', '라', '라', 'zeta')]),
        'want': ['big.html', 'big.html', 'c.html', 'd.html'],
    },
    {
        'name': '완전 동점이면 색인 순서 그대로',
        'q': 'zeta',
        'idx': [_rec('a.html', '', '가', '가', 'zeta'),
                _rec('b.html', '', '나', '나', 'zeta')],
        'want': ['a.html', 'b.html'],
    },
]


def _harness(fn_src, cases):
    lines = [fn_src, 'var CASES=' + json.dumps(cases, ensure_ascii=False) + ';',
             'var bad=[];',
             'for (var k=0;k<CASES.length;k++){',
             '  var c=CASES[k];',
             '  var got=fhRank(c.idx,c.q,c.cap||3,c.lim||12).hits'
             '.map(function(h){return h.e.p});',
             '  if(got.join("|")!==c.want.join("|"))',
             '    bad.push(c.name+" -> "+got.join(" ")+"  (바란 것: "'
             '+c.want.join(" ")+")");',
             '}',
             'console.log(JSON.stringify(bad));']
    return '\n'.join(lines)


def main(vault=None):
    import searchbox
    fn = extract(searchbox.CSS_JS)
    if not fn:
        print('  [!] 화면 JS 에서 fhRank 를 못 떼어 냈습니다 (표시가 사라졌나).')
        return False

    cases = [{k: v for k, v in c.items()} for c in CASES]
    src = _harness(fn, cases)
    fd, path = tempfile.mkstemp(suffix='.js')
    os.close(fd)
    try:
        io.open(path, 'w', encoding='utf-8', newline='\n').write(src)
        try:
            r = subprocess.run(['node', path], capture_output=True, text=True,
                               encoding='utf-8', timeout=60)
        except (OSError, subprocess.SubprocessError) as e:
            print('  건너뜁니다: node 를 못 돌렸습니다 (%s). 순위는 이번 빌드에서'
                  ' 검사되지 않았습니다' % e)
            return True
        if r.returncode != 0:
            print('  [!] node 가 실패했습니다: %s' % (r.stderr or '')[:400])
            return False
        try:
            bad = json.loads((r.stdout or '[]').strip().splitlines()[-1])
        except (ValueError, IndexError):
            print('  [!] 시험 결과를 못 읽었습니다: %s' % (r.stdout or '')[:200])
            return False
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    if bad:
        for b in bad:
            print('  ★ %s' % b)
        return False
    print('  화면 JS 의 fhRank 를 그대로 돌렸습니다 · 알려진 답 %d건 통과'
          % len(CASES))
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
