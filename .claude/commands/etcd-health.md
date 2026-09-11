# etcd-health

Assess etcd cluster health (embedded in K3s server nodes).

## 1. Member List + Leader
```
kubectl exec -n kube-system -l component=etcd -c etcd -- \
  etcdctl member list --write-out=table 2>/dev/null || \
  kubectl exec -n kube-system $(kubectl get pods -n kube-system -l component=etcd -o name | head -1) -- \
  etcdctl --endpoints=https://127.0.0.1:2379 \
  --cacert=/var/lib/rancher/k3s/server/tls/etcd/server-ca.crt \
  --cert=/var/lib/rancher/k3s/server/tls/etcd/server-client.crt \
  --key=/var/lib/rancher/k3s/server/tls/etcd/server-client.key \
  member list
```
Pass: 3 members, 1 leader, all `started`.

## 2. Endpoint Health
```
kubectl exec -n kube-system -l component=etcd -- \
  etcdctl endpoint health --cluster
```
Pass: All endpoints `healthy`.

## 3. DB Size + Compaction
```
kubectl exec -n kube-system -l component=etcd -- \
  etcdctl endpoint status --write-out=table
```
Check `DB SIZE`. Pass: < 4GB. If approaching 8GB (quota), compact + defrag:
```
etcdctl compact $(etcdctl endpoint status --write-out=json | jq '.[0].Status.header.revision')
etcdctl defrag
```

## 4. Snapshot Freshness (K3s embedded)
```
ls -lh /var/lib/rancher/k3s/server/db/snapshots/
```
Pass: Snapshot < 12h old (K3s defaults every 12h).

## 5. Alarm Check
```
etcdctl alarm list
```
Pass: No alarms. `NOSPACE` alarm is critical — triggers read-only mode.

## 6. Raft Index Lag
From `endpoint status --write-out=table`, compare `RAFT INDEX` across members.
Pass: Lag < 100 between leader and followers.

## Report
Member list table, DB sizes, snapshot age, alarms. Flag anything approaching limits.
