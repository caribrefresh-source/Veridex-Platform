# loki-log-review

Query Loki for errors, crashes, and anomalies across the Veridex platform.

## 1. Loki Stack Health
```
kubectl get pods -n logging 2>/dev/null || kubectl get pods -A | grep loki
kubectl get pods -n monitoring | grep loki 2>/dev/null
```
Pass: Loki and Loki gateway pods Running.

## 2. Fluent Bit Health
```
kubectl get daemonset -A | grep fluent
kubectl get pods -A -l app=fluent-bit | grep -v Running
```
Pass: fluent-bit DaemonSet running on all nodes. No pods in Error/CrashLoop.

## 3. Error Rate by Namespace (last 1 hour)
Using Loki via port-forward or kubectl exec:
```
kubectl port-forward -n logging svc/loki-gateway 3100:80 &
curl -s -G 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query=sum by (namespace) (count_over_time({level=~"error|ERROR|Error"}[1h]))' \
  --data-urlencode 'start='$(date -d '1 hour ago' +%s)'000000000' \
  --data-urlencode 'end='$(date +%s)'000000000' | python3 -m json.tool
```

## 4. CrashLoop Signals
```
# LogQL query for recent crash/restart logs
{namespace="data-plane"} |= "panic" or {namespace="data-plane"} |= "fatal" or {namespace="data-plane"} |= "OOMKilled"
```

## 5. Auth Failures (docintel)
```
# LogQL
{namespace="docintel"} |= "unauthorized" or {namespace="docintel"} |= "401" or {namespace="docintel"} |= "authentication failed"
```
Review: Elevated auth failures may indicate brute force or misconfigured clients.

## 6. Traefik Access Logs
```
{namespace="kube-system", app="traefik"} | json | status >= 500
```
Review: 5xx errors from Traefik indicate backend service issues.

## 7. CNPG/PostgreSQL Errors
```
{namespace="data-plane"} |= "FATAL" or {namespace="data-plane"} |= "connection refused" or {namespace="data-plane"} |= "too many connections"
```

## 8. Audit Log Anomalies
```
{namespace="logging"} |= "exec" or {namespace="logging"} |= "secrets" |= "get"
```
Flag: exec into pods, secret access in audit logs during off-hours.

## 9. Log Volume Check (Fluent Bit output rate)
```
kubectl exec -A -l app=fluent-bit -- \
  wget -qO- http://localhost:2020/api/v1/metrics | python3 -m json.tool | grep -E 'output\|records'
```

## Report
Error rate per namespace, CrashLoop signals, auth failure count, 5xx rate, audit anomalies.
