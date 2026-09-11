# cnpg-backup-validation

Validate CloudNativePG backup integrity for the DIP PostgreSQL cluster.

## 1. Latest Backup Status
```
kubectl get backup -n data-plane --sort-by='.metadata.creationTimestamp' -o custom-columns='NAME:.metadata.name,STATUS:.status.phase,STARTED:.status.startedAt,COMPLETED:.status.completedAt,SIZE:.status.backupName'
```
Pass: Last backup `Completed`. Not older than 24 hours.

## 2. WAL Archive Continuity
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT last_archived_wal, last_archived_time, last_failed_wal, last_failed_time, failed_count FROM pg_stat_archiver;"
```
Pass: `failed_count = 0`. `last_archived_time` within last 10 minutes.

## 3. MinIO S3 Bucket Accessible
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT pg_walfile_name(pg_current_wal_lsn());"
```
Verify WAL is being archived by confirming object exists in MinIO `dip-artifacts` bucket:
```
kubectl exec -n data-plane -l app=dip-minio -- \
  mc ls local/dip-artifacts/cnpg/ 2>/dev/null | tail -5
```

## 4. pgbackrest Stanza Check
```
kubectl exec -n data-plane $(kubectl get pod -n data-plane -l cnpg.io/instanceRole=primary -o name | head -1) -- \
  pgbackrest --stanza=app info 2>/dev/null | head -30
```
Pass: Stanza exists, full backup present, WAL archiving active.

## 5. ScheduledBackup Config
```
kubectl get scheduledbackup -n data-plane -o yaml | grep -E 'schedule:|backupOwnerReference:|retentionPolicy:'
```
Verify: Schedule set (e.g., `0 2 * * *`), retention policy defined.

## 6. Recovery Target Test (dry-run)
```
kubectl get cluster -n data-plane -o jsonpath='{.items[0].spec.backup}'
```
Confirm: Recovery source, WAL archive, and MinIO credentials are all referenced.

## 7. Sealed Secret for Backup Credentials
```
kubectl get sealedsecret -n data-plane | grep -i backup
kubectl get secret -n data-plane | grep -i backup
```
Pass: Backup credentials secret exists and is decrypted.

## Report
Last backup age, WAL archive health, S3 accessibility, retention policy, restore capability verdict.
