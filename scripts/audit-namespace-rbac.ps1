[CmdletBinding()]
param([string]$OutputPath = "rbac-inventory.json")

$ErrorActionPreference = "Stop"
$namespaces = kubectl get namespace -l veridex.io/data-classification -o json | ConvertFrom-Json
$inventory = @()
$errors = @()
foreach ($item in $namespaces.items) {
  $name = $item.metadata.name
  $roles = kubectl -n $name get role -o json | ConvertFrom-Json
  $bindings = kubectl -n $name get rolebinding -o json | ConvertFrom-Json
  foreach ($role in $roles.items) {
    foreach ($rule in @($role.rules)) {
      if (@($rule.verbs) -contains "*" -or @($rule.apiGroups) -contains "*" -or @($rule.resources) -contains "*") {
        $errors += "$name/Role/$($role.metadata.name) contains a wildcard"
      }
    }
  }
  foreach ($binding in $bindings.items) {
    if ($binding.roleRef.kind -eq "ClusterRole" -and $binding.roleRef.name -ne "view") {
      $errors += "$name/RoleBinding/$($binding.metadata.name) references ClusterRole/$($binding.roleRef.name)"
    }
    foreach ($subject in @($binding.subjects)) {
      if ($subject.kind -eq "ServiceAccount" -and $subject.namespace -and $subject.namespace -ne $name) {
        $errors += "$name/RoleBinding/$($binding.metadata.name) has cross-namespace subject $($subject.namespace)/$($subject.name)"
      }
    }
  }
  $inventory += [ordered]@{ namespace = $name; roles = $roles.items; roleBindings = $bindings.items }
}
[ordered]@{
  capturedAt = (Get-Date).ToUniversalTime().ToString("o")
  context = kubectl config current-context
  inventory = $inventory
  errors = $errors
} | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputPath
if ($errors.Count) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }
Write-Host "RBAC inventory passed; evidence written to $OutputPath"
