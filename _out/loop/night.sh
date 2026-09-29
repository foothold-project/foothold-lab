#!/usr/bin/env bash
# 밤새 혼자 끝낸다. 학습 -> 등록 -> 평가 -> 판정 -> 자료 -> 영상 -> 다음 회차.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「학습 fs1, fs2 끝나면 절대 지시했다고 멈추지 말고 watchdog 으로
#       다시 세팅해서 전체 과정 실패 없이 진행해」 · 「1번으로 가」 (장치 교차)
#       `CRITERIA.md:495` GPU 금지 · `:544` GPU 효과 미측정
# 요지: **한 회차에 한 단계만** 하고 나간다. 예약 작업이 10 분마다 다시 부른다.
#       단계마다 표식을 남겨서 중간에 죽어도 다음 회차가 이어서 한다.
#
# 회차가 둘이다
#   1 회차  fs1 @cuda:0 (feet 0.01) · fs2 @cuda:1 (feet 0.1)
#   2 회차  fs1b @cuda:1 (feet 0.01) · fs2b @cuda:0 (feet 0.1)   <- 장치를 «바꾼다»
#
#   둘을 합치면 보상 x 장치 2 x 2 가 되어 **장치 효과와 보상 효과가 갈린다.**
#   1 회차만으로는 보상 대비가 장치 효과를 품고 있다.
#
# 내가 «안» 하는 것
#   보고서 본문을 자동 생성하지 않는다. 숫자와 영상과 표만 모아 둔다.
#   자동 생성한 산문은 근거 없는 문장을 만든다.

set -u
set -o pipefail

LAB="C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
ISAAC="C:/isaac/IsaacLab"
RUNS="$ISAAC/logs/rsl_rl/unitree_go2_gap_nvidia"
LOGS="$ISAAC/logs/gap_run_logs"
OUT="$LAB/_out/loop"
LOG="$OUT/night.log"
LOCK="$OUT/night.lock"
ROUNDF="$OUT/night.round"
BUNDLE="$LAB/sim/eval/results/20260928-scratch-vs-resume"
PY="C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe"
ITERS=4501

cd "$LAB" || exit 1
say() { echo "[밤 $(date '+%m/%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# ---------------------------------------------------------------- 자물쇠
if [ -f "$LOCK" ]; then
  AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$AGE" -lt 5400 ] && exit 0
  say "자물쇠가 ${AGE}초 묵었다. 버린다"
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

# ---------------------------------------------------------------- 회차
[ -f "$ROUNDF" ] || echo 1 > "$ROUNDF"
ROUND=$(tr -dc '0-9' < "$ROUNDF"); ROUND=${ROUND:-1}
STAGE="$OUT/night.stage.r$ROUND"

case "$ROUND" in
  1) A_NAME=20260928_fs1-scratch-f001   ; A_GPU=cuda:0 ; A_FEET=0.01
     B_NAME=20260928_fs2-scratch-f01    ; B_GPU=cuda:1 ; B_FEET=0.1
     LAUNCH=no ;;   # 1 회차는 이미 걸려 있다
  2) A_NAME=20260928_fs1b-scratch-f001-g1 ; A_GPU=cuda:1 ; A_FEET=0.01
     B_NAME=20260928_fs2b-scratch-f01-g0  ; B_GPU=cuda:0 ; B_FEET=0.1
     LAUNCH=yes ;;  # 2 회차는 이 스크립트가 건다
  *) say "회차 $ROUND · 할 일이 없다"; exit 0 ;;
esac

done_stage() { grep -qx "$1" "$STAGE" 2>/dev/null; }
mark_stage() { echo "$1" >> "$STAGE"; }

