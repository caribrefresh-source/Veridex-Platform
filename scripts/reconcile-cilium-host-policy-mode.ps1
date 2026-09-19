[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('Check', 'Reconcile')]
    [string]$Action = 'Check',

    [string]$Kubeconfig = "$HOME/.kube/veridex-netcup-breakglass.yaml",

    [string]$DesiredStatePath = (Join-Path $PSScriptRoot '../docs/evidence/gap-closure/tls-public/stage-e/host-endpoint-policy-mode.json'),

    [switch]$ConfirmProductionChange
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Action -eq 'Reconcile' -and -not $ConfirmProductionChange) {
    throw 'Reconcile requires -ConfirmProductionChange. Run -Action Check first.'
}

$kubectl = Get-Command kubectl -ErrorAction Stop
$desired = Get-Content -LiteralPath $DesiredStatePath -Raw | ConvertFrom-Json
$pods = & $kubectl.Source --kubeconfig $Kubeconfig -n kube-system get pods `
    -l k8s-app=cilium -o json | ConvertFrom-Json

$results = foreach ($entry in $desired.nodes.PSObject.Properties) {
    $node = $entry.Name
    $wanted = [string]$entry.Value
    if ($wanted -notin @('Enabled', 'Disabled')) {
        throw "Invalid desired mode '$wanted' for $node."
    }

    $matches = @($pods.items | Where-Object { $_.spec.nodeName -eq $node })
    if ($matches.Count -ne 1) {
        throw "Expected one Cilium pod on $node; found $($matches.Count)."
    }

    $pod = [string]$matches[0].metadata.name
    $endpoint = (& $kubectl.Source --kubeconfig $Kubeconfig -n kube-system `
        exec $pod -c cilium-agent -- cilium-dbg endpoint get `
        -l reserved:host -o 'jsonpath={$[0].id}').Trim()
    if ($endpoint -notmatch '^\d+$') {
        throw "Could not derive the reserved:host endpoint on $node."
    }

    $config = & $kubectl.Source --kubeconfig $Kubeconfig -n kube-system `
        exec $pod -c cilium-agent -- cilium-dbg endpoint config $endpoint
    $modeMatch = [regex]::Match(($config -join "`n"), 'PolicyAuditMode\s*:\s*(Enabled|Disabled)')
    if (-not $modeMatch.Success) {
        throw "Could not read PolicyAuditMode for $node endpoint $endpoint."
    }

    $actual = $modeMatch.Groups[1].Value
    $changed = $false
    if ($actual -ne $wanted -and $Action -eq 'Reconcile') {
        if ($PSCmdlet.ShouldProcess("$node endpoint $endpoint", "Set PolicyAuditMode=$wanted")) {
            & $kubectl.Source --kubeconfig $Kubeconfig -n kube-system `
                exec $pod -c cilium-agent -- cilium-dbg endpoint config `
                $endpoint "PolicyAuditMode=$wanted"
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to reconcile $node endpoint $endpoint."
            }
            $actual = $wanted
            $changed = $true
        }
    }

    [pscustomobject]@{
        Node = $node
        Pod = $pod
        Endpoint = $endpoint
        Desired = $wanted
        Actual = $actual
        InSync = ($actual -eq $wanted)
        Changed = $changed
    }
}

$results | Sort-Object Node | Format-Table -AutoSize
if (@($results | Where-Object { -not $_.InSync }).Count -gt 0) {
    throw 'One or more host endpoints differ from the recorded desired state.'
}
