# fluent-bit-health

Check Fluent Bit DaemonSet health and log pipeline integrity.

## 1. DaemonSet Status
```
kubectl get daemonset -A | grep fluent-bit
kubectl get pods -A -l app=fluent-bit -o wide
```
Pass: fluent-bit pods Running on ALL nodes. No Pending or CrashLoop.

## 2. Fluent Bit Logs (errors)
```
kubectl logs -A -l app=fluent-bit --tail=50 | grep -E 'error|Error|fail|Fail' | grep -v 'suppressed'
```
Pass: No persistent error output. Transient connection errors OK if recovering.

## 3. Metrics API
```
kubectl exec -A -l app=fluent-bit -- wget -qO- http://localhost:2020/api/v1/metrics 2>/dev/null | python3 -m json.tool | head -80
```
Check: `output.Loki.proc_records` incrementing = logs flowing. `output.Loki.errors` = 0.

## 4. Loki Output Records
```
kubectl exec -A -l app=fluent-bit -- wget -qO- http://localhost:2020/api/v1/metrics 2>/dev/null | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
for plugin in data.get('output', {}).values():
    print(f\"{plugin.get('name','?')}: proc={plugin.get('proc_records',0)} drop={plugin.get('drop_records',0)} err={plugin.get('errors',0)}\")
"
```
Pass: `proc_records` > 0 across all nodes. `drop_records` = 0.

## 5. K8s API Log Discovery
```
kubectl exec -A -l app=fluent-bit -- wget -qO- http://localhost:2020/api/v1/metrics 2>/dev/null | \
  python3 -m json.tool | grep -E 'input|kubernetes'
```
Pass: kubernetes_filter processing records for all namespaces.

## 6. Audit Log Pipeline
```
kubectl get configmap -A -l app=fluent-bit -o yaml | grep -E 'audit|kube-apiserver'
```
Verify: Audit log file path configured in Fluent Bit ConfigMap. Tailing `/var/log/kubernetes/audit.log`.

## 7. ConfigMap Review
```
kubectl get configmap -n logging fluent-bit-config 2>/dev/null -o yaml | grep -E 'Path|Host|Port|Match|Filter'
```
Verify: Loki output Host points to correct service. Namespace labels included.

## Report
Node coverage, records/sec flowing, drop count, Loki connection health, audit log pipeline.
