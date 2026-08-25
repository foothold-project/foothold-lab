#!/usr/bin/env bash
# A4 한 장 PDF. Chrome headless. 나눔고딕.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="$(cd "$ROOT/.." && pwd)"
UA="/tmp/foothold-oneshot-chrome"
FONTDIR="$ROOT/fonts"

mkdir -p "$FONTDIR"
for f in NanumGothic.ttf NanumGothicBold.ttf; do
  if [[ ! -f "$FONTDIR/$f" ]]; then
    cp "/usr/share/fonts/truetype/nanum/$f" "$FONTDIR/$f"
  fi
done

print_one() {
  local html="$1"
  local pdf="$2"
  local ua="$UA-$(basename "$pdf" .pdf | tr -cd 'A-Za-z0-9_-')"
  rm -rf "$ua"
  mkdir -p "$ua"
  python3 - "$html" "$pdf" "$ua" <<'PY'
import pathlib, subprocess, sys, urllib.parse
html, pdf, ua = sys.argv[1], sys.argv[2], sys.argv[3]
url = pathlib.Path(html).resolve().as_uri()
cmd = [
    "google-chrome",
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--disable-extensions",
    "--no-pdf-header-footer",
    f"--user-data-dir={ua}",
    "--virtual-time-budget=5000",
    f"--print-to-pdf={pdf}",
    url,
]
try:
    r = subprocess.run(cmd, timeout=35)
except subprocess.TimeoutExpired:
    r = None
p = pathlib.Path(pdf)
if not p.exists() or p.stat().st_size < 1000:
    sys.exit(1 if r is None else (r.returncode or 1))
print("wrote", pdf, p.stat().st_size)
PY
}

print_one "$ROOT/Foothold_260814.html" "$OUT/Foothold_260814.pdf"
print_one "$ROOT/Foothold(박철제님)_260824.html" "$OUT/Foothold(박철제님)_260824.pdf"
