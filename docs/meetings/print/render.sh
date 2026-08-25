#!/usr/bin/env bash
# A4 한 장 PDF. Chrome headless.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="$(cd "$ROOT/.." && pwd)"
UA="/tmp/foothold-oneshot-chrome"

print_one() {
  local html="$1"
  local pdf="$2"
  mkdir -p "$UA"
  timeout 40 google-chrome \
    --headless=new \
    --disable-gpu \
    --no-first-run \
    --disable-extensions \
    --no-pdf-header-footer \
    --user-data-dir="$UA" \
    --virtual-time-budget=4000 \
    --print-to-pdf="$pdf" \
    "file://$html"
  echo "wrote $pdf"
}

print_one "$ROOT/260814_Foothold_회의록.html" "$OUT/Foothold_회의록_260814.pdf"
print_one "$ROOT/260824_Foothold_정리본_박철제.html" "$OUT/Foothold_정리본(박철제님)_260824.pdf"
