# Open remediation register

Historical gate evidence remains immutable. This register records corrective work without rewriting the original verdicts.

| Finding | Repository remediation | Live action required | Closure evidence | State |
| --- | --- | --- | --- | --- |
| Gate 10 broad Argo CD PAT | Bootstrap rejects classic PAT scopes and Git contents write permission | Fine-grained token deployed and verified; superseded credential retained by explicit operator direction and excluded from Argo CD | validator PASS; Argo Synced/Healthy at `53b3c1f1d012e203c7238c54289e6469a32efdf1` | Rotation complete; retained old credential is accepted residual risk |
| B2 plaintext and exposure | Ansible suppresses task output and diffs; minimum-scope key documented | Select Gate 21 runtime secret mechanism, deploy it, rotate key | no Git/log leak, scoped-key proof, upload and isolated restore | Partial; runtime plaintext remains |
| Gate 9 native-uploader mismatch | Governing plan names b2-CLI sidecar as implemented producer | Re-run upload/retention/download/restore at Gate 17 | pinned versions, alert failure test, checksum and restore | Repository reconciled; live Gate 17 pending |
| Gate 6 failed test baseline | Capacity/Cilium metrics retained; original record preserved | Re-run full suite, classify every failure, require clean scoped baseline before Gate 30 enforcement | full raw result plus positive/negative policy tests | Live test pending |
| Migration inventory | Version-controlled disposition register created | Reconcile live source objects and populate measurements | every live object has one disposition and rollback | Source access required |
