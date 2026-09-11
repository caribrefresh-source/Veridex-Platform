# cnpg-restore-test

Validate CNPG point-in-time recovery (PITR) capability from MinIO S3 backups.

## 1. Pre-Test: Verify Backup Exists
```
kubectl get backup -n data-plane --sort-by='.metadata.creationTimestamp' | tail -3
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  pgbackrest --stanza=db info 2>/dev/null | grep -E 'full|incr|diff|wal'
```
Pass: At least one `full` backup exists. WAL archive current.

## 2. Verify MinIO S3 Accessibility
```
kubectl exec -n data-plane deployment/dip-minio -- \
  mc ls local/dip-artifacts/base/ 2>/dev/null | head -5
kubectl exec -n data-plane deployment/dip-minio -- \
  mc ls local/dip-artifacts/WALS/ 2>/dev/null | tail -5
```
Pass: Base backup files present. Recent WAL files present.

## 3. PITR Restore (to a new cluster — NON-DESTRUCTIVE)
Create a test restore cluster pointing to same S3:
```yaml
# Apply temporarily, then delete after verification
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: dip-postgres-restore-test
  namespace: data-plane
spec:
  instances: 1
  bootstrap:
    recovery:
      source: dip-postgres-backup
      recoveryTarget:
        targetTime: "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)"
  externalClusters:
    - name: dip-postgres-backup
      barmanObjectStore:
        destinationPath: s3://dip-artifacts/
        endpointURL: http://dip-minio.data-plane.svc:9000
        s3Credentials:
          accessKeyId:
            name: minio-credentials
            key: access-key
          secretAccessKey:
            name: minio-credentials
            key: secret-key
  storage:
    size: 10Gi
    storageClass: hcloud-volumes
```
```
kubectl apply -f /tmp/cnpg-restore-test.yaml
kubectl wait --for=condition=Ready cluster/dip-postgres-restore-test -n data-plane --timeout=300s
```

## 4. Verify Restored Data
```
kubectl exec -n data-plane dip-postgres-restore-test-1 -- \
  psql -U postgres -c "SELECT version(); SELECT current_timestamp; SELECT count(*) FROM pg_stat_user_tables;"
```
Pass: PostgreSQL version matches production. Tables present. Data from before recovery target time accessible.

## 5. Cleanup Test Cluster
```
kubectl delete cluster -n data-plane dip-postgres-restore-test
kubectl delete pvc -n data-plane -l cnpg.io/cluster=dip-postgres-restore-test
```
Pass: Test cluster removed. No leftover PVCs.

## 6. Recovery Metrics
Document:
- Time from `kubectl apply` to `cluster Ready`: _____ minutes
- Recovery target time vs actual restore point: _____ minutes difference
- Data completeness: all tables present? _____ rows in key tables

## Report
Backup age, WAL continuity, restore time (RTO), recovery point accuracy (RPO test), cleanup confirmed.
