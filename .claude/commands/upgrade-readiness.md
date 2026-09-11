# upgrade-readiness

Pre-upgrade checklist for K3s, Cilium, ArgoCD, and application upgrades.

## 1. Current Version Inventory
```
kubectl get nodes -o wide | awk '{print $1,$5}'
kubectl exec -n kube-system -l k8s-app=cilium -- cilium version 2>/dev/null | head -3
kubectl get pods -n argocd -l app.kubernetes.io/name=argocd-server -o jsonpath='{.items[0].spec.containers[0].image}'
kubectl get deployment -n data-plane dip-postgres -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null
```

## 2. API Deprecations (before K3s upgrade)
```
kubectl api-versions | grep -E 'v1beta1|v1alpha1'
kubectl get all -A -o json | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data.get('items', []):
    av = item.get('apiVersion', '')
    if 'beta' in av or 'alpha' in av:
        print(av, item['kind'], item['metadata'].get('namespace',''), item['metadata']['name'])
" | sort -u
```
Pass: No resources on deprecated API versions that will be removed in target K3s version.

## 3. PDB Coverage
```
kubectl get poddisruptionbudget -A
kubectl get pods -A -o json | \
  jq '.items[] | select(.metadata.labels | has("app")) | .metadata.labels.app' | sort -u
```
Pass: All stateful applications have PDBs (minAvailable: 1).

## 4. Backup Freshness
Run /backup-validation — confirm CNPG backup < 30 min old before upgrade.

## 5. etcd Health
Run /etcd-health — confirm all 3 members healthy, no alarms, DB size < 1.5GB.

## 6. Drain Simulation
```
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data --dry-run 2>&1 | head -30
```
Run for each server node (one at a time). Pass = no blocking pods.

## 7. Cilium Upgrade Compatibility
Check: https://docs.cilium.io/en/stable/network/kubernetes/compatibility/
```
cilium-current-version=$(kubectl exec -n kube-system -l k8s-app=cilium -- cilium version 2>/dev/null | grep "Cilium client" | awk '{print $4}')
k3s-target-version=$(cat ansible/roles/base/defaults/main.yml | grep k3s_version | awk '{print $2}')
echo "Cilium: $cilium-current-version | K3s target: $k3s-target-version"
```

## 8. Upgrade Order (K3s HA)
1. Backup etcd snapshot manually
2. Upgrade first server node (primary)
3. Wait for control plane healthy (all 3 components)
4. Upgrade remaining server nodes (one at a time)
5. Upgrade agent/worker nodes (can parallel)
6. Run /cluster-postflight

## Report
Version matrix, deprecated API count, PDB gaps, backup age, etcd health, upgrade order confirmed.
