# argocd-app-health

Deep health inspection of ArgoCD application resources.

## 1. All Applications Summary
```
kubectl get application -n argocd -o json | \
  jq '.items[] | {name: .metadata.name, health: .status.health.status, sync: .status.sync.status, wave: (.metadata.annotations["argocd.argoproj.io/sync-wave"] // "0")} | select(.health != "Healthy" or .sync != "Synced")'
```
Pass: No output = all apps Healthy and Synced.

## 2. Degraded App Drill-Down
```
kubectl get application -n argocd -o json | \
  jq '.items[] | select(.status.health.status == "Degraded") | {name: .metadata.name, message: .status.conditions[]?.message, resources: [.status.resources[] | select(.health.status == "Degraded") | {kind: .kind, name: .name, message: .health.message}]}'
```

## 3. OutOfSync Resources
```
kubectl get application -n argocd -o json | \
  jq '.items[] | select(.status.sync.status == "OutOfSync") | {name: .metadata.name, outOfSync: [.status.resources[] | select(.status == "OutOfSync") | {kind: .kind, name: .name, namespace: .namespace}]}'
```

## 4. Sync-Wave Order Verification
```
kubectl get application -n argocd -o json | \
  jq '[.items[] | {name: .metadata.name, wave: (.metadata.annotations["argocd.argoproj.io/sync-wave"] // "0" | tonumber)}] | sort_by(.wave)'
```
Verify order (lower wave syncs first):
- Wave 0: cert-manager, kube-vip, CRDs
- Wave 1: Cilium, ArgoCD self
- Wave 2: CNPG, MinIO, NATS
- Wave 3: Temporal, Redis, Traefik
- Wave 4: DIP applications, ingestion-api

## 5. Last Sync Time
```
kubectl get application -n argocd -o json | \
  jq '.items[] | {name: .metadata.name, lastSync: .status.operationState.finishedAt}' | \
  python3 -c "
import sys, json
from datetime import datetime, timezone
for line in sys.stdin:
    if not line.strip(): continue
    try:
        d = json.loads(line)
        ts = d.get('lastSync', '')
        if ts:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts.replace('Z','+00:00'))).total_seconds() / 3600
            flag = 'STALE' if age > 2 else 'OK'
            print(f\"{flag:6} {d['name']}: {age:.1f}h ago\")
    except: pass
"
```
Pass: All synced within last 2 hours (selfHeal=true means continuous reconciliation).

## 6. Pending Operations
```
kubectl get application -n argocd -o json | \
  jq '.items[] | select(.status.operationState.phase == "Running") | {name: .metadata.name, phase: .status.operationState.phase, message: .status.operationState.message}'
```
Pass: No apps stuck in Running sync operation > 5 minutes.

## 7. Resource Health Summary
```
kubectl get application -n argocd -o json | \
  jq '[.items[].status.resources[] | .health.status] | group_by(.) | map({status: .[0], count: length})'
```

## Report
Degraded apps list, OutOfSync resources, sync-wave order, last sync age, pending operations.
