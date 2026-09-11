# kyverno-policy-review

Review Kyverno policy coverage and enforcement status across the cluster.

## 1. Policy Inventory
```
kubectl get clusterpolicy,policy -A -o custom-columns='KIND:.kind,NS:.metadata.namespace,NAME:.metadata.name,MODE:.spec.validationFailureAction,READY:.status.ready'
```
Pass: All policies `ready=true`. Critical policies in `Enforce` mode (not `Audit`).

## 2. Policies in Audit Mode (need to Enforce)
```
kubectl get clusterpolicy -o json | \
  jq '.items[] | select(.spec.validationFailureAction == "Audit") | .metadata.name'
```
Review: Audit-mode policies are not enforcing. Plan migration to Enforce for each.

## 3. Policy Violations
```
kubectl get policyreport -A -o json | \
  jq '[.items[] | .results[] | select(.result == "fail")] | length'
kubectl get policyreport -A -o json | \
  jq '.items[] | select(.summary.fail > 0) | {ns: .metadata.namespace, fail: .summary.fail}'
```
Pass: Zero failures across all namespaces.

## 4. Critical Policy Coverage Check
Verify these policies exist:
- Require resource limits
- Require non-root user
- Require readOnlyRootFilesystem
- Disallow privileged containers
- Disallow hostPath volumes
- Require image tag (no :latest)
- Require pod labels
```
kubectl get clusterpolicy | grep -E 'resource-limit|non-root|readonly|privileged|hostpath|image-tag|require-label'
```

## 5. Exception Audit
```
kubectl get policyexception -A 2>/dev/null
```
Review: Each PolicyException must have a justification comment. No blanket exceptions.

## 6. Policy Sync from ArgoCD
```
kubectl get application -n argocd | grep kyverno
```
Verify: Kyverno ClusterPolicies managed by ArgoCD (tracked in gitops/).

## 7. Admission Webhook Health
```
kubectl get validatingwebhookconfiguration | grep kyverno
kubectl get mutatingwebhookconfiguration | grep kyverno
```
Pass: Kyverno webhooks registered and active.

## 8. Kyverno Pod Health
```
kubectl get pods -n kyverno 2>/dev/null || kubectl get pods -A | grep kyverno
```
Pass: kyverno-admission-controller, kyverno-background-controller, kyverno-reports-controller all Running.

## Report
Policy count by mode, violation count by namespace, missing policy coverage, exception list.
