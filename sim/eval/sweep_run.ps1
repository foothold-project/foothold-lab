# 난이도 스윕 실행기. 한 GPU 가 자기 몫의 칸을 순서대로 돈다.
#
# 쓰는 법:  powershell -File sweep_run.ps1 -Gpu 0 -Cells "1.0:0.1,1.0:0.2"
#   Cells 는 "속도:난이도" 를 쉼표로 이은 것.
#
# **출력 폴더는 칸마다 다르다.** 두 프로세스가 같은 자리에 쓰지 않게 하는 유일한 장치다.

param(
    [Parameter(Mandatory=$true)][int]$Gpu,
    [Parameter(Mandatory=$true)][string]$Cells,
    [string]$Root,
    [ValidateSet("unseen10", "rough6")][string]$TerrainSet = "unseen10",
    [string]$Terrains,
    [int]$EnvsPerTerrain = 10,
    [double]$RailThickness = 0,
    [string]$CondaEnv = $env:FOOTHOLD_ISAAC_ENV,
    [string]$Checkpoint = $env:FOOTHOLD_GO2_CHECKPOINT,
    [int]$Episodes = 100
)

$ErrorActionPreference = "Continue"

# **기계 이름이 붙은 경로를 박아 두지 않는다** (철칙 1). 저장소 자리는 이 스크립트
# 위치에서 되짚고, 환경·체크포인트는 인자나 환경변수로 받는다. 기본값은 이 기계의
# 것이지만 다른 PC 에서는 인자로 덮어쓰면 그대로 돈다.
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if (-not $Root)       { $Root = Join-Path $repo "sim\eval\results\20260910-difficulty-sweep" }
if (-not $CondaEnv)   { $CondaEnv = "$env:USERPROFILE\anaconda3\envs\isaac311" }
if (-not $Checkpoint) {
    $Checkpoint = "C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt"
}

$env:OMNI_KIT_ACCEPT_EULA = "YES"
$env:CUDA_VISIBLE_DEVICES = "$Gpu"

# **`conda run` 을 쓰지 않는다.** 두 개를 동시에 띄우면 활성화용 임시파일
# (`%TEMP%\__conda_tmp_*.txt`) 을 서로 밟아 한쪽이 1.6초 만에 exit=3 으로 죽는다
# (2026-09-10 실측 · GPU 두 대를 동시에 걸자마자 재현). 그래서 환경의 python.exe 를
# 직접 부르고, conda 활성화가 해 주던 PATH 만 손으로 깐다.
$py = Join-Path $CondaEnv "python.exe"

$env:CONDA_PREFIX = $CondaEnv
$env:PATH = ($CondaEnv, "$CondaEnv\Library\mingw-w64\bin", "$CondaEnv\Library\usr\bin",
             "$CondaEnv\Library\bin", "$CondaEnv\Scripts", "$CondaEnv\bin",
             $env:PATH) -join ";"

if (-not (Test-Path $py))         { throw "python.exe 가 없다: $py" }
if (-not (Test-Path $Checkpoint)) { throw "체크포인트가 없다: $Checkpoint" }

$ckpt = $Checkpoint

# 기록할 지형. 안 주면 집합마다 뜻이 있는 기본값을 쓴다.
#   unseen10 -> 실패 5종만 (통과 5종은 이 스윕의 관심사가 아니다)
#   rough6   -> 여섯 다
if (-not $Terrains) {
    if ($TerrainSet -eq "rough6") {
        $Terrains = "all"
    } else {
        $Terrains = "gap,rails,pit,stepping_stones,floating_ring"
    }
}

$terrains = $Terrains

Set-Location $repo

$log = Join-Path $Root ("_driver-gpu{0}.log" -f $Gpu)

# **두 폴더를 다 만든다.** `runs` 가 없으면 아래 `*>` 리다이렉트가 conda 를 부르기도
# 전에 죽고, 그러면 sec=0 · exit 빈칸으로 조용히 지나간다 (2026-09-10 에 실제로 겪음).
New-Item -ItemType Directory -Force -Path $Root | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "runs") | Out-Null

