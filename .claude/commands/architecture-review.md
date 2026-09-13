# architecture-review

Review the overall K3s-HA + DIP platform architecture for soundness and gaps.

## 1. Control Plane Architecture
```
kubectl get nodes -l node-role.kubernetes.io/control-plane -o wide
kubectl get pods -n kube-system | grep -E 'kube-apiserver|kube-controller|kube-scheduler|etcd'
```
Verify: 3 server nodes (HA). kube-vip VIP on eth1 (`kubevip_vip` in ansible/inventory/production/group_vars/all.yml) for API HA.

## 2. CNI and Network Architecture
```
kubectl get pods -n kube-system -l k8s-app=cilium -o wide
kubectl get ciliumnode | awk '{print $1, $2, $3}'
```
Verify: Cilium with WireGuard encryption (tunnelProtocol: vxlan, not wireguard — known gotcha).
SPIFFE/SPIRE mTLS on 4 critical paths.

## 3. GitOps Architecture
```
kubectl get application -n argocd -o custom-columns='NAME:.metadata.name,WAVE:.metadata.annotations.argocd\.argoproj\.io/sync-wave,HEALTH:.status.health.status'
```
Verify: Sync-wave ordering correct (infra → platform → apps). ArgoCD self-manages.

## 4. Data-Plane Architecture
```
kubectl get pods -n data-plane -o wide
kubectl get svc -n data-plane
```
Verify services present: CNPG (PostgreSQL), MinIO (S3), NATS (JetStream), Redis (auth revocation), Temporal (workflow engine).
KEDA ScaledObjects for ingestion-api scaling.

## 5. Ingress Architecture
```
kubectl get ingressroute -A --no-headers | wc -l
kubectl get middleware -n kube-system -o wide
```
Verify: Single ingress (Traefik v3.7 hostNetwork). ForwardAuth on all app routes. Coraza WAF + CrowdSec bouncer.

## 6. Secret Architecture
```
kubectl get clustersecretstore
kubectl get externalsecret -A --no-headers | wc -l
kubectl get sealedsecret -A --no-headers | wc -l
```
Verify: ESO + SealedSecrets dual approach. SOPS for Ansible vars.

## 7. Observability Architecture
```
kubectl get pods -n observability -o wide 2>/dev/null || kubectl get pods -n monitoring -o wide 2>/dev/null
```
Verify: VictoriaMetrics (metrics), Loki (logs), Fluent Bit (log shipping), Hubble (network flows).

## 8. Known Architectural Constraints
- Traefik hostNetwork = node-local; single point of ingress per node
- MinIO single-node = not HA (30Gi PVC, CNPG WAL archive only backup)
- NATS without clustering = single-node JetStream
- Redis without sentinel/cluster = single-node (auth revocation only, not session store)
- etcd embedded in K3s (not external) = simpler but coupled to node lifecycle

## 9. Architecture Debt
Review gitops/ for TODOs or FIXME comments:
```
grep -rn 'TODO\|FIXME\|HACK\|WORKAROUND\|temp\|temporary' gitops/ ansible/ --include='*.yaml' --include='*.yml' | grep -v '.git'
```

## Report
HA coverage per tier, known single points of failure, architecture debt items, recommendations.
