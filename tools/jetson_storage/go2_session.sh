#!/bin/bash
# ai-lx01 side of a real Go2 X record (11/19). Starts academy_1119.sh on the Jetson, sends the stage lines
# to the lead run, stops at the zero-Hz gate, then pulls to D and NAS.
#   go2_session.sh <marker>          e.g. 20261120-1400-lodging-full
# The owner moves the robot by joystick; nothing here sends a robot command.
set -u
N=${1:?marker}
cd "$(dirname "$0")"
O="-o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=8"
H=~/.mai/foothold-env/foothold.env   # team env file, local only (public repo): GO2X_SYNC_JETSON=user@addr
J=$(sed -n 's/^GO2X_SYNC_JETSON=//p' $H 2>/dev/null); [ -n "$J" ] || { echo "GO2X_SYNC_JETSON= missing in $H"; exit 1; }
RUN=run_5283fa2c059b
snd() { T=$(date +%H:%M); "$ORCA_CLI_COMMAND" orchestration send --run $RUN --subject "($T) $1" --body "($T) $2" >/dev/null 2>&1; echo "$(date +%T) $1"; }
log() { timeout -k 2 15 ssh $O $J "cat ~/go2_diag/records/$N/run.log" 2>/dev/null; }
scp -q $O jrec.py academy_1119.sh lowstate_once.py $J:go2_diag/jetson_storage/ || { snd "막힘: Jetson 에 못 붙음" "scp 실패 · $N 시작 안 함"; exit 1; }
timeout 20 ssh $O $J "cd ~/go2_diag/jetson_storage && ~/foothold-robot/venv/bin/python lowstate_once.py /tmp/lowstate-start-$N.json >/dev/null 2>&1; setsid nohup ./academy_1119.sh $N >/dev/null 2>&1 < /dev/null &" ; sleep 2
snd "기록 준비 · $N" "카메라 켜고 토픽 Hz 약 1~2 분. 아직 걷지 말 것. 「지금 서 있기 1 분」 줄이 오면 시작."
for k in $(seq 1 30); do sleep 10; log | grep -q '^gate ' && break; done
L=$(log)
if ! echo "$L" | grep -q '^gate ok'; then
  Z=$(echo "$L" | sed -n 's/^gate fail://p'); [ -z "$Z" ] && Z="Hz 단계가 5 분 안에 안 끝남"
  snd "기록 안 함 · 0 Hz 토픽:$Z" "$N 의 Hz 단계에서 0 인 것이 있어 full 기록을 시작하지 않았다 · 카메라 끔. 고친 뒤 다시 시작 (새 마커)."
  exit 2
fi
timeout 15 ssh $O $J "touch ~/go2_diag/records/$N/GO"
snd "지금 서 있기 1 분 (평평한 바닥 · 그대로)" "관문 통과 (L2 · imu · odom · 깊이 모두 Hz 있음) · 기록 540 초 시작."
sleep 60; snd "지금 걷기 (한 바퀴 이상 · 6 분 · 같은 자리로 돌아오기)" "3 분 뒤 중간 줄, 6 분 뒤 「지금 앉기」."
sleep 180; snd "걷기 3 분 지남 · 3 분 더" "같은 자리로 돌아올 준비."
sleep 180; snd "지금 앉기 (2 분 그대로)" "앉은 채 2 분 뒤 기록 끝 · 이어서 zstd 60 초."
for k in $(seq 1 60); do sleep 10; log | grep -q '^end ' && break; done
timeout 20 ssh $O $J "cd ~/go2_diag/jetson_storage && ~/foothold-robot/venv/bin/python lowstate_once.py ~/go2_diag/records/${N%-full}-zstdtest/lowstate-end.json" >/dev/null 2>&1
snd "기록 끝 · 받기 시작" "카메라 끔. D · NAS 받기와 대조 뒤 「꺼도 됨」."
python3 jetson_sync.py sync
grep -q "	$N	backed_up" ~/.mai/jetson-storage/log.tsv && snd "받기 끝 · 대조 통과 · 꺼도 됨" "$N · D · NAS 두 곳 sha256 통과." \
  || snd "받기 덜 됨" "$N · ~/.mai/jetson-storage/log.tsv 마지막 줄 확인. 타이머가 이어 받음."