# ---------------------------------------------------------------- 조회
count_py() {   # $1 = 명령줄 정규식 · 못 읽으면 -1
  local out
  out=$(powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match '$1' }).Count" \
    2>/dev/null | tr -d '\r ')
  case "$out" in ''|*[!0-9]*) echo -1 ;; *) echo "$out" ;; esac
}
ckpt_max() {
  local d; d=$(ls -d "$RUNS"/*"$1"* 2>/dev/null | head -1)
  [ -z "$d" ] && { echo 0; return; }
  local m; m=$(ls "$d"/model_*.pt 2>/dev/null | sed 's/.*model_//;s/\.pt//' | sort -n | tail -1)
  echo "${m:-0}"
}
launched() { ls "$LOGS"/*"$1"*.log >/dev/null 2>&1; }
run_over() {
  ls "$RUNS"/*"$1"*/model_4500.pt >/dev/null 2>&1 && return 0
  local l; l=$(ls -t "$LOGS"/*"$1"*.log 2>/dev/null | head -1)
  [ -z "$l" ] && return 1
  grep -q "exit=" "$l" 2>/dev/null
}
launch_run() {   # 이름 · 장치 · feet
  say "  건다 · $1 · $2 · feet_air_time $3 · 처음부터 · lr 1e-3"
  powershell -NoProfile -Command \
    "Set-Location C:\isaac\IsaacLab; .\run_gap_train.ps1 -Task Isaac-Velocity-V2b-Unitree-Go2-v0 \
     -Iterations $ITERS -NumEnvs 4096 -Seed 42 -Device $2 -RunName $1 -FromScratch \
     -Extra @('agent.device=$2','agent.algorithm.learning_rate=1.0e-3','env.rewards.feet_air_time.weight=$3') -Detached" \
    2>&1 | grep -E "log file" | sed 's/^/          /' | tee -a "$LOG"
}

N=$(count_py 'run_name'); E=$(count_py 'eval_|record_')
if [ "$N" = "-1" ] || [ "$E" = "-1" ]; then say "프로세스를 못 읽었다. 이번 회차는 넘긴다"; exit 0; fi

# ---------------------------------------------------------------- 1 · 학습
if ! done_stage "train"; then
  # 2 회차는 여기서 «건다». 아직 안 걸렸고 GPU 가 비었을 때만.
  if [ "$LAUNCH" = "yes" ]; then
    if ! launched "$A_NAME" && [ "$N" -eq 0 ] && [ "$E" -eq 0 ]; then
      say "**회차 $ROUND · 장치를 바꾼 짝을 건다**"
      launch_run "$A_NAME" "$A_GPU" "$A_FEET"
      sleep 40
      launch_run "$B_NAME" "$B_GPU" "$B_FEET"
      exit 0
    fi
    if ! launched "$A_NAME"; then
      say "회차 $ROUND · GPU 가 아직 바쁘다 (학습 $N · 평가 $E). 기다린다"
      exit 0
    fi
  fi

  if run_over "$A_NAME" && run_over "$B_NAME"; then
    say "**회차 $ROUND · 학습 둘이 끝났다**"
    for r in "$A_NAME" "$B_NAME"; do
      if ls "$RUNS"/*"$r"*/model_4500.pt >/dev/null 2>&1; then
        say "  $r · 완주 4500"
      else
        l=$(ls -t "$LOGS"/*"$r"*.log 2>/dev/null | head -1)
        say "  $r · **완주 못 함** · 최대 $(ckpt_max "$r") · $(grep -o 'RuntimeError:.*' "$l" 2>/dev/null | tail -1 | cut -c1-56)"
      fi
    done
    mark_stage "train"
  else
    say "회차 $ROUND · 학습 중 · $(basename "$A_NAME") $(ckpt_max "$A_NAME") / 4500 · $(basename "$B_NAME") $(ckpt_max "$B_NAME") / 4500 · 도는 판 $N"
    exit 0
  fi
fi

# ---------------------------------------------------------------- 2 · 등록
if ! done_stage "register"; then
  say "상태 파일에 반영한다"
  $PY _out/loop/register.py 2>&1 | tail -6 | sed 's/^/          /' | tee -a "$LOG"
  mark_stage "register"; exit 0
fi

# ---------------------------------------------------------------- 3 · 평가
if ! done_stage "eval"; then
  if [ "$E" -gt 0 ]; then say "평가가 도는 중 ($E 개). 기다린다"; exit 0; fi
  if [ -f "$OUT/night.eval2-started.r$ROUND" ]; then
    say "평가가 끝났다 (최고점 구간 포함)"; mark_stage "eval"
  elif [ -f "$OUT/night.eval-started.r$ROUND" ]; then
    # 1 차가 끝났다. «최고점 구간» 을 더 잰다.
    # 근거: 학습 곡선에서 fs1 이 step 3765 · fs2 가 3892 에서 총 보상 최고를 찍고
    #       4500 에서 내려왔다. 다섯 점만 보면 그 구간을 건너뛴다 (팀장 지시).
    say "최고점 구간을 더 잰다 (3750 · 4000)"
    date > "$OUT/night.eval2-started.r$ROUND"
    FOOTHOLD_EVAL_CKPTS=3750,4000       $PY _out/loop/eval_runner.py 2>&1 | tail -4 | sed 's/^/          /' | tee -a "$LOG"
    exit 0
  else
    say "평가를 건다 (1500 · 2000 · 2500 · 3000 · 4500)"
    date > "$OUT/night.eval-started.r$ROUND"
    # 관문은 앞 넷을 본다 (verdict.py:41). 4500 은 «보고용» 이다.
    FOOTHOLD_EVAL_CKPTS=1500,2000,2500,3000,4500 \
      $PY _out/loop/eval_runner.py 2>&1 | tail -4 | sed 's/^/          /' | tee -a "$LOG"
    exit 0
  fi
fi

# ---------------------------------------------------------------- 4 · 판정
if ! done_stage "verdict"; then
  say "판정문을 낸다"
  for r in v2g2-feetair01 fs1-scratch-f001 fs2-scratch-f01 fs1b-scratch-f001-g1 fs2b-scratch-f01-g0; do
    ls -d "$RUNS"/*"$r"* >/dev/null 2>&1 || continue
    $PY _out/loop/verdict.py --run "$r" \
      --out "inbox/jay/20260927-methodology/VERDICT-$r.md" >/dev/null 2>&1 \
      && say "  판정문 $r" || say "  판정문 «못 냈다» $r"
  done
  mark_stage "verdict"; exit 0
fi

# ---------------------------------------------------------------- 5 · 자료 묶음
if ! done_stage "bundle"; then
  say "숫자를 한 곳에 모은다 -> $BUNDLE"
  mkdir -p "$BUNDLE"
  $PY _out/loop/bundle3.py --out "$BUNDLE" 2>&1 | tail -8 | sed 's/^/          /' | tee -a "$LOG"
  say "상세 표를 만든다 (지형별 · 집합별 · 성분별 · 체크포인트별)"
  $PY _out/loop/detail3.py --out "$BUNDLE" 2>&1 | tail -8 | sed 's/^/          /' | tee -a "$LOG"
  mark_stage "bundle"; exit 0
fi

# ---------------------------------------------------------------- 6 · 영상
if ! done_stage "video"; then
  if [ "$E" -gt 0 ]; then say "영상이 도는 중. 기다린다"; exit 0; fi
  if [ -f "$OUT/night.video-started.r$ROUND" ]; then
    say "영상이 끝났다"; mark_stage "video"
  else
    say "영상을 찍는다"
    date > "$OUT/night.video-started.r$ROUND"
    bash _out/loop/record3.sh >> "$LOG" 2>&1 &
    exit 0
  fi
fi

# ---------------------------------------------------------------- 6.5 · 보고서와 웹
if ! done_stage "report"; then
  say "보고서에 표를 끼워 넣는다 (서사는 사람 것 · 표식 사이만 갈아 끼운다)"
  $PY _out/loop/splice_report.py \
      --report docs/research/20260928-scratch-vs-resume.md \
      --bundle "$BUNDLE" 2>&1 | sed 's/^/          /' | tee -a "$LOG"

  say "웹을 굽는다 (관문 80 여 개를 지난다)"
  ( cd web && timeout 900 "$PY" _build/build.py > "$OUT/night.build.r$ROUND.log" 2>&1 )
  RC=$?
  if [ "$RC" -eq 0 ]; then
    say "  웹 빌드 통과 · 로그 _out/loop/night.build.r$ROUND.log"
  else
    say "  ** 웹 빌드가 막혔다 (종료 $RC). 사람이 로그를 볼 것 **"
    grep -E "🔴|배포를 중단|Traceback" "$OUT/night.build.r$ROUND.log" 2>/dev/null \
      | head -6 | sed 's/^/            /' | tee -a "$LOG"
  fi
  mark_stage "report"; exit 0
fi

# ---------------------------------------------------------------- 7 · 알림과 다음 회차
if ! done_stage "notify"; then
  say "텔레그램을 보낸다"
  $PY _out/loop/heartbeat.py 2>&1 | tail -3 | sed 's/^/          /' | tee -a "$LOG"
  mark_stage "notify"

  say "**회차 $ROUND 가 다 끝났다.**"
  say "  판정문   inbox/jay/20260927-methodology/VERDICT-*.md"
  say "  자료     $BUNDLE"
  say "  영상     sim/eval/results/20260928-scratch-clips"

  # **회차 2 를 뺐다** (팀장 지시 2026-09-28 · 「회차 2 빼고」)
  #
  # 원래 이유는 「장치 효과와 보상 효과를 2 x 2 로 가른다」였다. 그 사이에
  # 장치 효과를 «0 으로» 측정했다. 그래서 회차 2 는 이미 있는 파일을 복제한다.
  #
  #   v2b-r 대 v2b-p11 · resume · lr 1e-4 · sim 과 PPO 를 «같이» 옮긴 짝
  #     v2b-r   agent cuda:0 · sim cuda:0
  #     v2b-p11 agent cuda:1 · sim cuda:1
  #     체크포인트 121 개 «전수» · 정책 가중치와 optimizer 상태 텐서까지 전부 동일
  #     최대 차 0.000e+00
  #   probe-det-g0 (cuda:0) 대 fs2 (cuda:1) · 처음부터 · lr 1e-3 · 26 회
  #     model_0 과 model_25 가 완전 동일
  #
  # **한정이 있다. 0 인 것은 둘을 «같이» 옮긴 짝에서다.**
  #   v2b 는 agent cuda:0 · sim cuda:1 로 «갈라» 놓았고, v2b-p11 과
  #   model_0 부터 다르다 (0.0063 -> 25 에서 0.0897 -> 1500 에서 0.6216 ->
  #   3000 에서 1.1519). 그래서 「GPU 효과 0」을 조건 없이 쓰면 틀린다.
  #   회차 2 를 뺄 수 있는 이유는 `launch_run` 이 `-Device` 와
  #   `agent.device` 를 **같은 값으로** 주기 때문이다 (둘을 같이 옮긴다).
  #
  # 함정 하나를 같이 적는다. **파일 sha256 은 121 개가 전부 다르다.**
  # `torch.save` 가 텐서의 device 를 함께 적기 때문이다. 해시로만 보면
  # 「다르다」로 읽힌다. 내용은 같다. CRITERIA 가 이 칸을 오래 「미측정」으로
  # 둔 것도 이 함정일 수 있다.
  say "**회차 1 로 끝낸다.** 회차 2 (장치 교차) 는 «뺐다»"
  say "  왜: sim·PPO 를 같이 옮긴 짝에서 장치 효과가 0 이다 (121 개 전수 동일)"
  say "      fs1b 는 fs1 과, fs2b 는 fs2 와 비트 단위로 같은 파일이 된다"
  say "  보고서 두 장의 «본문» 은 사람이 쓴다"
fi

exit 0
