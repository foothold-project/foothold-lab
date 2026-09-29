#!/usr/bin/env bash
# 계보의 «전환점» 을 보여 주는 컷을 굽는다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「영상을 뽑자고 하는 것은 우리가 영상을 통해서 보여주고자 하는
#       것이 명확해야한다. 단순히 실험중 하나를 랜더하는 것이 절대 아니다」
# 요지: 컷마다 **무엇을 보여 주는지** 를 먼저 적고 그것에 맞는 짝을 찍는다.
#
# **이 파일을 도는 중에 고치지 않는다.** bash 가 조금씩 읽어 오프셋이 밀린다.
#
# ## 컷과 그 컷이 말하는 것
#
# ① 명령을 열면 gap 을 잃는다        v1 의 gap  대  D 의 gap        (1.0 m/s)
#    v1 100 % · D 72 % · 세 속도 전부 진짜 하락.
#    화면에서 「돌아서서 딴 데로 간다」가 보인다.
#
# ② 회전을 얻었다                    v1 의 turn 대  v2 의 turn
#    v1 은 `ang_vel_z = (0,0)` 이라 `clip(x,0,0)` 이 언제나 0 이다.
#    **1500 회 동안 0 이 아닌 회전 명령을 한 번도 안 받았다.** 아예 안 돈다.
#
# ③ 노출을 지형으로 푼다             forward_gap 타일  대  omni_gap 타일
#    로봇 한 마리 · 위에서. 모양만 보면 된다.
#    forward_gap 은 +x 에만 있고 omni_gap 은 스폰을 둘러싼 고리다.
#
# 짝을 나란히 놓을 것이므로 **같은 조건** 으로 찍는다. 난이도 · 속도 · 시간 ·
# 카메라가 같아야 차이가 판 때문이라고 말할 수 있다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
OUT=sim/eval/results/20260928-lineage-clips
DEV="${RENDER_DEV:-cuda:0}"
export OMNI_KIT_ACCEPT_EULA=YES

V1=models/foothold-v1.pt
D=$L/2026-09-18_11-19-19_20260918_gapwidecmd_seed42_iter1500/model_1500.pt
V2=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt

say() { echo "[$(date +%H:%M:%S)] $*"; }
for f in "$V1" "$D" "$V2"; do
  [ -f "$f" ] || { say "** 체크포인트 없음 ** $f"; exit 1; }
