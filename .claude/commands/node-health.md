# node-health

Detailed per-node health assessment for the K3s-HA cluster.

## 1. Node Status + Conditions
```
kubectl get nodes -o json | jq '.items[] | {name: .metadata.name, conditions: .status.conditions, allocatable: .status.allocatable}'
```
Check each node for: `MemoryPressure=False`, `DiskPressure=False`, `PIDPressure=False`, `Ready=True`.

## 2. Kubelet Version Consistency
```
kubectl get nodes -o custom-columns='NAME:.metadata.name,VERSION:.status.nodeInfo.kubeletVersion,OS:.status.nodeInfo.osImage'
```
Pass: All nodes running same k3s version (`v1.35.4+k3s1`). Flag any drift.

## 3. Node Resource Utilization
```
kubectl top nodes
```
Pass: CPU < 80%, Memory < 85% per node. Flag nodes over threshold.

## 4. Disk Usage on Nodes (via pod exec or Ansible)
```
ansible all -i ansible/inventory/hcloud.yml -m shell -a "df -h / /var/lib/rancher"
```
Pass: Root < 80%, rancher data dir < 80%.

## 5. Cilium Agent per Node
```
kubectl get pods -n kube-system -l k8s-app=cilium -o wide
```
Pass: One cilium-agent pod per node, all Running.

## 6. SPIRE Agent per Node
```
kubectl get pods -n spire-system -l app=spire-agent -o wide 2>/dev/null || echo "SPIRE agents managed by Cilium — check cilium-spire-agent daemonset"
kubectl get pods -n kube-system -l app=spire-agent -o wide 2>/dev/null
```
Pass: SPIRE agent Running on every node.

## 7. Node Events
```
kubectl get events -A --field-selector=involvedObject.kind=Node --sort-by='.lastTimestamp' | tail -20
```
Review: NodeNotReady, OOM, disk pressure events are failures.

## Report
Table: node | CPU% | MEM% | disk% | cilium | spire | conditions | verdict
