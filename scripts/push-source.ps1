param([string]$Repository = 'Self-Command/word-module-studio', [Parameter(Mandatory=$true)][string]$Baseline)
# Development transport fallback: upload only explicit tracked Git changes.
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
function Invoke-TaskApi([string]$Path, [string]$Method='GET', $Body=$null) {
    for ($taskAttempt=0; $taskAttempt -lt 3; $taskAttempt++) {
        if ($null -eq $Body) { $taskOutput = gh api $Path } else {
            $taskOutput = ($Body | ConvertTo-Json -Depth 15 -Compress) | gh api --method $Method $Path --input -
        }
        if ($LASTEXITCODE -eq 0) { return ($taskOutput | ConvertFrom-Json) }
    }
    throw "GitHub transport failed: $Path"
}
$taskBase = Invoke-TaskApi "repos/$Repository/git/ref/heads/main"
$taskCommit = Invoke-TaskApi "repos/$Repository/git/commits/$($taskBase.object.sha)"
$taskEntries = @()
foreach ($taskChange in (git -C $taskRoot diff --name-status $Baseline HEAD)) {
    $taskFields = $taskChange -split "`t"
    $taskPath = $taskFields[-1]
    if ($taskFields[0] -eq 'D') { $taskEntries += @{path=$taskPath; mode='100644'; type='blob'; sha=$null}; continue }
    $taskResolved = [IO.Path]::GetFullPath((Join-Path $taskRoot $taskPath))
    if (-not $taskResolved.StartsWith($taskRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected path' }
    $taskBlob = Invoke-TaskApi "repos/$Repository/git/blobs" 'POST' @{encoding='base64'; content=[Convert]::ToBase64String([IO.File]::ReadAllBytes($taskResolved))}
    $taskEntries += @{path=$taskPath; mode='100644'; type='blob'; sha=$taskBlob.sha}
}
if ($taskEntries.Count -eq 0) { Write-Output 'No tracked source changes'; exit 0 }
$taskTree = Invoke-TaskApi "repos/$Repository/git/trees" 'POST' @{base_tree=$taskCommit.tree.sha; tree=$taskEntries}
$taskNewCommit = Invoke-TaskApi "repos/$Repository/git/commits" 'POST' @{message=(git -C $taskRoot log -1 --format=%s); tree=$taskTree.sha; parents=@($taskBase.object.sha)}
Invoke-TaskApi "repos/$Repository/git/refs/heads/main" 'PATCH' @{sha=$taskNewCommit.sha; force=$false} | Select-Object -ExpandProperty object
Write-Output "Uploaded $($taskEntries.Count) explicit tracked files"
