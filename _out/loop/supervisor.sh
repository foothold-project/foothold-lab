#!/usr/bin/env bash
# 남은 학습을 걸고, 다 끝나면 평가·판정·상호작용까지 «혼자» 마친다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-27
# 근거: 팀장 지시 「사슬을 예약 작업으로 먼저 옮겨」
#       2026-09-27 실측 · 학습 python 은 고아 프로세스라 세션이 죽어도 살지만,
#       queue_s42_2x2.sh 와 gather_all.sh 는 Claude Code 세션에 «묶여» 있어서
#       세션을 올리는 순간 s42D 가 영영 안 걸린다.
#
# 이 파일이 앞의 둘과 다른 점
#   **한 번 돌고 끝난다.** 기다리지 않는다. 예약 작업이 10 분마다 다시 부른다.
#   그래서 중간에 죽어도 다음 회차가 «이어서» 한다. 세션과 무관하다.
#
#   상태를 «변수» 가 아니라 «디스크» 에서 읽는다. 어느 회차에 들어와도 같은 답이
#   나와야 하기 때문이다. 걸렸나 = 로그 파일이 있나. 끝났나 = model_3000.pt 가
#   있거나 프로세스가 없고 로그가 끝나 있나.
#
# 돌리는 법
#   bash _out/loop/supervisor.sh          (예약 작업이 이렇게 부른다)

set -u
set -o pipefail

LAB="C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
ISAAC="C:/isaac/IsaacLab"
RUNS="$ISAAC/logs/rsl_rl/unitree_go2_gap_nvidia"
LOGS="$ISAAC/logs/gap_run_logs"
OUT="$LAB/_out/loop"
LOG="$OUT/supervisor.log"
LOCK="$OUT/supervisor.lock"
DONE="$OUT/supervisor.done"

cd "$LAB" || exit 1

say() { echo "[감독 $(date '+%m/%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# ---------------------------------------------------------------- 자물쇠
# 앞 회차가 아직 돌고 있으면 «겹쳐 돌지 않는다». 30 분이 지난 자물쇠는 버린다.
if [ -f "$LOCK" ]; then
  AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  if [ "$AGE" -lt 1800 ]; then exit 0; fi
  say "자물쇠가 ${AGE}초 묵었다. 버리고 진행한다"
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

[ -f "$DONE" ] && exit 0

# ---------------------------------------------------------------- 조회
# @() 로 싼다. 정확히 «한 개» 일 때 .Count 가 비는 것을 여러 번 당했다.
trainers() {
  local out
  out=$(powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'run_name' }).Count" \
    2>/dev/null | tr -d '\r ')
  case "$out" in ''|*[!0-9]*) echo -1 ;; *) echo "$out" ;; esac
}

free_gpu() {
  local used
  used=$(powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'run_name' }) | ForEach-Object { if (\$_.CommandLine -match '--device\s+(\S+)') { \$Matches[1] } }" \
    2>/dev/null | tr -d '\r ')
  for g in cuda:0 cuda:1; do
    echo "$used" | grep -q "^${g}$" || { echo "$g"; return; }
  done
  echo ""
}

