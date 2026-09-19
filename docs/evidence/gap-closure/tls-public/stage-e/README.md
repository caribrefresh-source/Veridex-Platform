# Stage E evidence status

Stage E reuses the cluster-wide Cilium policy objects delivered and reviewed
in Stage D. It does not introduce a separate policy manifest. Its operational
change is the imperative `PolicyAuditMode` setting on each node's current
`reserved:host` endpoint.

## Ladder interpretation

| Cell | Status | Precise meaning |
|---|---|---|
| Coded | Qualified pass | The policy logic is coded in the Stage D manifests; Stage E adds no policy manifest. |
| Declared | Qualified pass | The policy objects are declared in Git. Desired endpoint modes are recorded in `host-endpoint-policy-mode.json`, but no in-cluster controller continuously reconciles them. |
| Applied | Runtime evidence required | Each node record must show the exact endpoint, timestamp, command result, and post-change mode. |
| Observed | Per-node | Requires a clean 60-minute window and the health, connectivity, and verdict checks defined by the procedures. |
| Verified | Pending full closure | Requires all five per-node records, a final cluster-wide gate, and preservation of this evidence through review and merge. |

Neither a green `Coded` cell nor a green `Declared` cell means that
`PolicyAuditMode=Disabled` is reconciled by GitOps. Endpoint recreation can
change the runtime state and endpoint ID. Run the versioned checker after any
Cilium restart, node restart, provider snapshot, or endpoint-ID change:

```powershell
./scripts/reconcile-cilium-host-policy-mode.ps1 -Action Check
```

If the checked-in desired state is correct and an authorized operator has
validated the console rollback path, reconciliation is explicit:

```powershell
./scripts/reconcile-cilium-host-policy-mode.ps1 `
  -Action Reconcile -ConfirmProductionChange -WhatIf
```

Remove `-WhatIf` only inside an approved per-node change window. A Git revert
is not the runtime rollback; set the affected endpoint back to
`PolicyAuditMode=Enabled` as documented in the procedures.
