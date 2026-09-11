# ingestion-api-health

Health check for the ingestion-api service and its end-to-end pipeline.

## 1. Pod Status (KEDA managed)
```
kubectl get pods -n data-plane -l app=ingestion-api -o wide
kubectl get hpa -n data-plane -o json | \
  jq '.items[] | select(.metadata.name | test("ingestion")) | {current: .status.currentReplicas, desired: .status.desiredReplicas}'
```
Pass: 0 replicas at idle (off-hours), scaling when NATS lag > 30 or cron window active.

## 2. ScaledObject Triggers Active
```
kubectl get scaledobject -n data-plane ingestion-api-scaler -o json | jq '.status'
```
Check: `conditions[].type=Active` shows which trigger is driving scale.

## 3. Readiness / Liveness
```
kubectl describe pods -n data-plane -l app=ingestion-api | grep -A5 'Readiness\|Liveness\|Last State'
```
Pass: Readiness probe passing. No recent liveness probe failures.

## 4. End-to-End Test (manual trigger)
Publish a test message to NATS ingestion_events:
```
kubectl exec -n data-plane -l app=dip-nats -- \
  nats pub ingestion_events '{"document_id": "test-001", "type": "test", "source": "health-check"}' 2>/dev/null
```
Verify: KEDA scales ingestion-api from 0 → 1, Temporal workflow starts, message processed, consumer lag drops back to 0.

## 5. API Endpoint Health (if port-forward available)
```
kubectl port-forward -n data-plane svc/ingestion-api 8080:8080 &
sleep 2
curl -s http://localhost:8080/health | python3 -m json.tool
curl -s http://localhost:8080/metrics | grep -E 'ingestion|documents|queue'
```

## 6. Ingestion Throughput Metrics
```
kubectl port-forward -n observability svc/victoriametrics 8428:8428 &
curl -s 'http://localhost:8428/api/v1/query?query=rate(ingestion_documents_total[5m])' | \
  python3 -m json.tool | grep value
```
Baseline: Expected throughput depends on cron window and document load.

## 7. Error Rate
```
kubectl logs -n data-plane -l app=ingestion-api --since=1h --tail=200 | \
  grep -E 'error|ERROR|failed|panic' | head -20
```
Pass: No persistent errors. Transient retry errors OK if recovering.

## 8. NATS Connection Health
```
kubectl logs -n data-plane -l app=ingestion-api --since=5m --tail=50 | \
  grep -E 'nats|jetstream|disconnect|reconnect'
```
Pass: No NATS disconnects. JetStream consumer active.

## Report
Current replica count, KEDA trigger state, end-to-end test result, throughput/error rate, NATS connection.
