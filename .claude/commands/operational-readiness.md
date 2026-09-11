# operational-readiness

Full operational readiness gate check — run before going to production or after major changes.

## Platform Health (run all, pass all)
```
# Node health
kubectl get nodes | grep -v Ready
kubectl get pods -A --field-selector=status.phase!=Running | grep -v Completed | grep -v Pending

# Control plane
kubectl get pods -n kube-system | grep -E 'kube-vip|cilium|traefik' | grep -v Running
```

## GitOps Health
```
kubectl get application -n argocd -o json | \
  jq '.items[] | select(.status.health.status != "Healthy" or .status.sync.status != "Synced") | {name: .metadata.name, health: .status.health.status, sync: .status.sync.status}'
```
Pass: All apps Synced + Healthy.

## Data-Plane Health
```
kubectl get pods -n data-plane | grep -v Running
kubectl get cluster -n data-plane -o jsonpath='{.items[0].status.phase}'
```
Pass: All data-plane pods Running. CNPG cluster `Cluster in healthy state`.

## Security Gate
```
# No plaintext secrets in manifests
grep -rn 'password:\|token:\s' gitops/ --include='*.yaml' | grep -v 'secretRef\|SealedSecret\|ExternalSecret\|#'
# All external certs valid
kubectl get certificate -A -o json | python3 -c "
import sys, json
from datetime import datetime, timezone
data = json.load(sys.stdin)
for cert in data['items']:
    expiry = cert.get('status', {}).get('notAfter', '')
    if expiry:
        days = (datetime.fromisoformat(expiry.replace('Z','+00:00')) - datetime.now(timezone.utc)).days
        if days < 14: print('WARN:', cert['metadata']['namespace'] + '/' + cert['metadata']['name'], days, 'days')
"
```

## Backup Gate
```
kubectl get backup -n data-plane --sort-by='.metadata.creationTimestamp' -o json | \
  jq '.items[-1] | {phase: .status.phase, age: .metadata.creationTimestamp}'
```
Pass: Last CNPG backup Completed within 2 hours.

## Observability Gate
```
kubectl get pods -n observability | grep -v Running 2>/dev/null
kubectl get daemonset -A | grep fluent | awk '{print $1,$2,$3,$4,$5}'
```
Pass: VictoriaMetrics, Loki Running. Fluent Bit DESIRED==READY.

## Ingress Gate
```
curl -sk https://argocd.entrepeai.com/healthz | head -5
kubectl get ingressroute -A --no-headers | wc -l
```
Pass: argocd.entrepeai.com returns 200 OK. All IngressRoutes present.

## Final Score
Pass criteria (all must pass for READY):
- [ ] All nodes Ready
- [ ] All ArgoCD apps Synced + Healthy
- [ ] All data-plane pods Running
- [ ] CNPG cluster healthy
- [ ] No certs expiring < 14 days
- [ ] CNPG backup < 2h old
- [ ] Observability stack Running
- [ ] External ingress reachable

READY = all 8 pass. Report any failures with remediation steps.
