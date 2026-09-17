[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^age1[0-9a-z]+$')]
    [string]$AgeRecipient,

    [string]$OutputPath = '.tmp/route53-credentials.enc.yaml'
)

$ErrorActionPreference = 'Stop'
$accessKeyBstr = [IntPtr]::Zero
$secretKeyBstr = [IntPtr]::Zero
$accessKey = $null
$secretKey = $null

try {
    foreach ($command in @('kubectl', 'sops')) {
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
            throw "Required command '$command' is not installed or not on PATH."
        }
    }

    $context = kubectl config current-context
    Write-Host "Active Kubernetes context: $context"
    if ($context -ne 'veridex-netcup') {
        throw "Refusing to continue: expected context 'veridex-netcup'."
    }

    $confirmation = Read-Host "Type veridex-netcup to confirm the target cluster"
    if ($confirmation -cne 'veridex-netcup') {
        throw 'Cluster confirmation did not match.'
    }

    $accessKeySecure = Read-Host 'AWS access-key ID' -AsSecureString
    $secretKeySecure = Read-Host 'AWS secret access key' -AsSecureString
    $accessKeyBstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($accessKeySecure)
    $secretKeyBstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secretKeySecure)
    $accessKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($accessKeyBstr)
    $secretKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretKeyBstr)

    if ([string]::IsNullOrWhiteSpace($accessKey) -or [string]::IsNullOrWhiteSpace($secretKey)) {
        throw 'Both credential components are required.'
    }

    $secret = [ordered]@{
        apiVersion = 'v1'
        kind = 'Secret'
        metadata = [ordered]@{
            name = 'route53-credentials'
            namespace = 'cert-manager'
        }
        type = 'Opaque'
        stringData = [ordered]@{
            'access-key-id' = $accessKey
            'secret-access-key' = $secretKey
        }
    } | ConvertTo-Json -Depth 8

    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = (Get-Command sops).Source
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    foreach ($argument in @('--encrypt', '--age', $AgeRecipient, '--encrypted-regex', '^(data|stringData)$', '--input-type', 'json', '--output-type', 'yaml', '/dev/stdin')) {
        [void]$startInfo.ArgumentList.Add($argument)
    }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    [void]$process.Start()
    $process.StandardInput.Write($secret)
    $process.StandardInput.Close()
    $encryptedText = $process.StandardOutput.ReadToEnd()
    $null = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if ($process.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($encryptedText)) {
        throw 'SOPS encryption failed; no output was written.'
    }

    if ($encryptedText -notmatch 'ENC\[' -or $encryptedText.Contains($accessKey) -or $encryptedText.Contains($secretKey)) {
        throw 'Encrypted output validation failed; no output was written.'
    }

    $parent = Split-Path -Parent $OutputPath
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
    $resolvedOutputPath = if ([IO.Path]::IsPathFullyQualified($OutputPath)) {
        $OutputPath
    } else {
        Join-Path (Get-Location) $OutputPath
    }
    [IO.File]::WriteAllText($resolvedOutputPath, $encryptedText, [Text.UTF8Encoding]::new($false))
    Write-Host "Encrypted SOPS manifest written to $resolvedOutputPath"
}
finally {
    if ($accessKeyBstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($accessKeyBstr) }
    if ($secretKeyBstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretKeyBstr) }
    $accessKey = $null
    $secretKey = $null
    $accessKeySecure = $null
    $secretKeySecure = $null
}
