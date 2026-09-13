# -*- coding: utf-8 -*-
"""절 참조가 가리키는 절이 실제로 있는지 본다.

★ 2026-08-28. `FLOW.md` 를 v2.0 으로 다시 쓰면서 절 번호가 통째로 바뀌었다.
  옛 §3 은 「증류」였고 새 §3 은 「트랙 A · 시뮬에서 학습」이다.
  그런데 다른 문서 두 곳이 여전히 **「FLOW §3 (증류)」** 를 가리키고 있었다.

  링크는 안 깨졌다. `FLOW.md` 는 그대로 있으니 링크 검사([3.6])는 통과한다.
  **깨진 것은 링크가 아니라 «그 안의 몇 번째 절인가» 다.**
  기존 관문 어느 것도 이 층위를 안 봤다 (커널 철칙 4).

  자기 문서 안의 참조도 같이 본다. 절을 재배치하면 «(§3-1 참조)» 가 먼저 어긋난다.

두 층위를 본다
  ① 그 절이 **있는가**
  ② 딱지가 그 절의 **제목과 맞는가**

  ②가 실제로 일어난 쪽이다. `FLOW.md` 를 다시 썼을 때 §3 은 그대로 있었다.
  없어진 것이 아니라 뜻이 바뀌었다. **①만 보는 검사는 이것을 못 잡는다.**
  한 층위만 보면 나머지 층위에서 조용히 무너진다 (커널 철칙 4).

무엇을 절로 세나
  `## 3. 제목`  -> 3
  `### 3-1. 제목` -> 3-1
  번호가 안 붙은 제목은 애초에 §로 가리킬 수 없으므로 세지 않는다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 절 번호. `## 3.` · `### 3-1.` · `## 2.5` 를 모두 센다.
#   ★ 2026-08-28 감사에서 잡혔다. 처음에는 «숫자 뒤 마침표 뒤 공백» 을 요구해서
#     `## 2.5 일감의 계층` 을 §2 로 읽었다. COLLAB 이 실제로 그 꼴을 쓴다.
SECT = re.compile(r'^#{2,4}\s+(\d+(?:[-.]\d+)?)\.?\s+', re.M)
TITLED = re.compile(r'^#{2,4}\s+(\d+(?:[-.]\d+)?)\.?\s+(.+?)\s*$', re.M)
# 「§3 (증류)」처럼 참조 뒤에 붙는 딱지. 이것이 그 절의 제목과 맞는지 본다.
LABEL = re.compile(r'^\s*[(（]([^)）]{1,24})[)）]')
# 딱지 노릇을 못 하는 말. 제목과 대조해 봐야 뜻이 없다.
STOP = ('참조', '아래', '위', '앞', '뒤', '항목', '부분', '표', '그림', '절', '번')
TOKEN = re.compile(r'[가-힣A-Za-z]{2,}')
REF = re.compile(r'§\s*(\d+(?:[-.]\d+)?)')
# 참조 앞에 붙는 문서 이름 세 꼴.
#   ① `[글](경로.md) §3`   ② `경로/이름.md` §3 (역따옴표)   ③ FLOW §3 (맨이름)
LINKED = re.compile(r'\]\(([^)]+?\.md)\)[^§]{0,12}$')
TICKED = re.compile(r'`([^`]+?)`[^§]{0,4}$')
BARE = re.compile(r'([A-Z][A-Z0-9-]{2,})\s*$')
# «자기 문서 안» 이라고 확신할 수 있는 모양만 자기 참조로 본다.
#   (§3-1) · 아래 §2 · 위 §4 · 같은 §1
# 그 밖에 «관계표 §4» 처럼 한글 이름으로 남을 가리키는 것은 대상을 특정할 수
# 없으므로 **건너뛴다.** 관문이 시끄러우면 무시당하고, 무시당하는 관문은 없는 것과 같다.
SELF = re.compile(r'(\(|\[|위|아래|앞|뒤|같은|본 문서|이 문서)\s*$')
# `[FLOW §6](FLOW.md)` 처럼 링크 «글자» 안에 든 경우
INLINK = re.compile(r'\[[^\]]*§\s*(\d+(?:[-.]\d+)?)[^\]]*\]\(([^)]+?\.md)\)')


def sections(text):
    return set(SECT.findall(text))


def titles(text):
    return dict(TITLED.findall(text))


def label_fits(label, title):
    """딱지가 그 절의 제목과 «같은 것을 말하는가».

    ★ 이것이 실제로 일어난 사고다. `FLOW.md` 를 다시 썼을 때 §3 은 그대로
      있었다. 없어진 것이 아니라 **뜻이 바뀌었다** (증류 -> 트랙 A 시뮬 학습).
      번호만 보는 검사는 이것을 못 잡는다.

    낱말 하나라도 겹치면 통과시킨다. 좁게 잡으면 관문이 시끄러워진다.
    """
    words = [w for w in TOKEN.findall(label) if w not in STOP]
    if not words:
        return True                     # 대조할 말이 없다
    return any(w in title for w in words)


def _resolve(base_dir, target, index):
    """상대경로 또는 맨이름을 index 의 열쇠로 바꾼다."""
    if target.endswith('.md'):
        p = os.path.normpath(os.path.join(base_dir, target))
        return p if p in index else None
    for p in index:
        if os.path.splitext(os.path.basename(p))[0].upper() == target.upper():
            return p
    return None


def _judge(bad, path, i, tgt, num, after, index):
    """절이 있는가, 그리고 딱지가 그 절의 제목과 맞는가."""
    if num not in sections(index[tgt]):
        bad.append((path, i, tgt, num, None))
        return
    lm = LABEL.match(after or '')
    if lm and not label_fits(lm.group(1), titles(index[tgt]).get(num, '')):
        bad.append((path, i, tgt, num, lm.group(1)))


def scan(index):
    """[(파일, 줄번호, 가리킨 문서, 절번호, 어긋난 딱지 or None)]."""
    bad = []
    for path, text in index.items():
        base = os.path.dirname(path)
        for i, line in enumerate(text.split(chr(10)), 1):
            # 인용 블록은 «남의 말» 이다. 그 안의 §5.3 은 우리 문서의 절이 아니라
            # 인용된 원문(ISO 표준 · 논문 · 남의 README)의 절이다. 우리 절 번호로
            # 대조하면 없는 절을 가리킨다고 잡는다.
            # 2026-09-05: 직진성-외부표준.md 가 ISO 18646-1 §5.2 · §5.3 을 인용했는데
            # 「자기 안 §5.3 (그런 절이 없습니다)」로 배포가 섰다. 거짓 양성이다.
            if line.lstrip().startswith('>'):
                continue
            seen = set()
            # ① 링크 글자 안에 든 참조
            for m in INLINK.finditer(line):
                tgt = _resolve(base, m.group(2), index)
                seen.add(m.start())
                if tgt:
                    _judge(bad, path, i, tgt, m.group(1), line[m.end():], index)
            # ② 그 밖의 참조
            for m in REF.finditer(line):
                if any(abs(m.start() - s) < 60 for s in seen):
                    continue
                before = line[:m.start()]
                lm = LINKED.search(before)
                tm = TICKED.search(before)
                bm = BARE.search(before)
                if lm:
                    tgt = _resolve(base, lm.group(1), index)
                elif tm:
                    tgt = _resolve(base, tm.group(1), index)
                elif bm:
                    tgt = _resolve(base, bm.group(1), index)
                elif SELF.search(before):
                    tgt = path                      # 자기 문서 안의 참조
                else:
                    tgt = None                      # 대상을 특정 못 함. 건너뜀
                if tgt:
                    _judge(bad, path, i, tgt, m.group(1), line[m.end():], index)
    return bad


def _kat():
    """★ 답을 아는 입력으로 먼저 시험한다."""
    n = chr(10)
    s = chr(0xa7)
    flow = ('## 1. 하나' + n + '## 3. 셋' + n + '### 3-1. 셋의 하나' + n +
            '## 2.5 소수점 절' + n)
    other = ('[FLOW.md](FLOW.md) ' + s + '3 은 있다' + n +
             '[FLOW.md](FLOW.md) ' + s + '9 는 없다' + n +
             '[FLOW ' + s + '3-1](FLOW.md) 링크 안, 있다' + n +
             '[FLOW ' + s + '7](FLOW.md) 링크 안, 없다' + n +
             '## 2. 내 절' + n + '내 안의 (' + s + '2) 는 있다' + n +
             '내 안의 (' + s + '8) 은 없다' + n +
             '`FLOW.md` ' + s + '3 은 있다 (역따옴표)' + n +
             '`FLOW.md` ' + s + '4 는 없다 (역따옴표)' + n +
             '관계표 ' + s + '9 는 대상을 몰라 건너뛴다' + n)
    idx = {'FLOW.md': flow, 'OTHER.md': other}
    bad = scan(idx)
    got = sorted((os.path.basename(t), num) for _, _, t, num, _ in bad)
    want = [('FLOW.md', '4'), ('FLOW.md', '7'), ('FLOW.md', '9'), ('OTHER.md', '8')]
    if got != want:
        return False, '잡아야 할 %s · 실제 %s' % (want, got)
    if not sections(flow) == {'1', '3', '3-1', '2.5'}:
        return False, '절 번호를 잘못 셈'

    # ★ 실제로 일어난 사고: 절은 있는데 뜻이 바뀐 경우
    flow2 = '## 3. 트랙 A · 시뮬에서 학습' + n
    idx2 = {'FLOW.md': flow2,
            'A.md': '[FLOW.md](FLOW.md) ' + s + '3 (증류)' + n,
            'B.md': '[FLOW.md](FLOW.md) ' + s + '3 (트랙 A · 시뮬에서 학습)' + n,
            'C.md': '[FLOW.md](FLOW.md) ' + s + '3 (아래 참조)' + n}
    got2 = sorted(os.path.basename(p) for p, _, _, _, lab in scan(idx2) if lab)
    if got2 != ['A.md']:
        return False, '딱지 대조: A.md 만 잡아야 하는데 %s' % got2
    return True, ''


def main(lab=None):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False

    if lab is None:
        import docs_pages
        lab = next((p for p in docs_pages.LAB_CANDIDATES
                    if os.path.isdir(os.path.join(p, 'docs'))), None)
    if not lab:
        print('  [!] foothold-lab 을 못 찾음. 건너뜀')
        return True

    root = os.path.join(lab, 'docs')
    index = {}
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith('.md'):
                p = os.path.normpath(os.path.join(dirpath, f))
                index[p] = io.open(p, encoding='utf-8', newline=None).read()

    bad = scan(index)
    n_ref = sum(len(REF.findall(t)) for t in index.values())
    print('  문서 %d개 · 절 참조 %d곳' % (len(index), n_ref))
    if not bad:
        print('  가리키는 절이 모두 있습니다')
        return True

    for path, line, tgt, num, mislabel in bad[:12]:
        here = os.path.relpath(path, lab).replace(os.sep, '/')
        there = os.path.relpath(tgt, lab).replace(os.sep, '/')
        where = '자기 안' if tgt == path else there
        if mislabel is None:
            print('  ★ %s:%d -> %s §%s (그런 절이 없습니다)' % (here, line, where, num))
        else:
            print('  ★ %s:%d -> %s §%s 를 「%s」라 부르는데 실제 제목은 「%s」입니다'
                  % (here, line, where, num, mislabel,
                     titles(index[tgt]).get(num, '?')))
    if len(bad) > 12:
        print('    ... 그 밖 %d곳' % (len(bad) - 12))
    print('    문서를 다시 쓰면 남이 가리키던 절 번호와 그 뜻이 조용히 어긋납니다.')
    return False


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
