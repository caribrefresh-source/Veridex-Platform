# nats-consumer-lag-review

Review NATS JetStream consumer lag for the ingestion pipeline.

## 1. Stream Status
```
kubectl exec -n data-plane -l app=dip-nats -- \
  nats stream info ingestion_events --json 2>/dev/null | \
  python3 -m json.tool | grep -E 'messages|bytes|consumer_count|num_subjects|first_seq|last_seq'
```
Pass: Stream `ingestion_events` exists. `num_subjects` > 0.

## 2. Consumer Lag
```
kubectl exec -n data-plane -l app=dip-nats -- \
  nats consumer info ingestion_events ingestion_consumer --json 2>/dev/null | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
num_pending = data.get('num_pending', 0)
num_redelivered = data.get('num_redelivered', 0)
ack_floor = data.get('ack_floor', {}).get('consumer_seq', 0)
delivered = data.get('delivered', {}).get('consumer_seq', 0)
print(f'Pending: {num_pending} | Redelivered: {num_redelivered} | Delivered: {delivered} | AckFloor: {ack_floor}')
if num_pending > 100:
    print('WARNING: Consumer lag > 100 messages — check ingestion-api pod count and KEDA')
if num_pending > 1000:
    print('CRITICAL: Consumer lag > 1000 — ingestion pipeline may be blocked')
"
```
KEDA threshold: `lagThreshold: 30` → ingestion-api scales up at 30+ pending messages.

## 3. Redelivery Rate (stuck messages)
```
kubectl exec -n data-plane -l app=dip-nats -- \
  nats consumer info ingestion_events ingestion_consumer --json 2>/dev/null | \
  python3 -m json.tool | grep -E 'num_redelivered|nak_count|max_deliver'
```
Flag: High `num_redelivered` with low `num_pending` = messages failing processing (Temporal workflow errors?).

## 4. KEDA Response to Lag
```
kubectl get scaledobject -n data-plane ingestion-api-scaler -o json | \
  jq '.status | {desiredReplicas: .desiredReplicas, lastScaleTime: .lastScaleTime}'
kubectl get hpa -n data-plane -o json | \
  jq '.items[] | {name: .metadata.name, current: .status.currentReplicas, desired: .status.desiredReplicas, min: .spec.minReplicas, max: .spec.maxReplicas}'
```
Pass: At lag > 30, `desiredReplicas` > `minReplicas`.

## 5. Message Age Distribution
```
kubectl exec -n data-plane -l app=dip-nats -- \
  nats stream info ingestion_events --json 2>/dev/null | \
  python3 -m json.tool | grep -E 'first_ts|last_ts'
```
Flag: If `first_ts` is > 5 minutes old and lag > 0, the oldest messages are stuck.

## 6. Consumer Config Verification
```
kubectl exec -n data-plane -l app=dip-nats -- \
  nats consumer info ingestion_events ingestion_consumer --json 2>/dev/null | \
  python3 -m json.tool | grep -E 'ack_policy|deliver_policy|max_deliver|ack_wait'
```
Verify: `ack_policy: explicit`, `ack_wait: 30s`, `max_deliver: 5` (matches retry budget).

## Report
Current lag, redelivery rate, KEDA scale response, oldest message age, consumer config.