function Say($msg) {
    $line = "[{0}] gpu{1} | {2}" -f (Get-Date -Format "HH:mm:ss"), $Gpu, $msg

    # **이 로그를 `tail -f` 로 지켜보지 마십시오** `확인됨`. 윈도우에서 `tail` 이
    # 파일을 잡고 있으면 `Add-Content` 가 「다른 프로세스가 사용 중」으로 실패하고,
    # 로그가 그 자리에서 얼어붙는다. 2026-09-10 에 실제로 그렇게 됐다.
    # 실행은 30칸 전부 정상이었는데 로그만 첫 칸에서 멈춰, 하마터면 멀쩡한
    # 작업을 죽었다고 판단할 뻔했다.
    #
    # **진행 상황의 정본은 이 로그가 아니라 `runs/*/run_manifest.json` 이다.**
    # manifest 에는 기계가 적은 started/finished 가 들어 있고, 파일이 생겼다는
    # 사실 자체가 그 칸이 끝났다는 뜻이다.
    #
    # 실패해도 실행을 멈추지 않는다. 로그는 거들 뿐이다.
    Add-Content -Path $log -Value $line -Encoding utf8 -ErrorAction SilentlyContinue
    Write-Output $line
}

Say ("START cells=" + $Cells)

foreach ($cell in $Cells.Split(",")) {
    $parts = $cell.Split(":")
    $vx = [double]$parts[0]
    $diff = [double]$parts[1]

    # 거리 예산을 6 m 로 고정한다. 속도만 바뀌고 갈 수 있는 거리는 안 바뀐다.
    $dur = [math]::Round(6.0 / $vx, 4)

    # **소수 둘째 자리를 잘라 먹으면 안 된다.** "0.0" 형식으로 찍으면 0.12 가
    # "0.1" 이 되어 **이미 있는 칸을 덮어쓴다.** 벽 구간을 0.02 씩 촘촘히 잴 때
    # 정확히 그 일이 난다. 그래서 한 자리로 떨어지는 값만 "0.0" 을 쓰고,
    # 아니면 "0.00" 을 쓴다. 기존 칸 이름(d0.1 · d1.0)은 그대로 유지된다.
    if ([math]::Round($diff, 1) -eq $diff) {
        $dstr = $diff.ToString("0.0")
    } else {
        $dstr = $diff.ToString("0.00")
    }

    $name = "v{0}-d{1}" -f $vx.ToString("0.0"), $dstr
    $out = Join-Path $Root ("runs\" + $name)

    if (Test-Path (Join-Path $out "run_manifest.json")) {
        Say ("SKIP  " + $name + " (이미 있음)")
        continue
    }

    Say ("BEGIN " + $name + "  vx=" + $vx + " dur=" + $dur + " diff=" + $diff)
    $t0 = Get-Date

    # `rails` 두께를 못 박는 팔. 0 이면 안 준다(설정 그대로).
    $extra = @()

    if ($RailThickness -gt 0) {
        $extra += "--rail_thickness"
        $extra += "$RailThickness"
    }

    & $py sim/eval/eval_generalization.py `
        --checkpoint $ckpt `
        --terrain_set $TerrainSet `
        --terrains $terrains `
        --difficulty $diff `
        --episodes $Episodes `
        --envs_per_terrain $EnvsPerTerrain `
        --eval_duration $dur `
        --command_vx $vx `
        --min_progress_m 3.0 `
        --max_lateral_drift 0.75 `
        --max_velocity_mae 0.25 `
        --seed 42 `
        --headless `
        --device cuda:0 `
        --output_dir $out `
        --note ("difficulty sweep 20260910 | set=" + $TerrainSet + " vx=" + $vx + " difficulty=" + $diff + " | gpu" + $Gpu) `
        @extra `
        *> (Join-Path $Root ("runs\" + $name + ".log"))

    $code = $LASTEXITCODE
    $secs = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)

    # 종료코드만 믿지 않는다. 결과 파일이 실제로 생겼는지 센다.
    $csv = Join-Path $out "generalization_raw.csv"

    # `Measure-Object -Line` 은 이 저장소에 오답 기록이 있다(빈 문자열을 0줄로 셈).
    # 배열로 받아 원소를 센다.
    if (Test-Path $csv) {
        $n = @(Get-Content $csv).Count - 1
    } else {
        $n = -1
    }

    Say ("END   " + $name + "  exit=" + $code + " sec=" + $secs + " rows=" + $n)

    if ($n -lt 1) {
        Say ("FAIL  " + $name + " 결과 행이 없다. 로그를 본다: runs\" + $name + ".log")
    }
}

Say "DONE"
