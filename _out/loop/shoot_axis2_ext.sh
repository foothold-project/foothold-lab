#!/usr/bin/env bash
# 확장 축 2 여섯 시나리오를 «영상으로» 찍는다.
#
# 분류: 운영 · 작성: 오흥재 · 2026-09-29
# 근거: 팀장 지시 「저속 넷이랑 turn_rest, turn_rev 영상 찍어서 보고서에 올려」
#
# ## 왜 있나
#
# 보고서 11 절 「나」 행에 **「평가 지표로는 안 쓰고 자료와 영상으로 남긴다」**
# 고 적어 놓고 숫자만 올렸다. 영상이 0 편이었다 `확인됨`
# (`20260928-v2g2-axis2-ext/` 여섯 폴더에 mp4 0 편).
#
# ## 무엇을 찍나
#
#   slow010 ~ slow040   전진 0.10 ~ 0.40 m/s 고정 · 20 초씩
#   turn_rest           회전 계단 · 칸 사이 1.5 초 쉼 · 25 초
#   turn_rev            회전 계단 · 순서 뒤집음 · 18 초
#
# 판 셋은 축 2 컷과 **같은 체크포인트** 를 쓴다 (sha 를 로그에 남긴다).
#
# ## env 51 을 쓰는 까닭
#
# 저속 넷 · 판 셋 · 열두 칸에서 **추종비가 중앙값에 가장 가까운 칸** 이다
# (대표성 0.0672 · 64 칸 중 1 위) `확인됨`. 그리고 세 판의 특징이 다
# 드러난다 · NVIDIA 0.01(안 움직임) · v1 낙상 · v2g2 1.74(넘어섬).
# **유리한 칸을 고르면 컷이 표를 설명하지 못한다.**
#
# 축 2 프로브 컷이 쓴 env 8 은 대표성 60 / 64 라 안 쓴다.
#
# ## 한 번에 도는 까닭
#
# `--scenario` 가 쉼표 목록을 받는다. Isaac 을 판마다 한 번만 띄운다.
set -u
cd "$(dirname "$0")/../.." || exit 1

PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
OUT=sim/eval/results/20260929-axis2-ext-clips
SCN=slow010,slow020,slow030,slow040,turn_rest,turn_rev
VENV=51

export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE

# **CUDA_VISIBLE_DEVICES 를 건드리지 않는다.** 랜더는 화면용 GPU 를 쓰고,
# 가리면 창 생성에서 조용히 멈춘다 (2026-09-28 에 당했다).

NV=C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt
V1=models/foothold-v1.pt
V2=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt

say() { echo "[$(date +%H:%M:%S)] $*"; }

mkdir -p "$OUT"
say "확장 축 여섯 · 판 셋 · env 64 · 시드 42 · 영상 env $VENV"
say "시나리오 $SCN"

fail=0
for row in "nvidia|$NV" "v1|$V1" "v2|$V2"; do
  lab="${row%%|*}"
  ck="${row#*|}"

  if [ ! -f "$ck" ]; then
    say "** 체크포인트 없음 ** $lab $ck"
    fail=1
    continue
  fi

  odir="$OUT/$lab"
  if [ -f "$odir/probe_manifest.json" ]; then
    say "$lab 건너뜀 (이미 있음)"
    continue
  fi

  mkdir -p "$odir"
  say "$lab 시작"
  "$PY" sim/eval/eval_command_response.py \
    --checkpoint "$ck" --label "$lab" \
    --scenario "$SCN" \
    --num_envs 64 --seed 42 --headless \
    --video --video_env "$VENV" \
    --output_dir "$odir" > "$odir/run.log" 2>&1
  rc=$?

  # **mp4 는 시나리오 폴더 안으로 들어간다** (`<폴더>/<시나리오>/<판>_<시나리오>.mp4`
  # · `eval_command_response.py` 837~840 행). 2026-09-29 에 `"$odir"/*.mp4` 로
  # 세서 여섯 편을 다 쓰고도 「0 편」 으로 찍혔다. find 로 센다.
  n=$(find "$odir" -name '*.mp4' 2>/dev/null | wc -l)
  if [ -f "$odir/probe_manifest.json" ] && [ "$n" -ge 6 ]; then
    say "  $lab exit=$rc · mp4 $n 편"
    while IFS= read -r f; do
      say "     $(basename "$f")  $(du -h "$f" | cut -f1)"
    done < <(find "$odir" -name '*.mp4' | sort)
  else
    say "  $lab exit=$rc · ** mp4 $n 편 (여섯이어야 한다) **"
    grep -oE '(RuntimeError|ValueError|SystemExit|AssertionError|Error):.*' \
      "$odir/run.log" 2>/dev/null | tail -3
    fail=1
  fi
done

say "끝 · 총 mp4 $(find "$OUT" -name '*.mp4' 2>/dev/null | wc -l) 편 (열여덟이어야 한다)"
exit $fail
