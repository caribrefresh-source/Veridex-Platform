# Gate 34 build status

Date: 2026-09-18

Status: **CODE COMPLETE — LIVE ROLLOUT PENDING**

## Delivered

- Permanent, synthetic-only `veridex-policy-test` namespace with restricted
  Pod Security and namespace deletion protection.
- Reachable Argo CD `policy-test` Application with prune enabled only for the
  namespace's disposable child resources.
- Tokenless default ServiceAccount plus an empty least-privilege Role and
  RoleBinding.
- Native CEL admission controls for wildcard Roles, privileged ClusterRole
  bindings, and cross-namespace ServiceAccount subjects.
- Digest-pinned restricted echo workload, ClusterIP Service, and two-sided
  NetworkPolicy allow rules under default deny.
- Positive, same-namespace negative, arbitrary-DNS, internet-egress, and
  cross-namespace recurring test Jobs.
- `scripts/verify-policy-test.ps1` for two-run admission, quota, Pod Security,
  cleanup, Argo, EndpointSlice, and Hubble evidence capture.

## Least-privilege audit

The default workload ServiceAccount has token automount disabled. Its Role has
no rules. Test Jobs use that identity and require no Kubernetes API access.
The external verification identity is intentionally not declared here: it is
an approved break-glass identity, checked at runtime, and is required because
the day-to-day `veridex-operator` identity cannot create test resources or
capture Hubble flows. Kubernetes RBAC cannot constrain delete by label, so any
such temporary authority must remain confined to this synthetic namespace;
the harness additionally deletes only its run label.

## Promotion gates

The feature must not be merged in one step. First merge and reconcile PR #83,
which preserves the old namespace path, adds `Prune=false,Delete=false` to all
existing Namespace objects, and removes automated namespace pruning. Verify
the stored child Application and live annotations. Only then may the active
path migration and Gate 34 feature revision merge.

Do not mark Reconciled, Running, or Verified from repository tests. Those
states require retained live evidence at the exact deployed main commit.
