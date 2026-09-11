# cnpg-cluster-health

Validate CloudNativePG PostgreSQL cluster health in the data-plane namespace.

## 1. Cluster Status
```
kubectl get cluster -n data-plane -o custom-columns='NAME:.metadata.name,PHASE:.status.phase,PRIMARY:.status.currentPrimary,READY:.status.readyInstances,INSTANCES:.status.instances'
```
Pass: Phase `Cluster in healthy state`. Primary elected. readyInstances == instances.

## 2. Pod Status
```
kubectl get pods -n data-plane -l cnpg.io/cluster -o wide
```
Pass: Primary pod Running. Replica pods Running. No Pending/CrashLoop.

## 3. Replication Lag
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT client_addr, state, write_lag, flush_lag, replay_lag FROM pg_stat_replication;"
```
Pass: Replicas in `streaming` state. Replay lag < 1 second.

## 4. WAL Archive Status
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT archived_count, failed_count, last_archived_wal, last_failed_wal FROM pg_stat_archiver;"
```
Pass: `failed_count = 0`. `last_archived_wal` recent (< 5 min ago). WAL archiving to MinIO S3 active.

## 5. Cluster Conditions
```
kubectl get cluster -n data-plane -o json | \
  jq '.items[].status.conditions[] | select(.status != "True" or .type | test("Degraded|Failed"))'
```
Pass: No Degraded or Failed conditions.

## 6. Scheduled Backups
```
kubectl get scheduledbackup -n data-plane
kubectl get backup -n data-plane --sort-by='.metadata.creationTimestamp' | tail -5
```
Pass: ScheduledBackup resource exists. Last backup Completed < 24h ago.

## 7. pgbackrest CronJobs
```
kubectl get cronjob -n data-plane | grep -i backup
kubectl get job -n data-plane --sort-by='.metadata.creationTimestamp' | tail -5
```
Pass: CronJobs scheduled. Most recent job Completed.

## 8. Connection Pool (if pgBouncer configured)
```
kubectl get pooler -n data-plane 2>/dev/null
```

## Report
Cluster phase, primary, replica lag, WAL archive status, last backup time, overall verdict.
