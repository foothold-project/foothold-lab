# EX-41 relaunch (D178 / D179): m6000 -> 6000 updates, one HEAD, locked checkout.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File launch_ex41r.ps1 -Checkout <fixed worktree>
# The checkout must be a clean worktree at the pushed gate HEAD. ASCII only (PS 5.1 reads ANSI).
param([Parameter(Mandatory = $true)][string]$Checkout)
$ErrorActionPreference = 'Continue'
$env:OMNI_KIT_ACCEPT_EULA = 'YES'
$env:TEMP = 'D:/mai-tmp/runner'
$env:TMP = 'D:/mai-tmp/runner'
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONUTF8 = '1'
# Gate M9: alerts must reach the lead pane (11/04: 15 alerts sat pending without a target).
$env:EX41_ORCHESTRATION_TO = 'term_37f1d02b-35f8-435d-940e-d43a8a5be1de'
Remove-Item Env:CUDA_VISIBLE_DEVICES -ErrorAction SilentlyContinue
Set-Location $Checkout
$dirty = git status --porcelain --untracked-files=no
if ($dirty) { "refuse: checkout has uncommitted tracked changes" | Out-File -Append -Encoding utf8 D:/mai-tmp/lead/ex41_launch.txt; exit 3 }
$head = git rev-parse HEAD
$stamp = Get-Date -Format yyyyMMdd_HHmmss
$root = "C:/Users/AI-WS01/s2_lab/ex41_main_$stamp"
$run = "$root/main/EX-41-B-main_$stamp"
$log = "D:/mai-tmp/lead/ex41_main_$stamp.log"
"launch $(Get-Date -Format HH:mm:ss) head $head root $root log $log" | Out-File -Append -Encoding utf8 D:/mai-tmp/lead/ex41_launch.txt
# I04 (11/05 04:14): the push250 watcher is separate from training and was not started at launch.
# Start it here from the same checkout; it waits for scores and stable checkpoints by itself.
New-Item -ItemType Directory -Force "$root/eval/push250" | Out-Null
Start-Process -WindowStyle Hidden -WorkingDirectory $Checkout -FilePath 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' -ArgumentList '-m','foothold_s2.eval.ex41_push250_watch','--run-dir',$run,'--score-dir',"$root/eval/scores",'--out-dir',"$root/eval/push250" -RedirectStandardOutput "$root/eval/push250/watch.stdout.log" -RedirectStandardError "$root/eval/push250/watch.stderr.log"
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' 'foothold_s2/scripts/train_start.py' --task=FootholdS2-Go2-S2-SB-v0 --agent=rsl_rl_cfg_entry_point --num_envs=3072 --seed=42 --headless --device=cuda:0 --ex41_table='foothold_s2/curriculum/ex41-fixed5000.yaml' --ex41_parent_checkpoint='C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/model_6000.pt' --ex41_log_root=$run --ex41_score_dir="$root/eval/scores" --ex41-production-launch-approved *> $log
"end rc=$LASTEXITCODE $(Get-Date -Format HH:mm:ss)" | Out-File -Append -Encoding utf8 D:/mai-tmp/lead/ex41_launch.txt
