# gitops-compliance-review

Review GitOps manifests in gitops/ for compliance with platform standards.

## 1. No Hardcoded IPs or Secrets
```
grep -rn '\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b' gitops/ --include='*.yaml' | grep -v '#\|clusterIP\|127.0.0.1\|0.0.0.0\|10.43\|10.1'
grep -rn 'password\|secret\|token\|key' gitops/ --include='*.yaml' | grep -v 'secretRef\|secretName\|ENC\[\|ExternalSecret\|kind: Secret'
```
Pass: No plaintext credentials or hardcoded LB IPs in manifests.

## 2. Image Tag Pinning (no 'latest')
```
grep -rn 'image:.*:latest' gitops/ --include='*.yaml'
grep -rn "image:.*[^']$" gitops/ --include='*.yaml' | grep -v '#\|digest\|sha256' | grep -v ':[0-9]'
```
Pass: No `:latest` tags. All images pinned to specific version.

## 3. Resource Limits Set
```
kubectl get pods -n data-plane -o json | jq '.items[] | select(.spec.containers[].resources.limits == null) | .metadata.name'
kubectl get pods -n argocd -o json | jq '.items[] | select(.spec.containers[].resources.limits == null) | .metadata.name'
```
Pass: No pods without resource limits.

## 4. Health Probes Defined
```
kubectl get deployments -n data-plane -o json | \
  jq '.items[] | select(.spec.template.spec.containers[].livenessProbe == null) | .metadata.name'
```
Pass: All Deployments in data-plane have liveness + readiness probes.

## 5. Kustomize Overlay Consistency
Check scale overlays match base:
```
diff <(kubectl kustomize gitops/overlays/scale-small 2>/dev/null) <(kubectl kustomize gitops/overlays/scale-medium 2>/dev/null) | grep -E '^[<>]' | head -20
```

## 6. ArgoCD App Source Points to Main
```
kubectl get applications -n argocd -o json | \
  jq '.items[] | select(.spec.source.targetRevision != "HEAD" and .spec.source.targetRevision != "main") | {name: .metadata.name, revision: .spec.source.targetRevision}'
```
Pass: All apps target `HEAD` or `main`. No feature branches in production.

## 7. Namespace Ownership (single owner rule)
From memory: no namespace should have multiple ArgoCD apps creating it.
```
kubectl get applications -n argocd -o json | \
  jq -r '.items[].spec.destination.namespace' | sort | uniq -d
```
Pass: No duplicate destination namespaces owned by multiple apps.

## Report
Credential scan results, pinned image count, resource limit coverage, probe coverage, overlay drift.
