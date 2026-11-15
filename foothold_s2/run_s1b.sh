#!/usr/bin/env bash
# S1-b 본 학습 실행 (S1-a blind 의 model_5999.pt 에서 이어 3,000 회, 4096 env, iteration 6000 -> 9000).
# usage: run_s1b.sh <cuda:N> [추가 train_s1 인자...]
#   처음 시작: 가장 최근 S1-a blind 학습 폴더의 model_5999.pt 에서 단계 전이(--stage_transfer: 가중치 · optimizer · iteration · 명령 상한만 옮기고 지형 칸은 새로).
#   중단 뒤 이어: 인자에 --resume --load_run <S1-b 폴더> --checkpoint latest.pt --load_experiment foothold_s1b 를 준다(그러면 기본 단계 전이 인자를 붙이지 않는다).
# 판정은 종료 코드가 아니라 logs/s1b_blind_*/run.log 의 Traceback 과 train_start_status.json 으로 한다.
# 주의: 돌고 있는 S1-a 의 run_s1.sh 와 따로 둔 파일이다(bash 는 스크립트를 조금씩 읽어서, 돌고 있는 스크립트를 고치면 끝 줄이 깨진다).
set -u
DEV="$1"; shift 1
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s1b_blind_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
EXTRA=("$@")
RESUMING=0
for a in "$@"; do [ "$a" = "--resume" ] && RESUMING=1; done
if [ "$RESUMING" = "0" ]; then
    FROM_EXP="${S1B_FROM_EXPERIMENT:-foothold_s1a}"          # S1a-v1.1 에서 이어 받을 때: foothold_s1a_v11 (run_s1b_from_v11.sh)
    FROM_SUFFIX="${S1B_FROM_SUFFIX:-s1a_blind}"
    FROM="$(basename "$(ls -d logs/rsl_rl/${FROM_EXP}/*${FROM_SUFFIX} | tail -1)")"
    CKPT="${S1B_FROM_CHECKPOINT:-model_5999.pt}"
    echo "S1-b 시작: $FROM_EXP / $FROM / $CKPT" > "$OUT/start_from.txt"
    EXTRA=(--resume --load_run "$FROM" --checkpoint "$CKPT" --load_experiment "$FROM_EXP" --stage_transfer "$@")
fi
TOTAL="${S1B_TOTAL_ITERATIONS:-9000}"
"$ENV/python.exe" -m foothold_s2.train_s1 --task FootholdS2-Go2-S1b-blind-v0 --headless --device "$DEV" \
    --num_envs "${S1B_NUM_ENVS:-4096}" --max_iterations "$TOTAL" --run_name s1b_blind "${EXTRA[@]}" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
