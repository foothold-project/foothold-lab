# -*- coding: utf-8 -*-
r"""`web/_build/scan.py` 의 주민등록번호 과탐을 «규칙으로» 고친다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: `web/_build/scan.py:168` 「값 하나를 ALLOW 로 미는 대신 규칙을 고친다」
      (2026-08-11 SVG 좌표 과탐 때 정한 선례) · `scan.py:284-286` BLOCK 은
      ALLOW 를 «안 본다»
요지: 갤러리 manifest 의 sha256 안 13자리 숫자열이 주민등록번호로 잡힌다.
      32자 이상 16진 연속을 검사 전에 가린다. 자가검증에 과탐 둘을 박는다.

가려도 안전한 근거
    BLOCK 의 비밀 규칙은 전부 고유한 접두사나 모양을 가진다.
      -----BEGIN · sk- · sk-ant- · gh?_ · AKIA · xox?- · 숫자9~10: · Bearer
      카드번호는 네 자리씩 구분자 · 이메일은 @ · 경로는 드라이브문자나 OneDrive
    **맨 16진 문자열인 규칙이 하나도 없다.** WARN 의 MAC 주소도 콜론을 쓴다.
"""

from __future__ import annotations

import ast
import io
import sys

P = "web/_build/scan.py"

MASK_BLOCK = r'''

# 긴 16진 문자열(해시)은 개인정보가 아니다. 갤러리 manifest 의 sha256 안에 있는
#   13자리 숫자열이 주민등록번호로 잡혔다(2026-09-28). 값을 ALLOW 로 미는 대신
#   규칙을 고친다 (2026-08-11 SVG 좌표 때와 같은 처리다).
#
#   **BLOCK 은 ALLOW 를 안 본다** (`scan_text` 의 BLOCK 순회에 allowed 검사가
#   없다). 그래서 이 종류의 과탐은 «가리기» 로만 풀린다.
#
#   가려도 안전한 근거: BLOCK 의 비밀 규칙은 전부 고유한 접두사나 모양을 가진다.
#   맨 16진 문자열인 규칙이 하나도 없다. WARN 의 MAC 주소도 콜론을 쓴다.
#   곧 32자 이상 16진 연속을 가려도 «가려지는 비밀이 없다».
HEX_RUN = re.compile(r'\b[0-9a-fA-F]{32,}\b')


def mask_hashes(text):
    """긴 16진 문자열을 공백으로 덮는다. 줄바꿈은 보존한다."""
    return HEX_RUN.sub(lambda m: re.sub(r'[^\n]', ' ', m.group(0)), text)


def mask_noise(text):
    """검사 전에 «개인정보가 살지 않는 자리» 를 덮는다."""
    return mask_hashes(mask_geometry(text))
'''

NEG_ADD = '''    # 2026-09-28 실제 과탐: 갤러리 manifest 의 sha256 안 13자리 숫자열
    ('주민등록번호',
     '"sha256": "f8ca0347664793797e29b6e76a42b6dbb1045fddec186a4e3de071642ed94bbb"'),
    ('주민등록번호',
     '"sha256": "9f34f7905314930720cf7e8a902c7d54cf6eb5be383b3f71bb414339a0ccb731"'),
'''


def main() -> int:
    t = io.open(P, encoding="utf-8").read()

    # 1 · 무용지물인 ALLOW 항목을 되돌린다
    head = "    # ── 2026-09-28. SHA-256 해시"
    if head in t:
        s = t.find(head)
        tailmark = "'2026-09-28'),\n\n"
        e = t.find(tailmark, s)
        assert e > s, "ALLOW 끝을 못 찾았다"
        e2 = t.find(tailmark, e + 1)
        e = (e2 if e2 > 0 else e) + len(tailmark)
        t = t[:s] + t[e:]
        print("  ALLOW 항목을 되돌렸다 (BLOCK 은 ALLOW 를 안 본다)")
    else:
        print("  ALLOW 항목이 없다 (이미 되돌렸거나 안 넣었다)")

    # 2 · 해시 가리기를 더한다
    if "def mask_hashes(" in t:
        print("  mask_hashes 가 이미 있다")
    else:
        anchor = "    return GEOMETRY_ATTR.sub(lambda m: re.sub(r'[^\\n]', ' ', m.group(0)), text)\n"
        assert anchor in t, "mask_geometry 본문을 못 찾았다"
        t = t.replace(anchor, anchor + MASK_BLOCK, 1)
        print("  mask_hashes · mask_noise 를 더했다")

    # 3 · 두 호출 자리를 바꾼다
    n1 = t.count("mask_geometry(sample)")
    n2 = t.count("text = mask_geometry(text)")
    t = t.replace("mask_geometry(sample)", "mask_noise(sample)")
    t = t.replace("text = mask_geometry(text)", "text = mask_noise(text)")
    print("  호출 교체 · 자가검증 %d 곳 · 본검사 %d 곳" % (n1, n2))
    if (n1, n2) != (1, 1):
        print("  ** 호출 자리가 기대와 다르다. 멈춘다 **")
        return 1

    # 4 · 자가검증에 과탐 둘을 박는다
    # 기준 줄을 «내용으로» 찾는다. 한글 이스케이프를 손으로 쓰다 두 번 틀렸다.
    if "f8ca0347664793797" in t.split("SELFTEST_NEGATIVE")[-1]:
        print("  자가검증 항목이 이미 있다")
    else:
        cand = [l for l in t.split("\n") if "184.1496124267578" in l]
        if not cand:
            print("  ** 자가검증 기준 줄을 못 찾았다. 멈춘다 **")
            return 1
        neg = cand[0] + "\n"
        t = t.replace(neg, neg + NEG_ADD, 1)
        print("  자가검증에 과탐 둘을 박았다")

    ast.parse(t)
    io.open(P, "w", encoding="utf-8").write(t)
    print("  문법 통과 · 썼다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
