# alerting-review

Review alerting rules, firing alerts, and notification routing.

## 1. AlertManager / VMAlert Status
```
kubectl get pods -n observability -l app=vmalert 2>/dev/null || \
  kubectl get pods -A | grep -E 'alertmanager|vmalert'
```
Pass: Alert evaluation pod Running.

## 2. Firing Alerts
```
kubectl port-forward -n observability svc/victoriametrics 8428:8428 &
sleep 2
curl -s 'http://localhost:8428/api/v1/query?query=ALERTS{alertstate="firing"}' | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('data', {}).get('result', [])
for r in results:
    labels = r.get('metric', {})
    print(f\"{labels.get('alertname','?')} | severity={labels.get('severity','?')} | ns={labels.get('namespace','?')}\")
if not results:
    print('No alerts firing')
"
```
Pass: No critical alerts firing. Review any warning alerts.

## 3. Alert Rule Coverage
```
kubectl get prometheusrule,vmrule -A 2>/dev/null
```
Verify: Alert rules defined for:
- CNPG cluster down / replica lag > 30s
- NATS consumer lag > 100
- Temporal worker down
- MinIO disk >80%
- Node memory/CPU > 90%
- cert-manager certificate expiring < 14 days
- Pod CrashLoopBackOff

## 4. Critical Alert Check
```
curl -s 'http://localhost:8428/api/v1/rules' | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
groups = data.get('data', {}).get('groups', [])
for g in groups:
    for r in g.get('rules', []):
        if r.get('type') == 'alerting':
            print(r.get('name','?'), '|', r.get('health','?'), '|', r.get('lastEvaluation','?'))
"
```

## 5. Notification Channel Test
```
kubectl exec -n observability deployment/alertmanager -- \
  amtool alert add alertname=TestAlert severity=warning --insecure 2>/dev/null || \
  echo "Send test alert via UI or HTTP API"
```
Verify: Test alert delivered to configured notification channel (Slack, PagerDuty, email).

## 6. Silences
```
kubectl exec -n observability deployment/alertmanager -- \
  amtool silence query 2>/dev/null
```
Review: No forgotten silences masking real problems.

## Report
Firing alert list, rule count, critical rule coverage, notification channel health, active silences.
