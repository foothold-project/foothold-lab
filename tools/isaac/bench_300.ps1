# 작업 2-2 — 300 iteration 재측정
# 목적: 30 iteration에서 본 "에피소드 길이 절반" 이 진짜인지, 수렴하는지 확인
# 주의: PowerShell 에서 $args 는 자동변수라 변수명으로 쓰지 않는다 (1차 실패 원인)

& "$env:USERPROFILE\anaconda3\shell\condabin\conda-hook.ps1"
conda activate isaac311
Set-Location C:\isaac\IsaacLab
$env:OMNI_KIT_ACCEPT_EULA = "YES"

$TASK  = "Isaac-Velocity-Rough-Unitree-Go2-v0"
$ENVS  = 4096
$ITERS = 300
$SEED  = 42                      # 두 조건의 시드를 명시적으로 고정 — 공정 비교
$out   = Join-Path $env:TEMP "bench300_summary.txt"

"===== 300 iteration 재측정  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') =====" | Set-Content $out -Encoding UTF8
"task=$TASK  envs=$ENVS  iters=$ITERS  seed=$SEED" | Add-Content $out -Encoding UTF8

# --- A: 플래그 없음 ---
$logA = Join-Path $env:TEMP "b300_A.log"
"[A] 시작 $(Get-Date -Format 'HH:mm:ss')" | Add-Content $out -Encoding UTF8
$swA = [Diagnostics.Stopwatch]::StartNew()
python train_go2_win.py --task $TASK --num_envs $ENVS --max_iterations $ITERS --seed $SEED --headless *> $logA
$swA.Stop()
"[A] 종료 exit=$LASTEXITCODE  wall=$([math]::Round($swA.Elapsed.TotalMinutes,2))분" | Add-Content $out -Encoding UTF8

Start-Sleep -Seconds 30

# --- B: 플래그 있음 ---
$logB = Join-Path $env:TEMP "b300_B.log"
"[B] 시작 $(Get-Date -Format 'HH:mm:ss')" | Add-Content $out -Encoding UTF8
$swB = [Diagnostics.Stopwatch]::StartNew()
python train_go2_win.py --task $TASK --num_envs $ENVS --max_iterations $ITERS --seed $SEED --headless --kit_args="--/physics/collisionApproximateCylinders=true" *> $logB
$swB.Stop()
"[B] 종료 exit=$LASTEXITCODE  wall=$([math]::Round($swB.Elapsed.TotalMinutes,2))분" | Add-Content $out -Encoding UTF8

"완료 $(Get-Date -Format 'HH:mm:ss')" | Add-Content $out -Encoding UTF8
