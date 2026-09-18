# cert-rotation

Rotate TLS certificates across the Veridex netcup cluster (manual and forced rotation).

## 1. Current Certificate Status
Run /cert-expiry-check first to identify which certs need rotation.

## 2. cert-manager Auto-Renewal (verify)
cert-manager automatically renews 30 days before expiry. Check if auto-renewal is working:
```
kubectl describe certificate -A | grep -E 'Status|Renewal|Not After|Reason'
kubectl get events -A | grep cert-manager | grep -E 'Issued|Renewing|Failed' | tail -20
```
Pass: Renewals happening automatically. No `Failed` renewal events.

## 3. Force Renew a Specific Certificate
```
# Method 1: Delete the TLS secret (cert-manager re-issues immediately)
kubectl delete secret <tls-secret-name> -n <namespace>

# Method 2: Annotate to trigger re-issue
kubectl annotate certificate <cert-name> -n <namespace> cert-manager.io/issue-once="$(date +%s)" --overwrite

# Verify re-issue started
kubectl describe certificate <cert-name> -n <namespace> | grep -A5 'Status\|Message'
```

## 4. Rotate letsencrypt-dns ClusterIssuer Credentials
If DNS-01 credentials need rotation (none exist yet: veridexeai.com DNS is at Squarespace, which offers no DNS API, so no DNS-01 issuer is configured):
```
# Update the secret referenced by the ClusterIssuer
kubectl get clusterissuer letsencrypt-dns -o yaml | grep secretName
kubectl edit secret <dns-secret-name> -n cert-manager
# Or update the SOPS-encrypted source in Git and let Argo CD reconcile
```
After rotation: trigger re-issue on a test cert to verify DNS-01 still works.

## 5. K3s Internal Certificate Rotation
K3s auto-rotates internal certs annually. For manual rotation:
```
ansible k3s_servers -i ansible/inventory/production/hosts.yml -m shell -a \
  "systemctl stop k3s && k3s certificate rotate && systemctl start k3s" \
  --limit <server-node> 2>/dev/null
```
Note: Rolling rotation — one server at a time. Monitor etcd quorum.

## 6. CNPG PostgreSQL TLS
```
kubectl get certificate -n data-plane
kubectl delete secret -n data-plane $(kubectl get certificate -n data-plane -o jsonpath='{.items[0].spec.secretName}')
kubectl wait --for=condition=Ready certificate -n data-plane --all --timeout=120s
```

## 7. Verify Post-Rotation
```
kubectl get certificate -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,READY:.status.conditions[0].status,EXPIRY:.status.notAfter'
# ARGOCD_HOST / HUBBLE_HOST: platform hostnames under veridexeai.com (created at Gates 10 and 15)
echo | openssl s_client -connect "$ARGOCD_HOST:443" -servername "$ARGOCD_HOST" 2>/dev/null | openssl x509 -noout -dates
```
Pass: All certs Ready. Live endpoint TLS not-after is updated.

## Report
Which certs were rotated, pre/post expiry dates, any rotation failures.
