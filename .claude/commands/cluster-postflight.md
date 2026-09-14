# cluster-postflight

Validate the cluster after a deployment or change. Run immediately after any ArgoCD sync or Ansible playbook.

## 1. ArgoCD Sync Status
```
kubectl get applications -n argocd -o custom-columns='NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status'
```
Pass: All applications `Synced` + `Healthy`. Investigate any `OutOfSync`, `Degraded`, `Unknown`.

## 2. No New CrashLoops
```
kubectl get pods -A | grep -E 'CrashLoop|Error|OOMKilled|Evicted'
```
Pass: No output.

## 3. Data Plane Pods
```
kubectl get pods -n data-plane
```
Pass: CNPG cluster pods Running, MinIO Running, Redis Running, NATS Running.
Ingestion API may be 0 replicas (scale-to-zero is normal when idle).

## 4. Certificate Health
```
kubectl get certificate -A
```
Pass: All certificates `Ready=True`. No `False`.

## 5. Ingress Routing
```
kubectl get ingressroute -A
kubectl get ingress -A
```
Pass: All IngressRoutes present. Verify the Argo CD and Hubble hostnames under veridexeai.com resolve (created at Gates 10 and 15).

## 6. Network Policies Active
```
kubectl get networkpolicy -n data-plane
kubectl get ciliumnetworkpolicy -n docintel
```
Pass: All expected policies present. No namespace missing default-deny.

## 7. Recent Events
```
kubectl get events -A --sort-by='.lastTimestamp' | tail -30
```
Review: Identify any Warning events from the last deploy window.

## 8. Resource Pressure
```
kubectl top nodes
kubectl top pods -A --sort-by=memory | head -20
```
Pass: No node above 80% CPU or 85% memory.

## Report
PASS / FAIL per check. Flag any regression vs pre-deployment state.
