# argocd-sync-validation

Validate ArgoCD GitOps state for the caribrefresh-source/k3s-ha repository.

## 1. All Applications Health
```
kubectl get applications -n argocd -o custom-columns='NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status,REVISION:.status.sync.revision'
```
Pass: Every app `Synced` + `Healthy`. Fail on: `OutOfSync`, `Degraded`, `Unknown`, `Missing`.

## 2. Sync Wave Order Integrity
Check wave annotations are correct:
- Wave -1: network-policies
- Wave 0: namespace/RBAC
- Wave 1: CNPG operator, storage
- Wave 2: MinIO, databases
- Wave 3: Redis, NATS
- Wave 5: Temporal, application services
```
kubectl get applications -n argocd -o json | jq '.items[] | {name: .metadata.name, wave: .metadata.annotations["argocd.argoproj.io/sync-wave"]}'
```

## 3. Degraded Resource Drill-Down
For any Degraded app, get resource tree:
```
kubectl get application <app-name> -n argocd -o json | jq '.status.resources[] | select(.health.status != "Healthy")'
```

## 4. prune:false on Stateful Apps
```
kubectl get applications -n argocd -o json | \
  jq '.items[] | select(.metadata.name | test("cnpg|minio|temporal|nats|redis")) | {name: .metadata.name, prune: .spec.syncPolicy.automated.prune}'
```
Pass: All stateful apps have `prune: false`. Prune:true on stateful data is destructive.

## 5. selfHeal Enabled
```
kubectl get applications -n argocd -o json | \
  jq '.items[] | select(.spec.syncPolicy.automated.selfHeal != true) | .metadata.name'
```
Pass: No output (all apps have selfHeal:true).

## 6. ServerSideApply Enabled
```
kubectl get applications -n argocd -o json | \
  jq '.items[] | {name: .metadata.name, ssa: [.spec.syncPolicy.syncOptions[] | select(. == "ServerSideApply=true")] | length}'
```
Pass: All apps have ServerSideApply=true in syncOptions.

## 7. Pending Operations
```
kubectl get applications -n argocd -o json | jq '.items[] | select(.status.operationState.phase == "Running") | .metadata.name'
```
Pass: No output (no active sync operations competing).

## 8. Last Sync Freshness
```
kubectl get applications -n argocd -o json | \
  jq '.items[] | {name: .metadata.name, lastSync: .status.operationState.finishedAt}'
```
Review: Any app not synced in > 24h while main branch has had commits.

## Report
App status table, wave order verification, prune safety, any degraded resource drill-down.
