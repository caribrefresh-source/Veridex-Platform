# resilience-review

Review fault tolerance, retry logic, and graceful degradation across the platform.

## 1. Pod Disruption Budgets
```
kubectl get poddisruptionbudget -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,MIN:.spec.minAvailable,MAX:.spec.maxUnavailable,DISRUPTIONS:.status.currentHealthy'
```
Pass: All stateful services have PDBs. minAvailable >= 1 for single-replica services.

## 2. Restart Policies and Back-off
```
kubectl get pods -A -o json | \
  jq '.items[] | select(.status.containerStatuses[]?.restartCount > 5) | {ns: .metadata.namespace, pod: .metadata.name, restarts: .status.containerStatuses[].restartCount}'
```
Flag: Pods with > 5 restarts need investigation — exponential backoff may hide slow CrashLoop.

## 3. Health Probes
```
kubectl get pods -n data-plane -o json | \
  jq '.items[] | select(.spec.containers[].readinessProbe == null or .spec.containers[].livenessProbe == null) | {pod: .metadata.name, containers: [.spec.containers[] | select(.readinessProbe == null) | .name]}'
```
Pass: All data-plane pods have readiness and liveness probes.

## 4. CNPG Failover
```
kubectl get cluster -n data-plane -o json | \
  jq '.items[] | {name: .metadata.name, primary: .status.currentPrimary, targetPrimary: .status.targetPrimary, readyInstances: .status.readyInstances, phase: .status.phase}'
```
Pass: `readyInstances == spec.instances`. `phase: Cluster in healthy state`.
Automatic failover: CNPG promotes replica if primary crashes within ~30s.

## 5. NATS JetStream Persistence
```
kubectl get statefulset -n data-plane -l app=dip-nats -o jsonpath='{.items[0].spec.volumeClaimTemplates}'
```
Pass: JetStream backed by PVC (not emptyDir). Messages survive pod restart.

## 6. KEDA Scale-to-Zero Recovery
```
kubectl get scaledobject -n data-plane -o yaml | grep -A10 'fallback'
```
Verify: Fallback configured for KEDA ScaledObject (ingestion-api). If VictoriaMetrics unreachable, KEDA falls back to minReplicas, not 0.

## 7. Temporal Retry Policies
Run /temporal-workflow-review to audit retry configs.

## 8. Redis Eviction Policy
```
kubectl exec -n data-plane deployment/dip-redis -- redis-cli CONFIG GET maxmemory-policy
```
Pass: Policy is `noeviction` or `volatile-lru`. **NEVER `allkeys-lru`** — would evict active auth revocation keys.

## 9. Circuit Breaker (Traefik)
```
kubectl get middleware -n kube-system -o yaml | grep -A5 circuitBreaker
```
Verify: Circuit breaker middleware configured for ingestion-api and auth-service routes.

## Report
PDB gaps, pods with no probes, CNPG failover state, Redis eviction policy, KEDA fallback config.
