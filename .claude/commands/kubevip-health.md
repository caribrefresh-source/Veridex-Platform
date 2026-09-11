# kubevip-health

Validate kube-vip HA VIP (10.1.0.100) for K3s API server high availability.

## 1. kube-vip Pod Status
```
kubectl get pods -n kube-system -l app=kube-vip -o wide
```
Pass: One kube-vip pod Running on EACH server node (DaemonSet). No missing nodes.

## 2. VIP Reachability
```
kubectl run vip-test --rm -it --restart=Never --image=busybox -- ping -c 3 10.1.0.100
```
Pass: VIP responds. Leader is elected.

## 3. Leader Election
```
kubectl logs -n kube-system -l app=kube-vip --tail=50 | grep -E 'leader|elected|VIP'
```
Pass: Logs show one node as leader with VIP bound. No rapid leader flapping.

## 4. API Server via VIP
```
kubectl --server=https://10.1.0.100:6443 get nodes 2>/dev/null || echo "Test from within cluster network"
```

## 5. Interface Binding (eth1 per config)
```
ansible servers -i ansible/inventory/hcloud.yml -m shell -a "ip addr show eth1 | grep 10.1.0.100 || echo 'VIP not on this node'"
```
Pass: Exactly one server node holds 10.1.0.100 on eth1.

## 6. ConfigMap Config
```
kubectl get configmap -n kube-system kubevip -o yaml
```
Verify: `vip_interface=eth1`, `vip_address=10.1.0.100`, `vip_leaseduration`, `vip_renewdeadline` set.

## Failure Recovery
If VIP unreachable: check kube-vip logs on all server nodes. Restart kube-vip pod on current leader node. VIP should migrate to another server within lease duration.

## Report
Pod status per node, VIP owner, leader log tail, API reachability verdict.
