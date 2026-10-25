# CPU only. Rebuild EX-32 result tables, figures, report, and SHA list.
$py = 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe'
$out = Split-Path -Parent $MyInvocation.MyCommand.Path
$report = Join-Path $out '../../REPORT-sol-26a.md'
$env:CUDA_VISIBLE_DEVICES = '-1'
& $py (Join-Path $out 'generate_result26a.py') `
  --label G0-B `
  --run-dir C:/mai/wt/foothold-lab/impl-g0b/logs/rsl_rl/foothold_s2_g0b/2026-10-25_20-37-41_g0b-main `
  --baseline-run C:/mai/wt/foothold-lab/lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main `
  --eval-root C:/mai/wt/foothold-lab/impl-turncases/logs/g0b_eval `
  --baseline-map C:/mai/wt/foothold-lab/impl-w2/logs_gate/eval/parent_b1500/map_modes.json `
  --baseline-probe C:/mai/wt/foothold-lab/impl-turncases/logs/six_cases/b1500 `
  --out $out --expected-modes none --turn-layout none:turn16 --report $report
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$rows = @(Get-ChildItem -LiteralPath $out -File |
  Where-Object Name -ne 'SHA256SUMS.txt' |
  Sort-Object Name |
  ForEach-Object {
    '{0}  {1}' -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(), $_.Name
  })
$rows += '{0}  {1}' -f (Get-FileHash -LiteralPath $report -Algorithm SHA256).Hash.ToLowerInvariant(), '../../REPORT-sol-26a.md'
$rows | Set-Content -LiteralPath (Join-Path $out 'SHA256SUMS.txt') -Encoding utf8
