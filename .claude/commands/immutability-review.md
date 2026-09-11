# immutability-review

Verify infrastructure follows immutable patterns — no mutable in-place changes, configs tracked in git.

## 1. No Manual kubectl edits (config drift)
```
kubectl get configmap -A -o json | \
  jq '.items[] | select(.metadata.annotations["kubectl.kubernetes.io/last-applied-configuration"] == null and .metadata.annotations["argocd.argoproj.io/managed-by"] == null) | {ns: .metadata.namespace, name: .metadata.name}'
```
Flag: ConfigMaps not tracked by ArgoCD or last-applied annotation — may have been edited manually.

## 2. All Images Pinned (not :latest)
```
kubectl get pods -A -o json | \
  jq '.items[] | .spec.containers[] | select(.image | test(":latest$|@sha256" | not) | not) | select(.image | test(":latest$")) | {image: .image}' | sort -u
```
Pass: No `:latest` tags in any pod. All images pinned to exact version or digest.

## 3. ArgoCD Self-Heal Enabled
```
kubectl get application -n argocd -o json | \
  jq '.items[] | select(.spec.syncPolicy.automated.selfHeal != true) | {name: .metadata.name}'
```
Pass: All apps have `selfHeal: true`. Manual changes to live cluster get reverted.

## 4. No kubectl exec history in config
```
grep -rn 'kubectl exec\|kubectl edit\|kubectl patch' ansible/ --include='*.yml' --include='*.sh' | \
  grep -v '#\|dry-run\|description'
```
Review: `kubectl edit` in automation breaks immutability. Prefer declarative patches.

## 5. Traefik Manifests Raw (not Helm)
Confirmed: Traefik deployed via `kubectl apply` raw manifests (not Helm) per recent refactor.
```
kubectl get deployment -n kube-system traefik -o jsonpath='{.metadata.annotations.meta\.helm\.sh/release-name}' 2>/dev/null
```
Pass: No Helm annotation — confirms raw manifest deployment.

## 6. Immutable ConfigMaps / Secrets
```
kubectl get configmap -n data-plane -o json | \
  jq '.items[] | {name: .metadata.name, immutable: .immutable}'
```
Good practice: Mark stable ConfigMaps as `immutable: true` to prevent accidental in-place edits.

## 7. PVC Reclaim Policy
```
kubectl get pvc -A -o json | \
  jq '.items[] | {ns: .metadata.namespace, pvc: .metadata.name, reclaim: .spec.storageClassName}'
kubectl get storageclass -o json | jq '.items[] | {name: .metadata.name, reclaim: .reclaimPolicy}'
```
Verify: hcloud-volumes reclaim policy is `Retain` (not `Delete`) for stateful data (CNPG, MinIO).

## Report
Manual drift ConfigMaps, :latest images, apps without selfHeal, Retain vs Delete PVCs.
