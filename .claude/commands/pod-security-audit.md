# pod-security-audit

Audit pod security contexts across the K3s-HA cluster.

## 1. Privileged Containers
```
kubectl get pods -A -o json | \
  jq '.items[] | select(.spec.containers[].securityContext.privileged == true) | {ns: .metadata.namespace, pod: .metadata.name, containers: [.spec.containers[] | select(.securityContext.privileged == true) | .name]}'
```
Pass: Only system pods in kube-system/cilium have privileged containers. None in data-plane or docintel.

## 2. Running as Root
```
kubectl get pods -A -o json | \
  jq '.items[] | select(.spec.securityContext.runAsUser == 0 or (.spec.containers[].securityContext.runAsUser == 0)) | {ns: .metadata.namespace, pod: .metadata.name}' | \
  jq 'select(.ns | test("data-plane|docintel|argocd"))'
```
Pass: No application pods (data-plane, docintel) running as root (UID 0).

## 3. ReadOnly Root Filesystem
```
kubectl get pods -n data-plane -o json | \
  jq '.items[] | select(.spec.containers[].securityContext.readOnlyRootFilesystem != true) | {pod: .metadata.name, containers: [.spec.containers[] | select(.securityContext.readOnlyRootFilesystem != true) | .name]}'
```
Review: Non-readonly filesystems should have justification (MinIO needs write access — known exception).

## 4. Capability Drops
```
kubectl get pods -n data-plane -o json | \
  jq '.items[] | {pod: .metadata.name, caps: [.spec.containers[].securityContext.capabilities]}'
```
Pass: All containers drop ALL capabilities. No `NET_RAW`, `SYS_ADMIN` added unnecessarily.

## 5. Pod Security Admission Labels
```
kubectl get ns data-plane docintel argocd -o json | \
  jq '.items[] | {ns: .metadata.name, enforce: .metadata.labels["pod-security.kubernetes.io/enforce"], warn: .metadata.labels["pod-security.kubernetes.io/warn"]}'
```
Pass: Namespaces have PSA labels. `data-plane` and `docintel` should be `restricted` or `baseline`.

## 6. Kyverno PolicyReport
```
kubectl get policyreport -A -o json | \
  jq '.items[] | select(.summary.fail > 0) | {ns: .metadata.namespace, fail: .summary.fail, results: [.results[] | select(.result == "fail") | {policy: .policy, message: .message}]}'
```
Pass: Zero failures in data-plane and docintel.

## 7. HostPath Mounts
```
kubectl get pods -A -o json | \
  jq '.items[] | select(.spec.volumes[]?.hostPath != null) | {ns: .metadata.namespace, pod: .metadata.name, paths: [.spec.volumes[].hostPath.path // empty]}'
```
Pass: Only kube-system pods mount host paths. No application pods.

## 8. ServiceAccount Token Automounting
```
kubectl get pods -n data-plane -o json | \
  jq '.items[] | select(.spec.automountServiceAccountToken != false) | .metadata.name'
```
Review: Pods that don't need API access should have `automountServiceAccountToken: false`.

## Report
Privileged container count, root pod count, PSA label coverage, Kyverno fail count, hostPath list.
