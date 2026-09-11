# redis-health

Validate Redis health — used as auth revocation cache (revoked:jti:*, revoked:user:*) in docintel namespace.

## 1. Redis Pod Status
```
kubectl get pods -n data-plane -l app=redis -o wide
kubectl get pods -n docintel -l app=auth-redis -o wide 2>/dev/null
```
Pass: Redis pod(s) Running.

## 2. Redis Ping
```
kubectl exec -n data-plane -l app=redis -- redis-cli ping 2>/dev/null || \
kubectl exec -n docintel -l app=auth-redis -- redis-cli ping 2>/dev/null
```
Pass: Returns `PONG`.

## 3. Memory Usage
```
kubectl exec -n data-plane -l app=redis -- redis-cli info memory 2>/dev/null | \
  grep -E 'used_memory_human|maxmemory_human|mem_fragmentation_ratio|maxmemory_policy'
```
Pass: `used_memory` < `maxmemory`. `maxmemory_policy` set (not `noeviction` for a cache).
Flag: `mem_fragmentation_ratio` > 1.5 (high fragmentation — consider restart).

## 4. Eviction Check
```
kubectl exec -n data-plane -l app=redis -- redis-cli info stats 2>/dev/null | \
  grep -E 'evicted_keys|keyspace_hits|keyspace_misses'
```
Pass: `evicted_keys = 0` for auth revocation cache. Evictions mean JWT blacklist entries are being lost.
Hit ratio: `keyspace_hits / (keyspace_hits + keyspace_misses)` > 80%.

## 5. Connected Clients
```
kubectl exec -n data-plane -l app=redis -- redis-cli info clients 2>/dev/null | \
  grep -E 'connected_clients|blocked_clients|tracking_clients'
```
Pass: `connected_clients` reasonable (< configured maxclients). `blocked_clients = 0`.

## 6. Auth Revocation Keys (auth-service specific)
```
kubectl exec -n data-plane -l app=redis -- \
  redis-cli scan 0 match "revoked:*" count 100 2>/dev/null | head -20
```
Review: Keys should have TTL matching JWT expiry. No keys without TTL.

## 7. Persistence (if enabled)
```
kubectl exec -n data-plane -l app=redis -- redis-cli info persistence 2>/dev/null | \
  grep -E 'rdb_last_save_time|rdb_last_bgsave_status|aof_enabled'
```
Note: For revocation cache, persistence may intentionally be disabled (lost keys on restart means users must re-authenticate — acceptable vs persistence overhead).

## 8. mTLS Policy Active (Cilium)
Verify the mutual-auth-auth-to-redis CiliumNetworkPolicy is enforcing:
```
kubectl get ciliumnetworkpolicy -n docintel mutual-auth-auth-to-redis -o jsonpath='{.spec.egress[0].authentication.mode}'
```
Pass: Returns `required`.

## Report
Pod status, PONG, memory headroom, eviction count, client count, revocation key sample, mTLS status.
