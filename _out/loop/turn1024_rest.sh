#!/usr/bin/env bash
# `turn` 을 1024 env 로 **나머지 후보 넷** 에도 돌린다.
#
# 분류: 진단
# 작성: 오흥재 · 2026-09-28
# 근거: 두 후보만 1024 로 재면 «고른 둘만» 유리해질 수 있다.
# 요지: **선정 규칙을 결과 보기 전에 하나로 못 박았다.**
#       「64 env 에서 축 2 가 7/9 이상인 칸 전부」다. 여섯 칸이 걸린다.
#       그중 둘은 이미 쟀다 (`v2b-r`@2500 · `v2g2`@3000). 나머지 넷을 돈다.
#
# 왜 1024 인가
#   64 env 에서 `turn/fell_ratio` 의 Wilson 95 % 가 문턱 0.10 을 품는다.
#   실제로 `v2g2`@3000 이 64 에서 7/64 = 0.1094 (미달) 였는데
#   1024 에서 79/1024 = 0.0771 [0.0623, 0.0951] 로 «통과» 가 됐다.
#   즉 64 env 판정이 표본 탓이었다. 그러면 다른 판도 같은 탓을 받는다.
#
# 장치 인자를 «안» 준다. `--device` 는 sim 만 옮겨 죽고, 기존 축 2 서른여섯
# 칸이 장치 인자 없이(기본 cuda:0) 나왔다. `turn1024.sh` 머리말에 실측을 적었다.
#
# ## 미리 못 박는 것
#   표본   env 1024 · turn 만 · seed 42 · 칸마다 «한 번»
#   대상   위 선정 규칙으로 뽑힌 여섯 칸 전부. 결과를 보고 더 넣지 않는다
#   판정   Wilson 95 % 가 문턱을 품으면 «미확인». 다시 안 돌린다
#   기록   결과가 어느 쪽이든 그대로 싣는다
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
OUT=sim/eval/results/20260928-turn1024
TODO=_out/loop/turn1024-todo.txt
N="${TURN_ENVS:-1024}"
export OMNI_KIT_ACCEPT_EULA=YES

[ -f "$TODO" ] || { echo "** 목록이 없다: $TODO **"; exit 1; }

# 정책 이름 -> 학습 폴더. **추측하지 않고 적어 둔다.**
run_dir() {
  case "$1" in
    v2b-r)              echo "$L/2026-09-23_14-42-33_20260923_v2b-r_seed42_iter3000" ;;
    v2g2-feetair01)     echo "$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000" ;;
    v2g3-feetair01-s43) echo "$L/2026-09-25_23-32-28_20260925_v2g3-feetair01-s43_seed43_iter3000" ;;
    v2g4-feetair01-s44) echo "$L/2026-09-26_15-22-03_20260926_v2g4-feetair01-s44_seed44_iter3000" ;;
    *)                  ls -d "$L"/*"$1"* 2>/dev/null | head -1 ;;
  esac
}

mkdir -p "$OUT"
# 마지막 줄에 개행이 없으면 `read` 가 버린다. 오늘 한 번 겪었다.
while IFS='|' read -r pol ck || [ -n "${pol:-}" ]; do
  [ -z "${pol:-}" ] && continue
  tag="$pol-iter$ck"
  odir="$OUT/$tag"
  if [ -f "$odir/probe_manifest.json" ]; then
    echo "[$(date +%H:%M:%S)] 건너뜀 (이미 있음) $tag"; continue
  fi
  d=$(run_dir "$pol")
  ckpt="$d/model_$ck.pt"
  if [ ! -f "$ckpt" ]; then
    echo "[$(date +%H:%M:%S)] ** 체크포인트 없음 ** $ckpt"; continue
  fi
  echo "[$(date +%H:%M:%S)] $tag · turn · env $N 시작"
  "$PY" sim/eval/eval_command_response.py \
    --checkpoint "$ckpt" \
    --label "$tag" \
    --scenario turn \
    --num_envs "$N" \
    --seed 42 \
    --headless \
    --output_dir "$odir" > "$OUT/$tag.log" 2>&1
  RC=$?
  if [ -f "$odir/probe_manifest.json" ]; then H="산출물 있음"; else H="** 산출물 없음 **"; fi
  echo "[$(date +%H:%M:%S)] $tag exit=$RC · $H"
done < "$TODO"

echo "[$(date +%H:%M:%S)] 표를 낸다"
"$PY" _out/loop/turn1024_table.py
