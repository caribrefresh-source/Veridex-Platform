# temporal-stuck-workflows

Find and triage stuck or long-running Temporal workflows in the ingestion pipeline.

## 1. Running Workflow Count
```
kubectl exec -n data-plane deployment/temporal-frontend -- \
  tctl --ns default wf list --query 'ExecutionStatus="Running"' --fields WorkflowId,RunId,StartTime,WorkflowType --limit 50 2>/dev/null
```
Alert: > 500 running = possible stuck workflow accumulation.

## 2. Long-Running Workflows (> 1 hour)
```
kubectl exec -n data-plane deployment/temporal-frontend -- \
  tctl --ns default wf list \
    --query 'ExecutionStatus="Running" AND StartTime < "'$(date -d '1 hour ago' --iso-8601=seconds)'"' \
    --fields WorkflowId,WorkflowType,StartTime --limit 20 2>/dev/null
```
Flag: Ingestion workflows should complete in < 5 minutes. Anything > 1 hour is stuck.

## 3. Failed Workflows (last 1h)
```
kubectl exec -n data-plane deployment/temporal-frontend -- \
  tctl --ns default wf list \
    --query 'ExecutionStatus="Failed" AND CloseTime > "'$(date -d '1 hour ago' --iso-8601=seconds)'"' \
    --fields WorkflowId,WorkflowType,CloseTime --limit 20 2>/dev/null
```
Review: Repeated failures of the same WorkflowType = systematic bug, not transient.

## 4. Timed-Out Workflows
```
kubectl exec -n data-plane deployment/temporal-frontend -- \
  tctl --ns default wf list --query 'ExecutionStatus="TimedOut"' --limit 10 2>/dev/null
```
Flag: Timeouts indicate activity execution exceeding `scheduleToCloseTimeout`.

## 5. Inspect a Stuck Workflow
```
kubectl exec -n data-plane deployment/temporal-frontend -- \
  tctl --ns default wf show --workflow_id <workflow-id> --run_id <run-id> 2>/dev/null | tail -30
```
Look for: Last activity, pending activities, schedule-to-start delays (worker pool exhaustion).

## 6. Terminate Stuck Workflow (if needed)
```
kubectl exec -n data-plane deployment/temporal-frontend -- \
  tctl --ns default wf terminate --workflow_id <workflow-id> --run_id <run-id> --reason "stuck > 1h manual terminate" 2>/dev/null
```
Note: Termination is immediate and irreversible. Workflow cannot be resumed.

## 7. Worker Health During Stuck Period
```
kubectl get pods -n data-plane -l app=ingestion-worker 2>/dev/null
kubectl logs -n data-plane -l app=ingestion-worker --since=1h --tail=100 | grep -E 'error|panic|failed|timeout'
```
Pass: Workers Running and processing. Stuck workflows correlate to worker errors?

## 8. Temporal DB Health
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT count(*) FROM temporal.executions WHERE status=1;" 2>/dev/null
```
Running executions count. Compare with tctl output.

## Report
Running/stuck count, failed/timed-out count in last hour, oldest workflow age, recommended terminations.
