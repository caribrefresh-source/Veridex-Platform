# Gate 34 namespace verification closure

- Verification date: 2026-09-19 UTC
- Deployed revision: `4d4b26591f179bdf73c4e1d19b5605ecbd2b6595`
- Namespace: `veridex-policy-test`
- Namespace UID: `75acbe48-0c4c-4c75-8e5a-098802ca82bf`
- Result: **PASS — two consecutive complete runs**

## Maturity decision

The namespace capability satisfies all six maturity levels: Specified, Coded,
Declared, Reconciled, Running, and Verified. This record closes the final
Verified condition with two consecutive successful executions of every Gate 34
functional and failure suite.

## Reconciled and running state

At evidence capture, the root, cluster namespace, cluster policy, and policy-test
Argo CD applications were Synced/Healthy at the deployed revision. The namespace
was Active with Pod Security Admission `restricted` enforcement and retained UID
`75acbe48-0c4c-4c75-8e5a-098802ca82bf`.

The digest-pinned echo workload reported one available and one ready replica:

```text
busybox:1.37.0@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0
```

Its Service had a ready EndpointSlice at `10.44.3.99`.

## Consecutive run 1

| Suite | Job | Result |
| --- | --- | --- |
| Allowed connectivity | `policy-test-allowed-29829843` | `POLICY_TEST_ALLOWED_PASS` |
| Admission and quota | `policy-test-admission-29829844` | `POLICY_ADMISSION_VERIFICATION_PASS` |
| Cross-namespace denial | `policy-test-cross-namespace-denied-29829844` | `POLICY_TEST_CROSS_NAMESPACE_DENIED_PASS` |
| Same-namespace and egress denial | `policy-test-denied-29829844` | `POLICY_TEST_DENIED_PASS` |
| Hubble evidence | `policy-test-hubble-29829844` | `POLICY_TEST_HUBBLE_PASS` |

The admission suite confirmed HTTP 403 rejection for a wildcard Role, a
`cluster-admin` RoleBinding, a privileged Pod under restricted PSA, and a Pod
exceeding ResourceQuota. Label-scoped cleanup reported zero residue.

Hubble observed both permitted and denied flows. The captured first-run summary
contained 403 `FORWARDED`, 26 `DROPPED`, and 26 `POLICY_DENIED` reason records.

## Consecutive run 2

| Suite | Job | Start (UTC) | Completion (UTC) | Result |
| --- | --- | --- | --- | --- |
| Allowed connectivity | `policy-test-allowed-29829845` | 04:05:00 | 04:05:05 | `POLICY_TEST_ALLOWED_PASS` |
| Admission and quota | `policy-test-admission-29829846` | 04:06:00 | 04:06:07 | `POLICY_ADMISSION_VERIFICATION_PASS` |
| Cross-namespace denial | `policy-test-cross-namespace-denied-29829846` | 04:06:00 | 04:06:07 | `POLICY_TEST_CROSS_NAMESPACE_DENIED_PASS` |
| Same-namespace and egress denial | `policy-test-denied-29829846` | 04:06:00 | 04:06:15 | `POLICY_TEST_DENIED_PASS` |
| Hubble evidence | `policy-test-hubble-29829846` | 04:06:00 | 04:07:07 | `POLICY_TEST_HUBBLE_PASS` |

The second admission suite independently confirmed all four HTTP 403 rejection
cases and zero cleanup residue. Hubble recorded 406 `FORWARDED` verdicts, 26
`DROPPED` verdicts, and 26 `POLICY_DENIED` reason records.

## Exit-gate assertions

- Positive DNS and allowed client-to-Service traffic: PASS.
- Same-namespace unauthorized traffic denial: PASS.
- Arbitrary DNS and external-egress denial: PASS.
- ResourceQuota rejection: PASS.
- Restricted Pod Security rejection: PASS.
- Wildcard Role and `cluster-admin` RoleBinding rejection: PASS.
- Cross-namespace traffic denial: PASS.
- Label-scoped cleanup with unchanged namespace UID: PASS.
- Hubble `FORWARDED`, `DROPPED`, and `POLICY_DENIED` evidence: PASS.
- Two consecutive complete successful runs: PASS.

## Post-run hygiene and capacity

No ConfigMaps carrying `veridex.io/policy-test-run` remained. At capture time the
quota reported 12 of 20 Jobs and 13 of 20 Pods, leaving sufficient headroom for
the next scheduled execution. Job-history limits and staggered schedules keep
that usage bounded.

## Interpretation note

Kubernetes' native RBAC escalation prevention rejected the wildcard Role and
