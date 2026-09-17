# minio-health

Validate MinIO object storage for the DIP platform (dip-documents, dip-artifacts buckets).

## 1. MinIO Pod Status
```
kubectl get pods -n data-plane -l app=dip-minio -o wide
```
Pass: MinIO pod Running. Note: standalone mode (single pod) — this is expected per dip-minio values.

## 2. MinIO API Reachability
```
kubectl exec -n data-plane -l app=dip-minio -- \
  mc alias set local http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD 2>/dev/null && \
  mc admin info local 2>/dev/null | head -20
```
Pass: Server responds, disk usage shown.

## 3. Bucket Inventory
```
kubectl exec -n data-plane -l app=dip-minio -- \
  mc ls local/ 2>/dev/null
```
Pass: `dip-documents` and `dip-artifacts` buckets exist.

## 4. Bucket Policies (not public)
```
kubectl exec -n data-plane -l app=dip-minio -- \
  mc anonymous get local/dip-documents 2>/dev/null
kubectl exec -n data-plane -l app=dip-minio -- \
  mc anonymous get local/dip-artifacts 2>/dev/null
```
Pass: Both buckets return `Access permission for ... is none` (no public access per purge:false,policy:none config).

## 5. Disk Usage
```
kubectl exec -n data-plane -l app=dip-minio -- \
  mc admin info local 2>/dev/null | grep -E 'used|total|available'
kubectl get pvc -n data-plane | grep minio
```
Pass: every MinIO data volume (direct local storage, plan Gate 26) is below the warning threshold defined in plan Gate 24. That threshold is not set yet.

## 6. Prometheus Scraping
```
kubectl get servicemonitor -n data-plane | grep minio
curl -s http://dip-minio.data-plane.svc:9000/minio/health/live 2>/dev/null
```
Pass: Health endpoint returns 200. ServiceMonitor or pod annotation `prometheus.io/scrape: "true"` present.

## 7. CNPG WAL Archive in dip-artifacts
```
kubectl exec -n data-plane -l app=dip-minio -- \
  mc ls local/dip-artifacts/cnpg/ 2>/dev/null | tail -5
```
Pass: Recent WAL files present (confirms CNPG is archiving successfully).

## 8. Credentials Secret
```
kubectl get secret -n data-plane | grep minio-credentials
```
Pass: `dip-minio-credentials` secret exists and decrypted.

## Report
Pod status, bucket inventory, disk usage, WAL archive presence, public access policy.
