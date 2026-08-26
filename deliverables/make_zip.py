# -*- coding: utf-8 -*-
"""제출용 zip 을 만든다.

저장소 폴더는 발표 시점 기준(plan · midterm · final · logs)이고,
운영진이 요구하는 zip 안 폴더는 공식 이름(1. 기획 및 분석 ...)이다.
어느 파일이 어느 공식 폴더로 가는지는 아래 SUBMIT 표가 정한다.
사람이 제출 직전에 폴더를 다시 짜면 실수가 나므로 스크립트가 한다.

    python deliverables/make_zip.py

내는 것: deliverables/_out/(트랙명_팀명)팀장이름.zip
"""
import io, os, sys, zipfile

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '_out')

TRACK, TEAM, LEADER = 'AI피지컬', 'FOOTHOLD', '오흥재'   # 학원 공식 명칭 (팀장 확인 2026-08-27)

# (저장소 경로, zip 안 공식 폴더). 여기 없는 파일은 제출물이 아니다.
SUBMIT = [
    ('plan/brainstorming.md',    '1. 기획 및 분석'),
    ('plan/proposal-summary.md', '1. 기획 및 분석'),
    ('plan/proposal-deck.md',    '1. 기획 및 분석'),
    ('plan/wbs.xlsx',            '3. 구현'),
    # midterm/ final/ 산출물은 발표가 끝나면 «4. 완료» 로 여기에 추가한다
]
NEEDS_CONVERT = ('.md',)   # 운영진은 hwp / xlsx / pptx / pdf 를 받는다


def strip_internal(md):
    """제출본에서 내부 표시를 걷어낸다.

    «> 분류: 계획» «> 상태: 초안» «> 완료 기준: 팀장이 판정한다» 는 우리 운영 표시다.
    채점받는 문서에 «상태: 초안» 이 붙어 있으면 능동적으로 해롭다.
    """
    out, skip = [], False
    for ln in md.split(chr(10)):
        t = ln.strip()
        if any(t.startswith('> %s:' % f) for f in ('분류', '작성', '근거', '요지', '상태')):
            if t.startswith('> 작성:'):
                out.append(ln)          # 작성자·날짜는 남긴다
            continue
        if t.startswith('> **완료 기준'):
            skip = True
            continue
        if skip:
            if t.startswith('>'):
                continue
            skip = False
        out.append(ln)
    body = chr(10).join(out)
    while chr(10) * 3 in body:
        body = body.replace(chr(10) * 3, chr(10) * 2)
    return body


def check_stale(items):
    """SUBMIT 표가 낡았는지 스스로 잡는다.

    자기 표만 검증하는 자기검증은 검증이 아니다. 실제 폴더와 대조한다.
    """
    listed = {rel for rel, _ in SUBMIT}
    on_disk = set()
    for d in ('plan', 'midterm', 'final'):
        root = os.path.join(HERE, d)
        if not os.path.isdir(root):
            continue
        for f in sorted(os.listdir(root)):
            if f.endswith(('.md', '.xlsx', '.pdf', '.pptx', '.hwp')):
                on_disk.add('%s/%s' % (d, f))
    missing = sorted(on_disk - listed)
    # 같은 이름의 더 나은 형식이 있으면 알린다 (md 옆에 xlsx 가 생긴 경우)
    upgrades = []
    for rel, _ in SUBMIT:
        if rel.endswith('.md'):
            for ext in ('.xlsx', '.pdf', '.pptx', '.hwp'):
                cand = rel[:-3] + ext
                if cand in on_disk:
                    upgrades.append((rel, cand))
    return missing, upgrades


def main():
    items = []
    for rel, official in SUBMIT:
        full = os.path.join(HERE, rel)
        if not os.path.isfile(full):
            raise SystemExit('제출 목록에 있는 파일이 없습니다: %s' % rel)
        items.append(('%s/%s' % (official, os.path.basename(rel)), full))
    if not items:
        raise SystemExit('제출할 파일이 없습니다. 중단합니다.')

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, '(%s_%s)%s.zip' % (TRACK, TEAM, LEADER))
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for arc, full in items:
            if arc.endswith('.md'):
                z.writestr(arc, strip_internal(io.open(full, encoding='utf-8').read()))
            else:
                z.write(full, arc)

    with zipfile.ZipFile(path) as z:            # 되읽어 확인
        got = sorted(z.namelist())
    if got != sorted(a for a, _ in items):
        raise SystemExit('zip 내용이 예상과 다릅니다.')

    print('만들었습니다: %s' % path)
    for a in got:
        print('   %s' % a)

    missing, upgrades = check_stale(items)
    if upgrades:
        print('')
        print('★ 더 나은 형식이 이미 있습니다. SUBMIT 표를 바꾸십시오.')
        for a, b in upgrades:
            print('   %s -> %s' % (a, b))
    if missing:
        print('')
        print('★ 폴더에 있는데 제출 목록에 없는 파일 %d개.' % len(missing))
        print('  발표가 끝나면 SUBMIT 표에 넣으십시오. 안 넣으면 영영 안 나갑니다.')
        for m in missing:
            print('   %s' % m)

    todo = [a for a in got if a.endswith(NEEDS_CONVERT)]
    if todo:
        print('')
        print('★ 아직 md 입니다. 운영진 제출 형식은 hwp / xlsx / pptx / pdf 입니다.')
        print('  제출 전에 변환본으로 SUBMIT 표를 바꾸십시오.')
        for a in todo:
            print('   %s' % a)


if __name__ == '__main__':
    main()
