# cilium-mtls-verify

> **DEPRECATED 2026-07-18.** Cilium Mutual Authentication (SPIRE) is being retired
> cluster-wide — deprecated upstream (cilium/cilium#47132), broken on this topology by
> an upstream bug closed WONTFIX (cilium/cilium#46720). See
> `gitops/infra/cilium/mutual-auth-policies.yaml` header for the decision record and
> PR #183/#184 for the removal. `authentication.mode: required` no longer appears on
> any policy after PR #183; SPIRE pods are gone after PR #184. Sections 1 and 4 below
> will fail by design — that is expected, not a regression. Sections 2, 3, and 5
> (Hubble flow/drop checks) remain valid as a general L3/L4 policy-enforcement check.
> Retained for historical reference only.

## Critical mTLS Paths (from mutual-auth-policies.yaml)
1. auth-service → auth-postgres (port 5432)
2. auth-postgres ← auth-service (port 5432)
3. auth-service → auth-redis (port 6379)
4. auth-redis ← auth-service (port 6379)
5. traefik → auth-service (port 8080, ForwardAuth)

## 1. Verify CiliumNetworkPolicies Exist
```
kubectl get ciliumnetworkpolicy -n docintel -o custom-columns='NAME:.metadata.name,MODE:.spec.egress[0].authentication.mode'
```
Expected policies:
- mutual-auth-auth-to-postgres
- mutual-auth-postgres-from-auth
- mutual-auth-auth-to-redis
- mutual-auth-redis-from-auth
- mutual-auth-traefik-to-auth

Pass: All 5 policies present with `authentication.mode: required`.

## 2. SPIFFE Identity Verification via Hubble
```
kubectl exec -n kube-system -l k8s-app=hubble-relay -- hubble observe \
  --namespace docintel \
  --verdict FORWARDED \
  --protocol TCP \
  --last 100 2>/dev/null | grep -E 'auth-service|auth-postgres|auth-redis|traefik'
```
Pass: Traffic between these services shows as FORWARDED (not DROPPED).

## 3. Test mTLS Enforcement (negative test)
Attempt connection from an unauthorized pod to auth-postgres:5432 — should be DROPPED.
```
kubectl run mtls-test --rm -it --restart=Never --image=busybox -n docintel -- \
  nc -zv auth-postgres 5432
```
Pass: Connection REFUSED or TIMEOUT (Cilium drops it — no SPIFFE identity).

## 4. SPIRE SVID Validity
```
kubectl exec -n kube-system -l app=spire-agent -- \
  /opt/spire/bin/spire-agent api fetch x509 2>/dev/null | grep -E 'SVID|expiry|valid'
```
Pass: SVIDs present, not expired, rotation upcoming within 1h.

## 5. Hubble Dropped Flows Audit
```
kubectl exec -n kube-system -l k8s-app=hubble-relay -- hubble observe \
  --namespace docintel --verdict DROPPED --last 50 2>/dev/null
```
Review: Any unexpected DROPS between legitimate service pairs indicates misconfigured policy.

## Report
Policy inventory (5/5 present), SPIFFE SVID status, positive/negative flow test results, dropped flow count.
