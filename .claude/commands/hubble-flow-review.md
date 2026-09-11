# hubble-flow-review

Review Cilium Hubble network flows for dropped traffic, policy violations, and unexpected egress.

## 1. Recent Dropped Flows (all namespaces)
```
kubectl exec -n kube-system -l k8s-app=hubble-relay -- \
  hubble observe --verdict DROPPED --last 100 --output json 2>/dev/null | \
  jq '{src: .source.namespace, dst: .destination.namespace, reason: .drop_reason_desc, time: .time}'
```
Review: Classify drops as expected (policy enforcement) vs unexpected (misconfiguration).

## 2. Dropped Flows in data-plane
```
kubectl exec -n kube-system -l k8s-app=hubble-relay -- \
  hubble observe --namespace data-plane --verdict DROPPED --last 50 2>/dev/null
```
Pass: Zero unexpected drops. mTLS enforcement drops from unauthorized sources are expected.

## 3. External Egress from data-plane
```
kubectl exec -n kube-system -l k8s-app=hubble-relay -- \
  hubble observe --namespace data-plane --verdict FORWARDED --last 200 2>/dev/null | \
  grep -v "data-plane\|kube-system\|monitoring" | head -30
```
Review: Any traffic leaving the cluster from data-plane should be intentional (MinIO S3 sync, etc.).

## 4. Top Talkers
```
kubectl exec -n kube-system -l k8s-app=hubble-relay -- \
  hubble observe --last 500 --output json 2>/dev/null | \
  jq -r '[.source.namespace, .source.pod_name, .destination.namespace, .destination.pod_name] | @csv' | \
  sort | uniq -c | sort -rn | head -20
```
Identify high-volume flows for capacity and security review.

## 5. Auth Service Flow Verification
```
kubectl exec -n kube-system -l k8s-app=hubble-relay -- \
  hubble observe --namespace docintel --verdict FORWARDED --last 100 2>/dev/null | \
  grep -E 'traefik|auth-service|auth-postgres|auth-redis'
```
Pass: ForwardAuth flows visible traefik→auth-service.

## 6. Hubble Relay Health
```
kubectl get pods -n kube-system -l k8s-app=hubble-relay
kubectl get pods -n kube-system -l k8s-app=hubble-ui
```
Pass: Both Running.

## Report
Drop count by namespace, unexpected egress list, top talkers, auth path visibility.
