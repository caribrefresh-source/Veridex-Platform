# temporal-worker-health

Validate Temporal workflow engine and worker health for the DIP platform.

## 1. Temporal Pods
```
kubectl get pods -n data-plane -l app.kubernetes.io/name=temporal -o wide
kubectl get pods -n data-plane | grep temporal
```
Pass: Temporal frontend, history, matching, worker services all Running.

## 2. Temporal Frontend Reachability
```
kubectl exec -n data-plane -l app=temporal-frontend -- \
  temporal operator cluster health 2>/dev/null || \
kubectl run temporal-check --rm -it --restart=Never --image=temporalio/admin-tools -- \
  temporal operator cluster health --address temporal-frontend.data-plane.svc:7233
```
Pass: Cluster health returns `SERVING`.

## 3. Worker Registration Check
```
kubectl run temporal-check --rm -it --restart=Never --image=temporalio/admin-tools --namespace=data-plane -- \
  temporal task-queue describe --task-queue ingestion-queue --namespace default --address temporal-frontend.data-plane.svc:7233 2>/dev/null | \
  grep -E 'worker|pollers|taskQueue'
```
Pass: At least one poller registered on `ingestion-queue`.

## 4. Running Workflows
```
kubectl run temporal-check --rm -it --restart=Never --image=temporalio/admin-tools --namespace=data-plane -- \
  temporal workflow list --namespace default --address temporal-frontend.data-plane.svc:7233 --limit 20 2>/dev/null
```
Review: Count of Running, TimedOut, Failed workflows.

## 5. Stuck Workflows (running > 1 hour)
```
kubectl run temporal-check --rm -it --restart=Never --image=temporalio/admin-tools --namespace=data-plane -- \
  temporal workflow list --namespace default --status RUNNING --address temporal-frontend.data-plane.svc:7233 2>/dev/null | \
  awk '$0 ~ /[0-9]+h/ {print}'
```
Flag: Any workflow running > 1h with no recent progress needs investigation.

## 6. Recent Failed Workflows
```
kubectl run temporal-check --rm -it --restart=Never --image=temporalio/admin-tools --namespace=data-plane -- \
  temporal workflow list --namespace default --status FAILED --limit 10 --address temporal-frontend.data-plane.svc:7233 2>/dev/null
```
Review: Failure patterns — same workflow type failing repeatedly indicates code bug.

## 7. Temporal DB (PostgreSQL backend)
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "\l" | grep -i temporal
```
Pass: Temporal databases (`temporal`, `temporal_visibility`) exist and accessible.

## Report
Service pod status, cluster health, worker pollers, running/stuck/failed workflow counts.
