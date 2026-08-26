# -*- coding: utf-8 -*-
"""제출용 zip 을 만든다.

저장소 폴더는 발표 시점 기준(plan · midterm · final · logs)이고,
운영진이 요구하는 zip 안 폴더는 공식 이름(1. 기획 및 분석 ...)이다.
어느 파일이 어느 공식 폴더로 가는지는 아래 SUBMIT 표가 정한다.
사람이 제출 직전에 폴더를 다시 짜면 실수가 나므로 스크립트가 한다.

    python deliverables/make_zip.py

내는 것: deliverables/_out/(트랙명_팀명)팀장이름.zip
"""
import os, sys, zipfile

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '_out')

TRACK, TEAM, LEADER = 'AI피지컬', 'FOOTHOLD', '오흥재'   # 학원 공식 명칭 (팀장 확인 2026-08-27)

# (저장소 경로, zip 안 공식 폴더). 여기 없는 파일은 제출물이 아니다.
SUBMIT = [
    ('plan/brainstorming.md',    '1. 기획 및 분석'),
    ('plan/proposal-summary.md', '1. 기획 및 분석'),
    ('plan/proposal-deck.md',    '1. 기획 및 분석'),
    ('plan/wbs.md',              '3. 구현'),          # xlsx 가 생기면 그걸로 바꾼다
    # midterm/ final/ 산출물은 발표가 끝나면 «4. 완료» 로 여기에 추가한다
]
NEEDS_CONVERT = ('.md',)   # 운영진은 hwp / xlsx / pptx / pdf 를 받는다


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
            z.write(full, arc)

    with zipfile.ZipFile(path) as z:            # 되읽어 확인
        got = sorted(z.namelist())
    if got != sorted(a for a, _ in items):
        raise SystemExit('zip 내용이 예상과 다릅니다.')

    print('만들었습니다: %s' % path)
    for a in got:
        print('   %s' % a)

    todo = [a for a in got if a.endswith(NEEDS_CONVERT)]
    if todo:
        print('')
        print('★ 아직 md 입니다. 운영진 제출 형식은 hwp / xlsx / pptx / pdf 입니다.')
        print('  제출 전에 변환본으로 SUBMIT 표를 바꾸십시오.')
        for a in todo:
            print('   %s' % a)


if __name__ == '__main__':
    main()
