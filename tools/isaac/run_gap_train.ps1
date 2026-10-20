# Go2 gap training on AI-WS01 - reproduction of the RunPod method (임석헌 · A/정책학습)
#
# 분류: 운영
# 작성: Claude 세션 (오흥재 지시) · 2026-09-10
# 근거: s3://rzklpc35sl/limseokheon/isaaclab/logs/rsl_rl/unitree_go2_gap_nvidia/
#        0909_nvidia_gap_v3_seed42_iter900/params/{env,agent}.yaml 실측
# 요지: NVIDIA 사전학습 체크포인트에서 출발해 험지 6종 0.9 + forward_gap 0.1 지형으로 학습한다
# 상태: 확정
#
# 사용법
#   .\run_gap_train.ps1 -Iterations 10   -NumEnvs 4096 -RunName smoke   (작은 시험)
#   .\run_gap_train.ps1 -Iterations 1501 -NumEnvs 4096 -RunName full    (본 학습)
#
# ---------------------------------------------------------------------------
# 이 스크립트가 이렇게 생긴 이유 (두 번 실패하고 고친 것)
#
# 1. EULA
#    Isaac Sim 5.1 은 kit_app.py 에서 EULA 를 물어본다. 비대화형 셸에서는
#    input() 이 EOF 로 죽는다. OMNI_KIT_ACCEPT_EULA=YES 로 건너뛴다.
#
# 2. PowerShell 이 파이썬 경고를 「오류」로 바꿔 학습을 죽인다  ★ 이게 진짜 함정
#    PowerShell 5.1 에서 네이티브 exe 의 stderr 를 *>&1 로 받으면 각 줄이
#    NativeCommandError 로 포장된다. 여기에 $ErrorActionPreference="Stop" 이
#    걸리면 파이썬이 UserWarning 한 줄만 뱉어도 스크립트가 종료된다.
#    실제로 4096 환경 생성까지 다 끝낸 학습이 obs_groups 경고 한 줄에 죽었다.
#    그래서 리다이렉션을 PowerShell 이 아니라 cmd.exe 에 맡긴다.
# ---------------------------------------------------------------------------

param(
    [int]$Iterations = 10,
    [int]$NumEnvs = 4096,
    [string]$RunName = "smoke",
    # 학습 조건을 고르는 팔. 기본값은 A(연습 틈 0.05~0.20).
    #   Isaac-Velocity-Gap-Unitree-Go2-v0      A · 좁은 틈
    #   Isaac-Velocity-GapWide-Unitree-Go2-v0  B · 평가 규격에 맞춘 틈 0.15~0.40
    [string]$Task = "Isaac-Velocity-Gap-Unitree-Go2-v0",
    [string]$Device = "cuda:0",
    [int]$Seed = 42,
    # 본 학습처럼 오래 도는 작업은 반드시 -Detached 로 띄운다.
    # 부모 셸(에이전트 백그라운드 태스크)이 10분 타임아웃으로 죽어도 학습은 살아남아야 한다.
    [switch]$Detached,
    # 처음부터 학습한다. resume/load_run/checkpoint 를 «넣지 않는다».
    # 근거: train.py:177,207 이 agent_cfg.resume 으로 갈린다 (2026-09-28 확인).
    [switch]$FromScratch,
    # hydra 덮어쓰기 같은 «추가 인자». 예: "agent.device=cuda:1"
    #   --device 는 AppLauncher 가 정의한 «시뮬레이션» 장치 인자다
    #   ("The device to run the simulation on"). PPO 장치는 agent.device 로
    #   따로 준다. IsaacLab 공식 hydra 덮어쓰기라 train.py 를 안 고쳐도 된다.
    [string[]]$Extra = @(),
    # 계측판을 쓰려면 train_instrumented.py 를 준다
    [string]$Script = "train_go2_win.py"
)

# 주의: Stop 을 쓰지 않는다. 위 2번 참조.
$ErrorActionPreference = "Continue"

$env:OMNI_KIT_ACCEPT_EULA = "YES"

Set-Location "C:\isaac\IsaacLab"

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$tag = "{0}_{1}" -f $stamp, $RunName
$logDir = "C:\isaac\IsaacLab\logs\gap_run_logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir ("{0}.log" -f $tag)

# 시작점: NVIDIA 공식 체크포인트를 iter=0 으로 재저장해 둔 사본.
#   원본 .pretrained_checkpoints/.../checkpoint.pt 는 iter=1499 를 들고 있다.
#   rsl_rl 의 load() 가 그 값을 current_learning_iteration 에 넣기 때문에
#   원본을 그대로 resume 하면 카운터가 1499 에서 시작해 버린다.
$loadRun = "nvidia_pretrained_source"
$loadCkpt = "nvidia_pretrained.pt"

