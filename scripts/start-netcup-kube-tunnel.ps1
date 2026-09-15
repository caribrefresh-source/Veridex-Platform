[CmdletBinding()]
param(
    [int]$LocalPort = 16443
)

$ErrorActionPreference = 'Stop'
$expectedUid = 'd7d8a462-c503-49ed-a1e0-899f372f9465'
$sshKey = Join-Path $env:USERPROFILE '.ssh\veridex_netcup_ed25519'

if (-not (Test-Path -LiteralPath $sshKey)) {
    throw "Missing netcup SSH key: $sshKey"
}

$listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $LocalPort `
    -State Listen -ErrorAction SilentlyContinue

if (-not $listener) {
    $arguments = @(
        '-N',
        '-L', "127.0.0.1:${LocalPort}:127.0.0.1:6443",
        '-i', $sshKey,
        '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=yes',
        '-o', 'ExitOnForwardFailure=yes',
        '-o', 'ServerAliveInterval=30',
        '-o', 'ServerAliveCountMax=3',
        'root@152.53.177.26'
    )
    $process = Start-Process -FilePath 'ssh.exe' -ArgumentList $arguments `
        -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 2
    if ($process.HasExited) {
        throw "netcup Kubernetes SSH tunnel exited with code $($process.ExitCode)"
    }
}

$uid = kubectl --context veridex-netcup get namespace kube-system `
    -o 'jsonpath={.metadata.uid}'
if ($LASTEXITCODE -ne 0 -or $uid -ne $expectedUid) {
    throw "Unexpected or unreachable netcup cluster identity: $uid"
}

Write-Output "veridex-netcup tunnel ready on 127.0.0.1:$LocalPort; cluster UID verified"
