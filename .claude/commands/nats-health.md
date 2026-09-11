# nats-health

Validate NATS JetStream health for the DIP ingestion pipeline (data-plane namespace).

## 1. NATS Pod Status
```
kubectl get pods -n data-plane -l app=dip-nats -o wide
```
Pass: All NATS pods Running. Check replica count matches StatefulSet desired.

## 2. JetStream Status
```
kubectl exec -n data-plane -l app=dip-nats -- nats server info 2>/dev/null | grep -E 'JetStream|version|cluster'
```
Pass: JetStream enabled. Server version shown.

## 3. Stream Health
```
kubectl exec -n data-plane -l app=dip-nats -- \
  nats stream list --server=nats://localhost:4222 2>/dev/null
```
Verify: `ingestion_events` stream exists.

## 4. Consumer Lag (ingestion_consumer)
```
kubectl exec -n data-plane -l app=dip-nats -- \
  nats consumer info ingestion_events ingestion_consumer --server=nats://localhost:4222 2>/dev/null | \
  grep -E 'Num Pending|Ack Pending|Redelivered'
```
Pass: `Num Pending` < 30 (matches KEDA lagThreshold). Redelivered count not growing.

## 5. NATS Server Metrics
```
kubectl exec -n data-plane -l app=dip-nats -- \
  wget -qO- http://localhost:8222/varz 2>/dev/null | python3 -m json.tool | \
  grep -E 'connections|subscriptions|slow_consumers|in_msgs|out_msgs'
```
Pass: No `slow_consumers`. Connection count healthy.

## 6. JetStream Storage
```
kubectl exec -n data-plane -l app=dip-nats -- \
  wget -qO- http://localhost:8222/jsz 2>/dev/null | python3 -m json.tool | \
  grep -E 'memory|storage|streams|consumers'
```
Pass: Storage usage < 80% of configured limit.

## 7. Network Policy (NATS port 4222)
```
kubectl get networkpolicy -n data-plane | grep nats
```
Pass: NetworkPolicy restricting access to port 4222 to data-plane namespace only.

## Report
Pod status, JetStream enabled, stream list, consumer lag count, storage usage.
