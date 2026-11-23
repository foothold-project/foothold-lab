#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 make_report.py
google-chrome --headless=new --disable-gpu --no-sandbox --allow-file-access-from-files \
  --no-pdf-header-footer --print-to-pdf="$PWD/report.pdf" "file://$PWD/report.html" >/dev/null 2>&1
pdfinfo report.pdf | grep -E 'Pages|File size'
sha256sum report.md report.html report.pdf > SHA256SUMS
