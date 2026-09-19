# Gate 2 — `veridex-agent-2` enforcement canary

| | |
|---|---|
| **Verdict** | **PASS** |
| **Canary flip (UTC)** | Start `2026-09-19T11:51:30.0244222Z`; complete `2026-09-19T11:51:32.7047022Z` |
| **Final verification (UTC)** | `2026-09-19T13:12:42.9489556Z` |
| **Observed duration** | 81.17 minutes |
| **Tested repository state** | `c248d174b5aa554b051dbaea3349abe55d6e6534` on `fix/monitoring-data-ownership` |
| **Cluster identity** | `kube-system` UID `d7d8a462-c503-49ed-a1e0-899f372f9465` |
| **Target** | `veridex-agent-2`; private `10.2.1.101`; public `159.195.197.40` |
| **Runtime target after snapshot** | pod `cilium-t5rm6` UID `62aad6b4-b719-4d35-95bd-23e3930127da`; host endpoint `446` |

## Preconditions and recovery paths

- Netcup offline snapshot `gate2-pre-enforcement-20260919` was created for
  `veridex-agent-2`, disk `vda`, before the canary.
- An SSH session to `root@159.195.197.40` was established with the existing
  `veridex_netcup_ed25519` credential and held during the transition.
- An authenticated root shell was held in the Netcup SCP Screen console.
- The console path was proven with `crictl`: container `de8547c292e47`
  resolved the `reserved:host` endpoint to `446`, and its config showed
  `PolicyAuditMode: Enabled` before the flip.
- Primary and console rollback commands were prepared before enforcement.

## Snapshot-induced state change

Before the snapshot, agent-2 used host endpoint `107` with audit mode enabled.
The snapshot pause restarted the Cilium container once and recreated the host
endpoint as `446`. The recreated endpoint came up with
`PolicyAuditMode: Disabled`, unintentionally enabling enforcement before
observation was armed. It was immediately returned to
`PolicyAuditMode: Enabled`; the node and applications were allowed to converge
fully before the fresh baseline began.

This confirms the procedure's requirement to re-derive identifiers and
re-verify audit mode after every snapshot or agent restart.

## Policy identity

| Policy | UID | Generation | Valid |
|---|---|---:|---|
| `veridex-host-baseline` | `4d280bb6-9f10-44ff-b0ef-64c07f8f85b7` | 1 | True |
| `veridex-host-public-ingress` | `aa6999b7-bf5b-4650-84f5-d140cd24a8b0` | 1 | True |

The live baseline policy contained `fromCIDR: 10.2.0.0/16`. This was not
treated as sufficient by inspection alone: API-to-kubelet access and the
console rollback path were both exercised before the flip.

## Fresh baseline

Baseline timestamp: `2026-09-19T11:42:04.1239547Z`.

- All five nodes were Ready.
- All nine Argo CD applications were Synced/Healthy.
- Both cluster-wide policies were Valid.
- All five `reserved:host` endpoints reported `PolicyAuditMode: Enabled`.
- Agent-2 endpoint config had drop, policy-verdict, source-IP-verification,
  and trace notifications enabled.
- TCP `443`, `32537`, and `32538` succeeded on both `159.195.197.136` and
  `159.195.197.40`.
- API `/readyz` returned `ok`.
- A five-minute pre-flip monitor sample showed internal VXLAN UDP `8472` and
  control-plane traffic allowed. Background unsupported-IPv6 neighbor traffic
  and unsolicited world scans were classified separately from the internal
  stop condition.

## Transition and observation

Only the runtime endpoint setting changed:

```text
cilium-dbg endpoint config 446 PolicyAuditMode=Disabled
```

No policy manifest was applied or reverted.

Immediately after the flip, policy verdicts changed unsolicited world scans
on unapproved ports from `audit` to `deny`, while internal VXLAN and
control-plane flows continued to report `allow`. A focused monitor emitted no
`Policy denied` event whose source was in `10.2.0.0/16`, `10.44.0.0/16`, or
`10.45.0.0/16` during the observation window.

At final verification:

- Endpoint `446` remained `PolicyAuditMode: Disabled`.
- API `/readyz` returned `ok`.
- All five nodes were Ready.
- All nine Argo CD applications were Synced/Healthy.
- TCP `443`, `32537`, and `32538` succeeded on agent-2's public IP.
- No legitimate internal flow had triggered the stop condition.

## Result and next step

The `veridex-agent-2` enforcement canary passed. The endpoint remains in
enforcement mode; no rollback was performed. Record this result before
preparing `veridex-agent-1`. Agent-1 requires its own fresh snapshot, held SSH
and console sessions, re-derived runtime identifiers, clean baseline, and
explicitly authorized flip.
