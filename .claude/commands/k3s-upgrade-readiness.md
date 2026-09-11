# k3s-upgrade-readiness

Assess readiness to upgrade K3s (currently v1.35.4+k3s1) or any core cluster component.

## 1. Current Versions
```
kubectl get nodes -o custom-columns='NODE:.metadata.name,VERSION:.status.nodeInfo.kubeletVersion'
kubectl version --short 2>/dev/null || kubectl version
```

## 2. API Deprecation Scan
```
kubectl get --raw /apis | jq '.groups[].preferredVersion.version'
```
Check gitops/ manifests against removed APIs for target K3s version.
Key risk areas: `networking.k8s.io/v1beta1`, `policy/v1beta1` PodDisruptionBudget.

## 3. PodDisruptionBudget Coverage
```
kubectl get pdb -A
```
Pass: Every stateful workload (CNPG, MinIO, NATS, Temporal, Redis) has a PDB with minAvailable >= 1.

## 4. etcd Quorum Check
```
kubectl exec -n kube-system etcd-$(kubectl get nodes -l node-role.kubernetes.io/master= -o name | head -1 | cut -d/ -f2) -- etcdctl endpoint health --cluster 2>/dev/null || \
  kubectl exec -n kube-system -l component=etcd -- etcdctl endpoint health --cluster
```
Pass: All members healthy, quorum maintained (2/3 servers minimum).

## 5. Drain Simulation (dry-run)
```
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data --dry-run
```
Run for each server node. Pass: No eviction errors (PDBs satisfied, no non-evictable pods).

## 6. Cilium Compatibility
Check Cilium release notes for target K3s/kernel version compatibility.
Current Cilium: check `kubectl get daemonset -n kube-system cilium -o jsonpath='{.spec.template.spec.containers[0].image}'`

## 7. ArgoCD Application Freeze
Confirm no active sync-waves running:
```
kubectl get applications -n argocd -o jsonpath='{range .items[?(@.status.operationState.phase=="Running")]}{.metadata.name}{"\n"}{end}'
```
Pass: No output (no syncs in progress).

## 8. Backup Freshness
Confirm CNPG backup completed within last 6 hours before upgrade window.

## Upgrade Order
1. Drain + upgrade agent nodes one at a time
2. Drain + upgrade server nodes (maintain quorum: never drain 2 servers simultaneously)
3. Validate cluster-postflight after each node

## Report
Go / No-Go per check. Produce upgrade runbook with node order and rollback trigger.
