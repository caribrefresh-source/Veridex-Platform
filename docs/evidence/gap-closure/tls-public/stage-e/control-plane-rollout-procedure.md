# Stage E — control-plane host-policy rollout

## Purpose and order

This procedure promotes the three control-plane host endpoints after both
worker canaries have passed. Change exactly one server at a time:

1. `veridex-server-3`
2. `veridex-server-2`
3. `veridex-server-1`

`veridex-server-1` is last because the SSH tunnel used by both local
kubeconfigs terminates there. At the 2026-09-19 preflight,
`veridex-server-2` was both the etcd leader and the kube-vip lease holder, so
the non-leader/non-holder `veridex-server-3` was promoted first. Re-evaluate
etcd leadership and the lease holder immediately before each later promotion;
do not treat this recorded order as a substitute for the live check.

## Hard prerequisites for each server

All items are mandatory:

1. The preceding node has completed a clean 60-minute observation window and
   its evidence is saved.
2. A current, separately named K3s etcd snapshot exists, with its path, size,
   creation time, and SHA-256 recorded. Creating the logical etcd snapshot must
   not restart K3s or Cilium.
3. A root SSH session to the target is established and held.
4. A Netcup SCP Screen console is authenticated to a root shell and held.
5. From the console, `crictl` independently resolves the current Cilium
   container and `reserved:host` endpoint ID.
6. The target endpoint is `PolicyAuditMode: Enabled`; previously promoted
   endpoints are `Disabled`; later endpoints remain `Enabled`.
7. The full baseline below is clean.

If any item is missing, stop. Do not substitute a second Kubernetes-dependent
path for the provider console.

## Snapshot warning

An offline provider snapshot pauses the VM and can restart Cilium. Endpoint
recreation discards the imperative audit-mode setting and defaults the new
endpoint to enforcement. Prefer the non-disruptive K3s logical etcd snapshot
for the normal control-plane recovery point. If a provider snapshot is
required separately, treat the restart as a potential enforcement transition:
re-derive the endpoint, restore audit mode immediately if necessary, and begin
the baseline again. Never pause or snapshot more than one etcd member at once.

## Baseline

Record all of the following immediately before the transition:

- five nodes Ready;
- API `/readyz?verbose`, including `etcd` and `etcd-readiness`, passing;
- all three control-plane members present and healthy;
- all three kube-vip pods Running and the private API VIP reachable;
- all nine Argo CD applications Synced/Healthy;
- Cilium status healthy on all five nodes;
- endpoint IDs and audit modes for all five host endpoints;
- SSH connectivity to all control-plane nodes;
- required public probes on both workers;
- a five-minute target-endpoint verdict sample showing internal VXLAN UDP
  `8472` and control-plane traffic allowed.

## Observation and stop condition

Before the flip, start:

- a full drop/policy-verdict stream related to the target host endpoint;
- a focused watcher for policy-denied sources in `10.2.0.0/16`,
  `10.44.0.0/16`, and `10.45.0.0/16`;
- a one-minute health loop covering API readiness, etcd readiness, kube-vip,
  nodes, applications, Cilium, SSH, and worker probes.

Stop immediately on any legitimate internal denial, loss of an etcd member or
quorum, API/VIP failure, node NotReady state, unhealthy application, Cilium
failure, or loss of the target's recovery paths.

## Flip

Only the imperative endpoint setting changes:

```bash
kubectl --kubeconfig ~/.kube/veridex-netcup-breakglass.yaml \
  -n kube-system exec <cilium-pod> -c cilium-agent -- \
  cilium-dbg endpoint config <endpoint-id> PolicyAuditMode=Disabled
```

Record start and completion timestamps and immediately verify the setting.
There is no `kubectl apply` step.

## Rollback

Primary:

```bash
kubectl --kubeconfig ~/.kube/veridex-netcup-breakglass.yaml \
  -n kube-system exec <cilium-pod> -c cilium-agent -- \
  cilium-dbg endpoint config <endpoint-id> PolicyAuditMode=Enabled
```

Console fallback:

```bash
crictl exec <container-id> cilium-dbg endpoint config \
  <endpoint-id> PolicyAuditMode=Enabled
```

Do not use Git revert or etcd/VM restoration as the first-line endpoint
rollback. Restore the one endpoint to audit mode. Snapshot restoration is for
cluster-state disaster recovery only.

## Per-node exit gate

Observe for at least 60 minutes. The node passes only if API and etcd readiness
remain healthy, all five nodes remain Ready, kube-vip and the private VIP
remain healthy, all applications remain Synced/Healthy, Cilium remains
healthy, worker probes pass, recovery access remains available, and no
legitimate internal flow is denied. Save evidence before preparing the next
server.

## Final closure

After `veridex-server-1` passes, verify all five host endpoints are enforcing
and repeat the complete cluster-wide gate. Record the recovery owner, snapshot
validator, and authority responsible for declaring recovery complete.
