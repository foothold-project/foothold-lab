# 작업 2 — collisionApproximateCylinders 플래그 A/B 실측
# 험지 학습 30 iteration 을 플래그 유무로 각각 돌려 steps/s 를 비교한다.
# 결과: %TEMP%\bench_A.log, bench_B.log  + 요약 bench_summary.txt

& "$env:USERPROFILE\anaconda3\shell\condabin\conda-hook.ps1"
conda activate isaac311
Set-Location C:\isaac\IsaacLab
$env:OMNI_KIT_ACCEPT_EULA = "YES"

$TASK = "Isaac-Velocity-Rough-Unitree-Go2-v0"
$ENVS = 4096
$ITERS = 30
$sum = Join-Path $env:TEMP "bench_summary.txt"

function Run-One {
    param([string]$Label, [string[]]$Extra, [string]$LogPath)
    "=== $Label 시작 $(Get-Date -Format 'HH:mm:ss') ===" | Tee-Object -FilePath $sum -Append
    $args = @('train_go2_win.py','--task',$TASK,'--num_envs',"$ENVS",'--max_iterations',"$ITERS",'--headless') + $Extra
    $sw = [Diagnostics.Stopwatch]::StartNew()
    & python @args *> $LogPath
    $code = $LASTEXITCODE
    $sw.Stop()

    # steps/s 값들을 뽑아 평균 (초반 2회는 워밍업이라 제외)
    $sps = Select-String -Path $LogPath -Pattern 'Computation:\s+(\d+)\s+steps/s' -AllMatches |
           ForEach-Object { $_.Matches } | ForEach-Object { [int]$_.Groups[1].Value }
    $itt = Select-String -Path $LogPath -Pattern 'Iteration time:\s+([\d.]+)s' -AllMatches |
           ForEach-Object { $_.Matches } | ForEach-Object { [double]$_.Groups[1].Value }
    $spsWarm = if($sps.Count -gt 2){ $sps[2..($sps.Count-1)] } else { $sps }
    $ittWarm = if($itt.Count -gt 2){ $itt[2..($itt.Count-1)] } else { $itt }

    $r = [pscustomobject]@{
        Label      = $Label
        Exit       = $code
        WallMin    = [math]::Round($sw.Elapsed.TotalMinutes,2)
        Samples    = $spsWarm.Count
        StepsPerSec= if($spsWarm.Count){ [math]::Round(($spsWarm | Measure-Object -Average).Average,0) } else { 0 }
        StepsMin   = if($spsWarm.Count){ ($spsWarm | Measure-Object -Minimum).Minimum } else { 0 }
        StepsMax   = if($spsWarm.Count){ ($spsWarm | Measure-Object -Maximum).Maximum } else { 0 }
        IterSec    = if($ittWarm.Count){ [math]::Round(($ittWarm | Measure-Object -Average).Average,3) } else { 0 }
    }
    ($r | Format-List | Out-String) | Tee-Object -FilePath $sum -Append
    return $r
}

"===== 작업 2: 플래그 A/B 실측  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') =====" | Set-Content $sum
"task=$TASK  envs=$ENVS  iters=$ITERS" | Add-Content $sum

$A = Run-One -Label "A. 플래그 없음 (기본)" -Extra @() -LogPath (Join-Path $env:TEMP "bench_A.log")
Start-Sleep -Seconds 20   # GPU 메모리 회수 대기
$B = Run-One -Label "B. collisionApproximateCylinders=true" `
     -Extra @('--kit_args','--/physics/collisionApproximateCylinders=true') `
     -LogPath (Join-Path $env:TEMP "bench_B.log")

"" | Add-Content $sum
"===== 비교 =====" | Add-Content $sum
$delta = if($A.StepsPerSec -gt 0){ [math]::Round((($B.StepsPerSec - $A.StepsPerSec) / $A.StepsPerSec) * 100, 1) } else { 0 }
"A steps/s : $($A.StepsPerSec)  (iter $($A.IterSec)s, wall $($A.WallMin)분)" | Add-Content $sum
"B steps/s : $($B.StepsPerSec)  (iter $($B.IterSec)s, wall $($B.WallMin)분)" | Add-Content $sum
"차이      : $delta %" | Add-Content $sum
"완료 $(Get-Date -Format 'HH:mm:ss')" | Add-Content $sum
