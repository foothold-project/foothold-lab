# -*- coding: utf-8 -*-
"""그림의 `viewBox` 를 내용에 맞춰 «사방 같은 여백» 으로 다시 잡는다.

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (브라우저 `getBBox` 로 잰 내용 상자 · 아래 표)
요지: 글자가 틀 가장자리에 닿고 반대쪽은 비어 있었다. 여백을 한 값으로 맞춘다

## 왜 있나

2026-09-14 팀장 지적: 「SVG 레이아웃이 이상했던 것 · 간격도 마찬가지고
border gap 같은거」. 재 보니 맞았다.

    그림    viewBox     글자 여백 좌/상/우/하
    fig01   780x320     0 / 1 /  86 / 15
    fig02   780x470     0 / 1 / 116 / 39
    fig03   780x360     0 / 1 / 321 / 16
    fig04   820x360     0 / 1 / 308 / 14
    fig05   972x702     0 / 1 /   5 / 45
    fig06   484x366    30 / 20 /  21 / 13      <- 혼자 균형이 맞는다
    fig07   780x300     0 / 1 / 134 / 16
    fig08  1000x700     0 / 1 /  81 / 93

**일곱 장이 왼쪽 여백 0 이다.** 제목 글자가 틀에 닿고 오른쪽은 최대 321 이
비어 있다. 문서에 `<img>` 로 넣으면 카드 테두리에 글자가 붙는다.
`fig08` 은 아래 12% 가 비어 그림이 그만큼 작게 보인다.

## 무엇을 하나

**그림을 옮기지 않는다.** `viewBox` 만 내용 상자 + 여백으로 다시 적는다.
좌표를 건드리지 않으므로 도형끼리의 관계는 그대로다.

    새 viewBox = (x0 - PAD, y0 - PAD, 폭 + 2*PAD, 높이 + 2*PAD)

## 내용 상자는 어디서 오나

글자 폭은 글꼴이 정한다. 파이썬으로는 못 잰다. **브라우저에서 `getBBox` 로
재서 아래 표에 박았다.** 그림이 바뀌면 다시 재야 한다 (`--measure` 가 그
방법을 찍어 준다). 추측으로 넣지 않는다.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

PAD = 20

# 브라우저 `getBBox` 실측 (2026-09-14 · 배경 사각형 제외 · width=1000 으로 띄움)
#   이름: (x0, y0, x1, y1)
BOX = {
    'eval-v2-fig01': (0, 1, 762, 305),
    # 2026-09-14 다시 잼: 「같은 광선 22개…」 줄이 위 상자에 파묻혀 있어
    #   그 줄부터 아래를 30 내렸다. 그래서 높이가 436 -> 466 이다.
    'eval-v2-fig02': (0, 0, 780, 466),
    'eval-v2-fig03': (0, 0, 780, 352),
    'eval-v2-fig04': (0, 0, 813.5, 354),
    'eval-v2-fig05': (0, 1, 972, 657),
    'eval-v2-fig06': (30.3, 20, 463, 353),
    'eval-v2-fig07': (0, 1, 780, 296),
    'eval-v2-fig08': (0, 1, 1000, 614),
    # 평가 하네스 그림과 Go2 제원 그림도 여백이 제각각이었다 (좌 0 이 둘).
    '20260908-go2-spec-diagram': (40, 18, 888.7, 659),
    'eval-harness-direction-gate': (32, 23, 944, 603),
    'eval-harness-four-axes': (0, 0, 954, 661),
    'eval-harness-termination': (0, 0, 948, 599),
    'eval-harness-terrains': (32, 23, 950, 613),
    'finetune-plan-flow': (30, 18.2, 1050, 644),
}
# 같은 그림의 옛 이름. 1부에서 빼면서 안 쓰게 됐지만 파일은 남아 있다.
ALIAS = {
    'eval-v2-scan-meaning': 'eval-v2-fig01',
    'eval-v2-scan-grid': 'eval-v2-fig02',
    'eval-v2-ring-section': 'eval-v2-fig03',
    'eval-v2-gap-geometry': 'eval-v2-fig04',
    'eval-v2-curves': 'eval-v2-fig05',
    'eval-v2-pipeline': 'eval-v2-fig07',
    'eval-v2-reward-map': 'eval-v2-fig08',
}

MEASURE_JS = """\
// 브라우저 콘솔에 붙여 넣어 내용 상자를 다시 잰다 (배경 사각형은 뺀다)
const host=document.createElement('div');
host.setAttribute('style','position:absolute;left:-99999px;top:0;width:1400px');
document.body.appendChild(host);
for(const n of Object.keys(BOX)){
  host.innerHTML=await (await fetch('/assets/visual/'+n+'.svg')).text();
  const svg=host.querySelector('svg'); svg.setAttribute('width','1000');
  const vb=svg.viewBox.baseVal; let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
  for(const e of svg.querySelectorAll('text,rect,circle,image,line,path,polygon,polyline')){
    let b;try{b=e.getBBox();}catch(x){continue;}
    if(!b.width&&!b.height)continue;
    if(b.width>=vb.width*0.9&&b.height>=vb.height*0.9)continue;
    x0=Math.min(x0,b.x);y0=Math.min(y0,b.y);
    x1=Math.max(x1,b.x+b.width);y1=Math.max(y1,b.y+b.height);}
  console.log(n,[x0,y0,x1,y1]);}
