#!/usr/bin/env bash
# SONNET-X25d: fwd_then_left 만 추가로 잰다(기존 16 env probe 와 같은 조건: B task, eval_pred, 고정 지형, 16 env). 체크포인트를 읽기만 한다. 학습 아님. GPU 를 쓰므로 lead 가 시킨 뒤에만 돌린다.
# usage: run_fwd_then_left.sh <cuda:N> [출력 상위 폴더=<repo>/logs/fwd_then_left]     네 개를 차례로 돈다(한 장치).
set -u
DEV="$1"
ROOT=C:/mai/wt/foothold-lab/impl-turncases
TOP="$ROOT/logs/six_cases"
STG=C:/mai/wt/foothold-lab/impl-stagger/logs/rsl_rl/foothold_s2_ex31r_stagger
declare -A CK=(
  [b1500]=C:/mai/wt/foothold-lab/lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main/model_1500.pt
  [b50_m1510]=$STG/2026-10-25_19-15-52_ex31r-b50/model_1510.pt
  [b50_m1550]=$STG/2026-10-25_19-15-52_ex31r-b50/model_1550.pt
  [a50_m1550]=$STG/2026-10-25_18-55-24_ex31r-a50/model_1550.pt
)
for TAG in b1500 b50_m1510 b50_m1550 a50_m1550; do
  OUT="$TOP/$TAG"
  mkdir -p "$OUT"
  git -C "$ROOT" rev-parse HEAD > "$OUT/git_head.txt"
  sha256sum "${CK[$TAG]}" > "$OUT/checkpoint_sha256.txt"
  MODULE=foothold_s2.eval.turn_probe DEVICE="$DEV" bash "$ROOT/foothold_s2/eval/run_kit.sh" "$OUT" \
    --task FootholdS2-Go2-S2-23f-B-v0 --checkpoint "${CK[$TAG]}" --envs 16 --map-mode eval_pred --fixed-terrain --cases all < /dev/null
  echo "rc=$?" > "$OUT/rc.txt"
  grep -q "TURNPROBE_DONE" "$OUT/run.log" || echo "DONE 줄 없음(Isaac 은 예외 뒤에도 0 을 낼 수 있다)" >> "$OUT/rc.txt"
done
