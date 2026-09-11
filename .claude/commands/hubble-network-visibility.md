# hubble-network-visibility

Review Hubble network observability coverage and flow data.

## 1. Hubble Relay and UI Status
```
kubectl get pods -n kube-system -l k8s-app=hubble-relay
kubectl get pods -n kube-system -l k8s-app=hubble-ui 2>/dev/null
```
Pass: hubble-relay Running. Hubble UI Running (if deployed).

## 2. Hubble CLI Status
```
hubble status 2>/dev/null || \
  kubectl exec -n kube-system -l k8s-app=cilium -- hubble status 2>/dev/null | head -10
```
Pass: `Healthcheck (via localhost:4245): Ok`. NumFlows > 0.

## 3. Live Flow Observation (30s sample)
```
hubble observe --last 100 --output json 2>/dev/null | \
  python3 -c "
import sys, json
from collections import Counter
verbs = Counter()
for line in sys.stdin:
    try:
        f = json.loads(line)
        verdict = f.get('flow', {}).get('verdict', 'UNKNOWN')
        verbs[verdict] += 1
    except: pass
for k, v in verbs.most_common(): print(f'{k}: {v}')
" || echo "Hubble CLI not available — port-forward to hubble-relay:4245"
```

## 4. Dropped Flows (all namespaces)
```
hubble observe --verdict DROPPED --last 50 --output json 2>/dev/null | \
  python3 -c "
import sys, json
for line in sys.stdin:
    try:
        f = json.loads(line).get('flow', {})
        src = f.get('source', {})
        dst = f.get('destination', {})
        reason = f.get('drop_reason_desc', '?')
        print(f\"{src.get('namespace','?')}/{src.get('workloads',[{}])[0].get('name','?')} -> {dst.get('namespace','?')}/{dst.get('workloads',[{}])[0].get('name','?')}: {reason}\")
    except: pass
"
```
Review: Policy drops expected for denied traffic. Unexpected drops may indicate broken NetworkPolicy.

## 5. Data-Plane mTLS Flows
```
hubble observe --namespace data-plane --last 50 --output json 2>/dev/null | \
  python3 -c "
import sys, json
for line in sys.stdin:
    try:
        f = json.loads(line).get('flow', {})
        auth = f.get('auth_type', '')
        if auth:
            print(f\"auth={auth}: {f.get('l4',{})}\")
    except: pass
"
```
Pass: Flows between auth-service↔postgres show `auth_type: SPIRE_GRPC_TLS` or equivalent mTLS indicator.

## 6. Hubble Metrics Coverage
```
kubectl port-forward -n kube-system svc/hubble-metrics 9965 &
curl -s http://localhost:9965/metrics | grep -E '^hubble_' | head -20
```
Pass: Hubble flow metrics being exported to VictoriaMetrics.

## Report
Relay health, flows/sec, drop rate per namespace, mTLS auth flow confirmation, metrics export status.