launched() { ls "$LOGS"/*"$1"*.log >/dev/null 2>&1; }

finished() {   # 완주했거나 죽었거나 · 「지금 돌고 있지 않다」가 아니다
  ls "$RUNS"/*"$1"*/model_3000.pt >/dev/null 2>&1 && return 0
  local l
  l=$(ls -t "$LOGS"/*"$1"*.log 2>/dev/null | head -1)
  [ -z "$l" ] && return 1
  grep -q "exit=" "$l" 2>/dev/null && return 0
  # 세게 죽으면 로그에 exit= 이 «안 남는다». 그러면 이 판은 영원히 「안 끝났다」로
  # 남아 마무리가 시작되지 않는다. 도는 학습이 «하나도 없으면» 걸린 판은 정의상
  # 끝난 것이다. 그 경우만 여기서 끝난 것으로 본다.
  [ "${N:-1}" = "0" ]
}

JOBS=(
  "20260927_s42A-scalar-f001-noopt|scalar|0.01|nvidia_pretrained_noopt"
  "20260927_s42B-scalar-f01-noopt|scalar|0.1|nvidia_pretrained_noopt"
  "20260927_s42C-log-f001|log|0.01|nvidia_pretrained_logstd"
  # s42D (log · 0.1) 를 «뺐다» · 2026-09-27 22:0x
  #
  # 왜 뺐나
  #   팀장 지적: 「log 를 기본으로 삼을지가 그렇게 중요한 게 아니라면 왜 지금까지
  #   이딴 짓을 하고 있는거야?」 옳다. std 매개화는 우리 주제(미경험 험지 지형
  #   정책 적응)의 물음이 아니다. 판이 죽어서 커진 «고장» 이고, 고장을 실험 축으로
  #   올린 뒤로는 매 걸음이 앞 걸음으로 정당화됐다. 자기 참조다.
  #
  #   A·B (scalar 0.01 대 0.1) 는 «남긴다». 그건 보상 비교이고 optimizer 처리가
  #   맞춰진 우리 프로젝트의 실험이다. C·D 가 매개화 팔이다.
  #
  # 되살리려면 아래 한 줄의 주석을 풀면 된다
  # "20260927_s42D-log-f01|log|0.1|nvidia_pretrained_logstd"
)

N=$(trainers)
if [ "$N" = "-1" ]; then say "프로세스를 못 읽었다. 이번 회차는 넘긴다"; exit 0; fi

# ---------------------------------------------------------------- 1 · 남은 학습
PENDING=0
for spec in "${JOBS[@]}"; do
  IFS='|' read -r name std feet ckdir <<< "$spec"
  if launched "$name"; then
    finished "$name" || PENDING=$((PENDING+1))
    continue
  fi
  PENDING=$((PENDING+1))
  # 아직 안 걸린 판이다. GPU 가 비었으면 건다
  if [ "$N" -lt 2 ]; then
    G=$(free_gpu)
    if [ -n "$G" ]; then
      say "건다 · $name · $G · std=$std · feet=$feet · 출발=$ckdir"
      powershell -NoProfile -Command \
        "Set-Location C:\isaac\IsaacLab; .\run_gap_train.ps1 -Task Isaac-Velocity-V2b-Unitree-Go2-v0 \
         -Iterations 3001 -NumEnvs 4096 -Seed 42 -Device $G -RunName $name \
         -Extra @('agent.device=$G','agent.policy.noise_std_type=$std','env.rewards.feet_air_time.weight=$feet','--load_run','$ckdir') -Detached" \
        2>&1 | grep -E "log file" | sed 's/^/          /' | tee -a "$LOG"
      exit 0   # 한 회차에 한 판만 건다. 다음 회차가 이어서 한다
    fi
  fi
  break        # 순서대로 건다. 앞이 안 걸렸으면 뒤도 안 건다
done

if [ "$PENDING" -gt 0 ]; then
  say "아직 $PENDING 판 남았다 (도는 중 $N). 기다린다"
  exit 0
fi
if [ "$N" -ne 0 ]; then
  say "네 판 다 걸렸고 $N 판이 아직 돈다. 기다린다"
  exit 0
fi

# ---------------------------------------------------------------- 2 · 마무리
say "**네 판이 다 끝났다.** 평가·판정·상호작용으로 넘어간다"
for spec in "${JOBS[@]}"; do
  IFS='|' read -r name _ _ _ <<< "$spec"
  if ls "$RUNS"/*"$name"*/model_3000.pt >/dev/null 2>&1; then
    say "  $name · 완주"
  else
    l=$(ls -t "$LOGS"/*"$name"*.log 2>/dev/null | head -1)
    say "  $name · **완주 못 함** · $(grep -o 'Learning iteration *[0-9]*' "$l" 2>/dev/null | tail -1) · $(grep -o 'RuntimeError:.*' "$l" 2>/dev/null | tail -1 | cut -c1-58)"
  fi
done

say "상태 파일에 반영한다"
python _out/loop/register.py 2>&1 | tail -5 | sed 's/^/          /' | tee -a "$LOG"

say "평가를 건다"
python _out/loop/eval_runner.py 2>&1 | tail -3 | sed 's/^/          /' | tee -a "$LOG"

say "평가가 끝나기를 기다린다 (이 회차 안에서 · 최대 3 시간)"
T=0
while [ "$T" -lt 180 ]; do
  E=$(powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'eval_' }).Count" \
    2>/dev/null | tr -d '\r ')
  case "$E" in ''|*[!0-9]*) E=-1 ;; esac
  [ "$E" = "0" ] && break
  sleep 60; T=$((T+1))
done
say "도는 평가가 없다 ($T 분 기다렸다)"

say "판정문을 낸다"
for spec in "${JOBS[@]}"; do
  IFS='|' read -r name _ _ _ <<< "$spec"
  short="${name#20260927_}"
  python _out/loop/verdict.py --run "$short" \
    --out "inbox/jay/20260923-lineage/VERDICT-$short.md" >/dev/null 2>&1 \
    && say "  판정문 $short" || say "  판정문 «못 냈다» $short"
done

say "상호작용을 센다"
{
  python _out/loop/interaction.py --design stones-x-feet
  echo
  python _out/loop/interaction.py --design logstd-x-feet
} > "$OUT/interaction-out.txt" 2>&1
sed 's/^/          /' "$OUT/interaction-out.txt" | tee -a "$LOG"

python _out/loop/heartbeat.py 2>&1 | sed 's/^/          /' | tee -a "$LOG"

date > "$DONE"
say "**다 끝났다.** supervisor.done 을 남긴다. 예약 작업은 이제 바로 빠져나온다"
