# cost-optimization

Identify resource waste and cost optimization opportunities on Hetzner Cloud.

## 1. Idle / Over-provisioned Nodes
```
kubectl top nodes 2>/dev/null
```
Compute: If any node is < 20% CPU and < 30% memory for > 7 days, it may be over-provisioned.
Hetzner pricing: CPX11 (€3.85/mo) → CPX21 (€5.83/mo) → CPX31 (€10.57/mo) etc.

## 2. Pods with No Resource Requests
```
kubectl get pods -A -o json | \
  jq '[.items[] | select(.spec.containers[].resources.requests == null)] | length'
kubectl get pods -n data-plane -o json | \
  jq '.items[] | select(.spec.containers[].resources.requests == null) | .metadata.name'
```
Issue: Pods without requests can be over-scheduled, causing noisy-neighbor evictions.

## 3. Pods Near Zero Utilization
```
kubectl top pods -A --sort-by=cpu 2>/dev/null | awk '{if ($2+0 < 5) print $0}' | head -20
```
Review: Very low CPU pods may be candidates for scale-to-zero (KEDA) or consolidation.

## 4. PVC Sizing vs Actual Usage
```
kubectl exec -n data-plane deployment/dip-minio -- df -h /data 2>/dev/null | tail -1
kubectl get pvc -n data-plane -o custom-columns='NAME:.metadata.name,CAPACITY:.spec.resources.requests.storage'
```
MinIO is 30Gi PVC. Hetzner volumes: €0.048/GB/month = €1.44/mo per 30Gi.
Review: Is 30Gi appropriately sized? Check actual usage vs capacity.

## 5. KEDA Scale-to-Zero Verification
```
kubectl get hpa -n data-plane 2>/dev/null
kubectl get scaledobject -n data-plane -o json | jq '.items[] | {name: .metadata.name, minReplicas: .spec.minReplicaCount, maxReplicas: .spec.maxReplicaCount}'
```
Verify: ingestion-api scales to 0 outside cron window (off Mon-Fri 8AM-6PM UTC).
Cost impact: scaling to 0 for ~16 hours/day and weekends = ~60% compute savings for that pod.

## 6. Image Pull Efficiency
```
kubectl get pods -A -o json | \
  jq '[.items[] | .spec.containers[].image] | group_by(.) | map({image: .[0], count: length}) | sort_by(.count) | reverse | .[0:10]'
```
Identify: Commonly used base images. Consider a local image registry (Harbor) to reduce Hetzner egress on pulls.

## 7. External Egress
Hetzner: 20TB free egress/month, then €1/TB.
```
# Estimate via Hubble (if available)
hubble observe --verdict FORWARDED --to-world --last 1000 --output json 2>/dev/null | \
  python3 -c "
import sys, json
from collections import Counter
bytes_out = 0
count = 0
for line in sys.stdin:
    try:
        f = json.loads(line).get('flow', {})
        bytes_out += f.get('l4', {}).get('tcp', {}).get('flags', {}).get('syn', 0)
        count += 1
    except: pass
print(f'External flows sampled: {count}')
"
```

## 8. MinIO vs S3 Trade-off
Planned: self-hosted MinIO on direct local storage (`minio-local`, plan Gate 26), never Longhorn. Not yet deployed.
Alternative: Hetzner Object Storage (S3-compatible, €0.0059/GB/month).
Cost at 30GB: MinIO = €1.44/mo (volume) + node compute. Hetzner S3 = €0.18/mo.
Recommendation: For WAL archive only, Hetzner Object Storage is cheaper. For documents, evaluate latency.

## Report
Node utilization summary, waste candidates, KEDA scale-to-zero confirmation, storage cost comparison.
