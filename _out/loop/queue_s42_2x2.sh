#!/usr/bin/env bash
# 시드 42 에서 «깨끗한» 2 x 2 를 닫는다. GPU 가 비는 대로 순서대로 건다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-27
# 근거: astra AUDIT9 3 절 「가장 명료한 첫 대조는 같은 NVIDIA actor·critic·
#       유효 std 에서 scalar 와 log «모두 optimizer 를 새로 시작» 하는 것」
# 요지: 네 칸을 «같은 optimizer 처리» 로 맞춘다. 두 칸만 걸면 오염된다.
#
# 왜 네 판인가 `확인됨`
#   기존 시드 42 두 칸(v2b-r · v2g2-feetair01)은 출발이
#   nvidia_pretrained_source 라 **optimizer 를 물려받았다** (로그로 확인).
#   새 log 판은 변환 체크포인트에 optimizer 가 «없어» 새로 시작할 수밖에 없다.
#   둘만 걸면 「매개화」와 「optimizer 처리」가 «같이» 바뀐다.
#   1 차 결합 판에서 이미 한 번 이런 오염을 겪었다.
#
#   그래서 scalar 쪽도 optimizer 를 버린 판으로 «다시» 돌린다.
#
# 네 칸
#   A  scalar + 0.01 + noopt      nvidia_pretrained_noopt
#   B  scalar + 0.1  + noopt      nvidia_pretrained_noopt
#   C  log    + 0.01 + noopt      nvidia_pretrained_logstd
#   D  log    + 0.1  + noopt      nvidia_pretrained_logstd
#
#   기존 v2b-r 과 v2g2-feetair01 은 «버리지 않는다». optimizer 를 물려받은
#   계보로 그대로 보존하고, 이 넷과 «섞지 않는다».
#
# 돌리는 법
#   bash _out/loop/queue_s42_2x2.sh

set -u
set -o pipefail
cd "C:/isaac/IsaacLab" || exit 1

say() { echo "[대기열 $(date '+%m/%d %H:%M:%S')] $*"; }

# 도는 학습 수. 숫자가 아니면 -1 («모른다») · @() 로 싸서 1 개일 때도 맞게 센다
trainers() {
  local out
  out=$(powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'run_name' }).Count" \
    2>/dev/null | tr -d '\r ')
  case "$out" in ''|*[!0-9]*) echo -1 ;; *) echo "$out" ;; esac
}

# 어느 GPU 가 비었나. 학습이 쓰는 device 를 읽어 «안 쓰는» 쪽을 돌려준다
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

launch() {
  local name="$1" dev="$2" std="$3" feet="$4" ckdir="$5"
  say "건다 · $name · $dev · std=$std · feet=$feet · 출발=$ckdir"
  powershell -NoProfile -Command \
    "Set-Location C:\isaac\IsaacLab; .\run_gap_train.ps1 -Task Isaac-Velocity-V2b-Unitree-Go2-v0 \
     -Iterations 3001 -NumEnvs 4096 -Seed 42 -Device $dev -RunName $name \
     -Extra @('agent.device=$dev','agent.policy.noise_std_type=$std','env.rewards.feet_air_time.weight=$feet','--load_run','$ckdir') -Detached" \
    2>&1 | grep -E "log file" | sed 's/^/          /'
  sleep 150
}

# A · B · C · D 를 «순서대로» · 빈 GPU 가 생길 때마다 하나씩
JOBS=(
  "20260927_s42A-scalar-f001-noopt|scalar|0.01|nvidia_pretrained_noopt"
  "20260927_s42B-scalar-f01-noopt|scalar|0.1|nvidia_pretrained_noopt"
  "20260927_s42C-log-f001|log|0.01|nvidia_pretrained_logstd"
  "20260927_s42D-log-f01|log|0.1|nvidia_pretrained_logstd"
)

say "시드 42 의 깨끗한 2 x 2 · 네 판을 «빈 GPU 가 생기는 대로» 건다"
say "  네 판 모두 optimizer 를 «새로» 시작한다. 그것이 이 배치의 전제다"

UNKNOWN=0
for spec in "${JOBS[@]}"; do
  IFS='|' read -r name std feet ckdir <<< "$spec"
  # 빈 GPU 가 생길 때까지 기다린다
  while :; do
    N=$(trainers)
    if [ "$N" = "-1" ]; then
      UNKNOWN=$((UNKNOWN + 1))
      say "  프로세스를 «못 읽었다» ($UNKNOWN 회). 계속 기다린다"
      [ "$UNKNOWN" -ge 20 ] && { say "** 스무 번 연속 못 읽었다. 멈춘다 **"; exit 3; }
      sleep 120; continue
    fi
    UNKNOWN=0
    if [ "$N" -lt 2 ]; then
      G=$(free_gpu)
      [ -n "$G" ] && break
    fi
    sleep 120
  done
  launch "$name" "$G" "$std" "$feet" "$ckdir"
done

say "네 판을 다 걸었다. 마지막 판이 끝나기를 기다린다"
while :; do
  N=$(trainers)
  [ "$N" = "0" ] && break
  sleep 180
done
say "시드 42 2 x 2 의 네 판이 «다 끝났다»"
