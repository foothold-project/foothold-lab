#!/usr/bin/env bash
# 새 E2 이어 가기 (경계 구간 뒤): lead 래퍼 환경 그대로 (e2_new.env · desired_kl 0.01 · VX_CORR 0.009 · UPDATE_ADJUST) + 경계 평가가 낸 결정.
# lead 02:4x 승인 · sonnet-code-lx. 학습 · 큐 · 런처 코드는 읽기만 하고 (잠근 사본 e2-new-1118), 이 스크립트와 e2c_*.py 만 새로 만들었다.
#   bash e2_continue.sh --print [--out OUT] [--iter 250]   결정 확인 + 런처가 만들 명령만 찍음 (아무것도 안 띄움)
#   systemd-run --user -p KillMode=process --unit=e2-continue-m250 bash e2_continue.sh --start      실제 기동 (첫 update 3b 확인 · run 받은편지함 알림까지)
# 멈춤 (rc): 3 = 결정이 continue 아님 (유지 표 HOLD 등: lead 판단, 기동 안 함) · 4 = 전제 불충족 · 5 = 기동 전 점검 실패 (학습이 이미 돎 · GPU 안 빔 등) · 6 = 기동 뒤 확인 실패
set -uo pipefail
MODE=${1:-}; shift || true
OUT=/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261119_013854/main/EX-42-B-E2_20261119_020447
IT=250
while [ $# -gt 0 ]; do case "$1" in --out) OUT=$2; shift 2 ;; --iter) IT=$2; shift 2 ;; *) echo "알 수 없는 인자 $1" >&2; exit 2 ;; esac; done
D=/home/jay/mai/tmp/lead/e2n
E2_ENV=${E2_ENV:-$D/e2_new.env}
COPY=${E2_COPY:-/home/jay/mai/wt/foothold-lab/e2-new-1118}
PROFILE=${FOOTHOLD_LINUX_ENV:-$HOME/mai/foothold-linux.env}
W=$D/continue/$(basename "$OUT"); mkdir -p "$W"    # OUT 별 작업 폴더
LOGDIR=/home/jay/mai/tmp/lead/e2_launch/E2_logdir
SIDECAR=/home/jay/mai/tmp/scripter/train-status-sidecar/train_status_sidecar.py
ORCA=${ORCA_BIN:-/home/jay/.config/orca/linux-orca-cli-shim/orca}
RUNID=run_5283fa2c059b
NEED_MIB=13500; GPUS="0 1"
say() { echo "$(date '+%m-%d %H:%M:%S') $*" | tee -a "$W/e2_continue.log"; }
notify() { [ "${E2C_NO_NOTIFY:-0}" = 1 ] && { say "[알림 생략] $1"; return 0; }
  "$ORCA" orchestration send --from "${ORCA_TERMINAL_HANDLE:-$(cat /home/jay/mai/tmp/lead/e2n/orca_from 2>/dev/null)}" --run "$RUNID" --to "run:$RUNID" --subject "[sonnet-code-lx] $1" --body "$2" >/dev/null 2>&1 && say "run 받은편지함 알림 보냄: $1" || say "알림 보내기 실패: $1"; }
free_mib() { nvidia-smi --query-gpu=index,memory.free --format=csv,noheader,nounits 2>/dev/null | awk -F', *' -v g="$1" '$1==g{print $2+0}'; }
gpus_free() { local g f; for g in $GPUS; do f=$(free_mib "$g"); [ -n "$f" ] && [ "$f" -ge "$NEED_MIB" ] || return 1; done; }
gpu_line() { local g o=""; for g in $GPUS; do o="$o GPU$g 빈 $(free_mib "$g") MiB"; done; echo "$o"; }
trainers() { pgrep -f -- 'scripts/train_start.py' 2>/dev/null; }
rank0_pid() {   # $1 = OUT. 런처 그룹 ($GP) 안 torchrun 의 자식 중 LOCAL_RANK=0
  local t p
  for t in $(pgrep -g "${GP:-0}" -f -- 'torch.distributed.run' 2>/dev/null); do
    for p in $(pgrep -P "$t" 2>/dev/null); do
      tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -qx 'LOCAL_RANK=0' || continue
      tr '\0' '\n' < /proc/$p/cmdline 2>/dev/null | grep -q -- "^--ex42_log_dir=$1" && { echo "$p"; return 0; }
    done
  done; return 1
}
load_env() {
  for k in $(env | grep -o '^EX42_[A-Z0-9_]*'); do unset "$k"; done
  set -a; . "$PROFILE"; . "$E2_ENV"; set +a
  : "${ISAAC311_PYTHON:?ISAAC311_PYTHON 없음 (machine profile)}"
  export EX42_PERCEPTION_VX_CORR_B=0.009                                   # lead 00:23 · 새 E2 와 같은 값
  export EX42_E2_HYDRA="${E2_KL_HYDRA:-agent.algorithm.desired_kl=0.01}"   # lead 래퍼와 같은 KL
  export CUDA_DEVICE_ORDER=PCI_BUS_ID NCCL_SHM_DISABLE=1 PYTHONPATH="$COPY${PYTHONPATH:+:$PYTHONPATH}" PYTHONDONTWRITEBYTECODE=1
  [ "${EX42_AUTO_TARGET_STAGE:-}" = E2 ] || { say "EX42_AUTO_TARGET_STAGE 가 E2 가 아님"; exit 4; }
  [ -n "${EX42_UPDATE_ADJUST:-}" ] && [ -f "$EX42_UPDATE_ADJUST" ] || { say "EX42_UPDATE_ADJUST 파일 없음: ${EX42_UPDATE_ADJUST:-unset}"; exit 4; }
}
decide() {   # 결정 확인 -> EX42_AUTO_* 를 이 셸에 export. rc 3 · 4 는 그대로 위로.
  local lines rc
  lines=$("$ISAAC311_PYTHON" -B "$D/e2c_decide.py" decide --out "$OUT" --iter "$IT" 2> "$W/decide.err"); rc=$?
  say "결정 확인 rc $rc: $(tail -c 600 "$W/decide.err" | tr '\n' ' ')"
  [ "$rc" = 0 ] || return "$rc"
  eval "$lines"
}
case "$MODE" in
  --print)
    load_env; decide || { rc=$?; say "결정이 continue 가 아니거나 전제 불충족 (rc $rc): 기동 안 함"; exit "$rc"; }
    "$ISAAC311_PYTHON" -B "$D/e2c_hydra.py" --print > "$W/print.out" 2>&1 || { say "런처 --print 실패: $(tail -3 "$W/print.out")"; exit 5; }
    cat "$W/print.out" | cut -c1-1500
    for pat in '--ex42_resume_from=' '--ex42_segment_end=' 'desired_kl=0.01' '--ex42_stage=E2'; do
      grep -q -- "$pat" "$W/print.out" && say "PRINT_CHECK 있음: $pat" || { say "PRINT_CHECK 없음: $pat"; exit 5; }
    done
    say "PRINT_CHECK 통과 (resume=$(basename "$EX42_AUTO_RESUME_CHECKPOINT") segment_end=$EX42_AUTO_SEGMENT_END VX_CORR_B=$EX42_PERCEPTION_VX_CORR_B UPDATE_ADJUST=$(basename "$EX42_UPDATE_ADJUST"))"
    exit 0 ;;
  --start)
    load_env
    [ -n "${INVOCATION_ID:-}" ] || say "경고: systemd 단위 밖에서 --start 중. 권장: systemd-run --user -p KillMode=process --unit=e2-continue-m$IT bash $0 --start"
    trainers >/dev/null && { say "기동 거절: train_start 가 이미 돌고 있음 ($(trainers | tr '\n' ' '))"; notify "E2 이어 가기 안 함 (학습이 이미 돎)" "train_start PID $(trainers | tr '\n' ' ') 가 있어 이어 가기를 시작하지 않았습니다."; exit 5; }
    gpus_free || { say "기동 거절: GPU 가 비어 있지 않음 ($(gpu_line))"; notify "E2 이어 가기 안 함 (GPU 안 빔)" "$(gpu_line) (필요 ${NEED_MIB} MiB 씩). 평가가 아직 GPU 를 쓰는지 확인 필요."; exit 5; }
    decide || { rc=$?
      notify "E2 이어 가기 멈춤 (rc $rc · lead 판단 필요)" "경계 m$IT 뒤 이어 가기를 하지 않았습니다. 결정 확인: $(tail -c 700 "$W/decide.err" | tr '\n' ' ') (rc 3 = 결정이 continue 아님, 예 유지 표 HOLD · rc 4 = 전제 불충족)"; exit "$rc"; }
    "$ISAAC311_PYTHON" -B "$D/e2c_hydra.py" --print > "$W/print.out" 2>&1 || { say "런처 --print 실패 (기동 안 함): $(tail -2 "$W/print.out")"; notify "E2 이어 가기 실패 (런처 --print)" "$(tail -c 500 "$W/print.out")"; exit 5; }
    if [ "${E2C_SKIP_DRY:-0}" != 1 ]; then   # CPU 한 rank 예행 (이어 가기 검증 · 저장본 상태 확인까지 가고 끝남). 실패하면 실제 기동도 실패하므로 여기서 멈춤.
      say "CPU 예행 (--dry-run) 시작 (최대 15 분 · E2C_SKIP_DRY=1 이면 건너뜀)"
      CUDA_VISIBLE_DEVICES= timeout -s KILL 900 taskset -c 37-44 "$ISAAC311_PYTHON" -B "$D/e2c_hydra.py" --dry-run > "$W/dry_run.out" 2>&1; DRC=$?
      if [ "$DRC" != 0 ] || LC_ALL=C grep -aq Traceback "$W/dry_run.out"; then
        say "CPU 예행 실패 rc $DRC: $(tail -c 500 "$W/dry_run.out" | tr '\n' ' ')"
        notify "E2 이어 가기 안 함 (CPU 예행 실패 rc $DRC)" "$(tail -c 900 "$W/dry_run.out")"; exit 5
      fi
      say "CPU 예행 통과"
    fi
    mkdir -p "$LOGDIR"; LOG=$W/e2_continue_$(date +%H%M%S).log
    ln -sfn "$LOG" "$LOGDIR/torchrun.stdout.log"
    say "기동: e2c_hydra.py → $LOG"
    nohup setsid "$ISAAC311_PYTHON" -B "$D/e2c_hydra.py" > "$LOG" 2>&1 &
    GP=$!; say "런처 PID $GP"
    R0=""; for i in $(seq 1 60); do R0=$(rank0_pid "$OUT") && break; sleep 5; done
    [ -n "$R0" ] || { say "rank0 PID 를 5 분 안에 못 찾음 (로그 $LOG)"; notify "E2 이어 가기 확인 실패 (rank0 없음)" "로그 $LOG 확인: $(grep -a -m3 -E 'refused|Traceback|Error' "$LOG" | cut -c1-200 | tr '\n' ' ')"; exit 6; }
    nohup /usr/bin/python3 "$SIDECAR" --out "$OUT" --log-dir "$LOGDIR" --pid "$R0" --interval 30 > "$W/sidecar.log" 2>&1 &
    say "곁 프로세스 PID $! (rank0 $R0)"
    say "첫 update 두 줄을 기다림 (최대 25 분)"
    OK=0; for i in $(seq 1 300); do
      LC_ALL=C grep -aqE 'Learning iteration (25[2-9]|2[6-9][0-9]|[3-9][0-9][0-9])/' "$LOG" && { OK=1; break; }
      LC_ALL=C grep -aq -E 'Traceback|Cuda error' "$LOG" && break
      kill -0 "$GP" 2>/dev/null || { pgrep -P "$GP" >/dev/null 2>&1 || pgrep -g "$GP" >/dev/null 2>&1 || break; }
      sleep 5
    done
    # 첫 update 3b 줄 확인 (lead 02:4x: foot_edge 음수 · std cap · slow_progress 0.6 · 열린 종류 상한)
    FAIL=""; chk() { if [ "$2" = ok ]; then say "  [있음] $1 $3"; else say "  [없음] $1 $3"; FAIL="$FAIL $1"; fi; }
    chk "Learning iteration 252 이후 줄" "$([ $OK = 1 ] && echo ok || echo no)" ""
    # foot_edge 는 처음 몇 회는 안 찍히거나 0 이다 (lead 12:35 m250 거짓 경보). 음수가 나올 때까지 최대 FE_WAIT 초 (기본 600) 더 기다린다.
    # 음수 = 통과 · 기다린 뒤에도 값 없음 또는 0 = 실패로 안 치고 [미확정] 로만 적음 · 양수 = 실패.
    fe_last() { LC_ALL=C grep -a "Episode_Reward/foot_edge" "$LOG" | tail -1 | grep -oE -- '-?[0-9.]+([eE]-?[0-9]+)?$' | tail -1; }
    FE=$(fe_last); FE_T0=$(date +%s)
    while [ "$(awk -v v="${FE:-0}" 'BEGIN{print (v+0<0)?1:0}')" = 0 ] && [ $(( $(date +%s) - FE_T0 )) -lt "${FE_WAIT:-600}" ] && kill -0 "$R0" 2>/dev/null; do sleep 10; FE=$(fe_last); done
    FE_KIND=$(awk -v v="${FE:-0}" -v e="${FE:+1}" 'BEGIN{ if (v+0<0) print "neg"; else if (v+0>0) print "pos"; else print "zero" }')
    case "$FE_KIND" in
      neg)  chk "foot_edge 음수" ok "(마지막 값 $FE)" ;;
      pos)  chk "foot_edge 음수" no "(마지막 값 $FE · 양수)" ;;
      *)    say "  [미확정] foot_edge 값 ${FE:-없음} (${FE_WAIT:-600} 초 기다려도 음수가 안 찍힘: 실패로 안 침 · lead 가 로그에서 본다)" ;;
    esac
    SC=$(LC_ALL=C grep -a "EX42_POLICY_STD_CAP" "$LOG" | tail -1 | cut -c1-160)
    chk "POLICY_STD_CAP 0.48" "$(echo "$SC" | grep -q '"cap": 0.48' && echo ok || echo no)" "$SC"
    # 이어 받기에서는 _restore 가 마지막 영수증 (ex42_update_adjust_m*.json) 의 after 값을 깔고 되읽기로 확인한다 (줄을 안 찍음).
    # 그래서 마지막 영수증 after 의 값으로 본다 (lead 11/19 04:2x · m250 에서 LIVE_ADJUST 줄만 찾다 거짓 경보).
    LR=$(ls "$OUT"/ex42_update_adjust_m*.json 2>/dev/null | sort -t m -k2 -V | awk -F'_m' '{print $NF" "$0}' | sort -n | tail -1 | cut -d' ' -f2)
    LA=$( [ -n "$LR" ] && python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['after']['rewards'].get('slow_progress'))" "$LR" 2>/dev/null)
    chk "slow_progress 0.6 (마지막 조정 영수증 after)" "$([ "$LA" = 0.6 ] && echo ok || echo no)" "($(basename "${LR:-없음}") · $LA)"
    # 조정 파일 (키 <= 시작 회차를 차례로 합친 마지막 상태) 와 live 상태가 다르면 알림 (lead 21:3x · EX42_LIVE_RESTORE 줄이 있는 새 코드면 그 줄도 비교)
    AS=$("$ISAAC311_PYTHON" -B "${ADJ_CHECK:-/home/jay/mai/wt/foothold-lab/adjust-restore-1119/_out/tools/ex42_adjust_state_check.py}" --adjust "$EX42_UPDATE_ADJUST" --out "$OUT" --start-iter "$IT" --log "$LOG" 2>&1); ASRC=$?
    chk "조정 파일 마지막 상태 = live" "$([ $ASRC = 0 ] && echo ok || echo no)" "$(echo "$AS" | cut -c1-400)"
    chk "VX_CORR b=0.009" "$(LC_ALL=C grep -a 'EX42_PERCEPTION_VX_CORR where=start' "$LOG" | grep -q 'b=0.009' && echo ok || echo no)" ""
    chk "FLAG_TURN_FIRST rad=0.5" "$(LC_ALL=C grep -aq 'EX42_FLAG_TURN_FIRST where=start rad=0.5' "$LOG" && echo ok || echo no)" ""
    chk "desired_kl 0.01 (hydra)" "$(LC_ALL=C grep -aq 'desired_kl' "$W/print.out" && echo ok || echo no)" ""
    VS=$("$ISAAC311_PYTHON" -B "$D/e2c_decide.py" verify-start --out "$OUT" --iter "$IT" 2>&1); VRC=$?
    chk "시작 노출 영수증 재계산 (D 축 이동 · 종류 상한)" "$([ $VRC = 0 ] && echo ok || echo no)" "$(echo "$VS" | cut -c1-600)"
    if [ -z "$FAIL" ]; then
      say "CONTINUE_RESULT ok"; notify "E2 이어 가기 기동 확인 (m$IT → $EX42_AUTO_SEGMENT_END)" "rank0 PID $R0 · 로그 $LOG · foot_edge ${FE} · $SC · 영수증: $VS · 확인 목록 전부 통과. GPU: $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"; exit 0
    fi
    say "CONTINUE_RESULT 실패 항목:$FAIL"; notify "E2 이어 가기 기동은 했으나 확인 실패:$FAIL" "rank0 PID $R0 (학습은 돌고 있음 · 끄지 않음) · 로그 $LOG · 영수증: $VS"; exit 6 ;;
  *) sed -n 2,9p "$0"; exit 1 ;;
esac
