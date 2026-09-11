# crowdsec-status

Validate CrowdSec IDS/WAF deployment on the K3s-HA cluster.

## 1. CrowdSec LAPI Pod
```
kubectl get pods -n crowdsec -l app=crowdsec
kubectl logs -n crowdsec -l app=crowdsec --tail=30 | grep -E 'level=error|level=warning|bouncer|decision'
```
Pass: LAPI pod Running. No error-level log entries at startup.

## 2. Traefik Bouncer Connection
```
kubectl get pods -n crowdsec -l app=crowdsec-traefik-bouncer
kubectl logs -n crowdsec -l app=crowdsec-traefik-bouncer --tail=20
```
Pass: Bouncer Running. Logs show successful LAPI connection.

## 3. Registered Bouncers
```
kubectl exec -n crowdsec -l app=crowdsec -- cscli bouncers list
```
Pass: At least one bouncer registered (traefik-bouncer). Status `valid`.

## 4. Active Decisions (Bans)
```
kubectl exec -n crowdsec -l app=crowdsec -- cscli decisions list --limit 20
```
Review: Active bans/captchas. Flag any false positives on known-good IPs.

## 5. Alerts
```
kubectl exec -n crowdsec -l app=crowdsec -- cscli alerts list --limit 20
```
Review: Recent detections. Classify: brute force, scanning, credential stuffing.

## 6. Hub Collections Installed
```
kubectl exec -n crowdsec -l app=crowdsec -- cscli collections list | grep enabled
```
Expect: traefik, linux, base-http-scenarios collections installed.

## 7. Sealed Secrets for CrowdSec
```
kubectl get sealedsecret -n crowdsec
kubectl get secret -n crowdsec | grep -v 'kubernetes.io'
```
Pass: LAPI credentials and bouncer API key secrets present and decrypted.

## 8. CrowdSec Metrics
```
kubectl exec -n crowdsec -l app=crowdsec -- cscli metrics
```
Review: Parsed lines, overflow count, ban count per parser.

## Report
LAPI status, bouncer count, active bans, recent alerts summary, collections list.
