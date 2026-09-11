# secret-management-audit

Audit secret management across the K3s-HA platform — SOPS, ESO, SealedSecrets.

## 1. No Plaintext Secrets in Git
```
git log --all --full-history -- '*.env' '**/.env' '**/secrets.yaml' '**/credentials*' 2>/dev/null | head -10
grep -rn 'password:\|token:\|secret:' gitops/ --include='*.yaml' | grep -v 'secretRef\|secretName\|SealedSecret\|ExternalSecret\|kind: Secret\|#'
```
Pass: No output. No plaintext credentials committed.

## 2. SOPS-Encrypted Files
```
find . -name '*.sops.yaml' -o -name '*.sops.json' | head -20
find ansible/ -name '*.yml' | xargs grep -l 'ENC\[AES256_GCM' 2>/dev/null
```
Verify: All sensitive Ansible vars are SOPS-encrypted.

## 3. SOPS Age Key in Environment (not in repo)
```
grep -rn 'AGE-SECRET-KEY\|age1' . --include='*.yaml' --include='*.json' --include='*.txt' 2>/dev/null | grep -v '.sops.yaml\|#'
```
Pass: No output. Age private key never committed.

## 4. External Secrets Operator Sync
```
kubectl get externalsecret -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,STATUS:.status.conditions[0].type,REASON:.status.conditions[0].reason'
```
Pass: All ExternalSecrets `Ready` with reason `SecretSynced`.

## 5. ClusterSecretStore Health
```
kubectl get clustersecretstore -o json | \
  jq '.items[] | {name: .metadata.name, status: .status.conditions[0].type, reason: .status.conditions[0].reason}'
```
Pass: All stores `Ready`.

## 6. SealedSecrets Decryption
```
kubectl get sealedsecret -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name'
kubectl get secret -A | grep -v 'kubernetes.io\|helm.sh\|default-token'
```
Cross-reference: Every SealedSecret should have a corresponding plain Secret (proof it decrypted).

## 7. Secret Rotation Age
```
kubectl get secret -A -o json | \
  jq '.items[] | select(.metadata.creationTimestamp != null) | {ns: .metadata.namespace, name: .metadata.name, age: .metadata.creationTimestamp}' | \
  python3 -c "import sys,json; from datetime import datetime,timezone; data=[json.loads(l) for l in sys.stdin if l.strip()]; [print(d['ns'],d['name'],d['age']) for d in data if (datetime.now(timezone.utc)-datetime.fromisoformat(d['age'].replace('Z','+00:00'))).days > 90]"
```
Review: Secrets older than 90 days should be evaluated for rotation.

## 8. Vaultwarden Backup
```
kubectl get cronjob -n vaultwarden 2>/dev/null || kubectl get cronjob | grep vault
kubectl get job | grep vault | tail -3
```
Pass: Vaultwarden backup CronJob scheduled and last job Completed.

## Report
Git scan clean, SOPS coverage, ESO sync status, SealedSecret count, rotation candidates.
