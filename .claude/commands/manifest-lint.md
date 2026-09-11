# manifest-lint

Lint all YAML manifests in gitops/ before committing. Run before any git push.

## 1. YAML Syntax Validation
```
find gitops/ -name '*.yaml' -o -name '*.yml' | xargs -I{} python3 -c "import yaml,sys; yaml.safe_load_all(open('{}'))" 2>&1 | grep -v '^$'
```
Or with yamllint if available:
```
yamllint -d relaxed gitops/ 2>&1 | grep -E 'error|warning' | head -30
```
Pass: No parse errors.

## 2. Kubernetes Schema Validation
```
find gitops/ -name '*.yaml' | xargs kubeval --ignore-missing-schemas 2>&1 | grep -v 'PASS\|skipping' | head -30
```
Or with kubeconform:
```
find gitops/ -name '*.yaml' | xargs kubeconform -ignore-missing-schemas -summary 2>&1
```
Pass: No schema violations.

## 3. ArgoCD-Specific Checks
```
grep -rn 'selfHeal: false' gitops/ --include='*.yaml'
grep -rn 'prune: true' gitops/ --include='*.yaml' | grep -E 'cnpg|minio|temporal|redis|nats'
```
Pass: No selfHeal:false. No prune:true on stateful workloads.

## 4. Duplicate Resource Names
```
grep -rn '^  name:' gitops/ --include='*.yaml' | awk -F: '{print $NF}' | sort | uniq -d
```
Review: Duplicate names are only a problem within the same namespace/kind.

## 5. SealedSecret Encryption Check
```
grep -rn 'encryptedData:' gitops/ --include='*.yaml' -l
grep -rn 'stringData:\|data:' gitops/secrets/ --include='*.yaml'
```
Pass: All secrets in gitops/secrets/ are SealedSecrets (no plaintext stringData).

## 6. Missing Finalizers on ArgoCD Apps
```
grep -rn 'finalizers' gitops/bootstrap/ --include='*.yaml' -l
grep -L 'finalizers' gitops/bootstrap/*.yaml gitops/apps/**/*.yaml 2>/dev/null
```
Pass: All ArgoCD Application manifests have `resources-finalizer.argocd.argoproj.io`.

## 7. Kustomize Build Test
```
kubectl kustomize gitops/infra --dry-run 2>&1 | grep -E 'error|Error' | head -10
kubectl kustomize gitops/apps --dry-run 2>&1 | grep -E 'error|Error' | head -10
```
Pass: No kustomize build errors.

## Report
Error count per check. Block commit on any error in checks 1, 2, 5.
