# incident-triage

Rapid incident triage playbook for K3s-HA cluster issues.

## Step 1: Scope Assessment (< 2 min)
```
kubectl get nodes
kubectl get pods -A --field-selector=status.phase!=Running | grep -v Completed
kubectl get events -A --sort-by='.lastTimestamp' | tail -30
```
Output: Node count, unhealthy pod list, recent events. Determines blast radius.

## Step 2: Control Plane Health
```
kubectl get pods -n kube-system | grep -E 'kube-system|cilium|kube-vip|traefik'
kubectl get application -n argocd -o wide | grep -v Synced
```
Pass: Control plane healthy. ArgoCD apps Synced.

## Step 3: Data-Plane Triage
```
kubectl get pods -n data-plane
kubectl get pods -n docintel
kubectl describe pods -n data-plane | grep -A5 'Reason\|Warning\|Error\|Exit Code'
```

## Step 4: Recent Logs (last 5 min)
```
kubectl logs -n data-plane -l app=dip-postgres --since=5m --tail=100 | grep -E 'FATAL|ERROR|panic'
kubectl logs -n data-plane -l app=dip-nats --since=5m --tail=50 | grep -E 'error|failed'
kubectl logs -n kube-system -l app=traefik --since=5m --tail=50 | grep -E 'error|5[0-9][0-9]'
```

## Step 5: Resource Pressure
```
kubectl top nodes 2>/dev/null
kubectl top pods -A --sort-by=memory 2>/dev/null | head -15
kubectl get events -A --sort-by='.lastTimestamp' | grep -E 'OOMKill|MemoryPressure|DiskPressure'
```

## Step 6: Network / Cilium
```
kubectl exec -n kube-system -l k8s-app=cilium -- cilium status --brief 2>/dev/null | head -10
kubectl get ciliumendpoints -A | grep -v 'ready'
```

## Step 7: Storage
```
kubectl get pvc -A | grep -v Bound
kubectl get events -A | grep -E 'FailedMount|volume|pvc'
```

## Step 8: ArgoCD Sync State
```
kubectl get application -n argocd -o json | \
  jq '.items[] | select(.status.health.status != "Healthy" or .status.sync.status != "Synced") | {name: .metadata.name, health: .status.health.status, sync: .status.sync.status, message: .status.conditions[]?.message}'
```

## Escalation Thresholds
- **P1 (page now)**: All control-plane nodes down, etcd quorum lost, ingress completely down
- **P2 (urgent)**: Single node down, data-plane pod CrashLoop > 5 min, cert expired
- **P3 (business hours)**: KEDA not scaling, single PVC warning, Kyverno audit failures

## Runbooks
- Node down: run `/node-health` → drain + cordon → check kube-vip VIP
- CNPG issue: run `/cnpg-cluster-health` → check WAL archive → failover if primary dead
- Traefik 502: run `/traefik-health` → check ForwardAuth → check backend pod
- NATS lag: run `/nats-health` → check KEDA `/keda-scaler-review` → manual scale