done
done_ok() { ls "$1"/*.mp4 >/dev/null 2>&1; }

shoot() {   # 이름 · 체크포인트 · 지형 · 집합 · 속도 · 시간 · 제목
  local name="$1" ck="$2" terr="$3" set="$4" vx="$5" dur="$6" title="$7"
  local o="$OUT/$name"
  if done_ok "$o"; then say "건너뜀 (이미 있음) $name"; return; fi
  mkdir -p "$o"
  say "$name · $terr · $vx m/s"
  "$PY" sim/eval/record_terrain_demo.py \
    --checkpoint "$ck" --output_dir "$o" \
    --terrain "$terr" --terrain_set "$set" --difficulty 0.5 \
    --cut A --view track_high --title "$title" \
    --num_envs 1 --columns 1 --rows 1 --spacing 3.0 \
    --width 1920 --height 1080 \
    --eval_duration "$dur" --command_vx "$vx" \
    --trace_csv "$o/trace.csv" \
    --gate_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 \
    --preset slow --crf 20 --device "$DEV" > "$o/render.log" 2>&1
  local rc=$?
  if done_ok "$o"; then
    say "  exit=$rc · 산출물 있음"
    local raw; raw=$(ls "$o"/*.mp4 2>/dev/null | grep -v '\.hud\.mp4$' | head -1)
    "$PY" sim/eval/overlay/render.py --video "$raw" --trace "$o/trace.csv" \
      --out "$o/$name.hud.mp4" > "$o/hud.log" 2>&1
  else
    say "  exit=$rc · ** 산출물 없음 ** · $(grep -oE '(RuntimeError|ValueError|SystemExit):.*' "$o/render.log" 2>/dev/null | tail -1 | cut -c1-84)"
  fi
}

# ---------------------------------------------------------------- ① gap
# 같은 지형 · 같은 속도 · 같은 시간. 다른 것은 «정책» 뿐이다.
shoot "gap-v1"  "$V1" gap unseen10 1.0 6.0 "v1 · gap · 1.0 m/s"
shoot "gap-D"   "$D"  gap unseen10 1.0 6.0 "D · gap · 1.0 m/s"
shoot "gap-v2"  "$V2" gap unseen10 1.0 6.0 "v2 · gap · 1.0 m/s"

# ---------------------------------------------------------------- ③ 지형 모양
# 로봇이 아니라 «지형» 을 보여 주는 컷이다. 위에서 한 마리.
# `forward_gap` 은 학습 지형이라 `rough6` 집합에 없다. 그래서 `gap`(평가 지형)
# 으로 대신 보여 준다. 둘 다 «+x 에만 있는 틈» 이라는 점이 같다.
for row in "terrain-gap|gap|unseen10|v2 · gap tile" \
           "terrain-ring|floating_ring|unseen10|v2 · ring tile"; do
  n="${row%%|*}"; r="${row#*|}"; t="${r%%|*}"; r="${r#*|}"; s="${r%%|*}"; ti="${r##*|}"
  o="$OUT/$n"
  if done_ok "$o"; then say "건너뜀 (이미 있음) $n"; continue; fi
  mkdir -p "$o"
  say "$n · 지형 모양 · 위에서"
  "$PY" sim/eval/record_terrain_demo.py \
    --checkpoint "$V2" --output_dir "$o" \
    --terrain "$t" --terrain_set "$s" --difficulty 0.5 \
    --terrain_rows 1 --terrain_cols 1 \
    --cut A --view topdown --title "$ti" \
    --num_envs 1 --columns 1 --rows 1 --spacing 3.0 \
    --width 1920 --height 1080 \
    --eval_duration 4.0 --command_vx 1.0 --gate off \
    --preset slow --crf 20 --device "$DEV" > "$o/render.log" 2>&1
  done_ok "$o" && say "  산출물 있음" || say "  ** 없음 ** $(grep -oE '(RuntimeError|ValueError|SystemExit):.*' "$o/render.log" | tail -1 | cut -c1-84)"
done

say "프레임 전수 검사"
"$PY" _out/loop/video_scan.py --allow-black --json "$OUT/scan.json" "$OUT/*/*.mp4" \
  2>&1 | sed 's/^/          /'

say "미리보기 png"
"$PY" - <<'PY' 2>&1 | sed 's/^/          /'
import os
try:
    import imageio.v2 as iio
    import numpy as np
except ImportError:
    print("imageio 가 없다"); raise SystemExit(0)
B = "sim/eval/results/20260928-lineage-clips"
P = os.path.join(B, "previews")
os.makedirs(P, exist_ok=True)
n = 0
for name in sorted(os.listdir(B)):
    d = os.path.join(B, name)
    if not os.path.isdir(d) or name == "previews":
        continue
    hud = [f for f in os.listdir(d) if f.endswith(".hud.mp4")]
    raw = [f for f in os.listdir(d)
           if f.endswith(".mp4") and not f.endswith(".hud.mp4")]
    pick = (hud or raw)
    if not pick:
        continue
    out = os.path.join(P, name + ".png")
    if os.path.isfile(out):
        n += 1
        continue
    try:
        r = iio.get_reader(os.path.join(d, pick[0]))
        c = r.count_frames()
        im = np.asarray(r.get_data(max(0, c // 2)))
        r.close()
        iio.imwrite(out, im)
        n += 1
    except Exception as exc:                                       # noqa: BLE001
        print("  ** %s · %s **" % (name, exc))
print("미리보기 %d 장" % n)
PY
say "끝"
