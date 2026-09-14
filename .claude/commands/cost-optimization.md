# cost-optimization

Identify resource waste and cost optimization opportunities on the Veridex netcup cluster.

## 1. Idle / Over-provisioned Nodes
```
kubectl top nodes 2>/dev/null
```
Compute: If any node is < 20% CPU and < 30% memory for > 7 days, it may be over-provisioned.
netcup pricing: use the current price list for the RS 1000 G12 and RS 2000 G12 servers in the inventory (prices are not recorded in this repo).

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
MinIO is planned on direct local storage (plan Gates 13 and 23-24); its size and storage cost are not decided yet.
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
Identify: Commonly used base images. Consider a local image registry (Harbor) to reduce registry egress on pulls.

## 7. External Egress
netcup traffic allowance: check the current terms for the servers in the inventory (not recorded in this repo).
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
Off-cluster copies: backups and archives go to Backblaze B2 (plan Gates 17-21). B2 bills per byte-hour with no minimum storage duration, so frequent pruning of WAL and etcd snapshots is cheap; the cost to watch is egress during a full restore, which is free only up to 3x average monthly storage, plus per-class transaction charges (plan Gate 18).

## Report
Node utilization summary, waste candidates, KEDA scale-to-zero confirmation, storage cost comparison.
