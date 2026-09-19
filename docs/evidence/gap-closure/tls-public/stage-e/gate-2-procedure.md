# Gate 2 — host-policy enforcement canary

## Scope

This procedure transitions one Cilium `reserved:host` endpoint from policy
audit mode to enforcement. The cluster-wide policies are already applied.
There is no `kubectl apply` step in this transition.

The canary order is:

1. `veridex-agent-2`
2. `veridex-agent-1`
3. control-plane nodes, with `veridex-server-1` last

Do not start a later node until the preceding node has remained clean for at
least 60 minutes.

## Hard prerequisites

All four are mandatory and must be established before the flip:

1. A fresh Netcup snapshot of the target node. Take it first because the VM
   pause can restart `cilium-agent`, recreate the host endpoint, and reset its
   runtime audit-mode setting.
2. A connected SSH session to the target node, held open.
3. An authenticated Netcup SCP Screen session with a root shell, held open.
4. A fresh baseline proving the target and every not-yet-promoted host
   endpoint have `PolicyAuditMode: Enabled`, every previously promoted host
   endpoint has `PolicyAuditMode: Disabled`, all five nodes are Ready, all
   nine Argo CD applications are Synced/Healthy, and required public probes
   pass.

If any prerequisite is absent, Gate 2 is blocked.

## Re-derive runtime identifiers

Never reuse endpoint or container IDs from an earlier run. On the node console:

```bash
crictl ps --name cilium-agent
crictl exec <container-id> cilium-dbg endpoint get \
  -l reserved:host \
  -o jsonpath='{$[0].id}'
```

The second command must return the same endpoint ID selected through the
Kubernetes path. If it does not, stop: the console rollback path is not proven.

## Arm observation

Observe the target host endpoint before and throughout the transition. At a
minimum, watch drop and policy-verdict events related to the endpoint, node/API
health, all Argo CD applications, and TCP `443`, `32537`, and `32538` on both
workers. UDP `8472` is the first internal signal because it carries inter-node
pod traffic.

Stop condition: any legitimate internal-source flow denied from
`10.2.0.0/16`, `10.44.0.0/16`, or `10.45.0.0/16`.

## Flip

After a clean five-minute pre-flip sample:

```bash
kubectl --kubeconfig ~/.kube/veridex-netcup-breakglass.yaml \
  -n kube-system exec <cilium-pod> -c cilium-agent -- \
  cilium-dbg endpoint config <endpoint-id> PolicyAuditMode=Disabled
```

Record start and completion timestamps and verify the setting reads
`PolicyAuditMode: Disabled`.

## Rollback

Primary, while Kubernetes access works:

```bash
kubectl --kubeconfig ~/.kube/veridex-netcup-breakglass.yaml \
  -n kube-system exec <cilium-pod> -c cilium-agent -- \
  cilium-dbg endpoint config <endpoint-id> PolicyAuditMode=Enabled
```

Fallback from the already-authenticated node console:

```bash
crictl exec <container-id> cilium-dbg endpoint config \
  <endpoint-id> PolicyAuditMode=Enabled
```

Do not use a Git revert as the operational rollback. It removes policy from
all five nodes and can reproduce the transient VXLAN gap from EG104 Finding 2.
The VM snapshot is disaster recovery, not the first-line rollback; the normal
remedy is returning the one endpoint to audit mode.

## Close

A clean canary requires at least 60 minutes with no legitimate internal drops,
the target node Ready, API readiness `ok`, all nine applications
Synced/Healthy, and required probes passing. Record evidence before preparing
the next node. A dirty canary is immediately returned to audit mode and Stage E
is paused until the policy is corrected.

## Source-of-truth limitation

The Cilium policy objects are declarative and inherited from Stage D. The
per-endpoint `PolicyAuditMode` setting is not a Kubernetes object and is not
continuously reconciled by Argo CD. Stage E therefore records desired runtime
state in `host-endpoint-policy-mode.json` and checks or reapplies it with
`scripts/reconcile-cilium-host-policy-mode.ps1`. This reduces configuration
drift but does not turn the setting into cluster-native declarative state.

Re-run the checker after every Cilium restart, node restart, provider
snapshot, or endpoint-ID change. Never store endpoint IDs in the registry;
the reconciler derives the current `reserved:host` endpoint each time.
