# spiffe-identity-audit

> **DEPRECATED 2026-07-18.** Cilium Mutual Authentication (SPIRE) is being retired
> cluster-wide — deprecated upstream (cilium/cilium#47132), broken on this topology by
> an upstream bug closed WONTFIX (cilium/cilium#46720). See
> `gitops/infra/cilium/mutual-auth-policies.yaml` header for the decision record and
> PR #183/#184 for the removal. Every check below assumes SPIRE is running and will
> fail by design once PR #184 merges — that is expected, not a regression. Do not run
> this as a health check after that point. Retained for historical reference only.

Audit SPIFFE/SPIRE identity issuance and mTLS enforcement across the cluster.

## 1. SPIRE Server Health
```
kubectl get pods -n spire 2>/dev/null || kubectl get pods -A | grep spire
kubectl logs -n spire -l app=spire-server --tail=20 | grep -E 'error|warn|ERROR|WARN'
```
Pass: spire-server and spire-agent pods Running. No errors in logs.

## 2. SPIRE Agent Registration
```
kubectl exec -n spire deployment/spire-server -- \
  /opt/spire/bin/spire-server agent list 2>/dev/null | grep -E 'ATTESTED|EXPIRED'
```
Pass: All 3 server nodes + all worker nodes have ATTESTED agents. None EXPIRED.

## 3. Workload Registrations
```
kubectl exec -n spire deployment/spire-server -- \
  /opt/spire/bin/spire-server entry show 2>/dev/null | grep -E 'SVID|spiffe://'
```
Verify: SVID entries exist for:
- `spiffe://cluster.local/ns/docintel/sa/auth-service`
- `spiffe://cluster.local/ns/data-plane/sa/cnpg-cluster`
- `spiffe://cluster.local/ns/docintel/sa/ingestion-api`
- `spiffe://cluster.local/ns/kube-system/sa/traefik`

## 4. SVID Expiry Check
```
kubectl exec -n spire deployment/spire-server -- \
  /opt/spire/bin/spire-server entry show -output json 2>/dev/null | \
  jq '.entries[] | {id: .id, spiffeId: .spiffe_id, ttl: .ttl}'
```
Pass: TTL set appropriately (default 3600s for workloads). No entries with 0 TTL.

## 5. Cilium SPIFFE Integration
```
kubectl get ciliumnetworkpolicy -A -o json | \
  jq '.items[] | select(.spec.ingress[]?.authentication.mode == "required") | {ns: .metadata.namespace, name: .metadata.name}'
```
Pass: Auth-required policies exist for all 4 critical mTLS paths.

## 6. Identity Federation (if applicable)
```
kubectl exec -n spire deployment/spire-server -- \
  /opt/spire/bin/spire-server federation list 2>/dev/null
```
Verify: No unexpected trust domain federations.

## 7. Certificate Rotation Status
```
kubectl exec -n spire deployment/spire-server -- \
  /opt/spire/bin/spire-server x509 show 2>/dev/null | grep -E 'Valid Until|Subject'
```
Pass: CA cert valid for >30 days.

## Report
Agent count vs expected, SVID registrations for all 4 critical services, CA expiry, mTLS coverage.
