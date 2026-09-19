# Gate 2 — `veridex-agent-1` enforcement canary

| | |
|---|---|
| **Verdict** | **PASS** |
| **Canary flip (UTC)** | Start `2026-09-19T13:48:24.7189521Z`; complete `2026-09-19T13:48:27.5766847Z` |
| **Final verification (UTC)** | `2026-09-19T14:49:49.6195083Z` |
| **Observed duration** | 61.37 minutes |
| **Tested repository state** | `c248d174b5aa554b051dbaea3349abe55d6e6534` on `fix/monitoring-data-ownership` |
| **Cluster identity** | `kube-system` UID `d7d8a462-c503-49ed-a1e0-899f372f9465` |
| **Target** | `veridex-agent-1`; private `10.2.1.100`; public `159.195.197.136` |
| **Runtime target after snapshot** | pod `cilium-5gtr7` UID `a169ca71-9547-4b12-9395-d9e63442675c`; host endpoint `1116` |

## Preconditions and recovery paths

- Netcup offline snapshot `gate2-agent1-pre-enforcement-20260919` was
  created for `veridex-agent-1`, disk `vda`, before the canary.
- An SSH session to `root@159.195.197.136` was established with the existing
  `veridex_netcup_ed25519` credential and held during the transition.
- An authenticated root shell was held in the Netcup SCP Screen console.
- The console path was proven with `crictl`: container `e158fcc79c584`
  resolved the `reserved:host` endpoint to `1116`, and its config showed
  `PolicyAuditMode: Enabled` before the flip.
- Primary and console rollback commands were prepared before enforcement.

## Snapshot-induced state change

Before the snapshot, agent-1 used host endpoint `2075` with audit mode
enabled. The snapshot pause restarted the Cilium container once and recreated
the host endpoint as `1116`. The recreated endpoint came up with
`PolicyAuditMode: Disabled`, unintentionally enabling enforcement before
observation was armed.

This was detected immediately. Endpoint `1116` was explicitly returned to
`PolicyAuditMode: Enabled`, the node and applications were verified healthy,
and the console rollback path was proven before the fresh baseline and
controlled transition began. The later flip at
`2026-09-19T13:48:27.5766847Z` was therefore a real transition from audit to
enforcement, not a no-op.

This independently reproduces the agent-2 finding: endpoint-level audit mode
does not survive Cilium endpoint recreation. Every snapshot or agent restart
requires re-deriving the endpoint ID and re-verifying its runtime mode.

## Policy identity

| Policy | UID | Generation | Valid |
|---|---|---:|---|
| `veridex-host-baseline` | `4d280bb6-9f10-44ff-b0ef-64c07f8f85b7` | 1 | True |
| `veridex-host-public-ingress` | `aa6999b7-bf5b-4650-84f5-d140cd24a8b0` | 1 | True |

## Fresh staged baseline

Baseline timestamp: `2026-09-19T13:28:01.4736050Z`.

- All five nodes were Ready.
- All nine Argo CD applications were Synced/Healthy.
- Both cluster-wide policies were Valid.
- Agent-2 endpoint `446` remained in enforcement mode after its successful
  canary.
- Agent-1 endpoint `1116` and the three control-plane host endpoints reported
  `PolicyAuditMode: Enabled`.
- API `/readyz` returned `ok`.
- TCP `443`, `32537`, and `32538` succeeded on both worker public IPs.
- A five-minute pre-flip monitor sample showed internal VXLAN UDP `8472` and
  control-plane traffic allowed. Baseline unsupported-IPv6 neighbor traffic
  and unsolicited world scans were classified separately from the internal
  stop condition.

## Transition and observation

Only the runtime endpoint setting changed:

```text
cilium-dbg endpoint config 1116 PolicyAuditMode=Disabled
```

No policy manifest was applied or reverted.

Immediately after the flip, unsolicited world traffic to unapproved ports was
denied while internal VXLAN traffic from the control-plane nodes and agent-2
continued to be allowed. A focused monitor emitted no `Policy denied` event
whose source was in `10.2.0.0/16`, `10.44.0.0/16`, or `10.45.0.0/16` during
the observation window.

At final verification:

- Endpoint `1116` remained `PolicyAuditMode: Disabled`.
- Agent-2 endpoint `446` also remained in enforcement mode.
- API `/readyz` returned `ok`.
- All five nodes were Ready.
- All nine Argo CD applications were Synced/Healthy.
- TCP `443`, `32537`, and `32538` succeeded on both worker public IPs.
- No legitimate internal flow triggered the stop condition.

## Result and next step

The `veridex-agent-1` enforcement canary passed. Both worker host endpoints
remain in enforcement mode; no rollback was performed. Before any
control-plane transition, prepare a control-plane-specific runbook that checks
etcd quorum and membership, kube-vip/VIP operation, API access through the
expected endpoint, Cilium health, and independent provider-console recovery.
Enforce one server at a time in the order `server-2`, `server-3`, then
`server-1`, with a strict health and observation gate between nodes.
