# idempotency-review

Verify all Ansible playbooks and kubectl manifests are safe to re-run without side effects.

## 1. Ansible Idempotency Check
Run each playbook in check mode (dry run) — should report 0 changes if cluster is already configured:
```
for p in ansible/playbooks/prepare-hosts.yml ansible/playbooks/install-k3s-servers.yml ansible/playbooks/install-k3s-agents.yml ansible/playbooks/install-cilium.yml; do ansible-playbook -i ansible/inventory/production/hosts.yml "$p" --check --diff; done 2>&1 | \
  grep -E 'changed|failed|TASK' | tail -40
```
Pass: All tasks show `ok` (not `changed`). Zero `failed`. This is the gold standard.

## 2. kubectl Apply Idempotency
Re-applying all manifests should produce no changes:
```
kubectl apply -f gitops/ -R --dry-run=server 2>&1 | grep -v 'unchanged' | head -30
```
Pass: Output shows only `unchanged`. Any `configured` or `created` indicates drift.

## 3. Helm Idempotency (ArgoCD managed)
```
kubectl get application -n argocd -o json | \
  jq '.items[] | select(.status.sync.status == "OutOfSync") | .metadata.name'
```
Pass: No OutOfSync apps. All Helm releases match gitops state.

## 4. Phase Playbooks (check individually)
```
ansible-playbook -i ansible/inventory/production/hosts.yml ansible/playbooks/install-k3s-servers.yml --check --diff 2>&1 | \
  grep -E 'changed|failed' | wc -l
```
Pass: 0 changes when VIP already configured.

## 5. CRD Pre-Apply Idempotency
```
kubectl apply -f gitops/infra/cert-manager/crds/ --dry-run=server 2>&1 | grep -v unchanged
kubectl apply -f gitops/infra/cnpg/crds/ --dry-run=server 2>&1 | grep -v unchanged
```
Pass: CRDs show unchanged.

## 6. SealedSecret Re-Apply Safety
```
kubectl apply -f gitops/secrets/ --dry-run=server 2>&1 | head -20
```
Pass: SealedSecrets idempotent (same encrypted content re-applies without rotating the underlying secret).

## 7. CNPG Cluster Re-Apply
```
kubectl apply -f gitops/infra/cnpg/cluster.yaml --dry-run=server 2>&1
```
Pass: Shows `unchanged`. CNPG operator should not modify a healthy cluster on re-apply.

## 8. Script/Entrypoint Repeatability
Check any `run_log.txt` or CI scripts for non-idempotent patterns:
```
grep -rn 'create\|kubectl run\|helm install ' ansible/ gitops/ --include='*.yaml' --include='*.yml' --include='*.sh' | \
  grep -v 'apply\|--dry-run\|idempotent\|upgrade --install\|createOrUpdate\|#'
```
Flag: `kubectl run` or `helm install` (not `upgrade --install`) are not idempotent.

## Report
Ansible check-mode change count, kubectl drift count, OutOfSync apps, non-idempotent patterns found.
