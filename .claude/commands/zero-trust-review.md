# zero-trust-review

Comprehensive zero-trust security posture review for the K3s-HA cluster.

## 1. mTLS Coverage (Cilium SPIFFE)
Run /cilium-mtls-verify to confirm all 5 critical paths enforced.
Additional check — all data-plane service-to-service:
```
kubectl get ciliumnetworkpolicy -A | wc -l
```
Target: Every sensitive service pair has `authentication.mode: required`.

## 2. Network Segmentation
```
kubectl get networkpolicy -A --no-headers | awk '{print $1}' | sort -u
```
Pass: Every namespace with workloads has at least one NetworkPolicy.
```
kubectl get ns --no-headers | awk '{print $1}' | while read ns; do
  count=$(kubectl get networkpolicy -n $ns --no-headers 2>/dev/null | wc -l)
  [ $count -eq 0 ] && echo "NO POLICY: $ns"
done
```

## 3. ForwardAuth on All External Routes
```
kubectl get ingressroute -A -o json | \
  jq '.items[] | select(.spec.routes[].middlewares == null or (.spec.routes[].middlewares | map(.name) | contains(["forward-auth"]) | not)) | {ns: .metadata.namespace, name: .metadata.name}'
```
Pass: No external IngressRoute without forward-auth middleware (or explicitly public routes justified).

## 4. Secret Encryption at Rest
```
kubectl get encryptionconfig 2>/dev/null || \
  ansible servers -i ansible/inventory/hcloud.yml -m shell -a "cat /etc/rancher/k3s/server/encryption-config.json" 2>/dev/null | grep -i aescbc
```
Pass: etcd encryption config exists with AES-CBC for Secrets.
(Confirmed via `phase-etcd-encryption.yml` playbook presence.)

## 5. Pod Security Standards
```
kubectl get ns -o json | jq '.items[] | select(.metadata.labels | has("pod-security.kubernetes.io/enforce")) | {ns: .metadata.name, level: .metadata.labels["pod-security.kubernetes.io/enforce"]}'
```
Pass: data-plane, docintel, argocd namespaces have `restricted` or `baseline` enforcement.

## 6. Kyverno Policies Active
```
kubectl get clusterpolicy,policy -A | grep -v NAME
kubectl get policyreport -A --no-headers | awk '{sum+=$4} END {print "FAIL total:", sum}'
```
Pass: Policies in `Enforce` mode. PolicyReport FAIL count = 0.

## 7. WAF Active on Perimeter
Traefik + Coraza WAF + CrowdSec bouncer all active (confirm via /traefik-health and /crowdsec-status).

## 8. Audit Logging
```
kubectl get daemonset -n logging -l app=fluent-bit 2>/dev/null || \
kubectl get daemonset -n kube-system | grep fluent
```
Pass: Fluent Bit DaemonSet running. K8s audit logs shipping to Loki.

## 9. RBAC Overprivilege Scan
```
kubectl get clusterrolebinding -o json | \
  jq '.items[] | select(.subjects[]?.kind == "ServiceAccount" and (.roleRef.name == "cluster-admin")) | {name: .metadata.name, sa: .subjects[].name}'
```
Pass: Only kube-system and argocd service accounts have cluster-admin. No data-plane SAs.

## Report
Score each of 9 domains PASS/FAIL/PARTIAL. Produce prioritized remediation list.
