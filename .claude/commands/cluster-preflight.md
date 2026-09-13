# cluster-preflight

Validate the K3s-HA cluster (entrepeai.com) is healthy before any deployment or change.

## 1. Node Readiness
```
kubectl get nodes -o wide
```
Pass: All nodes `Ready`, no `NotReady`, `SchedulingDisabled`, or version drift.

## 2. Control Plane Pods
```
kubectl get pods -n kube-system
```
Pass: CoreDNS (2 replicas), kube-proxy, metrics-server — all Running. No CrashLoopBackOff.

## 3. kube-vip
```
kubectl get pods -n kube-system -l app=kube-vip
kubectl get configmap -n kube-system kubevip
```
Pass: kube-vip pod Running on every server node. VIP (`kubevip_vip` in ansible/inventory/production/group_vars/all.yml) pingable from within cluster.

## 4. Cilium CNI
```
kubectl get pods -n kube-system -l k8s-app=cilium
kubectl get ciliumnode
```
Pass: cilium-agent Running on every node. No agents in `not-ready`. WireGuard tunnel established.

## 5. ArgoCD Health
```
kubectl get pods -n argocd
kubectl get applications -n argocd
```
Pass: All ArgoCD pods Running. No Application in `Degraded` or `Unknown` state.

## 6. cert-manager
```
kubectl get pods -n cert-manager
kubectl get clusterissuer letsencrypt-dns -o jsonpath='{.status.conditions[0].type}'
```
Pass: All pods Running. ClusterIssuer `Ready`.

## 7. External Secrets
```
kubectl get pods -n external-secrets
kubectl get clustersecretstore -o jsonpath='{.items[*].status.conditions[0].type}'
```
Pass: ESO pods Running. ClusterSecretStore `Ready`.

## 8. No Failing Workloads
```
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded | grep -v Completed
```
Pass: No output (all pods Running or Completed).

## Report
Output: PASS / FAIL per check. Block deployment on any FAIL.
