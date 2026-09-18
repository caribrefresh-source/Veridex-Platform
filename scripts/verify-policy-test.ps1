[CmdletBinding()]
param(
  [string]$EvidenceRoot = "docs/evidence/gates/gate-34/runtime",
  [int]$Runs = 2
)

$ErrorActionPreference = "Stop"
$namespace = "veridex-policy-test"
$required = @(
  @{ Verb = "create"; Resource = "pods"; Namespace = $namespace },
  @{ Verb = "delete"; Resource = "pods"; Namespace = $namespace },
  @{ Verb = "create"; Resource = "roles.rbac.authorization.k8s.io"; Namespace = $namespace },
  @{ Verb = "create"; Resource = "rolebindings.rbac.authorization.k8s.io"; Namespace = $namespace },
  @{ Verb = "create"; Resource = "pods/exec"; Namespace = "kube-system" }
)
foreach ($check in $required) {
  $answer = kubectl auth can-i $check.Verb $check.Resource -n $check.Namespace
  if ($answer -ne "yes") { throw "Authorized evidence identity required: cannot $($check.Verb) $($check.Resource) in $($check.Namespace)." }
}

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$dir = Join-Path $EvidenceRoot $stamp
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$uidBefore = kubectl get namespace $namespace -o jsonpath='{.metadata.uid}'

function Save-Output([string]$Name, [scriptblock]$Command) {
  & $Command 2>&1 | Tee-Object -FilePath (Join-Path $dir $Name)
  if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

Save-Output "00-context.txt" { kubectl config current-context; kubectl version; kubectl get namespace $namespace -o yaml }
Save-Output "01-argo.txt" {
  kubectl -n argocd get application root cluster-namespaces cluster-policies policy-test -o custom-columns='NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status,REVISION:.status.sync.revision,PATH:.spec.source.path,PRUNE:.spec.syncPolicy.automated.prune'
}
Save-Output "02-running.txt" {
  kubectl -n $namespace wait --for=condition=Available deployment/policy-test-echo --timeout=180s
  kubectl -n $namespace get deployment,service,endpointslice -o wide
  kubectl -n $namespace get endpointslice -l kubernetes.io/service-name=policy-test-echo -o jsonpath='{range .items[*].endpoints[*]}{.conditions.ready}{" "}{.addresses}{"\n"}{end}'
}

$badRole = @'
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: rejected-wildcard
  namespace: veridex-policy-test
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
'@
$badBinding = @'
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: rejected-cluster-admin
  namespace: veridex-policy-test
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
- kind: ServiceAccount
  name: policy-test
  namespace: veridex-policy-test
'@
$badPod = @'
apiVersion: v1
kind: Pod
metadata:
  name: rejected-privileged
  namespace: veridex-policy-test
spec:
  containers:
  - name: test
    image: busybox:1.37.0@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0
    securityContext:
      privileged: true
'@
$quotaPod = @'
apiVersion: v1
kind: Pod
metadata:
  name: rejected-quota
  namespace: veridex-policy-test
spec:
  restartPolicy: Never
  containers:
  - name: test
    image: busybox:1.37.0@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0
    command: ["true"]
    resources:
      requests: {cpu: "2", memory: 16Mi}
      limits: {cpu: "2", memory: 16Mi}
    securityContext:
      allowPrivilegeEscalation: false
      capabilities: {drop: ["ALL"]}
      runAsNonRoot: true
      runAsUser: 65532
      seccompProfile: {type: RuntimeDefault}
'@

function Expect-Rejected([string]$Name, [string]$Manifest, [string]$Pattern) {
  $output = $Manifest | kubectl apply --dry-run=server -f - 2>&1 | Out-String
  $output | Set-Content -LiteralPath (Join-Path $dir $Name)
  if ($LASTEXITCODE -eq 0 -or $output -notmatch $Pattern) { throw "$Name was not rejected for expected reason: $Pattern" }
}
Expect-Rejected "10-wildcard-role.txt" $badRole "veridex-deny-wildcard-roles|Wildcards are forbidden"
Expect-Rejected "11-cluster-admin-binding.txt" $badBinding "veridex-deny-privileged-rolebindings|unapproved ClusterRoles"
Expect-Rejected "12-pod-security.txt" $badPod "PodSecurity|restricted|privileged"
Expect-Rejected "13-quota.txt" $quotaPod "exceeded quota"

for ($run = 1; $run -le $Runs; $run++) {
  $runId = "$stamp-$run"
  Save-Output ("20-run-{0}.txt" -f $run) {
    kubectl -n $namespace create job "allowed-$runId" --from=cronjob/policy-test-allowed
    kubectl -n $namespace create job "denied-$runId" --from=cronjob/policy-test-denied
    kubectl -n $namespace label job "allowed-$runId" "veridex.io/policy-test-run=$runId"
    kubectl -n $namespace label job "denied-$runId" "veridex.io/policy-test-run=$runId"
    kubectl -n $namespace wait --for=condition=Complete job/"allowed-$runId" job/"denied-$runId" --timeout=180s
    kubectl -n $namespace logs job/"allowed-$runId"
    kubectl -n $namespace logs job/"denied-$runId"
  }
  $ciliumPod = kubectl -n kube-system get pod -l k8s-app=cilium -o jsonpath='{.items[0].metadata.name}'
  Save-Output ("21-hubble-{0}.json" -f $run) {
    kubectl -n kube-system exec $ciliumPod -- hubble observe --since 10m --namespace $namespace --output json
  }
  kubectl -n $namespace delete job -l "veridex.io/policy-test-run=$runId" --wait=true | Out-File (Join-Path $dir ("22-cleanup-{0}.txt" -f $run))
  $residue = kubectl -n $namespace get job,pod -l "veridex.io/policy-test-run=$runId" -o name
  if ($residue) { throw "Cleanup residue remains for $runId`: $residue" }
}

$uidAfter = kubectl get namespace $namespace -o jsonpath='{.metadata.uid}'
if ($uidBefore -ne $uidAfter) { throw "Namespace UID changed during verification." }
kubectl -n $namespace get resourcequota,limitrange,serviceaccount,networkpolicy -o yaml | Set-Content -LiteralPath (Join-Path $dir "30-baseline-after.yaml")
Get-FileHash -Algorithm SHA256 (Join-Path $dir "*") | Format-Table -AutoSize | Out-File (Join-Path $dir "SHA256SUMS.txt")
Write-Host "VERIFIED evidence retained at $dir"
