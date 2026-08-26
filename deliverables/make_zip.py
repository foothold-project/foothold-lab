# -*- coding: utf-8 -*-
"""제출용 zip 을 만든다.

저장소 폴더는 영문(01-plan)이고 운영진이 요구하는 폴더는 한글(1. 기획 및 분석)이다.
사람이 이름을 고치면 잊는다. 이 스크립트가 고친다.

    python deliverables/make_zip.py

내는 것: deliverables/_out/(트랙명_팀명)팀장이름.zip
"""
import io, os, sys, zipfile

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '_out')

TRACK, TEAM, LEADER = '피지컬AI', 'FOOTHOLD', '오흥재'   # 트랙명 표기는 운영진 확인 필요

# 저장소 폴더 -> 제출 zip 안의 공식 폴더 이름
MAP = [
    ('01-plan',  '1. 기획 및 분석'),
    ('03-build', '3. 구현'),
    ('04-done',  '4. 완료'),
]
# 「2. 설계」는 넣지 않는다. 실증 프로젝트에 해당 항목이 없다.

SKIP = {'README.md'}          # 우리 안내문은 제출물이 아니다
NEEDS_CONVERT = ('.md',)      # 운영진은 hwp/xlsx/pptx 를 받는다


def collect():
    """(zip 안 경로, 원본 경로) 목록. 하나도 못 모으면 예외를 낸다."""
    items = []
    for src_dir, official in MAP:
        root = os.path.join(HERE, src_dir)
        if not os.path.isdir(root):
            raise SystemExit('폴더가 없습니다: %s' % root)
        for dirpath, _, files in os.walk(root):
            for f in sorted(files):
                if f in SKIP:
                    continue
                full = os.path.join(dirpath, f)
                rel = os.path.relpath(full, root).replace(os.sep, '/')
                items.append(('%s/%s' % (official, rel), full))
    if not items:                                   # 조용한 실패 방지
        raise SystemExit('넣을 파일이 하나도 없습니다. 중단합니다.')
    return items


def main():
    items = collect()
    os.makedirs(OUT, exist_ok=True)
    name = '(%s_%s)%s.zip' % (TRACK, TEAM, LEADER)
    path = os.path.join(OUT, name)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for arc, full in items:
            z.write(full, arc)

    # 되읽어 확인한다. 쓴 것과 읽은 것이 같은지 본다.
    with zipfile.ZipFile(path) as z:
        got = sorted(z.namelist())
    want = sorted(a for a, _ in items)
    if got != want:
        raise SystemExit('zip 내용이 예상과 다릅니다.')

    print('만들었습니다: %s' % path)
    print('파일 %d개' % len(got))
    for a in got:
        print('   %s' % a)

    todo = [a for a in got if a.endswith(NEEDS_CONVERT)]
    if todo:
        print('')
        print('★ 아직 md 입니다. 운영진은 hwp / xlsx / pptx 를 받습니다.')
        print('  제출 전에 아래를 변환해서 다시 넣으세요.')
        for a in todo:
            print('   %s' % a)


if __name__ == '__main__':
    main()
