#!/usr/bin/env bash
# EX-42 B 빔 갈아 끼운 후보 메시 (easy10 + 짧은 빔) 의 M2 · M3 Kit 탐침 + M0~M3 영수증 한 번에.
# 사용: bash foothold_s2/scripts/ex42_m2m3_beam_run.sh [--dry-run] [cuda:0|cuda:1]
# 장치를 안 주면 여유가 2 GiB 이상인 쪽 (둘 다면 더 큰 쪽) 을 고른다. 둘 다 부족하면 rc 3 으로 서고 아무것도 안 띄운다.
# plan · prep.yaml · 정본 contract 는 읽기만 한다. 출력은 새 시각 폴더에만 쓴다.
set -u
DRY=0; DEV=""
for a in "$@"; do case "$a" in --dry-run) DRY=1;; cuda:0|cuda:1) DEV="$a";; *) echo "알 수 없는 인자 $a" >&2; exit 2;; esac; done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MESH=/home/jay/data/foothold/sonnet_beam_mesh_1119/b2m_rpy_lv
OUTROOT=/home/jay/data/foothold/sonnet_beam_mesh_1119/m2m3
NPZ_SHA=745d7886b3ee6b7ed3a7c71649b1cd9bcc00ef0b97676a2b1d68f2d5ef77baea
MANIFEST_SHA=261523d0fba60e59f395208dd88f8c725b289556ee087a565005c28e984b53ec
MIN_FREE_MIB=${MIN_FREE_MIB:-2048}
PY=${PY:-/home/jay/miniforge3/envs/isaac311/bin/python}

set -a; . ~/mai/foothold-linux.env >/dev/null 2>&1; set +a
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$REPO"
cd "$REPO" || exit 2

# 1) 입력 sha 가 기대와 같은지 (다르면 서고 아무것도 안 띄움)
got_npz=$(sha256sum "$MESH/terrain_mesh.npz" | cut -d' ' -f1)
got_man=$(sha256sum "$MESH/mesh_manifest.json" | cut -d' ' -f1)
[ "$got_npz" = "$NPZ_SHA" ] || { echo "npz sha 불일치: $got_npz" >&2; exit 4; }
[ "$got_man" = "$MANIFEST_SHA" ] || { echo "mesh_manifest sha 불일치: $got_man" >&2; exit 4; }

# 2) 장치 고르기 (장치 전체 기준 여유)
free0=$(nvidia-smi -i 0 --query-gpu=memory.free --format=csv,noheader,nounits | tr -d ' ')
free1=$(nvidia-smi -i 1 --query-gpu=memory.free --format=csv,noheader,nounits | tr -d ' ')
echo "$(date +%H:%M) GPU 여유 MiB: cuda:0=$free0 cuda:1=$free1 (필요 $MIN_FREE_MIB)"
if [ -z "$DEV" ]; then
  if [ "$free0" -ge "$free1" ]; then DEV=cuda:0; best=$free0; else DEV=cuda:1; best=$free1; fi
else
  [ "$DEV" = cuda:0 ] && best=$free0 || best=$free1
fi
if [ "$best" -lt "$MIN_FREE_MIB" ] && [ "$DRY" != 1 ]; then
  echo "여유 부족 ($DEV $best MiB < $MIN_FREE_MIB). 아무것도 띄우지 않음." >&2; exit 3
fi

STAMP=$(date +%Y%m%d_%H%M%S)
OUT="$OUTROOT/$STAMP"
PROBE="$OUT/kit-probe.json"
CMD1=("$PY" -m foothold_s2.scripts.ex42_m0_m3_probe --mesh-dir "$MESH" --out "$PROBE" --device "$DEV" --expected-npz-sha256 "$NPZ_SHA")
CMD2=("$PY" -m foothold_s2.tools.ex42_m0_m3 --mesh-dir "$MESH" --table /home/jay/data/foothold/sonnet_beam_mesh_1119/plan_draft/ex42-prep.yaml --out "$OUT/m0-m3.json" --probe "$PROBE")
echo "장치 $DEV · 출력 $OUT"
echo "1) ${CMD1[*]}"; echo "2) ${CMD2[*]}"
[ "$DRY" = 1 ] && { echo "dry-run: 띄우지 않음"; exit 0; }

mkdir -p "$OUT"
# plan 은 읽기 전용 사본이 이미 같은 폴더 계열에 있음. 탐침 한 번 (자체 600 초 watchdog).
echo "$(date +%H:%M:%S) 탐침 시작"
"${CMD1[@]}" > "$OUT/probe.log" 2>&1; rc1=$?
echo "$(date +%H:%M:%S) 탐침 rc=$rc1"
# Isaac 은 예외 뒤에도 rc 0 일 수 있으므로 산출물과 Traceback 으로도 본다
if [ "$rc1" -ne 0 ] || [ ! -s "$PROBE" ] || grep -q "Traceback" "$OUT/probe.log"; then
  echo "탐침 실패 (rc=$rc1, 산출물 $( [ -s "$PROBE" ] && echo 있음 || echo 없음 )). 로그: $OUT/probe.log" >&2; exit 5
fi
"${CMD2[@]}" > "$OUT/m0-m3.log" 2>&1; rc2=$?
echo "$(date +%H:%M:%S) 영수증 rc=$rc2 · $OUT/m0-m3.json sha256=$(sha256sum "$OUT/m0-m3.json" 2>/dev/null | cut -d' ' -f1)"
tail -5 "$OUT/m0-m3.log"
exit $rc2
