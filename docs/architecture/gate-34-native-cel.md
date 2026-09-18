# Gate 34 admission mechanism

Status: accepted 2026-09-18

Gate 34 originally named Kyverno or OPA as the unresolved implementation
choice. The cluster already supports and operates Kubernetes
`ValidatingAdmissionPolicy` (`admissionregistration.k8s.io/v1`), including the
host-port and NodePort controls reconciled by `cluster-policies`. Gate 34 is
therefore amended to accept native CEL admission as the third supported
mechanism.

Native CEL is selected because it adds no controller, webhook certificate,
failure domain, or upgrade lifecycle. `failurePolicy: Fail` and bindings scoped
by the `veridex.io/role` namespace label enforce the controls on workload
namespaces. The policies reject wildcard Roles, privileged ClusterRole
bindings, and cross-namespace ServiceAccount subjects. The only permitted
ClusterRole reference is the built-in read-only `view` role; application
permissions are otherwise expressed as namespace-local Roles.

This decision does not weaken Gate 34's evidence requirement. Server-side
negative admission tests, live RBAC inventory, two repeatable policy-test runs,
and retained Hubble evidence remain mandatory before the gate is Verified.
