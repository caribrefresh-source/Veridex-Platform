# traefik-health

Validate Traefik v3.7 ingress, WAF (Coraza), and ForwardAuth middleware on entrepeai.com.

## 1. Traefik Pod Status
```
kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik -o wide
```
Pass: Traefik pods Running. HostNetwork mode active (required for Cilium probe bypass).

## 2. IngressRoute Inventory
```
kubectl get ingressroute -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,HOST:.spec.routes[0].match'
```
Verify: argocd.entrepeai.com, hubble.entrepeai.com, and any DIP endpoints present.

## 3. TLS Options
```
kubectl get tlsoptions -A
```
Verify: TLS options resource exists (`gitops/infra/traefik/tlsoptions.yaml`) enforcing TLS 1.2+ minimum.

## 4. ForwardAuth Middleware
```
kubectl get middleware -A | grep -i auth
kubectl get ingressroute -A -o json | jq '.items[].spec.routes[].middlewares[]?.name' | grep -i auth
```
Pass: ForwardAuth middleware defined. At least one IngressRoute references it.

## 5. Coraza WAF Status
```
kubectl get middleware -A | grep -i coraza
kubectl logs -n kube-system -l app.kubernetes.io/name=traefik --tail=50 | grep -i 'coraza\|waf\|blocked'
```
Pass: Coraza middleware active. No startup errors in logs.

## 6. CrowdSec Bouncer Integration
```
kubectl get pods -n crowdsec -l app=crowdsec-traefik-bouncer
kubectl logs -n crowdsec -l app=crowdsec-traefik-bouncer --tail=20
```
Pass: Bouncer pod Running. Logs show ban decisions being applied.

## 7. TLS Certificate Valid
```
kubectl get certificate -A | grep -E 'entrepeai|argocd|hubble'
echo | openssl s_client -connect argocd.entrepeai.com:443 -servername argocd.entrepeai.com 2>/dev/null | openssl x509 -noout -dates
```
Pass: Certificate Ready. Not-after > 14 days from today.

## 8. Traefik Metrics
```
kubectl exec -n kube-system -l app.kubernetes.io/name=traefik -- \
  wget -qO- http://localhost:8082/metrics | grep -E 'traefik_requests_total|traefik_backend'
```
Pass: Metrics endpoint responding.

## Report
Pod status, IngressRoute count, WAF active, ForwardAuth active, TLS expiry, bouncer status.
