# kustomize-overlay-review

Validate kustomize overlays for correctness and environment consistency.

## 1. Kustomize Build (dry-run all overlays)
```
find gitops/ -name 'kustomization.yaml' -o -name 'kustomization.yml' | while read f; do
  dir=$(dirname "$f")
  echo "=== $dir ==="
  kubectl kustomize "$dir" 2>&1 | grep -E 'error|Error|FATAL' || echo "OK"
done
```
Pass: All kustomize build commands succeed. No YAML errors.

## 2. Overlay Structure Audit
```
find gitops/ -type d | head -30
ls -la gitops/infra/ gitops/apps/ 2>/dev/null
```
Verify: Base + overlay pattern present. Overlays only patch (not duplicate) base resources.

## 3. Image Overrides in Overlays
```
grep -rn 'newTag:\|newName:' gitops/ --include='kustomization.yaml' --include='kustomization.yml'
```
Verify: Image tags pinned in overlays. No `latest` tags.

## 4. Patch Coverage (no orphaned patches)
```
grep -rn 'patchesStrategicMerge\|patches:\|patchesJSON6902' gitops/ --include='kustomization.yaml' | head -20
```
For each patch, verify the target resource exists:
```
grep -rn 'path:' gitops/ --include='kustomization.yaml' | awk -F': ' '{print $2}' | while read p; do
  [ -f "$p" ] && echo "OK: $p" || echo "MISSING: $p"
done
```

## 5. Namespace Consistency
```
kubectl kustomize gitops/infra/ 2>/dev/null | grep 'namespace:' | sort -u
```
Verify: Each resource has correct namespace. No cross-namespace patches violating ArgoCD ownership rules.

## 6. ArgoCD App Source Matches
```
kubectl get application -n argocd -o json | \
  jq '.items[] | select(.spec.source.kustomize != null) | {name: .metadata.name, path: .spec.source.path, kustomize: .spec.source.kustomize}'
```
Verify: ArgoCD apps with kustomize source use correct overlay path.

## 7. Common Base Resources Check
```
find gitops/ -name 'kustomization.yaml' | xargs grep -l 'resources:' | while read f; do
  echo "=== $f ==="
  grep -A10 'resources:' "$f" | head -10
done | head -60
```
Verify: No raw YAML files duplicated across overlays (should be resources: ../../base/ pattern).

## Report
Build errors, orphaned patches, image tag violations, namespace inconsistencies, ArgoCD source alignment.
