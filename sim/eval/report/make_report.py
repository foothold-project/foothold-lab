"""종합보고서 한 판을 만든다. 명령 하나.

분류: 운영
작성: 오흥재 · 2026-09-12 02:15
근거: 팀장 「나중엔 코드 하나만 돌리면 기존꺼랑 비교할 수 있게 시스템화 하는 거 맞지?」
요지: 손으로 적은 숫자가 하나도 없게. N차에 그대로 다시 쓴다
상태: 확정

## 두 단계

```
    measure.py   원자료를 세고 차트 SVG 를 굽는다   -> report_numbers.json · chart_*.svg
    page.py      그 값으로 HTML 을 짠다             -> report-v1.html
```

나눈 이유는 **수치와 글을 따로 고칠 수 있게** 하려는 것이다. 문장을 다듬을 때
27,000 판을 다시 세지 않아도 된다.

## 관문

`measure.py` 는 시작하자마자 `matrix.required_cells` 와 `matrix.missing` 으로
선언된 칸이 다 찼는지 센다. **비어 있으면 죽는다.** `--allow_missing` 을 주면
넘어가되, 무엇이 비었는지 보고서 본문이 표와 경고로 밝힌다.

`확인됨` (2026-09-12 · 1차 발행 전 검증이 「본문은 14,400 판이라면서 곡선
18칸이 비었다」를 잡았다).

## 쓰는 법

```
python sim/eval/report/make_report.py
python sim/eval/report/make_report.py --allow_missing     # 빈 칸을 밝히고 넘어간다
```

어디에 무엇을 두는지는 환경 변수로 바꾼다.

| 변수 | 기본값 |
|---|---|
| `FOOTHOLD_REPO` | 이 파일 기준 저장소 뿌리 |
| `FOOTHOLD_REPORT_OUT` | `sim/eval/results/report-v1` |
| `FOOTHOLD_GALLERY` | `sim/eval/results/20260911-gallery-1080` |
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def stage(name, argv):
    print("[%s]" % name)
    done = subprocess.run([sys.executable, os.path.join(HERE, name)] + argv)

    if done.returncode != 0:
        raise SystemExit("%s 가 실패했다 (종료 %d). 멈춘다" % (name, done.returncode))


def main():
    # ★ 2026-09-14 (#412). 모르는 인자를 조용히 넘기지 않는다.
    #   같은 날 `build.py --out` 이 `--repro` 없이는 조용히 무시되고 실제
    #   배포본에 쓰는 것을 겪었다. 여기도 `--out` 을 안 받는데 주면 아무 말
    #   없이 흘려보냈다. 목적지는 `FOOTHOLD_REPORT_OUT` 로만 바꾼다.
    KNOWN = ("--link", "--allow_missing_clips", "--no_audit", "--allow_missing")
    unknown = [a for a in sys.argv[1:]
               if a.startswith("--") and a not in KNOWN]
    if unknown:
        print("  [!] 모르는 인자: %s" % " ".join(unknown))
        print("      이 도구가 받는 것: %s" % " ".join(KNOWN))
        if any(a == "--out" for a in unknown):
            print("      산출 자리는 인자가 아니라 환경 변수로 바꿉니다:")
            print("        FOOTHOLD_REPORT_OUT=<폴더> python "
                  "sim/eval/report/make_report.py")
        raise SystemExit(2)

    argv = [a for a in sys.argv[1:] if a != "--no_audit"]

    # `--link <앞머리>` 는 글을 짜는 쪽만 쓴다. 수치 쪽에는 안 넘긴다.
    link = []

    if "--link" in argv:
        i = argv.index("--link")
        link = argv[i:i + 2]
        argv = argv[:i] + argv[i + 2:]

    # 컷이 없어도 넘어가는 것은 «글 짜는 쪽» 인자다.
    if "--allow_missing_clips" in argv:
        argv.remove("--allow_missing_clips")
        link.append("--allow_missing_clips")

    # 산출 자리를 **먼저** 정한다. 곡선이 그 값을 쓴다.
    out = os.environ.get("FOOTHOLD_REPORT_OUT") or os.path.join(
        HERE, "..", "results", "report-v1")

    stage("measure.py", argv)
    # 곡선은 글보다 먼저 굽는다. `page.py` 가 그 파일을 읽는다.
    stage("curve.py", ["--out", os.path.abspath(os.path.join(out, "chart_curve.svg"))])
    stage("page.py", link)

    # **관문은 마지막 단계다.** 따로 돌리게 두면 안 돌린다.
    # `--no_audit` 은 배포 전 자리가 아직 안 갖춰졌을 때만 쓴다.
    audit = "--no_audit" not in sys.argv

    page = os.path.abspath(os.path.join(out, "report-v1.html"))

    if not os.path.isfile(page):
        raise SystemExit("보고서가 안 나왔다: %s" % page)

    print()
    print("만들었다 · %s (%.2f MB)" % (page, os.path.getsize(page) / 1048576))

    # ★ 2026-09-14. 순서를 틀리면 조용히 되돌아간다.
    #   보고서를 배포 폴더로 «복사» 하면 사이트 빌드가 넣어 둔 것이 지워진다
    #   (전역바 · 테마 토글 · 그림 테마 표시 data-themed). 실제로 한 번 지웠고
    #   아무 오류도 안 났다. 그 페이지만 다크에서 그림이 안 따라온다.
    #
    #   지켜야 할 순서:  make_report -> 배포본으로 복사 -> **사이트 빌드**
    #   빌드를 먼저 돌리고 복사하면 안 된다.
    print('  [순서] 복사한 뒤 `python web/_build/build.py --skip-secure` 를 '
          '한 번 더 돌립니다')
    print('         (전역바·테마 토글·그림 테마 표시가 복사로 지워집니다)')

    if audit:
        print()
        stage("audit.py", [])
    else:
        print("  [!] 관문을 건너뛰었다. 발행 전에 audit.py 를 반드시 돌린다")


if __name__ == "__main__":
    main()
