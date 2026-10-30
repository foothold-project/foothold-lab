$ErrorActionPreference = 'Continue'
$taskDir = 'C:/mai/wt/foothold-lab/analyst-ame2/_out/reports/ex40-w57-followup-1031'
$pythonExe = 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe'
$guardRoot = 'C:/mai/mai-tools/tools/mai-resume'
$deadline = [DateTimeOffset]::Parse('2026-10-31T13:00:00+09:00')
$nextDue = [DateTimeOffset]::Now.AddSeconds(45)
$probe = $true
Set-Location -LiteralPath $guardRoot
while ([DateTimeOffset]::Now -lt $deadline -and -not (Test-Path -LiteralPath "$taskDir/M500-REPORTED") -and -not (Test-Path -LiteralPath "$taskDir/STOP-WAKE-V2")) {
    if ([DateTimeOffset]::Now -ge $nextDue) {
        $stamp = Get-Date -Format o
        if ($probe) {
            $message = "[EX40-M500 ASCII wake test $stamp] Delivery test only. Record arrival, then continue W57 review. No new GPU, training, stop, or live-ledger authority."
        } else {
            $message = "[EX40-M500 read-only wake $stamp] Check actual model_500 and manifest, runner observer PID21272 report ex40-m500-watch-1031, evaluator child PID, GPU UUID, and Kit device logs. Confirm GPU1 from evidence. Preserve training, supervisor, frozen source, and live ledger. Continue pending W57/verifier work. No new execution authority."
        }
        & $pythonExe -m mai_resume send --to term_d0d6549f-2da1-433c-9d05-58ce534224d7 --text $message --wait 45 2>&1 | Out-File -LiteralPath "$taskDir/wake-v2-send.log" -Append -Encoding utf8
        "$stamp rc=$LASTEXITCODE probe=$probe" | Out-File -LiteralPath "$taskDir/wake-v2-status.log" -Append -Encoding utf8
        if ($probe) {
            $probe = $false
            $nextDue = [DateTimeOffset]::Parse('2026-10-31T07:20:00+09:00')
        } else {
            $nextDue = [DateTimeOffset]::Now.AddMinutes(20)
        }
    }
    Start-Sleep -Seconds 10
}
"$(Get-Date -Format o) observer reminders finished" | Out-File -LiteralPath "$taskDir/wake-v2-status.log" -Append -Encoding utf8