host.remove();
"""


def target(name):
    """이 그림의 새 viewBox 글자. 실측이 없으면 None."""
    key = ALIAS.get(name, name)
    if key not in BOX:
        return None
    x0, y0, x1, y1 = BOX[key]
    return '%g %g %g %g' % (round(x0 - PAD, 1), round(y0 - PAD, 1),
                            round(x1 - x0 + 2 * PAD, 1),
                            round(y1 - y0 + 2 * PAD, 1))


def check(root, say=print):
    """관문. 실측표에 있는 그림의 viewBox 가 그 값 그대로인지 본다.

    ★ 이것은 «여백을 다시 재는» 것이 아니다. 여백은 브라우저만 잰다.
      여기서 막는 것은 **누가 viewBox 를 되돌리거나 새 그림이 표에 없는 것**이다.
      표에 없는 그림은 «못 잼» 으로 적는다. 모르는 것을 통과로 쓰지 않는다.
    """
    seen, bad, unknown = 0, [], []
    for f in sorted(os.listdir(root)):
        if not f.endswith('.svg'):
            continue
        name = f[:-4]
        want = target(name)
        s = io.open(os.path.join(root, f), encoding='utf-8').read()
        m = re.search(r'viewBox="([^"]*)"', s)
        if want is None:
            unknown.append(f)
            continue
        seen += 1
        if not m:
            bad.append('%s 에 viewBox 가 없습니다' % f)
        elif m.group(1).strip() != want:
            bad.append('%s 의 viewBox 가 «%s» 입니다 (실측 기준 «%s»)'
                       % (f, m.group(1), want))
    say('  실측 기준을 가진 그림 %d장 검사 · 기준 없는 것 %d장'
        % (seen, len(unknown)))
    if unknown:
        say('      기준 없음: %s' % ' '.join(unknown[:5]))
        say('      `python tools/svg_pad.py --measure` 로 재서 표에 넣으십시오')
    for b in bad:
        say('      [!] ' + b)
    return not bad


def _selftest():
    """알려진 답. viewBox 를 망가뜨리면 잡아야 한다."""
    import tempfile
    d = tempfile.mkdtemp()
    name = 'eval-v2-fig08.svg'
    good = target(name[:-4])
    io.open(os.path.join(d, name), 'w', encoding='utf-8').write(
        '<svg viewBox="%s"></svg>' % good)
    ok = check(d, say=lambda *a: None)
    print('  %s 맞는 viewBox 는 통과' % ('OK ' if ok else '[X]'))
    io.open(os.path.join(d, name), 'w', encoding='utf-8').write(
        '<svg viewBox="0 0 1000 700"></svg>')
    ng = not check(d, say=lambda *a: None)
    print('  %s 옛 viewBox 는 잡음' % ('OK ' if ng else '[X]'))
    io.open(os.path.join(d, name), 'w', encoding='utf-8').write('<svg></svg>')
    ng2 = not check(d, say=lambda *a: None)
    print('  %s viewBox 없으면 잡음' % ('OK ' if ng2 else '[X]'))
    print('  %d/3' % (ok + ng + ng2))
    return ok and ng and ng2


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--selftest' in sys.argv:
        return 0 if _selftest() else 1
    if '--check' in sys.argv:
        return 0 if check(args[0] if args else 'docs/assets/visual') else 1
    if '--measure' in sys.argv:
        print(MEASURE_JS)
        return 0
    if not args:
        print('  쓰는 법: python tools/svg_pad.py [--write] <svg 폴더>')
        return 2
    write = '--write' in sys.argv
    root = args[0]
    done = skip = 0
    for f in sorted(os.listdir(root)):
        if not f.endswith('.svg'):
            continue
        name = f[:-4]
        want = target(name)
        if want is None:
            skip += 1
            continue
        p = os.path.join(root, f)
        s = io.open(p, encoding='utf-8').read()
        m = re.search(r'viewBox="([^"]*)"', s)
        if not m:
            print('  [!] %-28s viewBox 가 없습니다' % f)
            continue
        if m.group(1).strip() == want:
            print('  %-28s 이미 맞음 (%s)' % (f, want))
            continue
        print('  %-28s %s  ->  %s' % (f, m.group(1), want))
        if write:
            io.open(p, 'w', encoding='utf-8', newline='\n').write(
                s[:m.start(1)] + want + s[m.end(1):])
        done += 1
    print('  고칠 것 %d · 실측 없어 건너뜀 %d%s'
          % (done, skip, '' if write else '   (--write 를 줘야 씁니다)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
