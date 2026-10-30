$ErrorActionPreference = 'Stop'
$source = 'C:/mai/wt/foothold-lab/analyst-ex40-main-verified-1031'
$expectedHead = '2df419b0a4278981f6bd26e5eaedecbf7e8458db'
Set-Location -LiteralPath $source
$actualHead = (git rev-parse HEAD).Trim()
if ($actualHead -ne $expectedHead) { throw 'Fixed HEAD differs' }
if (git status --porcelain) { throw 'Fixed source is not clean' }
$ex40Start = Get-Date
$ex40Expected = $ex40Start.AddHours(67)
$ex40EndBy = $ex40Expected.AddHours(24)
$env:EX40_EXPECTED_FINISH = $ex40Expected.ToString('o')
$env:LIVE = '0'
$env:PYTHONDONTWRITEBYTECODE = '1'
Remove-Item Env:CUDA_VISIBLE_DEVICES -ErrorAction SilentlyContinue
$ex40Root = 'C:/Users/AI-WS01/s2_lab/ex40_main_dry_' + $ex40Start.ToString('yyyyMMdd_HHmmss')
$reportRoot = 'C:/mai/wt/foothold-lab/analyst-ame2/_out/reports/ex40-coord-1031'
$record = [ordered]@{ at=$ex40Start.ToString('o'); source=$source; head=$actualHead; LIVE='0'; expected_finish=$env:EX40_EXPECTED_FINISH; end_by=$ex40EndBy.ToString('o'); max_wall_seconds=345600; root=$ex40Root; argv=@('foothold_s2/run_ex40_b11.sh','B','cuda:0',$ex40EndBy.ToString('o'),$ex40Root,($ex40Root+'/scores'),'main'); training_started=$false }
$record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ($reportRoot+'/MAIN-DRY-LAUNCH.json') -Encoding UTF8
& 'C:/Program Files/Git/bin/bash.exe' @($record.argv) 1> ($reportRoot+'/MAIN-DRY-stdout.txt') 2> ($reportRoot+'/MAIN-DRY-stderr.txt')
$rc=$LASTEXITCODE
[ordered]@{ rc=$rc; finished=(Get-Date).ToString('o'); head=(git rev-parse HEAD).Trim(); root=$ex40Root; LIVE=$env:LIVE; training_started=$false } | ConvertTo-Json | Set-Content -LiteralPath ($reportRoot+'/MAIN-DRY-process.json') -Encoding UTF8
Get-Content -LiteralPath ($reportRoot+'/MAIN-DRY-stdout.txt')
Get-Content -LiteralPath ($reportRoot+'/MAIN-DRY-stderr.txt')
exit $rc
