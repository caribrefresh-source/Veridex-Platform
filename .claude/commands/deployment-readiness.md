# deployment-readiness

Validate a workload is ready for production deployment to the data-plane namespace.

## Inputs
Provide: deployment name, namespace, image tag being deployed.

## 1. Image Tag Pinned
Confirm image is not `:latest` and references a specific version or SHA digest.
```
kubectl get deployment <name> -n <namespace> -o jsonpath='{.spec.template.spec.containers[*].image}'
```
Pass: Specific tag (e.g., `v1.2.3` or `sha256:abc123`).

## 2. Resource Requests + Limits
```
kubectl get deployment <name> -n <namespace> -o json | \
  jq '.spec.template.spec.containers[] | {name: .name, requests: .resources.requests, limits: .resources.limits}'
```
Pass: Both `requests` and `limits` set for CPU and memory.

## 3. Liveness + Readiness Probes
```
kubectl get deployment <name> -n <namespace> -o json | \
  jq '.spec.template.spec.containers[] | {name: .name, liveness: .livenessProbe, readiness: .readinessProbe}'
```
Pass: Both probes defined.

## 4. PodDisruptionBudget
```
kubectl get pdb -n <namespace> | grep <name>
```
Pass: PDB exists with `minAvailable >= 1`.

## 5. Non-Root Security Context
```
kubectl get deployment <name> -n <namespace> -o json | \
  jq '.spec.template.spec | {runAsNonRoot: .securityContext.runAsNonRoot, containers: [.containers[] | {name: .name, runAsUser: .securityContext.runAsUser}]}'
```
Pass: `runAsNonRoot: true` or explicit non-zero `runAsUser`.

## 6. Network Policy Coverage
```
kubectl get networkpolicy -n <namespace> | grep <name>
```
Pass: A NetworkPolicy selects this workload (ingress + egress defined).

## 7. Secret References (not inline values)
```
kubectl get deployment <name> -n <namespace> -o json | \
  jq '[.spec.template.spec.containers[].env[] | select(.value != null and (.value | test("password|secret|token|key"; "i")))]'
```
Pass: No plaintext sensitive values in env. All via `secretKeyRef` or `envFrom.secretRef`.

## 8. Rollout Strategy
```
kubectl get deployment <name> -n <namespace> -o jsonpath='{.spec.strategy}'
```
Verify: `RollingUpdate` with appropriate `maxUnavailable`/`maxSurge` for stateless. `Recreate` acceptable for stateful single-replica workloads.

## 9. KEDA ScaledObject (if applicable)
```
kubectl get scaledobject -n <namespace> | grep <name>
```
If KEDA-managed: confirm triggers (prometheus, nats-jetstream, cron) are configured.

## Report
Go / No-Go per check. Block deployment on any fail in checks 1–7.
