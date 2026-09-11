# victoriametrics-health

Check VictoriaMetrics single-node health and scrape coverage.

## 1. Pod Status
```
kubectl get pods -n observability -l app=victoriametrics 2>/dev/null || \
  kubectl get pods -A | grep victoria
```
Pass: VictoriaMetrics pod Running. No OOMKilled restarts.

## 2. API Health
```
kubectl port-forward -n observability svc/victoriametrics 8428:8428 &
sleep 2
curl -s http://localhost:8428/health | python3 -m json.tool
curl -s http://localhost:8428/api/v1/status/tsdb | python3 -m json.tool | head -30
```
Pass: `{ "status": "ok" }` from /health.

## 3. Active Targets (scrape health)
```
curl -s 'http://localhost:8428/api/v1/targets' | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
active = data.get('data', {}).get('activeTargets', [])
up = sum(1 for t in active if t.get('health') == 'up')
down = [t['labels'].get('job','?') for t in active if t.get('health') != 'up']
print(f'Total: {len(active)}, Up: {up}, Down: {len(down)}')
if down: print('DOWN:', down)
"
```
Pass: All targets `up`. Any `down` targets need investigation.

## 4. KEDA ScaledObject Metrics Available
```
curl -s 'http://localhost:8428/api/v1/query?query=kube_pod_info{namespace="data-plane"}' | \
  python3 -m json.tool | head -20
```
Pass: Returns results — VictoriaMetrics serving the KEDA Prometheus trigger.

## 5. Retention and Storage
```
curl -s 'http://localhost:8428/api/v1/status/tsdb?topN=10' | \
  python3 -m json.tool | grep -E 'seriesCount|totalSeries|storageDataPath'
kubectl get pvc -A | grep victoria
```
Check: PVC utilization, series count within capacity.

## 6. Ingestion Rate
```
curl -s 'http://localhost:8428/metrics' | grep -E 'vm_rows_inserted|vm_http_request_duration'
```
Pass: `vm_rows_inserted_total` incrementing = data flowing from Prometheus scrapes.

## 7. Critical Metric Presence
```
# Verify CNPG metrics
curl -s 'http://localhost:8428/api/v1/query?query=cnpg_collector_up' | python3 -m json.tool | head -10
# Verify NATS metrics
curl -s 'http://localhost:8428/api/v1/query?query=nats_consumer_num_pending' | python3 -m json.tool | head -10
# Verify Traefik metrics
curl -s 'http://localhost:8428/api/v1/query?query=traefik_router_requests_total' | python3 -m json.tool | head -10
```

## Report
Target health (up/down count), series count, PVC utilization, KEDA metric availability, critical metric presence.
