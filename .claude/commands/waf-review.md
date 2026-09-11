# waf-review

Review Traefik + Coraza WAF + CrowdSec bouncer effectiveness.

## 1. Coraza WAF Configuration
```
kubectl get configmap -n kube-system | grep -i coraza
kubectl get configmap -n kube-system coraza-config -o yaml 2>/dev/null | head -60
```
Verify: OWASP Core Rule Set loaded. Detection mode vs blocking mode configured.

## 2. Traefik Plugin: Coraza Middleware
```
kubectl get middleware -n kube-system | grep -i coraza
kubectl get ingressroute -A -o json | \
  jq '.items[] | select(.spec.routes[].middlewares[]?.name | test("coraza|waf")) | {ns: .metadata.namespace, name: .metadata.name}'
```
Pass: All external-facing IngressRoutes use the Coraza WAF middleware.

## 3. WAF Logs — Recent Blocks
```
kubectl logs -n kube-system -l app=traefik --tail=200 | grep -E 'coraza|WAF|blocked|RULE'
```
Review: Active blocks indicate WAF is functioning. Investigate false positives.

## 4. CrowdSec LAPI Status
```
kubectl get pods -n crowdsec -l app=crowdsec
kubectl exec -n crowdsec deployment/crowdsec -- cscli version
kubectl exec -n crowdsec deployment/crowdsec -- cscli metrics | grep -E 'decisions|alerts'
```

## 5. Active Bans
```
kubectl exec -n crowdsec deployment/crowdsec -- cscli decisions list --limit 20
```
Review: IPs currently banned. Flag unexpected geographic sources or high volume.

## 6. Traefik Bouncer Plugin
```
kubectl get middleware -n kube-system | grep bouncer
kubectl logs -n kube-system -l app=traefik --tail=100 | grep -i crowdsec
```
Pass: Bouncer middleware registered. No authentication errors to LAPI.

## 7. Collections and Parsers
```
kubectl exec -n crowdsec deployment/crowdsec -- cscli collections list | grep enabled
```
Verify: `crowdsecurity/traefik` collection enabled. `crowdsecurity/linux` parser active.

## 8. False Positive Rate
```
kubectl exec -n crowdsec deployment/crowdsec -- cscli alerts list --limit 10 --type false_positive 2>/dev/null
```
Low FP rate = well-tuned WAF. High FP rate = needs rule tuning.

## 9. Rate Limiting (Traefik)
```
kubectl get middleware -A | grep -i ratelimit
kubectl get middleware -n kube-system -o yaml | grep -A5 rateLimit
```
Verify: Rate limit middleware applied to API-facing IngressRoutes.

## Report
WAF mode (detect/block), active Coraza rules, CrowdSec decision count, bouncer connectivity, false positive rate.
