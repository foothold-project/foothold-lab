# -*- coding: utf-8 -*-
"""모델 변환이 컷을 통째로 갈아 치웠을 때 쓰는 대체 경로.

「톤이 프리비즈다」에 대한 처방은 두 겹이었다.
  (가) 모델 변환      seedance_2_5
  (나) ffmpeg 그레이딩 (필수)

(가) 가 컷을 살리지 못하면 (나) 만 걸어 원본 시뮬레이션을 지킨다.
그림은 모델판만큼 세지 않다. 대신 화면에 있는 것이 우리가 실제로 돌린 시뮬레이션이다.

그레이딩 값은 `build-launch-a.py` 에서 읽어 온다. 두 곳에 적으면 갈라진다.

쓰는 법
  python scripts/grade-source-cut.py 07_rise [06_dolly ...]
"""
import os, re, subprocess, sys

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
CUTS4 = os.path.join(ROOT, "cuts4")
OUT = os.path.join(ROOT, "graded")


def read_grade():
    """조립 스크립트에서 GRADE 와 BLOOM 문자열을 그대로 가져온다."""
    src = open(os.path.join(HERE, "build-launch-a.py"), encoding="utf-8").read()
    ns = {}
    for name in ("GRADE", "BLOOM"):
        m = re.search(rf"^{name} = \(.*?^.*?\)$", src, re.S | re.M)
        if not m:
            sys.exit(f"{name} 를 못 찾았다")
        exec(m.group(0), ns)
    return ns["GRADE"], ns["BLOOM"]


def main(names):
    grade, bloom = read_grade()
    os.makedirs(OUT, exist_ok=True)
    for n in names:
        s = os.path.join(CUTS4, n + ".mp4")
        if not os.path.exists(s):
            sys.exit("원본 컷이 없다: " + s)
        d = os.path.join(OUT, n + ".mp4")
        r = subprocess.run([FF, "-y", "-v", "error", "-i", s,
                            "-filter_complex", f"[0:v]{grade},{bloom}[v]", "-map", "[v]", "-an",
                            "-c:v", "libx264", "-preset", "slow", "-crf", "14",
                            "-x264-params", "keyint=1", d],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print((r.stderr or "")[-1200:])
            sys.exit("실패: " + n)
        print(f"썼다  {d}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
