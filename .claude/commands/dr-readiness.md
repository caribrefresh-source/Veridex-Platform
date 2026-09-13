# dr-readiness

Disaster recovery readiness assessment for K3s-HA cluster.

## 1. Multi-Node Control Plane (HA)
```
kubectl get nodes -l node-role.kubernetes.io/control-plane -o wide
```
Pass: 3 server nodes Ready. Losing 1 node keeps quorum (2 of 3).

## 2. kube-vip VIP Health
```
VIP=$(awk -F'"' '/^kubevip_vip:/{print $2}' ansible/inventory/production/group_vars/all.yml)
ping -c 3 "$VIP" 2>/dev/null || curl -k "https://$VIP:6443/healthz"
```
Pass: VIP (`kubevip_vip` in ansible/inventory/production/group_vars/all.yml) reachable. Leader election active.
Run /kubevip-health for full VIP audit.

## 3. etcd Quorum & Backup
Run /etcd-health to confirm:
- 3-member cluster, all healthy
- DB size < 2GB (alert threshold)
- Snapshot < 24h old

## 4. CNPG Replication
```
kubectl get cluster -n data-plane -o json | \
  jq '.items[] | {name: .metadata.name, instances: .spec.instances, readyInstances: .status.readyInstances, primary: .status.currentPrimary}'
```
Pass: `readyInstances == instances`. Replica lag < 10s.
Failover command: `kubectl cnpg promote -n data-plane <cluster-name> <target-pod>`

## 5. Backup Freshness (RPO)
From /backup-validation:
- CNPG: WAL archive < 5 min old → RPO = 5 min
- Vaultwarden: daily backup → RPO = 24h

## 6. ArgoCD Recovery (GitOps)
```
kubectl get application -n argocd --no-headers | wc -l
```
If cluster is destroyed and rebuilt:
1. Re-run Ansible site.yml
2. ArgoCD bootstraps from gitops/ repo
3. All apps re-sync automatically
Estimated RTO: ~30-45 min for full cluster rebuild.

## 7. Secret Recovery Path
```
kubectl get sealedsecret -A --no-headers | wc -l
kubectl get externalsecret -A --no-headers | wc -l
```
Verify: SealedSecret private key backed up (in Vaultwarden or offline). ESO can re-sync from secret store.

## 8. Node Rebuild Playbook
```
cat ansible/playbooks/site.yml | grep -E '^  - ' | head -20
```
Verify: Full node rebuild is a single playbook run. All roles are idempotent.

## 9. DR Scenario Timelines
| Scenario | RPO | RTO |
|----------|-----|-----|
| Single node failure | 0 (HA) | 5-10 min auto-recover |
| Control-plane quorum loss | 0 (etcd snapshot) | 20-30 min |
| Full cluster loss | 5 min (WAL) | 45-60 min |
| Postgres data loss | 5 min (WAL) | 15-30 min PITR |
| Vaultwarden data loss | 24h (daily backup) | 5 min restore |

## Report
HA node count, VIP reachability, CNPG replica count, backup freshness, estimated RTO per scenario.
