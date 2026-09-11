# keda-scaler-review

Validate KEDA autoscaling for the ingestion-api deployment in data-plane.

## 1. KEDA Operator Status
```
kubectl get pods -n keda
kubectl get crds | grep keda
```
Pass: KEDA operator and metrics-apiserver Running. ScaledObject CRD exists.

## 2. ScaledObject Status
```
kubectl get scaledobject -n data-plane ingestion-api-scale -o yaml | \
  grep -A5 'conditions:'
kubectl describe scaledobject -n data-plane ingestion-api-scale | grep -E 'Active|Ready|Error|Fallback'
```
Pass: `Active=True`, `Ready=True`. No fallback replicas firing.

## 3. Trigger Health — Prometheus (VictoriaMetrics)
```
kubectl describe scaledobject -n data-plane ingestion-api-scale | grep -A10 'prometheus'
```
Verify: `serverAddress: http://victoriametrics.observability.svc:8428` reachable.
```
kubectl run metric-test --rm -it --restart=Never --image=curlimages/curl --namespace=data-plane -- \
  curl -s 'http://victoriametrics.observability.svc:8428/api/v1/query?query=rate(http_requests_total{job="ingestion-api"}[1m])' | python3 -m json.tool
```
Pass: Query returns result (not empty).

## 4. Trigger Health — NATS JetStream
```
kubectl describe scaledobject -n data-plane ingestion-api-scale | grep -A10 'nats-jetstream'
```
Verify: `natsServer: nats://dip-nats.data-plane.svc:4222`, consumer `ingestion_consumer` exists.

## 5. Trigger Health — Cron (Business Hours)
```
kubectl describe scaledobject -n data-plane ingestion-api-scale | grep -A10 'cron'
```
Verify: `start: 0 8 * * mon-fri`, `end: 0 18 * * mon-fri`, `desiredReplicas: "2"`.

## 6. Scale-to-Zero Verification
```
kubectl get deployment -n data-plane ingestion-api -o jsonpath='{.spec.replicas}'
```
Outside business hours with no traffic: should be `0`.
During business hours: should be `2`.

## 7. Fallback Configuration
```
kubectl get scaledobject -n data-plane ingestion-api-scale -o jsonpath='{.spec.fallback}'
```
Verify: `failureThreshold: 3`, `replicas: 1`. If all triggers fail 3 times → 1 replica (safe minimum).

## 8. Scaling Events
```
kubectl get events -n data-plane | grep -i 'scale\|keda' | tail -20
```
Review: Recent scale-up/scale-down events. Check for flapping (rapid up/down cycling).

## Report
KEDA status, all 3 trigger health, current replica count, fallback config, recent events.
