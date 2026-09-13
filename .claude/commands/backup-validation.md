# backup-validation

Validate all backup systems across the Veridex netcup cluster.

## 1. CNPG PostgreSQL Backups
```
kubectl get backup -n data-plane --sort-by='.metadata.creationTimestamp' | tail -5
kubectl get scheduledbackup -n data-plane
kubectl get backup -n data-plane -o json | \
  jq '.items[-1] | {name: .metadata.name, status: .status.phase, startedAt: .status.startedAt, stoppedAt: .status.stoppedAt}'
```
Pass: Latest backup `Completed`. No backup older than 24h (ScheduledBackup every 1h).
Run /cnpg-backup-validation for full CNPG backup audit.

## 2. MinIO WAL Archive (CNPG pgbackrest)
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  pgbackrest --stanza=db --log-level-console=info info 2>/dev/null | head -30
```
Pass: WAL archive current to within 5 minutes.

## 3. MinIO Bucket Inventory
```
kubectl exec -n data-plane deployment/dip-minio -- \
  mc ls local/dip-artifacts/WALS/ --recursive --summarize 2>/dev/null | tail -5
kubectl exec -n data-plane deployment/dip-minio -- \
  mc ls local/dip-artifacts/base/ --recursive --summarize 2>/dev/null | tail -5
```
Pass: WAL files present and recent. Base backup present.

## 4. Vaultwarden Backup
```
kubectl get cronjob -n vaultwarden -o wide 2>/dev/null || kubectl get cronjob | grep vault
kubectl get job -n vaultwarden --sort-by='.metadata.creationTimestamp' | tail -3
```
Pass: Last Vaultwarden backup job Completed within 24h.

## 5. etcd Snapshot
```
ansible servers -i ansible/inventory/hcloud.yml -m shell -a \
  "ls -lh /var/lib/rancher/k3s/server/db/snapshots/" --limit 1 2>/dev/null | tail -5
```
Pass: Snapshot file exists, modified within last 24h (K3s default: every 12h).

## 6. Audit Log S3 Archive
```
kubectl get job -A | grep audit-rclone | tail -5
```
Pass: rclone sync job Completed recently.

## 7. Recovery Time Estimate
Based on CNPG setup:
- PITR to any point: restore base + WAL replay (RPO ~5min, RTO ~15-30min for 10GB)
- Full restore from S3: depends on backup size and network bandwidth

## Report
CNPG backup age, WAL continuity, MinIO storage health, Vaultwarden backup age, etcd snapshot age.
