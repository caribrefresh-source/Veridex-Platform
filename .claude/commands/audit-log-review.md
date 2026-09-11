# audit-log-review

Review Kubernetes API audit logs for security events and anomalies.

## 1. Audit Policy Check
```
ansible servers -i ansible/inventory/hcloud.yml -m shell -a \
  "cat /etc/rancher/k3s/server/audit-policy.yaml" --limit "$(ansible servers -i ansible/inventory/hcloud.yml --list-hosts | grep -m1 -v 'hosts')" 2>/dev/null
```
Verify: Audit policy exists with RequestResponse level for sensitive verbs (secrets, exec, create, delete).

## 2. Audit Log File Presence
```
ansible servers -i ansible/inventory/hcloud.yml -m shell -a \
  "ls -lh /var/log/kubernetes/audit.log && tail -1 /var/log/kubernetes/audit.log | python3 -m json.tool | head -20"
```
Pass: Audit log exists and has recent entries (timestamp within last minute).

## 3. Query via Loki (recent exec events)
```
kubectl port-forward -n logging svc/loki-gateway 3100:80 &
curl -sG 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={job="audit"} |= "exec"' \
  --data-urlencode 'limit=20' | python3 -m json.tool | grep -E 'verb|user|resource|namespace'
```

## 4. Secret Access Events
```
curl -sG 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={job="audit"} |= "secrets" |= "get"' \
  --data-urlencode 'limit=30' | python3 -m json.tool | grep -E 'user|verb|name|namespace'
```
Review: Secret access by non-system accounts during off-hours is a security signal.

## 5. Service Account Privilege Usage
```
curl -sG 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={job="audit"} |= "system:serviceaccounts" |= "create"' \
  --data-urlencode 'limit=20'
```

## 6. Failed Auth Attempts
```
curl -sG 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={job="audit"} |= "\"code\":403"' \
  --data-urlencode 'limit=30'
```

## 7. Rclone S3 Sync Status
```
kubectl get cronjob -A | grep audit
kubectl get job -A | grep audit | tail -5
```
Verify: Audit log rclone sync CronJob running successfully. Logs archived to S3.

## Report
Recent exec events, secret access by non-system users, 403 count, S3 sync job status.
