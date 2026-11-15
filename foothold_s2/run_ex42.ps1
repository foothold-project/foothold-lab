param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('ops-check', 'rehearsal', 'production')]
    [string]$Mode,
    [Parameter(Mandatory = $true)]
    [string]$Exp,
    [string]$Python,
    [string]$Table,
    [string]$Approvals,
    [string]$Graduation,
    [string]$TerrainManifest,
    [string]$SourceRoot,
    [string]$ExpectedHead,
    [string]$RehearsalOutput,
    [int[]]$RehearsalStageUpdates,
    [switch]$ProductionLaunchApproved
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
Push-Location $repoRoot
try {
    $bootstrap = Get-Command python -ErrorAction Stop
    $profilePython = (& $bootstrap.Source -m foothold_s2.machine_profile --print-path conda_python).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $profilePython) { throw 'Selected machine profile did not provide conda_python.' }
    if ($Python -and [System.IO.Path]::GetFullPath($Python) -ne [System.IO.Path]::GetFullPath($profilePython)) {
        throw 'Python override differs from the selected machine profile.'
    }
    $Python = $profilePython
    $pythonArgs = @('-m', 'foothold_s2.scripts.ex42_ops', "--$Mode", '--exp', $Exp)
    if ($Table) { $pythonArgs += @('--table', $Table) }
    if ($Approvals) { $pythonArgs += @('--approvals', $Approvals) }
    if ($Graduation) { $pythonArgs += @('--graduation', $Graduation) }
    if ($TerrainManifest) { $pythonArgs += @('--terrain-manifest', $TerrainManifest) }
    if ($SourceRoot) { $pythonArgs += @('--source-root', $SourceRoot) }
    if ($ExpectedHead) { $pythonArgs += @('--expected-head', $ExpectedHead) }
    if ($RehearsalOutput) { $pythonArgs += @('--rehearsal-output', $RehearsalOutput) }
    if ($RehearsalStageUpdates) { $pythonArgs += @('--rehearsal-stage-updates') + $RehearsalStageUpdates }
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
