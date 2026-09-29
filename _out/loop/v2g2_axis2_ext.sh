#!/usr/bin/env bash
# 배포본 `v2g2` 의 «확장 축 2» 를 잰다. 판정에 안 쓰고 기록만 한다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「v2g2 확장 축도 돌려」 · [46][47] 「평가는 아니지만
#       관측(+ 영상)으로 남기고 기록하자」
# 요지: 확장 축을 `v2a` · `v2b` 까지만 쟀다. **배포본이 표에 없다**
#
# **이 파일을 도는 중에 고치지 않는다.** bash 가 조금씩 읽어 오프셋이 밀린다.
#
# ## 조건을 한 글자도 안 바꾼다
#
# `v2b-iter3000` 의 `probe_manifest.json` 에서 읽은 것이다. 하나라도 다르면
# 같은 표에 못 올린다.
#
# ```
#   num_envs 64 · seed 42 · pushes_enabled False
#   terrain  plane (무한 평면) · step_dt 0.02 · settle_speed 0.05
# ```
#
# ## 장치 인자를 «안» 준다
#
# 축 2 에 `--device cuda:1` 을 주면 `GRAVITY_VEC_W` 가 cuda:0 에 남아
# 16 초 만에 RuntimeError 가 난다 `확인됨`. 그리고 `CUDA_VISIBLE_DEVICES` 도
# 쓰지 않는다 (2026-09-28 · Kit 이 화면용 GPU 를 못 찾아 멈춘다).
#
# ## 무엇을 재나
#
# ```
#   slow010 ~ slow040   아주 느린 명령(0.10 ~ 0.40 m/s)을 따라가나
#   turn_rest           멈춘 채로 도는가        (지금은 D 만 갖고 있다)
#   turn_rev            반대로 도는가           (지금은 D 만 갖고 있다)
# ```
#
# **`push_robot` 은 안 넣는다.** 비교할 판이 하나도 없어서 혼자 재 봐야
# 읽을 수가 없다. 하네스에 있다는 것만 보고서에 적는다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
CK=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
OUT=sim/eval/results/20260928-v2g2-axis2-ext
export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE

say() { echo "[$(date +%H:%M:%S)] $*"; }
[ -f "$CK" ] || { say "** 체크포인트 없음 ** $CK"; exit 1; }

odir="$OUT/v2g2-feetair01-iter3000"

if [ -f "$odir/probe_manifest.json" ]; then
  say "건너뜀 (이미 있음)"
else
  mkdir -p "$odir"
  say "v2g2 @3000 · 확장 여섯 · env 64 · seed 42"
  "$PY" sim/eval/eval_command_response.py \
    --checkpoint "$CK" --label "v2g2-feetair01-iter3000" \
    --scenario slow010,slow020,slow030,slow040,turn_rest,turn_rev \
    --num_envs 64 --seed 42 --headless \
    --output_dir "$odir" > "$OUT/run.log" 2>&1
  rc=$?
  if [ -f "$odir/probe_manifest.json" ]; then
    say "  exit=$rc · 산출물 있음"
  else
    say "  exit=$rc · ** 산출물 없음 **"
    grep -oE '(RuntimeError|ValueError|SystemExit|Error):.*' "$OUT/run.log" 2>/dev/null | tail -2
    exit 1
  fi
fi

say "표를 만든다"
"$PY" - <<'PY' 2>&1 | sed 's/^/          /'
# -*- coding: utf-8 -*-
import json, io, os

EXT = ('slow010', 'slow020', 'slow030', 'slow040', 'turn_rest', 'turn_rev')
WANT = [
    ('NVIDIA', 'sim/eval/results/20260918-command-baseline/nvidia-zero'),
    ('foothold-v1', 'sim/eval/results/20260918-command-baseline/foothold-v1'),
    ('D', 'sim/eval/results/20260918-command-baseline/D'),
    ('v2a @3000', 'sim/eval/results/20260921-v2ab-axis2/v2a-iter3000'),
    ('v2b @3000', 'sim/eval/results/20260921-v2ab-axis2/v2b-iter3000'),
    ('v2g2 @3000',
     'sim/eval/results/20260928-v2g2-axis2-ext/v2g2-feetair01-iter3000'),
]


def load(d):
    f = os.path.join(d, 'probe_manifest.json')

    if not os.path.isfile(f):
        return None, None

    got = json.load(io.open(f, encoding='utf-8'))

    return got.get('summary') or {}, got


print('=== 잔류 속도 (m/s · 낮을수록 좋다) ===')
print('%-13s %9s %9s %9s %9s' % ('판', 'slow010', 'slow020', 'slow030', 'slow040'))

for lab, d in WANT:
    s, _ = load(d)
    if s is None:
        print('%-13s 없음' % lab); continue
    row = []
    for k in ('slow010', 'slow020', 'slow030', 'slow040'):
        v = (s.get(k) or {}).get('residual_speed_mps')
        row.append('%9.3f' % v if v is not None else '     없음')
    print('%-13s %s' % (lab, ' '.join(row)))

print()
print('=== 낙상 비율 ===')
print('%-13s %9s %9s %9s %9s %10s %9s'
      % ('판', 'slow010', 'slow020', 'slow030', 'slow040', 'turn_rest', 'turn_rev'))

for lab, d in WANT:
    s, _ = load(d)
    if s is None:
        continue
    row = []
    for k in EXT:
        v = (s.get(k) or {}).get('fell_ratio')
        row.append('%9.4f' % v if v is not None else '     없음')
    print('%-13s %s' % (lab, ' '.join(row)))

print()
s, meta = load(WANT[-1][1])
if meta:
    print('v2g2 조건 확인 · env %s · seed %s · pushes %s · terrain %s'
          % (meta.get('num_envs'), meta.get('seed'),
             meta.get('pushes_enabled'), meta.get('terrain')))
PY
say "끝"