# max_iterations 주의
#   rsl_rl 은 for it in range(start, start+N) 으로 돌며 model_{it}.pt 를 저장한다.
#   start=0 에서 model_1500.pt 를 얻으려면 N=1501 이어야 한다.
#   N=1500 이면 model_1499.pt 에서 끝나고 model_1500.pt 는 생기지 않는다.

$python = "C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe"

$baseArgs = @(
    $Script,
    "--task $Task",
    "--headless",
    "--num_envs $NumEnvs",
    "--max_iterations $Iterations",
    "--seed $Seed",
    "--device $Device",
    "--run_name $RunName"
)
if (-not $FromScratch) {
    $baseArgs += @("--resume", "--load_run $loadRun", "--checkpoint $loadCkpt")
}
$argString = ($baseArgs + $Extra) -join " "

$fullCommand = '"{0}" {1}' -f $python, $argString

# 재현용 기록: 명령 전문을 로그 첫머리에 남긴다
$header = @(
    "=== command ===",
    $fullCommand,
    "=== context ===",
    ("started       : {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    ("host          : {0}" -f $env:COMPUTERNAME),
    ("task          : {0}" -f $Task),
    ("iterations    : {0}" -f $Iterations),
    ("num_envs      : {0}" -f $NumEnvs),
    ("device        : {0}" -f $Device),
    ("seed          : {0}" -f $Seed),
    ("start ckpt    : logs/rsl_rl/unitree_go2_gap_nvidia/{0}/{1}" -f $loadRun, $loadCkpt),
    ("EULA env      : {0}" -f $env:OMNI_KIT_ACCEPT_EULA),
    ""
)
$header | Out-File -FilePath $logFile -Encoding utf8

Write-Output "log file: $logFile"
Write-Output "command : $fullCommand"

# 재현용 .cmd 를 만든다. 이 파일 하나가 곧 「실행 명령 전문」이라 나중에 그대로 다시 돌릴 수 있다.
# 리다이렉션도 여기서 처리한다. PowerShell 이 네이티브 stderr 를 만지면 NativeCommandError 가 된다.
$cmdFile = Join-Path $logDir ("{0}.cmd" -f $tag)
# 주의: 각 -f 식은 반드시 괄호로 묶는다.
#   "a","b","{0}" -f $x  는 배열 전체를 형식문자열로 삼아 한 줄로 뭉개 버린다.
#   실제로 그 실수로 .cmd 가 한 줄짜리 쓰레기가 됐고, Start-Process 는 PID 를
#   멀쩡히 돌려줬으며, 학습은 시작조차 못 한 채 조용히 끝났다.
$cmdLines = @(
    "@echo off",
    "rem Go2 gap training - regenerated command, runnable as-is",
    ("rem generated: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "set OMNI_KIT_ACCEPT_EULA=YES",
    "cd /d C:\isaac\IsaacLab",
    ('{0} >> "{1}" 2>&1' -f $fullCommand, $logFile),
    ('echo finished exit=%ERRORLEVEL% >> "{0}"' -f $logFile)
)
$cmdLines | Out-File -FilePath $cmdFile -Encoding ascii

# 관문: 쓴 것을 되읽어 「실제로 학습 명령이 들어 있는지」 스스로 주장하게 한다.
$written = Get-Content $cmdFile
if (($written.Count -lt 6) -or -not ($written -match [regex]::Escape($Script))) {
    Write-Output "FATAL: generated .cmd is malformed - training command missing"
    $written | ForEach-Object { Write-Output ("  | {0}" -f $_) }
    exit 9
}

Write-Output "cmd file: $cmdFile"

if ($Detached) {
    # 부모가 죽어도 살아남게 띄운다. PID 는 파일로 남겨 나중에 생존 확인에 쓴다.
    $proc = Start-Process -FilePath $cmdFile -WindowStyle Hidden -PassThru
    $pidFile = Join-Path $logDir ("{0}.pid" -f $tag)
    $proc.Id | Out-File -FilePath $pidFile -Encoding ascii
    ("launcher pid  : {0}" -f $proc.Id) | Out-File -FilePath $logFile -Encoding utf8 -Append
    Write-Output "launched detached, launcher pid: $($proc.Id)"
    Write-Output "pid file: $pidFile"
    # 주의: PID 가 돌아온 것은 「띄웠다」는 뜻일 뿐 「살아 있다」는 뜻이 아니다.
    #       호출한 쪽이 몇 분 뒤 반드시 생존과 체크포인트 증가를 다시 확인해야 한다.
    exit 0
}

& $cmdFile
$code = $LASTEXITCODE

Write-Output "exit code: $code"
exit $code
