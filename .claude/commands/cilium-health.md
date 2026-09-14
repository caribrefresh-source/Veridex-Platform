# cilium-health

Full Cilium CNI health check for the Veridex netcup cluster.

## 1. Cilium Agent Status
```
kubectl get pods -n kube-system -l k8s-app=cilium -o wide
kubectl exec -n kube-system -l k8s-app=cilium -c cilium-agent -- cilium status --brief
```
Pass: All agents `Running`. Status shows `OK` for BPF, IPAM, kube-proxy replacement.

## 2. Cilium Node Status
```
kubectl get ciliumnode -o custom-columns='NODE:.metadata.name,IPAM:.spec.ipam.podCIDRs[0],HEALTH:.status.ipam.operator-status.error'
```
Pass: All nodes have assigned pod CIDR, no IPAM errors.

## 3. WireGuard Encryption
```
kubectl exec -n kube-system -l k8s-app=cilium -c cilium-agent -- cilium encrypt status
```
Pass: `WireGuard` encryption enabled, peer count matches node count - 1.

## 4. Network Policy Enforcement
```
kubectl exec -n kube-system -l k8s-app=cilium -c cilium-agent -- cilium policy get | head -40
```
Pass: Policies loaded. Count > 0.

## 5. Hubble Status
```
kubectl exec -n kube-system -l k8s-app=cilium -c cilium-agent -- cilium status | grep -i hubble
```
Pass: Hubble enabled, observer running.

## 6. Endpoint Health
```
kubectl exec -n kube-system -l k8s-app=cilium -c cilium-agent -- cilium endpoint list | grep -v ready | grep -v ENDPOINT
```
Pass: No endpoints in `not-ready` state. All `ready`.

## 7. SPIRE Integration (mTLS)
```
kubectl get pods -n kube-system -l app=spire-server 2>/dev/null
kubectl exec -n kube-system -l k8s-app=cilium -- cilium status | grep -i spire
```
Pass: SPIRE server running. Cilium shows SPIRE connected for mutual auth.

## 8. Connectivity Test (if safe to run)
```
kubectl apply -f https://raw.githubusercontent.com/cilium/cilium/main/examples/kubernetes/connectivity-check/connectivity-check.yaml --dry-run=client
```
Or check recent Hubble flows for dropped traffic.

## Report
Agent count, encryption status, endpoint health, SPIRE status, any dropped flows from Hubble.
