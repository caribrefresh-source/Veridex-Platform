# cert-expiry-check

Check all TLS certificate expiry dates across the Veridex netcup cluster.

## 1. cert-manager Certificate Resources
```
kubectl get certificate -A -o json | \
  jq '.items[] | {ns: .metadata.namespace, name: .metadata.name, ready: .status.conditions[]|select(.type=="Ready").status, expiry: .status.notAfter, renewBefore: .spec.renewBefore}'
```
Pass: All `Ready=True`. Flag any expiring within 14 days.

## 2. Compute Days to Expiry
```
kubectl get certificate -A -o json | \
  python3 -c "
import sys, json
from datetime import datetime, timezone
data = json.load(sys.stdin)
for cert in data['items']:
    name = cert['metadata']['name']
    ns = cert['metadata']['namespace']
    expiry_str = cert.get('status', {}).get('notAfter', '')
    if expiry_str:
        expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
        days = (expiry - datetime.now(timezone.utc)).days
        status = 'CRITICAL' if days < 7 else 'WARNING' if days < 14 else 'OK'
        print(f'{status:10} {ns}/{name}: {days} days ({expiry_str})')
"
```

## 3. ClusterIssuer Health
```
kubectl get clusterissuer -o custom-columns='NAME:.metadata.name,READY:.status.conditions[0].status,REASON:.status.conditions[0].reason'
```
Pass: `letsencrypt-dns` Ready=True.

## 4. Live TLS Check (External Endpoints)
```
# ARGOCD_HOST / HUBBLE_HOST: platform hostnames under veridexeai.com (created at Gates 10 and 15)
echo | openssl s_client -connect "$ARGOCD_HOST:443" -servername "$ARGOCD_HOST" 2>/dev/null | openssl x509 -noout -dates -subject
echo | openssl s_client -connect "$HUBBLE_HOST:443" -servername "$HUBBLE_HOST" 2>/dev/null | openssl x509 -noout -dates -subject
```
Pass: `notAfter` > 14 days from today. Subject matches expected domain.

## 5. Internal CA (if used)
```
kubectl get clusterissuer | grep -i internal
kubectl get certificate -A | grep -i internal
```
Verify internal CA issuer and signed certificates are valid.

## 6. Traefik Default Certificate
```
kubectl get secret -n kube-system | grep -i tls
kubectl get secret -n kube-system argocd-server-tls -o jsonpath='{.data.tls\.crt}' 2>/dev/null | base64 -d | openssl x509 -noout -dates
```

## 7. CNPG TLS Certificates
```
kubectl get certificate -n data-plane 2>/dev/null
kubectl get secret -n data-plane | grep tls
```
Pass: CNPG cluster TLS certificates present and valid.

## Trigger Renewal (if needed)
```
kubectl annotate certificate <name> -n <ns> cert-manager.io/issue-once="true" --overwrite
```
Or delete the TLS secret to force re-issuance:
```
kubectl delete secret <tls-secret-name> -n <ns>
```

## Report
Table: namespace/cert | days remaining | status. CRITICAL (<7d), WARNING (<14d), OK.
