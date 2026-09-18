# Namespace promotion and rollback

1. Complete P0/P1 dependency inventory and observation evidence.
2. Add the complete namespace baseline under a staging/test path and validate
   intended allows and denials in `veridex-policy-test`.
3. Change the namespace map lifecycle from `planned` to `active` and move its
   Namespace manifest from `planned/` to `active/` in the same commit.
4. Land default denies and minimum allows before any workload replica starts.
5. Verify Argo resource-level health, Hubble flows, quotas, Pod Security and
   positive/negative connectivity tests.

Rollback policy or workload changes through Git. Do not roll back activation by
deleting a Namespace. Namespace objects carry Argo `Prune=false,Delete=false`;
decommissioning requires an inventory proving that no PVC, Secret, workload,
finalizer or production data remains, plus explicit operator authorization.

