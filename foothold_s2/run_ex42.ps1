param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('ops-check', 'rehearsal', 'production')]
    [string]$Mode,
    [string]$Python = 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe',
    [string]$Table = "$PSScriptRoot/curriculum/ex42-prep.yaml",
    [string]$Approvals = "$PSScriptRoot/curriculum/ex42-approvals.yaml",
    [string]$Graduation,
    [string]$TerrainManifest,
    [string]$SourceRoot,
    [string]$ExpectedHead,
    [switch]$ProductionLaunchApproved
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
Push-Location $repoRoot
try {
    $pythonArgs = @('-m', 'foothold_s2.scripts.ex42_ops', "--$Mode",
                    '--table', $Table, '--approvals', $Approvals)
    if ($Graduation) { $pythonArgs += @('--graduation', $Graduation) }
    if ($TerrainManifest) { $pythonArgs += @('--terrain-manifest', $TerrainManifest) }
    if ($SourceRoot) { $pythonArgs += @('--source-root', $SourceRoot) }
    if ($ExpectedHead) { $pythonArgs += @('--expected-head', $ExpectedHead) }
    if ($ProductionLaunchApproved) { $pythonArgs += '--production-launch-approved' }

    & $Python @pythonArgs
    $pythonExit = $LASTEXITCODE
    if ($pythonExit -ne 0) {
        throw "EX-42 $Mode gate rejected the request (rc=$pythonExit). No simulator or training process was started."
    }
}
finally {
    Pop-Location
}
