"""벤치마크 하네스 Candidate 스냅샷을 문서에서 다시 뽑아 대조한다.

`benchmark-setup-lim.md` 와 그 원본 제출본은 하네스 소스를
`cat > <경로> <<'PY' ... PY` 히어독으로 품고 있다.
이 스크립트는 그 히어독을 그대로 풀어 candidate-20260822/ 와 대조한다.

표준 라이브러리만 쓴다. GPU 도 Isaac 도 필요 없다.

    python sim/eval/provenance/extract_candidate.py --check
    python sim/eval/provenance/extract_candidate.py --out <디렉터리>
"""

import argparse
import hashlib
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SNAPSHOT = os.path.join(HERE, "candidate-20260822")

SOURCES = [
    os.path.join(REPO, "docs", "research", "benchmark-setup-lim.md"),
    os.path.join(
        REPO,
        "inbox",
        "lim",
        "20260822-베이스라인 모델의 간단한 미경험 험지 성능 측정.md",
    ),
]

HEREDOC = re.compile(r"^\s*cat > (\S+) <<'(\w+)'\s*$")


def extract(path):
    """히어독 블록을 {파일이름: 바이트} 로 푼다."""
    lines = io.open(path, encoding="utf-8").read().split("\n")
    out = {}
    i = 0
    while i < len(lines):
        m = HEREDOC.match(lines[i])
        if not m:
            i += 1
            continue
        name, term = os.path.basename(m.group(1)), m.group(2)
        i += 1
        body = []
        while i < len(lines) and lines[i].strip() != term:
            body.append(lines[i])
            i += 1
        # 히어독은 마지막 줄에도 개행을 붙인다. 실행본과 같게 맞춘다.
        out[name] = ("\n".join(body) + "\n").encode("utf-8")
        i += 1
    return out


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_sums():
    sums = {}
    p = os.path.join(SNAPSHOT, "SHA256SUMS")
    for line in io.open(p, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        h, name = line.split(None, 1)
        sums[name.lstrip("*")] = h
    return sums


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="스냅샷과 대조만 한다")
    ap.add_argument("--out", help="추출본을 이 디렉터리에 쓴다")
    args = ap.parse_args()

    extracted = [(p, extract(p)) for p in SOURCES]

    ok = True

    # 1. 문서 두 벌이 서로 같은가
    base_path, base = extracted[0]
    for path, other in extracted[1:]:
        for name in sorted(set(base) | set(other)):
            same = base.get(name) == other.get(name)
            print(f"[{'OK ' if same else 'DIFF'}] 문서 대조 {name}")
            ok = ok and same

    # 2. 스냅샷과 같은가
    if args.check or not args.out:
        sums = read_sums()
        for name, data in sorted(base.items()):
            want = sums.get(name)
            got = digest(data)
            same = want == got
            print(f"[{'OK ' if same else 'FAIL'}] 스냅샷 대조 {name}  {got}")
            ok = ok and same

    # 3. 요청하면 쓴다
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        for name, data in sorted(base.items()):
            with open(os.path.join(args.out, name), "wb") as f:
                f.write(data)
            print(f"[WROTE] {name}  {len(data)} bytes")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
