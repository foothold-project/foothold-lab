#!/usr/bin/env bash
# EX-33 S-B (SONNET-X25f): B(EX-28)와 같은 설정 + env 마다 에피소드 시작 때 확률 p_off 로 지도 끔(끝까지 유지). 처음부터 1501 회(model_1500), 3072 env, seed 42, 50 회마다 저장. 기동은 팀장 확인 뒤 lead 신호.
# usage: [P_OFF=0.5] run_sb.sh <main|smoke10|smoke2> <cuda:N> [smoke2 일 때: 이어 갈 smoke10 체크포인트 경로]
#   main    : 본 실행 1501 회 (run 이름 sb-main)
#   smoke10 : 짧은 Kit 새 시험 10 회 (run 이름 sb-main_smoke10)
#   smoke2  : smoke10 체크포인트에서 이어 2 회
set -u
KIND="$1"; DEV="$2"; RESUME="${3:-}"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
END_BY="$(date -d '+24 hours' --iso-8601=seconds)"
OUT="$ROOT/logs_gate/sb_${KIND}_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
EXTRA=()
[ -n "${P_OFF:-}" ] && EXTRA=(--p_map_off "$P_OFF")        # 끄는 비율 확정값(팀장 확인 뒤). 생략하면 agent cfg 의 기본 0.5
case "$KIND" in
  main) ;;
  smoke10) EXTRA+=(--smoke-updates 10) ;;
  smoke2) [ -n "$RESUME" ] || { echo "smoke2 는 smoke10 체크포인트 경로가 필요하다"; exit 2; }; EXTRA+=(--smoke-updates 2 --resume_from "$RESUME") ;;
  *) echo "main | smoke10 | smoke2"; exit 2 ;;
esac
ARGS=(--headless --device "$DEV" --num_envs 3072 --max_iterations 1501 --seed 42 --run_name sb-main --end-by "$END_BY" --max-wall-s 86400 ${EXTRA[@]+"${EXTRA[@]}")
printf '%s\n' "${ARGS[@]}" > "$OUT/launch_args.txt"
PYTHONPATH="$ROOT" "$ENV/python.exe" -m foothold_s2.prestart_check --args-file "$OUT/launch_args.txt" > "$OUT/prestart.json" || exit 5
"$ENV/python.exe" foothold_s2/scripts/train_sb.py "${ARGS[@]}" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
grep -q "TRAIN_START_STATUS done" "$OUT/run.log" || echo "DONE 줄 없음(Isaac 은 예외 뒤에도 0 을 낼 수 있다)" >> "$OUT/rc.txt"
