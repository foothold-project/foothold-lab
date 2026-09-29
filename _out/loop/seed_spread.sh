#!/usr/bin/env bash
# 지형 판 하나의 운이 성공률에 얼마나 실리나. 「위 한계」만 잰다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-29
# 근거: 팀장 물음 「#23 지형별 성공률이 지형 판 하나의 값인지 확인」
# 요지: 하네스는 지형과 출발 흔들기를 따로 못 뗀다. 그래서 둘을 같이 바꾼
#       퍼짐을 재고 그것을 지형 운의 위 한계로 쓴다
#
# **이 파일을 도는 중에 고치지 않는다.** bash 가 조금씩 읽어 오프셋이 밀린다.
#
# ## 1 차에서 내 전제가 틀렸다 (그대로 적어 둔다)
#
# 처음에는 `--terrain_seed` 를 새로 내서 지형만 가르려 했다. 돌려 보니
# 열 판 1,000 에피소드가 **바이트로 전부 같았다.** 까닭을 소스에서 찾았다.
#
#   terrain_generator.py:141-148  cfg.seed 는 self.np_rng 하나만 만든다
#                                 (「전역 상태를 안 건드리려고」라고 적혀 있다)
#   hf_terrains.py                지형을 그리는 함수는 전역 np.random 을 쓴다
#                                 (12 곳 · cfg.seed 는 0 곳)
#   mesh_terrains.py              같다 (4 곳 · cfg.seed 0 곳)
#   np_rng 가 쓰이는 곳            색 · 하위지형 고르기 · 난이도. 모양은 아니다
#
# 그러니 `TerrainGeneratorCfg.seed` 는 **지형 모양을 안 정한다.** 모양을
# 정하는 것은 전역 난수이고 그것은 `env_cfg.seed`, 즉 `--seed` 다.
# 인자는 도로 뺐고 까닭은 하네스 주석에 박았다.
#
# ## 그래서 무엇을 재나
#
# `--seed` 를 42 · 1 · 2 · 3 · 4 로 바꾼다. 이러면 **지형 판도 출발
# 흔들기도 같이** 바뀐다. 둘을 못 떼므로 나오는 퍼짐은
#
#   「지형 판 하나의 운」 + 「출발 흔들기의 운」
#
# 이다. 지형 운 하나만 말할 수 없고 **위 한계** 로만 말할 수 있다.
# 퍼짐이 0 이면 둘 다 0 이라는 뜻이라 그때는 답이 깨끗하다.
#
# 확인한 것 `확인됨`
#
#   generalization_env_cfg.py:48   num_rows=1 · num_cols=10
#   rough6_env_cfg.py:66           num_rows=1 · num_cols=6
#   run_manifest.json              terrain_num_rows 1 (두 하네스 다)
#   eval_generalization.py         출발 흔들기는 x/y +-0.10 m · yaw +-5 도
#
# 지형 하나에 타일 하나다. 그래서 한 실행의 100 판은 같은 지형 한 장 위를
# +-10 cm 만 다르게 출발해 걷는다.
#
# ## 답을 아는 판부터
#
# 첫 칸(`s42`)은 갤러리가 쓴 실행과 한 글자도 다르지 않다. 지형별 성공률이
# 똑같이 나와야 한다. 1 차에서 실제로 10/10 · 6/6 이 같았다 `확인됨`.
#
# ## 조건은 갤러리 칸과 한 글자도 안 바꾼다
#
#   episodes 100 · envs_per_terrain 10 · difficulty 0.5 · command_vx 1.0
#   eval_duration 6.0 · min_progress 3.0 · drift 0.75
#
# **장치도 cuda:1 로 고정한다.** 9/28 장치 대조에서 장치가 값을 움직인 적이
# 있다. 두 GPU 로 갈라 돌리면 그것이 두 번째 변수가 된다.
#
# ## note 에 길잡이표를 쓰지 않는다
#
# 1 차에서 한 칸이 죽었다 `확인됨`.
#
#   UnicodeEncodeError: cp949 codec can not encode character 0xab
#
# 하네스가 note 를 콘솔에 찍는데 Windows 콘솔이 cp949 다. 그 부호가 없다.
# 로그에도 안 남고 CSV 도 안 나온다.
#
# 칸 수 = 집합 둘 x 시드 다섯 = 10 판
set -u
cd "$(dirname "$0")/../.." || exit 1

PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
CK=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
OUT=sim/eval/results/20260929-seed-spread
DEV=cuda:1
export OMNI_KIT_ACCEPT_EULA=YES

say() { echo "[$(date +%H:%M:%S)] $*"; }

if [ ! -f "$CK" ]; then say "** 체크포인트가 없다: $CK **"; exit 1; fi
if [ ! -x "$PY" ]; then say "** python 이 없다: $PY **"; exit 1; fi

mkdir -p "$OUT"
say "시작 · 10 판 · 장치 $DEV"

n_ok=0
n_bad=0

for SET in unseen10 rough6; do
  for SD in 42 1 2 3 4; do
    D="$OUT/$SET/s$SD"
    if [ -f "$D/generalization_raw.csv" ]; then
      say "건너뜀 (이미 있다) · $SET s$SD"
      n_ok=$((n_ok + 1))
      continue
    fi
    mkdir -p "$D"

    NOTE="시드 퍼짐 · seed $SD · 장치 $DEV · 지형과 출발이 같이 바뀐다"
    if [ "$SD" = "42" ]; then
      NOTE="$NOTE · 갤러리 칸과 대조용 기준 판"
    fi

    say "돈다 · $SET s$SD"
    "$PY" sim/eval/eval_generalization.py \
      --checkpoint "$CK" \
      --terrain_set "$SET" \
      --terrains all \
      --difficulty 0.5 \
      --episodes 100 \
      --envs_per_terrain 10 \
      --command_vx 1.0 \
      --eval_duration 6.0 \
      --min_progress_m 3.0 \
      --max_lateral_drift 0.75 \
      --seed "$SD" \
      --headless \
      --device "$DEV" \
      --note "$NOTE" \
      --output_dir "$D" > "$D/run.log" 2>&1

    rc=$?
    if [ $rc -ne 0 ] || [ ! -f "$D/generalization_raw.csv" ]; then
      say "** 실패 · $SET s$SD · 종료 $rc · $D/run.log **"
      tail -12 "$D/run.log" 2>/dev/null
      n_bad=$((n_bad + 1))
    else
      say "끝 · $SET s$SD · $(wc -l < "$D/generalization_raw.csv") 줄"
      n_ok=$((n_ok + 1))
    fi
  done
done

say "다 돌았다 · 된 것 $n_ok · 실패 $n_bad"
exit $([ $n_bad -eq 0 ] && echo 0 || echo 1)
