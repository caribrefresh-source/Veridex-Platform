# postgres-performance-review

Review PostgreSQL performance metrics in the DIP CloudNativePG cluster.

## 1. Slow Queries (> 1 second)
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state FROM pg_stat_activity WHERE (now() - pg_stat_activity.query_start) > interval '1 second' AND state != 'idle' ORDER BY duration DESC LIMIT 20;"
```

## 2. Index Hit Ratio (should be > 99%)
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT schemaname, tablename, round(heap_blks_hit::numeric/(heap_blks_hit+heap_blks_read+1)*100, 2) AS cache_hit_ratio FROM pg_statio_user_tables ORDER BY cache_hit_ratio ASC LIMIT 20;"
```
Pass: All tables > 95% cache hit ratio.

## 3. Table Bloat
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT schemaname, tablename, n_dead_tup, n_live_tup, round(n_dead_tup::numeric/nullif(n_live_tup,0)*100,2) AS dead_ratio FROM pg_stat_user_tables WHERE n_dead_tup > 1000 ORDER BY dead_ratio DESC LIMIT 20;"
```
Pass: Dead tuple ratio < 10%. If higher, trigger VACUUM.

## 4. Connection Count
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```
Pass: Total connections < 80% of `max_connections`. No large pool of `idle in transaction`.

## 5. Lock Waits
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT pid, wait_event_type, wait_event, query, pg_blocking_pids(pid) AS blocked_by FROM pg_stat_activity WHERE wait_event_type = 'Lock';"
```
Pass: No persistent lock waits (> 30 seconds).

## 6. Database Size
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) AS size FROM pg_database ORDER BY pg_database_size(datname) DESC;"
```
Review: Growth trend. Flag if approaching PVC size.

## 7. PVC Utilization
```
kubectl get pvc -n data-plane | grep -i cnpg
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- df -h /var/lib/postgresql/data
```
Pass: PVC < 75% full.

## 8. autovacuum Activity
```
kubectl exec -n data-plane -l cnpg.io/instanceRole=primary -- \
  psql -U postgres -c "SELECT schemaname, tablename, last_autovacuum, last_autoanalyze FROM pg_stat_user_tables WHERE last_autovacuum IS NOT NULL ORDER BY last_autovacuum DESC LIMIT 10;"
```
Pass: autovacuum running regularly on all tables.

## Report
Slow query list, cache hit ratios, bloat table, connection counts, lock waits, DB size, PVC usage.
