#!/usr/bin/env bash
# 데이터 산출물 명세서 PDF 다시 만들기.
# 쓰는 법: spec.html 맨 위 「조정 칸」 숫자를 고친 뒤 이 폴더에서 `bash render.sh`
# 결과: ../FOOTHOLD_UnitreeGo2_RL_Data_Deliverable/FOOTHOLD_RL_Data_Deliverable_Spec.pdf 를 덮어쓰고 쪽 수를 보여 준다.
set -e
cd "$(dirname "$0")"
OUT=../FOOTHOLD_UnitreeGo2_RL_Data_Deliverable/FOOTHOLD_RL_Data_Deliverable_Spec.pdf
CHROME=$(command -v google-chrome || command -v chromium || command -v chromium-browser)
"$CHROME" --headless=new --disable-gpu --no-sandbox --allow-file-access-from-files \
  --no-pdf-header-footer --print-to-pdf="$OUT" "file://$PWD/spec.html" 2>/dev/null
echo "만듦: $OUT"
command -v pdfinfo >/dev/null && pdfinfo "$OUT" | grep -E "Pages|File size" || true
