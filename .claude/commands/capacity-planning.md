# capacity-planning

Assess resource utilization and capacity headroom for the Veridex netcup cluster.

## 1. Node Resource Utilization
```
kubectl top nodes 2>/dev/null
kubectl describe nodes | grep -A5 'Allocated resources'
```
Target: CPU < 70%, Memory < 80% per node.

## 2. Per-Namespace Resource Usage
```
kubectl top pods -A --sort-by=cpu 2>/dev/null | head -20
kubectl top pods -A --sort-by=memory 2>/dev/null | head -20
```
Identify: Top consumers. Any pods near their limits?

## 3. Resource Requests vs Limits
```
kubectl get pods -n data-plane -o json | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
for pod in data['items']:
    for c in pod['spec']['containers']:
        req = c.get('resources', {}).get('requests', {})
        lim = c.get('resources', {}).get('limits', {})
        print(f\"{pod['metadata']['name']}/{c['name']}: req={req} lim={lim}\")
"
```

## 4. PVC Utilization
```
kubectl get pvc -A -o wide
kubectl exec -n data-plane deployment/dip-minio -- df -h /data 2>/dev/null
kubectl exec -n data-plane -l cnpg.io/cluster -- df -h /var/lib/postgresql 2>/dev/null
```
Alert: MinIO 30Gi PVC > 80% used = 24Gi. CNPG PVC > 80%.

## 5. CNPG Connection Pool
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```
Capacity: max_connections configured × 0.8 = safe maximum.

## 6. NATS Storage
```
kubectl exec -n data-plane -l app=dip-nats -- \
  nats server info --json 2>/dev/null | python3 -m json.tool | grep -E 'store_dir|total_bytes|file_count'
```
Alert: JetStream storage > 80% = scale needed.

## 7. Temporal Workflow Backlog
```
kubectl exec -n data-plane deployment/temporal-frontend -- \
  tctl --ns default wf list --query 'ExecutionStatus="Running"' --limit 100 2>/dev/null | wc -l
```
Alert: > 500 running workflows = KEDA may need adjustment.

## 8. Growth Projection (30-day)
Using VictoriaMetrics:
```
kubectl port-forward -n observability svc/victoriametrics 8428:8428 &
curl -s 'http://localhost:8428/api/v1/query?query=predict_linear(container_memory_working_set_bytes{namespace="data-plane"}[7d],30*24*3600)' | \
  python3 -m json.tool | head -20
```

## Report
CPU/memory headroom per node, PVC utilization (MinIO/CNPG), connection pool usage, projected capacity exhaustion date.
