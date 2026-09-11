# network-policy-audit

Audit Kubernetes NetworkPolicies and CiliumNetworkPolicies across all namespaces.

## 1. Namespaces Without Default-Deny
```
for ns in $(kubectl get ns -o jsonpath='{.items[*].metadata.name}'); do
  count=$(kubectl get networkpolicy -n $ns --no-headers 2>/dev/null | grep -c "deny\|default" || echo 0)
  echo "$ns: $count default-deny policies"
done
```
Pass: `data-plane`, `docintel`, `argocd` all have default-deny ingress policy.

## 2. Wildcard Policy Scan (overly permissive)
```
kubectl get networkpolicy -A -o json | jq '.items[] | select(.spec.ingress[]?.from == null or .spec.egress[]?.to == null) | {ns: .metadata.namespace, name: .metadata.name}'
```
Flag: Any policy with empty `from: []` or `to: []` (allows all traffic).

## 3. Data Plane Policy Inventory
```
kubectl get networkpolicy -n data-plane -o custom-columns='NAME:.metadata.name,POD-SELECTOR:.spec.podSelector'
```
Verify: Policies for cnpg-cluster, minio, redis, nats, temporal, ingestion-api exist.

## 4. CiliumNetworkPolicy Inventory
```
kubectl get ciliumnetworkpolicy -A
```
Verify: docintel namespace has 5 mTLS policies (from cilium-mtls-verify).

## 5. Cross-Namespace Traffic Check
```
kubectl get networkpolicy -A -o json | \
  jq '.items[] | select(.spec.ingress[]?.from[]?.namespaceSelector != null) | {ns: .metadata.namespace, name: .metadata.name, allowedFrom: .spec.ingress[].from[].namespaceSelector}'
```
Review: Cross-namespace selectors should be explicit (not `matchLabels: {}`).

## 6. Egress Restrictions
```
kubectl get networkpolicy -A -o json | jq '.items[] | select(.spec.policyTypes[] == "Egress") | .metadata | {ns: .namespace, name: .name}'
```
Pass: Egress policies exist in data-plane and docintel to restrict outbound.

## Report
Table: namespace | default-deny | ingress policies | egress policies | wildcard risks | verdict
