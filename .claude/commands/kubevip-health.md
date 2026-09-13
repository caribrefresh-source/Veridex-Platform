# kubevip-health

Validate kube-vip HA VIP (`kubevip_vip` in ansible/inventory/production/group_vars/all.yml) for K3s API server high availability.

Set it once before running the commands below:

    VIP=$(awk -F'"' '/^kubevip_vip:/{print $2}' ansible/inventory/production/group_vars/all.yml)

## 1. kube-vip Pod Status
```
kubectl get pods -n kube-system -l app=kube-vip -o wide
```
Pass: One kube-vip pod Running on EACH server node (DaemonSet). No missing nodes.

## 2. VIP Reachability
```
kubectl run vip-test --rm -it --restart=Never --image=busybox -- ping -c 3 "$VIP"
```
Pass: VIP responds. Leader is elected.

## 3. Leader Election
```
kubectl logs -n kube-system -l app=kube-vip --tail=50 | grep -E 'leader|elected|VIP'
```
Pass: Logs show one node as leader with VIP bound. No rapid leader flapping.

## 4. API Server via VIP
```
kubectl --server="https://$VIP:6443" get nodes 2>/dev/null || echo "Test from within cluster network"
```

## 5. Interface Binding (eth1 per config)
```
ansible k3s_servers -i ansible/inventory/production/hosts.yml -m shell -a "ip addr show eth1 | grep $VIP || echo 'VIP not on this node'"
```
Pass: Exactly one server node holds the VIP on eth1.

## 6. ConfigMap Config
```
kubectl get configmap -n kube-system kubevip -o yaml
```
Verify: `vip_interface=eth1`, `vip_address` equal to the inventory's `kubevip_vip`, `vip_leaseduration`, `vip_renewdeadline` set.

## Failure Recovery
If VIP unreachable: check kube-vip logs on all server nodes. Restart kube-vip pod on current leader node. VIP should migrate to another server within lease duration.

## Report
Pod status per node, VIP owner, leader log tail, API reachability verdict.
